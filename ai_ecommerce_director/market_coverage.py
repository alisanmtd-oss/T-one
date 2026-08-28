from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from math import log1p
from pathlib import Path
from typing import Any

from .storage import OUTPUT_DIR, append_record, read_records
from .types import IntakeRecord


MARKET_COVERAGE_REPORT_PREFIX = "market_coverage_intelligence"


@dataclass(slots=True)
class MarketCoverageResult:
    run_date: str
    signals: list[dict[str, Any]]
    hypotheses: list[dict[str, Any]]
    plans: list[dict[str, Any]]
    tasks: list[dict[str, Any]]
    report: str
    report_path: Path
    json_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "signals": self.signals,
            "hypotheses": self.hypotheses,
            "plans": self.plans,
            "tasks": self.tasks,
            "report": self.report,
            "report_path": str(self.report_path),
            "json_path": str(self.json_path),
        }


def run_market_coverage_intelligence(root: Path, run_date: str | None = None) -> MarketCoverageResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    source_items = collect_market_inputs(root, report_date)
    segments = build_segment_snapshots(source_items, report_date)
    signals = build_market_signals(segments, report_date)
    hypotheses = build_market_hypotheses(signals, report_date)
    plans = build_market_plans(hypotheses, report_date)
    tasks = build_market_tasks(plans, report_date)

    persist_market_records(root, report_date, source_items, segments, signals, hypotheses, plans, tasks)
    report = build_market_coverage_report(report_date, segments, signals, hypotheses, plans, tasks)
    report_path, json_path = write_outputs(root, report_date, report, segments, signals, hypotheses, plans, tasks)

    return MarketCoverageResult(report_date, signals, hypotheses, plans, tasks, report, report_path, json_path)


def collect_market_inputs(root: Path, report_date: str) -> list[dict[str, Any]]:
    records = []
    for record_type in [
        "platform_ranking_signal",
        "viral_content_signal",
        "creator_spike_event",
        "review_insight",
        "keyword_intelligence",
        "hot_link",
    ]:
        records.extend(read_records(root, record_type))
    items = [normalize_source_record(record) for record in records]
    useful_items = [item for item in items if item and not is_weak_or_verification_item(item)]
    if useful_items:
        return useful_items
    return training_seed_market_items(report_date)


def normalize_source_record(record: IntakeRecord) -> dict[str, Any]:
    fields = record.fields
    platform = first_text(fields, ["platform", "marketplace", "source_platform", "platform_name"], "TikTok Shop")
    country = first_text(fields, ["country", "country_code", "market"], "US")
    product_name = first_text(fields, ["product_name", "title", "product_title", "keyword", "brand"], "")
    category = first_text(fields, ["category", "category_path", "niche", "data_category"], infer_category(product_name))
    segment = first_text(fields, ["segment", "sub_category", "keyword", "target_keyword"], infer_segment(product_name, category))
    rank_position = as_float(fields.get("rank_position") or fields.get("rank") or fields.get("position"), default=0)
    previous_rank = as_float(fields.get("previous_rank") or fields.get("baseline_rank"), default=rank_position + 18 if rank_position else 0)
    current_value = as_float(
        fields.get("sales_count")
        or fields.get("view_count")
        or fields.get("views")
        or fields.get("gmv")
        or fields.get("rank_score"),
        default=max(10, 120 - rank_position) if rank_position else 50,
    )
    baseline_7d = as_float(fields.get("baseline_7d") or fields.get("previous_value"), default=max(1, current_value * 0.72))
    baseline_30d = as_float(fields.get("baseline_30d"), default=max(1, current_value * 0.48))
    price = as_float(fields.get("price") or fields.get("avg_price"), default=infer_price(product_name, category))
    platform_priority = 1.0 if "tiktok" in platform.lower() else 0.68
    return {
        "source_record_id": record.record_id,
        "source_record_type": record.record_type,
        "source": record.source,
        "platform": platform,
        "country": country,
        "category": category,
        "segment": segment,
        "product_name": product_name or segment,
        "entity_id": first_text(fields, ["product_id", "asin", "video_url", "url", "source_url"], product_name or segment),
        "source_url": first_text(fields, ["product_url", "video_url", "url", "source_url", "page_url"], ""),
        "creator_handle": first_text(fields, ["creator_handle", "author_username", "influencer_handle"], ""),
        "keyword": first_text(fields, ["keyword", "target_keyword", "search_keyword"], segment),
        "rank_position": rank_position,
        "previous_rank": previous_rank,
        "current_value": current_value,
        "baseline_7d": baseline_7d,
        "baseline_30d": baseline_30d,
        "price": price,
        "review_count": as_float(fields.get("review_count"), default=0),
        "rating": as_float(fields.get("rating"), default=4.2),
        "risk_score": as_float(fields.get("risk_score"), default=infer_risk_score(product_name, category)),
        "confidence_score": as_float(fields.get("source_confidence") or record.confidence, default=0.64) * platform_priority,
        "evidence_count": 1,
        "raw_text": record.raw_text,
        "is_training_seed": False,
    }


def training_seed_market_items(report_date: str) -> list[dict[str, Any]]:
    seed_rows = [
        {
            "platform": "TikTok Shop",
            "country": "US",
            "category": "Beauty & Personal Care > Cleansers",
            "segment": "Amino Acid Cleanser",
            "product_name": "Gentle amino acid facial cleanser",
            "current_value": 136,
            "baseline_7d": 78,
            "baseline_30d": 42,
            "rank_position": 82,
            "previous_rank": 164,
            "price": 14.99,
            "risk_score": 0.18,
            "creator_handle": "beauty_micro_creator",
            "keyword": "amino acid cleanser",
        },
        {
            "platform": "TikTok Shop",
            "country": "US",
            "category": "Health > Sleep Support",
            "segment": "Melatonin Supplement",
            "product_name": "Melatonin sleep support gummies",
            "current_value": 118,
            "baseline_7d": 66,
            "baseline_30d": 41,
            "rank_position": 104,
            "previous_rank": 202,
            "price": 19.99,
            "risk_score": 0.46,
            "creator_handle": "wellness_creator",
            "keyword": "melatonin gummies",
        },
        {
            "platform": "TikTok Shop",
            "country": "US",
            "category": "Fashion > Menswear > T-Shirts",
            "segment": "Washed T-Shirt",
            "product_name": "Vintage washed heavyweight T-shirt",
            "current_value": 154,
            "baseline_7d": 92,
            "baseline_30d": 48,
            "rank_position": 68,
            "previous_rank": 146,
            "price": 29.99,
            "risk_score": 0.22,
            "creator_handle": "blue_collar_creator",
            "keyword": "washed t shirt",
        },
        {
            "platform": "TikTok Shop",
            "country": "US",
            "category": "Electronics Accessories > Phone Protection",
            "segment": "Phone Screen Protector",
            "product_name": "Matte privacy phone screen protector",
            "current_value": 172,
            "baseline_7d": 88,
            "baseline_30d": 52,
            "rank_position": 57,
            "previous_rank": 158,
            "price": 12.99,
            "risk_score": 0.14,
            "creator_handle": "phone_case_reviewer",
            "keyword": "phone screen protector",
        },
        {
            "platform": "TikTok Shop",
            "country": "US",
            "category": "Jewelry > Streetwear Jewelry",
            "segment": "Hip-hop Jewelry",
            "product_name": "Moissanite pendant streetwear jewelry",
            "current_value": 96,
            "baseline_7d": 54,
            "baseline_30d": 31,
            "rank_position": 122,
            "previous_rank": 230,
            "price": 69.99,
            "risk_score": 0.38,
            "creator_handle": "streetwear_fit_creator",
            "keyword": "moissanite pendant",
        },
        {
            "platform": "Amazon",
            "country": "US",
            "category": "Beauty & Personal Care > Skin Care",
            "segment": "Glycolic Acid Toner",
            "product_name": "Glycolic acid exfoliating toner",
            "current_value": 82,
            "baseline_7d": 64,
            "baseline_30d": 48,
            "rank_position": 88,
            "previous_rank": 119,
            "price": 12.99,
            "risk_score": 0.24,
            "creator_handle": "",
            "keyword": "glycolic acid toner",
        },
    ]
    items = []
    for index, row in enumerate(seed_rows, start=1):
        item = {
            **row,
            "source_record_id": f"training_seed_{report_date}_{index}",
            "source_record_type": "training_seed",
            "source": "market_coverage_training_seed",
            "entity_id": f"{row['platform']}::{row['country']}::{row['segment']}",
            "source_url": "",
            "review_count": 0,
            "rating": 4.2,
            "confidence_score": 0.52,
            "evidence_count": 1,
            "raw_text": f"Training seed for {row['segment']}. Replace with FastMoss/Kalodata/TikTok Shop evidence when collected.",
            "is_training_seed": True,
        }
        items.append(item)
    return items


def build_segment_snapshots(items: list[dict[str, Any]], report_date: str) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for item in items:
        key = (item["platform"], item["country"], item["category"], item["segment"])
        grouped.setdefault(key, []).append(item)

    snapshots = []
    for (platform, country, category, segment), rows in grouped.items():
        current = sum(row["current_value"] for row in rows)
        baseline_7d = max(1.0, sum(row["baseline_7d"] for row in rows))
        baseline_30d = max(1.0, sum(row["baseline_30d"] for row in rows))
        delta_7d = current - baseline_7d
        delta_30d = current - baseline_30d
        velocity = delta_7d / baseline_7d
        acceleration = (delta_7d / baseline_7d) - ((baseline_7d - baseline_30d) / baseline_30d)
        avg_price = sum(row["price"] for row in rows) / len(rows)
        avg_rank = sum(row["rank_position"] or 150 for row in rows) / len(rows)
        risk_score = sum(row["risk_score"] for row in rows) / len(rows)
        confidence_score = min(0.95, sum(row["confidence_score"] for row in rows) / len(rows) + min(len(rows), 5) * 0.03)
        competition_density = infer_competition_density(avg_rank, len(rows), platform)
        content_replicability = infer_content_replicability(category, segment)
        creator_availability = infer_creator_availability(rows)
        profit_potential = infer_profit_potential(avg_price, category)
        opportunity_score = score_opportunity(
            velocity=velocity,
            acceleration=acceleration,
            profit_potential=profit_potential,
            content_replicability=content_replicability,
            creator_availability=creator_availability,
            keyword_fit=0.82 if segment else 0.55,
            competition_density=competition_density,
            risk_score=risk_score,
            logistics_score=0.78,
        )
        snapshots.append(
            {
                "snapshot_id": stable_id("mseg", report_date, platform, country, category, segment),
                "run_date": report_date,
                "platform": platform,
                "country": country,
                "category": category,
                "segment": segment,
                "sample_count": len(rows),
                "current_value": round(current, 2),
                "baseline_7d": round(baseline_7d, 2),
                "baseline_30d": round(baseline_30d, 2),
                "delta_7d": round(delta_7d, 2),
                "delta_30d": round(delta_30d, 2),
                "velocity": round(velocity, 4),
                "acceleration": round(acceleration, 4),
                "avg_price": round(avg_price, 2),
                "avg_rank": round(avg_rank, 1),
                "risk_score": round(risk_score, 4),
                "confidence_score": round(confidence_score, 4),
                "competition_density": round(competition_density, 4),
                "content_replicability": round(content_replicability, 4),
                "creator_availability": round(creator_availability, 4),
                "profit_potential": round(profit_potential, 4),
                "opportunity_score": opportunity_score,
                "evidence_count": len(rows),
                "source_record_ids": [row["source_record_id"] for row in rows[:20]],
                "is_training_seed": all(row.get("is_training_seed") for row in rows),
                "keywords": sorted({row["keyword"] for row in rows if row.get("keyword")})[:8],
                "creators": sorted({row["creator_handle"] for row in rows if row.get("creator_handle")})[:8],
                "products": [row["product_name"] for row in rows[:5]],
            }
        )
    return sorted(snapshots, key=lambda item: item["opportunity_score"], reverse=True)


def build_market_signals(segments: list[dict[str, Any]], report_date: str) -> list[dict[str, Any]]:
    signals = []
    for segment in segments:
        signal_type = choose_signal_type(segment)
        signal = {
            "market_signal_id": stable_id("msig", report_date, segment["platform"], segment["country"], segment["category"], segment["segment"]),
            "signal_id": stable_id("msig", report_date, segment["platform"], segment["country"], segment["category"], segment["segment"]),
            "run_date": report_date,
            "platform": segment["platform"],
            "country": segment["country"],
            "category": segment["category"],
            "segment": segment["segment"],
            "entity_type": "market_segment",
            "entity_id": segment["snapshot_id"],
            "signal_type": signal_type,
            "current_value": segment["current_value"],
            "baseline_7d": segment["baseline_7d"],
            "baseline_30d": segment["baseline_30d"],
            "delta_7d": segment["delta_7d"],
            "delta_30d": segment["delta_30d"],
            "velocity": segment["velocity"],
            "acceleration": segment["acceleration"],
            "confidence_score": segment["confidence_score"],
            "risk_score": segment["risk_score"],
            "opportunity_score": segment["opportunity_score"],
            "evidence_count": segment["evidence_count"],
            "created_at": now_utc(),
            "summary": build_signal_summary(segment, signal_type),
            "recommended_next_step": recommended_signal_step(segment),
            "is_training_seed": segment["is_training_seed"],
        }
        signals.append(signal)
    return signals


def build_market_hypotheses(signals: list[dict[str, Any]], report_date: str) -> list[dict[str, Any]]:
    hypotheses = []
    for signal in signals[:8]:
        text = (
            f"{signal['platform']} {signal['country']} 的 {signal['segment']} 出现 {signal['signal_type']}，"
            f"可以用“热视频拆解 + 中腰部商品复盘 + 小预算测试”验证是否有进入价值。"
        )
        confidence = min(0.92, signal["confidence_score"] * 0.72 + signal["opportunity_score"] / 250)
        priority = round(signal["opportunity_score"] * confidence * (1 - signal["risk_score"]), 2)
        hypotheses.append(
            {
                "market_hypothesis_id": stable_id("mhyp", report_date, signal["market_signal_id"]),
                "hypothesis_id": stable_id("mhyp", report_date, signal["market_signal_id"]),
                "run_date": report_date,
                "signal_id": signal["market_signal_id"],
                "platform": signal["platform"],
                "country": signal["country"],
                "category": signal["category"],
                "segment": signal["segment"],
                "opportunity_type": "category_product_selection",
                "hypothesis_text": text,
                "expected_profit": round(signal["opportunity_score"] * 18, 2),
                "risk_score": signal["risk_score"],
                "confidence_score": round(confidence, 4),
                "priority_score": priority,
                "evidence_count": signal["evidence_count"],
                "status": "ready_for_director_review" if not signal["is_training_seed"] else "needs_real_platform_evidence",
                "created_from_signal": signal["market_signal_id"],
            }
        )
    return hypotheses


def build_market_plans(hypotheses: list[dict[str, Any]], report_date: str) -> list[dict[str, Any]]:
    plans = []
    for hypothesis in hypotheses[:5]:
        segment = hypothesis["segment"]
        plans.append(
            {
                "market_plan_id": stable_id("mplan", report_date, hypothesis["market_hypothesis_id"]),
                "plan_id": stable_id("mplan", report_date, hypothesis["market_hypothesis_id"]),
                "run_date": report_date,
                "hypothesis_id": hypothesis["market_hypothesis_id"],
                "platform": hypothesis["platform"],
                "country": hypothesis["country"],
                "category": hypothesis["category"],
                "segment": segment,
                "plan_name": f"{segment} 市场验证计划",
                "steps": [
                    "采集 TikTok Shop 买家入口 / FastMoss / Kalodata 的商品排名、达人、视频和评论证据",
                    "拆 10 条同品热视频：0-3秒钩子、场景、运镜、字幕、CTA、评论购买意图",
                    "对比 Amazon / Etsy / Walmart 的价格、评价痛点、主图和标题结构",
                    "生成小预算实验草稿：商品假设、素材脚本、达人类型、止损线和复盘指标",
                ],
                "guardrails": [
                    "不自动发布商品、不自动改价、不自动投放广告",
                    "涉及店铺动作进入人工确认队列",
                    "训练种子必须补齐真实平台证据后才能进入执行",
                ],
                "owner_agent": "Market Coverage Intelligence Agent",
                "target_agent": "AI Ecommerce Director",
                "status": "draft",
            }
        )
    return plans


def build_market_tasks(plans: list[dict[str, Any]], report_date: str) -> list[dict[str, Any]]:
    tasks = []
    for plan in plans:
        tasks.append(
            {
                "market_task_id": stable_id("mtask", report_date, plan["market_plan_id"]),
                "task_id": stable_id("mtask", report_date, plan["market_plan_id"]),
                "run_date": report_date,
                "plan_id": plan["market_plan_id"],
                "task_type": "market_evidence_collection",
                "platform": plan["platform"],
                "country": plan["country"],
                "category": plan["category"],
                "segment": plan["segment"],
                "priority": 95 if "tiktok" in plan["platform"].lower() else 72,
                "status": "queued",
                "automation_level": "L0-L2",
                "target_agent": "Market Coverage Intelligence Agent",
                "payload": {
                    "collect": ["product_rank", "creator_rank", "viral_video", "comments", "price", "reviews"],
                    "video_focus": "TikTok only for video scripts; Amazon is product/listing/review supplement.",
                    "manual_gate": True,
                },
            }
        )
    return tasks


def persist_market_records(
    root: Path,
    report_date: str,
    source_items: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    hypotheses: list[dict[str, Any]],
    plans: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
) -> None:
    category_seen = set()
    for segment in segments:
        category_key = (segment["platform"], segment["country"], segment["category"])
        if category_key not in category_seen:
            category_seen.add(category_key)
            append_market_record(root, "market_category_snapshot", {
                "snapshot_id": stable_id("mcat", report_date, *category_key),
                "run_date": report_date,
                "platform": segment["platform"],
                "country": segment["country"],
                "category": segment["category"],
                "segment_count": sum(1 for item in segments if (item["platform"], item["country"], item["category"]) == category_key),
                "top_segment": segment["segment"],
                "top_opportunity_score": segment["opportunity_score"],
            })
        append_market_record(root, "market_segment_snapshot", segment)
        append_market_record(root, "category_growth_snapshot", {
            "snapshot_id": stable_id("mgro", report_date, segment["snapshot_id"]),
            "run_date": report_date,
            **pick(segment, ["platform", "country", "category", "segment", "current_value", "baseline_7d", "baseline_30d", "delta_7d", "delta_30d", "velocity", "acceleration", "confidence_score"]),
        })
        if 50 <= float(segment["avg_rank"]) <= 500:
            append_market_record(root, "mid_rank_product_signal", {
                "signal_id": stable_id("mrank", report_date, segment["snapshot_id"]),
                "run_date": report_date,
                **pick(segment, ["platform", "country", "category", "segment", "avg_rank", "velocity", "opportunity_score", "products", "keywords"]),
                "reason": "中腰部排名正在上升，适合找还没被头部垄断的品和素材打法。",
            })
        if (segment["opportunity_score"] >= 30 or segment["velocity"] >= 0.35) and segment["competition_density"] <= 0.78:
            append_market_record(root, "long_tail_opportunity", {
                "opportunity_id": stable_id("mlong", report_date, segment["snapshot_id"]),
                "run_date": report_date,
                **pick(segment, ["platform", "country", "category", "segment", "keywords", "opportunity_score", "competition_density", "risk_score"]),
                "reason": "增长够快、竞争尚未过热，可进入长尾词和达人视频验证。",
            })
        append_market_record(root, "keyword_trend_snapshot", {
            "trend_id": stable_id("mkey", report_date, segment["snapshot_id"]),
            "run_date": report_date,
            **pick(segment, ["platform", "country", "category", "segment", "keywords", "velocity", "opportunity_score"]),
        })
        append_market_record(root, "creator_trend_snapshot", {
            "trend_id": stable_id("mcre", report_date, segment["snapshot_id"]),
            "run_date": report_date,
            **pick(segment, ["platform", "country", "category", "segment", "creators", "creator_availability", "opportunity_score"]),
        })
        append_market_record(root, "video_trend_snapshot", {
            "trend_id": stable_id("mvid", report_date, segment["snapshot_id"]),
            "run_date": report_date,
            **pick(segment, ["platform", "country", "category", "segment", "content_replicability", "opportunity_score"]),
            "video_script_focus": video_script_focus(segment),
        })
        append_market_record(root, "price_trend_snapshot", {
            "trend_id": stable_id("mpri", report_date, segment["snapshot_id"]),
            "run_date": report_date,
            **pick(segment, ["platform", "country", "category", "segment", "avg_price", "profit_potential", "risk_score"]),
        })
        append_market_record(root, "review_painpoint_snapshot", {
            "trend_id": stable_id("mrev", report_date, segment["snapshot_id"]),
            "run_date": report_date,
            **pick(segment, ["platform", "country", "category", "segment", "risk_score", "confidence_score"]),
            "painpoints_to_collect": infer_painpoints(segment),
        })
        append_market_record(root, "knowledge_concept_weight", {
            "concept_key": stable_id("concept", segment["platform"], segment["country"], segment["segment"]),
            "normalized_entity": segment["segment"].lower(),
            "entity_type": "market_segment",
            "platform": segment["platform"],
            "country": segment["country"],
            "weight": round(min(1.0, segment["opportunity_score"] / 100), 4),
            "source": "market_coverage_intelligence",
            "last_updated": now_utc(),
            "reason": "Market Coverage Intelligence updated segment opportunity weight.",
        })
    for signal in signals:
        append_market_record(root, "market_signal", signal)
    for hypothesis in hypotheses:
        append_market_record(root, "market_hypothesis", hypothesis)
    for plan in plans:
        append_market_record(root, "market_plan", plan)
    for task in tasks:
        append_market_record(root, "market_task", task)
        append_market_record(root, "task_queue", {
            "task_queue_id": stable_id("tsk", report_date, task["market_task_id"]),
            "task_type": task["task_type"],
            "target_agent_id": "market_coverage_intelligence_agent",
            "priority": task["priority"],
            "payload": task,
            "status": "queued",
            "created_at_utc": now_utc(),
        })
    append_market_record(root, "strategy_memory", {
        "memory_key": f"market_coverage_p0_{report_date}",
        "memory_type": "market_coverage",
        "title": f"{report_date} Market Coverage Intelligence",
        "summary": f"Generated {len(signals)} market signals, {len(hypotheses)} hypotheses, {len(plans)} plans and {len(tasks)} queued tasks.",
        "source": "market_coverage_intelligence",
        "run_date": report_date,
        "top_signals": [signal["summary"] for signal in signals[:5]],
    })


def build_market_coverage_report(
    report_date: str,
    segments: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    hypotheses: list[dict[str, Any]],
    plans: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
) -> str:
    tiktok_segments = [item for item in segments if "tiktok" in item["platform"].lower()]
    top_segments = segments[:5]
    seed_notice = "有训练种子，需补真实平台证据" if any(item["is_training_seed"] for item in segments) else "已使用现有采集记录"
    lines = [
        "# Market Coverage Intelligence P0 Report",
        "",
        f"Date: {report_date}",
        f"Data status: {seed_notice}",
        "",
        "## Boss Summary",
        "",
        f"- 今日生成 {len(signals)} 个市场信号、{len(hypotheses)} 个商业假设、{len(plans)} 个验证计划、{len(tasks)} 个采集任务。",
        f"- TikTok 相关细分机会 {len(tiktok_segments)} 个；视频脚本只看 TikTok / TikTok Shop / FastMoss / Kalodata，不用 Amazon 代替。",
        f"- 当前最高优先级：{top_segments[0]['platform']} / {top_segments[0]['segment']}，机会分 {top_segments[0]['opportunity_score']}。" if top_segments else "- 当前没有足够市场信号。",
        "",
        "## 1. 今日市场大盘变化",
        "",
        *bullet_lines(top_segments, lambda item: f"{item['platform']} {item['category']}：{item['segment']} velocity {item['velocity']}, score {item['opportunity_score']}"),
        "",
        "## 2. 今日细分类目变化",
        "",
        *bullet_lines(top_segments, lambda item: f"{item['segment']}：7日变化 {item['delta_7d']}, 30日变化 {item['delta_30d']}, 风险 {item['risk_score']}"),
        "",
        "## 3. 今日中腰部机会",
        "",
        *bullet_lines([item for item in segments if 50 <= float(item['avg_rank']) <= 500][:5], lambda item: f"{item['segment']}：平均排名 {item['avg_rank']}，适合先拆中腰部商品而不是只盯头部。"),
        "",
        "## 4. 今日长尾机会",
        "",
        *bullet_lines([item for item in segments if item["competition_density"] <= 0.78][:5], lambda item: f"{item['segment']}：关键词 {', '.join(item['keywords'][:4]) or item['segment']}，竞争密度 {item['competition_density']}。"),
        "",
        "## 5. 今日上涨关键词",
        "",
        *bullet_lines(top_segments, lambda item: f"{item['segment']}：{', '.join(item['keywords'][:5]) or item['segment']}"),
        "",
        "## 6. 今日上涨达人",
        "",
        *bullet_lines([item for item in top_segments if item["creators"]], lambda item: f"{item['segment']}：{', '.join(item['creators'][:5])}"),
        "",
        "## 7. 今日爆款视频框架",
        "",
        *bullet_lines(top_segments[:4], lambda item: f"{item['segment']}：{video_script_focus(item)}"),
        "",
        "## 8. 今日价格变化",
        "",
        *bullet_lines(top_segments, lambda item: f"{item['segment']}：参考均价 ${item['avg_price']}，利润潜力 {item['profit_potential']}。"),
        "",
        "## 9. 今日风险变化",
        "",
        *bullet_lines(top_segments, lambda item: f"{item['segment']}：风险 {item['risk_score']}，需重点看禁限售、侵权词、广告宣称和差评痛点。"),
        "",
        "## 10. 进入 AI Ecommerce Director 的 Signal",
        "",
        *bullet_lines(signals[:8], lambda item: f"{item['signal_type']} | {item['platform']} | {item['segment']} | score {item['opportunity_score']} | {item['recommended_next_step']}"),
        "",
        "## Next Action",
        "",
        "- 先补 TikTok Shop 买家入口、FastMoss、Kalodata 的真实商品/达人/视频证据。",
        "- 每个高分细分品至少拆 10 条视频：钩子、场景、运镜、字幕、CTA、评论购买意图。",
        "- 报告页只展示 Boss Summary 和异常机会；明细默认折叠。",
    ]
    return "\n".join(lines).strip() + "\n"


def write_outputs(
    root: Path,
    report_date: str,
    report: str,
    segments: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    hypotheses: list[dict[str, Any]],
    plans: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
) -> tuple[Path, Path]:
    output_dir = root / OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{MARKET_COVERAGE_REPORT_PREFIX}_{report_date}.md"
    json_path = output_dir / f"{MARKET_COVERAGE_REPORT_PREFIX}_{report_date}.json"
    report_path.write_text(report, encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "run_date": report_date,
                "segments": segments,
                "signals": signals,
                "hypotheses": hypotheses,
                "plans": plans,
                "tasks": tasks,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report_path, json_path


def append_market_record(root: Path, record_type: str, fields: dict[str, Any]) -> None:
    append_record(
        root,
        IntakeRecord(
            record_type=record_type,
            fields=fields,
            raw_text=json.dumps(fields, ensure_ascii=False),
            source="market_coverage_intelligence",
            confidence=float(fields.get("confidence_score") or fields.get("confidence") or 0.75),
            metadata={"generated_by": "market_coverage_intelligence_p0"},
        ),
    )


def score_opportunity(
    *,
    velocity: float,
    acceleration: float,
    profit_potential: float,
    content_replicability: float,
    creator_availability: float,
    keyword_fit: float,
    competition_density: float,
    risk_score: float,
    logistics_score: float,
) -> int:
    upside = (1 + max(0, velocity)) * (1 + max(0, acceleration) * 0.35)
    numerator = upside * profit_potential * content_replicability * creator_availability * keyword_fit * logistics_score
    denominator = max(0.18, competition_density * (0.7 + risk_score))
    raw = 42 * numerator / denominator
    return int(max(1, min(100, round(raw))))


def choose_signal_type(segment: dict[str, Any]) -> str:
    if segment["risk_score"] >= 0.45:
        return "risk_watch_growth"
    if segment["velocity"] >= 0.65 and segment["avg_rank"] >= 50:
        return "mid_rank_fast_growth"
    if segment["competition_density"] <= 0.62:
        return "long_tail_blue_ocean"
    return "category_growth"


def build_signal_summary(segment: dict[str, Any], signal_type: str) -> str:
    return f"{segment['platform']} {segment['segment']} generated {signal_type}, velocity {segment['velocity']}, score {segment['opportunity_score']}."


def recommended_signal_step(segment: dict[str, Any]) -> str:
    if "tiktok" in segment["platform"].lower():
        return "拆热视频和达人素材，再补商品卡/评论/价格证据"
    return "补平台榜单、Listing、价格和评论证据"


def video_script_focus(segment: dict[str, Any]) -> str:
    name = segment["segment"].lower()
    if "cleanser" in name or "toner" in name:
        return "0-2秒肤质痛点，2-6秒泡沫/质地近景，6-12秒使用前后，结尾评论区问题+优惠CTA。"
    if "melatonin" in name:
        return "0-2秒睡不着痛点，2-5秒夜间场景，5-10秒成分/口味，结尾避免夸张医疗宣称。"
    if "t-shirt" in name or "shirt" in name:
        return "0-2秒身份钩子，2-5秒上身版型，5-10秒场景穿搭，结尾礼物/限时折扣CTA。"
    if "screen" in name or "phone" in name:
        return "0-2秒摔屏/偷窥痛点，2-6秒安装过程，6-10秒强度演示，结尾套装优惠CTA。"
    if "jewelry" in name or "pendant" in name:
        return "0-2秒穿搭反差，2-6秒闪光细节，6-12秒套装搭配，结尾礼物场景CTA。"
    return "0-3秒强钩子，3-8秒产品证据，8-15秒场景和社证据，结尾CTA。"


def infer_painpoints(segment: dict[str, Any]) -> list[str]:
    name = segment["segment"].lower()
    if "cleanser" in name:
        return ["dry after wash", "sensitive skin irritation", "fake gentle claim", "small bottle"]
    if "melatonin" in name:
        return ["medical claim risk", "taste complaint", "morning grogginess", "dosage confusion"]
    if "shirt" in name:
        return ["shrink after wash", "thin fabric", "size mismatch", "print fading"]
    if "screen" in name or "phone" in name:
        return ["bubble installation", "bad fit", "weak privacy angle", "breaks too easily"]
    if "jewelry" in name:
        return ["tarnish", "stone falls out", "looks cheap", "wrong size"]
    return ["quality mismatch", "shipping delay", "unclear size", "price objection"]


def infer_category(product_name: str) -> str:
    name = product_name.lower()
    if any(word in name for word in ["cleanser", "toner", "cream", "serum"]):
        return "Beauty & Personal Care"
    if any(word in name for word in ["melatonin", "supplement", "gummy"]):
        return "Health"
    if any(word in name for word in ["shirt", "tee", "t-shirt"]):
        return "Fashion > T-Shirts"
    if any(word in name for word in ["protector", "charger", "phone"]):
        return "Electronics Accessories"
    if any(word in name for word in ["jewelry", "pendant", "chain"]):
        return "Jewelry"
    return "All Category Radar"


def infer_segment(product_name: str, category: str) -> str:
    name = product_name.strip()
    if name:
        words = name.split()
        return " ".join(words[:4]).title()
    return category.split(">")[-1].strip() or "Unknown Segment"


def infer_price(product_name: str, category: str) -> float:
    text = f"{product_name} {category}".lower()
    if "jewelry" in text or "pendant" in text:
        return 59.99
    if "shirt" in text or "tee" in text:
        return 29.99
    if "supplement" in text or "melatonin" in text:
        return 19.99
    if "protector" in text:
        return 12.99
    return 14.99


def infer_risk_score(product_name: str, category: str) -> float:
    text = f"{product_name} {category}".lower()
    if any(word in text for word in ["disney", "nike", "nfl", "barbie", "stanley"]):
        return 0.88
    if any(word in text for word in ["supplement", "melatonin", "health", "medical"]):
        return 0.46
    if any(word in text for word in ["jewelry", "moissanite"]):
        return 0.38
    return 0.22


def infer_competition_density(avg_rank: float, sample_count: int, platform: str) -> float:
    rank_pressure = 1 / max(1.0, log1p(max(1.0, avg_rank)))
    sample_pressure = min(0.28, sample_count * 0.04)
    platform_pressure = 0.08 if "amazon" in platform.lower() else 0.0
    return max(0.18, min(0.92, 0.74 - rank_pressure + sample_pressure + platform_pressure))


def infer_content_replicability(category: str, segment: str) -> float:
    text = f"{category} {segment}".lower()
    if any(word in text for word in ["beauty", "cleanser", "shirt", "protector", "jewelry"]):
        return 0.86
    if any(word in text for word in ["health", "supplement"]):
        return 0.62
    return 0.72


def infer_creator_availability(rows: list[dict[str, Any]]) -> float:
    creators = {row.get("creator_handle") for row in rows if row.get("creator_handle")}
    return min(0.92, 0.58 + len(creators) * 0.12)


def infer_profit_potential(avg_price: float, category: str) -> float:
    base = 0.45 + min(0.35, avg_price / 180)
    if "jewelry" in category.lower():
        base += 0.16
    if "fashion" in category.lower():
        base += 0.08
    return round(max(0.35, min(0.94, base)), 4)


def is_weak_or_verification_item(item: dict[str, Any]) -> bool:
    text = " ".join(str(item.get(key) or "") for key in ["product_name", "source_url", "raw_text"]).lower()
    return any(pattern in text for pattern in ["security check", "verify to continue", "captcha"]) or item["category"].lower() in {"", "unknown"}


def first_text(fields: dict[str, Any], keys: list[str], default: str = "") -> str:
    for key in keys:
        value = fields.get(key)
        if value not in (None, ""):
            if isinstance(value, list):
                clean = [str(item).strip() for item in value if str(item).strip()]
                if clean:
                    return ", ".join(clean)
            else:
                text = str(value).strip()
                if text:
                    return text
    return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return float(default)
        if isinstance(value, str):
            cleaned = value.replace("$", "").replace(",", "").strip()
            return float(cleaned)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "_".join(str(part).strip().lower().replace(" ", "_").replace("/", "_") for part in parts if str(part).strip())
    safe = "".join(char if char.isalnum() or char in "_-" else "_" for char in raw)
    while "__" in safe:
        safe = safe.replace("__", "_")
    return f"{prefix}_{safe[:120]}"


def pick(payload: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: payload[key] for key in keys if key in payload}


def bullet_lines(items: list[dict[str, Any]], formatter: Any) -> list[str]:
    if not items:
        return ["- 暂无足够证据。"]
    return [f"- {formatter(item)}" for item in items]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()
