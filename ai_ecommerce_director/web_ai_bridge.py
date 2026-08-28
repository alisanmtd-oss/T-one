from __future__ import annotations

import json
import re
from hashlib import sha1
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from .knowledge_engine import KnowledgeImportResult, import_conversation_knowledge
from .llm import LLMClient
from .reporting import generate_daily_report
from .selection_intelligence import latest_selection_report
from .selection_meeting import build_meeting_context
from .storage import append_record, read_recent_records, read_records
from .types import IntakeRecord


WEB_AI_CONFIG = Path("config") / "web_ai_bridge.json"
PACKAGE_DIR = Path("outputs") / "web_ai_packages"


@dataclass(slots=True)
class WebAIPackage:
    task: str
    provider: str
    prompt: str
    markdown_path: Path
    json_path: Path
    provider_url: str
    project_prompt: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "provider": self.provider,
            "prompt": self.prompt,
            "markdown_path": str(self.markdown_path),
            "json_path": str(self.json_path),
            "provider_url": self.provider_url,
            "project_prompt": self.project_prompt,
        }


@dataclass(slots=True)
class WebAIResponseResult:
    meeting_record: IntakeRecord
    feedback_records: list[IntakeRecord]
    memory_records: list[IntakeRecord]
    knowledge_import: KnowledgeImportResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "meeting": self.meeting_record.to_dict(),
            "feedback_records": [record.to_dict() for record in self.feedback_records],
            "memory_records": [record.to_dict() for record in self.memory_records],
            "knowledge_import": self.knowledge_import.to_dict() if self.knowledge_import else None,
            "feedback_count": len(self.feedback_records),
            "memory_count": len(self.memory_records),
            "knowledge_item_count": len(self.knowledge_import.knowledge_items) if self.knowledge_import else 0,
            "knowledge_edge_count": len(self.knowledge_import.knowledge_edges) if self.knowledge_import else 0,
            "concept_weight_count": len(self.knowledge_import.concept_weights) if self.knowledge_import else 0,
        }


def default_web_ai_config() -> dict[str, Any]:
    return {
        "enabled": True,
        "project_name": "AI Ecommerce Director",
        "safety_mode": "read_only_until_human_confirmation",
        "providers": [
            {
                "id": "chatgpt",
                "name": "ChatGPT",
                "enabled": True,
                "url": "https://chatgpt.com/",
                "project_hint": "Create a Project named AI Ecommerce Director, paste the project prompt, then paste task packages into new chats.",
            },
            {
                "id": "claude",
                "name": "Claude",
                "enabled": True,
                "url": "https://claude.ai/new",
                "project_hint": "Create a Project named AI Ecommerce Director, paste the project prompt, then paste task packages into project chats.",
            },
            {
                "id": "gemini",
                "name": "Gemini",
                "enabled": True,
                "url": "https://gemini.google.com/app",
                "project_hint": "Use a saved Gem or a new chat for AI Ecommerce Director task packages.",
            },
        ],
        "tasks": [
            {"id": "selection_meeting", "name": "Product Selection AI Meeting"},
            {"id": "daily_review", "name": "Daily Ecommerce Director Review"},
            {"id": "video_breakdown", "name": "Viral Video Breakdown"},
            {"id": "listing_builder", "name": "Listing Builder"},
            {"id": "risk_review", "name": "IP and Policy Risk Review"},
            {"id": "ai_api_integration_review", "name": "AI API Integration Review"},
            {"id": "completion_bug_review", "name": "Completion Bug Review Meeting"},
        ],
    }


def load_web_ai_config(root: Path) -> dict[str, Any]:
    path = root / WEB_AI_CONFIG
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(default_web_ai_config(), ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        payload = default_web_ai_config()
    if not isinstance(payload, dict):
        payload = default_web_ai_config()
    payload.setdefault("providers", default_web_ai_config()["providers"])
    payload.setdefault("tasks", default_web_ai_config()["tasks"])
    payload["tasks"] = merge_web_ai_tasks(payload.get("tasks", []))
    payload.setdefault("project_name", "AI Ecommerce Director")
    return payload


def merge_web_ai_tasks(tasks: Any) -> list[dict[str, str]]:
    existing = [item for item in tasks if isinstance(item, dict)]
    by_id = {str(item.get("id") or ""): item for item in existing if item.get("id")}
    for item in default_web_ai_config()["tasks"]:
        task_id = str(item.get("id") or "")
        if task_id and task_id not in by_id:
            existing.append(item)
    return existing


def provider_map(root: Path) -> dict[str, dict[str, Any]]:
    config = load_web_ai_config(root)
    providers = config.get("providers") if isinstance(config.get("providers"), list) else []
    return {
        str(item.get("id") or "").strip(): item
        for item in providers
        if isinstance(item, dict) and item.get("enabled", True)
    }


def project_prompt(root: Path) -> str:
    config = load_web_ai_config(root)
    return f"""# {config.get("project_name") or "AI Ecommerce Director"}

You are the web AI brain for a Global Commerce OS. Work as a cross-border ecommerce operating director, not as a generic chatbot.

Strategic positioning:
- This is not a TikTok tool, POD site, Amazon tool, or generic website.
- The target is Global Commerce OS and Commerce Brain for multi-platform, multi-country, B2C, B2B, creator economy, POD, and factory operations.
- The current practical goal is to build one AI Ecommerce Director that can actually help make money before expanding to 100+ or 1000+ stores.

Core business scope:
- TikTok Shop, Amazon, Walmart, Etsy, eBay, SHEIN, Shopify, Mercado Libre, Noon, Takealot, Lazada, Shopee, POD, B2B and factory operations.
- Product selection, competitor intelligence, keyword research, listing building, influencer development, viral video breakdown, content direction, advertising review, OMS, supply chain and risk control.

Data lake priority:
- Treat Product DB, Video DB, Influencer DB, Keyword DB, Listing DB, Review DB, Store DB, Supplier DB, Success DB and Failure DB as the core assets.
- When a feature is requested, first ask what data asset it creates, updates, validates, or uses.
- Prefer manual upload, screenshots, Excel, CSV and workflow validation before buying many APIs.

Operating rules:
- First deconstruct, then analyze, then summarize, then propose actions.
- Do not build random UI or new features just because an idea appears. Follow: analyze -> deconstruct -> document -> workflow -> database -> develop -> test -> review -> release.
- Separate broad category radar from focused product monitoring.
- One web AI account may handle many tasks, but each task package is isolated. Use only the context included in the current package.
- Do not use memory from other chats, other stores, other countries, other brands, other products or other users unless it is explicitly included in this package.
- Treat the local AI Ecommerce Director database as the only long-term memory source. The external AI should act as a stateless analyst for the current package.
- Always state the scope you used: store, country, platform, product, task and missing data.
- For every recommendation, include evidence, missing data, next action and risk.
- Do not invent sales numbers, rankings, creator data or platform rules. Mark unknowns clearly.
- Treat store login details, legal entity names, phone, email, passwords, API keys and internal shop data as sensitive. Ask the operator to redact when needed.
- Output drafts and action queues only. Do not ask to publish listings, change prices, join campaigns, contact creators, ship orders, authorize apps, pay money, buy IP nodes or change store settings without human confirmation.
- After each completed implementation, participate in a Completion Bug Review Meeting: check what changed, whether it really works, what tests passed, what data may still be fake or empty, what user workflow might break, and what should be fixed before the operator trusts it.

Preferred output:
1. Executive conclusion
2. Evidence table
3. Risks and missing data
4. Recommended action queue
5. Data to collect next
"""


def build_web_ai_prompt(root: Path, task: str, provider: str = "chatgpt", extra_message: str = "") -> str:
    task = task or "selection_meeting"
    provider = provider or "chatgpt"
    context = task_context(root, task)
    instructions = task_instructions(task)
    prompt = f"""{project_prompt(root)}

## Current Task
Provider target: {provider}
Task type: {task}
Task name: {task_display_name(root, task)}
Session rule: this package is a fresh isolated task. Do not use other chats or memories.

{instructions}

## Extra Operator Message
{sanitize_for_external_ai(extra_message) if extra_message else "No extra message."}

## Context Package
{sanitize_for_external_ai(json.dumps(context, ensure_ascii=False, indent=2))[:45000]}

Please answer in Chinese. Keep it practical and decision-oriented.
"""
    return prompt.strip() + "\n"


def task_context(root: Path, task: str) -> dict[str, Any]:
    if task == "selection_meeting":
        context = build_meeting_context(root)
        context["latest_platform_records"] = compact_records(read_recent_records(root, "platform_ranking_signal", 25), 25)
        context["latest_hot_links"] = compact_records(read_recent_records(root, "hot_link", 15), 15)
        return context
    if task == "daily_review":
        report, path = generate_daily_report(root)
        return {"daily_report_path": str(path), "daily_report_excerpt": report[:16000]}
    if task == "video_breakdown":
        return {
            "viral_content_records": compact_records(read_recent_records(root, "viral_content_signal", 15), 15),
            "video_breakdown_records": compact_records(read_recent_records(root, "video_breakdown", 15), 15),
            "video_script_records": compact_records(read_recent_records(root, "video_script", 15), 15),
        }
    if task == "listing_builder":
        return {
            "platform_ranking_records": compact_records(read_recent_records(root, "platform_ranking_signal", 20), 20),
            "hot_link_records": compact_records(read_recent_records(root, "hot_link", 15), 15),
            "review_insights": compact_records(read_recent_records(root, "review_insight", 15), 15),
            "store_metrics": compact_records(read_recent_records(root, "store_metric_snapshot", 10), 10),
        }
    if task == "risk_review":
        return {
            "compliance_terms": compact_records(read_recent_records(root, "compliance_term", 30), 30),
            "ip_image_risks": compact_records(read_recent_records(root, "ip_image_risk", 30), 30),
            "review_insights": compact_records(read_recent_records(root, "review_insight", 15), 15),
        }
    if task == "ai_api_integration_review":
        status = LLMClient(root=root, task="chat").status().to_dict()
        return {
            "multi_ai_status": status,
            "api_context_policy": {
                "one_account_allowed": True,
                "memory_source": "local AI Ecommerce Director database",
                "per_request_scope_keys": ["session_id", "task", "store_id", "country", "platform", "product_id", "product_target_id", "brand_id"],
                "rule": "Use one account/API key if needed, but never merge context across stores, countries, platforms, products, users or tasks.",
            },
            "api_health_check": {
                "endpoint": "/api/multi-ai/test",
                "payload": {"task": "chat"},
                "test_prompt": "Return OK. Do not include business analysis.",
            },
            "questions_for_external_ai": [
                "Is the one-account multi-task isolation design safe enough for a one-person ecommerce operating system?",
                "What provider routing should be used for chat, product intelligence, video breakdown, listing, review analysis and compliance?",
                "What bugs or operational risks should we test before real store data is connected?",
            ],
        }
    if task == "completion_bug_review":
        from .workflow_status import build_workflow_status

        workflow = build_workflow_status(root)
        return {
            "review_goal": "Post-implementation QA meeting with the external ecommerce intelligence project.",
            "local_workflow_status": workflow,
            "recent_bug_reports": compact_records(read_recent_records(root, "bug_report", 15), 15),
            "recent_feedback": compact_records(read_recent_records(root, "operator_feedback", 15), 15),
            "recent_actions": compact_records(read_recent_records(root, "store_operation_event", 15), 15),
            "recent_creator_records": compact_records(read_recent_records(root, "influencer_cooperation", 15), 15),
            "recent_rankings": compact_records(read_recent_records(root, "platform_ranking_signal", 15), 15),
            "required_review_checklist": [
                "Does the changed feature have real data behind it, or is it still a shell?",
                "Can the operator open the page and complete the workflow without coding knowledge?",
                "Are filters, buttons, forms and links wired to real APIs/routes?",
                "Are empty states honest and useful instead of pretending data exists?",
                "Did local tests cover data aggregation, page rendering and user workflow?",
                "Could this accidentally publish, change price, contact creators, move money, alter ads or affect real stores?",
                "What data accuracy issues should be cross-checked manually against the platform?",
                "What should be fixed before giving this to a real seller/top brand?",
            ],
        }
    report, path = latest_selection_report(root)
    return {"selection_report_path": str(path) if path else "", "selection_report_excerpt": report[:12000]}


def task_instructions(task: str) -> str:
    instructions = {
        "selection_meeting": (
            "Run a multi-role product selection meeting. Roles: Amazon analyst, TikTok viral analyst, supply-chain analyst, risk director and general manager. "
            "Pick launch/watch/reject, explain why, then list missing data and the next 5 concrete actions."
        ),
        "daily_review": (
            "Review the daily ecommerce report. Identify sales, return, product, content, creator, listing, ad, supply-chain and risk priorities. "
            "Create a morning action queue for a one-person company."
        ),
        "video_breakdown": (
            "Break down viral content. Extract hook, audience identity, emotion, scene, shot structure, comments, creator type, replication plan and 10 store-owned plus 10 influencer scripts."
        ),
        "listing_builder": (
            "Generate marketplace listing strategy. Include Amazon/TikTok/Etsy titles, bullet points, tags, image plan, price bands and conversion risks."
        ),
        "risk_review": (
            "Review IP, trademark, patent, copyright, TRO and platform policy risk. Separate authorized branded goods from unauthorized copying. Produce block/review/allow suggestions."
        ),
        "ai_api_integration_review": (
            "Review the multi-AI API integration design. Focus on one-account multi-task isolation, provider routing, API health checks, privacy boundaries, cost control, bug tests and rollout steps. "
            "Do not ask for real API keys or store credentials. Output an implementation checklist and test plan."
        ),
        "completion_bug_review": (
            "Run a post-implementation QA meeting as the external ecommerce intelligence reviewer. "
            "Inspect the completed work from the operator's point of view: what changed, what actually works, what is still empty or fake, which buttons/forms/routes may be broken, "
            "what tests passed, what tests are missing, what store-safety risks remain, what data should be manually cross-checked, and what must be fixed before trusted use. "
            "Output: pass/block decision, bug list by severity, missing workflow details, data-quality risks, safety risks, and next fix checklist."
        ),
    }
    return instructions.get(task, instructions["selection_meeting"])


def task_display_name(root: Path, task: str) -> str:
    config = load_web_ai_config(root)
    for item in config.get("tasks", []):
        if isinstance(item, dict) and str(item.get("id") or "") == task:
            return str(item.get("name") or task)
    return task


def write_web_ai_package(root: Path, task: str, provider: str, extra_message: str = "") -> WebAIPackage:
    root = root.resolve()
    providers = provider_map(root)
    provider_config = providers.get(provider) or providers.get("chatgpt") or {}
    provider_id = str(provider_config.get("id") or provider or "chatgpt")
    provider_url = str(provider_config.get("url") or "https://chatgpt.com/")
    prompt = build_web_ai_prompt(root, task, provider_id, extra_message)
    now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_task = safe_slug(task)
    safe_provider = safe_slug(provider_id)
    output_dir = root / PACKAGE_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / f"{now}_{safe_task}_{safe_provider}.md"
    json_path = output_dir / f"{now}_{safe_task}_{safe_provider}.json"
    markdown_path.write_text(prompt, encoding="utf-8")
    payload = {
        "task": task,
        "provider": provider_id,
        "provider_url": provider_url,
        "project_prompt": project_prompt(root),
        "prompt": prompt,
        "extra_message": sanitize_for_external_ai(extra_message),
        "context_policy": {
            "one_account_allowed": True,
            "isolation_rule": "One task package equals one isolated conversation. Do not merge stores, countries, products or users unless the package includes them.",
            "memory_source": "The local AI Ecommerce Director database is the only long-term memory source.",
            "sensitive_data": ["api keys", "passwords", "legal entity data", "phone", "email", "shop login", "customer data"],
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return WebAIPackage(task, provider_id, prompt, markdown_path, json_path, provider_url, payload["project_prompt"])


def save_web_ai_response(
    root: Path,
    task: str,
    provider: str,
    response_text: str,
    *,
    package_path: str = "",
    operator_notes: str = "",
) -> WebAIResponseResult:
    """Persist an external web-AI review and turn it into local closed-loop records."""

    clean_response = str(response_text or "").strip()
    if not clean_response:
        raise ValueError("External AI response is empty.")

    task = task or "completion_bug_review"
    provider = provider or "chatgpt"
    parsed = parse_web_ai_response(clean_response)
    now = datetime.now(timezone.utc).isoformat()
    meeting_key = sha1(f"{task}|{provider}|{package_path}|{clean_response[:2000]}".encode("utf-8")).hexdigest()[:16]
    meeting_fields = {
        "meeting_key": meeting_key,
        "task": task,
        "task_name": task_display_name(root, task),
        "provider": provider,
        "package_path": package_path,
        "operator_notes": operator_notes,
        "response_text": clean_response,
        "saved_at": now,
        "blocker_count": len([item for item in parsed if item["severity"] in {"P0", "P1"} and item["category"] == "blocker"]),
        "issue_count": len([item for item in parsed if item["category"] in {"blocker", "bug", "risk"}]),
        "suggestion_count": len([item for item in parsed if item["category"] == "suggestion"]),
        "next_action_count": len([item for item in parsed if item["category"] == "next_action"]),
        "closed_loop_status": "needs_fix" if parsed else "manual_review",
    }
    meeting_record = IntakeRecord(
        record_type="web_ai_meeting",
        source=f"web_ai_bridge:{provider}",
        raw_text=clean_response,
        fields=meeting_fields,
        score={"priority": 92 if meeting_fields["blocker_count"] else 78, "review_type": task},
        director_notes=[
            "External ecommerce intelligence response was saved into the local memory loop.",
            "Parsed issues should be reviewed before trusting the feature in real store operations.",
        ],
        metadata={"parsed_item_count": len(parsed)},
    )
    append_record(root, meeting_record)

    feedback_records: list[IntakeRecord] = []
    for index, item in enumerate(parsed, start=1):
        if item["category"] not in {"blocker", "bug", "risk", "next_action"}:
            continue
        fields = {
            "feedback_source": "web_ai_meeting",
            "source_meeting_id": meeting_record.record_id,
            "task": task,
            "provider": provider,
            "module_area": item["module_area"],
            "severity": item["severity"],
            "category": item["category"],
            "feedback_text": item["text"],
            "expected_behavior": "The AI Ecommerce Director feature should be usable by an operator without coding knowledge.",
            "actual_behavior": item["text"],
            "suggested_fix": item["next_action"],
            "page_url": "/web-ai-bridge",
            "status": "open",
            "review_order": index,
        }
        record = IntakeRecord(
            record_type="feedback_ticket",
            source=f"web_ai_bridge:{provider}",
            raw_text=item["text"],
            fields=fields,
            score={"priority": severity_priority(item["severity"]), "source": "external_ai_review"},
            director_notes=[
                "This issue came from the external ecommerce intelligence review.",
                "Fix or explicitly reject it before marking the implementation ready.",
            ],
            review_status="pending",
            confidence=0.82,
        )
        append_record(root, record)
        feedback_records.append(record)

    memory_records: list[IntakeRecord] = []
    for item in parsed:
        if item["category"] not in {"suggestion", "next_action"}:
            continue
        memory_key = sha1(f"web_ai:{task}:{item['category']}:{item['text']}".encode("utf-8")).hexdigest()[:18]
        record = IntakeRecord(
            record_type="strategy_memory",
            source=f"web_ai_bridge:{provider}",
            raw_text=item["text"],
            fields={
                "memory_key": f"web_ai_{memory_key}",
                "memory_type": "external_ai_review_learning",
                "task": task,
                "provider": provider,
                "source_meeting_id": meeting_record.record_id,
                "lesson": item["text"],
                "next_action": item["next_action"],
                "module_area": item["module_area"],
                "saved_at": now,
            },
            score={"priority": 70, "training_weight": "medium"},
            director_notes=["External AI suggestion saved as reusable strategy memory."],
            confidence=0.78,
        )
        append_record(root, record)
        memory_records.append(record)

    knowledge_import = import_conversation_knowledge(
        root,
        clean_response,
        source_type="web_ai_response",
        source_name=provider,
        provider=provider,
        task=task,
        operator_notes=operator_notes or "Imported from Web AI Bridge response.",
    )

    return WebAIResponseResult(meeting_record, feedback_records, memory_records, knowledge_import)


def parse_web_ai_response(response_text: str) -> list[dict[str, str]]:
    current_category = "bug"
    current_severity = "P2"
    parsed: list[dict[str, str]] = []
    for raw_line in response_text.splitlines():
        clean = strip_markdown_line(raw_line)
        if not clean:
            continue
        header = clean.lower()
        if any(key in header for key in ["阻塞", "blocker", "block", "p0", "严重问题", "必须先修"]):
            current_category = "blocker"
            current_severity = "P0"
            if is_section_header(clean):
                continue
        elif any(key in header for key in ["风险", "risk", "安全", "隐私", "权限"]):
            current_category = "risk"
            current_severity = "P1"
            if is_section_header(clean):
                continue
        elif any(key in header for key in ["一般问题", "bug", "问题", "遗漏", "空壳"]):
            current_category = "bug"
            current_severity = "P2"
            if is_section_header(clean):
                continue
        elif any(key in header for key in ["建议", "优化", "suggest", "improvement"]):
            current_category = "suggestion"
            current_severity = "P3"
            if is_section_header(clean):
                continue
        elif any(key in header for key in ["下一步", "next", "fix checklist", "待办", "修复"]):
            current_category = "next_action"
            current_severity = "P1"
            if is_section_header(clean):
                continue
        if len(clean) < 6 or clean in {"无", "none", "暂无"}:
            continue
        parsed.append(
            {
                "category": current_category,
                "severity": explicit_severity(clean, current_severity),
                "module_area": infer_module_area(clean),
                "text": clean[:1200],
                "next_action": infer_next_action(clean, current_category),
            }
        )
        if len(parsed) >= 60:
            break
    if not parsed:
        parsed.append(
            {
                "category": "bug",
                "severity": "P2",
                "module_area": "web_ai_bridge",
                "text": "External AI response saved but no structured issue was detected. Review the meeting text manually.",
                "next_action": "Open the saved meeting record and manually decide whether to create feedback tickets.",
            }
        )
    return parsed


def strip_markdown_line(value: str) -> str:
    clean = re.sub(r"^\s*[-*•\d.、\)]+\s*", "", value.strip())
    return clean.strip("# ：:| \t")


def is_section_header(value: str) -> bool:
    clean = value.strip()
    return len(clean) <= 28 and not re.search(r"[。.!?？]", clean)


def explicit_severity(text: str, fallback: str) -> str:
    upper = text.upper()
    for severity in ["P0", "P1", "P2", "P3"]:
        if severity in upper:
            return severity
    return fallback


def severity_priority(severity: str) -> int:
    return {"P0": 100, "P1": 90, "P2": 75, "P3": 55}.get(severity, 65)


def infer_module_area(text: str) -> str:
    lower = text.lower()
    mapping = [
        ("达人", "influencer_library"),
        ("creator", "influencer_library"),
        ("联系方式", "influencer_library"),
        ("contact", "influencer_library"),
        ("web-ai", "web_ai_bridge"),
        ("电商智能", "web_ai_bridge"),
        ("复盘", "web_ai_bridge"),
        ("按钮", "ui_workflow"),
        ("空壳", "ui_workflow"),
        ("数据", "data_quality"),
        ("隐私", "privacy"),
        ("脱敏", "privacy"),
        ("权限", "privacy"),
        ("店铺", "store_safety"),
        ("发布", "store_safety"),
        ("改价", "store_safety"),
        ("广告", "store_safety"),
        ("测试", "testing"),
    ]
    for key, area in mapping:
        if key in lower:
            return area
    return "ai_ecommerce_director"


def infer_next_action(text: str, category: str) -> str:
    if category == "suggestion":
        return "Evaluate this suggestion and convert it into a product/task improvement if it helps operator workflow."
    if category == "next_action":
        return text
    if any(key in text for key in ["隐私", "脱敏", "联系方式", "权限"]):
        return "Add privacy masking, permission labels and operator confirmation before using real contact/store data."
    if any(key in text for key in ["空壳", "按钮", "接口", "打不开"]):
        return "Wire the UI button to a real route/API, then test it from the operator page."
    if any(key in text for key in ["测试", "用例"]):
        return "Add a focused regression test and run the full test suite."
    return "Review, reproduce, fix, and record the result in the closed-loop center."


def recent_web_ai_meetings(root: Path, limit: int = 8) -> list[IntakeRecord]:
    return sorted(read_records(root, "web_ai_meeting"), key=lambda item: item.created_at, reverse=True)[:limit]


def provider_launch_links(root: Path, prompt: str = "") -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for provider in provider_map(root).values():
        provider_id = str(provider.get("id") or "")
        url = str(provider.get("url") or "")
        if provider_id == "gemini" and prompt:
            url = f"{url}?q={quote_plus(prompt[:3500])}"
        links.append(
            {
                "id": provider_id,
                "name": str(provider.get("name") or provider_id),
                "url": url,
                "hint": str(provider.get("project_hint") or ""),
            }
        )
    return links


def compact_records(records: list[Any], limit: int) -> list[dict[str, Any]]:
    items = sorted(records, key=lambda item: item.created_at, reverse=True)[:limit]
    return [
        {
            "record_id": item.record_id,
            "record_type": item.record_type,
            "created_at": item.created_at,
            "fields": item.fields,
            "score": item.score,
            "director_notes": item.director_notes[:3],
        }
        for item in items
    ]


def sanitize_for_external_ai(text: str) -> str:
    if not text:
        return ""
    patterns = [
        (r"(密码|口令|验证码|登录密码|支付密码)\s*[:：]\s*[^\s，。；;]+", r"\1: [REDACTED]"),
        (r"(密钥|令牌|访问令牌|授权码|API\s*Key|ApiKey)\s*[:：]\s*[^\s，。；;]+", r"\1: [REDACTED]"),
        (r"(密码|password|passcode)\s*[:：]\s*[^\s，,；;]+", r"\1: [REDACTED]"),
        (r"(api[_ -]?key|secret|token)\s*[:：]\s*[^\s，,；;]+", r"\1: [REDACTED]"),
        (r"([A-Za-z0-9._%+-])([A-Za-z0-9._%+-]*)(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", r"\1***\3"),
        (r"(\+?\d[\d\s\-]{7,}\d)", "[PHONE_REDACTED]"),
        (r"[A-Za-z]:\\[^\s，。；;,]+", "[LOCAL_PATH_REDACTED]"),
        (r"/(?:Users|home|mnt|tmp|var|workspace)/[^\s，。；;,]+", "[LOCAL_PATH_REDACTED]"),
        (r"(?i)\b(?:outputs|documents|desktop)\\[^\s，。；;,]+", "[LOCAL_PATH_REDACTED]"),
    ]
    result = str(text)
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def safe_slug(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip().lower())
    return clean.strip("_") or "task"
