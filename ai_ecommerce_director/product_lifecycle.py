from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .product_targets import load_product_targets
from .selection_intelligence import detect_new_release_candidates, detect_ranking_movements, parse_rank
from .storage import read_records
from .store_metrics import extract_metric_values
from .types import IntakeRecord


REPORT_PREFIX = "product_lifecycle"


@dataclass(slots=True)
class ProductLifecycleResult:
    run_date: str
    plans: list[dict[str, Any]]
    report: str
    report_path: Path
    json_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "plans": self.plans,
            "report": self.report,
            "report_path": str(self.report_path),
            "json_path": str(self.json_path),
        }


def run_product_lifecycle_analysis(root: Path, run_date: str | None = None) -> ProductLifecycleResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    plans = build_product_lifecycle_plans(root, report_date)
    report = build_lifecycle_report(report_date, plans)
    report_path = write_lifecycle_report(root, report_date, report)
    json_path = write_lifecycle_json(root, report_date, plans)
    return ProductLifecycleResult(report_date, plans, report, report_path, json_path)


def build_product_lifecycle_plans(root: Path, run_date: str | None = None, records: list[IntakeRecord] | None = None) -> list[dict[str, Any]]:
    records = records if records is not None else read_records(root)
    ranking_records = [record for record in records if record.record_type == "platform_ranking_signal"]
    movements = detect_ranking_movements(ranking_records)
    new_release_ids = {str(item.get("record_id") or "") for item in detect_new_release_candidates(ranking_records)}
    movement_by_id = {str(item.get("latest_record_id") or ""): item for item in movements if item.get("latest_record_id")}
    groups = build_product_groups(root, records)
    plans = [
        build_lifecycle_plan(key, items, movement_by_id, new_release_ids, run_date)
        for key, items in groups.items()
    ]
    plans = [plan for plan in plans if plan["signal_count"] > 0 or plan["source"] == "product_target"]
    return sorted(
        plans,
        key=lambda item: (
            0 if item.get("source") == "product_target" else 1,
            stage_sort_key(str(item.get("lifecycle_stage"))),
            -float(item.get("opportunity_score") or 0),
            str(item.get("product_name") or ""),
        ),
    )[:120]


def build_product_groups(root: Path, records: list[IntakeRecord]) -> dict[str, list[IntakeRecord | dict[str, Any]]]:
    groups: dict[str, list[IntakeRecord | dict[str, Any]]] = {}
    for target in load_product_targets(root).get("targets", []):
        if not isinstance(target, dict):
            continue
        key = normalized_key(target.get("id") or target.get("name") or target.get("product_family"))
        if not key:
            continue
        groups.setdefault(key, []).append({"record_type": "product_target", "fields": target})
    for record in records:
        key = product_key(record)
        if key:
            groups.setdefault(key, []).append(record)
    return groups


def product_key(record: IntakeRecord) -> str:
    fields = record.fields
    for key in ["product_target_id", "target_id"]:
        value = normalized_key(fields.get(key))
        if value:
            return value
    for key in ["product_target_name", "product_name", "product_theme", "product_family", "sku", "asin", "seller_sku"]:
        value = normalized_key(fields.get(key))
        if value:
            return value
    return ""


def build_lifecycle_plan(
    group_key: str,
    items: list[IntakeRecord | dict[str, Any]],
    movement_by_id: dict[str, dict[str, Any]],
    new_release_ids: set[str],
    run_date: str | None,
) -> dict[str, Any]:
    records = [item for item in items if isinstance(item, IntakeRecord)]
    target_items = [item for item in items if isinstance(item, dict)]
    product_name = choose_product_name(group_key, records, target_items)
    ranking_records = [record for record in records if record.record_type == "platform_ranking_signal"]
    own_metric_records = [record for record in records if record.record_type == "store_metric_snapshot"]
    content_records = [record for record in records if record.record_type in {"viral_content_signal", "creator_spike_event", "video_breakdown", "hot_link"}]
    review_records = [record for record in records if record.record_type == "review_insight"]
    supply_records = [record for record in records if record.record_type == "supply_chain"]

    best_rank = best_rank_position(ranking_records)
    rank_direction, rank_delta = rank_movement_summary(ranking_records, movement_by_id)
    competitor_demand = competitor_demand_score(ranking_records)
    content_spike = content_growth_score(content_records)
    recent_units, previous_units, recent_revenue = own_sales_windows(own_metric_records, run_date)
    return_rate = aggregate_return_rate(own_metric_records)
    inventory_qty = current_inventory(supply_records)
    lead_time_days = estimate_lead_time_days(supply_records)
    review_risks = review_risk_signals(review_records)
    is_new_release = any(record.record_id in new_release_ids or is_new_release_record(record) for record in ranking_records)

    own_growth = recent_units - previous_units
    growth_score = 0
    if rank_direction == "up":
        growth_score += min(30, max(5, rank_delta))
    if content_spike > 0:
        growth_score += content_spike
    if own_growth > 0:
        growth_score += min(25, own_growth * 2)
    if is_new_release:
        growth_score += 12

    demand_score = competitor_demand + min(25, recent_units * 2)
    if best_rank and best_rank <= 20:
        demand_score += 18
    elif best_rank and best_rank <= 80:
        demand_score += 8
    risk_score = review_risks["risk_score"]
    if return_rate >= 0.08:
        risk_score += 16
    if rank_direction == "down":
        risk_score += min(20, abs(rank_delta))

    stage = classify_lifecycle_stage(
        signal_count=len(records),
        recent_units=recent_units,
        previous_units=previous_units,
        growth_score=growth_score,
        demand_score=demand_score,
        risk_score=risk_score,
        is_new_release=is_new_release,
        rank_direction=rank_direction,
    )
    confidence = lifecycle_confidence(len(records), ranking_records, own_metric_records, content_records, review_records)
    opportunity_score = max(0, min(100, int(demand_score + growth_score * 0.8 - risk_score * 0.7)))
    stock_plan = build_stock_plan(stage, recent_units, previous_units, inventory_qty, lead_time_days, return_rate)
    extension_plan = lifecycle_extension_plan(stage, product_name, review_risks["pain_points"])
    next_actions = lifecycle_next_actions(stage, stock_plan, review_risks["pain_points"])

    return {
        "product_key": group_key,
        "product_name": product_name,
        "source": "product_target" if target_items else "records",
        "lifecycle_stage": stage,
        "stage_label": stage_label(stage),
        "confidence": confidence,
        "opportunity_score": opportunity_score,
        "signal_count": len(records),
        "best_rank": best_rank,
        "rank_direction": rank_direction,
        "rank_delta": rank_delta,
        "is_new_release": is_new_release,
        "recent_units_7d": recent_units,
        "previous_units_7d": previous_units,
        "recent_revenue_7d": round(recent_revenue, 2),
        "return_rate": round(return_rate, 4),
        "inventory_qty": inventory_qty,
        "lead_time_days": lead_time_days,
        "growth_score": int(growth_score),
        "demand_score": int(demand_score),
        "risk_score": int(risk_score),
        "stock_plan": stock_plan,
        "lifecycle_extension_plan": extension_plan,
        "next_actions": next_actions,
        "risks": review_risks["risks"],
        "pain_points": review_risks["pain_points"],
        "review_trigger": review_trigger(stage),
    }


def classify_lifecycle_stage(
    signal_count: int,
    recent_units: int,
    previous_units: int,
    growth_score: float,
    demand_score: float,
    risk_score: float,
    is_new_release: bool,
    rank_direction: str,
) -> str:
    if risk_score >= 45 or (rank_direction == "down" and recent_units <= max(1, previous_units // 2)):
        return "D"
    if growth_score >= 32 and demand_score >= 25 and risk_score < 35:
        return "B"
    if recent_units >= 20 and demand_score >= 35 and abs(recent_units - previous_units) <= max(5, recent_units * 0.25):
        return "C"
    if is_new_release or signal_count <= 3 or recent_units < 10:
        return "A"
    if demand_score >= 45 and risk_score < 35:
        return "C"
    return "A"


def build_stock_plan(stage: str, recent_units: int, previous_units: int, inventory_qty: int | None, lead_time_days: int, return_rate: float) -> dict[str, Any]:
    daily_units = max(0.2, recent_units / 7) if recent_units else 0.2
    growth_multiplier = 1.0
    if recent_units > previous_units and previous_units > 0:
        growth_multiplier = min(2.0, recent_units / previous_units)
    if stage == "A":
        test_qty = 30 if recent_units == 0 else max(30, min(150, int(recent_units * 2.5)))
        target_days = 7
        safety_factor = 1.1
    elif stage == "B":
        test_qty = max(120, int(daily_units * 14 * growth_multiplier))
        target_days = 21
        safety_factor = 1.45
    elif stage == "C":
        test_qty = max(80, int(daily_units * 14))
        target_days = 18
        safety_factor = 1.25
    else:
        test_qty = 0 if recent_units == 0 else min(30, int(daily_units * 5))
        target_days = 5
        safety_factor = 0.6
    if return_rate >= 0.08:
        safety_factor *= 0.75
    recommended_stock = int(math.ceil(daily_units * max(lead_time_days, target_days) * safety_factor))
    if stage == "A":
        recommended_stock = max(recommended_stock, test_qty)
    if inventory_qty is None:
        replenish_qty = recommended_stock
    else:
        replenish_qty = max(0, recommended_stock - inventory_qty)
    return {
        "mode": stock_mode(stage),
        "test_stock_qty": test_qty,
        "recommended_available_stock": recommended_stock,
        "replenishment_qty": replenish_qty,
        "safety_stock_days": target_days,
        "lead_time_days": lead_time_days,
        "daily_unit_estimate": round(daily_units, 2),
        "notes": stock_notes(stage),
    }


def lifecycle_extension_plan(stage: str, product_name: str, pain_points: list[str]) -> list[str]:
    base = {
        "A": [
            "先用小批量测 3-5 个素材方向，不急着大货。",
            "同品至少拆 5 个同行视频脚本：钩子、场景、运镜、评论购买理由。",
            "先验证主图、标题、价格和达人类型，转化稳定后再补货。",
        ],
        "B": [
            "进入放量期：增加达人矩阵、短视频频次和安全库存，不要让爆点断货。",
            "快速复制 3 个变体：颜色/套装/人群标签/场景版本，避免单一素材疲劳。",
            "每天看转化、退款、评论和素材衰减，增长断点出现时立即换脚本。",
        ],
        "C": [
            "成熟期重点拉长生命周期：做套装、升级款、礼品版、季节版和人群细分版。",
            "用差评反推二代改良，把缺点写进详情页和视频解释，降低退货。",
            "减少粗暴加预算，改成稳定复投、达人复购和关键词防守。",
        ],
        "D": [
            "衰退或风险期：停止大额补货，清库存，保留低成本测试。",
            "复盘下滑原因：素材疲劳、价格战、差评、季节结束、侵权/平台风险。",
            "只保留能改良的卖点，转成新包装、新人群或替代品重新测。",
        ],
    }[stage]
    if pain_points:
        base.append(f"优先修复差评/投诉痛点：{'; '.join(pain_points[:3])}。")
    return [item.replace("同品", product_name or "同品") for item in base]


def lifecycle_next_actions(stage: str, stock_plan: dict[str, Any], pain_points: list[str]) -> list[str]:
    if stage == "A":
        return [
            f"创建测品备货草稿：{stock_plan['test_stock_qty']} 件以内。",
            "生成 3 条自有号脚本 + 3 条达人脚本，先测内容转化。",
            "继续采集同款竞品链接、评论和视频，补齐生命周期判断证据。",
        ]
    if stage == "B":
        return [
            f"创建补货建议：补 {stock_plan['replenishment_qty']} 件，保持 {stock_plan['safety_stock_days']} 天安全库存。",
            "把高转化视频拆成达人 brief，做多达人并行种草。",
            "同步准备 Listing/主图/折扣草稿，但真实上架和改价进入确认中心。",
        ]
    if stage == "C":
        return [
            "创建二代/变体开发任务，优先做颜色、套装、礼品和场景版本。",
            "用评论痛点更新详情页 FAQ 和视频解释脚本。",
            f"维持安全库存，建议可用库存 {stock_plan['recommended_available_stock']} 件左右。",
        ]
    return [
        "停止大额补货，只做清库存或小样验证。",
        "生成衰退复盘：素材、价格、差评、季节、侵权、竞品压价。",
        "若痛点可修复，转成新版测品；不可修复则进入淘汰池。",
    ]


def review_trigger(stage: str) -> str:
    return {
        "A": "3 天后或累计 10 单/3 条视频后复盘。",
        "B": "每天复盘；库存低于 7 天或素材播放跌破均值 50% 立即预警。",
        "C": "每 7 天复盘；评分、退货率、排名明显恶化时提前复盘。",
        "D": "清库存结束或出现新素材/新版样品后再复盘。",
    }[stage]


def build_lifecycle_report(run_date: str, plans: list[dict[str, Any]]) -> str:
    lines = [
        f"# Product Lifecycle & Stock Plan - {run_date}",
        "",
        "## ABCD定义",
        "- A：新品/测品期。小批量验证内容、Listing、价格和达人，不急着大货。",
        "- B：增长放量期。补安全库存，扩大达人/视频/广告测试，避免断货。",
        "- C：成熟收割期。稳定复投，做变体、套装、二代和差评修复来拉长生命周期。",
        "- D：衰退/风险期。停止大额补货，清库存或改良后重测。",
        "",
        "## 今日结论",
    ]
    if not plans:
        lines.append("- 后台 AI 暂未读到足够的商品、同行、销量和评论数据；证据缺口已记录，等平台榜单、竞品链接、视频和店铺销量可读后会自动更新判断。")
        return "\n".join(lines)
    for stage in ["B", "A", "C", "D"]:
        stage_plans = [item for item in plans if item.get("lifecycle_stage") == stage]
        if stage_plans:
            lines.append(f"- {stage_label(stage)}：{len(stage_plans)} 个")
    lines.extend(["", "## 重点商品"])
    for plan in plans[:30]:
        stock = plan["stock_plan"]
        lines.append(
            f"- {plan['product_name']}｜{plan['stage_label']}｜机会分 {plan['opportunity_score']}｜"
            f"近7天 {plan['recent_units_7d']} 件｜建议补货 {stock['replenishment_qty']} 件｜"
            f"{plan['review_trigger']}"
        )
    return "\n".join(lines)


def write_lifecycle_report(root: Path, run_date: str, content: str) -> Path:
    path = root / "outputs" / f"{REPORT_PREFIX}_{run_date}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_lifecycle_json(root: Path, run_date: str, plans: list[dict[str, Any]]) -> Path:
    path = root / "outputs" / f"{REPORT_PREFIX}_{run_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"run_date": run_date, "plans": plans}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def latest_lifecycle_report(root: Path) -> tuple[str, Path | None]:
    output_dir = root / "outputs"
    if not output_dir.exists():
        return "No product lifecycle report yet.", None
    paths = sorted(output_dir.glob(f"{REPORT_PREFIX}_*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not paths:
        return "No product lifecycle report yet.", None
    return paths[0].read_text(encoding="utf-8"), paths[0]


def choose_product_name(group_key: str, records: list[IntakeRecord], target_items: list[dict[str, Any]]) -> str:
    for item in target_items:
        fields = item.get("fields", {})
        for key in ["name", "product_family"]:
            value = str(fields.get(key) or "").strip()
            if value:
                return value
    for record in records:
        for key in ["product_target_name", "product_name", "product_theme", "product_family", "sku", "asin"]:
            value = str(record.fields.get(key) or "").strip()
            if value:
                return value
    return group_key


def best_rank_position(records: list[IntakeRecord]) -> int | None:
    ranks = [parse_rank(record.fields.get("rank_position")) for record in records]
    ranks = [rank for rank in ranks if rank is not None]
    return min(ranks) if ranks else None


def rank_movement_summary(records: list[IntakeRecord], movement_by_id: dict[str, dict[str, Any]]) -> tuple[str, int]:
    movements = [movement_by_id.get(record.record_id) for record in records if movement_by_id.get(record.record_id)]
    if movements:
        strongest = sorted(movements, key=lambda item: abs(int(item.get("rank_improvement") or 0)), reverse=True)[0]
        delta = int(strongest.get("rank_improvement") or 0)
        return ("up" if delta > 0 else "down"), abs(delta)
    if len(records) >= 2:
        sorted_records = sorted(records, key=lambda item: item.created_at)
        older = parse_rank(sorted_records[-2].fields.get("rank_position"))
        newer = parse_rank(sorted_records[-1].fields.get("rank_position"))
        if older is not None and newer is not None and older != newer:
            return ("up" if older > newer else "down"), abs(older - newer)
    return "flat", 0


def competitor_demand_score(records: list[IntakeRecord]) -> int:
    score = 0
    for record in records[-12:]:
        fields = record.fields
        rank = parse_rank(fields.get("rank_position"))
        if rank:
            score += max(0, 18 - min(rank, 100) // 8)
        sales = number(fields.get("sales_count") or fields.get("unit_count") or fields.get("units_sold"))
        gmv = number(fields.get("gmv") or fields.get("total_revenue") or fields.get("sales_amount"))
        if sales:
            score += min(18, int(sales / 100))
        if gmv:
            score += min(18, int(gmv / 1000))
        priority = number(record.score.get("priority"))
        if priority and priority >= 85:
            score += 5
    return min(score, 60)


def content_growth_score(records: list[IntakeRecord]) -> int:
    score = 0
    for record in records[-10:]:
        fields = record.fields
        current_views = number(fields.get("current_views") or fields.get("views"))
        previous_views = number(fields.get("previous_views"))
        if current_views and previous_views and current_views > previous_views:
            score += min(22, int((current_views - previous_views) / max(previous_views, 1) * 6))
        elif current_views and current_views >= 100_000:
            score += 12
    return min(score, 35)


def own_sales_windows(records: list[IntakeRecord], run_date: str | None) -> tuple[int, int, float]:
    anchor = parse_date(run_date) or date.today()
    recent_start = anchor - timedelta(days=6)
    previous_start = anchor - timedelta(days=13)
    recent_units = 0
    previous_units = 0
    recent_revenue = 0.0
    for record in records:
        metric_date = record_date(record)
        values = extract_metric_values(record.fields)
        if recent_start <= metric_date <= anchor:
            recent_units += int(values.get("units") or values.get("orders") or 0)
            recent_revenue += float(values.get("revenue") or 0)
        elif previous_start <= metric_date < recent_start:
            previous_units += int(values.get("units") or values.get("orders") or 0)
    return recent_units, previous_units, recent_revenue


def aggregate_return_rate(records: list[IntakeRecord]) -> float:
    orders = 0.0
    returns = 0.0
    for record in records[-20:]:
        values = extract_metric_values(record.fields)
        orders += float(values.get("orders") or 0)
        returns += float(values.get("return_count") or values.get("refund_count") or 0)
    return returns / orders if orders > 0 else 0.0


def current_inventory(records: list[IntakeRecord]) -> int | None:
    values = [number(record.fields.get("inventory_qty") or record.fields.get("stock_qty") or record.fields.get("stock")) for record in records]
    values = [int(value) for value in values if value is not None]
    return max(values) if values else None


def estimate_lead_time_days(records: list[IntakeRecord]) -> int:
    for record in records:
        production = number(record.fields.get("production_days")) or 0
        shipping = number(record.fields.get("shipping_days")) or 0
        if production or shipping:
            return max(3, int(production + shipping))
    return 14


def review_risk_signals(records: list[IntakeRecord]) -> dict[str, Any]:
    risks: list[str] = []
    pain_points: list[str] = []
    score = 0
    for record in records[-15:]:
        fields = record.fields
        text = json.dumps(fields, ensure_ascii=False).lower()
        if any(word in text for word in ["negative", "bad", "1-star", "poor", "refund", "return", "complaint", "差评", "退款", "退货", "投诉"]):
            score += 8
        pain = str(fields.get("pain_point") or fields.get("defect_area") or fields.get("refund_reason") or "").strip()
        if pain:
            pain_points.append(pain[:120])
        if fields.get("suggested_fix"):
            risks.append(f"已有修复建议：{fields.get('suggested_fix')}")
    if len(pain_points) >= 3:
        score += 10
    if pain_points:
        risks.append("评论/投诉痛点：" + "；".join(pain_points[:3]))
    return {"risk_score": min(score, 60), "risks": risks[:6], "pain_points": list(dict.fromkeys(pain_points))[:6]}


def lifecycle_confidence(
    signal_count: int,
    ranking_records: list[IntakeRecord],
    own_metric_records: list[IntakeRecord],
    content_records: list[IntakeRecord],
    review_records: list[IntakeRecord],
) -> str:
    evidence = 0
    if ranking_records:
        evidence += 1
    if own_metric_records:
        evidence += 1
    if content_records:
        evidence += 1
    if review_records:
        evidence += 1
    if signal_count >= 8 and evidence >= 3:
        return "high"
    if signal_count >= 4 and evidence >= 2:
        return "medium"
    return "low"


def is_new_release_record(record: IntakeRecord) -> bool:
    text = " ".join(str(record.fields.get(key) or "") for key in ["ranking_type", "data_category", "ranking_page"]).lower()
    return any(term in text for term in ["new release", "new releases", "new in", "new arrivals", "新品"])


def stock_mode(stage: str) -> str:
    return {"A": "test_stock", "B": "scale_replenishment", "C": "steady_replenishment", "D": "clearance_or_pause"}[stage]


def stock_notes(stage: str) -> str:
    return {
        "A": "测品期只做小批量，避免内容没跑通就压库存。",
        "B": "增长期要防断货，备货按销量、交期和素材增长速度上调。",
        "C": "成熟期维持稳定库存，重点做变体和利润优化。",
        "D": "衰退期停止大货，只做清库存或改版重测。",
    }[stage]


def stage_label(stage: str) -> str:
    return {
        "A": "A 测品/验证期",
        "B": "B 增长/放量期",
        "C": "C 成熟/收割期",
        "D": "D 衰退/风险期",
    }.get(stage, stage)


def stage_sort_key(stage: str) -> int:
    return {"B": 0, "A": 1, "C": 2, "D": 3}.get(stage, 9)


def normalized_key(value: Any) -> str:
    return str(value or "").strip().lower()


def record_date(record: IntakeRecord) -> date:
    fields = record.fields
    raw = str(fields.get("snapshot_end") or fields.get("metric_date") or fields.get("snapshot_start") or record.created_at or "")
    return parse_date(raw) or date.today()


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).date()
    except ValueError:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        clean = value.strip().lower().replace(",", "").replace("$", "")
        multiplier = 1.0
        if clean.endswith("k"):
            multiplier = 1_000
            clean = clean[:-1]
        elif clean.endswith("m"):
            multiplier = 1_000_000
            clean = clean[:-1]
        if clean.endswith("%"):
            try:
                return float(clean[:-1]) / 100
            except ValueError:
                return None
        try:
            return float(clean) * multiplier
        except ValueError:
            return None
    return None
