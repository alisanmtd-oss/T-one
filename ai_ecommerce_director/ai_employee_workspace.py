from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from .storage import append_record, read_records
from .tk_overnight import build_tk_snapshot
from .types import IntakeRecord


EMPLOYEES: list[dict[str, Any]] = [
    {
        "agent_id": "ai_ecommerce_director",
        "name": "AI Ecommerce Director",
        "mission": "Own the boss summary, category priority, go/no-go decision and next 72h plan.",
        "views": ["platform_ranking_signal", "viral_content_signal", "video_breakdown", "creator_spike_event", "review_insight", "strategy_memory"],
    },
    {
        "agent_id": "product_selection_analyst",
        "name": "AI Product Selection Analyst",
        "mission": "Find category opportunities from TK-first evidence, then use Amazon/Etsy/Walmart/SHEIN only as supplement.",
        "views": ["platform_ranking_signal", "collection_job", "review_insight", "product_case", "failed_case"],
    },
    {
        "agent_id": "tk_viral_content_analyst",
        "name": "AI TikTok Viral Content Analyst",
        "mission": "Break down real TK videos into hook, shot timeline, camera movement, edit rhythm, scene, emotion, CTA and why viral.",
        "views": ["viral_content_signal", "video_breakdown", "video_script", "creative_inspiration", "video_comment_intelligence"],
    },
    {
        "agent_id": "influencer_hunter",
        "name": "AI Influencer Hunter",
        "mission": "Build private creator cards with niche, average views, engagement quality, contact route, sample cost and ROI expectation.",
        "views": ["creator_spike_event", "influencer_cooperation", "influencer_collab", "collection_job"],
    },
    {
        "agent_id": "listing_builder",
        "name": "AI Listing Builder",
        "mission": "Draft title, bullets, tags, price angle and image suggestions only after evidence and risk gates are clear.",
        "views": ["platform_ranking_signal", "listing_snapshot", "review_insight", "keyword", "strategy_memory"],
    },
    {
        "agent_id": "risk_director",
        "name": "AI Risk Director",
        "mission": "Scan IP, prohibited claims, medical wording, counterfeit risk, platform red lines and public/private listing decision.",
        "views": ["ip_image_risk", "compliance_term", "banned_term", "ip_registry", "platform_rule_snapshot", "review_insight"],
    },
    {
        "agent_id": "data_reviewer",
        "name": "AI Data Reviewer",
        "mission": "Reject empty pages, loading pages, generic homepages, mismatched products and duplicate rows before they enter reports.",
        "views": ["collection_job", "platform_ranking_signal", "viral_content_signal", "source_document", "evidence_claim"],
    },
    {
        "agent_id": "finance_budget_analyst",
        "name": "AI Finance & Budget Analyst",
        "mission": "Estimate budget, breakeven ROI, payback window, stop-loss and scale rules from store and market evidence.",
        "views": ["store_metric_snapshot", "finance_transaction", "experiment_metric", "budget_plan", "action_outcome"],
    },
]


CATEGORY_ROTATION: list[dict[str, Any]] = [
    {"category": "Beauty & Personal Care", "queries": ["amino acid cleanser", "facial serum", "hair growth oil"]},
    {"category": "Health & Supplements", "queries": ["melatonin supplement", "magnesium complex", "creatine gummies"]},
    {"category": "Fashion Apparel", "queries": ["washed t shirt", "oversized hoodie", "shapewear bodysuit"]},
    {"category": "Shoes & Accessories", "queries": ["cloud slides", "compression socks", "travel backpack"]},
    {"category": "Jewelry & Streetwear Accessories", "queries": ["hip hop necklace", "moissanite chain", "custom pendant"]},
    {"category": "Phone Accessories", "queries": ["phone screen protector", "magnetic phone case", "portable charger"]},
    {"category": "Home & Kitchen", "queries": ["ice maker", "portable blender", "organizer rack"]},
    {"category": "Pet Supplies", "queries": ["dog grooming brush", "cat water fountain", "pet hair remover"]},
    {"category": "Sports & Outdoors", "queries": ["pickleball paddle", "camping light", "fitness resistance bands"]},
    {"category": "Baby & Kids", "queries": ["baby bottle warmer", "kids educational toy", "toddler shoes"]},
    {"category": "Automotive Accessories", "queries": ["car phone holder", "portable tire inflator", "car vacuum"]},
    {"category": "Tools & Small Appliances", "queries": ["mini chainsaw", "laser level", "cordless handheld vacuum"]},
]


@dataclass(slots=True)
class EmployeeWorkspaceResult:
    run_date: str
    workspace_count: int
    proactive_task_count: int
    collection_job_count: int
    word_bank_count: int
    distillation_pack_count: int
    report: str
    report_path: Path
    json_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "workspace_count": self.workspace_count,
            "proactive_task_count": self.proactive_task_count,
            "collection_job_count": self.collection_job_count,
            "word_bank_count": self.word_bank_count,
            "distillation_pack_count": self.distillation_pack_count,
            "report": self.report,
            "report_path": str(self.report_path),
            "json_path": str(self.json_path),
        }


def run_ai_employee_workspace(root: Path, run_date: str | None = None, *, seed_collection_jobs: bool = True) -> EmployeeWorkspaceResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    snapshot = build_tk_snapshot(root)
    data_summary = build_data_summary(root, snapshot)
    workspaces = [build_workspace_record(employee, data_summary, snapshot, report_date, now) for employee in EMPLOYEES]
    for record in workspaces:
        append_record(root, record)
    tasks = [build_proactive_task(employee, data_summary, snapshot, report_date, now) for employee in EMPLOYEES]
    for record in tasks:
        append_record(root, record)
    collection_jobs = build_category_collection_jobs(report_date, now) if seed_collection_jobs else []
    for record in collection_jobs:
        append_record(root, record)
    word_bank_records = build_word_bank_records(report_date, now)
    for record in word_bank_records:
        append_record(root, record)
    distillation_packs = build_distillation_packs(report_date, now, data_summary, snapshot)
    for record in distillation_packs:
        append_record(root, record)
    report = build_employee_workspace_report(report_date, data_summary, workspaces, tasks, collection_jobs, word_bank_records, distillation_packs)
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"ai_employee_workspace_{report_date}.md"
    json_path = output_dir / f"ai_employee_workspace_{report_date}.json"
    report_path.write_text(report, encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "run_date": report_date,
                "data_summary": data_summary,
                "workspaces": [record.to_dict() for record in workspaces],
                "proactive_tasks": [record.to_dict() for record in tasks],
                "collection_jobs": [record.to_dict() for record in collection_jobs],
                "word_bank_records": [record.to_dict() for record in word_bank_records],
                "distillation_packs": [record.to_dict() for record in distillation_packs],
                "report_path": str(report_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return EmployeeWorkspaceResult(
        report_date,
        len(workspaces),
        len(tasks),
        len(collection_jobs),
        len(word_bank_records),
        len(distillation_packs),
        report,
        report_path,
        json_path,
    )


def build_data_summary(root: Path, snapshot: dict[str, Any]) -> dict[str, Any]:
    records = read_records(root)
    by_type: dict[str, int] = {}
    by_platform: dict[str, int] = {}
    by_category: dict[str, int] = {}
    latest_links: list[dict[str, str]] = []
    for record in records:
        by_type[record.record_type] = by_type.get(record.record_type, 0) + 1
        fields = record.fields or {}
        platform = str(fields.get("source_platform") or fields.get("marketplace") or fields.get("platform") or "").strip()
        category = str(fields.get("category") or fields.get("category_path") or fields.get("data_category") or fields.get("product_category") or "").strip()
        if platform:
            by_platform[platform] = by_platform.get(platform, 0) + 1
        if category:
            by_category[category] = by_category.get(category, 0) + 1
        url = str(fields.get("video_url") or fields.get("product_url") or fields.get("url") or "").strip()
        if url and len(latest_links) < 12:
            latest_links.append({"type": record.record_type, "platform": platform, "title": short_text(fields.get("product_name") or fields.get("product_title") or fields.get("title") or url, 90), "url": url})
    return {
        "record_count": len(records),
        "by_type": dict(sorted(by_type.items(), key=lambda item: item[1], reverse=True)[:30]),
        "by_platform": dict(sorted(by_platform.items(), key=lambda item: item[1], reverse=True)[:20]),
        "by_category": dict(sorted(by_category.items(), key=lambda item: item[1], reverse=True)[:20]),
        "tk_snapshot": snapshot,
        "full_category_rotation": [item["category"] for item in CATEGORY_ROTATION],
        "latest_links": latest_links,
        "safety": {
            "allowed_now": ["read local Data Lake", "create draft analysis", "create collection_job queue", "write report", "write strategy memory after evidence review"],
            "blocked_without_human": ["publish product", "change price", "run ads", "refund", "ship order", "contact creator", "authorize app", "upload public video"],
            "compliant_collection_order": [
                "official API or partner API",
                "authorized export / CSV / report download",
                "logged-in visible page capture from the user's existing session",
                "public page metadata where allowed",
                "manual verification wait; never bypass slider/login/robots restrictions",
            ],
        },
    }


def build_workspace_record(employee: dict[str, Any], data_summary: dict[str, Any], snapshot: dict[str, Any], run_date: str, now: str) -> IntakeRecord:
    agent_id = str(employee["agent_id"])
    fields = {
        "workspace_id": stable_id("workspace_", run_date, agent_id),
        "run_date": run_date,
        "agent_id": agent_id,
        "employee": employee["name"],
        "mission": employee["mission"],
        "accessible_record_types": employee["views"],
        "visible_data_summary": filtered_summary_for_employee(employee, data_summary),
        "tk_snapshot": snapshot,
        "must_be_proactive": True,
        "allowed_actions": data_summary["safety"]["allowed_now"],
        "blocked_actions": data_summary["safety"]["blocked_without_human"],
        "compliant_collection_order": data_summary["safety"].get("compliant_collection_order", []),
        "created_at_utc": now,
    }
    return IntakeRecord(
        record_type="agent_workspace_snapshot",
        source="ai_employee_workspace",
        raw_text=json.dumps(fields, ensure_ascii=False),
        fields=fields,
        score={"priority": 88, "employee_workspace": True},
        director_notes=["AI employee data-access snapshot. Employees can read/analyze and queue collection, but external execution remains gated."],
        confidence=0.9,
    )


def filtered_summary_for_employee(employee: dict[str, Any], data_summary: dict[str, Any]) -> dict[str, Any]:
    views = set(employee.get("views") or [])
    by_type = data_summary.get("by_type") if isinstance(data_summary.get("by_type"), dict) else {}
    return {
        "record_count": data_summary.get("record_count", 0),
        "relevant_type_counts": {key: by_type.get(key, 0) for key in views},
        "tk_snapshot": data_summary.get("tk_snapshot", {}),
        "top_platforms": data_summary.get("by_platform", {}),
        "top_categories": data_summary.get("by_category", {}),
        "latest_links": data_summary.get("latest_links", [])[:5],
    }


def build_proactive_task(employee: dict[str, Any], data_summary: dict[str, Any], snapshot: dict[str, Any], run_date: str, now: str) -> IntakeRecord:
    agent_id = str(employee["agent_id"])
    task_id = stable_id("employee_task_", run_date, agent_id, str(snapshot.get("real_tk_records", 0)), str(snapshot.get("viral_records", 0)))
    title, expected = task_spec_for_employee(agent_id, snapshot)
    fields = {
        "task_queue_id": task_id,
        "task_type": "ai_employee_proactive_data_work",
        "target_agent_id": employee["name"],
        "agent_id": agent_id,
        "task_title": title,
        "task_description": employee["mission"],
        "expected_output": expected,
        "status": "queued",
        "requires_confirmation": False,
        "automation_level": "L0-L2_read_analyze_queue_only",
        "data_workspace_id": stable_id("workspace_", run_date, agent_id),
        "data_views": employee["views"],
        "full_category_required": True,
        "tiktok_weight": 0.8,
        "all_platform_weight": 0.2,
        "safety_gate": "May create analysis and collection queues only. Real store/platform actions need human confirmation.",
        "created_at_utc": now,
        "priority": task_priority(agent_id, snapshot),
    }
    return IntakeRecord(
        record_type="task_queue",
        source="ai_employee_workspace.proactive_task",
        raw_text=json.dumps(fields, ensure_ascii=False),
        fields=fields,
        score={"priority": fields["priority"], "employee_proactive": True},
        director_notes=["Proactive task generated so AI employees do not wait for the owner to assign every step."],
        confidence=0.9,
    )


def task_spec_for_employee(agent_id: str, snapshot: dict[str, Any]) -> tuple[str, str]:
    if agent_id == "tk_viral_content_analyst":
        return (
            "主动补齐 TK 视频拆解",
            "10条真实TK视频卡片：链接、商品、达人、播放/评论、0-3秒钩子、运镜剪辑、场景、CTA、为什么能火、店铺自发脚本、达人脚本。",
        )
    if agent_id == "product_selection_analyst":
        return (
            "主动做全品类 TK-first 选品短报",
            "按12个大类轮训，每类给1个候选品：TK证据、生命周期、竞争强度、风险、预算建议、72小时测试动作。",
        )
    if agent_id == "influencer_hunter":
        return ("主动补达人库", "30个达人A/B/C分级：赛道、均播、互动、粉丝质量、联系方式路径、报价/样品成本、预估CPA、合作风险。")
    if agent_id == "risk_director":
        return ("主动做全平台风险扫描", "对监控商品和视频输出 clear/borderline/confirmed_ip/prohibited，附证据和允许公开/同步/私人定制判断。")
    if agent_id == "data_reviewer":
        return ("主动清洗错误数据", "列出20条坏数据：空页、加载页、首页、错品、重复、Amazon误混TK；给出隔离/保留/补采决定。")
    if agent_id == "finance_budget_analyst":
        return ("主动生成预算与止损建议", "按品类/平台给测品预算、保本ROI、CPA上限、回本周期、止损线和扩量线。")
    if agent_id == "listing_builder":
        return ("主动生成草稿型Listing建议", "只对证据合格商品给标题、五点、价格带、主图方向、标签；不得发布或改线上Listing。")
    return ("主动生成老板短报", "一页结论：今天机会、证据等级、员工分工、风险、明天Top 5任务；只保留重点，不堆长文。")


def task_priority(agent_id: str, snapshot: dict[str, Any]) -> int:
    base = 75
    if agent_id == "tk_viral_content_analyst" and int(snapshot.get("viral_records") or 0) < 30:
        return 98
    if agent_id == "data_reviewer" and int(snapshot.get("weak_tk_records") or 0) > int(snapshot.get("real_tk_records") or 0):
        return 96
    if agent_id == "product_selection_analyst":
        return 94
    if agent_id == "influencer_hunter" and int(snapshot.get("creator_records") or 0) < 30:
        return 92
    return base


def build_category_collection_jobs(run_date: str, now: str) -> list[IntakeRecord]:
    jobs: list[IntakeRecord] = []
    for item in CATEGORY_ROTATION:
        category = str(item["category"])
        query = str(item["queries"][0])
        for source_name, url in platform_search_urls(query).items():
            fields = {
                "collection_job_id": stable_id("col_agent_", run_date, source_name, category, query),
                "run_date": run_date,
                "source_platform": source_name,
                "marketplace": source_name,
                "platform": source_name,
                "data_category": "tk_full_category_training" if source_name in {"FastMoss", "Kalodata", "TikTok Shop Buyer"} else "all_platform_supplement",
                "category_focus": category,
                "keyword": query,
                "search_keyword": query,
                "url": url,
                "source_status": "pending_collection",
                "status": "queued",
                "assigned_agent": "AI Product Selection Analyst" if source_name != "TikTok Shop Buyer" else "AI TikTok Viral Content Analyst",
                "requires_visible_capture": source_name in {"FastMoss", "Kalodata", "TikTok Shop Buyer"},
                "collection_policy": "Use API/export first when available; otherwise use logged-in visible capture from existing user session. Do not bypass verification.",
                "keep_open_on_gate": True,
                "keep_open_after_run": True,
                "created_at_utc": now,
            }
            jobs.append(
                IntakeRecord(
                    record_type="collection_job",
                    source="ai_employee_workspace.category_collection",
                    raw_text=json.dumps(fields, ensure_ascii=False),
                    fields=fields,
                    score={"priority": 88, "tk_first": source_name in {"FastMoss", "Kalodata", "TikTok Shop Buyer"}, "full_category_training": True},
                    director_notes=["Queued by AI employee workspace. Collect category evidence; do not count empty pages as evidence."],
                    confidence=0.86,
                )
            )
    return jobs


def build_word_bank_records(run_date: str, now: str) -> list[IntakeRecord]:
    records: list[IntakeRecord] = []
    for term in risk_terms():
        fields = {
            "banned_term_id": stable_id("bt_", term["term"], term["risk_type"], term["platform"], term["country"]),
            "normalized_term": term["term"].lower(),
            "display_term": term["term"],
            "language": "en",
            "platform": term["platform"],
            "country": term["country"],
            "risk_type": term["risk_type"],
            "risk_level": term["risk_level"],
            "policy": "Learn for detection only. Do not use in public listing, ad copy, hashtags or scripts unless authorization is verified.",
            "created_at_utc": now,
        }
        records.append(
            IntakeRecord(
                record_type="banned_term",
                source="ai_employee_workspace.word_bank",
                raw_text=json.dumps(fields, ensure_ascii=False),
                fields=fields,
                score={"priority": 95, "risk_term": True},
                director_notes=["Risk/IP term added to detection-only word bank."],
                confidence=0.86,
            )
        )
    for item in keyword_terms():
        fields = {
            "keyword_id": stable_id("kw_", item["keyword"], item["keyword_type"], item["category"]),
            "keyword_key": stable_id("kwkey_", item["keyword"], item["keyword_type"], item["category"]),
            "keyword": item["keyword"],
            "keyword_type": item["keyword_type"],
            "category": item["category"],
            "source_platform": item["source_platform"],
            "verification_status": item["verification_status"],
            "use_case": item["use_case"],
            "created_at_utc": now,
        }
        records.append(
            IntakeRecord(
                record_type="keyword_intelligence",
                source="ai_employee_workspace.word_bank",
                raw_text=json.dumps(fields, ensure_ascii=False),
                fields=fields,
                score={"priority": item["priority"], "word_bank": True},
                director_notes=["Keyword added to the commerce word bank. Blue-ocean and hotspot terms require platform evidence before execution."],
                confidence=0.78 if item["verification_status"] == "candidate_unverified" else 0.86,
            )
        )
    for item in hotspot_watch_jobs(run_date, now):
        records.append(item)
    return records


def risk_terms() -> list[dict[str, str]]:
    brand_terms = [
        "Disney",
        "Nike",
        "Barbie",
        "Carhartt",
        "Gucci",
        "Louis Vuitton",
        "Chanel",
        "Rolex",
        "Pokemon",
        "Marvel",
        "Star Wars",
        "NFL",
        "NBA",
        "Stanley",
        "Stanley Cup",
    ]
    medical_terms = ["cure", "treat disease", "guaranteed results", "FDA approved", "clinically proven cure"]
    return [
        {"term": term, "risk_type": "ip_trademark_watch", "risk_level": "high", "platform": "all", "country": "US"}
        for term in brand_terms
    ] + [
        {"term": term, "risk_type": "medical_claim_watch", "risk_level": "high", "platform": "all", "country": "US"}
        for term in medical_terms
    ]


def keyword_terms() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in CATEGORY_ROTATION:
        category = str(item["category"])
        for query in item["queries"]:
            rows.append(keyword_row(query, "seed_keyword", category, "product search seed", 82, "needs_platform_evidence"))
            rows.append(keyword_row(f"{query} TikTok shop", "long_tail", category, "TK buyer-side search and video matching", 84, "candidate_unverified"))
            rows.append(keyword_row(f"{query} before and after", "content_hook", category, "video hook and proof scene", 80, "candidate_unverified"))
            rows.append(keyword_row(f"{query} review", "review_pain_point", category, "review mining and objection analysis", 78, "candidate_unverified"))
            rows.append(keyword_row(f"{query} under 30", "blue_ocean_candidate", category, "low-ticket test angle to validate", 76, "candidate_unverified"))
    hotspot_terms = [
        ("TikTok made me buy it", "hotspot_phrase", "All Categories"),
        ("GRWM", "hotspot_phrase", "Beauty & Fashion"),
        ("before after", "hotspot_phrase", "Beauty & Personal Care"),
        ("Amazon finds", "hotspot_phrase", "All Categories"),
        ("gift for dad", "seasonal_keyword", "Gifts"),
        ("summer travel essentials", "seasonal_keyword", "Travel & Accessories"),
    ]
    for keyword, keyword_type, category in hotspot_terms:
        rows.append(keyword_row(keyword, keyword_type, category, "hotspot monitoring and script inspiration", 86, "candidate_unverified"))
    return rows


def keyword_row(keyword: str, keyword_type: str, category: str, use_case: str, priority: int, verification_status: str) -> dict[str, Any]:
    return {
        "keyword": keyword,
        "keyword_type": keyword_type,
        "category": category,
        "source_platform": "ai_employee_workspace",
        "use_case": use_case,
        "priority": priority,
        "verification_status": verification_status,
    }


def hotspot_watch_jobs(run_date: str, now: str) -> list[IntakeRecord]:
    jobs: list[IntakeRecord] = []
    for source_name, url in {
        "TikTok Creative Center": "https://ads.tiktok.com/business/creativecenter/",
        "Google Trends": "https://trends.google.com/trends/",
        "YouTube Trending": "https://www.youtube.com/feed/trending",
        "Reddit Product Signals": "https://www.reddit.com/search/?q=tiktok%20shop%20made%20me%20buy%20it",
    }.items():
        fields = {
            "collection_job_id": stable_id("hotspot_", run_date, source_name),
            "run_date": run_date,
            "source_platform": source_name,
            "marketplace": source_name,
            "data_category": "network_hotspot_watch",
            "keyword": "product trend hotspot",
            "url": url,
            "source_status": "pending_research",
            "status": "queued",
            "assigned_agent": "AI Product Selection Analyst",
            "requires_visible_capture": True,
            "keep_open_on_gate": True,
            "created_at_utc": now,
        }
        jobs.append(
            IntakeRecord(
                record_type="collection_job",
                source="ai_employee_workspace.hotspot_watch",
                raw_text=json.dumps(fields, ensure_ascii=False),
                fields=fields,
                score={"priority": 82, "hotspot_watch": True},
                director_notes=["Network hotspot watch job. Use only allowed/public or logged-in visible capture; validate before using for products."],
                confidence=0.82,
            )
        )
    return jobs


def build_distillation_packs(run_date: str, now: str, data_summary: dict[str, Any], snapshot: dict[str, Any]) -> list[IntakeRecord]:
    packs: list[IntakeRecord] = []
    global_rules = [
        "TK/TikTok evidence has priority over Amazon. Amazon is supplemental, not a replacement.",
        "Empty pages, loading pages, tool homepages, mismatched products and duplicate rows are not market evidence.",
        "Video analysis must include hook, shot timeline, camera movement, edit rhythm, scene, emotion, CTA, comment signal and replication plan.",
        "Full-category training is mandatory: beauty, health, apparel, shoes, jewelry, phone accessories, home, pet, outdoor, baby, automotive, tools.",
        "Risk/IP terms are detection-only. Do not use protected brands, celebrities, teams, characters or medical-cure claims in public execution.",
        "External actions stay gated: no publish, ad spend, price change, creator contact, refund, shipment, authorization or public video upload without approval.",
    ]
    for employee in EMPLOYEES:
        fields = {
            "distillation_pack_id": stable_id("distill_", run_date, employee["agent_id"]),
            "run_date": run_date,
            "agent_id": employee["agent_id"],
            "employee": employee["name"],
            "mission": employee["mission"],
            "global_rules": global_rules,
            "role_rules": role_distillation_rules(str(employee["agent_id"])),
            "required_inputs": employee["views"],
            "current_tk_snapshot": snapshot,
            "category_rotation": data_summary.get("full_category_rotation", []),
            "word_bank_policy": {
                "risk_terms": "detect_only",
                "seed_keywords": "allowed_for_research",
                "long_tail_keywords": "validate_before_listing",
                "blue_ocean_terms": "candidate_until_platform_evidence",
                "hotspot_terms": "watch_and_verify_before_use",
            },
            "collection_policy": data_summary.get("safety", {}).get("compliant_collection_order", []),
            "created_at_utc": now,
        }
        packs.append(
            IntakeRecord(
                record_type="agent_distillation_pack",
                source="ai_employee_workspace.distillation",
                raw_text=json.dumps(fields, ensure_ascii=False),
                fields=fields,
                score={"priority": 96, "distillation": True},
                director_notes=["Role-specific distillation pack for AI employee training."],
                confidence=0.92,
            )
        )
    return packs


def role_distillation_rules(agent_id: str) -> list[str]:
    rules = {
        "tk_viral_content_analyst": [
            "Do not pass any video without a visible TikTok/FastMoss/Kalodata/TK buyer-side source link.",
            "For every video, produce both store-owned script and influencer script.",
            "Separate why it got views from why it can convert.",
        ],
        "product_selection_analyst": [
            "Score every product by TK evidence, lifecycle, category growth, competition, risk and 72h test feasibility.",
            "Never let unrelated products, such as power banks in cleanser/T-shirt reports, pollute a target report.",
            "Every category must have at least one candidate before repeating the same niche.",
        ],
        "influencer_hunter": [
            "A creator card is incomplete without contact route, average views, niche fit, cooperation risk and ROI expectation.",
            "Classify creators A/B/C and explain sample priority.",
        ],
        "risk_director": [
            "Borderline can be observed; confirmed IP cannot be public without authorization.",
            "Medical, supplement and beauty claims need extra claim-proof review.",
        ],
        "data_reviewer": [
            "Quarantine weak evidence before it reaches boss reports.",
            "Count hard TK evidence separately from Amazon supplement and strategy notes.",
        ],
        "finance_budget_analyst": [
            "Every plan needs breakeven ROI, CPA cap, budget ceiling, stop-loss and scale rule.",
            "Old/stable stores are observe-first; new test stores can use queued draft experiments only after approval.",
        ],
        "listing_builder": [
            "Listing drafts are only drafts until risk and evidence gates pass.",
            "Use keywords only after dedupe and platform validation.",
        ],
        "ai_ecommerce_director": [
            "Boss report must be short and decision-oriented.",
            "Assign employees, grade them and force retakes when evidence is weak.",
        ],
    }
    return rules.get(agent_id, ["Follow the global rules and submit concise evidence-backed output."])


def platform_search_urls(query: str) -> dict[str, str]:
    encoded = quote_plus(query)
    return {
        "FastMoss": f"https://www.fastmoss.com/zh/e-commerce/search?page=1&words={encoded}",
        "Kalodata": f"https://www.kalodata.com/explore?keyword={encoded}",
        "TikTok Shop Buyer": f"https://shop.tiktok.com/us/search?keyword={encoded}",
        "Amazon": f"https://www.amazon.com/s?k={encoded}",
    }


def build_employee_workspace_report(
    run_date: str,
    data_summary: dict[str, Any],
    workspaces: list[IntakeRecord],
    tasks: list[IntakeRecord],
    collection_jobs: list[IntakeRecord],
    word_bank_records: list[IntakeRecord],
    distillation_packs: list[IntakeRecord],
) -> str:
    snapshot = data_summary.get("tk_snapshot", {}) if isinstance(data_summary.get("tk_snapshot"), dict) else {}
    lines = [
        f"# AI Employee Proactive Workspace - {run_date}",
        "",
        "## Boss Summary",
        "",
        "- AI employees now have data workspaces: they can see scoped Data Lake summaries, create analysis, and queue collection jobs.",
        "- They are proactive in L0-L2 only: read, analyze, draft, queue. Real store/platform execution still needs human approval.",
        f"- Workspaces created: {len(workspaces)}; proactive tasks queued: {len(tasks)}; category collection jobs queued: {len(collection_jobs)}; word-bank rows added/updated: {len(word_bank_records)}; distillation packs: {len(distillation_packs)}.",
        f"- TK snapshot: hard TK {snapshot.get('real_tk_records', 0)}, videos {snapshot.get('viral_records', 0)}, creators {snapshot.get('creator_records', 0)}, weak {snapshot.get('weak_tk_records', 0)}.",
        "- Training coverage: 80% TikTok/TK, 20% all-platform supplement, rotating all 12 categories.",
        "- Word-bank rule: IP/risk terms are detection-only; long-tail/blue-ocean/hotspot terms must be validated by platform evidence before use.",
        "",
        "## Employee Assignments",
        "",
    ]
    for record in tasks:
        fields = record.fields
        lines.append(f"- {fields.get('target_agent_id')}: {fields.get('task_title')} -> {fields.get('expected_output')}")
    lines.extend(["", "## Category Collection Queue", ""])
    for item in CATEGORY_ROTATION:
        lines.append(f"- {item['category']}: {', '.join(item['queries'])}")
    lines.extend(["", "## Word Bank Tasks", ""])
    lines.append("- Risk/IP word bank: detect trademark, celebrity, team, character, counterfeit and medical-claim risks.")
    lines.append("- Keyword word bank: seed terms, long-tail terms, blue-ocean candidates, hotspot phrases and seasonal phrases.")
    lines.append("- Hotspot watch: TikTok Creative Center, Google Trends, YouTube Trending and Reddit product-signal jobs are queued as evidence-gated research.")
    lines.extend(["", "## Distillation Rule", ""])
    lines.append("- Every employee receives a role-specific distillation pack each run. The pack compresses current evidence, full-category rule, bad-data lessons, word-bank policy and safety gates.")
    lines.extend(["", "## Guardrail", "", "- No AI employee can publish, change price, run ads, refund, ship, contact creators, authorize apps or upload public videos without human confirmation."])
    return "\n".join(lines).rstrip() + "\n"


def latest_ai_employee_workspace_report(root: Path) -> tuple[str, Path | None]:
    output_dir = root / "outputs"
    if not output_dir.exists():
        return "No AI employee workspace report yet.", None
    paths = sorted(output_dir.glob("ai_employee_workspace_*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not paths:
        return "No AI employee workspace report yet.", None
    path = paths[0]
    return path.read_text(encoding="utf-8"), path


def stable_id(prefix: str, *parts: Any) -> str:
    return prefix + sha1("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:18]


def short_text(value: Any, limit: int = 120) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
