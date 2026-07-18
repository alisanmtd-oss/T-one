"""Safety gate for data sent to external AI providers.

The gateway is intentionally conservative. Seller-facing AI should get a
small task package, not raw records, credentials, buyer PII, local paths,
supplier costs, training prompts, or cross-tenant data.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from hashlib import sha256
import re
from typing import Any, Mapping


DATA_LEVEL_ORDER = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5}

SAFE_PRODUCT_FIELDS = {
    "product_name",
    "product_title",
    "title",
    "category",
    "keyword",
    "keywords",
    "price",
    "platform",
    "country",
    "region",
    "public_url",
}

FIELD_CATEGORY_RULES: list[tuple[set[str], str, str]] = [
    (
        {
            "api_key",
            "access_token",
            "refresh_token",
            "authorization",
            "bearer",
            "cookie",
            "password",
            "secret",
            "client_secret",
            "credential",
        },
        "credential",
        "L5",
    ),
    (
        {
            "buyer_name",
            "buyer_email",
            "buyer_phone",
            "buyer_address",
            "customer_name",
            "customer_email",
            "customer_phone",
            "customer_address",
            "recipient_name",
            "recipient_email",
            "recipient_phone",
            "recipient_address",
            "shipping_address",
            "billing_address",
        },
        "buyer_pii",
        "L5",
    ),
    (
        {
            "system_prompt",
            "developer_prompt",
            "raw_prompt",
            "chain_of_thought",
            "training_data",
            "strategy_memory_full",
        },
        "internal_prompt",
        "L5",
    ),
    (
        {
            "supplier_cost",
            "factory_cost",
            "floor_price",
            "margin_floor",
            "source_cost",
        },
        "supplier_cost",
        "L3",
    ),
    (
        {
            "raw_payload",
            "raw_html",
            "page_text",
            "local_path",
            "screenshot_path",
            "file_path",
            "debug_log",
            "raw_evidence",
        },
        "raw_evidence",
        "L3",
    ),
    (
        {
            "order_id",
            "tracking_number",
            "shipment_id",
            "refund_id",
            "payment_id",
        },
        "store_execution",
        "L4",
    ),
    (
        {
            "store_id",
            "orders",
            "order_count",
            "sales",
            "gmv",
            "roas",
            "roi",
            "ad_spend",
            "inventory",
            "refund_rate",
            "return_rate",
        },
        "store_metric",
        "L2",
    ),
]

TEXT_PATTERNS: list[tuple[str, str]] = [
    (r"\bsk-[A-Za-z0-9_-]{6,}\b", "credential"),
    (r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|authorization)\s*[:=]\s*[^\s,;]+", "credential"),
    (r"(?i)\bbearer\s+[A-Za-z0-9._-]+", "credential"),
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "buyer_pii"),
    (r"\+?\d[\d\s().-]{7,}\d", "buyer_pii"),
    (r"[A-Za-z]:\\[^\s,;]+", "local_path"),
    (r"/(?:Users|home|mnt|tmp|var|workspace)/[^\s,;]+", "local_path"),
    (r"(?i)\b(?:outputs|documents|desktop)\\[^\s,;]+", "local_path"),
    (r"(?i)(?:supplier|factory|source|floor)[_-]?(?:cost|price)\s*[:=]\s*\$?\d+(?:\.\d+)?", "supplier_cost"),
    (r"(?i)(?:api_key|token|access_token|refresh_token)=[^&\s]+", "credential"),
]

SENSITIVE_CATEGORIES = {
    "credential",
    "buyer_pii",
    "internal_prompt",
    "supplier_cost",
    "raw_evidence",
    "store_execution",
    "local_path",
    "legal_payment",
}

MODEL_OUTPUT_BLOCK_PATTERNS: list[tuple[str, str]] = [
    (
        r"(?i)\b(i\s+)?(already|have)\s+(published|posted|changed\s+the\s+price|updated\s+the\s+price|refunded|shipped|fulfilled|authorized|launched|uploaded|sent|contacted|deleted|deactivated)\b",
        "execution_claim",
    ),
    (
        r"(已经|已|我已|系统已|AI已|机器人已).{0,8}(发布|上架|改价|修改价格|退款|退货|发货|授权|投放|开广告|联系达人|上传|删除|下架|报名活动)",
        "execution_claim",
    ),
    (r"(绕过|规避).{0,12}(审核|验证|平台|风控|封禁|二审|侵权)", "bypass_claim"),
]


def _normalize_level(level: str | None, default: str = "L0") -> str:
    if not level:
        return default
    normalized = str(level).upper().strip()
    return normalized if normalized in DATA_LEVEL_ORDER else default


def _hash_value(value: str) -> str:
    return sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:12]


@dataclass(frozen=True)
class ProviderPolicy:
    name: str = "unknown"
    trust_level: str = "unknown"
    max_data_level: str = "L0"
    allow_onboarding: bool = False
    allow_store_execution: bool = False
    policy_review_status: str = "pending"
    allowed_tasks: tuple[str, ...] = ()


DEFAULT_PROVIDER_POLICIES: dict[str, ProviderPolicy] = {
    "unknown": ProviderPolicy(),
    "local": ProviderPolicy(
        name="local",
        trust_level="internal",
        max_data_level="L3",
        allow_onboarding=True,
        policy_review_status="approved",
    ),
    "openai": ProviderPolicy(
        name="openai",
        trust_level="official_paid",
        max_data_level="L2",
        allow_onboarding=False,
        policy_review_status="approved",
    ),
    "deepseek": ProviderPolicy(
        name="deepseek",
        trust_level="third_party",
        max_data_level="L1",
        allow_onboarding=False,
        policy_review_status="pending",
    ),
    "gemini": ProviderPolicy(
        name="gemini",
        trust_level="third_party",
        max_data_level="L1",
        allow_onboarding=False,
        policy_review_status="pending",
    ),
}


def normalize_provider_policy(policy: Mapping[str, Any] | ProviderPolicy | None, *, name: str = "unknown") -> dict[str, Any]:
    if isinstance(policy, ProviderPolicy):
        data = asdict(policy)
    elif isinstance(policy, Mapping):
        data = dict(policy)
    else:
        data = {}
    data.setdefault("name", name)
    data.setdefault("trust_level", "unknown")
    data["max_data_level"] = _normalize_level(data.get("max_data_level"), "L0")
    data.setdefault("allow_onboarding", False)
    data.setdefault("allow_store_execution", False)
    data.setdefault("policy_review_status", "pending")
    data.setdefault("allowed_tasks", [])
    return data


def provider_allows_data_level(policy: Mapping[str, Any] | ProviderPolicy | None, requested_level: str) -> bool:
    normalized = normalize_provider_policy(policy)
    requested = _normalize_level(requested_level, "L0")
    return DATA_LEVEL_ORDER[requested] <= DATA_LEVEL_ORDER[normalized["max_data_level"]]


def provider_policy(provider: str | None) -> ProviderPolicy:
    key = (provider or "unknown").lower().strip()
    return DEFAULT_PROVIDER_POLICIES.get(key, DEFAULT_PROVIDER_POLICIES["unknown"])


def classify_field(field_name: str) -> dict[str, str]:
    name = (field_name or "").lower().strip()
    if name in SAFE_PRODUCT_FIELDS:
        return {"category": "public_product", "level": "L1"}
    for needles, category, level in FIELD_CATEGORY_RULES:
        if name in needles or any(needle in name for needle in needles if len(needle) > 5):
            return {"category": category, "level": level}
    return {"category": "general", "level": "L1"}


def _field_allowed(field_name: str, max_data_level: str) -> bool:
    info = classify_field(field_name)
    category = info["category"]
    if category in SENSITIVE_CATEGORIES:
        return False
    return DATA_LEVEL_ORDER[info["level"]] <= DATA_LEVEL_ORDER[_normalize_level(max_data_level, "L0")]


@dataclass
class RedactionResult:
    text: str
    blocked_categories: list[str] = field(default_factory=list)
    matched_needles: list[str] = field(default_factory=list)


def redact_text_for_model(text: Any, *, max_data_level: str = "L1", task: str | None = None) -> RedactionResult:
    del task
    if text is None:
        return RedactionResult("")
    safe_text = str(text)
    blocked: list[str] = []
    matched_hashes: list[str] = []
    for pattern, category in TEXT_PATTERNS:
        matches = list(re.finditer(pattern, safe_text))
        if not matches:
            continue
        blocked.append(category)
        matched_hashes.extend(_hash_value(match.group(0)) for match in matches[:10])
        replacement = f"[REDACTED_{category.upper()}]"
        safe_text = re.sub(pattern, replacement, safe_text)
    if DATA_LEVEL_ORDER[_normalize_level(max_data_level, "L1")] < DATA_LEVEL_ORDER["L3"]:
        # Raw local paths are not useful to external models even when hidden in long text.
        safe_text = safe_text.replace("secret.csv", "[REDACTED_FILE]")
    return RedactionResult(
        text=safe_text,
        blocked_categories=sorted(set(blocked)),
        matched_needles=sorted(set(matched_hashes)),
    )


def _record_to_mapping(record: Any) -> dict[str, Any]:
    if isinstance(record, Mapping):
        return dict(record)
    if hasattr(record, "to_dict") and callable(record.to_dict):
        return dict(record.to_dict())
    if is_dataclass(record):
        return asdict(record)
    if hasattr(record, "__dict__"):
        return dict(record.__dict__)
    raise TypeError(f"Unsupported record type for gateway summary: {type(record)!r}")


def _compact_score(score: Any) -> Any:
    if not isinstance(score, Mapping):
        return score if isinstance(score, (int, float, str, bool)) or score is None else None
    safe: dict[str, Any] = {}
    for key, value in score.items():
        key_text = str(key).lower()
        if any(word in key_text for word in ("debug", "raw", "internal", "private", "cost")):
            continue
        if isinstance(value, (int, float, str, bool)) or value is None:
            safe[str(key)] = value
    return safe


@dataclass
class SafeRecordSummary:
    record_id: str
    record_type: str
    source: str
    created_at: str
    allowed_fields: dict[str, Any]
    score: Any
    blocked_fields: list[str]
    blocked_categories: list[str]

    @property
    def fields(self) -> dict[str, Any]:
        return self.allowed_fields

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "record_type": self.record_type,
            "source": self.source,
            "created_at": self.created_at,
            "fields": self.allowed_fields,
            "score": self.score,
            "blocked_fields": self.blocked_fields,
            "blocked_categories": self.blocked_categories,
        }

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)


def safe_record_summary(
    record: Any,
    *,
    task: str | None = None,
    audience: str | None = None,
    max_data_level: str = "L1",
) -> SafeRecordSummary:
    del task, audience
    data = _record_to_mapping(record)
    fields = data.get("fields")
    if not isinstance(fields, Mapping):
        fields = {k: v for k, v in data.items() if k not in {"record_id", "record_type", "source", "created_at", "score"}}

    allowed: dict[str, Any] = {}
    blocked_fields: list[str] = []
    blocked_categories: list[str] = []
    for key, value in fields.items():
        info = classify_field(str(key))
        if not _field_allowed(str(key), max_data_level):
            blocked_fields.append(str(key))
            blocked_categories.append(info["category"])
            continue
        safe_value = _sanitize_value_for_model(value, str(key), max_data_level, blocked_fields, blocked_categories)
        if safe_value is not _DROP:
            allowed[str(key)] = safe_value

    return SafeRecordSummary(
        record_id=str(data.get("record_id", "")),
        record_type=str(data.get("record_type", "")),
        source=str(data.get("source", "")),
        created_at=str(data.get("created_at", "")),
        allowed_fields=allowed,
        score=_compact_score(data.get("score")),
        blocked_fields=sorted(set(blocked_fields)),
        blocked_categories=sorted(set(blocked_categories)),
    )


class _DropValue:
    pass


_DROP = _DropValue()


def _sanitize_value_for_model(
    value: Any,
    field_name: str,
    max_data_level: str,
    blocked_fields: list[str],
    blocked_categories: list[str],
) -> Any:
    info = classify_field(field_name)
    if not _field_allowed(field_name, max_data_level):
        blocked_fields.append(field_name)
        blocked_categories.append(info["category"])
        return _DROP
    if isinstance(value, str):
        redacted = redact_text_for_model(value, max_data_level=max_data_level)
        blocked_categories.extend(redacted.blocked_categories)
        return redacted.text
    if isinstance(value, Mapping):
        nested: dict[str, Any] = {}
        for key, nested_value in value.items():
            nested_safe = _sanitize_value_for_model(
                nested_value,
                str(key),
                max_data_level,
                blocked_fields,
                blocked_categories,
            )
            if nested_safe is not _DROP:
                nested[str(key)] = nested_safe
        return nested
    if isinstance(value, list):
        items: list[Any] = []
        for item in value[:50]:
            item_safe = _sanitize_value_for_model(item, field_name, max_data_level, blocked_fields, blocked_categories)
            if item_safe is not _DROP:
                items.append(item_safe)
        return items
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:500]


@dataclass
class ModelRequestPackage:
    provider: str
    task: str
    requested_data_level: str
    effective_data_level: str
    prompt: str
    safe_context: dict[str, Any]
    blocked_fields: list[str]
    blocked_categories: list[str]
    policy: dict[str, Any]

    @property
    def context(self) -> dict[str, Any]:
        context = self.safe_context.get("context", {})
        return context if isinstance(context, dict) else {}

    @property
    def payload(self) -> dict[str, Any]:
        payload = self.safe_context.get("payload", {})
        return payload if isinstance(payload, dict) else {}

    @property
    def provider_policy(self) -> dict[str, Any]:
        return self.policy

    @property
    def blocked_fields_summary(self) -> dict[str, Any]:
        return {
            "fields": self.blocked_fields,
            "categories": self.blocked_categories,
        }


def _sanitize_mapping(mapping: Mapping[str, Any] | None, max_data_level: str) -> tuple[dict[str, Any], list[str], list[str]]:
    if not mapping:
        return {}, [], []
    safe: dict[str, Any] = {}
    blocked_fields: list[str] = []
    blocked_categories: list[str] = []
    for key, value in mapping.items():
        if key == "requested_data_level":
            continue
        safe_value = _sanitize_value_for_model(value, str(key), max_data_level, blocked_fields, blocked_categories)
        if safe_value is not _DROP:
            safe[str(key)] = safe_value
    return safe, sorted(set(blocked_fields)), sorted(set(blocked_categories))


def build_model_request_package(
    *,
    task: str,
    provider: str = "unknown",
    prompt: str = "",
    context: Mapping[str, Any] | None = None,
    requested_data_level: str = "L1",
    provider_policy: Mapping[str, Any] | ProviderPolicy | None = None,
    payload: Mapping[str, Any] | None = None,
) -> ModelRequestPackage:
    explicit_policy = provider_policy is not None
    policy = normalize_provider_policy(provider_policy or globals()["provider_policy"](provider), name=provider)
    if payload and payload.get("requested_data_level"):
        requested_data_level = str(payload["requested_data_level"])
    requested = _normalize_level(requested_data_level, "L1")

    if not provider_allows_data_level(policy, requested):
        if explicit_policy:
            raise ValueError(
                f"Provider policy only allows {policy['max_data_level']}, requested {requested}."
            )
        effective = policy["max_data_level"]
    else:
        effective = requested

    redacted_prompt = redact_text_for_model(prompt, max_data_level=effective)
    safe_context, context_blocked_fields, context_blocked_categories = _sanitize_mapping(context, effective)
    safe_payload, payload_blocked_fields, payload_blocked_categories = _sanitize_mapping(payload, effective)

    return ModelRequestPackage(
        provider=str(policy.get("name") or provider),
        task=task,
        requested_data_level=requested,
        effective_data_level=effective,
        prompt=redacted_prompt.text,
        safe_context={"context": safe_context, "payload": safe_payload},
        blocked_fields=sorted(set(context_blocked_fields + payload_blocked_fields)),
        blocked_categories=sorted(
            set(redacted_prompt.blocked_categories + context_blocked_categories + payload_blocked_categories)
        ),
        policy=policy,
    )


@dataclass
class ModelOutputScan:
    text: str
    is_safe: bool
    severity: str
    blocked_categories: list[str]
    requires_confirmation_item: bool
    seller_safe_rewrite: str | None = None

    @property
    def safe(self) -> bool:
        return self.is_safe

    @property
    def categories(self) -> list[str]:
        return self.blocked_categories


def scan_model_output(text: Any) -> ModelOutputScan:
    original = "" if text is None else str(text)
    categories: list[str] = []
    for pattern, category in MODEL_OUTPUT_BLOCK_PATTERNS:
        if re.search(pattern, original):
            categories.append(category)

    redacted = redact_text_for_model(original, max_data_level="L1")
    alias_map = {
        "credential": "secret_leak",
        "buyer_pii": "pii_leak",
        "local_path": "local_path",
        "raw_evidence": "local_path",
        "supplier_cost": "supplier_cost",
    }
    categories.extend(alias_map.get(category, category) for category in redacted.blocked_categories)
    categories = sorted(set(categories))

    unsafe = bool(categories)
    requires_confirmation = "execution_claim" in categories or "bypass_claim" in categories
    rewrite = None
    if unsafe:
        rewrite = (
            "Nothing has changed. I prepared a draft/checklist only. Any publish, price, refund, "
            "fulfillment, authorization, upload, or ad action must enter the confirmation queue first."
        )
    return ModelOutputScan(
        text=redacted.text,
        is_safe=not unsafe,
        severity="block" if unsafe else "ok",
        blocked_categories=categories,
        requires_confirmation_item=requires_confirmation,
        seller_safe_rewrite=rewrite,
    )


def write_audit_stub(package: ModelRequestPackage, output_scan: ModelOutputScan | None = None) -> dict[str, Any]:
    return {
        "provider": package.provider,
        "task": package.task,
        "requested_data_level": package.requested_data_level,
        "effective_data_level": package.effective_data_level,
        "blocked_fields": package.blocked_fields,
        "blocked_categories": package.blocked_categories,
        "output_safe": None if output_scan is None else output_scan.safe,
        "output_categories": [] if output_scan is None else output_scan.categories,
    }
