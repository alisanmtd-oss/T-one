from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .product_targets import add_product_target, load_product_targets, normalize_list
from .scoring import score_record
from .storage import append_record, read_records, write_report
from .tk_case_learning import seed_tk_case_learning_pool, tk_case_learning_summary
from .types import IntakeRecord


PILOT_SELLERS_CONFIG = Path("config") / "pilot_sellers.json"


@dataclass(slots=True)
class PilotLaunchResult:
    seller: dict[str, Any]
    records_created: int
    product_targets_created: int
    report_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "seller": self.seller,
            "records_created": self.records_created,
            "product_targets_created": self.product_targets_created,
            "report_path": str(self.report_path),
        }


def load_pilot_sellers(root: Path) -> dict[str, Any]:
    path = root / PILOT_SELLERS_CONFIG
    if not path.exists():
        return {"sellers": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"sellers": []}
    payload.setdefault("sellers", [])
    return payload


def save_pilot_sellers(root: Path, payload: dict[str, Any]) -> Path:
    path = root / PILOT_SELLERS_CONFIG
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def add_pilot_seller(root: Path, payload: dict[str, Any]) -> PilotLaunchResult:
    config = load_pilot_sellers(root)
    seller = normalize_seller_payload(payload)
    config.setdefault("sellers", []).append(seller)
    save_pilot_sellers(root, config)

    records_created = 0
    product_targets_created = 0
    records_created += append_store_profile(root, seller)
    for product in seller["products"]:
        add_product_target(
            root,
            {
                "name": product,
                "product_family": product,
                "keywords": "\n".join([product, *seller["keywords"]]),
                "competitor_links": "\n".join(seller["competitor_links"]),
                "platforms": "\n".join(seller["platforms"]),
                "market": ", ".join(seller["countries"]),
                "notes": f"Pilot seller: {seller['seller_name']} / {seller['brand_name']}",
            },
        )
        product_targets_created += 1
    for url in seller["competitor_links"]:
        records_created += append_link_record(root, seller, url, "hot_link")
    for url in seller["video_links"]:
        records_created += append_link_record(root, seller, url, "viral_content_signal")

    if int(payload.get("seed_case_jobs") or 0) > 0:
        seed_tk_case_learning_pool(root, int(payload.get("seed_case_jobs") or 1000))

    report = render_pilot_report(root, seller)
    report_path = write_report(root, f"pilot_launch_{date.today().isoformat()}_{seller['id']}", report)
    return PilotLaunchResult(seller, records_created, product_targets_created, report_path)


def normalize_seller_payload(payload: dict[str, Any]) -> dict[str, Any]:
    seller_name = str(payload.get("seller_name") or payload.get("sellerName") or "").strip()
    brand_name = str(payload.get("brand_name") or payload.get("brandName") or seller_name).strip()
    if not seller_name:
        raise ValueError("seller_name is required.")
    countries = normalize_list(payload.get("countries")) or ["US"]
    platforms = normalize_list(payload.get("platforms")) or ["TikTok Shop", "Amazon"]
    stores = normalize_list(payload.get("stores"))
    products = normalize_list(payload.get("products")) or normalize_list(payload.get("product_keywords"))
    keywords = normalize_list(payload.get("keywords")) or products
    return {
        "id": str(payload.get("id") or f"pilot-{uuid4().hex[:10]}"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "seller_name": seller_name,
        "brand_name": brand_name,
        "contact_note": str(payload.get("contact_note") or payload.get("contactNote") or "").strip(),
        "countries": countries,
        "platforms": platforms,
        "stores": stores,
        "products": products,
        "keywords": keywords,
        "competitor_links": normalize_list(payload.get("competitor_links")),
        "video_links": normalize_list(payload.get("video_links")),
        "notes": str(payload.get("notes") or "").strip(),
        "automation_level": "L0-L2 by default; L3 only after human confirmation",
        "status": "pilot_ready" if products or stores or normalize_list(payload.get("competitor_links")) else "needs_data",
    }


def append_store_profile(root: Path, seller: dict[str, Any]) -> int:
    fields = {
        "seller_name": seller["seller_name"],
        "brand_name": seller["brand_name"],
        "store_name": ", ".join(seller["stores"]),
        "marketplace": ", ".join(seller["platforms"]),
        "country_code": ", ".join(seller["countries"]),
        "product_focus": ", ".join(seller["products"]),
        "pilot_seller_id": seller["id"],
        "automation_level": seller["automation_level"],
        "notes": seller["notes"],
    }
    score, notes = score_record("store_profile", fields)
    append_record(
        root,
        IntakeRecord(
            record_type="store_profile",
            fields=fields,
            raw_text=json.dumps(seller, ensure_ascii=False),
            source="pilot_launch",
            score=score,
            director_notes=notes,
            metadata={"pilot_seller_id": seller["id"]},
        ),
    )
    return 1


def append_link_record(root: Path, seller: dict[str, Any], url: str, record_type: str) -> int:
    fields = {
        "url": url,
        "video_url": url if record_type == "viral_content_signal" else "",
        "source_platform": infer_platform_from_url(url),
        "marketplace": infer_platform_from_url(url),
        "seller_name": seller["seller_name"],
        "brand_name": seller["brand_name"],
        "product_theme": ", ".join(seller["products"]),
        "pilot_seller_id": seller["id"],
        "content_owner": "competitor" if record_type == "viral_content_signal" else "",
        "analysis_task": "pilot_seller_competitor_or_viral_case_review",
    }
    score, notes = score_record(record_type, fields)
    append_record(
        root,
        IntakeRecord(
            record_type=record_type,
            fields=fields,
            raw_text=json.dumps({"url": url, "seller": seller["id"]}, ensure_ascii=False),
            source="pilot_launch",
            score=score,
            director_notes=notes,
            metadata={"pilot_seller_id": seller["id"]},
        ),
    )
    return 1


def infer_platform_from_url(url: str) -> str:
    lowered = url.lower()
    if "tiktok" in lowered:
        return "TikTok"
    if "amazon" in lowered:
        return "Amazon"
    if "walmart" in lowered:
        return "Walmart"
    if "etsy" in lowered:
        return "Etsy"
    if "shopify" in lowered:
        return "Shopify"
    if "shein" in lowered:
        return "SHEIN"
    return "Web"


def build_pilot_readiness(root: Path) -> dict[str, Any]:
    sellers = load_pilot_sellers(root).get("sellers", [])
    targets = load_product_targets(root).get("targets", [])
    action_queue = latest_action_queue(root)
    summary = {
        "pilotSellers": len(sellers),
        "storeProfiles": len(read_records(root, "store_profile")),
        "productTargets": len(targets),
        "competitorLinks": len(read_records(root, "hot_link")),
        "viralCases": len(read_records(root, "viral_content_signal")),
        "videoBreakdowns": len(read_records(root, "video_breakdown")),
        "productScripts": len(read_records(root, "video_script")),
        "salesSnapshots": len(read_records(root, "store_metric_snapshot")),
        "strategyMemories": len(read_records(root, "strategy_memory")),
        "pendingApprovals": len([item for item in action_queue if item.get("requires_confirmation")]),
        "tkCaseLearning": tk_case_learning_summary(root),
    }
    blockers = []
    if summary["pilotSellers"] == 0:
        blockers.append("先添加至少 1 个试用卖家/品牌。")
    if summary["productTargets"] == 0:
        blockers.append("至少设置 1 个监控商品或商品关键词。")
    if summary["viralCases"] == 0 and summary["competitorLinks"] == 0:
        blockers.append("至少投喂竞品链接或 TK 视频链接，才能生成内容策略。")
    if summary["salesSnapshots"] == 0:
        blockers.append("还没有销售/财务报表，经营大屏只能显示内容/策略，不能看真实 GMV。")
    return {
        "summary": summary,
        "readyForPilot": len(blockers) <= 1 and summary["pilotSellers"] > 0,
        "blockers": blockers,
        "sellers": sellers[-48:],
        "latestActionQueue": action_queue[:20],
    }


def latest_action_queue(root: Path) -> list[dict[str, Any]]:
    output_dir = root / "outputs"
    paths = sorted(output_dir.glob("action_queue_*.json"), reverse=True)
    if not paths:
        return []
    try:
        payload = json.loads(paths[0].read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def render_pilot_report(root: Path, seller: dict[str, Any]) -> str:
    readiness = build_pilot_readiness(root)
    lines = [
        "# Pilot Seller Launch Report",
        "",
        f"Seller: {seller['seller_name']}",
        f"Brand: {seller['brand_name']}",
        f"Countries: {', '.join(seller['countries'])}",
        f"Platforms: {', '.join(seller['platforms'])}",
        f"Stores: {', '.join(seller['stores'])}",
        f"Products: {', '.join(seller['products'])}",
        "",
        "## Readiness",
        "",
        f"- Ready for pilot: {readiness['readyForPilot']}",
        *[f"- Blocker: {item}" for item in readiness["blockers"]],
        "",
        "## Safety",
        "",
        "- AI may observe, analyze, draft and queue.",
        "- Publishing, pricing, discounts, creator contact, refunds, app authorization and payments require human approval.",
    ]
    return "\n".join(lines) + "\n"
