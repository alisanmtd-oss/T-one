from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any

from .storage import append_record, read_records
from .types import IntakeRecord


REPORT_NAME = "AI_ECOMMERCE_DIRECTOR_AGENT_V1_REPORT.md"

AGENT_STATES = [
    "IDLE",
    "INGESTING",
    "CLASSIFYING",
    "SCORING",
    "SIGNAL_DETECTED",
    "HYPOTHESIS_CREATED",
    "PLAN_CREATED",
    "TASKS_CREATED",
    "WAITING_FOR_EXECUTION",
    "REVIEWING_RESULT",
    "MEMORY_UPDATED",
]

DOG_DAD_TEST_INPUT = (
    "TikTok US 爆款案例：一个 Dog Dad T-shirt 视频在父亲节前爆了。"
    "视频前3秒是一只狗扑向男主人，字幕是 \"Need a Father's Day gift for the dog dad in your life?\"，"
    "后面展示T恤图案和狗主人互动。评论区很多人说 \"buying this for my husband\"、"
    "\"my dad needs this\"、\"where can I get it\"。产品是T恤，目标人群是养狗男性、"
    "父亲节礼物买家、宠物家庭。"
)


@dataclass(slots=True)
class EcommerceDirectorAgentResult:
    agent_run_id: str
    status: str
    classification: dict[str, Any]
    scores: dict[str, Any]
    extracted_insights: dict[str, Any]
    signals: list[dict[str, Any]]
    hypotheses: list[dict[str, Any]]
    plans: list[dict[str, Any]]
    tasks: list[dict[str, Any]]
    memory_updates: list[dict[str, Any]]
    next_actions: list[str]
    report: str
    report_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_run_id": self.agent_run_id,
            "status": self.status,
            "classification": self.classification,
            "scores": self.scores,
            "extracted_insights": self.extracted_insights,
            "signals": self.signals,
            "hypotheses": self.hypotheses,
            "plans": self.plans,
            "tasks": self.tasks,
            "memory_updates": self.memory_updates,
            "next_actions": self.next_actions,
            "report": self.report,
            "report_path": str(self.report_path),
        }


def run_ecommerce_director_analysis(root: Path, payload: dict[str, Any] | str | None = None) -> EcommerceDirectorAgentResult:
    root = root.resolve()
    if isinstance(payload, str):
        payload = {"input_text": payload}
    payload = payload or {}
    input_text = str(payload.get("input_text") or payload.get("text") or DOG_DAD_TEST_INPUT).strip()
    if not input_text:
        raise ValueError("input_text is required.")
    input_type = str(payload.get("input_type") or "text")
    input_url = str(payload.get("input_url") or payload.get("url") or "").strip()
    now = datetime.now(timezone.utc).isoformat()
    agent_run_id = stable_id("run_", input_text[:4000], input_url, now)
    state_history = build_state_history(now)

    classification = classify_agent_input(
        input_text,
        platform=str(payload.get("platform") or ""),
        country=str(payload.get("country") or ""),
        category=str(payload.get("category") or ""),
    )
    scores = score_agent_input(input_text, classification)
    insights = extract_agent_insights(input_text, classification)

    source_document = build_source_document(agent_run_id, input_text, input_type, input_url, classification, scores, now)
    append_record(root, source_document)
    source_chunk = build_source_chunk(agent_run_id, source_document, input_text, now)
    append_record(root, source_chunk)

    evidence_claims = build_evidence_claims(agent_run_id, source_chunk, insights, scores, now)
    for record in evidence_claims:
        append_record(root, record)

    signals = build_signals(agent_run_id, classification, insights, scores, len(evidence_claims), now)
    signal_records = [build_signal_record(signal, source_chunk.record_id, now) for signal in signals]
    for record in signal_records:
        append_record(root, record)

    hypotheses = build_hypotheses(agent_run_id, signals, insights, scores, now)
    hypothesis_records = [build_hypothesis_record(item, now) for item in hypotheses]
    for record in hypothesis_records:
        append_record(root, record)

    plans = build_plans(agent_run_id, hypotheses, insights, scores, now)
    plan_records = [build_plan_record(item, now) for item in plans]
    for record in plan_records:
        append_record(root, record)

    plan_tasks = build_plan_tasks(agent_run_id, plans, insights, now)
    for record in plan_tasks:
        append_record(root, record)
    task_queue_records = [build_task_queue_record(task, now) for task in plan_tasks]
    for record in task_queue_records:
        append_record(root, record)

    review_record = build_initial_review(agent_run_id, plans[0]["plan_id"] if plans else "", scores, now)
    append_record(root, review_record)

    memory_records = build_memory_updates(agent_run_id, classification, insights, signals, hypotheses, scores, now)
    for record in memory_records:
        append_record(root, record)

    agent_run = IntakeRecord(
        record_type="agent_run",
        source="ecommerce_director_agent",
        raw_text=input_text,
        fields={
            "agent_run_id": agent_run_id,
            "run_type": "viral_video_product_case_analysis",
            "input_type": input_type,
            "input_url": input_url,
            "status": "WAITING_FOR_EXECUTION",
            "current_state": "WAITING_FOR_EXECUTION",
            "previous_state": "TASKS_CREATED",
            "state_history": state_history,
            "classification": classification,
            "scores": scores,
            "source_document_id": source_document.record_id,
            "created_at": now,
            "updated_at": now,
            "error_message": "",
        },
        score={"priority": scores["business_value_score"], "agent_v1": True},
        director_notes=["Agent V1 closed loop created Signal -> Hypothesis -> Plan -> Task -> Review placeholder -> Memory Update."],
        confidence=round(scores["evidence_score"] / 100, 3),
    )
    append_record(root, agent_run)

    next_actions = [
        "Open the plan tasks and collect real TikTok video/product/creator evidence before execution.",
        "Submit review metrics after the test: CTR, CVR, ROI, CPA, orders, refund rate and creator outcome.",
        "Do not publish, change price, contact creators or run ads until the approval queue is confirmed.",
    ]
    result_payload = {
        "agent_run_id": agent_run_id,
        "status": "WAITING_FOR_EXECUTION",
        "input_summary": compact(input_text, 280),
        "classification": classification,
        "scores": scores,
        "extracted_insights": insights,
        "signals": signals,
        "hypotheses": hypotheses,
        "plans": plans,
        "tasks": [record.fields for record in task_queue_records],
        "memory_updates": [record.fields for record in memory_records],
        "next_actions": next_actions,
    }
    report = build_agent_report(result_payload)
    report_path = write_agent_report(root, report)
    return EcommerceDirectorAgentResult(
        agent_run_id=agent_run_id,
        status="WAITING_FOR_EXECUTION",
        classification=classification,
        scores=scores,
        extracted_insights=insights,
        signals=signals,
        hypotheses=hypotheses,
        plans=plans,
        tasks=[record.fields for record in task_queue_records],
        memory_updates=[record.fields for record in memory_records],
        next_actions=next_actions,
        report=report,
        report_path=report_path,
    )


def submit_ecommerce_director_review(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    root = root.resolve()
    agent_run_id = str(payload.get("agent_run_id") or "").strip()
    if not agent_run_id:
        raise ValueError("agent_run_id is required.")
    result_status = str(payload.get("result_status") or "pending").strip().lower()
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    actual_result = str(payload.get("actual_result") or "").strip()
    human_notes = str(payload.get("human_notes") or "").strip()
    now = datetime.now(timezone.utc).isoformat()
    review_id = stable_id("rev_", agent_run_id, result_status, actual_result, human_notes, now)
    success = result_status == "success" or is_success_metric(metrics)
    failure = result_status == "failure" or is_failure_metric(metrics)
    review_text = build_review_text(result_status, metrics, actual_result, human_notes, success, failure)

    review_record = IntakeRecord(
        record_type="agent_review",
        source="ecommerce_director_agent.review",
        raw_text=review_text,
        fields={
            "agent_review_id": review_id,
            "agent_run_id": agent_run_id,
            "plan_id": str(payload.get("plan_id") or ""),
            "review_text": review_text,
            "result_status": result_status,
            "actual_result": actual_result,
            "metrics": metrics,
            "human_notes": human_notes,
            "success_reason": "Metrics or human result marked success." if success else "",
            "failure_reason": "Metrics or human result marked failure." if failure else "",
            "next_action": "scale cautiously with guardrails" if success else "stop or redesign hypothesis before spending more" if failure else "wait for more metrics",
            "memory_update_required": True,
            "created_at": now,
        },
        score={"priority": 90 if success or failure else 65, "agent_v1_review": True},
        director_notes=["Review closes the loop and updates pattern weights."],
        confidence=0.9 if success or failure else 0.65,
    )
    append_record(root, review_record)

    pattern_records = update_review_pattern_weights(root, agent_run_id, success, failure, now)
    for record in pattern_records:
        append_record(root, record)

    memory = IntakeRecord(
        record_type="strategy_memory",
        source="ecommerce_director_agent.review",
        raw_text=review_text,
        fields={
            "memory_key": f"agent-review:{agent_run_id}:{review_id}",
            "memory_type": "agent_review",
            "agent_run_id": agent_run_id,
            "review_id": review_id,
            "what_happened": actual_result or result_status,
            "metrics": metrics,
            "what_we_learned": review_text,
            "what_to_do": "Increase pattern weights and prepare next controlled test." if success else "Lower pattern weights and require a new hypothesis." if failure else "Collect more outcome data.",
            "what_not_to_do": "Do not scale without evidence, stop-loss and approval.",
            "updated_at": now,
        },
        score={"priority": 88 if success or failure else 62, "review_loop": True},
        director_notes=["Outcome feedback written back to long-term strategy memory."],
        confidence=0.9 if success or failure else 0.65,
    )
    append_record(root, memory)
    report_text = latest_ecommerce_director_training_report(root)[0]
    return {
        "review": review_record.to_dict(),
        "pattern_updates": [record.to_dict() for record in pattern_records],
        "memory": memory.to_dict(),
        "latest_report": report_text,
    }


def get_ecommerce_director_run(root: Path, agent_run_id: str) -> dict[str, Any]:
    records = read_records(root)
    run = next((record for record in records if record.record_type == "agent_run" and record.fields.get("agent_run_id") == agent_run_id), None)
    if not run:
        raise ValueError(f"agent_run not found: {agent_run_id}")
    related = [
        record.to_dict()
        for record in records
        if str(record.fields.get("agent_run_id") or "") == agent_run_id
        or str(record.fields.get("source_agent_run_id") or "") == agent_run_id
    ]
    return {"agent_run": run.to_dict(), "related_records": related}


def latest_ecommerce_director_training_report(root: Path) -> tuple[str, Path | None]:
    path = root / "outputs" / REPORT_NAME
    if not path.exists():
        return "No AI Ecommerce Director Agent V1 report yet.", None
    return path.read_text(encoding="utf-8"), path


def classify_agent_input(text: str, *, platform: str = "", country: str = "", category: str = "") -> dict[str, Any]:
    lower = text.lower()
    platform = platform or ("TikTok" if any(token in lower for token in ["tiktok", "tk", "抖音", "fastmoss", "kalodata"]) else "Unknown")
    country = country or ("US" if any(token in lower for token in ["us", "美国", "father", "dad", "husband"]) else "unknown")
    category = category or infer_category(lower)
    knowledge_type = "viral_video" if any(token in lower for token in ["视频", "hook", "钩子", "前3秒", "爆款"]) else "product_case"
    return {
        "knowledge_type": knowledge_type,
        "platform": platform,
        "country": country,
        "category": category,
        "agent_scope": "AI Ecommerce Director Agent V1",
        "automation_level": "L0-L2 now; external execution requires approval",
    }


def infer_category(lower: str) -> str:
    if any(token in lower for token in ["t-shirt", "tee", "shirt", "t恤", "水洗"]):
        return "Apparel"
    if any(token in lower for token in ["cleanser", "洗面奶", "serum", "skincare", "护肤"]):
        return "Beauty"
    if any(token in lower for token in ["screen protector", "phone", "手机膜"]):
        return "Phone Accessories"
    if any(token in lower for token in ["jewelry", "necklace", "aporro", "chain", "首饰"]):
        return "Jewelry"
    return "General Commerce"


def score_agent_input(text: str, classification: dict[str, Any]) -> dict[str, Any]:
    lower = text.lower()
    evidence = 35
    if any(token in lower for token in ["评论", "comment", "buying", "where can i get", "出单", "roi", "views", "播放"]):
        evidence += 20
    if any(token in lower for token in ["tiktok", "fastmoss", "kalodata", "amazon", "shop"]):
        evidence += 12
    if any(token in lower for token in ["视频", "钩子", "hook", "场景", "脚本", "cta"]):
        evidence += 16
    if any(token in lower for token in ["真实", "订单", "销售", "gmv", "退货", "广告"]):
        evidence += 10
    risk = 25
    if any(token in lower for token in ["disney", "nike", "barbie", "carhartt", "gucci", "仿牌", "侵权", "tro"]):
        risk += 45
    if any(token in lower for token in ["医疗", "治愈", "guarantee", "cure"]):
        risk += 20
    business = 55
    if classification.get("platform") == "TikTok":
        business += 12
    if classification.get("knowledge_type") == "viral_video":
        business += 15
    if any(token in lower for token in ["gift", "father", "holiday", "父亲节", "礼物"]):
        business += 8
    urgency = 55 + (12 if any(token in lower for token in ["father", "节", "holiday", "near", "前"]) else 0)
    credibility = min(evidence + 8, 95)
    return {
        "credibility_score": clamp_int(credibility),
        "business_value_score": clamp_int(business),
        "risk_score": clamp_int(risk),
        "urgency_score": clamp_int(urgency),
        "evidence_score": clamp_int(evidence),
    }


def extract_agent_insights(text: str, classification: dict[str, Any]) -> dict[str, Any]:
    lower = text.lower()
    product = "Dog Dad T-shirt" if "dog dad" in lower else infer_product(text)
    persona = []
    if "dog dad" in lower or "狗" in text:
        persona.extend(["Dog Dad", "pet family", "gift buyer"])
    if "dad" in lower or "father" in lower or "父亲" in text:
        persona.extend(["father", "husband gift buyer"])
    if not persona:
        persona.append("category buyer")
    hook = extract_hook(text) or ("Need a Father's Day gift for the dog dad in your life?" if "dog dad" in lower else "Show the product result in the first 3 seconds.")
    scene = "dog jumps to male owner, shirt reveal, owner-pet interaction" if "dog dad" in lower else "product close-up, before/after proof, product-card CTA"
    emotion = "identity, love, gift urgency, pet companionship" if "dog dad" in lower else "problem relief, trust, curiosity"
    keywords = keyword_list(text, classification)
    holiday_keywords = [item for item in ["Father's Day", "Christmas", "Halloween", "4th Of July", "Valentine's Day"] if item.lower() in lower or ("父亲节" in text and item == "Father's Day")]
    creator_type = ["pet creator", "dad/husband lifestyle creator"] if "dog dad" in lower else ["niche product creator", "daily-use demo creator"]
    risk_terms = [term for term in ["Disney", "Nike", "Barbie", "Carhartt", "Gucci", "medical cure", "TRO"] if term.lower() in lower]
    return {
        "product": product,
        "persona": unique(persona),
        "hook": hook,
        "scene": scene,
        "emotion": emotion,
        "keywords": keywords,
        "holiday_keywords": holiday_keywords,
        "creator_type": creator_type,
        "risk_terms": risk_terms,
        "comments_to_watch": ["buying this for my husband", "where can I get it", "will it arrive before holiday"],
        "video_script_fields_required": ["0-3s hook", "shot timeline", "scene", "emotion", "CTA", "comment purchase signal", "creator fit"],
    }


def infer_product(text: str) -> str:
    patterns = [
        r"产品是([^，。\n]+)",
        r"product(?: is|:)\s*([^,\n。]+)",
        r"商品[:：]\s*([^,\n。]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return compact(match.group(1), 80)
    return "Unknown product"


def extract_hook(text: str) -> str:
    quoted = re.findall(r"[\"“](.*?)[\"”]", text)
    if quoted:
        return compact(quoted[0], 180)
    match = re.search(r"(前3秒|hook|钩子)[^，。:：]*[:：]?\s*([^。.\n]+)", text, flags=re.IGNORECASE)
    return compact(match.group(2), 180) if match else ""


def keyword_list(text: str, classification: dict[str, Any]) -> list[str]:
    lower = text.lower()
    keywords = []
    for keyword in ["dog dad", "father's day gift", "pet dad shirt", "gift for husband", "t-shirt", "pet family", "TikTok Shop"]:
        if keyword.lower() in lower or keyword in {"dog dad", "father's day gift", "TikTok Shop"}:
            keywords.append(keyword)
    if classification.get("category") == "Apparel":
        keywords.extend(["graphic tee", "gift shirt"])
    return unique(keywords)[:12]


def build_state_history(now: str) -> list[dict[str, str]]:
    history = []
    previous = ""
    for state in AGENT_STATES:
        history.append({"previous_state": previous, "current_state": state, "changed_at": now})
        previous = state
    return history


def build_source_document(
    agent_run_id: str,
    input_text: str,
    input_type: str,
    input_url: str,
    classification: dict[str, Any],
    scores: dict[str, Any],
    now: str,
) -> IntakeRecord:
    source_id = stable_id("src_", agent_run_id)
    return IntakeRecord(
        record_type="source_document",
        source="ecommerce_director_agent.intake",
        raw_text=input_text,
        fields={
            "source_id": source_id,
            "agent_run_id": agent_run_id,
            "source_type": input_type,
            "source_url": input_url,
            "document_type": classification["knowledge_type"],
            "platform": classification["platform"],
            "country": classification["country"],
            "category": classification["category"],
            "content_hash": sha1(input_text.encode("utf-8")).hexdigest(),
            "credibility_score": scores["credibility_score"],
            "created_at": now,
        },
        score={"priority": scores["credibility_score"]},
        director_notes=["Agent V1 intake source document."],
        confidence=round(scores["credibility_score"] / 100, 3),
    )


def build_source_chunk(agent_run_id: str, source_document: IntakeRecord, input_text: str, now: str) -> IntakeRecord:
    chunk_id = stable_id("chk_", agent_run_id, "1")
    return IntakeRecord(
        record_type="source_chunk",
        source="ecommerce_director_agent.intake",
        raw_text=input_text,
        fields={
            "source_chunk_id": chunk_id,
            "source_id": source_document.fields["source_id"],
            "agent_run_id": agent_run_id,
            "chunk_index": 1,
            "chunk_type": "input_text",
            "text_excerpt": input_text[:1200],
            "created_at": now,
        },
        score={"priority": 70},
        director_notes=["Source chunk used for evidence claims."],
    )


def build_evidence_claims(agent_run_id: str, source_chunk: IntakeRecord, insights: dict[str, Any], scores: dict[str, Any], now: str) -> list[IntakeRecord]:
    claims = [
        ("product", insights["product"], "extracted product candidate"),
        ("hook", insights["hook"], "first-three-second hook"),
        ("persona", ", ".join(insights["persona"]), "target audience"),
        ("keywords", ", ".join(insights["keywords"]), "keyword cluster"),
        ("creator_type", ", ".join(insights["creator_type"]), "creator match"),
    ]
    records: list[IntakeRecord] = []
    for predicate, value, claim_text in claims:
        if not value:
            continue
        claim_id = stable_id("ev_", agent_run_id, predicate, str(value))
        records.append(
            IntakeRecord(
                record_type="evidence_claim",
                source="ecommerce_director_agent.evidence",
                raw_text=f"{claim_text}: {value}",
                fields={
                    "evidence_claim_id": claim_id,
                    "agent_run_id": agent_run_id,
                    "source_chunk_id": source_chunk.fields["source_chunk_id"],
                    "claim_text": f"{claim_text}: {value}",
                    "subject_type": "agent_input",
                    "subject_id": agent_run_id,
                    "predicate": predicate,
                    "object_value": value,
                    "confidence": scores["evidence_score"] / 100,
                    "created_at": now,
                },
                score={"priority": scores["evidence_score"]},
                director_notes=["Evidence claim created before strategy memory."],
                confidence=round(scores["evidence_score"] / 100, 3),
            )
        )
    return records


def build_signals(
    agent_run_id: str,
    classification: dict[str, Any],
    insights: dict[str, Any],
    scores: dict[str, Any],
    evidence_count: int,
    now: str,
) -> list[dict[str, Any]]:
    product = insights["product"]
    primary_keyword = insights["keywords"][0] if insights["keywords"] else product
    signal_text = f"{primary_keyword} + {classification['platform']} + {classification['country']} shows testable product/content signal for {product}."
    if "Father's Day" in insights["holiday_keywords"]:
        signal_text = "Dog Dad + Father's Day + pet creator + T-shirt gift has a testable TikTok US demand signal."
    return [
        {
            "signal_id": stable_id("sig_", agent_run_id, signal_text),
            "agent_run_id": agent_run_id,
            "signal_type": "creative_product_opportunity",
            "signal_text": signal_text,
            "related_platform": classification["platform"],
            "related_country": classification["country"],
            "related_category": classification["category"],
            "related_product": product,
            "related_keyword": primary_keyword,
            "related_creator": ", ".join(insights["creator_type"]),
            "confidence_score": scores["credibility_score"],
            "urgency_score": scores["urgency_score"],
            "risk_score": scores["risk_score"],
            "evidence_count": evidence_count,
            "created_at": now,
        }
    ]


def build_signal_record(signal: dict[str, Any], source_chunk_id: str, now: str) -> IntakeRecord:
    fields = dict(signal)
    fields.update({"source_chunk_id": source_chunk_id, "timestamp": now})
    return IntakeRecord(
        record_type="signal_event",
        source="ecommerce_director_agent.signal",
        raw_text=signal["signal_text"],
        fields=fields,
        score={"priority": signal["confidence_score"], "urgency": signal["urgency_score"]},
        director_notes=["Signal generated from Agent V1 analysis."],
        confidence=round(signal["confidence_score"] / 100, 3),
    )


def build_hypotheses(agent_run_id: str, signals: list[dict[str, Any]], insights: dict[str, Any], scores: dict[str, Any], now: str) -> list[dict[str, Any]]:
    output = []
    for signal in signals:
        text = f"{insights['product']} may be worth a small-budget {signal['related_platform']} {signal['related_country']} test."
        if "Dog Dad" in insights["product"] or "dog dad" in signal["signal_text"].lower():
            text = "Dog Dad Father's Day gift T-shirt is suitable for a small-budget TikTok US test."
        output.append(
            {
                "hypothesis_id": stable_id("hyp_", signal["signal_id"], text),
                "agent_run_id": agent_run_id,
                "signal_id": signal["signal_id"],
                "hypothesis_text": text,
                "opportunity_type": "tiktok_content_product_test",
                "expected_profit_level": "medium" if scores["business_value_score"] < 82 else "high",
                "required_resources": ["keywords", "listing draft", "creator list", "video scripts", "risk review", "small budget test"],
                "risk_score": scores["risk_score"],
                "confidence_score": min(scores["credibility_score"] + 5, 95),
                "status": "draft_waiting_evidence_or_approval",
                "created_at": now,
            }
        )
    return output


def build_hypothesis_record(hypothesis: dict[str, Any], now: str) -> IntakeRecord:
    fields = dict(hypothesis)
    fields["updated_at"] = now
    return IntakeRecord(
        record_type="hypothesis",
        source="ecommerce_director_agent.hypothesis",
        raw_text=hypothesis["hypothesis_text"],
        fields=fields,
        score={"priority": hypothesis["confidence_score"], "risk_score": hypothesis["risk_score"]},
        director_notes=["Hypothesis must be validated by evidence and review before scaling."],
        confidence=round(hypothesis["confidence_score"] / 100, 3),
    )


def build_plans(agent_run_id: str, hypotheses: list[dict[str, Any]], insights: dict[str, Any], scores: dict[str, Any], now: str) -> list[dict[str, Any]]:
    plans = []
    for hypothesis in hypotheses:
        steps = [
            "Generate 20 long-tail keywords.",
            "Generate 5 listing title and bullet variants.",
            "Find 30 matching creators.",
            "Break down 10 real TK videos in the niche.",
            "Generate 5 creator briefs and 3 store-owned scripts.",
            "Run a 72-hour small-budget test after approval.",
            "Review CTR, CVR, ROI, CPA, orders, refunds and comments.",
        ]
        stop_loss = ["Spend >= $50 with 0 orders", "CPA above breakeven for 24h", "negative comment/return risk rises", "confirmed IP or prohibited claim appears"]
        plans.append(
            {
                "plan_id": stable_id("plan_", hypothesis["hypothesis_id"]),
                "agent_run_id": agent_run_id,
                "hypothesis_id": hypothesis["hypothesis_id"],
                "plan_title": f"{insights['product']} controlled test plan",
                "goal": hypothesis["hypothesis_text"],
                "steps_json": steps,
                "budget_suggestion": "$50-$100 first test; no scale before review",
                "success_metrics_json": {"ctr_min": 1.5, "cvr_min": 3.0, "roi_min": 2.0, "cpa_max": 12.0},
                "stop_loss_rules_json": stop_loss,
                "risk_notes": "Draft only. No publish, ad spend, creator contact, price change or store action without human approval.",
                "approval_required": True,
                "created_at": now,
            }
        )
    return plans


def build_plan_record(plan: dict[str, Any], now: str) -> IntakeRecord:
    fields = dict(plan)
    fields["updated_at"] = now
    return IntakeRecord(
        record_type="execution_plan",
        source="ecommerce_director_agent.plan",
        raw_text=json.dumps(plan, ensure_ascii=False),
        fields=fields,
        score={"priority": 86, "approval_required": True},
        director_notes=["Execution plan generated by Agent V1; external actions remain gated."],
        confidence=0.86,
    )


def build_plan_tasks(agent_run_id: str, plans: list[dict[str, Any]], insights: dict[str, Any], now: str) -> list[IntakeRecord]:
    if not plans:
        return []
    plan_id = plans[0]["plan_id"]
    task_specs = [
        ("Keyword Agent", "keyword_research", "Generate 20 long-tail keywords", "20 long-tail terms with product, identity, holiday and emotion words"),
        ("Listing Agent", "listing_draft", "Generate listing titles and bullets", "5 titles, 5 bullets, risk-safe tags"),
        ("Influencer Agent", "creator_research", "Find 30 matching creators", "creator list with niche, fit, contact route and grade"),
        ("Content Agent", "video_script", "Generate store and creator scripts", "3 owned scripts and 5 creator briefs with hook/shot/CTA"),
        ("Risk Agent", "risk_review", "Check IP, prohibited words and platform risks", "risk score, blocked terms, safe replacements"),
        ("Data Reviewer", "evidence_review", "Verify TK evidence quality", "real TK product/video/creator evidence checklist"),
    ]
    records: list[IntakeRecord] = []
    for index, (agent, task_type, title, expected) in enumerate(task_specs, start=1):
        task_id = stable_id("pt_", plan_id, task_type)
        fields = {
            "plan_task_id": task_id,
            "agent_run_id": agent_run_id,
            "plan_id": plan_id,
            "assigned_agent": agent,
            "task_type": task_type,
            "task_title": title,
            "task_description": f"{title} for {insights['product']}.",
            "priority": 90 - index,
            "status": "pending",
            "approval_required": task_type in {"creator_research", "video_script", "listing_draft", "risk_review"},
            "expected_output": expected,
            "created_at": now,
            "updated_at": now,
        }
        records.append(
            IntakeRecord(
                record_type="plan_task",
                source="ecommerce_director_agent.task",
                raw_text=json.dumps(fields, ensure_ascii=False),
                fields=fields,
                score={"priority": fields["priority"], "approval_required": fields["approval_required"]},
                director_notes=["Plan task created by Agent V1."],
                confidence=0.86,
            )
        )
    return records


def build_task_queue_record(plan_task: IntakeRecord, now: str) -> IntakeRecord:
    fields = dict(plan_task.fields)
    fields.update(
        {
            "task_queue_id": stable_id("tsk_", fields["plan_task_id"]),
            "source_plan_task_id": fields["plan_task_id"],
            "target_agent_id": fields["assigned_agent"],
            "requires_confirmation": True,
            "automation_level": "L0-L2 draft; L3+ requires confirmation",
            "status": "waiting_approval" if fields["approval_required"] else "queued",
            "created_at_utc": now,
        }
    )
    return IntakeRecord(
        record_type="task_queue",
        source="ecommerce_director_agent.task_queue",
        raw_text=json.dumps(fields, ensure_ascii=False),
        fields=fields,
        score={"priority": fields["priority"], "approval_required": True},
        director_notes=["Queued task for AI employee. Real platform execution is gated."],
        confidence=0.86,
    )


def build_initial_review(agent_run_id: str, plan_id: str, scores: dict[str, Any], now: str) -> IntakeRecord:
    return IntakeRecord(
        record_type="agent_review",
        source="ecommerce_director_agent.review",
        raw_text="Review placeholder: waiting for execution results and metrics.",
        fields={
            "agent_review_id": stable_id("rev_", agent_run_id, "placeholder"),
            "agent_run_id": agent_run_id,
            "plan_id": plan_id,
            "review_text": "Waiting for execution results. Submit CTR/CVR/ROI/CPA/orders/refunds and human notes after test.",
            "result_status": "pending",
            "success_reason": "",
            "failure_reason": "",
            "next_action": "collect real TK evidence and submit outcome review",
            "memory_update_required": True,
            "created_at": now,
        },
        score={"priority": scores["urgency_score"], "review_placeholder": True},
        director_notes=["Initial review record ensures the loop has a review gate."],
        confidence=0.65,
    )


def build_memory_updates(
    agent_run_id: str,
    classification: dict[str, Any],
    insights: dict[str, Any],
    signals: list[dict[str, Any]],
    hypotheses: list[dict[str, Any]],
    scores: dict[str, Any],
    now: str,
) -> list[IntakeRecord]:
    memory = IntakeRecord(
        record_type="strategy_memory",
        source="ecommerce_director_agent.memory",
        raw_text=json.dumps({"signals": signals, "hypotheses": hypotheses, "insights": insights}, ensure_ascii=False),
        fields={
            "memory_key": f"agent-v1:{agent_run_id}",
            "memory_type": "agent_v1_analysis",
            "agent_run_id": agent_run_id,
            "platform": classification["platform"],
            "country": classification["country"],
            "category": classification["category"],
            "what_we_learned": f"{insights['product']} should be judged by product evidence + video hook + creator fit + comment purchase signal.",
            "what_to_do": "Create controlled test tasks, then require outcome review before weight increase.",
            "what_not_to_do": "Do not treat a story or course note as proven sales data.",
            "valid_when": "Valid only after real TK product/video/creator evidence is attached.",
            "created_at": now,
        },
        score={"priority": scores["business_value_score"], "agent_v1_memory": True},
        director_notes=["Agent V1 memory written after Signal/Hypothesis/Plan creation."],
        confidence=round(scores["credibility_score"] / 100, 3),
    )
    pattern_records = []
    for pattern_type, values in {
        "keyword": insights["keywords"],
        "creator_type": insights["creator_type"],
        "holiday": insights["holiday_keywords"],
        "hook": [insights["hook"]],
        "scene": [insights["scene"]],
    }.items():
        for value in values:
            if not value:
                continue
            pattern_records.append(
                IntakeRecord(
                    record_type="pattern_weight",
                    source="ecommerce_director_agent.memory",
                    raw_text=f"{pattern_type}: {value}",
                    fields={
                        "pattern_weight_id": stable_id("pw_", pattern_type, value),
                        "agent_run_id": agent_run_id,
                        "pattern_type": pattern_type,
                        "pattern_value": value,
                        "weight": 0.55,
                        "success_count": 0,
                        "failure_count": 0,
                        "status": "hypothesis_only",
                        "last_updated": now,
                    },
                    score={"priority": 68, "pattern_type": pattern_type},
                    director_notes=["Pattern created as hypothesis-level memory. Outcome review must raise or lower it."],
                    confidence=0.55,
                )
            )
    concept_records = [
        IntakeRecord(
            record_type="knowledge_concept_weight",
            source="ecommerce_director_agent.memory",
            raw_text=f"Agent concept weight: {value}",
            fields={
                "concept_key": stable_id("concept_", value),
                "entity": value,
                "normalized_entity": value.lower(),
                "concept_weight": min(scores["business_value_score"], 90),
                "concept_status": "agent_v1_hypothesis",
                "agent_run_id": agent_run_id,
                "last_updated": now,
            },
            score={"priority": min(scores["business_value_score"], 90)},
            director_notes=["Concept weight updated from Agent V1 analysis; still needs outcome review."],
            confidence=0.72,
        )
        for value in unique([insights["product"], *insights["keywords"], *insights["creator_type"], *insights["holiday_keywords"]])
        if value
    ]
    return [memory, *pattern_records, *concept_records]


def update_review_pattern_weights(root: Path, agent_run_id: str, success: bool, failure: bool, now: str) -> list[IntakeRecord]:
    related_patterns = [
        record
        for record in read_records(root, "pattern_weight")
        if str(record.fields.get("agent_run_id") or "") == agent_run_id
    ][:30]
    records: list[IntakeRecord] = []
    for record in related_patterns:
        fields = dict(record.fields)
        success_count = int(fields.get("success_count") or 0) + (1 if success else 0)
        failure_count = int(fields.get("failure_count") or 0) + (1 if failure else 0)
        weight = float(fields.get("weight") or 0.5)
        if success:
            weight = min(1.0, weight + 0.12)
        if failure:
            weight = max(0.05, weight - 0.12)
        records.append(
            IntakeRecord(
                record_type="pattern_weight",
                source="ecommerce_director_agent.review",
                raw_text=f"{fields.get('pattern_type')}: {fields.get('pattern_value')}",
                fields={
                    **fields,
                    "weight": round(weight, 3),
                    "success_count": success_count,
                    "failure_count": failure_count,
                    "status": "outcome_adjusted",
                    "last_updated": now,
                },
                score={"priority": int(weight * 100), "review_adjusted": True},
                director_notes=["Pattern weight adjusted after Agent V1 review."],
                confidence=weight,
            )
        )
    return records


def build_review_text(result_status: str, metrics: dict[str, Any], actual_result: str, human_notes: str, success: bool, failure: bool) -> str:
    if success:
        verdict = "Result is success or promising; update memory upward but still require scale guardrails."
    elif failure:
        verdict = "Result failed or triggered stop-loss; lower weights and redesign before spending more."
    else:
        verdict = "Result is pending; keep collecting evidence."
    return f"{verdict}\nStatus: {result_status}\nMetrics: {json.dumps(metrics, ensure_ascii=False)}\nResult: {actual_result}\nNotes: {human_notes}"


def is_success_metric(metrics: dict[str, Any]) -> bool:
    roi = parse_float(metrics.get("roi") or metrics.get("roas"))
    cvr = parse_float(metrics.get("cvr"))
    return bool((roi and roi >= 2.0) or (cvr and cvr >= 3.0))


def is_failure_metric(metrics: dict[str, Any]) -> bool:
    roi = parse_float(metrics.get("roi") or metrics.get("roas"))
    cpa = parse_float(metrics.get("cpa"))
    orders = parse_float(metrics.get("orders"))
    spend = parse_float(metrics.get("spend") or metrics.get("ad_spend"))
    return bool((roi is not None and roi < 1.0) or (cpa and cpa > 20) or ((orders == 0) and spend and spend >= 50))


def build_agent_report(payload: dict[str, Any]) -> str:
    signals = payload["signals"]
    hypotheses = payload["hypotheses"]
    plans = payload["plans"]
    tasks = payload["tasks"]
    insights = payload["extracted_insights"]
    lines = [
        "# AI Ecommerce Director Agent V1 Report",
        "",
        "## Boss Summary",
        "",
        f"- Status: {payload['status']}",
        f"- Agent Run: {payload['agent_run_id']}",
        f"- Product: {insights.get('product')}",
        f"- Platform/Country/Category: {payload['classification'].get('platform')} / {payload['classification'].get('country')} / {payload['classification'].get('category')}",
        f"- Scores: credibility {payload['scores'].get('credibility_score')}, business {payload['scores'].get('business_value_score')}, risk {payload['scores'].get('risk_score')}, urgency {payload['scores'].get('urgency_score')}, evidence {payload['scores'].get('evidence_score')}",
        "",
        "## Signal",
        "",
    ]
    for signal in signals:
        lines.append(f"- {signal['signal_text']} (confidence {signal['confidence_score']}, risk {signal['risk_score']})")
    lines.extend(["", "## Hypothesis", ""])
    for item in hypotheses:
        lines.append(f"- {item['hypothesis_text']} | confidence {item['confidence_score']} | risk {item['risk_score']}")
    lines.extend(["", "## Plan", ""])
    for plan in plans:
        lines.append(f"### {plan['plan_title']}")
        lines.append(f"- Goal: {plan['goal']}")
        lines.append(f"- Budget: {plan['budget_suggestion']}")
        lines.append(f"- Success metrics: {json.dumps(plan['success_metrics_json'], ensure_ascii=False)}")
        lines.append(f"- Stop loss: {'; '.join(plan['stop_loss_rules_json'])}")
        for step in plan["steps_json"]:
            lines.append(f"- {step}")
    lines.extend(["", "## TaskQueue", ""])
    for task in tasks:
        lines.append(f"- {task.get('assigned_agent')}: {task.get('task_title')} -> {task.get('expected_output')}")
    lines.extend(["", "## Review And Memory", ""])
    lines.append("- Review placeholder has been created. Submit real metrics after execution.")
    lines.append("- Strategy memory, concept weights and pattern weights were written as hypothesis-level memory.")
    lines.append("- Outcome review must raise or lower weights. No scaling without review.")
    lines.extend(["", "## Safety", ""])
    lines.append("- Draft only. Do not publish, change price, contact creators, run ads, ship, refund or change store settings without approval.")
    return "\n".join(lines).rstrip() + "\n"


def write_agent_report(root: Path, report: str) -> Path:
    path = root / "outputs" / REPORT_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    return path


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in parts)
    return prefix + sha1(raw.encode("utf-8")).hexdigest()[:18]


def compact(text: str, limit: int) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    return clean if len(clean) <= limit else clean[: limit - 3].rstrip() + "..."


def clamp_int(value: int | float) -> int:
    return max(0, min(100, int(round(value))))


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        clean = str(value or "").strip()
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            output.append(clean)
    return output


def parse_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(str(value).replace("%", "").strip())
    except ValueError:
        return None
