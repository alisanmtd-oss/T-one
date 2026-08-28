from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


SEA_RESTRICTED_PLATFORMS = {"tiktok", "tiktok_shop", "tiktokshop", "shopee", "lazada"}
COMMERCE_MODE_ALIASES = {
    "local_store": "local",
    "local_seller": "local",
    "cross_border_seller": "cross_border",
    "tiktok_accu_local": "local",
    "semi_managed_crossborder": "semi_managed",
    "semi_managed_cross_border": "semi_managed",
    "semi_managed_local": "semi_managed",
}
OWNERSHIP_ALIASES = {
    "self_store": "self_owned",
    "designer_self_store": "self_owned",
    "designer_owned": "self_owned",
    "teelab_co_ops": "platform_co_ops",
}


class UnsafeCredentialInputError(ValueError):
    """Raised when an execution scope payload contains raw credential fields."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalized_token(value: Any) -> str:
    return re.sub(r"[\s-]+", "_", _text(value).lower())


def _normalize_commerce_mode(value: Any) -> str:
    raw = _text(value)
    normalized = _normalized_token(raw)
    if (
        "official_full_managed" in normalized
        or normalized in {"full_managed", "full_service"}
        or "官方全托管" in raw
        or "平台全托管" in raw
    ):
        return "official_full_managed"
    return COMMERCE_MODE_ALIASES.get(normalized, normalized)


def _normalize_ownership(value: Any) -> str:
    normalized = _normalized_token(value)
    return OWNERSHIP_ALIASES.get(normalized, normalized)


def _normalize_field_name(value: Any) -> str:
    text = re.sub(r"(?<!^)(?=[A-Z])", "_", _text(value))
    return re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()


def _is_raw_credential_field(field_name: Any) -> bool:
    normalized = _normalize_field_name(field_name)
    if normalized == "credential_ref":
        return False
    parts = set(normalized.split("_"))
    if parts.intersection({"password", "secret", "token"}):
        return True
    if normalized in {
        "api_key",
        "api_key_env",
        "access_key",
        "private_key",
        "key_env",
        "credential",
        "credentials",
        "credential_value",
    }:
        return True
    return normalized.endswith(("_api_key", "_access_key", "_private_key"))


def _raw_credential_paths(value: Any, path: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            current = f"{path}.{key}" if path else str(key)
            if _is_raw_credential_field(key):
                paths.append(current)
                continue
            paths.extend(_raw_credential_paths(nested, current))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, nested in enumerate(value):
            paths.extend(_raw_credential_paths(nested, f"{path}[{index}]"))
    return paths


def _scope_component(value: Any) -> str:
    return _text(value).replace("%", "%25").replace("|", "%7C").replace("=", "%3D")


def make_route_key(platform: Any, country_site: Any, commerce_mode: Any) -> str:
    return ":".join(
        (
            _normalized_token(platform),
            _text(country_site).upper(),
            _normalize_commerce_mode(commerce_mode),
        )
    )


def make_scope_key(
    *,
    route_key: Any,
    tenant_id: Any,
    project_id: Any,
    store_binding_id: Any,
    execution_identity_ref: Any,
    ownership: Any,
    domain: Any,
    ad_account_identity: Any = "",
) -> str:
    fields = (
        ("route_key", route_key),
        ("tenant_id", tenant_id),
        ("project_id", project_id),
        ("store_binding_id", store_binding_id),
        ("execution_identity_ref", execution_identity_ref),
        ("ownership", ownership),
        ("domain", domain),
        ("ad_account_identity", ad_account_identity),
    )
    return "|".join(f"{key}={_scope_component(value)}" for key, value in fields)


def _is_sea_region(country_site: str) -> bool:
    compact = re.sub(r"[^A-Z0-9\u4e00-\u9fff]+", "", country_site.upper())
    return compact in {"SEA", "SOUTHEASTASIA", "东南亚"}


@dataclass(frozen=True, slots=True)
class StoreExecutionScope:
    tenant_id: str
    project_id: str
    store_binding_id: str
    execution_identity_ref: str
    platform: str
    country_site: str
    commerce_mode: str
    ownership: str
    domain: str
    credential_ref: str = ""
    ad_account_identity: str = ""
    route_key: str = field(init=False)
    scope_key: str = field(init=False)
    status: str = field(init=False)
    executable: bool = field(init=False)
    blocking_reasons: tuple[str, ...] = field(init=False)

    def __post_init__(self) -> None:
        normalized = {
            "tenant_id": _text(self.tenant_id),
            "project_id": _text(self.project_id),
            "store_binding_id": _text(self.store_binding_id),
            "execution_identity_ref": _text(self.execution_identity_ref),
            "platform": _normalized_token(self.platform),
            "country_site": _text(self.country_site).upper(),
            "commerce_mode": _normalize_commerce_mode(self.commerce_mode),
            "ownership": _normalize_ownership(self.ownership),
            "domain": _normalized_token(self.domain),
            "credential_ref": _text(self.credential_ref),
            "ad_account_identity": _text(self.ad_account_identity),
        }
        for name, value in normalized.items():
            object.__setattr__(self, name, value)

        route_key = make_route_key(
            normalized["platform"],
            normalized["country_site"],
            normalized["commerce_mode"],
        )
        scope_key = make_scope_key(
            route_key=route_key,
            tenant_id=normalized["tenant_id"],
            project_id=normalized["project_id"],
            store_binding_id=normalized["store_binding_id"],
            execution_identity_ref=normalized["execution_identity_ref"],
            ownership=normalized["ownership"],
            domain=normalized["domain"],
            ad_account_identity=normalized["ad_account_identity"],
        )
        object.__setattr__(self, "route_key", route_key)
        object.__setattr__(self, "scope_key", scope_key)

        reasons = [
            f"missing_{name}"
            for name in (
                "tenant_id",
                "project_id",
                "store_binding_id",
                "execution_identity_ref",
                "platform",
                "country_site",
                "commerce_mode",
                "ownership",
                "domain",
            )
            if not normalized[name]
        ]
        unsupported = normalized["commerce_mode"] == "official_full_managed"
        if unsupported:
            reasons.append("official_full_managed_unsupported")
        if (
            normalized["platform"] in SEA_RESTRICTED_PLATFORMS
            and _is_sea_region(normalized["country_site"])
        ):
            reasons.append("sea_region_not_executable")
        if normalized["domain"] == "ads" and not normalized["ad_account_identity"]:
            reasons.append("ad_account_identity_required")

        status = "unsupported" if unsupported else ("blocked" if reasons else "executable")
        object.__setattr__(self, "blocking_reasons", tuple(dict.fromkeys(reasons)))
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "executable", status == "executable")

    @property
    def is_executable(self) -> bool:
        return self.executable

    @property
    def unsupported(self) -> bool:
        return self.status == "unsupported"

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "project_id": self.project_id,
            "store_binding_id": self.store_binding_id,
            "execution_identity_ref": self.execution_identity_ref,
            "platform": self.platform,
            "country_site": self.country_site,
            "commerce_mode": self.commerce_mode,
            "ownership": self.ownership,
            "domain": self.domain,
            "credential_ref": self.credential_ref,
            "ad_account_identity": self.ad_account_identity,
            "route_key": self.route_key,
            "scope_key": self.scope_key,
            "status": self.status,
            "executable": self.executable,
            "blocking_reasons": list(self.blocking_reasons),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "StoreExecutionScope":
        return build_store_execution_scope(payload)


def _first(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return ""


def build_store_execution_scope(payload: Mapping[str, Any]) -> StoreExecutionScope:
    if not isinstance(payload, Mapping):
        raise TypeError("Store execution scope payload must be a mapping.")
    unsafe_paths = _raw_credential_paths(payload)
    if unsafe_paths:
        fields = ", ".join(sorted(unsafe_paths))
        raise UnsafeCredentialInputError(
            f"Raw credential fields are not accepted; use credential_ref only: {fields}"
        )
    return StoreExecutionScope(
        tenant_id=_first(payload, "tenant_id"),
        project_id=_first(payload, "project_id"),
        store_binding_id=_first(payload, "store_binding_id"),
        execution_identity_ref=_first(
            payload, "execution_identity_ref", "execution_identity_id"
        ),
        platform=_first(payload, "platform", "platform_id"),
        country_site=_first(payload, "country_site", "country_code", "country"),
        commerce_mode=_first(payload, "commerce_mode", "store_model", "shop_type"),
        ownership=_first(payload, "ownership", "store_ownership"),
        domain=_first(payload, "domain", "execution_domain"),
        credential_ref=_first(payload, "credential_ref"),
        ad_account_identity=_first(
            payload, "ad_account_identity", "ads_account_identity", "ad_account_id"
        ),
    )


def create_store_execution_scope(payload: Mapping[str, Any]) -> StoreExecutionScope:
    return build_store_execution_scope(payload)


__all__ = [
    "StoreExecutionScope",
    "UnsafeCredentialInputError",
    "build_store_execution_scope",
    "create_store_execution_scope",
    "make_route_key",
    "make_scope_key",
]
