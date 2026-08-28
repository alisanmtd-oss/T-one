from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .types import IntakeRecord


DASHBOARD_SURFACES = frozenset(
    {
        "realtime_dashboard",
        "module_dashboard",
        "project_dashboard",
        "business_dashboard",
        "ai_analysis",
    }
)

LEARNING_ASSET_TYPES = frozenset(
    {
        "learning_website",
        "user_material_pack",
        "platform_learning_pack",
        "unconnected_ai_research_pack",
    }
)

LEARNING_SOURCE_KINDS = frozenset(
    {
        "learning_website",
        "course_original",
        "public_or_login_gated_course_index",
        "official_public_learning_index",
        "public_template_index",
        "community_case",
        "platform_rule_learning_pack",
        "user_authorized_material",
        "protected_user_provided_course_export",
        "user_collected_unattributed_compilations",
        "unconnected_integration_candidate",
        "highlighted_external_ai_tool",
    }
)

LEARNING_SOURCE_REFS = frozenset(
    {
        "config/learning_direction_library_registry.json",
        "config/learning_sources.json",
        "config/user_collected_training_materials.json",
        "config/platform_rule_library_manifest.json",
        "config/github_capability_registry.json",
        "outputs/conversation_audit/platform_course_source_index_2026-07-21.json",
    }
)


@dataclass(frozen=True, slots=True)
class DashboardSourceAdmission:
    admitted: bool
    surface: str
    reason_code: str
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "admitted": self.admitted,
            "surface": self.surface,
            "reason_code": self.reason_code,
            "explanation": self.explanation,
        }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _record_parts(value: IntakeRecord | Mapping[str, Any]) -> tuple[Mapping[str, Any], Mapping[str, Any], str, str]:
    if isinstance(value, IntakeRecord):
        fields = _mapping(value.fields)
        metadata = _mapping(value.metadata)
        return fields, metadata, str(value.source or ""), str(value.record_type or "")
    payload = _mapping(value)
    fields = _mapping(payload.get("fields")) or payload
    metadata = _mapping(payload.get("metadata"))
    return (
        fields,
        metadata,
        str(payload.get("source") or fields.get("source") or ""),
        str(payload.get("record_type") or fields.get("record_type") or ""),
    )


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def dashboard_source_admission(
    value: IntakeRecord | Mapping[str, Any],
    *,
    surface: str = "realtime_dashboard",
) -> DashboardSourceAdmission:
    """Decide whether an input may power a business dashboard or AI analysis.

    This is an admission boundary, not a data-quality score. Learning websites,
    user training packs, platform rule candidates, GitHub candidates and
    unconnected AI research remain available to training/evaluation surfaces,
    but they can never become business metrics or connected/runtime claims.
    """

    normalized_surface = str(surface or "realtime_dashboard").strip().casefold()
    if normalized_surface not in DASHBOARD_SURFACES:
        return DashboardSourceAdmission(
            admitted=False,
            surface=normalized_surface,
            reason_code="unsupported_surface",
            explanation="该来源只可按已登记用途使用；请求的展示面不属于经营数据入口。",
        )

    fields, metadata, source, record_type = _record_parts(value)
    classification = _first_text(
        fields.get("classification"),
        metadata.get("classification"),
    ).casefold()
    asset_type = _first_text(fields.get("asset_type"), metadata.get("asset_type")).casefold()
    source_kind = _first_text(
        fields.get("source_kind"),
        metadata.get("source_kind"),
    ).casefold()
    source_ref = _first_text(
        fields.get("source_ref"),
        metadata.get("source_ref"),
        fields.get("source_file"),
        metadata.get("source_file"),
    ).replace("\\", "/").casefold()

    if classification == "learning_only":
        return DashboardSourceAdmission(
            admitted=False,
            surface=normalized_surface,
            reason_code="learning_only_classification",
            explanation="学习资产只能进入训练、蒸馏和回归，不能进入经营大盘或AI经营预测。",
        )
    if asset_type in LEARNING_ASSET_TYPES:
        return DashboardSourceAdmission(
            admitted=False,
            surface=normalized_surface,
            reason_code="learning_asset_type",
            explanation="课程、资料包、规则学习包和未接入AI研究包不是经营事实。",
        )
    if source_kind in LEARNING_SOURCE_KINDS or source_kind.endswith("_learning_index"):
        return DashboardSourceAdmission(
            admitted=False,
            surface=normalized_surface,
            reason_code="learning_source_kind",
            explanation="该来源类别只用于学习或研究，不能产生经营指标。",
        )
    if source_ref and any(source_ref.endswith(item.casefold()) for item in LEARNING_SOURCE_REFS):
        return DashboardSourceAdmission(
            admitted=False,
            surface=normalized_surface,
            reason_code="learning_source_registry",
            explanation="该记录来自学习资产注册表，不得进入经营大盘。",
        )
    if fields.get("show_in_dashboard") is False or metadata.get("show_in_dashboard") is False:
        return DashboardSourceAdmission(
            admitted=False,
            surface=normalized_surface,
            reason_code="dashboard_visibility_denied",
            explanation="来源已明确禁止在经营大盘显示。",
        )
    if fields.get("benchmark_only") is True or metadata.get("benchmark_only") is True:
        return DashboardSourceAdmission(
            admitted=False,
            surface=normalized_surface,
            reason_code="benchmark_only",
            explanation="竞品截图和界面基准只能用于产品设计，不是本企业经营数据。",
        )

    if record_type == "store_metric_snapshot":
        return DashboardSourceAdmission(
            admitted=True,
            surface=normalized_surface,
            reason_code="business_metric_candidate",
            explanation="可继续接受店铺身份、时间窗、数值和真实性校验。",
        )
    if record_type in {
        "actual_platform_settlement",
        "live_session_fact",
        "creator_affiliate_fact",
        "business_action_event_fact",
    }:
        return DashboardSourceAdmission(
            admitted=True,
            surface=normalized_surface,
            reason_code="business_fact_candidate",
            explanation="可继续接受业务事实的范围、来源、时效和证据校验。",
        )

    return DashboardSourceAdmission(
        admitted=False,
        surface=normalized_surface,
        reason_code="not_a_business_fact",
        explanation=(
            f"{record_type or source or 'unknown'} 不是允许进入经营大盘的业务事实类型。"
        ),
    )


def dashboard_source_is_admitted(
    value: IntakeRecord | Mapping[str, Any],
    *,
    surface: str = "realtime_dashboard",
) -> bool:
    return dashboard_source_admission(value, surface=surface).admitted
