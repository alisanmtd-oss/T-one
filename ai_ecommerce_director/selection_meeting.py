from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .llm import LLMClient
from .report_manifest import write_report_manifest
from .selection_intelligence import latest_selection_report
from .storage import read_records


SELECTION_MEETING_CONFIG = Path("config") / "selection_meeting.json"
SELECTION_MEETING_REPORT_PREFIX = "selection_meeting"


@dataclass(slots=True)
class SelectionMeetingResult:
    run_date: str
    participants: list[dict[str, Any]]
    transcript: list[dict[str, Any]]
    decision: str
    report: str
    report_path: Path
    json_path: Path
    manifest_path: Path
    llm_used: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "participants": self.participants,
            "transcript": self.transcript,
            "decision": self.decision,
            "report": self.report,
            "report_path": str(self.report_path),
            "json_path": str(self.json_path),
            "manifest_path": str(self.manifest_path),
            "llm_used": self.llm_used,
        }


def run_selection_meeting(root: Path, run_date: str | None = None) -> SelectionMeetingResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    config = load_selection_meeting_config(root)
    context = build_meeting_context(root)
    participants = [item for item in config.get("participants", []) if isinstance(item, dict) and item.get("enabled", True)]
    transcript: list[dict[str, Any]] = []
    llm_used = False
    for participant in participants:
        statement, used = participant_statement(root, participant, context)
        llm_used = llm_used or used
        transcript.append(
            {
                "role": participant.get("role"),
                "model_route": participant.get("model_route"),
                "provider": participant.get("provider") or "",
                "llm_used": used,
                "statement": statement,
            }
        )
    decision = final_decision(context, transcript)
    report = build_meeting_report(report_date, context, transcript, decision, llm_used)
    report_path = write_meeting_report(root, report_date, report)
    json_path = write_meeting_json(root, report_date, participants, transcript, decision, llm_used, context)
    manifest_records = (
        read_records(root, "platform_ranking_signal")
        + read_records(root, "ip_image_risk")
        + read_records(root, "viral_content_signal")
    )
    manifest_path = write_report_manifest(
        root,
        "selection_meeting",
        report_date,
        {"markdown": report_path, "json": json_path},
        manifest_records,
        parser_version="selection_meeting_v1",
        scope={
            "selection_report_label": context.get("selection_report_label") or "",
            "participant_roles": [str(item.get("role") or "") for item in participants],
            "product_focus": context.get("product_focus") or {},
        },
        exclusion_summary={
            "platform_records_available": context.get("platform_record_count", 0),
            "viral_records_available": context.get("viral_record_count", 0),
            "risk_items_reviewed": len(context.get("risk_items") or []),
            "top_products_reviewed": len(context.get("top_products") or []),
        },
        seller_safe_summary={
            "decision": decision,
            "evidence_gap": "Do not scale listings before marketplace, content, factory, and IP evidence are confirmed.",
            "next_step": "Use the meeting decision as an approval-gated watch or sample-test task.",
        },
    )
    return SelectionMeetingResult(report_date, participants, transcript, decision, report, report_path, json_path, manifest_path, llm_used)


def load_selection_meeting_config(root: Path) -> dict[str, Any]:
    path = root / SELECTION_MEETING_CONFIG
    if not path.exists():
        return default_selection_meeting_config()
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        return default_selection_meeting_config()
    payload.setdefault("participants", default_selection_meeting_config()["participants"])
    return payload


def default_selection_meeting_config() -> dict[str, Any]:
    return {
        "enabled": True,
        "meeting_rule": "After selection monitoring, multiple AI roles discuss product opportunities and produce one practical decision.",
        "participants": [
            {
                "role": "Amazon Category Analyst",
                "enabled": True,
                "model_route": "product_intelligence",
                "provider": "",
                "focus": "BSR/New Releases/category rank, price band, review count, and keyword demand.",
            },
            {
                "role": "TikTok Viral Content Analyst",
                "enabled": True,
                "model_route": "video_breakdown",
                "provider": "",
                "focus": "TikTok Shop, FastMoss, Kalodata, viral video hooks, creator fit, and content replicability.",
            },
            {
                "role": "Supply Chain and Margin Analyst",
                "enabled": True,
                "model_route": "strategy",
                "provider": "",
                "focus": "Factory fit, inventory, unit economics, price band, fulfillment difficulty, and launch speed.",
            },
            {
                "role": "Risk Director",
                "enabled": True,
                "model_route": "risk",
                "provider": "",
                "focus": "Trademark, patent, copyright, platform policy, TRO, and authorization risk.",
            },
            {
                "role": "General Manager",
                "enabled": True,
                "model_route": "strategy",
                "provider": "",
                "focus": "Final decision: launch, watch, reject, or collect more data. Keep it actionable.",
            },
        ],
    }


def build_meeting_context(root: Path) -> dict[str, Any]:
    selection_report, selection_path = latest_selection_report(root)
    selection_payload = latest_selection_payload(root)
    product_focus = active_product_focus(root)
    category_recommendations = selection_payload.get("category_recommendations", [])
    if isinstance(category_recommendations, list) and product_focus:
        focused = [
            item
            for item in category_recommendations
            if isinstance(item, dict) and recommendation_matches_focus(item, product_focus)
        ]
        if focused:
            category_recommendations = focused
    platform_records = read_records(root, "platform_ranking_signal")
    ip_records = read_records(root, "ip_image_risk")
    viral_records = read_records(root, "viral_content_signal")
    product_records = [record for record in platform_records if record_matches_focus(record, product_focus)]
    if not product_records:
        product_records = platform_records
    top_products = []
    seen = set()
    for record in sorted(product_records, key=lambda item: float(item.score.get("priority", 0) or 0), reverse=True):
        fields = record.fields
        name = str(fields.get("product_name") or fields.get("page_title") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        top_products.append(
            {
                "record_id": record.record_id,
                "source": record.source,
                "created_at": record.created_at,
                "product_name": name,
                "platform": fields.get("marketplace") or fields.get("source_platform") or "",
                "ranking_type": fields.get("ranking_type") or "",
                "rank_position": fields.get("rank_position") or "",
                "url": fields.get("url") or fields.get("page_url") or "",
                "priority": record.score.get("priority", 0),
            }
        )
        if len(top_products) >= 12:
            break
    risk_items = [
        {
            "record_id": record.record_id,
            "source": record.source,
            "created_at": record.created_at,
            "risk_element": record.fields.get("risk_element") or record.fields.get("product_name") or "",
            "source_platform": record.fields.get("source_platform") or "",
            "search_query": record.fields.get("search_query") or "",
            "priority": record.score.get("priority", 0),
        }
        for record in sorted(ip_records, key=lambda item: float(item.score.get("priority", 0) or 0), reverse=True)[:10]
    ]
    return {
        "selection_report_path": str(selection_path) if selection_path else "",
        "selection_report_label": f"outputs/{selection_path.name}" if selection_path else "",
        "selection_report_excerpt": selection_report[:6000],
        "product_focus": product_focus,
        "category_recommendations": category_recommendations[:30] if isinstance(category_recommendations, list) else [],
        "top_products": top_products,
        "risk_items": risk_items,
        "viral_record_count": len(viral_records),
        "platform_record_count": len(platform_records),
    }


def latest_selection_payload(root: Path) -> dict[str, Any]:
    paths = sorted((root / "outputs").glob("selection_intelligence_*.json"), reverse=True)
    if not paths:
        return {}
    try:
        payload = json.loads(paths[0].read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def active_product_focus(root: Path) -> dict[str, Any]:
    path = root / "config" / "product_targets.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}
    targets = payload.get("targets") if isinstance(payload, dict) else []
    if not isinstance(targets, list):
        return {}
    enabled = [item for item in targets if isinstance(item, dict) and item.get("enabled", True)]
    active = [item for item in enabled if item.get("active_for_meeting")]
    chosen = active[-1] if active else (enabled[-1] if enabled else {})
    if not isinstance(chosen, dict):
        return {}
    return {
        "id": chosen.get("id") or "",
        "name": chosen.get("name") or "",
        "product_family": chosen.get("product_family") or "",
        "keywords": chosen.get("keywords") if isinstance(chosen.get("keywords"), list) else [],
    }


def recommendation_matches_focus(item: dict[str, Any], focus: dict[str, Any]) -> bool:
    haystack = json.dumps(item, ensure_ascii=False).lower()
    focus_text = json.dumps(focus, ensure_ascii=False).lower()
    if any(term in focus_text for term in ["cleanser", "face wash", "skincare", "skin care", "amino"]):
        return any(term in haystack for term in ["cleanser", "amino", "skincare", "skin care", "facial"])
    terms = [str(focus.get("name") or ""), str(focus.get("product_family") or "")]
    terms.extend(str(keyword) for keyword in focus.get("keywords", []) if str(keyword).strip())
    tokens: list[str] = []
    for term in terms:
        for token in term.lower().replace("/", " ").replace("-", " ").split():
            clean = token.strip(" ,.;:()[]")
            if len(clean) >= 4 and clean not in {"acid", "gentle", "wash"}:
                tokens.append(clean)
    return sum(1 for token in set(tokens) if token in haystack) >= 2


def record_matches_focus(record: Any, focus: dict[str, Any]) -> bool:
    if not focus:
        return True
    fields = getattr(record, "fields", {}) or {}
    target_id = str(focus.get("id") or "")
    if target_id and str(fields.get("product_target_id") or "") == target_id:
        return True
    target_name = str(focus.get("name") or "").strip().lower()
    if target_name and str(fields.get("product_target_name") or "").strip().lower() == target_name:
        return True
    haystack = json.dumps(fields, ensure_ascii=False).lower()
    terms = [str(focus.get("name") or ""), str(focus.get("product_family") or "")]
    terms.extend(str(keyword) for keyword in focus.get("keywords", []) if str(keyword).strip())
    tokens: list[str] = []
    for term in terms:
        for token in term.lower().replace("/", " ").replace("-", " ").split():
            clean = token.strip(" ,.;:()[]")
            if len(clean) >= 4 and clean not in {"acid", "gentle", "wash", "shop"}:
                tokens.append(clean)
    return sum(1 for token in set(tokens) if token in haystack) >= 2


def participant_statement(root: Path, participant: dict[str, Any], context: dict[str, Any]) -> tuple[str, bool]:
    client = LLMClient(root=root, task=str(participant.get("model_route") or "strategy"), provider=str(participant.get("provider") or "") or None)
    prompt = (
        f"You are {participant.get('role')} in an AI Ecommerce Director product-selection meeting.\n"
        f"Focus: {participant.get('focus')}\n"
        "Read the context and give concise Chinese recommendations. Include: keep/watch/reject, reasons, missing data, and next action.\n\n"
        f"Context:\n{json.dumps(context, ensure_ascii=False, indent=2)[:12000]}"
    )
    if client.enabled:
        try:
            return client.chat("You are a practical cross-border ecommerce operating expert.", prompt, task=str(participant.get("model_route") or "strategy")), True
        except Exception as exc:  # noqa: BLE001 - fall back to deterministic meeting.
            return fallback_statement(participant, context, error=str(exc)), False
    return fallback_statement(participant, context), False


def fallback_statement(participant: dict[str, Any], context: dict[str, Any], error: str = "") -> str:
    role = str(participant.get("role") or "")
    products = context.get("top_products") or []
    first = products[0] if products else {}
    product_name = first.get("product_name") or "当前监控商品"
    if not products:
        product_name = "current monitored product"
    if "Amazon" in role:
        base = f"Recommendation: keep watching and deeply review {product_name}. Amazon already has product-level ranking or keyword records. Check price band, review count, negative reviews, and whether it repeatedly enters New Releases or Top 30."
    elif "TikTok" in role:
        base = "TikTok buyer-side entry can still trigger verification. Use FastMoss, Kalodata, and TikTok video search to collect content evidence. Prioritize videos that show washed texture, fit, styling, and identity-based audiences."
    elif "Supply" in role:
        base = "If the factory has washed, heavyweight, or oversized blanks in stock, or can sample quickly, run a small sample test. If not, do not scale listings yet because sizing, shrinkage, and fabric weight stability are key risks."
    elif "Risk" in role:
        base = "Do not copy brand elements from Carhartt, Comfort Colors, or similar competitors. The washed process itself can be used, but graphics, logos, slogans, and patches need trademark, copyright, patent, and authorization review."
    else:
        base = "Initial decision: keep as WATCH + SAMPLE TEST, not a full-scale listing push. First verify Amazon price/review data, TikTok video playbook, supply-chain cost, and IP risk."
    if error:
        base += f" Model call failed, so rule-based input was used: {error[:160]}"
    return base


def final_decision(context: dict[str, Any], transcript: list[dict[str, Any]]) -> str:
    category_recommendations = context.get("category_recommendations") or []
    if category_recommendations:
        product = category_recommendations[0].get("product_name") or "category winner"
        category = category_recommendations[0].get("category_path") or "target category"
        score = category_recommendations[0].get("score") or "-"
        return (
            f"Meeting decision: {product} is the current category winner for {category}, score {score}. "
            "Run WATCH + SAMPLE TEST first. Next data needed: 1. Amazon comparable price, reviews, and negative reviews; "
            "2. FastMoss, Kalodata, and TikTok viral content evidence; "
            "3. factory cost, stock, fabric/spec stability, and IP risk. "
            "Do not scale listings before category fit and TikTok content evidence are confirmed."
        )
    products = context.get("top_products") or []
    product = products[0].get("product_name") if products else "Washed T-Shirt"
    return (
        f"Meeting decision: {product} enters WATCH + SAMPLE TEST. "
        "Next data needed: 1. Amazon comparable price, reviews, and negative reviews; "
        "2. FastMoss, Kalodata, and TikTok viral content evidence; "
        "3. Factory cost, fabric weight, sizing, and shrinkage stability. "
        "Do not scale listings before TikTok sales/content evidence is confirmed."
    )


def build_meeting_report(run_date: str, context: dict[str, Any], transcript: list[dict[str, Any]], decision: str, llm_used: bool) -> str:
    lines = [
        f"# Product Selection AI Meeting - {run_date}",
        "",
        f"LLM used: {llm_used}",
        f"Selection report: {context.get('selection_report_label') or '-'}",
        "",
        "## Context",
        f"- Platform records: {context.get('platform_record_count', 0)}",
        f"- Viral records: {context.get('viral_record_count', 0)}",
        f"- Top products reviewed: {len(context.get('top_products') or [])}",
        "",
        "## Participants",
    ]
    for turn in transcript:
        lines.append(f"### {turn.get('role')} ({'LLM' if turn.get('llm_used') else 'rules'})")
        lines.append(str(turn.get("statement") or "").strip())
        lines.append("")
    lines.extend(["## Final Decision", decision, ""])
    return "\n".join(lines).rstrip() + "\n"


def write_meeting_report(root: Path, run_date: str, content: str) -> Path:
    path = root / "outputs" / f"{SELECTION_MEETING_REPORT_PREFIX}_{run_date}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_meeting_json(
    root: Path,
    run_date: str,
    participants: list[dict[str, Any]],
    transcript: list[dict[str, Any]],
    decision: str,
    llm_used: bool,
    context: dict[str, Any] | None = None,
) -> Path:
    path = root / "outputs" / f"{SELECTION_MEETING_REPORT_PREFIX}_{run_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "run_date": run_date,
                "participants": participants,
                "transcript": transcript,
                "decision": decision,
                "context": context or {},
                "llm_used": llm_used,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def latest_selection_meeting_report(root: Path) -> tuple[str, Path | None]:
    paths = sorted((root / "outputs").glob(f"{SELECTION_MEETING_REPORT_PREFIX}_*.md"), reverse=True)
    if not paths:
        return "No product-selection AI meeting report yet.", None
    path = paths[0]
    return path.read_text(encoding="utf-8"), path
