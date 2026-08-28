from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


SUPPORTED_METRICS = {
    "impressions",
    "views",
    "three_second_views",
    "average_watch_seconds",
    "completion_rate",
    "retention_25_rate",
    "retention_50_rate",
    "retention_75_rate",
    "rewatches",
    "likes",
    "comments",
    "shares",
    "saves",
    "clicks",
    "profile_visits",
    "followers_gained",
    "leads",
    "negative_feedback",
    "orders",
    "spend",
    "revenue",
    "refunds",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def _prediction_payload(experiment: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": str(experiment.get("experiment_id") or ""),
        "mode": str(experiment.get("mode") or ""),
        "primary_metric": str(experiment.get("primary_metric") or ""),
        "prediction_recorded_at": str(experiment.get("prediction_recorded_at") or ""),
        "variants": experiment.get("variants") if isinstance(experiment.get("variants"), list) else [],
    }


def prediction_sha256(experiment: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        _prediction_payload(experiment), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_content_experiment(
    *,
    experiment_id: str,
    template_id: str,
    platform: str,
    country_site: str,
    primary_metric: str = "views",
    variants: Sequence[Mapping[str, Any]] | None = None,
    account_baseline_ref: str = "",
    recorded_at: str = "",
) -> dict[str, Any]:
    """Create a blind, immutable prediction contract before publication.

    This is a local content-operations contract. It never publishes content,
    reads a social account, changes ad spend, or treats a prediction as an
    observed result.
    """

    clean_id = _clean(experiment_id, 160)
    if not clean_id:
        raise ValueError("内容实验必须有 experiment_id。")
    metric = _clean(primary_metric, 80).lower()
    if metric not in SUPPORTED_METRICS:
        raise ValueError("内容实验的 primary_metric 不受支持。")
    source_variants = list(variants or ())
    if not source_variants:
        source_variants = [
            {
                "variant_id": "pain-hook",
                "hypothesis": "真实痛点先出现，可能提高前三秒继续观看。",
                "predicted_rank": 2,
                "rubric_scores": {"hook_clarity": 8, "product_proof": 7, "originality": 7},
            },
            {
                "variant_id": "result-hook",
                "hypothesis": "先展示可核验结果，可能提高观看和点击。",
                "predicted_rank": 1,
                "rubric_scores": {"hook_clarity": 9, "product_proof": 9, "originality": 7},
            },
            {
                "variant_id": "identity-scene",
                "hypothesis": "先说明人群与场景，可能提高目标受众互动。",
                "predicted_rank": 3,
                "rubric_scores": {"hook_clarity": 7, "product_proof": 7, "originality": 8},
            },
        ]
    if not 2 <= len(source_variants) <= 8:
        raise ValueError("内容实验需要 2 到 8 个变体。")
    clean_variants: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_ranks: set[int] = set()
    for raw in source_variants:
        if not isinstance(raw, Mapping):
            raise ValueError("内容实验变体必须是对象。")
        variant_id = _clean(raw.get("variant_id"), 120)
        hypothesis = _clean(raw.get("hypothesis"), 600)
        if not variant_id or variant_id in seen_ids or not hypothesis:
            raise ValueError("内容实验变体需要唯一编号和明确假设。")
        try:
            rank = int(raw.get("predicted_rank"))
        except (TypeError, ValueError) as exc:
            raise ValueError("每个变体必须有唯一 predicted_rank。") from exc
        if not 1 <= rank <= len(source_variants) or rank in seen_ranks:
            raise ValueError("predicted_rank 必须是从 1 开始的不重复连续名次。")
        scores_source = raw.get("rubric_scores") if isinstance(raw.get("rubric_scores"), Mapping) else {}
        scores: dict[str, float] = {}
        for key, value in scores_source.items():
            name = _clean(key, 80)
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError("rubric_scores 必须是 0 到 10 的数字。") from exc
            if not name or number < 0 or number > 10:
                raise ValueError("rubric_scores 必须是 0 到 10 的数字。")
            scores[name] = round(number, 3)
        if not scores:
            raise ValueError("每个变体至少需要一个 rubric score。")
        seen_ids.add(variant_id)
        seen_ranks.add(rank)
        clean_variants.append(
            {
                "variant_id": variant_id,
                "hypothesis": hypothesis,
                "predicted_rank": rank,
                "rubric_scores": scores,
            }
        )
    if seen_ranks != set(range(1, len(clean_variants) + 1)):
        raise ValueError("predicted_rank 必须覆盖全部连续名次。")
    experiment = {
        "schema_version": 1,
        "experiment_id": clean_id,
        "template_id": _clean(template_id, 160),
        "platform": _clean(platform, 120),
        "country_site": _clean(country_site, 20).upper() or "GLOBAL",
        "mode": "calibration" if _clean(account_baseline_ref) else "cold_start",
        "primary_metric": metric,
        "account_baseline_ref": _clean(account_baseline_ref, 500),
        "prediction_status": "immutable_blind_prediction",
        "prediction_recorded_at": _clean(recorded_at, 80) or _now_iso(),
        "variants": sorted(clean_variants, key=lambda item: item["predicted_rank"]),
        "observation_status": "not_observed",
        "external_action_performed": False,
        "owner_review_required_for_publish": True,
        "automatic_rubric_update_allowed": False,
        "method_reference": {
            "repository": "XBuilderLAB/cheat-on-content",
            "pinned_commit": "9c42fe0c932fe81a12f07428492bdf7ae8488f41",
            "reuse": "clean_room_method_reference_only",
            "installed": False,
        },
    }
    experiment["prediction_sha256"] = prediction_sha256(experiment)
    return experiment


def evaluate_content_observation(
    experiment: Mapping[str, Any],
    *,
    variant_id: str,
    metrics: Mapping[str, Any],
    evidence_ref: str,
    window_start: str,
    window_end: str,
) -> dict[str, Any]:
    """Record an observation without rewriting the blind prediction."""

    expected_hash = _clean(experiment.get("prediction_sha256"), 80)
    if not expected_hash or expected_hash != prediction_sha256(experiment):
        raise ValueError("内容实验的盲预测已变化，不能回写观察结果。")
    clean_variant = _clean(variant_id, 120)
    variants = experiment.get("variants") if isinstance(experiment.get("variants"), list) else []
    predicted = next(
        (item for item in variants if isinstance(item, Mapping) and item.get("variant_id") == clean_variant),
        None,
    )
    if predicted is None:
        raise ValueError("观察结果没有对应的预测变体。")
    clean_metrics: dict[str, float] = {}
    for key, value in metrics.items():
        metric = _clean(key, 80).lower()
        if metric not in SUPPORTED_METRICS or isinstance(value, bool):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number < 0:
            raise ValueError("内容观察指标不能为负数。")
        clean_metrics[metric] = number
    primary_metric = str(experiment.get("primary_metric") or "")
    if primary_metric not in clean_metrics:
        raise ValueError("观察结果必须包含实验的 primary_metric。")
    if not _clean(evidence_ref, 1000) or not _clean(window_start, 80) or not _clean(window_end, 80):
        raise ValueError("内容观察必须有证据引用和统计窗口。")
    return {
        "experiment_id": str(experiment.get("experiment_id") or ""),
        "variant_id": clean_variant,
        "prediction_sha256": expected_hash,
        "predicted_rank": int(predicted.get("predicted_rank") or 0),
        "primary_metric": primary_metric,
        "observed_primary_value": clean_metrics[primary_metric],
        "metrics": clean_metrics,
        "evidence_ref": _clean(evidence_ref, 1000),
        "window_start": _clean(window_start, 80),
        "window_end": _clean(window_end, 80),
        "observation_status": "evidence_recorded",
        "calibration_status": "pending_comparable_variants",
        "calibration_reason": "需要同一实验其余变体在可比窗口的证据，才能核对预测排序。",
        "rubric_update": "owner_review_candidate_only",
        "external_action_performed": False,
        "recorded_at": _now_iso(),
    }
