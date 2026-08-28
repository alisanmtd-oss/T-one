from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from .storage import append_record, read_records, write_report
from .types import IntakeRecord


CONTENT_RECORD_TYPES = [
    "viral_content_signal",
    "creator_spike_event",
    "video_breakdown",
    "video_script",
    "influencer_cooperation",
]


def build_tk_content_strategy(root: Path, product: str = "", store: str = "", run_date: str | None = None) -> dict[str, Any]:
    run_date = run_date or date.today().isoformat()
    records = filter_content_records(load_content_records(root), product=product, store=store)
    competitor = [record for record in records if content_owner(record) == "competitor"]
    owned = [record for record in records if content_owner(record) == "owned"]
    influencer = [record for record in records if content_owner(record) == "influencer"]
    unknown = [record for record in records if content_owner(record) == "unknown"]

    groups = {
        "competitor": analyze_group("同行视频", competitor),
        "owned": analyze_group("店铺自有打品视频", owned),
        "influencer": analyze_group("达人视频", influencer),
        "unknown": analyze_group("待归档视频", unknown),
    }
    decision = decide_content_stage(groups, records)
    scripts = build_script_recommendations(groups, decision, product)
    action_plan = build_action_plan(decision, groups)
    content = render_strategy_report(run_date, product, store, groups, decision, scripts, action_plan)
    report_path = write_report(root, f"tk_content_strategy_{run_date}", content)
    memory_record = persist_strategy_memory(root, run_date, product, store, groups, decision, action_plan)
    return {
        "run_date": run_date,
        "filters": {"product": product, "store": store},
        "summary": {
            "records": len(records),
            "competitor": len(competitor),
            "owned": len(owned),
            "influencer": len(influencer),
            "unknown": len(unknown),
        },
        "groups": groups,
        "decision": decision,
        "scripts": scripts,
        "action_plan": action_plan,
        "report_path": str(report_path),
        "memory_record": memory_record.to_dict(),
    }


def load_content_records(root: Path) -> list[IntakeRecord]:
    records: list[IntakeRecord] = []
    for record_type in CONTENT_RECORD_TYPES:
        records.extend(read_records(root, record_type))
    return sorted(records, key=lambda record: record.created_at, reverse=True)


def filter_content_records(records: list[IntakeRecord], product: str = "", store: str = "") -> list[IntakeRecord]:
    product_key = product.strip().lower()
    store_key = store.strip().lower()
    filtered = []
    for record in records:
        haystack = " ".join(str(value) for value in record.fields.values()).lower()
        if product_key and product_key not in haystack:
            continue
        if store_key and store_key not in haystack:
            continue
        filtered.append(record)
    return filtered


def content_owner(record: IntakeRecord) -> str:
    fields = record.fields
    raw = " ".join(
        str(fields.get(key) or "")
        for key in ["content_owner", "owner_type", "video_source", "source_type", "script_type", "relationship"]
    ).lower()
    if any(word in raw for word in ["competitor", "同行", "竞品"]):
        return "competitor"
    if any(word in raw for word in ["owned", "store", "brand", "self", "自有", "自播", "店铺", "品牌"]):
        return "owned"
    if any(word in raw for word in ["influencer", "creator", "达人", "affiliate"]):
        return "influencer"
    if record.record_type in {"creator_spike_event", "influencer_cooperation"}:
        return "influencer"
    if record.record_type == "video_script" and record.score.get("script_channel") == "store_owned":
        return "owned"
    return "unknown"


def analyze_group(label: str, records: list[IntakeRecord]) -> dict[str, Any]:
    top_records = sorted(records, key=record_priority, reverse=True)[:8]
    total_views = sum(number(record.fields.get("current_views") or record.fields.get("latest_video_views") or record.fields.get("views")) for record in records)
    avg_priority = sum(record_priority(record) for record in records) / len(records) if records else 0
    hooks = top_unique(fields_value(record, ["hook_text", "hook"]) for record in top_records)
    scenes = top_unique(fields_value(record, ["scene", "shooting_scene", "setting"]) for record in top_records)
    emotions = top_unique(fields_value(record, ["emotion", "emotional_value", "viral_reason"]) for record in top_records)
    purchase_signals = sum(1 for record in records if fields_value(record, ["purchase_intent_comments", "comment_insights", "buying_motivation"]))
    ready_scripts = sum(1 for record in records if record.record_type == "video_script" and bool(record.score.get("production_ready")))
    return {
        "label": label,
        "count": len(records),
        "total_views": int(total_views),
        "avg_priority": round(avg_priority, 2),
        "purchase_signal_count": purchase_signals,
        "production_ready_scripts": ready_scripts,
        "top_hooks": hooks,
        "top_scenes": scenes,
        "top_emotions": emotions,
        "top_records": [compact_content_record(record) for record in top_records],
    }


def decide_content_stage(groups: dict[str, dict[str, Any]], records: list[IntakeRecord]) -> dict[str, Any]:
    competitor_score = strategy_score(groups["competitor"])
    owned_score = strategy_score(groups["owned"])
    influencer_score = strategy_score(groups["influencer"])
    total_purchase = sum(group["purchase_signal_count"] for group in groups.values())
    has_script = groups["owned"]["production_ready_scripts"] + groups["influencer"]["production_ready_scripts"] > 0

    if not records:
        stage = "collect"
        recommendation = "先补同品类 TK 商品视频、达人视频、商品卡和评论区证据；没有证据不要判断打法。"
    elif competitor_score >= 75 and owned_score < 55:
        stage = "seed"
        recommendation = "同行已经有强信号，但我们自己的素材储备不足，先做种草和小样复刻测试。"
    elif owned_score >= 60 and influencer_score >= 60 and total_purchase >= 2:
        stage = "harvest"
        recommendation = "自有素材和达人都有信号，可以进入收割：商品卡、优惠、达人复投和广告放大。"
    elif influencer_score >= 70 and not has_script:
        stage = "creator_seed"
        recommendation = "达人侧有明显信号，先补达人 brief 和寄样脚本，再决定是否放大。"
    elif owned_score >= 65 and total_purchase == 0:
        stage = "optimize"
        recommendation = "素材表现还可以，但购买意图不足，优先优化 CTA、商品卡承接、评论引导和标题卖点。"
    else:
        stage = "test"
        recommendation = "进入小批量 A/B 测试，同时收集评论购买意图和订单转化。"

    return {
        "stage": stage,
        "recommendation": recommendation,
        "competitor_score": competitor_score,
        "owned_score": owned_score,
        "influencer_score": influencer_score,
        "purchase_signal_count": total_purchase,
        "harvest_ready": stage == "harvest",
    }


def build_script_recommendations(groups: dict[str, dict[str, Any]], decision: dict[str, Any], product: str) -> list[dict[str, str]]:
    theme = product or "目标商品"
    hooks = first_nonempty(groups["competitor"]["top_hooks"], groups["owned"]["top_hooks"], ["先用一个真实痛点开头"])
    scenes = first_nonempty(groups["competitor"]["top_scenes"], groups["owned"]["top_scenes"], ["真实使用场景", "产品细节近景"])
    emotions = first_nonempty(groups["competitor"]["top_emotions"], groups["influencer"]["top_emotions"], ["解决一个具体问题"])
    return [
        {
            "type": "store_owned_seed",
            "title": "店铺自有种草脚本",
            "hook": hooks[0],
            "structure": f"0-2秒钩子 -> 2-6秒{scenes[0]} -> 6-12秒产品证明 -> 12-18秒细节/利益点 -> 评论或商品卡 CTA。",
            "goal": "先拉高完播、评论和收藏，不要一上来硬卖。"
        },
        {
            "type": "influencer_seed",
            "title": "达人自然种草 brief",
            "hook": f"从个人故事或人群痛点开头：{emotions[0]}",
            "structure": f"达人先讲自己的场景，再展示 {theme} 的真实使用，再给软性商品卡 CTA。",
            "goal": "验证达人类型和人群共鸣，重点看评论区是否出现购买意图。"
        },
        {
            "type": "harvest",
            "title": "收割脚本",
            "hook": "等这个品的人，今天可以试这一版。",
            "structure": "0-2秒限时/强证明 -> 2-7秒最强效果镜头 -> 7-12秒优惠/组合 -> 12-18秒评论证明 -> 商品卡 CTA。",
            "goal": "配合折扣、达人复投、广告放大和商品卡承接。"
        },
    ]


def build_action_plan(decision: dict[str, Any], groups: dict[str, dict[str, Any]]) -> list[str]:
    stage = decision["stage"]
    actions = {
        "collect": [
            "采集 20 条同品同行视频、10 条达人视频、评论区购买意图和商品卡链接。",
            "每条视频标记为同行 / 自有 / 达人，并补充播放、增长、Hook、场景、评论。"
        ],
        "seed": [
            "用同行最高频 Hook 和场景做 3 条店铺自有种草视频。",
            "找 5 个同人群达人做自然种草，不急着强转化。",
            "观察 24-72 小时播放增长、评论购买意图、收藏和商品卡点击。"
        ],
        "creator_seed": [
            "把爆发达人拆成画像：粉丝质量、均播、最新爆发、评论区购买意图。",
            "生成达人 brief，先小批量寄样或低预算合作。"
        ],
        "test": [
            "做 3 组 A/B：Hook、场景、CTA 各换一版。",
            "低预算跑达人/店铺自有素材测试，记录每条视频的转化和评论。"
        ],
        "optimize": [
            "补强商品卡、标题、主图和详情页承接，避免视频好看但不成交。",
            "把评论区问题改成下一条视频的前 2 秒 Hook。"
        ],
        "harvest": [
            "对 A 级达人复投，并把同款脚本复制到 3-5 个相近达人类型。",
            "配合折扣、优惠券、限时活动和商品卡 CTA 做收割。",
            "把 ROAS、退款、差评同步到脚本复盘，避免只追 GMV。"
        ],
    }
    return actions.get(stage, actions["test"])


def render_strategy_report(
    run_date: str,
    product: str,
    store: str,
    groups: dict[str, dict[str, Any]],
    decision: dict[str, Any],
    scripts: list[dict[str, str]],
    action_plan: list[str],
) -> str:
    lines = [
        "# TK Content Strategy Report",
        "",
        f"- Date: {run_date}",
        f"- Product filter: {product or 'all'}",
        f"- Store filter: {store or 'all'}",
        f"- Stage: {decision['stage']}",
        f"- Recommendation: {decision['recommendation']}",
        "",
        "## Signals",
    ]
    for key in ["competitor", "owned", "influencer", "unknown"]:
        group = groups[key]
        lines.extend(
            [
                f"### {group['label']}",
                f"- Records: {group['count']}",
                f"- Total views: {group['total_views']}",
                f"- Avg priority: {group['avg_priority']}",
                f"- Purchase signals: {group['purchase_signal_count']}",
                f"- Hooks: {', '.join(group['top_hooks']) or '-'}",
                f"- Scenes: {', '.join(group['top_scenes']) or '-'}",
                "",
            ]
        )
    lines.extend(["## Scripts"])
    for script in scripts:
        lines.extend([f"### {script['title']}", f"- Hook: {script['hook']}", f"- Structure: {script['structure']}", f"- Goal: {script['goal']}", ""])
    lines.extend(["## Action Plan", *[f"- {item}" for item in action_plan], ""])
    return "\n".join(lines)


def persist_strategy_memory(
    root: Path,
    run_date: str,
    product: str,
    store: str,
    groups: dict[str, dict[str, Any]],
    decision: dict[str, Any],
    action_plan: list[str],
) -> IntakeRecord:
    product_key = product.strip().lower() or "all-products"
    store_key = store.strip().lower() or "all-stores"
    stage = str(decision.get("stage") or "unknown")
    fields = {
        "memory_key": f"tk-content:{run_date}:{product_key}:{store_key}",
        "memory_type": "tk_content_strategy",
        "product_name": product,
        "store_id": store,
        "strategy_stage": stage,
        "recommendation": decision.get("recommendation"),
        "competitor_score": decision.get("competitor_score"),
        "owned_score": decision.get("owned_score"),
        "influencer_score": decision.get("influencer_score"),
        "harvest_ready": decision.get("harvest_ready"),
        "rule_summary": strategy_rule_summary(stage),
        "action_plan": action_plan,
        "what_to_do": action_plan,
        "what_not_to_do": guardrails_for_stage(stage),
        "valid_when": valid_when_for_stage(stage),
    }
    record = IntakeRecord(
        record_type="strategy_memory",
        fields=fields,
        raw_text=f"TK content strategy memory for {product or 'all products'} / {store or 'all stores'} on {run_date}",
        source="tk_content_strategy",
        score={"priority": 80 if decision.get("harvest_ready") else 65, "training_weight": "high"},
        director_notes=[str(decision.get("recommendation") or "")],
    )
    append_record(root, record)
    return record


def strategy_rule_summary(stage: str) -> str:
    return {
        "collect": "证据不足时，不直接判断打法；先补同行、达人、自有视频和评论区。",
        "seed": "同行有强信号但自有素材弱时，先种草和小样复刻，不急着收割。",
        "creator_seed": "达人侧爆发时，先做达人 brief 和小批量寄样，再放大。",
        "test": "信号混杂时，小预算 A/B 测试，记录评论和转化。",
        "optimize": "有播放但购买意图弱时，优化 CTA、商品卡、Listing 和评论引导。",
        "harvest": "自有素材、达人素材和购买意图都出现时，再组合商品卡、优惠、复投和广告放大。",
    }.get(stage, "证据没有确认前，策略保持保守。")


def guardrails_for_stage(stage: str) -> list[str]:
    base = [
        "未经确认不发布、不下架、不改价、不联系达人、不报名活动、不改店铺设置。",
        "不复制竞品品牌、商标、版权角色、明星肖像或原始素材。",
    ]
    if stage != "harvest":
        base.append("没有购买意图或转化证据前，不做强收割。")
    return base


def valid_when_for_stage(stage: str) -> list[str]:
    return {
        "seed": ["同行内容有强播放或增长。", "自有脚本或达人池还弱。"],
        "creator_seed": ["达人新视频明显高于均播。", "评论区出现人群共鸣或购买意图。"],
        "test": ["已有信号但不足以放大。", "预算和样品要保持小规模。"],
        "optimize": ["有播放但转化或购买评论弱。", "商品卡、Listing 或 CTA 可能是瓶颈。"],
        "harvest": ["自有内容有信号。", "达人内容有信号。", "评论或转化证据出现。"],
    }.get(stage, ["数据不足，先补证据。"])


def compact_content_record(record: IntakeRecord) -> dict[str, Any]:
    fields = record.fields
    return {
        "record_id": record.record_id,
        "record_type": record.record_type,
        "name": fields_value(record, ["product_name", "video_title", "title", "creator_handle", "influencer_handle", "url"]) or record.record_id[:8],
        "url": fields_value(record, ["video_url", "url", "profile_url"]),
        "owner": content_owner(record),
        "priority": record_priority(record),
        "views": int(number(fields.get("current_views") or fields.get("latest_video_views") or fields.get("views"))),
        "hook": fields_value(record, ["hook_text", "hook"]),
        "scene": fields_value(record, ["scene", "shooting_scene", "setting"]),
    }


def strategy_score(group: dict[str, Any]) -> float:
    score = 0.0
    score += min(float(group["count"]) * 10, 20)
    score += min(float(group["total_views"]) / 50_000 * 10, 30)
    score += min(float(group["avg_priority"]) / 100 * 35, 35)
    score += min(float(group["purchase_signal_count"]) * 10, 10)
    score += min(float(group["production_ready_scripts"]) * 20, 20)
    return round(score, 2)


def record_priority(record: IntakeRecord) -> float:
    try:
        return float(record.score.get("priority") or 0)
    except (TypeError, ValueError):
        return 0.0


def fields_value(record: IntakeRecord, keys: list[str]) -> str:
    for key in keys:
        value = record.fields.get(key)
        if value is not None and value != "":
            return str(value).strip()
    return ""


def top_unique(values: Any) -> list[str]:
    output = []
    for value in values:
        clean = str(value or "").strip()
        if clean and clean not in output:
            output.append(clean)
        if len(output) >= 5:
            break
    return output


def first_nonempty(*groups: list[str]) -> list[str]:
    for group in groups:
        if group:
            return group
    return []


def number(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return 0.0
    clean = str(value).strip().lower()
    multiplier = 1.0
    if clean.endswith("k"):
        multiplier = 1_000.0
        clean = clean[:-1]
    elif clean.endswith("m"):
        multiplier = 1_000_000.0
        clean = clean[:-1]
    clean = "".join(ch for ch in clean if ch.isdigit() or ch in ".-")
    try:
        return float(clean) * multiplier if clean else 0.0
    except ValueError:
        return 0.0
