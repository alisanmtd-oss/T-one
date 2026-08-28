from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

from . import product_scout
from . import web_audit
from .storage import read_records

# TK体系2.0 skill agents. Each agent runs one operational playbook from the
# commerce skill registry against real inputs and returns a structured verdict
# tied to docs/TK_OPERATION_STANDARD_V2.md. The registry is the single source of
# truth for skill metadata; this module only adds the executable judgement.

SKILL_REGISTRY_FILE = "commerce_skill_registry.json"

# Thresholds come straight from TK体系2.0 第3课(测品) / 第5课(达人); kept as named
# constants so they live in one place and can be tuned without touching logic.
TEST_CTR_TIERS_PCT: list[tuple[float, str]] = [(3.0, "大爆品"), (2.0, "优秀"), (1.5, "合格")]
TEST_CVR_TIERS_PCT: list[tuple[float, str]] = [(15.0, "大爆品"), (10.0, "优秀"), (5.0, "合格")]

INFLUENCER_QUALIFY = {
    "min_fans": 5000,
    "max_fans": 500000,
    "min_vertical_pct": 80.0,
    "min_avg_views": 50000,
    "min_like_pct": 3.0,
    "min_fulfil_pct": 65.0,
    "min_audience_overlap_pct": 60.0,
}

TITLE_SEGMENTS = ["流量词", "核心词", "场景词", "信任词", "长尾词"]
# 绝对化 / 虚假 / 侵权词（部分），命中即提示改写。
FORBIDDEN_TITLE_WORDS = ["最佳", "第一", "顶级", "全网最低", "全球最", "100%", "平替", "同款", "假一赔"]


def _num(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(str(value).replace(",", "").replace("$", "").replace("%", "").strip())
    except ValueError:
        return 0.0


def _grade(value: float, tiers: list[tuple[float, str]]) -> str:
    for threshold, label in tiers:
        if value >= threshold:
            return label
    return "不合格"


def load_skill_registry(root: Path) -> dict[str, Any]:
    try:
        return json.loads((root / "config" / SKILL_REGISTRY_FILE).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


OPERATION_SKILL_KEYS = ["tk_operation_skills", "multichannel_operation_skills"]


def _operation_skills(registry: dict[str, Any]) -> list[dict[str, Any]]:
    skills: list[dict[str, Any]] = []
    for key in OPERATION_SKILL_KEYS:
        value = registry.get(key)
        if isinstance(value, list):
            skills.extend(item for item in value if isinstance(item, dict))
    return skills


def _connector_skills(registry: dict[str, Any]) -> list[dict[str, Any]]:
    """注册表 `skills` 里的连接器（对接 Keepa/FastMoss/智慧芽/HeyGen 等数据源/AI）。"""
    value = registry.get("skills")
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _all_runnable_metas(registry: dict[str, Any]) -> list[dict[str, Any]]:
    return _operation_skills(registry) + _connector_skills(registry)



def _connector_api_source_label(api_source_id: str) -> str:
    if not api_source_id:
        return "本地/浏览器能力，无外部 API 绑定"
    if "placeholder" in api_source_id.lower():
        return "候选连接，待确认接口和授权"
    return "已登记连接配置，待授权校验"


def run_connector(meta: dict[str, Any]) -> dict[str, Any]:
    """Return customer-safe connector readiness without leaking placeholder IDs."""
    integration = meta.get("integration") or {}
    required = [k for k in (integration.get("required_env") or []) if k]
    missing = [k for k in required if not os.environ.get(k)]
    api_source_id = str(integration.get("api_source_id") or "")
    enabled = bool(meta.get("enabled", True))
    common = {
        "recommendation": meta.get("recommendation", ""),
        "source_ref": "后台已记录，客户侧不展示原始来源说明。",
        "guidance": meta.get("operator_prompt", ""),
        "enabled": enabled,
        "api_source": _connector_api_source_label(api_source_id),
        "real_action_boundary": "只读检查或草稿建议；真实外部动作仍进入待确认队列。",
    }
    if missing:
        return {
            **common,
            "status": "待配置授权",
            "connection_state": "missing_authorization" if enabled else "candidate_disabled",
            "needs_env": missing,
            "note": f"接入前需要配置授权环境变量：{', '.join(missing)}。未配置时只能作为候选工具或本地判断参考。",
        }
    if not required:
        return {
            **common,
            "status": "本地可用",
            "connection_state": "local_available" if enabled else "candidate_disabled",
            "note": "不需要第三方密钥；由本地记录、浏览器读取或模型判断能力执行，真实动作不自动提交。",
        }
    return {
        **common,
        "status": "授权已配置，待只读验证",
        "connection_state": "authorization_configured" if enabled else "candidate_disabled",
        "note": "授权变量已存在；仍需要按平台、国家站点、店铺模式和执行身份做只读验证后才能进入生产流程。",
    }


def list_skill_agents(root: Path) -> list[dict[str, Any]]:
    """All runnable operation skills (TK体系2.0 + 多平台) with executability."""
    registry = load_skill_registry(root)
    connector_ids = {str(s.get("id") or "") for s in _connector_skills(registry)}
    result: list[dict[str, Any]] = []
    for skill in _all_runnable_metas(registry):
        if not isinstance(skill, dict):
            continue
        sid = str(skill.get("id") or "")
        result.append({
            "id": sid,
            "name": skill.get("name", sid),
            "agent_module": skill.get("agent_module", ""),
            "standard_ref": skill.get("standard_ref", ""),
            "key_thresholds": skill.get("key_thresholds", ""),
            "executable": sid in _HANDLERS or sid in connector_ids,
            "kind": "connector" if sid in connector_ids else "operation",
            "enabled": bool(skill.get("enabled", True)),
        })
    return result


# --- executable skill handlers (pure; return structured verdicts) ----------------

def run_product_selection(payload: dict[str, Any]) -> dict[str, Any]:
    scored = product_scout.score_product(payload)
    return {"verdict": scored["verdict_label"], "total": scored["total"], "scores": scored["scores"], "rationale": scored["rationale"]}


def run_product_testing(payload: dict[str, Any]) -> dict[str, Any]:
    ctr = _num(payload.get("ctr"))
    cvr = _num(payload.get("cvr"))
    gpm = _num(payload.get("gpm"))
    price = _num(payload.get("price"))
    ctr_grade = _grade(ctr, TEST_CTR_TIERS_PCT)
    cvr_grade = _grade(cvr, TEST_CVR_TIERS_PCT)
    gpm_explosive = bool(gpm and price and gpm >= price)
    if ctr_grade == "大爆品" and cvr_grade == "大爆品":
        verdict, action = "大爆品", "立即放量 + 备货 + 大量铺达人"
    elif "不合格" not in (ctr_grade, cvr_grade):
        verdict, action = "合格", "继续优化素材/价格，达标后放量"
    else:
        verdict, action = "不合格", "淘汰或换素材重测"
    if gpm_explosive:
        action = "GPM≥客单价=爆品信号；" + action
    return {"verdict": verdict, "ctr_grade": ctr_grade, "cvr_grade": cvr_grade, "gpm_explosive": gpm_explosive, "next_action": action}


def run_influencer_tiering(payload: dict[str, Any]) -> dict[str, Any]:
    fans = _num(payload.get("fans"))
    q = INFLUENCER_QUALIFY
    if fans >= 1_000_000:
        tier, role = "S4", "头部/破圈层"
    elif fans >= 100_000:
        tier, role = "S3", "泛垂/规模转化层"
    elif fans >= q["min_fans"]:
        tier, role = "S2", "垂类信任层"
    else:
        tier, role = "S1", "素人/社会证明层"
    checks = {
        "粉丝量级": q["min_fans"] <= fans <= q["max_fans"],
        "内容垂直度": _num(payload.get("vertical_pct")) >= q["min_vertical_pct"],
        "均播": _num(payload.get("avg_views")) >= q["min_avg_views"],
        "点赞率": _num(payload.get("like_pct")) >= q["min_like_pct"],
        "履约率": _num(payload.get("fulfil_pct")) >= q["min_fulfil_pct"],
        "画像重合": _num(payload.get("audience_overlap_pct")) >= q["min_audience_overlap_pct"],
    }
    failed = [name for name, ok in checks.items() if not ok]
    qualified = not failed
    return {
        "tier": tier,
        "role": role,
        "qualified": qualified,
        "failed_checks": failed,
        "recommendation": "进核心建联/独家佣金" if qualified else "暂不深度合作：先补 " + "、".join(failed),
    }


def run_ads_gmvmax_diagnose(payload: dict[str, Any]) -> dict[str, Any]:
    ctr = _num(payload.get("ctr"))
    cvr = _num(payload.get("cvr"))
    impressions_low = bool(payload.get("impressions_low"))
    if impressions_low:
        cause, fix = "eCPM低/素材差", "小幅提价；无效则立即换素材，优化前3秒钩子"
    elif ctr >= 2.0 and cvr < 1.0:
        cause, fix = "引来错误人群/承接不足", "优化承接(锚点/详情/价格)，用更精准素材过滤人群"
    elif ctr < 1.0 and cvr >= 2.0:
        cause, fix = "素材吸引力不足", "优化开头钩子、更强利益承诺、蹭热点"
    else:
        cause, fix = "数据正常或样本不足", "持续喂多样化素材，尊重3-5天学习期"
    return {"diagnosis": cause, "fix": fix}


def run_product_card_title_audit(payload: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("title") or "").strip()
    front30 = title[:30]
    hits = [word for word in FORBIDDEN_TITLE_WORDS if word in title]
    segments = [seg for seg in title.replace("｜", "|").split("|") if seg.strip()]
    five_segment_ok = len(segments) >= len(TITLE_SEGMENTS)
    issues: list[str] = []
    if not title:
        issues.append("标题为空")
    if hits:
        issues.append("含禁用词(绝对化/虚假/侵权)：" + "、".join(hits))
    if not five_segment_ok:
        issues.append(f"建议五段式(竖杠分隔)：{'/'.join(TITLE_SEGMENTS)}（当前 {len(segments)} 段）")
    if len(title) > 255:
        issues.append("超过255字符上限")
    return {
        "pass": not issues,
        "front_30_chars": front30,
        "segment_count": len(segments),
        "forbidden_hits": hits,
        "issues": issues,
    }


def run_content_hooks(payload: dict[str, Any]) -> dict[str, Any]:
    """Build an evidence-gated local content framework without publishing.

    This is deliberately deterministic: the visual/model route supplies observed
    facts, while this skill turns those facts into editable hook directions.  It
    never invents product benefits, account performance, music rights, or a CTA.
    """
    observations = [
        str(item.get("statement") if isinstance(item, dict) else item).strip()
        for item in (payload.get("observations") or [])
    ]
    observations = [item for item in observations if item][:12]
    product_name = str(payload.get("product_name") or "").strip()
    audience = str(payload.get("audience") or "").strip()
    verified_benefit = str(payload.get("verified_benefit") or "").strip()
    unknowns: list[str] = []
    if not product_name:
        unknowns.append("product_name")
    if not audience:
        unknowns.append("audience")
    if not verified_benefit:
        unknowns.append("verified_benefit")
    if not observations:
        unknowns.append("visual_observations")
    subject = product_name or "待确认商品"
    benefit = verified_benefit or "待核实卖点"
    return {
        "status": "draft_ready" if observations else "needs_observed_evidence",
        "evidence_observations": observations,
        "hook_directions": [
            {"type": "视觉钩子", "draft": f"前 3 秒直接展示 {subject} 的可见变化；只使用已观察画面。"},
            {"type": "提问钩子", "draft": f"向 {audience or '待确认受众'} 提问其真实痛点，不预设答案。"},
            {"type": "利益钩子", "draft": f"仅在证据确认后表达：{benefit}。"},
            {"type": "悬念钩子", "draft": "先展示可验证结果，再解释过程；未知效果不得补写。"},
            {"type": "挑战钩子", "draft": "挑战条件、样本和结果必须可复现，当前仅生成草稿。"},
            {"type": "情境钩子", "draft": "优先真实使用情境、自然口吻和清晰字幕，不冒充消费者见证。"},
        ],
        "editing_guardrails": [
            "前 3 秒建立单一可见信息",
            "建议每 1-2 秒检查镜头信息增量，但不机械硬切",
            "字幕只写已核实事实；音乐和素材权利保持待复核",
            "发布、挂车、账号操作和广告动作均不在本地 Skill 内执行",
        ],
        "unknowns": unknowns,
        "native_video_model_used": False,
        "external_business_action_count": 0,
    }


# Cross-platform executors (Amazon / 独立站 DTC / 外贸 B2B). General e-commerce
# best-practice thresholds, kept as named constants.
HEALTHY_MARGIN_PCT = 20.0
MIN_LTV_CAC_RATIO = 3.0


def run_unit_economics(payload: dict[str, Any]) -> dict[str, Any]:
    """Margin + CAC/LTV gate. Works for Amazon, independent store and POD."""
    price = _num(payload.get("price"))
    profit = product_scout.estimate_profit(
        price,
        cost_ratio=_num(payload.get("cost_ratio")) or 0.30,
        platform_fee_ratio=_num(payload.get("platform_fee_ratio")) or 0.08,
        ad_ratio=_num(payload.get("ad_ratio")) or 0.15,
        return_ratio=_num(payload.get("return_ratio")) or 0.05,
        ship_cost=_num(payload.get("ship_cost")) or 2.0,
    )
    cac = _num(payload.get("cac"))
    ltv = _num(payload.get("ltv"))
    ltv_cac = round(ltv / cac, 2) if cac else 0.0
    issues: list[str] = []
    if profit["margin_pct"] < HEALTHY_MARGIN_PCT:
        issues.append(f"毛利率 {profit['margin_pct']}% 偏低（健康线≥{HEALTHY_MARGIN_PCT}%）")
    if cac and profit["net_unit_profit"] < cac:
        issues.append("单位净利 < 获客成本(CAC)，单次成交亏损")
    if cac and ltv and ltv_cac < MIN_LTV_CAC_RATIO:
        issues.append(f"LTV/CAC {ltv_cac} < {MIN_LTV_CAC_RATIO}，复购价值不足以覆盖获客")
    return {"verdict": "健康" if not issues else "需优化", "profit": profit, "ltv_cac": ltv_cac, "issues": issues}


def run_web_audit(payload: dict[str, Any]) -> dict[str, Any]:
    """SEO/AEO/GEO audit of an operator's own site (local path) or pasted HTML."""
    path = str(payload.get("path") or "").strip()
    if path:
        return web_audit.audit_site(path)
    return web_audit.audit_html(str(payload.get("html") or ""), url=str(payload.get("url") or ""))


def run_b2b_inquiry(payload: dict[str, Any]) -> dict[str, Any]:
    """Score / qualify a 外贸 B2B inquiry (lead)."""
    quantity = _num(payload.get("quantity"))
    moq = _num(payload.get("moq"))
    has_company = bool(payload.get("company"))
    target_price = _num(payload.get("target_price"))
    floor_price = _num(payload.get("floor_price"))
    checks = {
        "达到MOQ": (not moq) or quantity >= moq,
        "公司信息": has_company,
        "目标价可做": (not target_price) or (not floor_price) or target_price >= floor_price,
    }
    failed = [name for name, ok in checks.items() if not ok]
    score = int(100 - len(failed) * 30)
    return {
        "qualified": not failed,
        "score": max(0, score),
        "failed_checks": failed,
        "recommendation": "优先报价/打样" if not failed else "先补：" + "、".join(failed),
    }


AMAZON_EVIDENCE_STATES = {
    "official_policy",
    "live_store_fact",
    "buyer_page_observation",
    "historical_store_fact",
    "third_party_observation",
    "inference",
    "draft",
    "unverified_claim",
}


def run_amazon_commerce_evidence_gate(payload: dict[str, Any]) -> dict[str, Any]:
    """Gate Amazon conclusions and external actions on scoped, time-bound evidence."""
    required = [
        "marketplace",
        "country_site",
        "store_binding_id",
        "route_key",
        "entity_type",
        "entity_id",
        "captured_at",
        "evidence_state",
        "source_refs",
    ]
    missing = [name for name in required if not payload.get(name)]
    state = str(payload.get("evidence_state") or "")
    if state and state not in AMAZON_EVIDENCE_STATES:
        missing.append("valid_evidence_state")

    route_key = str(payload.get("route_key") or "")
    country_site = str(payload.get("country_site") or "")
    route_mismatch = bool(route_key and country_site and f":{country_site}:" not in route_key)
    if route_mismatch:
        missing.append("route_country_match")

    current_fact_states = {"official_policy", "live_store_fact", "buyer_page_observation"}
    fact_claim_allowed = not missing and state in current_fact_states
    external_effect = bool(payload.get("external_effect"))
    owner_confirmed = bool(payload.get("owner_confirmed"))

    if missing:
        verdict = "blocked_missing_identity_or_evidence"
    elif external_effect and not owner_confirmed:
        verdict = "requires_owner_confirmation"
    elif state not in current_fact_states:
        verdict = "analysis_only_not_current_fact"
    else:
        verdict = "ready"

    return {
        "verdict": verdict,
        "missing": sorted(set(missing)),
        "evidence_state": state,
        "fact_claim_allowed": fact_claim_allowed,
        "analysis_allowed": True,
        "external_effect": external_effect,
        "owner_confirmation_required": external_effect and not owner_confirmed,
        "next_action": (
            "Collect missing scoped evidence."
            if missing
            else "Queue the action for owner confirmation."
            if external_effect and not owner_confirmed
            else "Use as analysis or hypothesis only; recheck a current authoritative surface before claiming live state."
            if state not in current_fact_states
            else "Proceed within the declared evidence and action scope."
        ),
    }


_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "tk-product-selection": run_product_selection,
    "tk-product-testing": run_product_testing,
    "tk-influencer-tiering": run_influencer_tiering,
    "tk-ads-gmvmax": run_ads_gmvmax_diagnose,
    "tk-product-card-audit": run_product_card_title_audit,
    "tk-content-hooks": run_content_hooks,
    "amazon-listing-audit": run_product_card_title_audit,
    "amazon-profit-check": run_unit_economics,
    "amazon-commerce-operator": run_amazon_commerce_evidence_gate,
    "dtc-unit-economics": run_unit_economics,
    "b2b-inquiry-score": run_b2b_inquiry,
    "web-seo-geo-audit": run_web_audit,
}


def run_skill_agent(root: Path, skill_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run one skill agent. Executable skills return a judgement; reference-only
    skills return their playbook guidance from the registry."""
    payload = payload or {}
    handler = _HANDLERS.get(skill_id)
    registry = load_skill_registry(root)
    meta = next((s for s in _all_runnable_metas(registry) if s.get("id") == skill_id), None)
    if meta is None:
        return {"ok": False, "error": f"未知技能：{skill_id}"}
    base = {"ok": True, "skill_id": skill_id, "name": meta.get("name"), "standard_ref": meta.get("standard_ref")}
    if handler is not None:
        return {**base, "executable": True, "result": handler(payload)}
    if skill_id in {str(s.get("id") or "") for s in _connector_skills(registry)}:
        return {**base, "executable": True, "kind": "connector", "result": run_connector(meta)}
    return {**base, "executable": False, "guidance": meta.get("operator_prompt", ""), "key_thresholds": meta.get("key_thresholds", "")}


# --- batch runners over local Data Lake records -----------------------------------

BATCH_PRODUCT_TYPES = {"platform_ranking_signal", "hot_link", "viral_content_signal"}
BATCH_INFLUENCER_TYPES = {"creator_spike_event", "influencer_profile", "influencer_cooperation", "store_metric_snapshot"}
BATCH_SUPPORTED = {"tk-product-selection", "tk-product-card-audit", "amazon-listing-audit", "tk-influencer-tiering"}


def _field(fields: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = fields.get(key)
        if value not in (None, ""):
            return value
    return ""


def _batch_payload(skill_id: str, record: Any) -> tuple[dict[str, Any], str]:
    fields = getattr(record, "fields", {}) or {}
    if skill_id == "tk-product-selection":
        return product_scout.signals_from_record(record), str(_field(fields, "product_name", "title", "url") or "(商品)")
    if skill_id in {"tk-product-card-audit", "amazon-listing-audit"}:
        title = str(_field(fields, "product_name", "title", "page_title"))
        return {"title": title}, title or "(无标题)"
    if skill_id == "tk-influencer-tiering":
        label = str(_field(fields, "creator_handle", "profile_url", "store_name") or "(达人)")
        payload = {
            "fans": _field(fields, "fans", "follower_count", "followers"),
            "vertical_pct": _field(fields, "vertical_pct", "vertical"),
            "avg_views": _field(fields, "avg_views", "latest_video_views", "baseline_avg_views", "average_views", "current_views"),
            "like_pct": _field(fields, "like_pct", "engagement_rate"),
            "fulfil_pct": _field(fields, "fulfil_pct", "fulfillment_rate"),
            "audience_overlap_pct": _field(fields, "audience_overlap_pct", "audience_match"),
        }
        return payload, label
    return {}, ""


def run_skill_batch(root: Path, skill_id: str, limit: int = 50) -> dict[str, Any]:
    """Run an executable skill across the relevant local records and return rows."""
    handler = _HANDLERS.get(skill_id)
    if handler is None or skill_id not in BATCH_SUPPORTED:
        return {"ok": False, "error": "该技能暂不支持本地批量（方法论技能或需外部数据）。"}
    types = BATCH_INFLUENCER_TYPES if skill_id == "tk-influencer-tiering" else BATCH_PRODUCT_TYPES
    records = [record for record in read_records(root) if record.record_type in types]
    records.sort(key=lambda record: record.created_at, reverse=True)
    rows: list[dict[str, Any]] = []
    for record in records[: max(1, limit)]:
        payload, label = _batch_payload(skill_id, record)
        if not any(str(value).strip() for value in payload.values()):
            continue
        rows.append({"label": label, "result": handler(payload)})
    return {"ok": True, "skill_id": skill_id, "count": len(rows), "rows": rows}
