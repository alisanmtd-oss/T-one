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


AUTONOMOUS_V2_REPORT_PREFIX = "autonomous_v2_mvp"
AUTONOMOUS_V2_SIMULATION_PREFIX = "autonomous_v2_24h_simulation"
TIKTOK_SOURCE_HINTS = ("tiktok", "tik tok", "tk", "fastmoss", "kalodata")


@dataclass(slots=True)
class AutonomousV2Result:
    run_id: str
    run_at_utc: str
    signal_events: list[IntakeRecord]
    signal_snapshots: list[IntakeRecord]
    signal_alerts: list[IntakeRecord]
    hypotheses: list[IntakeRecord]
    experiments: list[IntakeRecord]
    reinforcement_records: list[IntakeRecord]
    priority_records: list[IntakeRecord]
    report: str
    report_path: Path
    simulation_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "run_at_utc": self.run_at_utc,
            "signal_events": [record.to_dict() for record in self.signal_events],
            "signal_snapshots": [record.to_dict() for record in self.signal_snapshots],
            "signal_alerts": [record.to_dict() for record in self.signal_alerts],
            "hypotheses": [record.to_dict() for record in self.hypotheses],
            "experiments": [record.to_dict() for record in self.experiments],
            "reinforcement_records": [record.to_dict() for record in self.reinforcement_records],
            "priority_records": [record.to_dict() for record in self.priority_records],
            "report": self.report,
            "report_path": str(self.report_path),
            "simulation_path": str(self.simulation_path),
        }


def run_autonomous_v2_mvp(root: Path, run_at: str | None = None) -> AutonomousV2Result:
    root = root.resolve()
    now = parse_run_at(run_at)
    run_id = stable_id("v2_", now.isoformat())

    seed_thresholds(root, now)
    source_records = tiktok_mvp_source_records(read_records(root))
    signal_events, signal_snapshots, signal_alerts, signal_weights = build_signal_layer(source_records, now)
    for record in [*signal_events, *signal_snapshots, *signal_alerts, *signal_weights]:
        append_record(root, record)

    hypotheses, hypothesis_evidence, hypothesis_scores = build_hypothesis_layer(signal_events, now)
    for record in [*hypotheses, *hypothesis_evidence, *hypothesis_scores]:
        append_record(root, record)

    experiments, experiment_details, compatibility_runs = build_experiment_layer(hypotheses, now)
    for record in [*experiments, *experiment_details, *compatibility_runs]:
        append_record(root, record)

    reinforcement_records = build_reinforcement_layer(root, hypotheses, experiments, now)
    for record in reinforcement_records:
        append_record(root, record)

    priority_records = build_priority_layer(run_id, hypotheses, experiments, now)
    for record in priority_records:
        append_record(root, record)

    report = build_v2_report(
        now,
        source_records,
        signal_events,
        hypotheses,
        experiments,
        reinforcement_records,
        priority_records,
    )
    report_path = write_output(root, AUTONOMOUS_V2_REPORT_PREFIX, now, report)
    simulation_path = write_output(root, AUTONOMOUS_V2_SIMULATION_PREFIX, now, build_24h_simulation_report(now, hypotheses, experiments))
    return AutonomousV2Result(
        run_id=run_id,
        run_at_utc=now.isoformat(),
        signal_events=signal_events,
        signal_snapshots=signal_snapshots,
        signal_alerts=signal_alerts,
        hypotheses=hypotheses,
        experiments=experiments,
        reinforcement_records=reinforcement_records,
        priority_records=priority_records,
        report=report,
        report_path=report_path,
        simulation_path=simulation_path,
    )


def seed_thresholds(root: Path, now: datetime) -> None:
    thresholds = [
        ("trend_velocity", "trend", "velocity", 0.4, "gt", "high"),
        ("anomaly_z_score", "anomaly", "z_score", 2.5, "gt", "high"),
        ("seasonal_score", "seasonality", "seasonal_score", 0.6, "gt", "watch"),
        ("saturation_score", "saturation", "saturation_score", 0.7, "gt", "watch"),
    ]
    for key, engine_type, metric_name, threshold_value, operator, severity in thresholds:
        append_record(
            root,
            IntakeRecord(
                record_type="signal_threshold",
                fields={
                    "signal_threshold_id": stable_id("sth_", key),
                    "engine_type": engine_type,
                    "metric_name": metric_name,
                    "platform": "TikTok",
                    "country": "US",
                    "threshold_value": threshold_value,
                    "operator": operator,
                    "severity": severity,
                    "enabled": True,
                    "updated_at_utc": now.isoformat(),
                },
                raw_text=json.dumps({"threshold": key}, ensure_ascii=False),
                source="autonomous_v2.signal_engine",
                score={"priority": 80, "layer": "signal_threshold"},
                director_notes=["Default Autonomous v2 MVP threshold."],
                confidence=0.9,
            ),
        )


def tiktok_mvp_source_records(records: list[IntakeRecord]) -> list[IntakeRecord]:
    source_types = {
        "platform_ranking_signal",
        "viral_content_signal",
        "creative_snapshot",
        "query_snapshot",
        "creator_spike_event",
        "video_breakdown",
        "video_script",
        "hot_link",
    }
    candidates = [record for record in records if record.record_type in source_types and is_tiktok_related(record)]
    candidates.sort(key=lambda record: int(record.score.get("priority") or 0), reverse=True)
    return candidates[:40]


def is_tiktok_related(record: IntakeRecord) -> bool:
    explicit_platform = " ".join(
        str(value or "")
        for value in [
            record.fields.get("platform"),
            record.fields.get("source_platform"),
            record.fields.get("marketplace"),
            record.fields.get("bridge_provider"),
        ]
    ).lower()
    explicit_url = " ".join(
        str(value or "")
        for value in [
            record.fields.get("url"),
            record.fields.get("product_url"),
            record.fields.get("video_url"),
            record.fields.get("source_page_url"),
        ]
    ).lower()
    if "amazon" in explicit_platform and not any(hint in explicit_platform or hint in explicit_url for hint in TIKTOK_SOURCE_HINTS):
        return False
    text = " ".join(
        str(value or "")
        for value in [
            record.record_type,
            record.source,
            record.raw_text,
            record.fields.get("platform"),
            record.fields.get("source_platform"),
            record.fields.get("marketplace"),
            record.fields.get("url"),
            record.fields.get("product_url"),
            record.fields.get("video_url"),
            record.fields.get("source_page_url"),
            record.fields.get("bridge_provider"),
            record.fields.get("data_category"),
        ]
    ).lower()
    if any(hint in text for hint in TIKTOK_SOURCE_HINTS):
        return True
    if record.record_type in {"viral_content_signal", "video_breakdown", "video_script", "creative_snapshot", "creator_spike_event"}:
        return True
    return False


def tiktok_mvp_platform(record: IntakeRecord) -> str:
    platform = first_text(
        record.fields.get("source_platform"),
        record.fields.get("bridge_provider"),
        record.fields.get("platform"),
        record.fields.get("marketplace"),
        "TikTok",
    )
    tiktok_source_text = " ".join(
        str(value or "")
        for value in [
            record.source,
            record.raw_text,
            record.fields.get("url"),
            record.fields.get("product_url"),
            record.fields.get("video_url"),
            record.fields.get("source_page_url"),
            record.fields.get("bridge_provider"),
        ]
    ).lower()
    if any(hint in tiktok_source_text for hint in TIKTOK_SOURCE_HINTS):
        return "TikTok"
    return platform


def build_signal_layer(records: list[IntakeRecord], now: datetime) -> tuple[list[IntakeRecord], list[IntakeRecord], list[IntakeRecord], list[IntakeRecord]]:
    events: list[IntakeRecord] = []
    snapshots: list[IntakeRecord] = []
    alerts: list[IntakeRecord] = []
    weights: list[IntakeRecord] = []
    for record in records:
        facts = signal_facts_from_record(record)
        if not facts:
            continue
        entity_type = facts["entity_type"]
        entity_label = facts["entity_label"]
        entity_id = facts["entity_id"]
        platform = facts["platform"]
        metric_name = facts["metric_name"]
        current = facts["current_value"]
        baseline = facts["baseline_value"]
        delta = round(current - baseline, 4)
        velocity = round(delta / baseline, 4) if baseline else round(min(current / 100, 3), 4)
        z_score = round(delta / max(abs(baseline) * 0.25, 1), 4)
        seasonal_score = seasonality_score(entity_label, record)
        saturation_score_value = saturation_score(entity_label, records)
        anomaly_score = round(max(0, z_score) / 3, 4)
        engine_type = choose_engine_type(velocity, z_score, seasonal_score, saturation_score_value)
        signal_type = f"{engine_type}_signal"
        confidence = clamp(0.45 + min(abs(velocity), 2) * 0.18 + seasonal_score * 0.12 + min(int(record.score.get("priority") or 0), 100) / 400, 0.35, 0.95)
        risk_score = signal_risk_score(record)
        signal_id = stable_id("sig_", engine_type, entity_type, entity_id, metric_name, now.isoformat())
        event_fields = {
            "signal_id": signal_id,
            "engine_type": engine_type,
            "signal_type": signal_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_label": entity_label,
            "platform": platform,
            "country": str(record.fields.get("country") or record.fields.get("market") or "US"),
            "metric_name": metric_name,
            "baseline_value": baseline,
            "current_value": current,
            "delta": delta,
            "velocity": velocity,
            "z_score": z_score,
            "seasonal_score": seasonal_score,
            "saturation_score": saturation_score_value,
            "anomaly_score": anomaly_score,
            "confidence": round(confidence, 4),
            "risk_score": risk_score,
            "source_record_id": record.record_id,
            "timestamp": now.isoformat(),
            "status": "detected",
        }
        event = IntakeRecord(
            record_type="signal_event",
            fields=event_fields,
            raw_text=json.dumps(record.to_dict(), ensure_ascii=False),
            source="autonomous_v2.signal_engine",
            score={"priority": int(priority_from_signal(event_fields)), "engine_type": engine_type},
            director_notes=[f"{engine_type} signal for {entity_label}."],
            confidence=confidence,
        )
        events.append(event)
        snapshots.append(
            IntakeRecord(
                record_type="signal_snapshot",
                fields={
                    "signal_snapshot_id": stable_id("ssn_", entity_type, entity_id, metric_name, now.isoformat()),
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "platform": platform,
                    "metric_name": metric_name,
                    "value": current,
                    "value_last_7d": baseline,
                    "value_last_30d": max(baseline * 0.82, 1),
                    "delta": delta,
                    "velocity": velocity,
                    "acceleration": round(velocity - ((baseline - max(baseline * 0.82, 1)) / max(max(baseline * 0.82, 1), 1)), 4),
                    "snapshot_at_utc": now.isoformat(),
                },
                raw_text=json.dumps(event_fields, ensure_ascii=False),
                source="autonomous_v2.signal_engine",
                score={"priority": int(priority_from_signal(event_fields)), "layer": "signal_snapshot"},
                director_notes=["Signal time-series snapshot."],
                confidence=confidence,
            )
        )
        weights.append(
            IntakeRecord(
                record_type="signal_weight",
                fields={
                    "signal_weight_id": stable_id("swg_", signal_id, engine_type),
                    "signal_id": signal_id,
                    "engine_type": engine_type,
                    "weight": round(confidence * (1 + max(velocity, 0)) * (1 - min(risk_score, 95) / 120), 4),
                    "evidence_count": evidence_count(entity_label, records),
                    "calculated_at_utc": now.isoformat(),
                },
                raw_text=json.dumps(event_fields, ensure_ascii=False),
                source="autonomous_v2.signal_engine",
                score={"priority": int(priority_from_signal(event_fields)), "layer": "signal_weight"},
                director_notes=["Signal weight for priority engine."],
                confidence=confidence,
            )
        )
        if should_alert(event_fields):
            alerts.append(
                IntakeRecord(
                    record_type="signal_alert",
                    fields={
                        "signal_alert_id": stable_id("sal_", signal_id, signal_type),
                        "signal_id": signal_id,
                        "alert_type": f"{engine_type}_threshold_crossed",
                        "severity": "high" if velocity > 0.4 or z_score > 2.5 else "watch",
                        "message": f"{entity_label} crossed {engine_type} threshold on {platform}.",
                        "created_at_utc": now.isoformat(),
                        "status": "open",
                    },
                    raw_text=json.dumps(event_fields, ensure_ascii=False),
                    source="autonomous_v2.signal_engine",
                    score={"priority": int(priority_from_signal(event_fields)), "layer": "signal_alert"},
                    director_notes=["Alert converted from signal threshold."],
                    confidence=confidence,
                )
            )
    return events[:30], snapshots[:30], alerts[:30], weights[:30]


def signal_facts_from_record(record: IntakeRecord) -> dict[str, Any]:
    fields = record.fields
    label = first_text(
        fields.get("product_name"),
        fields.get("product_theme"),
        fields.get("content_theme"),
        fields.get("keyword"),
        fields.get("creator_handle"),
        fields.get("title"),
        fields.get("ranking_page"),
        fields.get("url"),
        record.raw_text[:120],
    )
    if not label:
        return {}
    platform = tiktok_mvp_platform(record)
    if record.record_type in {"viral_content_signal", "video_breakdown", "video_script", "creative_snapshot"}:
        entity_type = "video"
        metric_name = "views_or_content_growth"
        current = first_number(fields.get("current_views"), fields.get("latest_video_views"), fields.get("views"), fields.get("view_growth"), fields.get("growth_rate"), 100)
        baseline = first_number(fields.get("baseline_avg_views"), fields.get("previous_views"), max(current / 1.85, 1))
        entity_id = first_text(fields.get("video_url"), fields.get("source_breakdown_id"), label)
    elif record.record_type == "creator_spike_event":
        entity_type = "creator"
        metric_name = "creator_video_spike"
        current = first_number(fields.get("latest_video_views"), fields.get("current_views"), fields.get("spike_multiplier"), fields.get("avg_views"), 100)
        baseline = first_number(fields.get("baseline_avg_views"), fields.get("avg_views"), max(current / 2, 1))
        entity_id = first_text(fields.get("creator_handle"), fields.get("profile_url"), label)
    elif record.record_type == "query_snapshot":
        entity_type = "keyword"
        metric_name = "query_heat"
        current = first_number(fields.get("current_value"), fields.get("search_volume"), fields.get("growth_rate"), fields.get("query_count"), 100)
        baseline = first_number(fields.get("baseline_value"), fields.get("value_last_7d"), max(current / 1.6, 1))
        entity_id = first_text(fields.get("normalized_query"), fields.get("keyword"), label)
    else:
        entity_type = "product"
        metric_name = "ranking_growth"
        rank = first_number(fields.get("rank_position"), fields.get("rank"), 0)
        growth = first_number(fields.get("growth_rate"), fields.get("visible_growth_signal"), fields.get("rank_delta"), 0)
        current = growth if growth else (max(101 - rank, 1) if rank else first_number(fields.get("sales_count"), fields.get("gmv"), 100))
        baseline = first_number(fields.get("baseline_value"), fields.get("value_last_7d"), max(current / 1.6, 1))
        entity_id = first_text(fields.get("product_url"), fields.get("url"), fields.get("product_id"), label)
    return {
        "entity_type": entity_type,
        "entity_label": label[:220],
        "entity_id": entity_id[:260],
        "platform": platform,
        "metric_name": metric_name,
        "current_value": max(float(current), 0.0),
        "baseline_value": max(float(baseline), 1.0),
    }


def build_hypothesis_layer(signal_events: list[IntakeRecord], now: datetime) -> tuple[list[IntakeRecord], list[IntakeRecord], list[IntakeRecord]]:
    hypotheses: list[IntakeRecord] = []
    evidence: list[IntakeRecord] = []
    scores: list[IntakeRecord] = []
    for signal in sorted(signal_events, key=lambda item: int(item.score.get("priority") or 0), reverse=True)[:12]:
        fields = signal.fields
        expected_profit = estimate_expected_profit(fields)
        risk = float(fields.get("risk_score") or 0) / 100
        confidence = float(fields.get("confidence") or 0.5)
        time_sensitivity = time_sensitivity_for(fields)
        priority = priority_formula(expected_profit, confidence, time_sensitivity, risk)
        hypothesis_id = stable_id("hyp_", fields.get("signal_id"), "mvp")
        entity_label = str(fields.get("entity_label") or "")
        opportunity_type = opportunity_type_for(fields)
        hypothesis_text = hypothesis_text_for(entity_label, fields, opportunity_type)
        related = {
            "entity_type": fields.get("entity_type"),
            "entity_id": fields.get("entity_id"),
            "platform": fields.get("platform"),
            "keyword_or_theme": entity_label,
            "source_record_id": fields.get("source_record_id"),
        }
        hypotheses.append(
            IntakeRecord(
                record_type="hypothesis",
                fields={
                    "hypothesis_id": hypothesis_id,
                    "signal_id": fields.get("signal_id"),
                    "opportunity_type": opportunity_type,
                    "related_entities": related,
                    "hypothesis_text": hypothesis_text,
                    "expected_profit": expected_profit,
                    "risk_score": risk,
                    "confidence_score": confidence,
                    "priority_score": priority,
                    "status": "scored",
                    "created_at_utc": now.isoformat(),
                },
                raw_text=json.dumps(fields, ensure_ascii=False),
                source="autonomous_v2.hypothesis_generator",
                score={"priority": int(min(priority, 100)), "layer": "hypothesis"},
                director_notes=[hypothesis_text],
                confidence=confidence,
            )
        )
        evidence.append(
            IntakeRecord(
                record_type="hypothesis_evidence",
                fields={
                    "hypothesis_evidence_id": stable_id("hev_", hypothesis_id, fields.get("signal_id"), fields.get("source_record_id")),
                    "hypothesis_id": hypothesis_id,
                    "signal_id": fields.get("signal_id"),
                    "source_record_id": fields.get("source_record_id"),
                    "evidence_type": fields.get("engine_type"),
                    "evidence_summary": f"{fields.get('metric_name')} velocity={fields.get('velocity')} z={fields.get('z_score')}",
                    "confidence": confidence,
                },
                raw_text=json.dumps(fields, ensure_ascii=False),
                source="autonomous_v2.hypothesis_generator",
                score={"priority": int(min(priority, 100)), "layer": "hypothesis_evidence"},
                director_notes=["Evidence attached to v2 hypothesis."],
                confidence=confidence,
            )
        )
        scores.append(
            IntakeRecord(
                record_type="hypothesis_score",
                fields={
                    "hypothesis_score_id": stable_id("hsc_", hypothesis_id, "v2_mvp"),
                    "hypothesis_id": hypothesis_id,
                    "score_version": "v2_mvp",
                    "expected_profit": expected_profit,
                    "confidence_score": confidence,
                    "risk_score": risk,
                    "time_sensitivity": time_sensitivity,
                    "priority_score": priority,
                    "calculated_at_utc": now.isoformat(),
                },
                raw_text=json.dumps({"formula": "expected_profit * confidence * time_sensitivity * (1 - risk)"}, ensure_ascii=False),
                source="autonomous_v2.priority_engine",
                score={"priority": int(min(priority, 100)), "layer": "hypothesis_score"},
                director_notes=["Priority formula calculated for v2 hypothesis."],
                confidence=confidence,
            )
        )
    return hypotheses, evidence, scores


def build_experiment_layer(hypotheses: list[IntakeRecord], now: datetime) -> tuple[list[IntakeRecord], list[IntakeRecord], list[IntakeRecord]]:
    experiments: list[IntakeRecord] = []
    details: list[IntakeRecord] = []
    compatibility_runs: list[IntakeRecord] = []
    for hypothesis in hypotheses[:2]:
        fields = hypothesis.fields
        experiment_id = stable_id("expv2_", fields.get("hypothesis_id"))
        platform = str(fields.get("related_entities", {}).get("platform") or "TikTok") if isinstance(fields.get("related_entities"), dict) else "TikTok"
        budget = min(max(round(float(fields.get("expected_profit") or 250) * 0.12, 2), 25), 50)
        cpa_limit = 12
        roi_target = 2
        experiments.append(
            IntakeRecord(
                record_type="experiment",
                fields={
                    "experiment_id": experiment_id,
                    "hypothesis_id": fields.get("hypothesis_id"),
                    "platform": platform,
                    "budget_limit": budget,
                    "cpa_limit": cpa_limit,
                    "roi_target": roi_target,
                    "start_time": "",
                    "end_time": "",
                    "state": "waiting_manual_execution",
                    "manual_execution_required": True,
                    "time_window": "24h watch + 72h decision",
                },
                raw_text=json.dumps(fields, ensure_ascii=False),
                source="autonomous_v2.experiment_planner",
                score={"priority": int(min(float(fields.get("priority_score") or 0), 100)), "layer": "experiment"},
                director_notes=["MVP experiment created as manual-execution draft; no real ad/listing/publish action was taken."],
                confidence=float(fields.get("confidence_score") or 0.5),
            )
        )
        details.extend(
            [
                IntakeRecord(
                    record_type="experiment_variant",
                    fields={
                        "experiment_variant_id": stable_id("exv_", experiment_id, "store_script"),
                        "experiment_id": experiment_id,
                        "variant_name": "store_owned_script",
                        "variant_type": "tiktok_video_script",
                        "variant_payload": {
                            "hook": "identity/emotion first 2 seconds",
                            "scene": "home/work/real-use scene",
                            "cta": "product card + comment demand",
                        },
                    },
                    raw_text=json.dumps(fields, ensure_ascii=False),
                    source="autonomous_v2.experiment_planner",
                    score={"priority": 84, "layer": "experiment_variant"},
                    director_notes=["Store-owned TikTok script variant."],
                ),
                IntakeRecord(
                    record_type="experiment_stop_rule",
                    fields={
                        "experiment_stop_rule_id": stable_id("esr_", experiment_id, "cpa"),
                        "experiment_id": experiment_id,
                        "rule_name": "cpa_stop_loss",
                        "condition": f"Stop if CPA > {cpa_limit} or ROI < 1.0 after the first valid window.",
                        "action": "stop_test_and_write_failure_memory",
                    },
                    raw_text=json.dumps(fields, ensure_ascii=False),
                    source="autonomous_v2.experiment_planner",
                    score={"priority": 86, "layer": "experiment_stop_rule"},
                    director_notes=["Stop-loss rule attached."],
                ),
                IntakeRecord(
                    record_type="experiment_scale_rule",
                    fields={
                        "experiment_scale_rule_id": stable_id("esc_", experiment_id, "roi"),
                        "experiment_id": experiment_id,
                        "rule_name": "roi_scale_rule",
                        "condition": f"Scale if ROI >= {roi_target} and comments show purchase intent.",
                        "action": "prepare_scale_plan_for_approval",
                    },
                    raw_text=json.dumps(fields, ensure_ascii=False),
                    source="autonomous_v2.experiment_planner",
                    score={"priority": 86, "layer": "experiment_scale_rule"},
                    director_notes=["Scale rule attached."],
                ),
                IntakeRecord(
                    record_type="experiment_metric",
                    fields={
                        "experiment_metric_id": stable_id("exm_", experiment_id, "targets", now.isoformat()),
                        "experiment_id": experiment_id,
                        "metric_name": "target_roi",
                        "metric_value": 0,
                        "target_value": roi_target,
                        "measured_at_utc": now.isoformat(),
                    },
                    raw_text=json.dumps(fields, ensure_ascii=False),
                    source="autonomous_v2.metric_monitor",
                    score={"priority": 72, "layer": "experiment_metric"},
                    director_notes=["Metric placeholder for manual execution result import."],
                ),
            ]
        )
        compatibility_runs.append(
            IntakeRecord(
                record_type="experiment_run",
                fields={
                    "experiment_id": stable_id("exp_", experiment_id),
                    "subject_type": "video",
                    "subject_id": experiment_id,
                    "hypothesis": fields.get("hypothesis_text"),
                    "action_taken": "Create TikTok MVP test plan; execution remains manual until approved.",
                    "owner": "AI Ecommerce Director",
                    "status": "draft",
                    "linked_strategy_id": "",
                    "linked_agent_id": "agn_ecommerce_director_v1",
                    "budget_limit_usd": budget,
                    "cpa_limit_usd": cpa_limit,
                    "roi_target": roi_target,
                    "requires_confirmation": True,
                    "guardrail_reason": "MVP only prepares a small-budget test. Real posting, ads, and creator contact require approval.",
                },
                raw_text=json.dumps(fields, ensure_ascii=False),
                source="autonomous_v2.compatibility_bridge",
                score={"priority": int(min(float(fields.get("priority_score") or 0), 100)), "layer": "experiment_run_bridge"},
                director_notes=["Compatibility experiment_run record for existing approval center."],
            )
        )
    return experiments, details, compatibility_runs


def build_reinforcement_layer(root: Path, hypotheses: list[IntakeRecord], experiments: list[IntakeRecord], now: datetime) -> list[IntakeRecord]:
    records: list[IntakeRecord] = []
    outcomes = [*read_records(root, "experiment_outcome"), *read_records(root, "action_outcome")]
    outcome_by_experiment = {
        str(outcome.fields.get("experiment_id") or ""): outcome
        for outcome in outcomes
        if outcome.fields.get("experiment_id")
    }
    for hypothesis in hypotheses[:6]:
        pattern_value = extract_pattern_value(hypothesis)
        pattern_type = pattern_type_for_hypothesis(hypothesis)
        experiment_id = stable_id("expv2_", hypothesis.fields.get("hypothesis_id"))
        outcome = outcome_by_experiment.get(experiment_id) or outcome_by_experiment.get(stable_id("exp_", experiment_id))
        conclusion = str(outcome.fields.get("conclusion") or "").lower() if outcome else ""
        success_delta = 0.12 if conclusion in {"won", "positive"} else 0
        failure_delta = -0.08 if conclusion in {"lost", "negative"} else 0
        signal_delta = 0.03 if not outcome else 0
        weight_delta = round(success_delta + failure_delta + signal_delta, 4)
        weight = round(max(0.1, min(1.0, 0.5 + weight_delta)), 4)
        pattern_weight_id = stable_id("pwt_", pattern_type, pattern_value)
        records.append(
            IntakeRecord(
                record_type="pattern_weight",
                fields={
                    "pattern_weight_id": pattern_weight_id,
                    "pattern_type": pattern_type,
                    "pattern_value": pattern_value,
                    "success_count": 1 if success_delta else 0,
                    "failure_count": 1 if failure_delta else 0,
                    "weight": weight,
                    "last_updated": now.isoformat(),
                    "source_hypothesis_id": hypothesis.fields.get("hypothesis_id"),
                    "source_experiment_id": experiment_id,
                },
                raw_text=json.dumps(hypothesis.fields, ensure_ascii=False),
                source="autonomous_v2.reinforcement",
                score={"priority": int(weight * 100), "layer": "pattern_weight"},
                director_notes=["Pattern initialized or updated from signals/outcomes."],
                confidence=float(hypothesis.fields.get("confidence_score") or 0.5),
            )
        )
        records.append(
            IntakeRecord(
                record_type="pattern_history",
                fields={
                    "pattern_history_id": stable_id("phs_", pattern_weight_id, now.isoformat()),
                    "pattern_weight_id": pattern_weight_id,
                    "event_type": "signal_confirmation" if not outcome else f"outcome_{conclusion}",
                    "delta": weight_delta,
                    "reason": "Repeated signal confirmation before execution." if not outcome else "Experiment outcome updated pattern weight.",
                    "event_time_utc": now.isoformat(),
                },
                raw_text=json.dumps(hypothesis.fields, ensure_ascii=False),
                source="autonomous_v2.reinforcement",
                score={"priority": int(weight * 100), "layer": "pattern_history"},
                director_notes=["Pattern history appended."],
            )
        )
    if experiments:
        records.append(
            IntakeRecord(
                record_type="strategy_adjustment",
                fields={
                    "strategy_adjustment_id": stable_id("sad_", "mvp", now.isoformat()),
                    "hypothesis_id": experiments[0].fields.get("hypothesis_id"),
                    "adjustment_type": "mvp_manual_test_queue",
                    "adjustment_summary": "Run the top TikTok opportunity as a small manual experiment before scaling automation.",
                    "created_at_utc": now.isoformat(),
                    "status": "draft",
                },
                raw_text=json.dumps([record.fields for record in experiments], ensure_ascii=False),
                source="autonomous_v2.reinforcement",
                score={"priority": 86, "layer": "strategy_adjustment"},
                director_notes=["MVP strategy adjustment drafted."],
            )
        )
    return records


def build_priority_layer(run_id: str, hypotheses: list[IntakeRecord], experiments: list[IntakeRecord], now: datetime) -> list[IntakeRecord]:
    records: list[IntakeRecord] = []
    top_items: list[dict[str, Any]] = []
    for hypothesis in sorted(hypotheses, key=lambda item: float(item.fields.get("priority_score") or 0), reverse=True)[:10]:
        fields = hypothesis.fields
        entity = fields.get("related_entities") if isinstance(fields.get("related_entities"), dict) else {}
        entity_type = str(entity.get("entity_type") or "hypothesis")
        entity_id = str(entity.get("entity_id") or fields.get("hypothesis_id"))
        components = {
            "expected_profit": float(fields.get("expected_profit") or 0),
            "confidence_score": float(fields.get("confidence_score") or 0),
            "time_sensitivity": time_sensitivity_for(fields),
            "risk_score": float(fields.get("risk_score") or 0),
        }
        score = priority_formula(
            components["expected_profit"],
            components["confidence_score"],
            components["time_sensitivity"],
            components["risk_score"],
        )
        top_items.append(
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "title": entity.get("keyword_or_theme") or fields.get("hypothesis_text"),
                "priority_score": score,
                "next_step": "manual small-budget TikTok test" if experiments else "wait for experiment planning",
            }
        )
        records.append(
            IntakeRecord(
                record_type="priority_score",
                fields={
                    "priority_score_id": stable_id("psc_", entity_type, entity_id, now.isoformat()),
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "score_formula": "expected_profit * confidence * time_sensitivity * (1 - risk)",
                    "priority_score": score,
                    "components": components,
                    "calculated_at_utc": now.isoformat(),
                },
                raw_text=json.dumps(fields, ensure_ascii=False),
                source="autonomous_v2.priority_engine",
                score={"priority": int(min(score, 100)), "layer": "priority_score"},
                director_notes=["Priority score calculated."],
                confidence=components["confidence_score"],
            )
        )
        records.append(
            IntakeRecord(
                record_type="backlog",
                fields={
                    "backlog_id": stable_id("bkl_", entity_type, entity_id, fields.get("opportunity_type")),
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "opportunity_type": fields.get("opportunity_type"),
                    "priority_score": score,
                    "status": "planned" if experiments else "open",
                    "created_at_utc": now.isoformat(),
                },
                raw_text=json.dumps(fields, ensure_ascii=False),
                source="autonomous_v2.priority_engine",
                score={"priority": int(min(score, 100)), "layer": "backlog"},
                director_notes=["Backlog item created from hypothesis."],
                confidence=components["confidence_score"],
            )
        )
    records.append(
        IntakeRecord(
            record_type="priority_rebalance_log",
            fields={
                "priority_rebalance_log_id": stable_id("prb_", run_id),
                "run_id": run_id,
                "top_items": top_items,
                "created_at_utc": now.isoformat(),
            },
            raw_text=json.dumps(top_items, ensure_ascii=False),
            source="autonomous_v2.priority_engine",
            score={"priority": 88 if top_items else 50, "layer": "priority_rebalance"},
            director_notes=["Top opportunity backlog rebalanced."],
        )
    )
    for experiment in experiments:
        task_queue_id = stable_id("tsk_", "manual_execute", experiment.fields.get("experiment_id"))
        expected_profit = float(next((h.fields.get("expected_profit") for h in hypotheses if h.fields.get("hypothesis_id") == experiment.fields.get("hypothesis_id")), 250) or 250)
        confidence = experiment.confidence or 0.6
        score = priority_formula(expected_profit, confidence, 0.95, 0.18)
        records.append(
            IntakeRecord(
                record_type="task_queue",
                fields={
                    "task_queue_id": task_queue_id,
                    "task_type": "manual_execute_tiktok_mvp_experiment",
                    "source_event_inbox_id": f"autonomous_v2:{now.date().isoformat()}",
                    "target_agent_id": "agn_ecommerce_director_v1",
                    "priority": int(min(score, 100)),
                    "payload": {
                        "experiment_id": experiment.fields.get("experiment_id"),
                        "budget_limit": experiment.fields.get("budget_limit"),
                        "cpa_limit": experiment.fields.get("cpa_limit"),
                        "roi_target": experiment.fields.get("roi_target"),
                        "requires_confirmation": True,
                    },
                    "status": "waiting_approval",
                    "created_at_utc": now.isoformat(),
                    "not_before_utc": now.isoformat(),
                },
                raw_text=json.dumps(experiment.fields, ensure_ascii=False),
                source="autonomous_v2.execution_queue",
                score={"priority": int(min(score, 100)), "layer": "task_queue"},
                director_notes=["Manual execution task for TikTok MVP experiment."],
                confidence=confidence,
            )
        )
        records.append(
            IntakeRecord(
                record_type="task_priority",
                fields={
                    "task_priority_id": stable_id("tpr_", task_queue_id, now.isoformat()),
                    "task_queue_id": task_queue_id,
                    "expected_profit": expected_profit,
                    "confidence_score": confidence,
                    "time_sensitivity": 0.95,
                    "risk_score": 0.18,
                    "priority_score": score,
                    "calculated_at_utc": now.isoformat(),
                },
                raw_text=json.dumps(experiment.fields, ensure_ascii=False),
                source="autonomous_v2.priority_engine",
                score={"priority": int(min(score, 100)), "layer": "task_priority"},
                director_notes=["Task priority calculated for manual MVP execution."],
                confidence=confidence,
            )
        )
    return records


def build_v2_report(
    now: datetime,
    source_records: list[IntakeRecord],
    signals: list[IntakeRecord],
    hypotheses: list[IntakeRecord],
    experiments: list[IntakeRecord],
    reinforcement_records: list[IntakeRecord],
    priority_records: list[IntakeRecord],
) -> str:
    lines = [
        "# Autonomous Commerce OS v2 MVP Report",
        "",
        f"Run at UTC: {now.isoformat()}",
        "",
        "## MVP Boundary",
        "",
        "- Focus: TikTok / FastMoss / Kalodata signals first.",
        "- Goal: find opportunity -> generate hypothesis -> draft small experiment -> monitor metrics -> update pattern weight.",
        "- Real posting, ads, discounts, listing edits, creator outreach, refunds, shipping, and store settings still require confirmation.",
        "",
        "## Counts",
        "",
        f"- TikTok source records: {len(source_records)}",
        f"- signal_event: {len(signals)}",
        f"- hypothesis: {len(hypotheses)}",
        f"- experiment: {len(experiments)}",
        f"- reinforcement records: {len(reinforcement_records)}",
        f"- priority records: {len(priority_records)}",
        "",
        "## Top Signals",
        "",
    ]
    if not signals:
        lines.append("- No TikTok MVP signal yet. Add FastMoss/Kalodata/TikTok product/video captures first.")
    for signal in signals[:10]:
        fields = signal.fields
        lines.append(
            f"- {fields.get('engine_type')} | {fields.get('entity_label')} | velocity {fields.get('velocity')} | confidence {fields.get('confidence')} | risk {fields.get('risk_score')}"
        )
    lines.extend(["", "## Top Hypotheses", ""])
    if not hypotheses:
        lines.append("- No hypothesis generated.")
    for hypothesis in hypotheses[:8]:
        fields = hypothesis.fields
        lines.append(f"- {fields.get('hypothesis_text')} | priority {fields.get('priority_score')} | status {fields.get('status')}")
    lines.extend(["", "## MVP Experiments", ""])
    if not experiments:
        lines.append("- No MVP experiment created.")
    for experiment in experiments:
        fields = experiment.fields
        lines.append(
            f"- {fields.get('experiment_id')} | {fields.get('platform')} | budget ${fields.get('budget_limit')} | CPA {fields.get('cpa_limit')} | ROI target {fields.get('roi_target')} | {fields.get('state')}"
        )
    lines.extend(["", "## Priority Formula", ""])
    lines.append("`priority_score = expected_profit * confidence_score * time_sensitivity * (1 - risk_score)`")
    lines.extend(["", "## Next Manual Inputs Needed", ""])
    lines.append("- Import or capture TikTok/FastMoss/Kalodata product/video ranking pages for the precise target product.")
    lines.append("- After a test is manually executed, import ROI/CPA/CTR/CVR so pattern_weight can learn from outcomes.")
    lines.append("- Keep old profitable stores protected; run aggressive tests only on new or approved test stores.")
    return "\n".join(lines).rstrip() + "\n"


def build_24h_simulation_report(now: datetime, hypotheses: list[IntakeRecord], experiments: list[IntakeRecord]) -> str:
    top_hypothesis = hypotheses[0].fields if hypotheses else {}
    top_experiment = experiments[0].fields if experiments else {}
    theme = (
        top_hypothesis.get("related_entities", {}).get("keyword_or_theme")
        if isinstance(top_hypothesis.get("related_entities"), dict)
        else ""
    ) or "Dog Dad + Father's Day + emotional script"
    experiment_id = top_experiment.get("experiment_id") or "expv2_example"
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    timeline = [
        ("00:00", "Scheduler collects TikTok Top Products, Top Ads, creator spikes, and keyword heat."),
        ("02:00", f"Signal Engine detects growth around {theme}."),
        ("02:05", "Hypothesis Generator creates a commercial assumption from the signal."),
        ("02:10", "Risk Guardrail checks trademark, IP, claims, platform policy, and account health."),
        ("02:20", f"Experiment Planner drafts {experiment_id}: budget $50, CPA stop-loss $12, ROI target 2."),
        ("08:00", "Execution Queue prepares script, creator brief, product-card checklist, and manual approval task."),
        ("14:00", "Metric Monitor expects CTR/CVR/ROI import from store or ad report."),
        ("18:00", "Stop/Scale Rule decides whether to stop, keep watching, or prepare a scale plan."),
        ("22:00", "Reinforcement updates pattern_weight for keyword, hook, scene, and creator type."),
        ("23:59", "Priority Engine rebalances tomorrow's Top 10 opportunities."),
    ]
    lines = [
        "# Autonomous v2 24h Run Simulation",
        "",
        f"Simulation date UTC: {start.date().isoformat()}",
        "",
        "This is a dry-run simulation. It does not execute store, ads, listing, creator, or publishing actions.",
        "",
    ]
    for time_label, description in timeline:
        lines.append(f"## {time_label}")
        lines.append("")
        lines.append(description)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def latest_autonomous_v2_report(root: Path) -> tuple[str, Path | None]:
    output_dir = root / "outputs"
    paths = sorted(output_dir.glob(f"{AUTONOMOUS_V2_REPORT_PREFIX}_*.md"), reverse=True)
    if not paths:
        return "No Autonomous v2 report yet.", None
    path = paths[0]
    return path.read_text(encoding="utf-8"), path


def latest_autonomous_v2_simulation(root: Path) -> tuple[str, Path | None]:
    output_dir = root / "outputs"
    paths = sorted(output_dir.glob(f"{AUTONOMOUS_V2_SIMULATION_PREFIX}_*.md"), reverse=True)
    if not paths:
        return "No Autonomous v2 simulation yet.", None
    path = paths[0]
    return path.read_text(encoding="utf-8"), path


def write_output(root: Path, prefix: str, now: datetime, content: str) -> Path:
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{prefix}_{now.date().isoformat()}.md"
    path.write_text(content, encoding="utf-8")
    return path


def parse_run_at(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    clean = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", clean):
        return datetime.fromisoformat(clean).replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(clean.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha1("|".join(str(part or "") for part in parts).encode("utf-8")).hexdigest()[:18]
    return f"{prefix}{digest}"


def first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def first_number(*values: Any) -> float:
    for value in values:
        parsed = parse_number(value)
        if parsed is not None:
            return parsed
    return 0.0


def parse_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    percent = "%" in text
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group(0))
    return number / 100 if percent else number


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def seasonality_score(label: str, record: IntakeRecord) -> float:
    text = f"{label} {record.raw_text}".lower()
    signals = ["father", "mother", "christmas", "halloween", "thanksgiving", "july", "easter", "valentine", "holiday", "gift"]
    return 0.75 if any(signal in text for signal in signals) else 0.2


def saturation_score(label: str, records: list[IntakeRecord]) -> float:
    key = normalize_pattern(label)
    if not key:
        return 0.1
    count = sum(1 for record in records if key in normalize_pattern(str(record.fields.get("product_name") or record.fields.get("product_theme") or record.raw_text)))
    return clamp(count / 12, 0.05, 0.95)


def evidence_count(label: str, records: list[IntakeRecord]) -> int:
    key = normalize_pattern(label)
    if not key:
        return 1
    return max(1, sum(1 for record in records if key in normalize_pattern(str(record.fields) + record.raw_text)))


def choose_engine_type(velocity: float, z_score: float, seasonal_score: float, saturation_score_value: float) -> str:
    if saturation_score_value > 0.7:
        return "saturation"
    if seasonal_score > 0.6:
        return "seasonality"
    if z_score > 2.5:
        return "anomaly"
    return "trend"


def signal_risk_score(record: IntakeRecord) -> float:
    text = f"{record.raw_text} {record.fields}".lower()
    risky = ["disney", "nike", "nfl", "barbie", "stanley", "gucci", "carhartt", "pokemon", "super bowl"]
    return 68 if any(item in text for item in risky) else 18


def priority_from_signal(fields: dict[str, Any]) -> float:
    velocity = abs(float(fields.get("velocity") or 0))
    confidence = float(fields.get("confidence") or 0.5)
    risk = min(float(fields.get("risk_score") or 0), 95) / 100
    return clamp((velocity * 60 + confidence * 60) * (1 - risk / 2), 1, 100)


def should_alert(fields: dict[str, Any]) -> bool:
    return (
        float(fields.get("velocity") or 0) > 0.4
        or float(fields.get("z_score") or 0) > 2.5
        or float(fields.get("seasonal_score") or 0) > 0.6
        or float(fields.get("saturation_score") or 0) > 0.7
    )


def estimate_expected_profit(fields: dict[str, Any]) -> float:
    base = 180
    velocity_bonus = min(max(float(fields.get("velocity") or 0), 0), 2) * 150
    confidence_bonus = float(fields.get("confidence") or 0.5) * 120
    platform_bonus = 60 if "tiktok" in str(fields.get("platform") or "").lower() else 25
    return round(base + velocity_bonus + confidence_bonus + platform_bonus, 2)


def time_sensitivity_for(fields: dict[str, Any]) -> float:
    text = json.dumps(fields, ensure_ascii=False).lower()
    if any(token in text for token in ["father", "mother", "christmas", "halloween", "holiday", "gift"]):
        return 0.98
    return 0.82


def priority_formula(expected_profit: float, confidence: float, time_sensitivity: float, risk: float) -> float:
    return round(expected_profit * confidence * time_sensitivity * (1 - min(max(risk, 0), 0.95)), 2)


def opportunity_type_for(fields: dict[str, Any]) -> str:
    entity_type = str(fields.get("entity_type") or "")
    engine_type = str(fields.get("engine_type") or "")
    if entity_type == "video":
        return "creative_script_test"
    if entity_type == "creator":
        return "creator_seed_test"
    if engine_type == "saturation":
        return "overheat_watch_or_differentiation"
    if engine_type == "seasonality":
        return "seasonal_product_content_test"
    return "product_content_test"


def hypothesis_text_for(entity_label: str, fields: dict[str, Any], opportunity_type: str) -> str:
    if opportunity_type == "creative_script_test":
        return f"{entity_label} can be tested as a TikTok creative script pattern using hook, scene, CTA, and creator variation."
    if opportunity_type == "creator_seed_test":
        return f"{entity_label} may be a creator seeding opportunity if recent video spike and audience fit hold."
    if opportunity_type == "seasonal_product_content_test":
        return f"{entity_label} may convert when combined with seasonal timing, emotional hook, product card, and small-budget test."
    if opportunity_type == "overheat_watch_or_differentiation":
        return f"{entity_label} is active but may be crowded; test only with differentiation and strict stop-loss."
    return f"{entity_label} may be a TikTok product/content opportunity; test script, product card, price band, and comment demand."


def extract_pattern_value(hypothesis: IntakeRecord) -> str:
    fields = hypothesis.fields
    related = fields.get("related_entities") if isinstance(fields.get("related_entities"), dict) else {}
    return normalize_display(str(related.get("keyword_or_theme") or fields.get("hypothesis_text") or "unknown"))[:120]


def pattern_type_for_hypothesis(hypothesis: IntakeRecord) -> str:
    opportunity = str(hypothesis.fields.get("opportunity_type") or "")
    if "creative" in opportunity:
        return "hook"
    if "creator" in opportunity:
        return "creator"
    if "seasonal" in opportunity:
        return "keyword"
    return "product"


def normalize_pattern(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def normalize_display(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
