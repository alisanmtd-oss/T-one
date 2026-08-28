from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .storage import append_record, read_records
from .types import IntakeRecord


AUTONOMOUS_LOOP_CONFIG = Path("config") / "autonomous_loop.json"
AUTONOMOUS_LOOP_REPORT_PREFIX = "autonomous_loop"
AUTONOMOUS_LOOP_STATE_PREFIX = "autonomous_loop_state"

RISK_RECORD_TYPES = {
    "policy_diff",
    "enforcement_event",
    "account_health",
    "ip_image_risk",
    "compliance_term",
    "banned_term",
    "claim_requirement",
    "content_rights_asset",
}

EXTERNAL_ACTION_FAMILIES = {
    "publish_or_update_listing",
    "creator_outreach",
    "ad_budget_test",
    "price_or_discount_test",
    "video_publish_test",
    "inventory_or_supply_action",
    "appeal_or_policy_action",
}


@dataclass(slots=True)
class LoopSignal:
    signal_id: str
    signal_type: str
    object_id: str
    object_label: str
    source_record_id: str
    source_record_type: str
    platform: str
    country: str
    delta: float
    velocity: float
    acceleration: float
    signal_strength: float
    confidence_score: float
    risk_score: float
    evidence_count: int
    time_sensitivity: float
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type,
            "object_id": self.object_id,
            "object_label": self.object_label,
            "source_record_id": self.source_record_id,
            "source_record_type": self.source_record_type,
            "platform": self.platform,
            "country": self.country,
            "delta": self.delta,
            "velocity": self.velocity,
            "acceleration": self.acceleration,
            "signal_strength": self.signal_strength,
            "confidence_score": self.confidence_score,
            "risk_score": self.risk_score,
            "evidence_count": self.evidence_count,
            "time_sensitivity": self.time_sensitivity,
            "summary": self.summary,
        }


@dataclass(slots=True)
class LoopHypothesis:
    hypothesis_id: str
    opportunity_type: str
    action_family: str
    subject_type: str
    subject_id: str
    subject_label: str
    platform: str
    country: str
    hypothesis: str
    evidence_signal_ids: list[str]
    expected_profit: float
    confidence_score: float
    risk_score: float
    time_sensitivity: float
    priority_score: float
    requires_confirmation: bool
    guardrail_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "opportunity_type": self.opportunity_type,
            "action_family": self.action_family,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "subject_label": self.subject_label,
            "platform": self.platform,
            "country": self.country,
            "hypothesis": self.hypothesis,
            "evidence_signal_ids": self.evidence_signal_ids,
            "expected_profit": self.expected_profit,
            "confidence_score": self.confidence_score,
            "risk_score": self.risk_score,
            "time_sensitivity": self.time_sensitivity,
            "priority_score": self.priority_score,
            "requires_confirmation": self.requires_confirmation,
            "guardrail_reason": self.guardrail_reason,
        }


@dataclass(slots=True)
class AutonomousLoopResult:
    run_id: str
    run_at_utc: str
    scheduler_tasks: list[IntakeRecord]
    signals: list[LoopSignal]
    hypotheses: list[LoopHypothesis]
    experiments: list[IntakeRecord]
    execution_tasks: list[IntakeRecord]
    outcome_memories: list[IntakeRecord]
    priority_backlog: list[dict[str, Any]]
    report: str
    report_path: Path
    state_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "run_at_utc": self.run_at_utc,
            "scheduler_tasks": [record.to_dict() for record in self.scheduler_tasks],
            "signals": [signal.to_dict() for signal in self.signals],
            "hypotheses": [item.to_dict() for item in self.hypotheses],
            "experiments": [record.to_dict() for record in self.experiments],
            "execution_tasks": [record.to_dict() for record in self.execution_tasks],
            "outcome_memories": [record.to_dict() for record in self.outcome_memories],
            "priority_backlog": self.priority_backlog,
            "report": self.report,
            "report_path": str(self.report_path),
            "state_path": str(self.state_path),
        }


def run_autonomous_loop(root: Path, run_at: str | None = None) -> AutonomousLoopResult:
    root = root.resolve()
    now = parse_run_at(run_at)
    run_id = stable_id("loop_", now.isoformat())
    config = load_autonomous_loop_config(root)
    if not config.get("enabled", True):
        report = "# Autonomous Commerce Loop\n\nStatus: disabled.\n"
        report_path = write_loop_report(root, now, report)
        state_path = write_loop_state(root, now, {"run_id": run_id, "disabled": True})
        return AutonomousLoopResult(run_id, now.isoformat(), [], [], [], [], [], [], [], report, report_path, state_path)

    records = read_records(root)
    scheduler_tasks = build_due_scheduler_tasks(root, now, config)
    for task in scheduler_tasks:
        append_record(root, task)

    signals = detect_signals(records, now, config)
    learning_events = [build_signal_learning_event(signal, now) for signal in signals]
    for event in learning_events:
        append_record(root, event)

    hypotheses = build_hypotheses(signals, config)
    experiments = plan_experiments(hypotheses, now, config)
    for experiment in experiments:
        append_record(root, experiment)

    execution_tasks = build_execution_tasks(hypotheses, experiments, now, config)
    for task in execution_tasks:
        append_record(root, task)

    outcome_memories = evaluate_outcomes(root, now)
    priority_backlog = rebalance_priorities(hypotheses, execution_tasks, scheduler_tasks, config)
    loop_memory = build_loop_strategy_memory(run_id, now, scheduler_tasks, signals, hypotheses, experiments, priority_backlog)
    append_record(root, loop_memory)

    report = build_loop_report(now, scheduler_tasks, signals, hypotheses, experiments, execution_tasks, outcome_memories, priority_backlog)
    report_path = write_loop_report(root, now, report)
    state_path = write_loop_state(
        root,
        now,
        {
            "run_id": run_id,
            "run_at_utc": now.isoformat(),
            "scheduler_tasks": [record.to_dict() for record in scheduler_tasks],
            "signals": [signal.to_dict() for signal in signals],
            "hypotheses": [item.to_dict() for item in hypotheses],
            "experiments": [record.to_dict() for record in experiments],
            "execution_tasks": [record.to_dict() for record in execution_tasks],
            "outcome_memories": [record.to_dict() for record in outcome_memories],
            "priority_backlog": priority_backlog,
        },
    )
    return AutonomousLoopResult(
        run_id=run_id,
        run_at_utc=now.isoformat(),
        scheduler_tasks=scheduler_tasks,
        signals=signals,
        hypotheses=hypotheses,
        experiments=experiments,
        execution_tasks=execution_tasks,
        outcome_memories=outcome_memories,
        priority_backlog=priority_backlog,
        report=report,
        report_path=report_path,
        state_path=state_path,
    )


def load_autonomous_loop_config(root: Path) -> dict[str, Any]:
    path = root / AUTONOMOUS_LOOP_CONFIG
    if not path.exists():
        return default_autonomous_loop_config()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default_autonomous_loop_config()
    if not isinstance(payload, dict):
        return default_autonomous_loop_config()
    default = default_autonomous_loop_config()
    merged = {**default, **payload}
    if not isinstance(merged.get("scheduler_jobs"), list):
        merged["scheduler_jobs"] = default["scheduler_jobs"]
    if not isinstance(merged.get("guardrails"), dict):
        merged["guardrails"] = default["guardrails"]
    return merged


def default_autonomous_loop_config() -> dict[str, Any]:
    return {
        "enabled": True,
        "max_signals": 30,
        "max_hypotheses": 12,
        "max_experiments": 6,
        "signal_threshold": 55,
        "allow_external_auto_execute": False,
        "guardrails": {
            "max_experiment_budget_usd": 50,
            "max_daily_loss_usd": 0,
            "max_category_risk_share": 0.25,
            "policy_pause_risk_score": 80,
            "ip_pause_risk_score": 75,
        },
        "scheduler_jobs": [
            {
                "id": "collect_tiktok_top_ads",
                "name": "TikTok Top Ads and viral videos",
                "cadence_hours": 2,
                "priority": 95,
                "target_agent_id": "agn_viral_content_intelligence",
                "payload": {"source_family": "TikTok", "record_type": "creative_snapshot", "read_only": True},
            },
            {
                "id": "collect_tiktok_top_products",
                "name": "TikTok Shop buyer-side top products",
                "cadence_hours": 2,
                "priority": 94,
                "target_agent_id": "agn_competitor_intelligence",
                "payload": {"source_family": "TikTok Shop", "record_type": "platform_ranking_signal", "read_only": True},
            },
            {
                "id": "refresh_keyword_trends",
                "name": "Keyword trend snapshots",
                "cadence_hours": 4,
                "priority": 88,
                "target_agent_id": "agn_keyword_intelligence",
                "payload": {"record_type": "query_snapshot", "read_only": True},
            },
            {
                "id": "refresh_creator_growth",
                "name": "Creator growth and cooperation watchlist",
                "cadence_hours": 6,
                "priority": 86,
                "target_agent_id": "agn_influencer_intelligence",
                "payload": {"record_type": "creator_spike_event", "read_only": True},
            },
            {
                "id": "refresh_competitor_price",
                "name": "Competitor listing and price movement",
                "cadence_hours": 6,
                "priority": 84,
                "target_agent_id": "agn_competitor_intelligence",
                "payload": {"record_type": "competitor_snapshot", "read_only": True},
            },
            {
                "id": "refresh_review_sentiment",
                "name": "Review, return, and complaint intelligence",
                "cadence_hours": 24,
                "priority": 82,
                "target_agent_id": "agn_risk_intelligence",
                "payload": {"record_type": "review_insight", "read_only": True},
            },
            {
                "id": "diff_platform_policies",
                "name": "Official platform policy diff",
                "cadence_hours": 24,
                "priority": 90,
                "target_agent_id": "agn_risk_intelligence",
                "payload": {"record_type": "policy_diff", "read_only": True},
            },
            {
                "id": "refresh_account_health",
                "name": "Own-store account health and appeal watch",
                "cadence_hours": 24,
                "priority": 89,
                "target_agent_id": "agn_risk_intelligence",
                "payload": {"record_type": "account_health", "read_only": True},
            },
        ],
    }


def build_due_scheduler_tasks(root: Path, now: datetime, config: dict[str, Any]) -> list[IntakeRecord]:
    existing_tasks = read_records(root, "task_queue")
    tasks: list[IntakeRecord] = []
    for job in config.get("scheduler_jobs", []):
        if not isinstance(job, dict) or not job.get("id"):
            continue
        if not job.get("enabled", True):
            continue
        cadence_hours = max(float(job.get("cadence_hours") or 24), 0.25)
        if not scheduler_job_due(existing_tasks, str(job["id"]), now, cadence_hours):
            continue
        bucket = int(now.timestamp() // (cadence_hours * 3600))
        task_id = stable_id("tsk_", "scheduler", job["id"], bucket)
        payload = dict(job.get("payload") or {})
        payload.update(
            {
                "scheduler_job_id": job["id"],
                "scheduler_job_name": job.get("name") or job["id"],
                "cadence_hours": cadence_hours,
                "safe_mode": True,
                "instruction": "Collect or request read-only evidence only. Do not login-bypass, publish, edit, pay, message, ship, or change settings.",
            }
        )
        tasks.append(
            IntakeRecord(
                record_type="task_queue",
                fields={
                    "task_queue_id": task_id,
                    "task_type": str(job["id"]),
                    "source_event_inbox_id": f"autonomous_loop:{bucket}",
                    "target_agent_id": str(job.get("target_agent_id") or "agn_ecommerce_director_v1"),
                    "priority": int(job.get("priority") or 70),
                    "payload": payload,
                    "status": "queued",
                    "created_at_utc": now.isoformat(),
                    "not_before_utc": now.isoformat(),
                },
                raw_text=json.dumps(payload, ensure_ascii=False),
                source="autonomous_loop.scheduler",
                score={"priority": int(job.get("priority") or 70), "loop_stage": "scheduler"},
                director_notes=[f"Scheduled {job.get('name') or job['id']} as a safe read-only task."],
            )
        )
    return tasks


def scheduler_job_due(existing_tasks: list[IntakeRecord], job_id: str, now: datetime, cadence_hours: float) -> bool:
    latest: datetime | None = None
    for record in existing_tasks:
        fields = record.fields
        if str(fields.get("task_type") or "") != job_id:
            continue
        payload = fields.get("payload") if isinstance(fields.get("payload"), dict) else {}
        if payload.get("scheduler_job_id") != job_id:
            continue
        created = parse_datetime(str(fields.get("created_at_utc") or record.created_at))
        if created and (latest is None or created > latest):
            latest = created
    return latest is None or now - latest >= timedelta(hours=cadence_hours)


def detect_signals(records: list[IntakeRecord], now: datetime, config: dict[str, Any]) -> list[LoopSignal]:
    threshold = float(config.get("signal_threshold") or 55)
    candidates: list[LoopSignal] = []
    for record in records:
        signal = signal_from_record(record, now)
        if signal and signal.signal_strength >= threshold:
            candidates.append(signal)
    candidates.sort(key=lambda item: (item.signal_strength, item.confidence_score, item.time_sensitivity), reverse=True)
    return candidates[: int(config.get("max_signals") or 30)]


def signal_from_record(record: IntakeRecord, now: datetime) -> LoopSignal | None:
    fields = record.fields
    signal_type = infer_signal_type(record)
    if not signal_type:
        return None
    priority = number(record.score.get("priority"))
    risk_score = infer_risk_score(record)
    delta = extract_delta(fields, record.raw_text)
    velocity = extract_velocity(fields, priority)
    acceleration = extract_acceleration(fields, delta, velocity)
    confidence = clamp((priority / 100 * 0.65) + (record.confidence * 0.35), 0.05, 0.98)
    time_sensitivity = infer_time_sensitivity(record, now)
    evidence_count = infer_evidence_count(record)
    strength = clamp(priority * 0.52 + abs(delta) * 0.12 + velocity * 18 + time_sensitivity * 10 + evidence_count * 2 - risk_score * 0.18, 0, 100)
    label = record_label(record)
    platform = str(fields.get("platform") or fields.get("marketplace") or fields.get("source_platform") or record.source or "")
    country = str(fields.get("country") or fields.get("market") or fields.get("country_code") or fields.get("shop_region") or "")
    return LoopSignal(
        signal_id=stable_id("sig_", record.record_id, signal_type, label),
        signal_type=signal_type,
        object_id=object_id_for_record(record),
        object_label=label,
        source_record_id=record.record_id,
        source_record_type=record.record_type,
        platform=platform,
        country=country,
        delta=round(delta, 4),
        velocity=round(velocity, 4),
        acceleration=round(acceleration, 4),
        signal_strength=round(strength, 2),
        confidence_score=round(confidence, 3),
        risk_score=round(risk_score, 2),
        evidence_count=evidence_count,
        time_sensitivity=round(time_sensitivity, 3),
        summary=f"{signal_type}: {label} | strength {strength:.1f}, confidence {confidence:.2f}, risk {risk_score:.1f}",
    )


def infer_signal_type(record: IntakeRecord) -> str:
    mapping = {
        "platform_ranking_signal": "product_growth",
        "hot_link": "product_growth",
        "viral_content_signal": "creative_growth",
        "video_breakdown": "creative_pattern",
        "creative_snapshot": "creative_growth",
        "creative_pattern": "creative_pattern",
        "query_snapshot": "keyword_growth",
        "creator_spike_event": "creator_growth",
        "influencer_cooperation": "creator_roi",
        "review_insight": "review_pain",
        "return_rma": "return_pain",
        "refund_record": "refund_pain",
        "store_metric_snapshot": "own_store_metric",
        "policy_diff": "policy_risk",
        "enforcement_event": "account_risk",
        "account_health": "account_risk",
        "ip_image_risk": "ip_risk",
        "compliance_term": "claim_risk",
        "banned_term": "claim_risk",
        "seasonal_event": "seasonality",
    }
    return mapping.get(record.record_type, "")


def build_signal_learning_event(signal: LoopSignal, now: datetime) -> IntakeRecord:
    fields = {
        "learning_event_id": stable_id("evt_", "signal", signal.signal_id),
        "event_type": "signal_detected",
        "source_id": f"src_{signal.source_record_id[:12]}",
        "classification": [signal.signal_type, signal.source_record_type],
        "tags": [signal.platform, signal.country, signal.object_label],
        "entities": [signal.object_id, signal.object_label],
        "knowledge_score": signal.signal_strength,
        "concept_weight_delta": {
            signal.object_label: round(signal.confidence_score * signal.time_sensitivity * (1 - min(signal.risk_score, 95) / 120), 3)
        },
        "affected_agents": affected_agents_for_signal(signal),
        "status": "detected",
        "created_at_utc": now.isoformat(),
    }
    return IntakeRecord(
        record_type="learning_event",
        fields=fields,
        raw_text=json.dumps(signal.to_dict(), ensure_ascii=False),
        source="autonomous_loop.signal_engine",
        score={"priority": int(signal.signal_strength), "loop_stage": "signal_detection"},
        director_notes=[signal.summary],
        confidence=signal.confidence_score,
    )


def build_hypotheses(signals: list[LoopSignal], config: dict[str, Any]) -> list[LoopHypothesis]:
    hypotheses: list[LoopHypothesis] = []
    for signal in signals:
        spec = hypothesis_spec_for_signal(signal)
        if not spec:
            continue
        expected_profit = estimate_profit(signal)
        risk_score = apply_guardrail_risk(signal, spec["action_family"], config)
        confidence = clamp(signal.confidence_score * (1 + signal.evidence_count / 20), 0.05, 0.98)
        time_sensitivity = signal.time_sensitivity
        risk_factor = max(0.05, 1 - risk_score / 100)
        priority_score = round(expected_profit * confidence * time_sensitivity * risk_factor, 2)
        requires_confirmation = spec["action_family"] in EXTERNAL_ACTION_FAMILIES or risk_score >= 60
        guardrail_reason = guardrail_reason_for(signal, spec["action_family"], risk_score, config)
        hypothesis_text = render_hypothesis(signal, spec["opportunity_type"])
        hypotheses.append(
            LoopHypothesis(
                hypothesis_id=stable_id("hyp_", signal.signal_id, spec["action_family"]),
                opportunity_type=spec["opportunity_type"],
                action_family=spec["action_family"],
                subject_type=spec["subject_type"],
                subject_id=signal.object_id,
                subject_label=signal.object_label,
                platform=signal.platform,
                country=signal.country,
                hypothesis=hypothesis_text,
                evidence_signal_ids=[signal.signal_id],
                expected_profit=round(expected_profit, 2),
                confidence_score=round(confidence, 3),
                risk_score=round(risk_score, 2),
                time_sensitivity=round(time_sensitivity, 3),
                priority_score=priority_score,
                requires_confirmation=requires_confirmation,
                guardrail_reason=guardrail_reason,
            )
        )
    hypotheses.sort(key=lambda item: item.priority_score, reverse=True)
    return hypotheses[: int(config.get("max_hypotheses") or 12)]


def hypothesis_spec_for_signal(signal: LoopSignal) -> dict[str, str] | None:
    if signal.signal_type in {"policy_risk", "account_risk", "ip_risk", "claim_risk"}:
        return {
            "opportunity_type": "risk_pause_or_repair",
            "action_family": "appeal_or_policy_action",
            "subject_type": "store",
        }
    if signal.signal_type in {"creative_growth", "creative_pattern"}:
        return {
            "opportunity_type": "creative_test",
            "action_family": "video_publish_test",
            "subject_type": "video",
        }
    if signal.signal_type in {"product_growth", "seasonality"}:
        return {
            "opportunity_type": "product_listing_test",
            "action_family": "publish_or_update_listing",
            "subject_type": "product",
        }
    if signal.signal_type == "keyword_growth":
        return {
            "opportunity_type": "keyword_listing_test",
            "action_family": "publish_or_update_listing",
            "subject_type": "listing",
        }
    if signal.signal_type in {"creator_growth", "creator_roi"}:
        return {
            "opportunity_type": "creator_seed_test",
            "action_family": "creator_outreach",
            "subject_type": "creator",
        }
    if signal.signal_type in {"review_pain", "return_pain", "refund_pain"}:
        return {
            "opportunity_type": "quality_fix_test",
            "action_family": "publish_or_update_listing",
            "subject_type": "product",
        }
    if signal.signal_type == "own_store_metric":
        return {
            "opportunity_type": "budget_pacing_test",
            "action_family": "ad_budget_test",
            "subject_type": "store",
        }
    return None


def plan_experiments(hypotheses: list[LoopHypothesis], now: datetime, config: dict[str, Any]) -> list[IntakeRecord]:
    experiments: list[IntakeRecord] = []
    max_items = int(config.get("max_experiments") or 6)
    for hypothesis in hypotheses[:max_items]:
        status = "draft"
        budget = recommended_budget(hypothesis, config)
        fields = {
            "experiment_id": stable_id("exp_", hypothesis.hypothesis_id),
            "subject_type": hypothesis.subject_type,
            "subject_id": hypothesis.subject_id,
            "hypothesis": hypothesis.hypothesis,
            "action_taken": action_taken_for_hypothesis(hypothesis),
            "owner": "AI Ecommerce Director",
            "status": status,
            "linked_agent_id": "agn_ecommerce_director_v1",
            "budget_limit_usd": budget,
            "cpa_limit_usd": round(max(budget / 5, 5), 2),
            "time_window": "24h watch + 72h decision window",
            "control_group": "current listing/content/creator baseline",
            "variant_group": variant_group_for_hypothesis(hypothesis),
            "stop_loss_rule": stop_loss_rule_for(hypothesis),
            "scale_rule": scale_rule_for(hypothesis),
            "confidence_score": hypothesis.confidence_score,
            "risk_score": hypothesis.risk_score,
            "priority_score": hypothesis.priority_score,
            "requires_confirmation": hypothesis.requires_confirmation,
            "guardrail_reason": hypothesis.guardrail_reason,
            "planned_at_utc": now.isoformat(),
        }
        experiments.append(
            IntakeRecord(
                record_type="experiment_run",
                fields=fields,
                raw_text=json.dumps(hypothesis.to_dict(), ensure_ascii=False),
                source="autonomous_loop.experiment_planner",
                score={"priority": int(min(hypothesis.priority_score, 100)), "loop_stage": "experiment_planning"},
                director_notes=[hypothesis.hypothesis, hypothesis.guardrail_reason],
                confidence=hypothesis.confidence_score,
            )
        )
    return experiments


def build_execution_tasks(
    hypotheses: list[LoopHypothesis],
    experiments: list[IntakeRecord],
    now: datetime,
    config: dict[str, Any],
) -> list[IntakeRecord]:
    allow_external = bool(config.get("allow_external_auto_execute", False))
    experiment_by_id = {str(record.fields.get("experiment_id")): record for record in experiments}
    tasks: list[IntakeRecord] = []
    for hypothesis in hypotheses:
        experiment_id = stable_id("exp_", hypothesis.hypothesis_id)
        experiment = experiment_by_id.get(experiment_id)
        payload = {
            "hypothesis": hypothesis.to_dict(),
            "experiment_id": experiment_id if experiment else "",
            "execution_state_machine": "CREATED -> QUEUED -> RUNNING -> MONITORING -> SUCCESS/FAILED/SCALED/ARCHIVED",
            "allowed_now": "draft_and_queue_only" if hypothesis.requires_confirmation or not allow_external else "low_risk_auto_execute",
            "guardrails": {
                "requires_confirmation": hypothesis.requires_confirmation or not allow_external,
                "max_daily_loss_usd": config.get("guardrails", {}).get("max_daily_loss_usd", 0),
                "risk_score": hypothesis.risk_score,
            },
        }
        status = "waiting_approval" if hypothesis.requires_confirmation or hypothesis.action_family in EXTERNAL_ACTION_FAMILIES else "queued"
        tasks.append(
            IntakeRecord(
                record_type="task_queue",
                fields={
                    "task_queue_id": stable_id("tsk_", "execute", hypothesis.hypothesis_id, now.date().isoformat()),
                    "task_type": f"experiment_{hypothesis.action_family}",
                    "source_event_inbox_id": f"autonomous_loop:{now.date().isoformat()}",
                    "target_agent_id": "agn_ecommerce_director_v1",
                    "priority": int(min(max(hypothesis.priority_score, 1), 100)),
                    "payload": payload,
                    "status": status,
                    "created_at_utc": now.isoformat(),
                    "not_before_utc": now.isoformat(),
                },
                raw_text=json.dumps(payload, ensure_ascii=False),
                source="autonomous_loop.execution_state_machine",
                score={"priority": int(min(max(hypothesis.priority_score, 1), 100)), "loop_stage": "execution_queue"},
                director_notes=[hypothesis.guardrail_reason],
                confidence=hypothesis.confidence_score,
            )
        )
    return tasks


def evaluate_outcomes(root: Path, now: datetime) -> list[IntakeRecord]:
    memories: list[IntakeRecord] = []
    outcomes = read_records(root, "action_outcome")
    outcomes.extend(read_records(root, "execution_result"))
    for outcome in outcomes:
        conclusion = str(outcome.fields.get("conclusion") or outcome.fields.get("outcome") or "").lower()
        if conclusion not in {"won", "lost", "positive", "negative"}:
            continue
        weight_delta = 8 if conclusion in {"won", "positive"} else -6
        memory_key = f"outcome-feedback:{outcome.record_id}:{conclusion}"
        memory = IntakeRecord(
            record_type="strategy_memory",
            fields={
                "memory_key": memory_key,
                "memory_type": "autonomous_outcome_feedback",
                "strategy_stage": "outcome_to_weight_update",
                "recommendation": outcome.fields.get("learning_summary") or f"Outcome {conclusion} should update strategy weights.",
                "valid_when": [f"experiment_id={outcome.fields.get('experiment_id') or ''}", f"metric={outcome.fields.get('metric_name') or outcome.fields.get('action_type') or ''}"],
                "what_not_to_do": ["Do not scale a failed pattern without a new hypothesis and stop-loss rule."],
                "source_outcome_id": outcome.record_id,
                "concept_weight_delta": weight_delta,
                "updated_at_utc": now.isoformat(),
            },
            raw_text=json.dumps(outcome.to_dict(), ensure_ascii=False),
            source="autonomous_loop.outcome_evaluator",
            score={"priority": 84 if weight_delta > 0 else 76, "loop_stage": "reinforcement"},
            director_notes=["Outcome converted into reinforcement memory."],
        )
        append_record(root, memory)
        memories.append(memory)
    return memories


def rebalance_priorities(
    hypotheses: list[LoopHypothesis],
    execution_tasks: list[IntakeRecord],
    scheduler_tasks: list[IntakeRecord],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for hypothesis in hypotheses:
        items.append(
            {
                "kind": "hypothesis",
                "id": hypothesis.hypothesis_id,
                "title": hypothesis.subject_label,
                "platform": hypothesis.platform,
                "priority_score": hypothesis.priority_score,
                "risk_score": hypothesis.risk_score,
                "confidence_score": hypothesis.confidence_score,
                "next_step": "queue experiment with guardrail" if not hypothesis.requires_confirmation else "wait for approval before external action",
            }
        )
    for task in execution_tasks:
        items.append(
            {
                "kind": "task",
                "id": task.fields.get("task_queue_id"),
                "title": task.fields.get("task_type"),
                "priority_score": task.fields.get("priority", 0),
                "risk_score": task.fields.get("payload", {}).get("guardrails", {}).get("risk_score", 0) if isinstance(task.fields.get("payload"), dict) else 0,
                "confidence_score": task.confidence,
                "next_step": task.fields.get("status"),
            }
        )
    for task in scheduler_tasks:
        items.append(
            {
                "kind": "scheduler",
                "id": task.fields.get("task_queue_id"),
                "title": task.fields.get("task_type"),
                "priority_score": task.fields.get("priority", 0),
                "risk_score": 0,
                "confidence_score": 0.8,
                "next_step": "collect read-only evidence",
            }
        )
    items.sort(key=lambda item: float(item.get("priority_score") or 0), reverse=True)
    return items[:10]


def build_loop_strategy_memory(
    run_id: str,
    now: datetime,
    scheduler_tasks: list[IntakeRecord],
    signals: list[LoopSignal],
    hypotheses: list[LoopHypothesis],
    experiments: list[IntakeRecord],
    priority_backlog: list[dict[str, Any]],
) -> IntakeRecord:
    return IntakeRecord(
        record_type="strategy_memory",
        fields={
            "memory_key": f"autonomous-loop:{now.date().isoformat()}:{run_id}",
            "memory_type": "autonomous_loop",
            "strategy_stage": "continuous_learning_and_execution",
            "recommendation": f"Loop generated {len(scheduler_tasks)} scheduler tasks, {len(signals)} signals, {len(hypotheses)} hypotheses, and {len(experiments)} draft experiments.",
            "valid_when": ["Use when deciding the next daily priorities, evidence collection order, or safe experiments."],
            "what_not_to_do": [
                "Do not treat stored knowledge as enough; keep scheduling fresh evidence.",
                "Do not execute external store/platform actions without guardrail approval.",
            ],
            "priority_backlog": priority_backlog,
            "updated_at_utc": now.isoformat(),
        },
        raw_text=json.dumps(
            {
                "scheduler_tasks": [record.fields for record in scheduler_tasks],
                "signals": [signal.to_dict() for signal in signals],
                "hypotheses": [item.to_dict() for item in hypotheses],
                "experiments": [record.fields for record in experiments],
                "priority_backlog": priority_backlog,
            },
            ensure_ascii=False,
        ),
        source="autonomous_loop.priority_rebalancer",
        score={"priority": 88 if signals or hypotheses else 62, "loop_stage": "priority_rebalance"},
        director_notes=["Autonomous loop summary saved as strategy memory."],
    )


def build_loop_report(
    now: datetime,
    scheduler_tasks: list[IntakeRecord],
    signals: list[LoopSignal],
    hypotheses: list[LoopHypothesis],
    experiments: list[IntakeRecord],
    execution_tasks: list[IntakeRecord],
    outcome_memories: list[IntakeRecord],
    priority_backlog: list[dict[str, Any]],
) -> str:
    lines = [
        "# Autonomous Commerce Loop Report",
        "",
        f"Run at UTC: {now.isoformat()}",
        "",
        "## Safety",
        "",
        "- The loop may collect, parse, detect, draft, plan experiments, monitor metrics, and update memory.",
        "- Store-impacting actions stay in task queues with guardrails unless explicitly enabled and low-risk.",
        "- Captcha, login bypass, publishing, price changes, discounts, ads, refunds, shipping, creator messages, payments, app authorization, and store settings are not executed here.",
        "",
        "## Scheduler",
        "",
    ]
    if not scheduler_tasks:
        lines.append("- No due scheduler task in this run.")
    for task in scheduler_tasks:
        lines.append(f"- {task.fields.get('task_type')} | priority {task.fields.get('priority')} | status {task.fields.get('status')}")

    lines.extend(["", "## Signals", ""])
    if not signals:
        lines.append("- No signal above threshold yet.")
    for signal in signals[:12]:
        lines.append(
            f"- {signal.signal_type} | {signal.object_label} | strength {signal.signal_strength} | confidence {signal.confidence_score} | risk {signal.risk_score}"
        )

    lines.extend(["", "## Hypotheses", ""])
    if not hypotheses:
        lines.append("- No hypothesis generated yet.")
    for item in hypotheses[:10]:
        gate = "approval required" if item.requires_confirmation else "auto draft allowed"
        lines.append(f"- {item.hypothesis} | priority {item.priority_score} | {gate}")

    lines.extend(["", "## Draft Experiments", ""])
    if not experiments:
        lines.append("- No draft experiment generated.")
    for experiment in experiments:
        fields = experiment.fields
        lines.append(
            f"- {fields.get('experiment_id')} | {fields.get('subject_type')} | budget ${fields.get('budget_limit_usd')} | stop-loss: {fields.get('stop_loss_rule')}"
        )

    lines.extend(["", "## Execution Queue", ""])
    if not execution_tasks:
        lines.append("- No execution task queued.")
    for task in execution_tasks[:12]:
        lines.append(f"- {task.fields.get('task_type')} | {task.fields.get('status')} | priority {task.fields.get('priority')}")

    lines.extend(["", "## Reinforcement", ""])
    if not outcome_memories:
        lines.append("- No new outcome memory generated.")
    for memory in outcome_memories[:8]:
        lines.append(f"- {memory.fields.get('recommendation')}")

    lines.extend(["", "## Top 10 Priority Backlog", ""])
    if not priority_backlog:
        lines.append("- Backlog is empty.")
    for index, item in enumerate(priority_backlog, start=1):
        lines.append(f"{index}. {item.get('title')} | {item.get('kind')} | score {item.get('priority_score')} | {item.get('next_step')}")
    return "\n".join(lines).rstrip() + "\n"


def latest_autonomous_loop_report(root: Path) -> tuple[str, Path | None]:
    output_dir = root / "outputs"
    paths = sorted(output_dir.glob(f"{AUTONOMOUS_LOOP_REPORT_PREFIX}_*.md"), reverse=True)
    if not paths:
        return "No autonomous loop report yet.", None
    path = paths[0]
    return path.read_text(encoding="utf-8"), path


def write_loop_report(root: Path, now: datetime, content: str) -> Path:
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{AUTONOMOUS_LOOP_REPORT_PREFIX}_{now.date().isoformat()}.md"
    path.write_text(content, encoding="utf-8")
    return path


def write_loop_state(root: Path, now: datetime, payload: dict[str, Any]) -> Path:
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{AUTONOMOUS_LOOP_STATE_PREFIX}_{now.date().isoformat()}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def affected_agents_for_signal(signal: LoopSignal) -> list[str]:
    if signal.signal_type in {"creative_growth", "creative_pattern"}:
        return ["AI Ecommerce Director", "Viral Content Intelligence", "Content Director"]
    if signal.signal_type in {"product_growth", "keyword_growth", "seasonality"}:
        return ["AI Ecommerce Director", "Competitor Intelligence", "Keyword Intelligence", "Listing Intelligence"]
    if signal.signal_type in {"creator_growth", "creator_roi"}:
        return ["AI Ecommerce Director", "Influencer Intelligence"]
    if signal.signal_type.endswith("_risk") or signal.signal_type in {"policy_risk", "account_risk"}:
        return ["AI Ecommerce Director", "Risk Intelligence"]
    return ["AI Ecommerce Director"]


def action_taken_for_hypothesis(hypothesis: LoopHypothesis) -> str:
    if hypothesis.opportunity_type == "creative_test":
        return "Draft a TikTok script variant, creator brief, music/disclosure check, and A/B material test plan."
    if hypothesis.opportunity_type == "product_listing_test":
        return "Draft listing, image brief, keyword set, price band, and small-market test plan."
    if hypothesis.opportunity_type == "keyword_listing_test":
        return "Draft keyword insertion, long-tail title/tag variants, and query snapshot monitoring."
    if hypothesis.opportunity_type == "creator_seed_test":
        return "Draft creator scoring, outreach candidate list, sample rule, and ROI measurement plan."
    if hypothesis.opportunity_type == "quality_fix_test":
        return "Draft product/listing/script fix from review pain and monitor return/refund impact."
    if hypothesis.opportunity_type == "budget_pacing_test":
        return "Draft budget pacing and stop-loss plan from own-store metrics."
    if hypothesis.opportunity_type == "risk_pause_or_repair":
        return "Draft pause, evidence collection, appeal, or policy repair task before any external action."
    return "Draft a controlled experiment plan."


def variant_group_for_hypothesis(hypothesis: LoopHypothesis) -> str:
    variants = {
        "creative_test": "new hook, shot order, CTA, disclosure, and audio-safe variant",
        "product_listing_test": "new title, main-image brief, price band, and platform tag variant",
        "keyword_listing_test": "long-tail keyword and translated query variant",
        "creator_seed_test": "A/B creator niche and brief variant",
        "quality_fix_test": "listing proof point, FAQ, and script clarification variant",
        "budget_pacing_test": "low-budget test cell with stop-loss and ROAS monitor",
        "risk_pause_or_repair": "evidence/appeal repair variant; no public execution until safe",
    }
    return variants.get(hypothesis.opportunity_type, "controlled variant")


def stop_loss_rule_for(hypothesis: LoopHypothesis) -> str:
    if hypothesis.risk_score >= 75:
        return "Stop immediately if policy/IP/account-health risk remains unresolved."
    if hypothesis.action_family == "ad_budget_test":
        return "Stop if CPA exceeds limit, ROAS < 1.0, refund rate rises, or no purchase signal after the test window."
    if hypothesis.action_family == "video_publish_test":
        return "Stop if early views, product-card clicks, or comment sentiment stay below baseline."
    return "Stop if conversion, comments, ranking, or account-health signals are worse than baseline."


def scale_rule_for(hypothesis: LoopHypothesis) -> str:
    if hypothesis.risk_score >= 60:
        return "Do not scale until risk review is clear."
    if hypothesis.action_family == "video_publish_test":
        return "Scale only after view velocity, product-card clicks, purchase-intent comments, and rights/disclosure checks pass."
    if hypothesis.action_family == "publish_or_update_listing":
        return "Scale only after ranking, CTR/CVR, reviews, returns, margin, and inventory pass guardrails."
    return "Scale only after ROI, confidence, and repeatability pass the experiment threshold."


def recommended_budget(hypothesis: LoopHypothesis, config: dict[str, Any]) -> float:
    max_budget = float(config.get("guardrails", {}).get("max_experiment_budget_usd", 50) or 50)
    base = max_budget * clamp(hypothesis.confidence_score, 0.2, 0.95) * max(0.2, 1 - hypothesis.risk_score / 120)
    return round(max(5.0, min(max_budget, base)), 2)


def render_hypothesis(signal: LoopSignal, opportunity_type: str) -> str:
    label = signal.object_label
    if opportunity_type == "creative_test":
        return f"{label} may work because the creative signal is rising; test hook, shot order, CTA, and creator fit before scaling."
    if opportunity_type == "product_listing_test":
        return f"{label} may be a product opportunity because marketplace ranking or seasonality is strong; test listing, image, price, and supply fit."
    if opportunity_type == "keyword_listing_test":
        return f"{label} may be a keyword opportunity; test translated long-tail title, tags, and query snapshots."
    if opportunity_type == "creator_seed_test":
        return f"{label} may be a creator opportunity; test small creator seeding with ROI and cooperation tracking."
    if opportunity_type == "quality_fix_test":
        return f"{label} indicates a customer pain point; test a product/listing/script fix and monitor complaints and returns."
    if opportunity_type == "budget_pacing_test":
        return f"{label} indicates own-store metric movement; test cautious budget pacing with stop-loss."
    if opportunity_type == "risk_pause_or_repair":
        return f"{label} is a risk signal; pause external action, collect evidence, and prepare appeal or repair steps."
    return f"{label} should be tested with a controlled experiment."


def guardrail_reason_for(signal: LoopSignal, action_family: str, risk_score: float, config: dict[str, Any]) -> str:
    if risk_score >= float(config.get("guardrails", {}).get("policy_pause_risk_score", 80) or 80):
        return "High policy/account/IP risk: only evidence collection, draft repair, or approval queue is allowed."
    if action_family in EXTERNAL_ACTION_FAMILIES and not config.get("allow_external_auto_execute", False):
        return "External store/platform action: draft and queue only until human approval enables execution."
    return "Low-risk internal loop action: collect, analyze, draft, monitor, and remember automatically."


def apply_guardrail_risk(signal: LoopSignal, action_family: str, config: dict[str, Any]) -> float:
    risk = signal.risk_score
    if action_family in EXTERNAL_ACTION_FAMILIES:
        risk += 18
    if signal.signal_type in {"policy_risk", "account_risk", "ip_risk", "claim_risk"}:
        risk += 22
    return clamp(risk, 0, 100)


def estimate_profit(signal: LoopSignal) -> float:
    base = 20 + signal.signal_strength * 1.8 + max(signal.delta, 0) * 1.5
    if signal.signal_type in {"creative_growth", "product_growth", "keyword_growth"}:
        base *= 1.35
    if signal.signal_type in {"policy_risk", "account_risk", "ip_risk", "claim_risk"}:
        base *= 0.45
    return max(5.0, base)


def infer_risk_score(record: IntakeRecord) -> float:
    fields = record.fields
    if record.record_type in RISK_RECORD_TYPES:
        base = 65
    else:
        base = 20
    risk_text = " ".join(str(fields.get(key) or "") for key in ["risk_level", "severity", "impact_level", "review_status", "status", "risk_type"])
    lowered = risk_text.lower()
    if any(word in lowered for word in ["critical", "confirmed", "blocked", "prohibited", "high"]):
        base += 25
    elif any(word in lowered for word in ["medium", "suspected", "borderline"]):
        base += 12
    if record.record_type in {"ip_image_risk", "banned_term", "claim_requirement"}:
        base += 10
    return clamp(base, 0, 100)


def infer_time_sensitivity(record: IntakeRecord, now: datetime) -> float:
    fields = record.fields
    if record.record_type in {"viral_content_signal", "creative_snapshot", "creator_spike_event"}:
        return 1.45
    if record.record_type in {"policy_diff", "enforcement_event", "account_health"}:
        return 1.35
    if record.record_type == "seasonal_event":
        start = parse_datetime(str(fields.get("event_start_date") or ""))
        if start:
            days = (start.date() - now.date()).days
            if 0 <= days <= 45:
                return 1.5
    return 1.0


def infer_evidence_count(record: IntakeRecord) -> int:
    count = 1
    fields = record.fields
    for key in ["url", "video_url", "product_url", "page_url", "source_url", "image_url", "metric_lines", "page_links", "comments", "review_count"]:
        value = fields.get(key)
        if value:
            count += len(value) if isinstance(value, list) else 1
    count += int(record.metadata.get("dedupe_count") or 1) - 1
    return min(max(count, 1), 20)


def extract_delta(fields: dict[str, Any], raw_text: str) -> float:
    for key in ["delta", "delta_value", "rank_improvement", "growth_rate", "visible_growth_rate", "sales_growth", "view_growth", "acceleration"]:
        value = fields.get(key)
        if value not in {None, ""}:
            return number(value)
    text = " ".join([raw_text, json.dumps(fields, ensure_ascii=False)])
    percent = re.search(r"([+-]?\d+(?:\.\d+)?)\s*%", text)
    if percent:
        return number(percent.group(1))
    return 0.0


def extract_velocity(fields: dict[str, Any], priority: float) -> float:
    for key in ["velocity", "view_velocity", "sales_velocity", "trend_velocity"]:
        value = fields.get(key)
        if value not in {None, ""}:
            return number(value)
    return clamp(priority / 100, 0, 1)


def extract_acceleration(fields: dict[str, Any], delta: float, velocity: float) -> float:
    for key in ["acceleration", "view_acceleration", "sales_acceleration"]:
        value = fields.get(key)
        if value not in {None, ""}:
            return number(value)
    return delta * velocity / 100


def object_id_for_record(record: IntakeRecord) -> str:
    fields = record.fields
    for key in [
        "product_id",
        "listing_id",
        "video_id",
        "creator_id",
        "store_id",
        "external_listing_id",
        "product_asin",
        "asin",
        "sku",
        "url",
        "video_url",
        "query_text",
        "normalized_query",
    ]:
        value = fields.get(key)
        if value:
            return str(value)[:160]
    return record.record_id


def record_label(record: IntakeRecord) -> str:
    fields = record.fields
    for key in [
        "product_name",
        "title",
        "query_text",
        "normalized_query",
        "event_name",
        "creative_url",
        "video_url",
        "creator_handle",
        "store_id",
        "term",
        "risk_element",
        "page_title",
        "url",
    ]:
        value = fields.get(key)
        if value:
            return str(value)[:140]
    return record.record_id[:10]


def parse_run_at(run_at: str | None) -> datetime:
    if not run_at:
        return datetime.now(timezone.utc)
    parsed = parse_datetime(run_at)
    if parsed:
        return parsed
    return datetime.now(timezone.utc)


def parse_datetime(value: str) -> datetime | None:
    clean = str(value or "").strip()
    if not clean:
        return None
    if clean.endswith("Z"):
        clean = clean[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(clean)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(clean + "T00:00:00+00:00")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def stable_id(prefix: str, *parts: Any) -> str:
    raw = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:18]
    return f"{prefix}{digest}"


def number(value: Any) -> float:
    if value in {None, ""}:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    clean = re.sub(r"[^0-9.+-]", "", str(value))
    if clean in {"", "-", "+", ".", "-.", "+."}:
        return 0.0
    try:
        return float(clean)
    except ValueError:
        return 0.0


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
