from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .creative_video import analyze_video
from .expert_learning_policy import load_expert_learning_policy


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("视频来源 URL 必须是 http(s) 公共地址。")
    if parsed.username or parsed.password:
        raise ValueError("视频来源 URL 不能携带登录凭据。")
    return raw[:2000]


def _existing_file(value: Any) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    return path if path.is_file() else None


def prepare_video_learning_intake(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    policy = load_expert_learning_policy(root)
    video_policy = policy["video_learning"]
    rights_basis = str(payload.get("rights_basis") or "").strip().lower()
    allowed_rights = set(video_policy.get("rights_basis") or [])
    source_url = _safe_url(payload.get("source_url"))
    local_media = _existing_file(payload.get("local_media_path"))
    transcript = _existing_file(payload.get("transcript_path"))
    target = str(payload.get("target_expert_id") or payload.get("task_id") or "").strip()[:160]
    missing: list[str] = []
    if rights_basis not in allowed_rights:
        missing.append("verified_rights_basis")
    if not target:
        missing.append("target_expert_or_task")
    if not source_url and local_media is None and transcript is None:
        missing.append("source_url_local_media_or_transcript")

    if missing:
        return {
            "ok": False,
            "status": "blocked_source_contract",
            "missing": missing,
            "external_actions": [],
        }

    if source_url and local_media is None and transcript is None:
        return {
            "ok": False,
            "status": "blocked_connector",
            "missing": ["permitted_local_media_or_transcript", "approved_network_video_fetch_connector"],
            "source_url": source_url,
            "rights_basis": rights_basis,
            "target": target,
            "stop_rules": video_policy.get("stop_rules") or [],
            "external_actions": [],
        }

    selected = local_media or transcript
    return {
        "ok": True,
        "status": "ready_local_analysis" if local_media else "ready_transcript_review",
        "source_url": source_url,
        "input_path": str(selected),
        "input_kind": "video" if local_media else "transcript",
        "input_sha256": _sha256(selected),
        "rights_basis": rights_basis,
        "target": target,
        "temporary_download": bool(payload.get("temporary_download")),
        "delete_after_learning": bool(payload.get("delete_after_learning")),
        "owner_approved_delete": bool(payload.get("owner_approved_delete")),
        "external_actions": [],
    }


def _write_receipt(root: Path, receipt: dict[str, Any]) -> Path:
    output_dir = root / "outputs" / "video_learning"
    output_dir.mkdir(parents=True, exist_ok=True)
    digest = str(receipt.get("input_sha256") or "nohash")[:12]
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
    path = output_dir / f"learning-receipt-{stamp}-{digest}.json"
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _is_designated_temp_path(root: Path, path: Path, policy: dict[str, Any]) -> bool:
    resolved = path.resolve()
    for relative in policy["video_learning"].get("temporary_roots") or []:
        allowed = (root / str(relative)).resolve()
        if resolved == allowed or allowed in resolved.parents:
            return True
    return False


def delete_temporary_video_after_learning(
    root: Path,
    *,
    path: str | Path,
    expected_sha256: str,
    analysis_succeeded: bool,
    receipt_path: str | Path,
    temporary_download: bool,
    owner_approved_delete: bool,
) -> dict[str, Any]:
    policy = load_expert_learning_policy(root)
    target = Path(path).expanduser().resolve()
    receipt = Path(receipt_path).expanduser().resolve()
    checks = {
        "temporary_download_true": temporary_download is True,
        "owner_approved_delete_true": owner_approved_delete is True,
        "analysis_succeeded": analysis_succeeded is True,
        "receipt_persisted": receipt.is_file(),
        "path_inside_designated_temporary_root": _is_designated_temp_path(root, target, policy),
        "exact_hash_unchanged": target.is_file() and _sha256(target) == expected_sha256,
    }
    missing = [key for key, passed in checks.items() if not passed]
    if missing:
        return {"ok": False, "status": "blocked_delete_gate", "missing": missing, "deleted": False}
    target.unlink()
    return {
        "ok": True,
        "status": "temporary_source_deleted",
        "deleted": True,
        "deleted_path": str(target),
        "deleted_sha256": expected_sha256,
        "receipt_path": str(receipt),
    }


def run_local_video_learning(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    intake = prepare_video_learning_intake(root, payload)
    if not intake.get("ok"):
        return intake
    if intake["input_kind"] != "video":
        receipt = {
            **intake,
            "generated_at": _now_iso(),
            "status": "transcript_ready_for_semantic_review",
            "claim_boundary": "A transcript was fingerprinted; no video semantics or platform outcome is claimed.",
        }
        receipt_path = _write_receipt(root, receipt)
        return {**receipt, "receipt_path": str(receipt_path)}

    analysis = analyze_video(root, intake["input_path"])
    succeeded = bool(analysis.get("ok"))
    receipt = {
        **intake,
        "generated_at": _now_iso(),
        "status": "local_analysis_complete" if succeeded else "local_analysis_failed",
        "analysis": analysis,
        "claim_boundary": "Technical analysis is evidence input, not proof that a platform rule or sales tactic is generally true.",
    }
    receipt_path = _write_receipt(root, receipt)
    deletion = {"ok": True, "status": "source_retained", "deleted": False}
    if intake.get("delete_after_learning"):
        deletion = delete_temporary_video_after_learning(
            root,
            path=intake["input_path"],
            expected_sha256=intake["input_sha256"],
            analysis_succeeded=succeeded,
            receipt_path=receipt_path,
            temporary_download=bool(intake.get("temporary_download")),
            owner_approved_delete=bool(intake.get("owner_approved_delete")),
        )
    return {**receipt, "receipt_path": str(receipt_path), "deletion": deletion}
