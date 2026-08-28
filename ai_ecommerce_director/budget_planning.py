from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .launch_control import build_launch_control_plans
from .product_lifecycle import build_product_lifecycle_plans
from .product_targets import load_product_targets, normalize_list
from .storage import read_records
from .store_metrics import extract_metric_values, number
from .types import IntakeRecord


BUDGET_PLANS_CONFIG = Path("config") / "budget_plans.json"
REPORT_PREFIX = "budget_planning"


@dataclass(slots=True)
class BudgetPlanningResult:
    run_date: str
    plans: list[dict[str, Any]]
    summary: dict[str, Any]
    report: str
    report_path: Path
    json_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "plans": self.plans,
            "summary": self.summary,
            "report": self.report,
            "report_path": str(self.report_path),
            "json_path": str(self.json_path),
        }


def run_budget_planning_analysis(root: Path, run_date: str | None = None) -> BudgetPlanningResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    payload = build_budget_planning_payload(root, report_date)
    report = build_budget_planning_report(report_date, payload["plans"], payload["summary"])
    report_path = write_budget_report(root, report_date, report)
    json_path = write_budget_json(root, report_date, payload)
    return BudgetPlanningResult(report_date, payload["plans"], payload["summary"], report, report_path, json_path)


def build_budget_planning_payload(root: Path, run_date: str | None = None) -> dict[str, Any]:
    root = root.resolve()
    config = load_budget_plans(root)
    configured_scenarios = [item for item in config.get("plans", []) if isinstance(item, dict) and item.get("enabled", True)]
    all_records = read_records(root)
    records_by_type: dict[str, list[IntakeRecord]] = {}
    for record in all_records:
        records_by_type.setdefault(record.record_type, []).append(record)
    lifecycle_plans = build_product_lifecycle_plans(root, run_date, records=all_records)
    launch_plans = build_launch_control_plans(root, run_date, lifecycle_plans=lifecycle_plans, records=all_records)
    scenarios = merge_budget_scenarios(
        configured_scenarios,
        default_scenarios_from_products(root, lifecycle_plans, launch_plans),
    )
    plans = [
        build_budget_plan(root, scenario, lifecycle_plans, launch_plans, run_date, records_by_type)
        for scenario in scenarios
    ]
    plans = [plan for plan in plans if plan.get("product_name")]
    plans = sorted(plans, key=lambda item: (-int(item.get("priority_score") or 0), str(item.get("product_name") or "")))[:120]
    summary = build_budget_summary(plans)
    return {"config": config, "scenarios": scenarios, "plans": plans, "summary": summary}


def merge_budget_scenarios(configured: list[dict[str, Any]], generated: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in [*configured, *generated]:
        product = normalized_key(item.get("product_name") or item.get("product"))
        channels = "|".join(sorted(normalize_channels(item.get("channels"))))
        key = f"{product}:{channels}"
        if not product or key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def load_budget_plans(root: Path) -> dict[str, Any]:
    path = root / BUDGET_PLANS_CONFIG
    if not path.exists():
        return {"plans": []}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        return {"plans": []}
    payload.setdefault("plans", [])
    return payload


def save_budget_plans(root: Path, payload: dict[str, Any]) -> Path:
    path = root / BUDGET_PLANS_CONFIG
    path.parent.mkdir(parents=True, exist_ok=True)
    payload.setdefault("plans", [])
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def add_budget_plan(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    config = load_budget_plans(root)
    product_name = str(payload.get("product_name") or payload.get("product") or "").strip()
    if not product_name:
        raise ValueError("Product name is required.")
    total_budget = number(payload.get("total_budget")) or 0
    if total_budget <= 0:
        raise ValueError("Total budget must be greater than 0.")
    channels = normalize_channels(payload.get("channels"))
    if not channels:
        channels = ["TikTok Shop"]
    plan = {
        "id": uuid4().hex[:12],
        "enabled": True,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "plan_name": str(payload.get("plan_name") or payload.get("name") or f"{product_name} budget plan").strip(),
        "product_name": product_name,
        "product_key": normalized_key(payload.get("product_key") or product_name),
        "total_budget": round(float(total_budget), 2),
        "currency": str(payload.get("currency") or "USD").strip().upper(),
        "duration_days": int(number(payload.get("duration_days")) or 30),
        "store_count": max(1, int(number(payload.get("store_count")) or 1)),
        "channels": channels,
        "countries": normalize_list(payload.get("countries") or payload.get("country")) or ["US"],
        "target_margin": clamp_float(number(payload.get("target_margin")) or 0.45, 0.05, 0.9),
        "risk_appetite": str(payload.get("risk_appetite") or "balanced").strip(),
        "notes": str(payload.get("notes") or "").strip(),
    }
    config.setdefault("plans", []).append(plan)
    save_budget_plans(root, config)
    return plan


def default_scenarios_from_products(root: Path, lifecycle_plans: list[dict[str, Any]], launch_plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    targets = load_product_targets(root).get("targets", [])
    scenarios: list[dict[str, Any]] = []
    seen: set[str] = set()
    for lifecycle in lifecycle_plans[:30]:
        product = str(lifecycle.get("product_name") or "").strip()
        if not product:
            continue
        key = normalized_key(product)
        if key in seen:
            continue
        seen.add(key)
        launch = find_launch_plan(product, launch_plans)
        channels = channels_from_launch(launch) or channels_from_targets(product, targets) or ["TikTok Shop"]
        stage = str(lifecycle.get("lifecycle_stage") or "A")
        scenarios.append(
            {
                "id": f"auto-{key[:10]}",
                "enabled": True,
                "plan_name": f"Auto plan / {product}",
                "product_name": product,
                "product_key": key,
                "total_budget": default_budget_for_stage(stage),
                "currency": "USD",
                "duration_days": 30,
                "store_count": 1,
                "channels": channels,
                "countries": ["US"],
                "target_margin": 0.45,
                "risk_appetite": "conservative",
                "notes": "Auto-generated from monitored product signals. Add a custom scenario to override.",
            }
        )
    for target in targets:
        if not isinstance(target, dict):
            continue
        product = str(target.get("name") or target.get("product_family") or "").strip()
        key = normalized_key(product)
        if not product or key in seen:
            continue
        seen.add(key)
        scenarios.append(
            {
                "id": f"target-{key[:10]}",
                "enabled": True,
                "plan_name": f"Target plan / {product}",
                "product_name": product,
                "product_key": key,
                "total_budget": 3000.0,
                "currency": "USD",
                "duration_days": 30,
                "store_count": 1,
                "channels": normalize_channels(target.get("platforms")) or ["TikTok Shop"],
                "countries": [str(target.get("market") or "US")],
                "target_margin": 0.45,
                "risk_appetite": "conservative",
                "notes": "Auto-generated from product target.",
            }
        )
    return scenarios


def build_budget_plan(
    root: Path,
    scenario: dict[str, Any],
    lifecycle_plans: list[dict[str, Any]],
    launch_plans: list[dict[str, Any]],
    run_date: str | None,
    records_by_type: dict[str, list[IntakeRecord]] | None = None,
) -> dict[str, Any]:
    product = str(scenario.get("product_name") or scenario.get("product") or "").strip()
    total_budget = float(number(scenario.get("total_budget")) or 0)
    duration_days = max(7, int(number(scenario.get("duration_days")) or 30))
    store_count = max(1, int(number(scenario.get("store_count")) or 1))
    channels = normalize_channels(scenario.get("channels")) or ["TikTok Shop"]
    currency = str(scenario.get("currency") or "USD").strip().upper()
    records_by_type = records_by_type or {}
    margin = clamp_float(number(scenario.get("target_margin")) or estimate_margin(root, product, records_by_type.get("supply_chain")), 0.05, 0.9)
    lifecycle = find_lifecycle_plan(product, lifecycle_plans)
    launch = find_launch_plan(product, launch_plans)
    related_rankings = related_records(product, records_by_type.get("platform_ranking_signal") or [])
    related_metrics = related_records(product, records_by_type.get("store_metric_snapshot") or [])
    related_reviews = related_records(product, records_by_type.get("review_insight") or [])
    own = summarize_own_performance(related_metrics)
    market = summarize_market_size(related_rankings)
    competitors = summarize_competitor_intensity(related_rankings)
    stage = str(lifecycle.get("lifecycle_stage") or "A")
    launch_stage = str(launch.get("launch_stage") or "seed_launch")
    mode = scenario_mode(channels, store_count)
    expected_roas = forecast_roas(stage, launch_stage, own, market, competitors, channels)
    expected_revenue = round(total_budget * expected_roas, 2)
    expected_gross_profit = round(expected_revenue * margin, 2)
    expected_profit_after_budget = round(expected_gross_profit - total_budget, 2)
    payback_days = estimate_payback_days(total_budget, expected_revenue, margin, duration_days)
    allocations = build_allocations(total_budget, currency, channels, stage, launch_stage, store_count)
    adjustment = budget_adjustment(stage, launch_stage, own, market, competitors, expected_roas, total_budget)
    risks = budget_risks(stage, own, market, competitors, lifecycle, related_reviews)
    priority_score = priority_score_for_plan(stage, market, own, competitors, expected_roas, risks)
    return {
        "scenario_id": scenario.get("id") or "",
        "plan_name": scenario.get("plan_name") or scenario.get("name") or f"{product} budget plan",
        "product_name": product,
        "budget_mode": mode,
        "total_budget": round(total_budget, 2),
        "currency": currency,
        "duration_days": duration_days,
        "store_count": store_count,
        "countries": normalize_list(scenario.get("countries") or scenario.get("country")) or ["US"],
        "channels": channels,
        "per_store_budget": round(total_budget / store_count, 2),
        "target_margin": round(margin, 3),
        "lifecycle_stage": stage,
        "lifecycle_label": lifecycle.get("stage_label") or stage,
        "launch_stage": launch_stage,
        "launch_label": launch.get("launch_label") or launch_stage,
        "market_size": market,
        "competitor_intensity": competitors,
        "own_performance": own,
        "platform_mechanisms": launch.get("platform_mechanisms") or [],
        "expected_roas": expected_roas,
        "expected_revenue": expected_revenue,
        "expected_gross_profit": expected_gross_profit,
        "expected_profit_after_budget": expected_profit_after_budget,
        "payback_days": payback_days,
        "payback_label": payback_label(payback_days, duration_days),
        "recommended_allocation": allocations,
        "budget_adjustment": adjustment,
        "risks": risks,
        "next_actions": next_actions(product, mode, stage, launch_stage, allocations, adjustment),
        "strategy_memory": strategy_memory(product, stage, mode, market, own, risks),
        "priority_score": priority_score,
        "notes": str(scenario.get("notes") or ""),
    }


def summarize_own_performance(records: list[IntakeRecord]) -> dict[str, Any]:
    bucket = {
        "revenue": 0.0,
        "net_revenue": 0.0,
        "orders": 0.0,
        "units": 0.0,
        "ad_spend": 0.0,
        "refund_amount": 0.0,
        "return_count": 0.0,
        "refund_count": 0.0,
    }
    platforms: set[str] = set()
    stores: set[str] = set()
    for record in records[-60:]:
        values = extract_metric_values(record.fields)
        for key in bucket:
            bucket[key] += float(values.get(key) or 0)
        platform = record.fields.get("marketplace") or record.fields.get("source_platform") or record.fields.get("platform")
        store = record.fields.get("store_id") or record.fields.get("store_name") or record.fields.get("seller_name")
        if platform:
            platforms.add(str(platform))
        if store:
            stores.add(str(store))
    revenue = bucket["revenue"]
    ad_spend = bucket["ad_spend"]
    orders = bucket["orders"]
    return_rate = (bucket["return_count"] + bucket["refund_count"]) / orders if orders > 0 else 0.0
    return {
        "signal_count": len(records),
        "revenue": round(revenue, 2),
        "net_revenue": round(bucket["net_revenue"], 2),
        "orders": int(round(orders)),
        "units": int(round(bucket["units"])),
        "ad_spend": round(ad_spend, 2),
        "refund_amount": round(bucket["refund_amount"], 2),
        "return_rate": round(return_rate, 4),
        "roas": round(revenue / ad_spend, 4) if ad_spend > 0 else None,
        "platforms": sorted(platforms),
        "stores": sorted(stores),
    }


def summarize_market_size(records: list[IntakeRecord]) -> dict[str, Any]:
    gmv = 0.0
    sales = 0.0
    ranks: list[int] = []
    categories: set[str] = set()
    platforms: set[str] = set()
    for record in records[-80:]:
        fields = record.fields
        gmv += number(fields.get("gmv") or fields.get("total_revenue") or fields.get("sales_amount")) or 0
        sales += number(fields.get("sales_count") or fields.get("unit_count") or fields.get("units_sold") or fields.get("orders")) or 0
        rank = parse_rank(fields.get("rank_position") or fields.get("rank"))
        if rank:
            ranks.append(rank)
        category = fields.get("category_path") or fields.get("ranking_page") or fields.get("keyword")
        platform = fields.get("marketplace") or fields.get("source_platform") or fields.get("platform")
        if category:
            categories.add(str(category))
        if platform:
            platforms.add(str(platform))
    best_rank = min(ranks) if ranks else None
    score = min(35, int(gmv / 4000)) + min(25, int(sales / 200)) + min(20, len(records) * 3) + min(10, len(categories) * 2)
    if best_rank and best_rank <= 10:
        score += 12
    elif best_rank and best_rank <= 50:
        score += 7
    return {
        "score": max(0, min(100, score)),
        "signal_count": len(records),
        "visible_gmv": round(gmv, 2),
        "visible_sales": int(round(sales)),
        "best_rank": best_rank,
        "category_count": len(categories),
        "platforms": sorted(platforms),
        "market_level": market_level(score),
    }


def summarize_competitor_intensity(records: list[IntakeRecord]) -> dict[str, Any]:
    sellers: set[str] = set()
    brands: set[str] = set()
    prices: list[float] = []
    ranks: list[int] = []
    for record in records[-80:]:
        fields = record.fields
        for key, target in [("seller_name", sellers), ("shop_name", sellers), ("brand_name", brands), ("brand", brands)]:
            value = fields.get(key)
            if value:
                target.add(str(value))
        price = number(fields.get("price") or fields.get("sale_price"))
        if price:
            prices.append(price)
        rank = parse_rank(fields.get("rank_position") or fields.get("rank"))
        if rank:
            ranks.append(rank)
    best_rank = min(ranks) if ranks else None
    score = min(35, len(records) * 3) + min(25, len(sellers) * 5) + min(20, len(brands) * 4)
    if best_rank and best_rank <= 10:
        score += 18
    elif best_rank and best_rank <= 30:
        score += 10
    return {
        "score": max(0, min(100, score)),
        "signal_count": len(records),
        "seller_count": len(sellers),
        "brand_count": len(brands),
        "best_rank": best_rank,
        "average_price": round(sum(prices) / len(prices), 2) if prices else None,
        "level": intensity_level(score),
    }


def forecast_roas(
    stage: str,
    launch_stage: str,
    own: dict[str, Any],
    market: dict[str, Any],
    competitors: dict[str, Any],
    channels: list[str],
) -> float:
    own_roas = own.get("roas")
    if own_roas is not None:
        baseline = float(own_roas) * 0.68 + 0.8
    else:
        baseline = {"A": 1.15, "B": 2.2, "C": 1.85, "D": 0.75}.get(stage, 1.1)
    if market.get("score", 0) >= 70:
        baseline += 0.35
    elif market.get("score", 0) <= 20:
        baseline -= 0.25
    if competitors.get("score", 0) >= 75 and stage in {"A", "D"}:
        baseline -= 0.35
    elif competitors.get("score", 0) >= 75 and stage in {"B", "C"}:
        baseline -= 0.15
    if launch_stage == "scale_control":
        baseline += 0.25
    elif launch_stage == "cooldown_reset":
        baseline -= 0.5
    if any(is_amazon(channel) for channel in channels) and not own_roas:
        baseline += 0.15
    if any(is_tiktok(channel) for channel in channels) and stage == "A":
        baseline -= 0.1
    if own.get("return_rate", 0) >= 0.1:
        baseline -= 0.4
    return round(max(0.45, min(6.0, baseline)), 2)


def build_allocations(total_budget: float, currency: str, channels: list[str], stage: str, launch_stage: str, store_count: int) -> list[dict[str, Any]]:
    if total_budget <= 0:
        return []
    if len(channels) == 1:
        channel = channels[0]
        return channel_allocations(channel, total_budget, currency, stage, launch_stage, store_count)
    weights = channel_weights(channels)
    allocations: list[dict[str, Any]] = []
    for channel in channels:
        channel_budget = total_budget * weights[channel]
        allocations.extend(channel_allocations(channel, channel_budget, currency, stage, launch_stage, store_count, nested=True))
    return allocations


def channel_allocations(
    channel: str,
    channel_budget: float,
    currency: str,
    stage: str,
    launch_stage: str,
    store_count: int,
    nested: bool = False,
) -> list[dict[str, Any]]:
    if is_tiktok(channel):
        split = [
            ("content_horse_race", "Store-owned scripts, AI video prompts, shooting/editing, hook tests", 0.28),
            ("creator_seed_and_samples", "Creator seeding, samples, briefs, paid micro creators", 0.24),
            ("small_ads_or_gmv_max", "Small budget heat-up / GMV Max tests after content wins", 0.18),
            ("store_group_ops", "Coupons, product-card readiness, live/link rhythm drafts", 0.16),
            ("reserve_stop_loss", "Reserve for refunds, stock risk, failed materials, manual gates", 0.14),
        ]
        if stage == "B" or launch_stage == "scale_control":
            split = [
                ("winning_content_reinvestment", "Reinvest in winning videos, creators, and channel accounts", 0.30),
                ("creator_scale_pool", "A/B creator cooperation and repeat orders", 0.28),
                ("gmv_max_or_ads_ladder", "Laddered ad/Gmv Max budget with ROAS guardrail", 0.22),
                ("store_group_ops", "Discount/live/product-card execution drafts", 0.12),
                ("reserve_stop_loss", "Reserve and stop-loss buffer", 0.08),
            ]
    elif is_amazon(channel):
        split = [
            ("listing_visual_keyword", "Listing, main image, keyword map, A+ and offer readiness", 0.24),
            ("ppc_keyword_buying", "PPC keyword tests / ranking defense under ACOS guardrail", 0.38),
            ("coupon_review_service", "Coupon, review pain-point fixes, service response", 0.15),
            ("inventory_buffer", "Inventory and fulfillment buffer for paid traffic", 0.13),
            ("reserve_stop_loss", "Reserve for failed keywords and returns", 0.10),
        ]
    else:
        split = [
            ("listing_and_market_test", "Listing, marketplace fit, local keyword/category tests", 0.34),
            ("content_or_placement", "Content, creator, placement, or platform-specific traffic", 0.28),
            ("ops_and_service", "Store operations, fulfillment readiness, return handling", 0.18),
            ("reserve_stop_loss", "Reserve and stop-loss buffer", 0.20),
        ]
    rows = []
    for purpose, desc, weight in split:
        amount = round(channel_budget * weight, 2)
        rows.append(
            {
                "channel": channel,
                "purpose": purpose,
                "description": desc,
                "amount": amount,
                "currency": currency,
                "per_store_amount": round(amount / max(store_count, 1), 2),
                "guardrail": guardrail_for_purpose(channel, purpose),
                "nested": nested,
            }
        )
    return rows


def channel_weights(channels: list[str]) -> dict[str, float]:
    base: dict[str, float] = {}
    for channel in channels:
        if is_tiktok(channel):
            base[channel] = 0.40
        elif is_amazon(channel):
            base[channel] = 0.30
        elif "etsy" in channel.lower():
            base[channel] = 0.10
        elif "shopify" in channel.lower() or "own" in channel.lower():
            base[channel] = 0.10
        elif "walmart" in channel.lower():
            base[channel] = 0.08
        else:
            base[channel] = 0.06
    total = sum(base.values()) or 1.0
    return {channel: value / total for channel, value in base.items()}


def budget_adjustment(
    stage: str,
    launch_stage: str,
    own: dict[str, Any],
    market: dict[str, Any],
    competitors: dict[str, Any],
    expected_roas: float,
    total_budget: float,
) -> dict[str, Any]:
    roas = own.get("roas")
    return_rate = float(own.get("return_rate") or 0)
    if stage == "D" or launch_stage == "cooldown_reset" or return_rate >= 0.12 or (roas is not None and roas < 1.1):
        return {
            "decision": "cut_or_hold",
            "change_ratio": -0.35,
            "suggested_budget": round(max(500.0, total_budget * 0.65), 2),
            "reason": "Risk or weak return signal. Hold external spend, fix content/listing/returns first.",
        }
    if stage == "B" and expected_roas >= 2.0 and market.get("score", 0) >= 45:
        return {
            "decision": "increase_ladder",
            "change_ratio": 0.25,
            "suggested_budget": round(total_budget * 1.25, 2),
            "reason": "Growth stage with acceptable return forecast. Increase by ladder, not all at once.",
        }
    if not own.get("signal_count"):
        return {
            "decision": "test_budget_only",
            "change_ratio": 0,
            "suggested_budget": round(min(total_budget, 3000.0), 2),
            "reason": "No own store data yet. Use small validation budget before store-group scaling.",
        }
    if competitors.get("score", 0) >= 75 and market.get("score", 0) < 45:
        return {
            "decision": "hold",
            "change_ratio": 0,
            "suggested_budget": round(total_budget, 2),
            "reason": "Competitor pressure is high but market signal is not strong enough for aggressive spend.",
        }
    return {
        "decision": "keep_balanced",
        "change_ratio": 0,
        "suggested_budget": round(total_budget, 2),
        "reason": "Keep planned budget and review after the next sales/ad/content data window.",
    }


def budget_risks(
    stage: str,
    own: dict[str, Any],
    market: dict[str, Any],
    competitors: dict[str, Any],
    lifecycle: dict[str, Any],
    review_records: list[IntakeRecord],
) -> list[str]:
    risks: list[str] = []
    if stage == "D":
        risks.append("Lifecycle is D: avoid adding large budget before product/listing/content reset.")
    if not own.get("signal_count"):
        risks.append("Own-store sales/ad/return data is missing; forecast is based on market signals only.")
    if own.get("roas") is not None and float(own["roas"]) < 1.2:
        risks.append("Own ROAS is below the safe test line.")
    if float(own.get("return_rate") or 0) >= 0.1:
        risks.append("Return/refund rate is high; budget scaling can magnify losses.")
    if market.get("score", 0) < 25:
        risks.append("Market signal is still small; do not build a large store group yet.")
    if competitors.get("score", 0) >= 75:
        risks.append("Competitor intensity is high; price, review, creator, and listing quality must be checked before scaling.")
    if lifecycle.get("inventory_qty") is None:
        risks.append("Inventory/cost data is missing; payback and stock plan need supply-chain input.")
    elif int(lifecycle.get("inventory_qty") or 0) <= 30 and stage in {"B", "C"}:
        risks.append("Inventory is too low for a scale plan.")
    if review_records:
        risks.append("Review/complaint records exist; check pain points before adding budget.")
    return risks[:8]


def next_actions(
    product: str,
    mode: str,
    stage: str,
    launch_stage: str,
    allocations: list[dict[str, Any]],
    adjustment: dict[str, Any],
) -> list[str]:
    actions = [
        f"Create a budget approval draft for {product}; no real ad, price, discount, or listing action runs automatically.",
        "Bind this plan to current store sales/ad/return snapshots and refresh it daily.",
    ]
    if mode == "tk_only":
        actions.append("Prepare TK horse-race pool: store-owned videos, creator briefs, channel accounts, product-card conversion checks.")
    elif mode == "multi_platform":
        actions.append("Split budget by platform: TikTok for content discovery, Amazon for keyword buying, long-tail platforms for listing validation.")
    if stage == "A":
        actions.append("Run small validation first; do not open multiple stores before content and conversion prove themselves.")
    if stage == "B" or launch_stage == "scale_control":
        actions.append("Use ladder scaling: review ROAS, return rate, stock days, and material decay before every budget increase.")
    if adjustment.get("decision") in {"cut_or_hold", "test_budget_only"}:
        actions.append("Send scale actions to pending approval and keep execution paused until the weak signal is fixed.")
    top = sorted(allocations, key=lambda item: float(item.get("amount") or 0), reverse=True)[:2]
    for item in top:
        actions.append(f"Prepare {item['purpose']} work package: {item['currency']} {item['amount']}.")
    return actions[:8]


def strategy_memory(
    product: str,
    stage: str,
    mode: str,
    market: dict[str, Any],
    own: dict[str, Any],
    risks: list[str],
) -> dict[str, Any]:
    return {
        "observed": [
            f"{product} lifecycle stage is {stage}.",
            f"Market level: {market.get('market_level')} with {market.get('signal_count')} related signals.",
            f"Own data signals: {own.get('signal_count')} records, ROAS {own.get('roas') if own.get('roas') is not None else 'missing'}.",
        ],
        "worked_before": [
            "TK: prepare multiple content/creator/account horses first, then scale winners.",
            "Amazon: buy keywords only when listing, image, price, review, and inventory can carry paid search.",
        ],
        "failed_before": [
            "Scaling without own-store sales/return data creates false confidence.",
            "Large budget on old/protected stores can disturb working ads or listings; use approval queues.",
        ],
        "valid_conditions": [
            "Increase budget only when ROAS, return rate, stock days, and content signal are all healthy.",
            f"Current mode {mode} is valid only if the selected platforms and store count match available operations capacity.",
        ],
        "cannot_do": risks or ["No major blocker detected, but real spend still needs confirmation."],
        "next_review_trigger": "Review daily, and immediately after ROAS drops below guardrail, return rate rises, inventory falls under safety days, or a competitor ranking spike appears.",
    }


def priority_score_for_plan(
    stage: str,
    market: dict[str, Any],
    own: dict[str, Any],
    competitors: dict[str, Any],
    expected_roas: float,
    risks: list[str],
) -> int:
    score = int(market.get("score", 0) * 0.45 + competitors.get("score", 0) * 0.15 + expected_roas * 12)
    if stage == "B":
        score += 18
    elif stage == "C":
        score += 8
    elif stage == "D":
        score -= 20
    if own.get("roas") and float(own["roas"]) >= 2:
        score += 12
    score -= min(24, len(risks) * 4)
    return max(0, min(100, score))


def build_budget_summary(plans: list[dict[str, Any]]) -> dict[str, Any]:
    total_budget = sum(float(item.get("total_budget") or 0) for item in plans)
    expected_revenue = sum(float(item.get("expected_revenue") or 0) for item in plans)
    expected_profit = sum(float(item.get("expected_profit_after_budget") or 0) for item in plans)
    increase = len([item for item in plans if item.get("budget_adjustment", {}).get("decision") == "increase_ladder"])
    hold = len([item for item in plans if item.get("budget_adjustment", {}).get("decision") in {"hold", "cut_or_hold", "test_budget_only"}])
    return {
        "plan_count": len(plans),
        "total_budget": round(total_budget, 2),
        "expected_revenue": round(expected_revenue, 2),
        "expected_profit_after_budget": round(expected_profit, 2),
        "average_expected_roas": round(expected_revenue / total_budget, 2) if total_budget > 0 else 0,
        "increase_candidates": increase,
        "hold_or_test_candidates": hold,
    }


def build_budget_planning_report(run_date: str, plans: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        f"# Product Budget Planning Report - {run_date}",
        "",
        "## Summary",
        f"- Plans: {summary.get('plan_count', 0)}",
        f"- Total budget: ${float(summary.get('total_budget') or 0):,.2f}",
        f"- Expected revenue: ${float(summary.get('expected_revenue') or 0):,.2f}",
        f"- Expected profit after budget: ${float(summary.get('expected_profit_after_budget') or 0):,.2f}",
        f"- Average expected ROAS: {summary.get('average_expected_roas', 0)}",
        "",
        "## Product Plans",
    ]
    if not plans:
        lines.append("- No product budget plan yet. Add a budget scenario or set monitored products first.")
        return "\n".join(lines) + "\n"
    for plan in plans[:40]:
        adjustment = plan.get("budget_adjustment", {})
        lines.append(
            f"- {plan['product_name']} | {plan['budget_mode']} | budget ${float(plan['total_budget']):,.2f} | "
            f"ROAS {plan['expected_roas']} | payback {plan['payback_label']} | "
            f"{adjustment.get('decision')}: {adjustment.get('reason')}"
        )
    lines.extend(["", "## Safety", "- Real ad spend, discount, price, listing, inventory, campaign, refund, shipping, or publishing actions must go to the approval center first."])
    return "\n".join(lines) + "\n"


def write_budget_report(root: Path, run_date: str, content: str) -> Path:
    path = root / "outputs" / f"{REPORT_PREFIX}_{run_date}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_budget_json(root: Path, run_date: str, payload: dict[str, Any]) -> Path:
    path = root / "outputs" / f"{REPORT_PREFIX}_{run_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"run_date": run_date, **payload}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def latest_budget_planning_report(root: Path) -> tuple[str, Path | None]:
    output_dir = root / "outputs"
    if not output_dir.exists():
        return "No budget planning report yet.", None
    paths = sorted(output_dir.glob(f"{REPORT_PREFIX}_*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not paths:
        return "No budget planning report yet.", None
    return paths[0].read_text(encoding="utf-8"), paths[0]


def related_records(product_name: str, records: list[IntakeRecord]) -> list[IntakeRecord]:
    key = normalized_key(product_name)
    if not key:
        return []
    words = [word for word in key.split() if len(word) >= 3]
    result: list[IntakeRecord] = []
    for record in records:
        compact = record_search_text(record)
        if key in compact or (words and all(word in compact for word in words[:4])):
            result.append(record)
    return result


def record_search_text(record: IntakeRecord) -> str:
    cached = record.metadata.get("_budget_search_text")
    if isinstance(cached, str):
        return cached
    compact = normalized_key(json.dumps(record.fields, ensure_ascii=False).lower())
    record.metadata["_budget_search_text"] = compact
    return compact


def find_lifecycle_plan(product: str, plans: list[dict[str, Any]]) -> dict[str, Any]:
    key = normalized_key(product)
    for plan in plans:
        if normalized_key(plan.get("product_name")) == key:
            return plan
    for plan in plans:
        if key and key in normalized_key(plan.get("product_name")):
            return plan
    return {}


def find_launch_plan(product: str, plans: list[dict[str, Any]]) -> dict[str, Any]:
    key = normalized_key(product)
    for plan in plans:
        if normalized_key(plan.get("product_name")) == key:
            return plan
    for plan in plans:
        if key and key in normalized_key(plan.get("product_name")):
            return plan
    return {}


def channels_from_launch(launch: dict[str, Any]) -> list[str]:
    mechanisms = launch.get("platform_mechanisms") if isinstance(launch.get("platform_mechanisms"), list) else []
    channels = [str(item.get("platform") or "") for item in mechanisms if isinstance(item, dict) and item.get("platform")]
    return normalize_channels(channels)


def channels_from_targets(product: str, targets: list[Any]) -> list[str]:
    key = normalized_key(product)
    for target in targets:
        if isinstance(target, dict) and normalized_key(target.get("name") or target.get("product_family")) == key:
            return normalize_channels(target.get("platforms"))
    return []


def estimate_margin(root: Path, product: str, supply_records: list[IntakeRecord] | None = None) -> float:
    costs: list[float] = []
    prices: list[float] = []
    for record in related_records(product, supply_records if supply_records is not None else read_records(root, "supply_chain")):
        cost = number(record.fields.get("unit_cost") or record.fields.get("cost"))
        price = number(record.fields.get("sale_price") or record.fields.get("price"))
        if cost:
            costs.append(cost)
        if price:
            prices.append(price)
    if costs and prices:
        avg_cost = sum(costs) / len(costs)
        avg_price = sum(prices) / len(prices)
        if avg_price > 0:
            return clamp_float((avg_price - avg_cost) / avg_price, 0.05, 0.9)
    return 0.45


def normalize_channels(value: Any) -> list[str]:
    aliases = {
        "tk": "TikTok Shop",
        "tiktok": "TikTok Shop",
        "tiktok shop": "TikTok Shop",
        "amazon": "Amazon",
        "etsy": "Etsy",
        "walmart": "Walmart",
        "shopify": "Shopify",
        "shein": "SHEIN",
        "shopee": "Shopee",
    }
    raw = normalize_list(value)
    channels: list[str] = []
    for item in raw:
        clean = item.strip()
        label = aliases.get(clean.lower(), clean)
        if label and label not in channels:
            channels.append(label)
    return channels


def scenario_mode(channels: list[str], store_count: int) -> str:
    if channels and all(is_tiktok(channel) for channel in channels):
        return "tk_only_store_group" if store_count > 1 else "tk_only"
    if len(channels) >= 2:
        return "multi_platform_store_group" if store_count > 1 else "multi_platform"
    return "single_platform"


def guardrail_for_purpose(channel: str, purpose: str) -> str:
    if "reserve" in purpose:
        return "Do not spend unless a reviewed risk or failed test requires it."
    if is_tiktok(channel):
        return "Only scale after content retention, product-card clicks, orders, return rate, and stock are healthy."
    if is_amazon(channel):
        return "Keep PPC under break-even ACOS/ROAS and pause losing keywords quickly."
    return "Use small tests first; real platform actions need approval."


def default_budget_for_stage(stage: str) -> float:
    return {"A": 3000.0, "B": 20000.0, "C": 12000.0, "D": 1000.0}.get(stage, 3000.0)


def estimate_payback_days(total_budget: float, expected_revenue: float, margin: float, duration_days: int) -> int | None:
    if total_budget <= 0 or expected_revenue <= 0 or margin <= 0:
        return None
    daily_gross_profit = expected_revenue * margin / max(duration_days, 1)
    if daily_gross_profit <= 0:
        return None
    return int(math.ceil(total_budget / daily_gross_profit))


def payback_label(payback_days: int | None, duration_days: int) -> str:
    if payback_days is None:
        return "unknown"
    if payback_days <= duration_days:
        return f"{payback_days} days / inside plan window"
    return f"{payback_days} days / longer than plan window"


def market_level(score: int) -> str:
    if score >= 75:
        return "large"
    if score >= 45:
        return "medium"
    if score >= 20:
        return "small_validating"
    return "unknown_or_tiny"


def intensity_level(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 45:
        return "medium"
    if score >= 20:
        return "low"
    return "unknown"


def parse_rank(value: Any) -> int | None:
    parsed = number(value)
    if parsed is None or parsed <= 0:
        return None
    return int(parsed)


def is_tiktok(channel: str) -> bool:
    lowered = channel.lower()
    return "tiktok" in lowered or lowered == "tk" or "tk shop" in lowered


def is_amazon(channel: str) -> bool:
    return "amazon" in channel.lower()


def clamp_float(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def normalized_key(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").replace("-", " ").split())
