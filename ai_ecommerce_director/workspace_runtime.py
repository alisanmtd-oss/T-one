from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .workspace_schema import (
    find_store_in_project,
    find_task_context,
    iter_project_stores,
    iter_project_tasks,
    normalize_workspace_config,
)
from .credential_store import SAFE_CREDENTIAL_REF
from .global_commerce_dimensions import (
    commerce_model_routing_dimensions,
    normalize_commerce_model_selection,
)
from .seller_mode_skill_packs import load_seller_mode_skill_pack_registry
from .store_execution_scope import build_store_execution_scope, make_scope_key


RUNTIME_PATH = Path("data") / "workspace_runtime.json"
PROJECTS_DIRECTORY = Path("projects")
PROJECT_FOLDER_SUBDIRECTORIES = (
    "inputs",
    "attachments",
    "knowledge",
    "memory",
    "runs",
    "results",
    "receipts",
    "tasks",
)
TASKS_DIRECTORY = Path("tasks")
TASK_FOLDER_SUBDIRECTORIES = (
    "inputs",
    "attachments",
    "runs",
    "results",
    "receipts",
    "memory",
)
MULTI_AI_PATH = Path("config") / "multi_ai.json"
CAPABILITY_PACK_REGISTRY_PATH = Path("config") / "capability_pack_registry.json"
PLATFORM_ADAPTER_REGISTRY_PATH = Path("config") / "platform_adapter_registry.json"
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
TOOLKIT_KEYS = ("plugins", "skills", "agents")
SUPPORTED_BROWSER_PROVIDERS = {"bitbrowser", "ziniao", "zhanfu", "chrome"}
STORE_CONNECTION_INPUT_FIELDS = {
    "browser_provider",
    "browser_profile_id",
    "browser_profile_sequence",
    "browser_profile_seq",
    "credential_ref",
    "erp_connector_id",
}
STORE_CONNECTION_PERSISTED_FIELDS = (
    "browser_provider",
    "browser_profile_id",
    "browser_profile_sequence",
    "credential_ref",
    "erp_connector_id",
)
STORE_CONNECTION_METADATA_FIELDS = (
    "connection_updated_at",
    "connection_updated_by",
)
RUNTIME_PLAINTEXT_SECRET_FIELDS = {
    "access_key",
    "access_token",
    "api_key",
    "authorization",
    "client_secret",
    "cookie",
    "id_token",
    "password",
    "passphrase",
    "refresh_token",
    "secret_key",
    "session_cookie",
}
_LOCK = threading.RLock()
AUTO_MODEL_PROVIDER_VALUES = {"", "auto", "automatic", "自动路由"}

PRIMARY_STORE_CONVERSATION = "primary"
SECONDARY_STORE_CONVERSATION = "secondary"
INDEPENDENT_PROJECT_CONVERSATION = "independent"
UNBOUND_STORE_PLACEHOLDER_SUBTITLES = {
    "独立对话 · 未连接店铺",
    "项目工作流 · 待配置执行资料",
}


def _is_unbound_store_placeholder(task: dict[str, Any]) -> bool:
    """Return True for generic store placeholders without a real binding."""

    return (
        str(task.get("platform") or "general").strip().lower() == "general"
        and not str(task.get("store_binding_id") or "").strip()
        and not str(task.get("store_id") or "").strip()
        and str(task.get("subtitle") or "").strip()
        in UNBOUND_STORE_PLACEHOLDER_SUBTITLES
    )


def _drop_unbound_store_placeholders(workspace: dict[str, Any]) -> None:
    """Keep placeholder conversations out of business and store projections."""

    for project in workspace.get("projects", []):
        if not isinstance(project, dict):
            continue
        for key in ("workstreams", "tasks"):
            items = project.get(key)
            if isinstance(items, list):
                project[key] = [
                    item
                    for item in items
                    if not (
                        isinstance(item, dict)
                        and _is_unbound_store_placeholder(item)
                    )
                ]
    standalone = workspace.get("standalone_tasks")
    if isinstance(standalone, list):
        workspace["standalone_tasks"] = [
            item
            for item in standalone
            if not (
                isinstance(item, dict) and _is_unbound_store_placeholder(item)
            )
        ]


def _looks_like_raw_credential_value(value: str) -> bool:
    compact = "".join(str(value or "").strip().split()).lower()
    return compact.startswith(
        (
            "sk-",
            "sk_",
            "akia",
            "asya",
            "xoxb-",
            "xoxp-",
            "ya29.",
            "bearer",
            "eyj",
        )
    )


def _is_safe_credential_reference(value: str) -> bool:
    reference = str(value or "").strip().lower()
    return bool(
        reference
        and SAFE_CREDENTIAL_REF.fullmatch(reference)
        and (":" in reference or "/" in reference)
        and not _looks_like_raw_credential_value(reference)
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _verified_browser_store_evidence(
    root: Path,
    payload: dict[str, Any],
    *,
    platform: str,
    country_site: str,
    external_id: str,
    browser_profile_sequence: int,
) -> dict[str, Any]:
    """Validate one local, read-only browser receipt before claiming connection."""

    evidence_ref = str(payload.get("connection_evidence_ref") or "").strip()
    if not evidence_ref:
        return {}
    relative = Path(evidence_ref)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("店铺连接证据必须位于当前工作区内。")
    evidence_path = (root / relative).resolve()
    try:
        evidence_path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("店铺连接证据不在当前工作区内。") from exc
    evidence = _load_json(evidence_path)
    if not evidence or not evidence_path.is_file():
        raise ValueError("店铺连接证据不存在或不是有效 JSON。")
    if int(evidence.get("external_store_write_actions") or 0) != 0:
        raise ValueError("只读连接证据包含外部店铺写入，不能用于本次绑定。")
    if evidence.get("amazon_touched") is not False:
        raise ValueError("连接证据未明确证明 Amazon 保持未触碰。")
    expected_origins = {"shein": "https://sellerhub.shein.com"}
    expected_origin = expected_origins.get(platform)
    if not expected_origin:
        raise ValueError("当前平台还没有可验证的只读浏览器连接协议。")
    target = next(
        (
            item
            for item in evidence.get("targets", [])
            if isinstance(item, dict)
            and int(item.get("profile_sequence") or 0) == browser_profile_sequence
            and external_id in [str(value) for value in item.get("store_ids", [])]
        ),
        None,
    )
    if target is None:
        raise ValueError("连接证据与当前浏览器环境或店铺编号不匹配。")
    if str(target.get("origin") or "") != expected_origin:
        raise ValueError("连接证据不是当前平台的官方商家后台。")
    if target.get("login_prompt_visible") is not False:
        raise ValueError("当前店铺仍显示登录提示，不能标记为已连接。")
    if target.get("captcha_or_mfa_visible") is not False:
        raise ValueError("当前店铺需要验证码或 MFA，必须由负责人接管。")
    if target.get("product_list_visible") is not True:
        raise ValueError("当前会话没有读到真实商品列表。")
    if country_site != "US" or str(target.get("store_mode_visible") or "") != "platform_self_operated":
        raise ValueError("连接证据的国家站点或店铺模式与当前绑定不匹配。")
    return {
        "status": "verified_read_only",
        "evidence_ref": relative.as_posix(),
        "checked_at": str(evidence.get("checked_at") or "")[:80],
        "profile_sequence": browser_profile_sequence,
        "profile_name": str(target.get("profile_name") or "")[:120],
        "external_id": external_id,
        "origin": expected_origin,
        "page_title": str(target.get("title") or "")[:120],
        "read_capability": "product_list",
        "external_store_write_actions": 0,
    }


def _verified_workspace_connector_script(root: Path, value: Any) -> str:
    script_ref = str(value or "").strip()
    if not script_ref:
        return ""
    relative = Path(script_ref)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("店铺页面连接器必须位于当前工作区内。")
    script = (root / relative).resolve()
    try:
        script.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("店铺页面连接器不在当前工作区内。") from exc
    if not script.is_file():
        raise ValueError("店铺页面连接器不存在。")
    return relative.as_posix()


def _fulfillment_route_snapshot(root: Path, route_id: str) -> dict[str, Any]:
    clean_route_id = str(route_id or "").strip().lower()
    if not clean_route_id:
        return {}
    registry = _load_json(root / PLATFORM_ADAPTER_REGISTRY_PATH)
    adapters = registry.get("adapters")
    if not isinstance(adapters, list):
        raise ValueError("履约路线注册表当前不可用。")
    for adapter in adapters:
        if not isinstance(adapter, dict):
            continue
        route_policy = adapter.get("fulfillment_route_policy")
        if not isinstance(route_policy, dict):
            continue
        route = route_policy.get(clean_route_id)
        if not isinstance(route, dict):
            continue
        return {
            "fulfillment_route_id": clean_route_id,
            "fulfillment_platform": str(adapter.get("platform") or "").strip().lower()[:40],
            "fulfillment_store_mode": str(route.get("store_mode") or "").strip()[:80],
            "warehouse_country": str(route.get("warehouse_country") or "").strip().upper()[:8],
            "ship_from_country": str(route.get("ship_from_country") or "").strip().upper()[:8],
            "fulfillment_route_verified_sites": [
                str(site or "").strip().upper()[:8]
                for site in route.get("verified_sites", [])
                if str(site or "").strip()
            ][:40],
            "fulfillment_route_other_site_status": str(
                route.get("other_site_status") or ""
            ).strip()[:160],
            "fulfillment_route_execution_status": str(
                route.get("execution_status") or ""
            ).strip()[:120],
            "fulfillment_route_source": PLATFORM_ADAPTER_REGISTRY_PATH.as_posix(),
        }
    raise ValueError("所选履约路线不在当前已核验注册表中。")


def _runtime_path(root: Path) -> Path:
    return root / RUNTIME_PATH


def _load_runtime(root: Path) -> dict[str, Any]:
    payload = _load_json(_runtime_path(root))
    projects = payload.get("projects") if isinstance(payload.get("projects"), list) else []
    stores = payload.get("stores") if isinstance(payload.get("stores"), list) else []
    tasks = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
    configurations = (
        payload.get("task_configurations")
        if isinstance(payload.get("task_configurations"), dict)
        else {}
    )
    raw_sidebar_metadata = (
        payload.get("sidebar_metadata")
        if isinstance(payload.get("sidebar_metadata"), dict)
        else {}
    )
    sidebar_metadata = {
        kind: {
            str(item_id).strip().lower(): deepcopy(record)
            for item_id, record in (
                raw_sidebar_metadata.get(kind)
                if isinstance(raw_sidebar_metadata.get(kind), dict)
                else {}
            ).items()
            if SAFE_ID.fullmatch(str(item_id).strip().lower())
            and isinstance(record, dict)
        }
        for kind in ("projects", "tasks")
    }
    raw_commerce_profiles = (
        payload.get("commerce_profiles")
        if isinstance(payload.get("commerce_profiles"), dict)
        else {}
    )
    commerce_profiles = {
        "projects": {
            str(project_id).strip().lower(): deepcopy(record)
            for project_id, record in (
                raw_commerce_profiles.get("projects")
                if isinstance(raw_commerce_profiles.get("projects"), dict)
                else {}
            ).items()
            if SAFE_ID.fullmatch(str(project_id).strip().lower())
            and isinstance(record, dict)
        }
    }
    runtime = deepcopy(payload)
    try:
        schema_version = max(2, int(payload.get("schema_version") or 2))
    except (TypeError, ValueError):
        schema_version = 2
    runtime.update({
        "schema_version": schema_version,
        "projects": [deepcopy(item) for item in projects if isinstance(item, dict)],
        "stores": [deepcopy(item) for item in stores if isinstance(item, dict)],
        "tasks": [deepcopy(item) for item in tasks if isinstance(item, dict)],
        "task_configurations": {
            str(key): dict(value)
            for key, value in configurations.items()
            if isinstance(value, dict)
        },
        "sidebar_metadata": sidebar_metadata,
        "commerce_profiles": commerce_profiles,
        "updated_at": str(payload.get("updated_at") or ""),
    })
    return runtime


def _sanitize_connection_override_record(record: dict[str, Any]) -> dict[str, Any]:
    clean = {
        "id": str(record.get("id") or "").strip().lower(),
        "project_id": str(record.get("project_id") or "").strip().lower(),
        "connection_override_only": True,
    }
    clean.update(_connection_override_patch(record, strict=False))
    for key in STORE_CONNECTION_METADATA_FIELDS:
        if key in record:
            clean[key] = str(record.get(key) or "")[:160]
    return clean


def _strip_plaintext_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]+", "_", str(key).strip().lower()).strip("_")
            if normalized in RUNTIME_PLAINTEXT_SECRET_FIELDS:
                continue
            if normalized == "credential_ref":
                reference = str(item or "").strip().lower()
                clean[str(key)] = reference if not reference or _is_safe_credential_reference(reference) else ""
                continue
            clean[str(key)] = _strip_plaintext_secrets(item)
        return clean
    if isinstance(value, list):
        return [_strip_plaintext_secrets(item) for item in value]
    return deepcopy(value)


def _write_runtime(root: Path, payload: dict[str, Any]) -> None:
    path = _runtime_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = deepcopy(payload) if isinstance(payload, dict) else {}
    try:
        clean["schema_version"] = max(2, int(clean.get("schema_version") or 2))
    except (TypeError, ValueError):
        clean["schema_version"] = 2
    clean["projects"] = [
        deepcopy(item) for item in clean.get("projects", []) if isinstance(item, dict)
    ]
    clean["stores"] = [
        _sanitize_connection_override_record(item)
        if item.get("connection_override_only") is True
        else deepcopy(item)
        for item in clean.get("stores", [])
        if isinstance(item, dict)
    ]
    clean["tasks"] = [
        deepcopy(item) for item in clean.get("tasks", []) if isinstance(item, dict)
    ]
    clean["task_configurations"] = {
        str(key): deepcopy(value)
        for key, value in (clean.get("task_configurations") or {}).items()
        if isinstance(value, dict)
    } if isinstance(clean.get("task_configurations"), dict) else {}
    raw_sidebar_metadata = (
        clean.get("sidebar_metadata")
        if isinstance(clean.get("sidebar_metadata"), dict)
        else {}
    )
    clean["sidebar_metadata"] = {
        kind: {
            str(item_id).strip().lower(): deepcopy(record)
            for item_id, record in (
                raw_sidebar_metadata.get(kind)
                if isinstance(raw_sidebar_metadata.get(kind), dict)
                else {}
            ).items()
            if SAFE_ID.fullmatch(str(item_id).strip().lower())
            and isinstance(record, dict)
        }
        for kind in ("projects", "tasks")
    }
    raw_commerce_profiles = (
        clean.get("commerce_profiles")
        if isinstance(clean.get("commerce_profiles"), dict)
        else {}
    )
    clean["commerce_profiles"] = {
        "projects": {
            str(project_id).strip().lower(): deepcopy(record)
            for project_id, record in (
                raw_commerce_profiles.get("projects")
                if isinstance(raw_commerce_profiles.get("projects"), dict)
                else {}
            ).items()
            if SAFE_ID.fullmatch(str(project_id).strip().lower())
            and isinstance(record, dict)
        }
    }
    clean["updated_at"] = _now_iso()
    clean = _strip_plaintext_secrets(clean)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _connection_override_patch(
    payload: dict[str, Any], *, strict: bool
) -> dict[str, Any]:
    """Normalize only user-settable connection fields.

    Key absence means inherit, key presence with a value means set, and key
    presence with an empty value means explicitly clear the inherited value.
    """

    patch: dict[str, Any] = {}
    if "browser_provider" in payload:
        provider = str(payload.get("browser_provider") or "").strip().lower()
        if provider and provider not in SUPPORTED_BROWSER_PROVIDERS:
            if strict:
                raise ValueError("所选浏览器环境不受支持。")
        else:
            patch["browser_provider"] = provider

    if "browser_profile_id" in payload:
        profile_id = " ".join(str(payload.get("browser_profile_id") or "").split())[:160]
        if profile_id and _looks_like_raw_credential_value(profile_id):
            if strict:
                raise ValueError("浏览器环境编号不能包含 API Key、Token 或密码。")
        else:
            patch["browser_profile_id"] = profile_id

    sequence_keys = [
        key
        for key in ("browser_profile_sequence", "browser_profile_seq")
        if key in payload
    ]
    if sequence_keys:
        parsed: list[int] = []
        for key in sequence_keys:
            try:
                value = int(payload.get(key) or 0)
            except (TypeError, ValueError):
                if strict:
                    raise ValueError("浏览器环境序号必须是整数。") from None
                parsed = []
                break
            if value < 0:
                if strict:
                    raise ValueError("浏览器环境序号不能小于 0。")
                parsed = []
                break
            parsed.append(value)
        if parsed:
            if len(set(parsed)) > 1:
                if strict:
                    raise ValueError("浏览器环境序号字段互相冲突。")
            else:
                patch["browser_profile_sequence"] = parsed[0]

    if "credential_ref" in payload:
        credential_ref = str(payload.get("credential_ref") or "").strip().lower()
        if credential_ref and not _is_safe_credential_reference(credential_ref):
            if strict:
                raise ValueError(
                    "这里不能填写 API Key、Token、密码或明文密钥；请填写本地凭据库引用。"
                )
        else:
            patch["credential_ref"] = credential_ref

    if "erp_connector_id" in payload:
        connector_id = str(payload.get("erp_connector_id") or "").strip().lower()
        if connector_id and not SAFE_ID.fullmatch(connector_id):
            if strict:
                raise ValueError("ERP 连接器编号格式无效。")
        else:
            patch["erp_connector_id"] = connector_id

    if patch.get("browser_provider") == "":
        patch.setdefault("browser_profile_id", "")
        patch.setdefault("browser_profile_sequence", 0)
    return patch


def _apply_connection_override(store: dict[str, Any], record: dict[str, Any]) -> bool:
    patch = _connection_override_patch(record, strict=False)
    for key, value in patch.items():
        store[key] = deepcopy(value)
    for key in STORE_CONNECTION_METADATA_FIELDS:
        if key in record:
            store[key] = str(record.get(key) or "")[:160]
    return bool(
        set(patch).intersection(
            {"browser_provider", "browser_profile_id", "browser_profile_sequence"}
        )
    )


def _recompute_store_connection_state(
    workspace: dict[str, Any],
    project: dict[str, Any],
    channel: dict[str, Any],
    store: dict[str, Any],
    *,
    browser_override_applied: bool = False,
) -> None:
    previous_binding_status = str(store.get("browser_binding_status") or "").strip()
    verification = (
        store.get("connection_verification")
        if isinstance(store.get("connection_verification"), dict)
        else {}
    )
    provider = str(store.get("browser_provider") or "").strip().lower()
    profile_id = " ".join(str(store.get("browser_profile_id") or "").split())[:160]
    raw_profile_sequence = store.get("browser_profile_sequence")
    if raw_profile_sequence is None or raw_profile_sequence == "":
        raw_profile_sequence = store.get("browser_profile_seq") or 0
    try:
        profile_sequence = int(raw_profile_sequence or 0)
    except (TypeError, ValueError):
        profile_sequence = 0
    if profile_sequence < 0:
        profile_sequence = 0
    browser_identity = profile_id or (str(profile_sequence) if profile_sequence else "")
    project_id = str(project.get("id") or "").strip().lower()
    store_binding_id = str(store.get("id") or "").strip().lower()
    browser_environment_id = (
        f"browser:{provider}:{browser_identity}" if provider and browser_identity else ""
    )
    previous_execution_identity = str(store.get("execution_identity_id") or "").strip()
    if provider and browser_identity:
        # A browser profile/window is only the shared network/session container.
        # The executable identity remains unique to the selected project/store so
        # multiple platforms or stores can reuse one environment without making
        # their queues, receipts, credentials or writes interchangeable.
        execution_identity_id = (
            f"{browser_environment_id}:project:{project_id}:store:{store_binding_id}"
        )
    elif browser_override_applied and previous_execution_identity.startswith("browser:"):
        execution_identity_id = ""
    else:
        execution_identity_id = previous_execution_identity

    credential_ref = str(store.get("credential_ref") or "").strip().lower()
    if credential_ref and not _is_safe_credential_reference(credential_ref):
        credential_ref = ""
    erp_connector_id = str(store.get("erp_connector_id") or "").strip().lower()
    if erp_connector_id and not SAFE_ID.fullmatch(erp_connector_id):
        erp_connector_id = ""
    execution_domains = [
        str(item).strip().lower()[:80]
        for item in store.get("execution_domains", [])
        if str(item).strip()
    ] if isinstance(store.get("execution_domains"), list) else []
    if not execution_domains:
        execution_domains = ["seller_center"]
    ad_account_identity = str(store.get("ad_account_identity") or "").strip()[:200]

    store.update(
        {
            "browser_provider": provider,
            "browser_profile_id": profile_id,
            "browser_profile_sequence": profile_sequence,
            "browser_profile_seq": profile_sequence,
            "browser_binding_status": (
                "verified_read_only"
                if provider
                and browser_identity
                and previous_binding_status == "verified_read_only"
                and verification.get("status") == "verified_read_only"
                else "profile_selected" if provider and browser_identity else "unbound"
            ),
            "browser_environment_id": browser_environment_id,
            "browser_environment_sharing": (
                "shared_profile_many_stores_store_scoped_actions"
                if browser_environment_id
                else "unbound"
            ),
            "execution_identity_id": execution_identity_id,
            "credential_ref": credential_ref,
            "erp_connector_id": erp_connector_id,
            "execution_domains": execution_domains,
        }
    )
    previous_ref_type = str(store.get("credential_ref_type") or "").strip()
    if credential_ref:
        store["credential_ref_type"] = "store_api_bundle"
    elif execution_identity_id.startswith("browser:"):
        store["credential_ref_type"] = "browser_profile"
    elif previous_ref_type in {"store_api_bundle", "browser_profile"}:
        store["credential_ref_type"] = ""
    else:
        store["credential_ref_type"] = previous_ref_type

    platform = str(channel.get("platform") or store.get("platform") or "").lower()
    country_site = str(
        channel.get("country_site") or store.get("country_site") or "GLOBAL"
    ).upper()
    commerce_mode = str(store.get("store_model") or "").strip().lower()
    route_key = ":".join(
        (
            re.sub(r"[\s-]+", "_", platform),
            country_site,
            re.sub(r"[\s-]+", "_", commerce_mode),
        )
    )
    scope_base = {
        "tenant_id": str(workspace.get("workspace_id") or "default-workspace"),
        "project_id": project_id,
        "store_binding_id": store_binding_id,
        "execution_identity_ref": execution_identity_id,
        "platform": platform,
        "country_site": country_site,
        "commerce_mode": commerce_mode,
        "ownership": str(store.get("ownership") or "").lower(),
        "credential_ref": credential_ref,
        "ad_account_identity": ad_account_identity,
    }
    scopes: list[dict[str, Any]] = []
    for domain in execution_domains:
        scope = build_store_execution_scope({**scope_base, "domain": domain}).to_dict()
        scope["commerce_mode"] = commerce_mode
        scope["route_key"] = route_key
        scope["scope_key"] = make_scope_key(
            route_key=route_key,
            tenant_id=scope["tenant_id"],
            project_id=scope["project_id"],
            store_binding_id=scope["store_binding_id"],
            execution_identity_ref=scope["execution_identity_ref"],
            ownership=scope["ownership"],
            domain=scope["domain"],
            ad_account_identity=scope["ad_account_identity"],
        )
        scopes.append(scope)
    store["execution_scopes"] = scopes
    store["route_key"] = route_key
    store["scope_status"] = (
        "executable" if all(item["executable"] for item in scopes) else "blocked"
    )


@contextmanager
def _process_runtime_lock(root: Path):
    """Serialize workspace JSON mutations across desktop instances on Windows."""
    lock_path = root / "data" / "workspace_runtime.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    try:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            import msvcrt

            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.02)
            yield
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except ImportError:
            yield
    finally:
        handle.close()


def _clean_toolkit(raw: Any) -> dict[str, list[str]]:
    source = raw if isinstance(raw, dict) else {}
    result: dict[str, list[str]] = {}
    for key in TOOLKIT_KEYS:
        values = source.get(key) if isinstance(source.get(key), list) else []
        seen: set[str] = set()
        cleaned: list[str] = []
        for value in values:
            text = " ".join(str(value or "").split()).strip()[:100]
            if not text or text.casefold() in seen:
                continue
            seen.add(text.casefold())
            cleaned.append(text)
            if len(cleaned) >= 100:
                break
        result[key] = cleaned
    return result


def _merge_toolkits(*toolkits: Any) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {key: [] for key in TOOLKIT_KEYS}
    for toolkit in toolkits:
        clean = _clean_toolkit(toolkit)
        for key in TOOLKIT_KEYS:
            known = {item.casefold() for item in merged[key]}
            for item in clean[key]:
                if item.casefold() not in known:
                    merged[key].append(item)
                    known.add(item.casefold())
    return _clean_toolkit(merged)


def _resolved_task_toolkit(
    configuration: dict[str, Any], workspace_default: Any
) -> dict[str, list[str]]:
    """Keep legacy blank runtime records from erasing task-owned defaults."""

    configured = _clean_toolkit(configuration.get("toolkit"))
    has_configured_values = any(configured[key] for key in TOOLKIT_KEYS)
    explicitly_saved = str(configuration.get("toolkit_mode") or "") == "explicit"
    if has_configured_values or explicitly_saved:
        return configured
    return _clean_toolkit(workspace_default)


def load_capability_pack_catalog(root: Path, *, strict: bool = False) -> dict[str, Any]:
    registry_path = root / CAPABILITY_PACK_REGISTRY_PATH
    catalog_error = ""
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("注册表根节点必须是对象。")
    except (OSError, ValueError) as exc:
        catalog_error = f"能力包注册表无法读取或格式无效：{exc}"
        if strict:
            raise ValueError(catalog_error) from exc
        payload = {}
    packs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in payload.get("packs", []):
        if not isinstance(raw, dict):
            continue
        pack_id = str(raw.get("id") or "").strip().lower()
        if not SAFE_ID.fullmatch(pack_id) or pack_id in seen:
            continue
        pack = dict(raw)
        pack["id"] = pack_id
        pack["dependencies"] = [
            str(item or "").strip().lower()
            for item in raw.get("dependencies", [])
            if SAFE_ID.fullmatch(str(item or "").strip().lower())
        ]
        pack["toolkit"] = _clean_toolkit(raw.get("toolkit"))
        pack["required_connectors"] = [
            " ".join(str(item or "").split()).strip()[:160]
            for item in raw.get("required_connectors", [])
            if str(item or "").strip()
        ]
        packs.append(pack)
        seen.add(pack_id)
    return {
        "schema_version": int(payload.get("schema_version") or 1),
        "principles": [str(item) for item in payload.get("principles", []) if str(item).strip()],
        "scale_model": payload.get("scale_model") if isinstance(payload.get("scale_model"), dict) else {},
        "route_taxonomy": (
            payload.get("route_taxonomy")
            if isinstance(payload.get("route_taxonomy"), dict)
            else {}
        ),
        "layers": [dict(item) for item in payload.get("layers", []) if isinstance(item, dict)],
        "packs": packs,
        "catalog_error": catalog_error,
    }


def _resolved_pack_ids(catalog: dict[str, Any], requested_pack_id: str) -> list[str]:
    pack_by_id = {
        str(item.get("id") or ""): item
        for item in catalog.get("packs", [])
        if isinstance(item, dict)
    }
    if requested_pack_id not in pack_by_id:
        raise ValueError("能力包不存在或未通过本地注册表校验。")
    resolved: list[str] = []
    visiting: set[str] = set()

    def visit(pack_id: str) -> None:
        if pack_id in resolved:
            return
        if pack_id in visiting:
            raise ValueError("能力包依赖存在循环，已阻止安装。")
        pack = pack_by_id.get(pack_id)
        if pack is None:
            raise ValueError(f"能力包依赖不存在：{pack_id}")
        visiting.add(pack_id)
        for dependency in pack.get("dependencies", []):
            visit(str(dependency))
        visiting.remove(pack_id)
        resolved.append(pack_id)

    visit(requested_pack_id)
    return resolved


def _base_workspace(root: Path) -> dict[str, Any]:
    return _load_json(root / "config" / "workspace_projects.json")


def _is_archived_conversation(task: dict[str, Any]) -> bool:
    if task.get("archived") is True:
        return True
    status = str(
        task.get("conversation_status")
        or task.get("lifecycle_status")
        or ""
    ).strip().lower()
    return status in {"archived", "已归档"}


def _primary_store_conversation(store: dict[str, Any]) -> dict[str, Any] | None:
    tasks = [item for item in store.get("tasks", []) if isinstance(item, dict)]
    explicit = [
        item
        for item in tasks
        if str(item.get("conversation_role") or "").strip().lower()
        == PRIMARY_STORE_CONVERSATION
        and not _is_archived_conversation(item)
    ]
    if explicit:
        return explicit[0]

    # Legacy store tasks did not carry a conversation role.  Preserve their
    # stable store order and promote the first active record instead of
    # deleting or silently replacing history.
    legacy = [
        item
        for item in tasks
        if not str(item.get("conversation_role") or "").strip()
        and not _is_archived_conversation(item)
    ]
    return legacy[0] if legacy else None


def _annotate_store_conversations(workspace: dict[str, Any]) -> None:
    """Expose one primary conversation per composite project/store identity.

    Existing duplicate tasks remain addressable through the runtime API.  They
    are marked as secondary history so a client can hide them from its primary
    sidebar without losing task configuration, execution evidence or reports.
    """

    for project in workspace.get("projects", []):
        if not isinstance(project, dict):
            continue
        for _channel, store in iter_project_stores(project):
            tasks = [item for item in store.get("tasks", []) if isinstance(item, dict)]
            primary = _primary_store_conversation(store)
            primary_id = str(primary.get("id") or "") if primary else ""
            secondary_count = 0
            for task in tasks:
                task["conversation_scope"] = "store"
                task["primary_conversation_id"] = primary_id
                if task is primary:
                    task["conversation_role"] = PRIMARY_STORE_CONVERSATION
                    task["archived_compatible"] = False
                    task["sidebar_visible"] = True
                    task.pop("history_parent_task_id", None)
                    continue
                secondary_count += 1
                task["conversation_role"] = SECONDARY_STORE_CONVERSATION
                task["archived_compatible"] = True
                task["sidebar_visible"] = False
                task["history_parent_task_id"] = primary_id
            store["primary_conversation_id"] = primary_id
            store["conversation_count"] = len(tasks)
            store["secondary_conversation_count"] = secondary_count


def seller_mode_options(root: Path) -> list[dict[str, str]]:
    """Return the reviewed, classification-only seller modes."""

    registry = load_seller_mode_skill_pack_registry(root, strict=True)
    return [
        {
            "id": str(item.get("id") or "").strip().lower(),
            "label": str(item.get("label") or item.get("id") or "").strip(),
        }
        for item in registry.get("modes", [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    ]


def _normalize_seller_mode(root: Path, value: Any, *, allow_empty: bool = True) -> str:
    seller_mode = str(value or "").strip().lower().replace("-", "_")
    if not seller_mode and allow_empty:
        return ""
    valid = {item["id"] for item in seller_mode_options(root)}
    if seller_mode not in valid:
        raise ValueError("卖家模式不在当前已核验注册表中。")
    return seller_mode


def _apply_project_commerce_profiles(
    root: Path,
    projects: list[dict[str, Any]],
    runtime: dict[str, Any],
) -> None:
    profiles = runtime.get("commerce_profiles")
    profiles = profiles if isinstance(profiles, dict) else {}
    project_profiles = profiles.get("projects")
    project_profiles = project_profiles if isinstance(project_profiles, dict) else {}
    for project in projects:
        project_id = str(project.get("id") or "").strip().lower()
        override = project_profiles.get(project_id)
        if not isinstance(override, dict):
            continue
        selection = normalize_commerce_model_selection(
            root,
            override,
            inherit_from=project,
            strict=True,
        )
        for key in (
            "relationship_model",
            "secondary_relationship_models",
            "commerce_forms",
            "commerce_model_source",
            "commerce_model_field_sources",
            "commerce_model_status",
            "commerce_model_owner_review_required",
            "commerce_model_registry_path",
            "commerce_model_registry_version",
        ):
            project[key] = deepcopy(selection[key])
        project["seller_mode"] = _normalize_seller_mode(
            root,
            override.get("seller_mode", project.get("seller_mode")),
        )
        project["commerce_profile_updated_at"] = str(
            override.get("updated_at") or ""
        )
        project["commerce_profile_updated_by"] = str(
            override.get("updated_by") or ""
        )
        project["commerce_dimension_route"] = commerce_model_routing_dimensions(
            root, project
        )


def load_workspace_config(root: Path) -> dict[str, Any]:
    """Return the base workspace merged with store-scoped runtime changes."""

    with _LOCK:
        base = deepcopy(_base_workspace(root))
        runtime = _load_runtime(root)
    base_projects = [item for item in base.get("projects", []) if isinstance(item, dict)]
    known_project_ids = {str(item.get("id") or "") for item in base_projects}
    for runtime_project in runtime["projects"]:
        project_id = str(runtime_project.get("id") or "")
        if SAFE_ID.fullmatch(project_id) and project_id not in known_project_ids:
            base_projects.append(dict(runtime_project))
            known_project_ids.add(project_id)
    _apply_project_commerce_profiles(root, base_projects, runtime)
    base["projects"] = base_projects
    workspace = normalize_workspace_config(base)
    projects = [item for item in workspace.get("projects", []) if isinstance(item, dict)]
    project_by_id = {
        str(item.get("id") or "").strip().lower(): item for item in projects
    }
    connection_overrides: list[dict[str, Any]] = []

    # Attach real runtime-created stores first.  A record colliding with an
    # existing project/store identity is treated as a legacy connection
    # override and never replaces store identity, channel or tasks.
    for runtime_store in runtime["stores"]:
        project_id = str(runtime_store.get("project_id") or "").strip().lower()
        store_id = str(runtime_store.get("id") or "").strip().lower()
        project = project_by_id.get(project_id)
        if project is None or not SAFE_ID.fullmatch(store_id):
            continue
        if runtime_store.get("connection_override_only") is True:
            connection_overrides.append(runtime_store)
            continue
        if find_store_in_project(workspace, project_id, store_id) is not None:
            connection_overrides.append(runtime_store)
            continue

        channel_id = str(runtime_store.get("channel_id") or "").strip().lower()
        platform = str(runtime_store.get("platform") or "general").strip().lower()
        country = str(runtime_store.get("country_site") or "GLOBAL").strip().upper()
        channels = [item for item in project.get("channels", []) if isinstance(item, dict)]
        channel = next(
            (
                item
                for item in channels
                if str(item.get("id") or "").strip().lower() == channel_id
            ),
            None,
        ) if channel_id else None
        if channel is not None and (
            str(channel.get("platform") or "").strip().lower() != platform
            or str(channel.get("country_site") or "GLOBAL").strip().upper() != country
        ):
            channel = None
        if channel is None:
            channel = next(
                (
                    item
                    for item in channels
                    if str(item.get("platform") or "").strip().lower() == platform
                    and str(item.get("country_site") or "GLOBAL").strip().upper() == country
                ),
                None,
            )
        if channel is None:
            channel = {
                "id": channel_id or f"{platform.replace('_', '-')}-{country.lower()}",
                "name": f"{platform.replace('_', ' ').title()} {country}",
                "platform": platform,
                "country_site": country,
                "status": "store_configuration_required",
                "stores": [],
            }
            channels.append(channel)
            project["channels"] = channels
        stored = deepcopy(runtime_store)
        stored.setdefault("tasks", [])
        channel.setdefault("stores", []).append(stored)

    # Normalize once so runtime-created stores can also receive a separate
    # override record by their composite project/store identity.
    workspace["projects"] = projects
    workspace = normalize_workspace_config(workspace)
    projects = [item for item in workspace.get("projects", []) if isinstance(item, dict)]
    project_by_id = {
        str(item.get("id") or "").strip().lower(): item for item in projects
    }

    browser_overrides: set[tuple[str, str]] = set()
    for runtime_store in connection_overrides:
        override_project_id = str(runtime_store.get("project_id") or "").strip().lower()
        override_store_id = str(runtime_store.get("id") or "").strip().lower()
        found_store = find_store_in_project(
            workspace,
            override_project_id,
            override_store_id,
        )
        if found_store is not None and _apply_connection_override(
            found_store[2], runtime_store
        ):
            browser_overrides.add((override_project_id, override_store_id))

    # Connection identity, route and executable status are derived data.  They
    # are rebuilt after every override instead of trusting persisted snapshots.
    for project in projects:
        for channel, store in iter_project_stores(project):
            identity = (
                str(project.get("id") or "").strip().lower(),
                str(store.get("id") or "").strip().lower(),
            )
            _recompute_store_connection_state(
                workspace,
                project,
                channel,
                store,
                browser_override_applied=identity in browser_overrides,
            )
    workspace["projects"] = projects
    workspace = normalize_workspace_config(workspace)
    projects = [item for item in workspace.get("projects", []) if isinstance(item, dict)]
    project_by_id = {
        str(item.get("id") or "").strip().lower(): item for item in projects
    }

    standalone_tasks: list[dict[str, Any]] = []
    for runtime_task in runtime["tasks"]:
        project_id = str(runtime_task.get("project_id") or "").strip().lower()
        project = project_by_id.get(project_id)
        task_id = str(runtime_task.get("id") or "").strip().lower()
        if not SAFE_ID.fullmatch(task_id):
            continue
        if project is None and not project_id:
            standalone_tasks.append(dict(runtime_task))
            continue
        if project is None:
            continue
        if any(
            str(item.get("id") or "") == task_id
            for item in project.get("tasks", [])
            if isinstance(item, dict)
        ):
            continue
        store_binding_id = str(runtime_task.get("store_binding_id") or "").strip().lower()
        store_context = (
            find_store_in_project(workspace, project_id, store_binding_id)
            if store_binding_id
            else None
        )
        if store_context:
            store_context[2].setdefault("tasks", []).append(dict(runtime_task))
        else:
            project.setdefault("workstreams", []).append(dict(runtime_task))

    workspace["projects"] = projects
    workspace["standalone_tasks"] = standalone_tasks
    _drop_unbound_store_placeholders(workspace)
    workspace = normalize_workspace_config(workspace)
    projects = [item for item in workspace.get("projects", []) if isinstance(item, dict)]

    configurations = runtime["task_configurations"]
    for project in projects:
        for _channel, _store, task in iter_project_tasks(project):
            task_id = str(task.get("id") or "")
            configuration = configurations.get(task_id, {})
            task["toolkit"] = _resolved_task_toolkit(
                configuration, task.get("toolkit")
            )
            task["model_provider"] = str(
                configuration.get("model_provider")
                if "model_provider" in configuration
                else task.get("model_provider") or ""
            )
            task["reasoning_effort"] = str(
                configuration.get("reasoning_effort")
                if "reasoning_effort" in configuration
                else task.get("reasoning_effort") or "standard"
            )
            task["execution_speed"] = str(
                configuration.get("execution_speed")
                if "execution_speed" in configuration
                else task.get("execution_speed") or "standard"
            )
            task["configuration_source"] = (
                "runtime" if configuration else "workspace_default"
            )
            task["installed_packs"] = [
                str(item)
                for item in configuration.get("installed_packs", [])
                if SAFE_ID.fullmatch(str(item))
            ]
    for task in workspace.get("standalone_tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("id") or "")
        configuration = configurations.get(task_id, {})
        task["toolkit"] = _resolved_task_toolkit(
            configuration, task.get("toolkit")
        )
        task["model_provider"] = str(
            configuration.get("model_provider")
            if "model_provider" in configuration
            else task.get("model_provider") or ""
        )
        task["reasoning_effort"] = str(
            configuration.get("reasoning_effort")
            if "reasoning_effort" in configuration
            else task.get("reasoning_effort") or "standard"
        )
        task["execution_speed"] = str(
            configuration.get("execution_speed")
            if "execution_speed" in configuration
            else task.get("execution_speed") or "standard"
        )
        task["configuration_source"] = (
            "runtime" if configuration else "workspace_default"
        )
        task["installed_packs"] = [
            str(item)
            for item in configuration.get("installed_packs", [])
            if SAFE_ID.fullmatch(str(item))
        ]
    workspace["projects"] = projects
    # Rebuild the flattened compatibility view from the configured nested tasks.
    workspace = normalize_workspace_config(workspace)
    _annotate_store_conversations(workspace)
    sidebar_metadata = runtime.get("sidebar_metadata") or {}
    project_metadata = (
        sidebar_metadata.get("projects")
        if isinstance(sidebar_metadata.get("projects"), dict)
        else {}
    )
    task_metadata = (
        sidebar_metadata.get("tasks")
        if isinstance(sidebar_metadata.get("tasks"), dict)
        else {}
    )
    for project in workspace.get("projects", []):
        if not isinstance(project, dict):
            continue
        project_id = str(project.get("id") or "").strip().lower()
        override = project_metadata.get(project_id, {})
        if isinstance(override, dict):
            if str(override.get("name") or "").strip():
                project["name"] = str(override["name"]).strip()
            project["sidebar_pinned"] = bool(override.get("pinned"))
            project["sidebar_archived"] = bool(override.get("archived"))
            project["sidebar_unread"] = bool(override.get("unread"))
        for _channel, _store, task in iter_project_tasks(project):
            task_id = str(task.get("id") or "").strip().lower()
            task_override = task_metadata.get(task_id, {})
            if isinstance(task_override, dict):
                if str(task_override.get("name") or "").strip():
                    task["name"] = str(task_override["name"]).strip()
                if "initial_instruction" in task_override:
                    task["initial_instruction"] = str(
                        task_override.get("initial_instruction") or ""
                    ).strip()[:2000]
                if str(task_override.get("status") or "").strip():
                    task["status"] = str(task_override["status"]).strip()[:40]
                task["sidebar_pinned"] = bool(task_override.get("pinned"))
                task["sidebar_archived"] = bool(task_override.get("archived"))
                task["sidebar_unread"] = bool(task_override.get("unread"))
                task["sidebar_project_id"] = str(
                    task_override.get("project_id")
                    if "project_id" in task_override
                    else project_id
                ).strip().lower()
            else:
                task["sidebar_project_id"] = project_id
    for task in workspace.get("standalone_tasks", []):
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("id") or "").strip().lower()
        task_override = task_metadata.get(task_id, {})
        if isinstance(task_override, dict):
            if str(task_override.get("name") or "").strip():
                task["name"] = str(task_override["name"]).strip()
            if "initial_instruction" in task_override:
                task["initial_instruction"] = str(
                    task_override.get("initial_instruction") or ""
                ).strip()[:2000]
            if str(task_override.get("status") or "").strip():
                task["status"] = str(task_override["status"]).strip()[:40]
            task["sidebar_pinned"] = bool(task_override.get("pinned"))
            task["sidebar_archived"] = bool(task_override.get("archived"))
            task["sidebar_unread"] = bool(task_override.get("unread"))
            task["sidebar_project_id"] = str(
                task_override.get("project_id") or ""
            ).strip().lower()
        else:
            task["sidebar_project_id"] = ""
    workspace["runtime_updated_at"] = runtime.get("updated_at") or ""
    return workspace


def _find_task(workspace: dict[str, Any], task_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    found = find_task_context(workspace, task_id)
    return (found[0], found[3]) if found else None


def task_configuration_snapshot(root: Path, task_id: str) -> dict[str, Any]:
    task_id = str(task_id or "").strip().lower()
    if not SAFE_ID.fullmatch(task_id):
        raise ValueError("任务编号无效。")
    found = _find_task(load_workspace_config(root), task_id)
    if found is None:
        raise ValueError("任务不存在。")
    project, task = found
    runtime = _load_runtime(root)
    current = (
        runtime.get("task_configurations", {}).get(task_id, {})
        if isinstance(runtime.get("task_configurations"), dict)
        else {}
    )
    installations = (
        current.get("pack_installations")
        if isinstance(current.get("pack_installations"), dict)
        else {}
    )
    clean_installations: dict[str, dict[str, str]] = {}
    for pack_id, record in installations.items():
        safe_pack_id = str(pack_id or "").strip().lower()
        if not SAFE_ID.fullmatch(safe_pack_id) or not isinstance(record, dict):
            continue
        clean_installations[safe_pack_id] = {
            key: str(record.get(key) or "")[:160]
            for key in (
                "installed_at",
                "installed_by",
                "last_reconciled_at",
                "last_reconciled_by",
            )
            if str(record.get(key) or "").strip()
        }
    installed_packs = [
        str(item)
        for item in task.get("installed_packs", [])
        if SAFE_ID.fullmatch(str(item))
    ]
    catalog = load_capability_pack_catalog(root)
    pack_by_id = {
        str(item.get("id") or ""): item
        for item in catalog.get("packs", [])
        if isinstance(item, dict)
    }
    connection_requirements: list[str] = []
    incompatible_installed_packs: list[dict[str, str]] = []
    for pack_id in installed_packs:
        pack = pack_by_id.get(pack_id, {})
        for requirement in pack.get("required_connectors", []):
            if requirement not in connection_requirements:
                connection_requirements.append(requirement)
        if pack:
            try:
                _assert_pack_task_compatibility(task, [pack])
            except ValueError as exc:
                incompatible_installed_packs.append(
                    {"pack_id": pack_id, "error": str(exc)}
                )
    model_provider = str(task.get("model_provider") or "")
    return {
        "schema_version": 2,
        "task_id": task_id,
        "project_id": str(project.get("id") or ""),
        "store_binding_id": str(task.get("store_binding_id") or ""),
        "scope_type": str(task.get("scope_type") or "project_workstream"),
        "toolkit": _clean_toolkit(task.get("toolkit")),
        "model_provider": model_provider,
        "model_selection_mode": "explicit" if model_provider else "auto",
        "reasoning_effort": str(task.get("reasoning_effort") or "standard"),
        "execution_speed": str(task.get("execution_speed") or "standard"),
        "installed_packs": installed_packs,
        "pack_installations": clean_installations,
        "connection_requirements": connection_requirements,
        "incompatible_installed_packs": incompatible_installed_packs,
        "installation_authorization_state": "not_granted_by_installation",
        "execution_ready_from_installation": False,
        "configuration_source": str(task.get("configuration_source") or "workspace_default"),
    }


def _configured_model_provider_names(root: Path) -> set[str]:
    try:
        payload = json.loads((root / MULTI_AI_PATH).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return set()
    providers = payload.get("providers") if isinstance(payload, dict) else []
    if not isinstance(providers, list):
        return set()
    return {
        str(item.get("name") or item.get("id") or "").strip()
        for item in providers
        if isinstance(item, dict)
        and str(item.get("name") or item.get("id") or "").strip()
    }


def save_task_configuration(
    root: Path, payload: dict[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    task_id = str(payload.get("task_id") or "").strip().lower()
    if not SAFE_ID.fullmatch(task_id):
        raise ValueError("任务编号无效。")
    if _find_task(load_workspace_config(root), task_id) is None:
        raise ValueError("任务不存在。")

    with _LOCK, _process_runtime_lock(root):
        runtime = _load_runtime(root)
        current = dict(runtime["task_configurations"].get(task_id) or {})
        if "toolkit" in payload:
            current["toolkit"] = _clean_toolkit(payload.get("toolkit"))
            current["toolkit_mode"] = "explicit"
            has_selected_capability = any(current["toolkit"].get(kind) for kind in TOOLKIT_KEYS)
            if has_selected_capability:
                metadata = runtime.setdefault(
                    "sidebar_metadata", {"projects": {}, "tasks": {}}
                )
                task_metadata = metadata.setdefault("tasks", {})
                task_record = dict(task_metadata.get(task_id) or {})
                current_status = str(task_record.get("status") or "").strip()
                if current_status in {"", "待配置", "待办"}:
                    task_record["status"] = "待执行"
                    task_record["updated_at"] = _now_iso()
                    task_record["updated_by"] = str(actor or "owner")[:80]
                    task_metadata[task_id] = task_record
        if "model_provider" in payload:
            requested_provider = str(payload.get("model_provider") or "").strip()[:80]
            if requested_provider.lower() in AUTO_MODEL_PROVIDER_VALUES:
                requested_provider = ""
            elif requested_provider not in _configured_model_provider_names(root):
                raise ValueError(
                    "所选 AI 模型尚未配置。请先在“AI 模型”中保存该供应商和模型，"
                    "再回到当前任务选择；系统不会静默切换到其他模型。"
                )
            current["model_provider"] = requested_provider
        if "reasoning_effort" in payload:
            reasoning_effort = str(payload.get("reasoning_effort") or "standard").strip().lower()
            if reasoning_effort not in {"quick", "standard", "deep", "maximum"}:
                raise ValueError("推理强度无效。")
            current["reasoning_effort"] = reasoning_effort
        if "execution_speed" in payload:
            execution_speed = str(payload.get("execution_speed") or "standard").strip().lower()
            if execution_speed not in {"fast", "standard", "quality"}:
                raise ValueError("运行速度无效。")
            current["execution_speed"] = execution_speed
        current["updated_at"] = _now_iso()
        current["updated_by"] = str(actor or "owner")[:80]
        runtime["task_configurations"][task_id] = current
        _write_runtime(root, runtime)
    refreshed = _find_task(load_workspace_config(root), task_id)
    if refreshed is not None:
        ensure_task_local_folder(root, refreshed[1])
    return {"ok": True, **task_configuration_snapshot(root, task_id)}


def capability_pack_catalog_snapshot(root: Path, task_id: str = "") -> dict[str, Any]:
    catalog = load_capability_pack_catalog(root)
    installed: set[str] = set()
    if task_id:
        installed = set(task_configuration_snapshot(root, task_id).get("installed_packs") or [])
    packs: list[dict[str, Any]] = []
    for item in catalog["packs"]:
        pack = dict(item)
        pack["installed"] = str(pack.get("id") or "") in installed
        packs.append(pack)
    return {**catalog, "packs": packs, "task_id": task_id}


def _assert_pack_task_compatibility(
    task: dict[str, Any], resolved_packs: list[dict[str, Any]]
) -> None:
    task_platform = str(task.get("platform") or "").strip().lower().replace("-", "_")
    platform_aliases = {
        "tiktok": {"tiktok", "tiktok_shop"},
        "tiktok_shop": {"tiktok", "tiktok_shop"},
        "independent_store": {"shopify", "woocommerce", "independent_store"},
    }
    task_platforms = platform_aliases.get(task_platform, {task_platform})
    for pack in resolved_packs:
        if str(pack.get("layer") or "") != "platform":
            continue
        route_policy = (
            pack.get("route_policy") if isinstance(pack.get("route_policy"), dict) else {}
        )
        required_platform = (
            str(route_policy.get("platform") or "").strip().lower().replace("-", "_")
        )
        if not required_platform:
            continue
        accepted_platforms = platform_aliases.get(required_platform, {required_platform})
        if task_platforms.isdisjoint(accepted_platforms):
            pack_name = str(pack.get("name") or pack.get("id") or "平台能力包")
            raise ValueError(
                f"{pack_name} 只能安装到 {required_platform} 任务；"
                f"当前任务平台是 {task_platform or '未配置'}。"
            )


def install_capability_pack(
    root: Path, payload: dict[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    task_id = str(payload.get("task_id") or "").strip().lower()
    pack_id = str(payload.get("pack_id") or "").strip().lower()
    if not SAFE_ID.fullmatch(task_id):
        raise ValueError("请选择要安装能力的任务。")
    if not SAFE_ID.fullmatch(pack_id):
        raise ValueError("能力包编号无效。")
    found = _find_task(load_workspace_config(root), task_id)
    if found is None:
        raise ValueError("任务不存在。")
    _project, task = found
    catalog = load_capability_pack_catalog(root, strict=True)
    pack_by_id = {
        str(item.get("id") or ""): item
        for item in catalog.get("packs", [])
        if isinstance(item, dict)
    }
    resolved_ids = _resolved_pack_ids(catalog, pack_id)
    resolved_packs = [pack_by_id[item] for item in resolved_ids]
    _assert_pack_task_compatibility(task, resolved_packs)

    with _LOCK, _process_runtime_lock(root):
        runtime = _load_runtime(root)
        current = dict(runtime["task_configurations"].get(task_id) or {})
        toolkit = current.get("toolkit") if isinstance(current.get("toolkit"), dict) else task.get("toolkit")
        for pack in resolved_packs:
            toolkit = _merge_toolkits(toolkit, pack.get("toolkit"))
        installed = [
            str(item)
            for item in current.get("installed_packs", [])
            if SAFE_ID.fullmatch(str(item))
        ]
        already_installed = [item for item in resolved_ids if item in installed]
        newly_installed = [item for item in resolved_ids if item not in installed]
        for resolved_id in resolved_ids:
            if resolved_id not in installed:
                installed.append(resolved_id)
        installations = (
            dict(current.get("pack_installations"))
            if isinstance(current.get("pack_installations"), dict)
            else {}
        )
        installed_at = _now_iso()
        for resolved_id in resolved_ids:
            previous = (
                dict(installations.get(resolved_id) or {})
                if isinstance(installations.get(resolved_id), dict)
                else {}
            )
            if not previous.get("installed_at"):
                previous["installed_at"] = installed_at
                previous["installed_by"] = str(actor or "owner")[:80]
            previous["last_reconciled_at"] = installed_at
            previous["last_reconciled_by"] = str(actor or "owner")[:80]
            installations[resolved_id] = previous
        current["toolkit"] = toolkit
        current["toolkit_mode"] = "explicit"
        current["installed_packs"] = installed
        current["pack_installations"] = installations
        current["updated_at"] = installed_at
        current["updated_by"] = str(actor or "owner")[:80]
        runtime["task_configurations"][task_id] = current
        _write_runtime(root, runtime)

    connector_requirements: list[str] = []
    for pack in resolved_packs:
        for requirement in pack.get("required_connectors", []):
            if requirement not in connector_requirements:
                connector_requirements.append(requirement)
    return {
        "ok": True,
        **task_configuration_snapshot(root, task_id),
        "requested_pack_id": pack_id,
        "resolved_pack_ids": resolved_ids,
        "newly_installed_pack_ids": newly_installed,
        "already_installed_pack_ids": already_installed,
        "needs_configuration": connector_requirements,
        "installation_authorization_state": "not_granted_by_installation",
        "execution_ready_from_installation": False,
        "message": (
            (
                f"已为当前任务安装 {len(newly_installed)} 个新能力包并校验全部依赖；"
                if newly_installed
                else f"当前任务的 {len(resolved_ids)} 个能力包及依赖已存在，已重新校验；"
            )
            + (f"仍需配置 {len(connector_requirements)} 类真实连接。" if connector_requirements else "无需新增外部连接。")
            + " 本次安装不会授予 OAuth、账号、浏览器会话或发布权限。"
        ),
    }


def session_can_manage_task(
    root: Path, task_id: str, session_info: dict[str, Any] | None
) -> bool:
    if not session_info:
        return False
    if session_info.get("is_owner"):
        return True
    permissions = {str(item) for item in session_info.get("permissions", [])}
    if "admin.automation" not in permissions:
        return False
    found = _find_task(load_workspace_config(root), str(task_id or "").strip().lower())
    if found is None:
        return False
    project, task = found

    def scope_values(value: Any) -> set[str]:
        if isinstance(value, list):
            values = {str(item or "").strip() for item in value if str(item or "").strip()}
        else:
            values = {
                item.strip()
                for item in re.split(r"[,;，；\n]+", str(value or ""))
                if item.strip()
            }
        return {"all"} if not values or "all" in {item.casefold() for item in values} else values

    project_scope = scope_values(session_info.get("project_scope"))
    if "all" not in project_scope and str(project.get("id") or "") not in project_scope:
        return False
    store_scope = scope_values(session_info.get("store_scope"))
    store_candidates = {
        str(task.get("store_binding_id") or ""),
        str(task.get("store_id") or ""),
    }
    if str(task.get("scope_type") or "") == "store_task" and (
        "all" not in store_scope and not store_scope.intersection(store_candidates)
    ):
        return False
    task_scope = scope_values(session_info.get("task_scope"))
    task_candidates = {
        str(task.get("id") or ""),
        str(task.get("name") or ""),
    }
    return "all" in task_scope or bool(task_scope.intersection(task_candidates))


def _new_task_id(runtime: dict[str, Any], workspace: dict[str, Any], name: str) -> str:
    existing = {
        str(task.get("id") or "")
        for project in workspace.get("projects", [])
        if isinstance(project, dict)
        for task in project.get("tasks", [])
        if isinstance(task, dict)
    }
    seed = f"{name}|{_now_iso()}|{len(runtime.get('tasks') or [])}"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
    task_id = f"task-{digest}"
    while task_id in existing:
        digest = hashlib.sha1(f"{seed}|{task_id}".encode("utf-8")).hexdigest()[:12]
        task_id = f"task-{digest}"
    return task_id


def create_workspace_task(
    root: Path, payload: dict[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    project_id = str(payload.get("project_id") or "").strip().lower()
    store_binding_id = str(payload.get("store_binding_id") or "").strip().lower()
    name = " ".join(str(payload.get("name") or "").split()).strip()[:100]
    initial_instruction = " ".join(
        str(payload.get("initial_instruction") or "").split()
    )[:2000]
    standalone = payload.get("standalone") is True
    if not project_id and not standalone:
        raise ValueError("请选择项目组。")
    if project_id and not SAFE_ID.fullmatch(project_id):
        raise ValueError("请选择项目组。")
    if standalone and store_binding_id:
        raise ValueError("独立任务不能绑定店铺身份。")
    if not name:
        raise ValueError("请输入任务名称。")

    workspace = load_workspace_config(root)
    project = next(
        (
            item
            for item in workspace.get("projects", [])
            if isinstance(item, dict) and str(item.get("id") or "") == project_id
        ),
        None,
    )
    if project is None and not standalone:
        raise ValueError("项目组不存在。")

    store_context = (
        find_store_in_project(workspace, project_id, store_binding_id)
        if store_binding_id and project_id
        else None
    )
    if store_binding_id and store_context is None:
        raise ValueError("所选店铺不属于当前项目。")
    store = store_context[2] if store_context else {}
    channel = store_context[1] if store_context else {}
    platform = str(payload.get("platform") or channel.get("platform") or "general")
    country = str(payload.get("country") or channel.get("country_site") or "")
    fulfillment_route = _fulfillment_route_snapshot(
        root, str(payload.get("fulfillment_route_id") or "")
    )
    if fulfillment_route and platform != "store_onboarding":
        raise ValueError("履约路线只能在接入新店铺时选择。")
    browser_provider = str(
        payload.get("browser_provider") or store.get("browser_provider") or ""
    ).strip().lower()[:40]
    browser_profile_id = str(
        payload.get("browser_profile_id") or store.get("browser_profile_id") or ""
    ).strip()[:160]
    try:
        browser_profile_sequence = int(
            payload.get("browser_profile_sequence")
            or payload.get("browser_profile_seq")
            or store.get("browser_profile_sequence")
            or store.get("browser_profile_seq")
            or 0
        )
    except (TypeError, ValueError):
        browser_profile_sequence = 0
    browser_binding_status = str(
        payload.get("browser_binding_status")
        or store.get("browser_binding_status")
        or ("profile_selected" if browser_profile_id or browser_profile_sequence else "")
    ).strip()[:80]
    if store_binding_id:
        subtitle = f"{store.get('name') or store_binding_id} · 独立任务上下文"
    elif platform == "store_onboarding":
        subtitle = "在对话中识别并接入真实店铺"
    elif platform != "general" or initial_instruction:
        subtitle = "项目工作流"
    else:
        # This is an explicitly created project task, not a generic store
        # placeholder.  Placeholder cleanup must never erase a real task just
        # because its goal has not been filled in yet.
        subtitle = "项目任务"

    with _LOCK, _process_runtime_lock(root):
        if store_binding_id:
            # Re-read under the cross-process lock.  Without this second check,
            # two desktop windows can both observe an empty store and create
            # competing main conversations.
            current_workspace = load_workspace_config(root)
            current_store_context = find_store_in_project(
                current_workspace, project_id, store_binding_id
            )
            current_store = current_store_context[2] if current_store_context else {}
            existing_primary = _primary_store_conversation(current_store)
            if existing_primary is not None:
                existing_task = deepcopy(existing_primary)
                if current_store_context is not None:
                    ensure_project_local_folder(root, current_store_context[0])
                _folder, local_folder = ensure_task_local_folder(root, existing_task)
                existing_task["local_folder"] = local_folder
                return {
                    "ok": True,
                    "created": False,
                    "reused": True,
                    "task": existing_task,
                    "href": "/desktop?project="
                    + project_id
                    + "&task="
                    + str(existing_task.get("id") or ""),
                }

        runtime = _load_runtime(root)
        task_id = _new_task_id(runtime, workspace, name)
        task = {
            "id": task_id,
            "project_id": project_id,
            "store_binding_id": store_binding_id,
            "name": name,
            "subtitle": "独立任务 · 未归属项目" if standalone else subtitle,
            "status": "进行中" if store_binding_id else "待配置",
            "platform": platform,
            "country": country,
            "store_id": str(
                store.get("external_id")
                or store.get("store_external_id")
                or store_binding_id
                or ""
            ),
            "browser_provider": browser_provider,
            "browser_profile_id": browser_profile_id,
            "browser_profile_sequence": browser_profile_sequence,
            "browser_profile_seq": browser_profile_sequence,
            "browser_binding_status": browser_binding_status,
            "store_surface_connector_script": str(
                store.get("store_surface_connector_script") or ""
            )[:240],
            **fulfillment_route,
            "initial_instruction": initial_instruction,
            "scope_type": (
                "store_task"
                if store_binding_id
                else "standalone_task" if standalone else "project_workstream"
            ),
            "audience": "seller",
            "toolkit": _clean_toolkit(payload.get("toolkit")),
            "created_at": _now_iso(),
            "created_by": str(actor or "owner")[:80],
        }
        if store_binding_id:
            task.update(
                {
                    "conversation_scope": "store",
                    "conversation_role": PRIMARY_STORE_CONVERSATION,
                    "primary_conversation_id": task_id,
                    "archived_compatible": False,
                    "sidebar_visible": True,
                }
            )
        else:
            task["conversation_role"] = INDEPENDENT_PROJECT_CONVERSATION
        if project is not None:
            ensure_project_local_folder(root, project)
        _folder, local_folder = ensure_task_local_folder(root, task)
        task["local_folder"] = local_folder
        runtime["tasks"].append(task)
        _write_runtime(root, runtime)
    return {
        "ok": True,
        "created": True,
        "reused": False,
        "task": task,
        "href": (
            "/desktop?task=" + task_id
            if standalone
            else "/desktop?project=" + project_id + "&task=" + task_id
        ),
    }


def update_workspace_item(
    root: Path, payload: dict[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    """Persist sidebar organization metadata without changing execution identity.

    Moving a task changes only its human workspace grouping. Store-bound tasks
    cannot move because their project/store execution scope must remain exact.
    """

    item_type = str(payload.get("item_type") or "").strip().lower()
    item_id = str(payload.get("item_id") or "").strip().lower()
    action = str(payload.get("action") or "").strip().lower()
    if item_type not in {"project", "task"}:
        raise ValueError("只能修改项目或任务。")
    if not SAFE_ID.fullmatch(item_id):
        raise ValueError("项目或任务编号无效。")
    if action not in {
        "rename",
        "pin",
        "unpin",
        "archive",
        "unarchive",
        "mark_unread",
        "mark_read",
        "move",
        "update_brief",
    }:
        raise ValueError("不支持这个工作区操作。")

    workspace = load_workspace_config(root)
    projects = {
        str(item.get("id") or "").strip().lower(): item
        for item in workspace.get("projects", [])
        if isinstance(item, dict)
    }
    task_context = find_task_context(workspace, item_id) if item_type == "task" else None
    if item_type == "project" and item_id not in projects:
        raise ValueError("项目不存在。")
    if item_type == "task" and task_context is None:
        raise ValueError("任务不存在。")

    with _LOCK, _process_runtime_lock(root):
        runtime = _load_runtime(root)
        metadata = runtime.setdefault(
            "sidebar_metadata", {"projects": {}, "tasks": {}}
        )
        bucket_name = "projects" if item_type == "project" else "tasks"
        bucket = metadata.setdefault(bucket_name, {})
        record = dict(bucket.get(item_id) or {})
        if action == "rename":
            name = " ".join(str(payload.get("name") or "").split()).strip()[:100]
            if not name:
                raise ValueError("名称不能为空。")
            record["name"] = name
        elif action in {"pin", "unpin"}:
            record["pinned"] = action == "pin"
        elif action in {"archive", "unarchive"}:
            record["archived"] = action == "archive"
            if action == "archive":
                record["pinned"] = False
        elif action in {"mark_unread", "mark_read"}:
            record["unread"] = action == "mark_unread"
        elif action == "move":
            if item_type != "task" or task_context is None:
                raise ValueError("只有任务可以移动。")
            _project, _channel, store, _task = task_context
            if store is not None:
                raise ValueError("店铺身份任务不能移动；请移动独立任务，避免串店。")
            target_project_id = str(payload.get("target_project_id") or "").strip().lower()
            if target_project_id and target_project_id not in projects:
                raise ValueError("目标项目不存在。")
            record["project_id"] = target_project_id
        elif action == "update_brief":
            if item_type != "task" or task_context is None:
                raise ValueError("只有任务可以修改目标说明。")
            instruction = " ".join(
                str(payload.get("initial_instruction") or "").split()
            )[:2000]
            if not instruction:
                raise ValueError("请填写任务目标。")
            record["initial_instruction"] = instruction
        record["updated_at"] = _now_iso()
        record["updated_by"] = " ".join(str(actor or "owner").split())[:80]
        bucket[item_id] = record
        _write_runtime(root, runtime)
    if action == "update_brief":
        refreshed = _find_task(load_workspace_config(root), item_id)
        if refreshed is not None:
            ensure_task_local_folder(root, refreshed[1])
    return {
        "ok": True,
        "item_type": item_type,
        "item_id": item_id,
        "action": action,
        "metadata": record,
        "external_actions": 0,
    }


def _new_runtime_id(prefix: str, runtime: dict[str, Any], name: str) -> str:
    seed = f"{prefix}|{name}|{_now_iso()}"
    candidate = f"{prefix}-{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:10]}"
    known = {
        str(item.get("id") or "")
        for key in ("projects", "stores", "tasks")
        for item in runtime.get(key, [])
        if isinstance(item, dict)
    }
    while candidate in known:
        seed += candidate
        candidate = f"{prefix}-{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:10]}"
    return candidate


def project_local_folder(root: Path, project_id: str) -> Path:
    """Return the project-owned local directory without accepting path input.

    Project ids are generated by this runtime, so deriving the folder from the
    id prevents a project payload from redirecting file writes elsewhere on the
    computer.
    """

    normalized_id = str(project_id or "").strip().lower()
    if not SAFE_ID.fullmatch(normalized_id):
        raise ValueError("项目编号无效，不能创建本地项目文件夹。")
    return (root / PROJECTS_DIRECTORY / normalized_id).resolve()


def _project_manifest(project: dict[str, Any], local_folder: str) -> dict[str, Any]:
    """Keep a small, portable description beside the project's local files."""

    return {
        "schema_version": 2,
        "project_id": str(project.get("id") or ""),
        "name": str(project.get("name") or ""),
        "description": str(project.get("description") or ""),
        "created_at": str(project.get("created_at") or ""),
        "created_by": str(project.get("created_by") or ""),
        "local_folder": local_folder,
        "storage_policy": "local_only_by_default",
        "workspace_contract": "t_one_project_workspace_v1",
        "paths": {
            "inputs": "inputs",
            "attachments": "attachments",
            "knowledge": "knowledge",
            "memory": "memory",
            "tasks": "tasks",
            "runs": "runs",
            "results": "results",
            "receipts": "receipts",
        },
        "folder_purposes": {
            "inputs": "待处理的原始输入",
            "attachments": "项目附件与媒体",
            "knowledge": "已整理、可复用的项目资料",
            "memory": "经确认的长期项目记忆",
            "tasks": "本项目的独立任务工作区",
            "runs": "AI、CLI 与工具运行记录",
            "results": "可交付结果",
            "receipts": "运行回执",
        },
    }


def _write_local_manifest_if_changed(path: Path, payload: dict[str, Any]) -> bool:
    """Atomically update a small local manifest only when its content changed."""

    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    try:
        if path.read_text(encoding="utf-8") == content:
            return False
    except FileNotFoundError:
        pass
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return True


def ensure_project_local_folder(root: Path, project: dict[str, Any]) -> tuple[Path, str]:
    """Create the durable local project layout and its non-secret manifest."""

    folder = project_local_folder(root, str(project.get("id") or ""))
    root_resolved = root.resolve()
    try:
        folder.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("项目文件夹必须位于当前 T One 工作区内。") from exc
    folder.mkdir(parents=True, exist_ok=True)
    for name in PROJECT_FOLDER_SUBDIRECTORIES:
        (folder / name).mkdir(exist_ok=True)
    relative_folder = folder.relative_to(root_resolved).as_posix()
    _write_local_manifest_if_changed(
        folder / "project.json",
        _project_manifest(project, relative_folder),
    )
    return folder, relative_folder


def task_local_folder(root: Path, task: dict[str, Any]) -> Path:
    """Return one stable task directory derived only from validated runtime ids."""

    task_id = str(task.get("id") or "").strip().lower()
    project_id = str(task.get("project_id") or "").strip().lower()
    if not SAFE_ID.fullmatch(task_id):
        raise ValueError("任务编号无效，不能创建本地任务文件夹。")
    if project_id:
        if not SAFE_ID.fullmatch(project_id):
            raise ValueError("项目编号无效，不能创建本地任务文件夹。")
        return (project_local_folder(root, project_id) / "tasks" / task_id).resolve()
    return (root / TASKS_DIRECTORY / task_id).resolve()


def _task_manifest(task: dict[str, Any], local_folder: str) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "task_id": str(task.get("id") or ""),
        "project_id": str(task.get("project_id") or ""),
        "name": str(task.get("name") or ""),
        "initial_instruction": str(task.get("initial_instruction") or ""),
        "status": str(task.get("status") or ""),
        "platform": str(task.get("platform") or ""),
        "country": str(task.get("country") or ""),
        "toolkit": _clean_toolkit(task.get("toolkit")),
        "scope_type": str(task.get("scope_type") or ""),
        "store_binding_id": str(task.get("store_binding_id") or ""),
        "created_at": str(task.get("created_at") or ""),
        "created_by": str(task.get("created_by") or ""),
        "local_folder": local_folder,
        "storage_policy": "local_only_by_default",
        "folder_stability": "stable_when_sidebar_group_changes",
        "workspace_contract": "t_one_task_workspace_v1",
        "paths": {
            "inputs": "inputs",
            "attachments": "attachments",
            "memory": "memory",
            "runs": "runs",
            "results": "results",
            "receipts": "receipts",
        },
        "folder_purposes": {
            "inputs": "本任务的原始输入",
            "attachments": "本任务附件",
            "memory": "本任务经确认的记忆",
            "runs": "AI、CLI 与工具运行记录",
            "results": "本任务结果",
            "receipts": "本任务运行回执",
        },
    }


def ensure_task_local_folder(root: Path, task: dict[str, Any]) -> tuple[Path, str]:
    """Create a durable task layout without accepting a caller-supplied path."""

    folder = task_local_folder(root, task)
    root_resolved = root.resolve()
    try:
        folder.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("任务文件夹必须位于当前 T One 工作区内。") from exc
    folder.mkdir(parents=True, exist_ok=True)
    for name in TASK_FOLDER_SUBDIRECTORIES:
        (folder / name).mkdir(exist_ok=True)
    relative_folder = folder.relative_to(root_resolved).as_posix()
    _write_local_manifest_if_changed(
        folder / "task.json",
        _task_manifest(task, relative_folder),
    )
    return folder, relative_folder


def workspace_item_local_folder(root: Path, item_type: str, item_id: str) -> tuple[Path, str]:
    """Resolve and repair one project's or task's local folder inside T One."""

    item_type = str(item_type or "").strip().lower()
    item_id = str(item_id or "").strip().lower()
    if item_type not in {"project", "task"} or not SAFE_ID.fullmatch(item_id):
        raise ValueError("只能打开当前工作区中的项目或任务文件夹。")
    workspace = load_workspace_config(root)
    if item_type == "project":
        project = next(
            (
                item
                for item in workspace.get("projects", [])
                if isinstance(item, dict)
                and str(item.get("id") or "").strip().lower() == item_id
            ),
            None,
        )
        if project is None:
            raise ValueError("项目不存在。")
        return ensure_project_local_folder(root, project)
    context = find_task_context(workspace, item_id)
    if context is None:
        runtime_task = next(
            (
                item
                for item in _load_runtime(root).get("tasks", [])
                if isinstance(item, dict)
                and str(item.get("id") or "").strip().lower() == item_id
            ),
            None,
        )
        if runtime_task is None:
            raise ValueError("任务不存在。")
        project_id = str(runtime_task.get("project_id") or "").strip().lower()
        if project_id:
            project = next(
                (
                    item
                    for item in workspace.get("projects", [])
                    if isinstance(item, dict)
                    and str(item.get("id") or "").strip().lower() == project_id
                ),
                None,
            )
            if project is None:
                raise ValueError("任务所属项目不存在。")
            ensure_project_local_folder(root, project)
        return ensure_task_local_folder(root, runtime_task)
    project, _channel, _store, task = context
    if str(task.get("project_id") or "").strip():
        ensure_project_local_folder(root, project)
    return ensure_task_local_folder(root, task)


def workspace_item_context(root: Path, item_type: str, item_id: str) -> dict[str, Any]:
    """Return the one portable path index shared by AI, CLI, MCP and Skills."""

    root = Path(root).resolve()
    item_type = str(item_type or "").strip().lower()
    folder, relative_folder = workspace_item_local_folder(root, item_type, item_id)
    manifest_name = "project.json" if item_type == "project" else "task.json"
    manifest_path = folder / manifest_name
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_paths = manifest.get("paths") if isinstance(manifest.get("paths"), dict) else {}
    paths = {
        str(key): (Path(relative_folder) / str(value)).as_posix()
        for key, value in raw_paths.items()
        if str(key).strip() and str(value).strip()
    }
    return {
        "schema_version": 1,
        "workspace_contract": str(manifest.get("workspace_contract") or ""),
        "item_type": item_type,
        "item_id": str(item_id or "").strip().lower(),
        "local_folder": relative_folder,
        "entry_manifest": (Path(relative_folder) / manifest_name).as_posix(),
        "paths": paths,
        "folder_purposes": dict(manifest.get("folder_purposes") or {}),
        "path_scope": "relative_to_t_one_workspace",
        "copy_policy": "reference_canonical_files_do_not_duplicate",
    }


def project_workspace_context(
    root: Path, project_id: str, task_id: str = ""
) -> dict[str, Any]:
    """Resolve a project and optional owned task through the same path contract."""

    project = workspace_item_context(root, "project", project_id)
    task: dict[str, Any] | None = None
    normalized_task_id = str(task_id or "").strip().lower()
    if normalized_task_id:
        workspace = load_workspace_config(Path(root).resolve())
        context = find_task_context(workspace, normalized_task_id)
        owning_project_id = (
            str(context[0].get("id") or "").strip().lower() if context else ""
        )
        if not owning_project_id:
            runtime_task = next(
                (
                    item
                    for item in _load_runtime(Path(root).resolve()).get("tasks", [])
                    if isinstance(item, dict)
                    and str(item.get("id") or "").strip().lower() == normalized_task_id
                ),
                None,
            )
            owning_project_id = str(
                (runtime_task or {}).get("project_id") or ""
            ).strip().lower()
        if owning_project_id != str(project_id or "").strip().lower():
            raise ValueError("所选任务不属于当前项目。")
        task = workspace_item_context(root, "task", normalized_task_id)
    return {
        "schema_version": 1,
        "project": project,
        "task": task,
        "discovery_order": [
            project["entry_manifest"],
            *([task["entry_manifest"]] if task else []),
        ],
        "external_side_effect_count": 0,
    }


def create_workspace_project(
    root: Path, payload: dict[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    name = " ".join(str(payload.get("name") or "").split()).strip()[:100]
    if not name:
        raise ValueError("请输入真实项目名称。")
    commerce_selection = normalize_commerce_model_selection(root, payload)
    seller_mode = _normalize_seller_mode(root, payload.get("seller_mode"))
    with _LOCK, _process_runtime_lock(root):
        runtime = _load_runtime(root)
        project_id = _new_runtime_id("project", runtime, name)
        project = {
            "id": project_id,
            "name": name,
            "project_type": str(payload.get("project_type") or "commerce")[:40],
            "description": " ".join(str(payload.get("description") or "").split())[:240],
            "channels": [],
            "workstreams": [],
            "relationship_model": commerce_selection["relationship_model"],
            "secondary_relationship_models": commerce_selection[
                "secondary_relationship_models"
            ],
            "commerce_forms": commerce_selection["commerce_forms"],
            "commerce_model_source": commerce_selection["commerce_model_source"],
            "commerce_model_field_sources": commerce_selection[
                "commerce_model_field_sources"
            ],
            "commerce_model_status": commerce_selection["commerce_model_status"],
            "commerce_model_owner_review_required": commerce_selection[
                "commerce_model_owner_review_required"
            ],
            "commerce_model_registry_path": commerce_selection[
                "commerce_model_registry_path"
            ],
            "commerce_model_registry_version": commerce_selection[
                "commerce_model_registry_version"
            ],
            "seller_mode": seller_mode,
            "created_at": _now_iso(),
            "created_by": str(actor or "owner")[:80],
        }
        project["commerce_dimension_route"] = commerce_model_routing_dimensions(
            root, project
        )
        _folder, local_folder = ensure_project_local_folder(root, project)
        project["local_folder"] = local_folder
        runtime["projects"].append(project)
        _write_runtime(root, runtime)
    return {
        "ok": True,
        "project": project,
        "href": f"/desktop?project={project_id}",
        "external_actions": 0,
    }


def save_workspace_commerce_profile(
    root: Path, payload: dict[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    """Save one project's local commerce classification without external work."""

    project_id = str(payload.get("project_id") or "").strip().lower()
    if not SAFE_ID.fullmatch(project_id):
        raise ValueError("项目编号无效。")
    workspace = load_workspace_config(root)
    project = next(
        (
            item
            for item in workspace.get("projects", [])
            if isinstance(item, dict)
            and str(item.get("id") or "").strip().lower() == project_id
        ),
        None,
    )
    if project is None:
        raise ValueError("项目不存在。")
    selection = normalize_commerce_model_selection(
        root,
        payload,
        inherit_from=project,
        strict=True,
    )
    if not selection["relationship_model"]:
        raise ValueError("请选择主要经营关系。")
    seller_mode = _normalize_seller_mode(
        root,
        payload.get("seller_mode", project.get("seller_mode")),
        allow_empty=False,
    )
    updated_at = _now_iso()
    profile = {
        "relationship_model": selection["relationship_model"],
        "secondary_relationship_models": list(
            selection["secondary_relationship_models"]
        ),
        "commerce_forms": list(selection["commerce_forms"]),
        "commerce_model_source": selection["commerce_model_source"],
        "commerce_model_field_sources": deepcopy(
            selection["commerce_model_field_sources"]
        ),
        "commerce_model_status": selection["commerce_model_status"],
        "commerce_model_owner_review_required": selection[
            "commerce_model_owner_review_required"
        ],
        "commerce_model_registry_path": selection[
            "commerce_model_registry_path"
        ],
        "commerce_model_registry_version": selection[
            "commerce_model_registry_version"
        ],
        "seller_mode": seller_mode,
        "classification_only": True,
        "updated_at": updated_at,
        "updated_by": " ".join(str(actor or "owner").split())[:80],
    }
    with _LOCK, _process_runtime_lock(root):
        runtime = _load_runtime(root)
        profiles = runtime.setdefault("commerce_profiles", {"projects": {}})
        projects = profiles.setdefault("projects", {})
        projects[project_id] = deepcopy(profile)
        _write_runtime(root, runtime)
    return {
        "ok": True,
        "project_id": project_id,
        "profile": profile,
        "href": f"/desktop?view=settings&project={project_id}",
        "external_actions": 0,
    }


def create_workspace_store(
    root: Path, payload: dict[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    project_id = str(payload.get("project_id") or "").strip().lower()
    platform = str(payload.get("platform") or "").strip().lower()
    country = str(payload.get("country_site") or payload.get("country") or "").strip().upper()
    name = " ".join(str(payload.get("name") or "").split()).strip()[:120]
    store_model = str(payload.get("store_model") or "").strip().lower()
    ownership = str(payload.get("ownership") or "").strip().lower()
    browser_provider = str(payload.get("browser_provider") or "").strip().lower()[:40]
    browser_profile_id = str(payload.get("browser_profile_id") or "").strip()[:160]
    if browser_provider and browser_provider not in SUPPORTED_BROWSER_PROVIDERS:
        raise ValueError("所选浏览器环境不受支持。")
    try:
        browser_profile_sequence = int(
            payload.get("browser_profile_sequence")
            or payload.get("browser_profile_seq")
            or 0
        )
    except (TypeError, ValueError):
        browser_profile_sequence = 0
    workspace = load_workspace_config(root)
    project = next(
        (
            item
            for item in workspace.get("projects", [])
            if isinstance(item, dict) and str(item.get("id") or "") == project_id
        ),
        None,
    )
    if not SAFE_ID.fullmatch(project_id) or project is None:
        raise ValueError("请选择真实项目。")
    if not name or not platform or not country or not store_model or not ownership:
        raise ValueError("店铺名称、平台、国家站点、店铺模式和归属都必须明确。")
    if store_model == "official_full_managed":
        raise ValueError("平台官方全托管只用于识别，TeeLab 当前不接入。")
    commerce_selection = normalize_commerce_model_selection(
        root,
        payload,
        inherit_from=project,
    )
    execution_identity_id = " ".join(
        str(payload.get("execution_identity_id") or "").split()
    )[:200]
    if not execution_identity_id and (browser_profile_id or browser_profile_sequence):
        browser_identity = browser_profile_id or str(browser_profile_sequence)
        execution_identity_id = f"browser:{browser_provider or 'unassigned'}:{browser_identity}"
    raw_execution_domains = payload.get("execution_domains")
    if isinstance(raw_execution_domains, str):
        raw_execution_domains = raw_execution_domains.split(",")
    execution_domains = [
        str(item).strip().lower()[:80]
        for item in (raw_execution_domains if isinstance(raw_execution_domains, list) else [])
        if str(item).strip()
    ]
    if execution_identity_id and not execution_domains:
        execution_domains = ["seller_center"]
    credential_ref = " ".join(str(payload.get("credential_ref") or "").split()).lower()[:240]
    if credential_ref and not _is_safe_credential_reference(credential_ref):
        raise ValueError("平台 API 授权必须填写本地凭据库引用，不能填写明文密钥。")
    ad_account_identity = " ".join(
        str(payload.get("ad_account_identity") or "").split()
    )[:200]
    external_id = " ".join(str(payload.get("external_id") or "").split())[:160]
    connector_script = _verified_workspace_connector_script(
        root, payload.get("store_surface_connector_script")
    )
    connection_verification = _verified_browser_store_evidence(
        root,
        payload,
        platform=platform,
        country_site=country,
        external_id=external_id,
        browser_profile_sequence=browser_profile_sequence,
    )
    with _LOCK, _process_runtime_lock(root):
        runtime = _load_runtime(root)
        store_id = _new_runtime_id("store", runtime, name)
        channel_id = str(payload.get("channel_id") or f"{platform.replace('_', '-')}-{country.lower()}")
        scope_payload = dict(payload)
        scope_payload.update(
            {
                "tenant_id": str(workspace.get("workspace_id") or "default-workspace"),
                "project_id": project_id,
                "store_binding_id": store_id,
                "execution_identity_ref": execution_identity_id,
                "platform": platform,
                "country_site": country,
                "commerce_mode": store_model,
                "ownership": ownership,
                "relationship_model": commerce_selection["relationship_model"],
                "secondary_relationship_models": commerce_selection[
                    "secondary_relationship_models"
                ],
                "commerce_forms": commerce_selection["commerce_forms"],
                "credential_ref": credential_ref,
                "ad_account_identity": ad_account_identity,
            }
        )
        scopes = []
        for domain in execution_domains or ["seller_center"]:
            scope_payload["domain"] = domain
            scopes.append(build_store_execution_scope(scope_payload).to_dict())
        store = {
            "id": store_id,
            "project_id": project_id,
            "channel_id": channel_id,
            "name": name,
            "platform": platform,
            "country_site": country,
            "store_model": store_model,
            "ownership": ownership,
            "relationship_model": commerce_selection["relationship_model"],
            "secondary_relationship_models": commerce_selection[
                "secondary_relationship_models"
            ],
            "commerce_forms": commerce_selection["commerce_forms"],
            "commerce_model_source": commerce_selection["commerce_model_source"],
            "commerce_model_field_sources": commerce_selection[
                "commerce_model_field_sources"
            ],
            "commerce_model_status": commerce_selection["commerce_model_status"],
            "commerce_model_owner_review_required": commerce_selection[
                "commerce_model_owner_review_required"
            ],
            "commerce_model_registry_path": commerce_selection[
                "commerce_model_registry_path"
            ],
            "commerce_model_registry_version": commerce_selection[
                "commerce_model_registry_version"
            ],
            "external_id": external_id,
            "browser_provider": browser_provider,
            "browser_profile_id": browser_profile_id,
            "browser_profile_sequence": browser_profile_sequence,
            "browser_profile_seq": browser_profile_sequence,
            "browser_binding_status": str(
                "verified_read_only"
                if connection_verification
                else payload.get("browser_binding_status")
                or ("profile_selected" if browser_profile_id or browser_profile_sequence else "unbound")
            )[:80],
            "execution_identity_id": execution_identity_id,
            "credential_ref": credential_ref,
            "ad_account_identity": ad_account_identity,
            "credential_ref_type": (
                "browser_profile" if execution_identity_id.startswith("browser:") else ""
            ),
            "execution_domains": execution_domains,
            "execution_scopes": scopes,
            "store_surface_connector_script": connector_script,
            "connection_verification": connection_verification,
            "route_key": scopes[0]["route_key"],
            "scope_status": (
                "executable" if all(item["executable"] for item in scopes) else "blocked"
            ),
            "status": (
                "connected_read_only"
                if connection_verification
                else "authorization_required" if external_id else "identity_required"
            ),
            "tasks": [],
            "created_at": _now_iso(),
            "created_by": str(actor or "owner")[:80],
        }
        store["commerce_dimension_route"] = commerce_model_routing_dimensions(
            root, project, store=store
        )
        runtime["stores"].append(store)
        _write_runtime(root, runtime)
    return {
        "ok": True,
        "store": store,
        "href": f"/desktop?project={project_id}&store={store_id}",
        "external_actions": 0,
    }


def save_store_connection_configuration(
    root: Path,
    project_id: str,
    store_binding_id: str,
    payload: dict[str, Any],
    *,
    actor: str = "owner",
) -> dict[str, Any]:
    """Persist safe connection references for one existing store binding.

    Raw passwords, tokens and API keys are rejected by the execution-scope
    validator. The runtime file stores only browser identity metadata and
    references to separately managed credentials/connectors.
    """

    project_id = str(project_id or "").strip().lower()
    store_binding_id = str(store_binding_id or "").strip().lower()
    if not SAFE_ID.fullmatch(project_id) or not SAFE_ID.fullmatch(store_binding_id):
        raise ValueError("项目或店铺编号无效。")
    if not isinstance(payload, dict):
        raise TypeError("连接配置必须是对象。")
    unsupported = sorted(set(payload).difference(STORE_CONNECTION_INPUT_FIELDS))
    if unsupported:
        raise ValueError("连接配置包含不支持或不安全的字段：" + "、".join(unsupported))

    patch = _connection_override_patch(payload, strict=True)
    workspace = load_workspace_config(root)
    found = find_store_in_project(workspace, project_id, store_binding_id)
    if found is None:
        raise ValueError("所选真实店铺不存在，或不属于当前项目。")
    project, channel, current_store = found

    effective_store = deepcopy(current_store)
    for key, value in patch.items():
        effective_store[key] = deepcopy(value)
    _recompute_store_connection_state(
        workspace,
        project,
        channel,
        effective_store,
        browser_override_applied=bool(
            set(patch).intersection(
                {"browser_provider", "browser_profile_id", "browser_profile_sequence"}
            )
        ),
    )
    provider = str(effective_store.get("browser_provider") or "")
    profile_id = str(effective_store.get("browser_profile_id") or "")
    profile_sequence = int(effective_store.get("browser_profile_sequence") or 0)
    if (profile_id or profile_sequence) and not provider:
        raise ValueError("选择浏览器环境前必须明确浏览器类型。")

    with _LOCK, _process_runtime_lock(root):
        runtime = _load_runtime(root)
        previous_overrides = [
            item
            for item in runtime["stores"]
            if item.get("connection_override_only") is True
            and str(item.get("id") or "").strip().lower() == store_binding_id
            and str(item.get("project_id") or "").strip().lower() == project_id
        ]
        persisted_patch: dict[str, Any] = {}
        for previous in previous_overrides:
            persisted_patch.update(_connection_override_patch(previous, strict=False))
        persisted_patch.update(patch)
        override = {
            "id": store_binding_id,
            "project_id": project_id,
            "connection_override_only": True,
            **persisted_patch,
            "connection_updated_at": _now_iso(),
            "connection_updated_by": " ".join(str(actor or "owner").split())[:80],
        }
        runtime["stores"] = [
            item
            for item in runtime["stores"]
            if not (
                item.get("connection_override_only") is True
                and str(item.get("id") or "").strip().lower() == store_binding_id
                and str(item.get("project_id") or "").strip().lower() == project_id
            )
        ]
        runtime["stores"].append(override)
        _write_runtime(root, runtime)

    credential_ref = str(effective_store.get("credential_ref") or "")
    erp_connector_id = str(effective_store.get("erp_connector_id") or "")
    return {
        "ok": True,
        "project_id": project_id,
        "store_binding_id": store_binding_id,
        "configuration": {
            "browser_configured": bool(provider and (profile_id or profile_sequence)),
            "browser_provider": provider,
            "browser_profile_sequence": profile_sequence,
            "platform_api_reference_configured": bool(credential_ref),
            "erp_connector_configured": bool(erp_connector_id),
            "route_key": str(effective_store.get("route_key") or ""),
            "scope_status": str(effective_store.get("scope_status") or "blocked"),
        },
        "message": "当前店铺的连接引用已保存；在线能力仍以连接检测结果为准。",
    }
