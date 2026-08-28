from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ALLOWED_ACTION_CLASSES = {"browser_readonly", "windows_local_test"}


def _workspace_file(root: Path, value: Any, label: str) -> tuple[Path, str]:
    relative = Path(str(value or "").strip())
    if not str(relative) or relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label}必须是工作区内的安全相对路径。")
    root_resolved = root.resolve()
    target = (root / relative).resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"{label}超出工作区。") from exc
    if not target.is_file():
        raise ValueError(f"{label}不存在。")
    return target, target.relative_to(root_resolved).as_posix()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_local_operator_receipt(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    action_class = str(payload.get("action_class") or "").strip().lower()
    if action_class not in ALLOWED_ACTION_CLASSES:
        raise ValueError("本地操作回执类型无效。")
    evidence: dict[str, Any] = {}
    screenshot_value = str(payload.get("screenshot_ref") or "").strip()
    if screenshot_value:
        screenshot_path, screenshot_ref = _workspace_file(root, screenshot_value, "截图")
        evidence.update(
            {
                "screenshot_ref": screenshot_ref,
                "screenshot_sha256": _sha256(screenshot_path),
            }
        )
    elif action_class == "windows_local_test":
        capture_id = str(payload.get("screenshot_capture_id") or "").strip()
        if not capture_id:
            raise ValueError("Windows 本地测试回执缺少视觉捕获证据。")
        evidence.update(
            {
                "screenshot_capture_id": capture_id[:120],
                "screenshot_storage": "computer_use_ephemeral_capture",
                "visual_verified": bool(payload.get("visual_verified")),
            }
        )
    else:
        raise ValueError("浏览器只读回执缺少工作区截图。")
    snapshot_ref = str(payload.get("snapshot_ref") or "").strip()
    if snapshot_ref:
        snapshot_path, clean_snapshot_ref = _workspace_file(root, snapshot_ref, "页面快照")
        evidence.update(
            {
                "snapshot_ref": clean_snapshot_ref,
                "snapshot_sha256": _sha256(snapshot_path),
            }
        )

    source_url = str(payload.get("source_url") or "").strip()
    if action_class == "browser_readonly":
        parsed = urlparse(source_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("浏览器只读回执缺少 HTTP(S) 来源。")
        if str(payload.get("http_method") or "GET").upper() != "GET":
            raise ValueError("浏览器只读回执只允许 GET。")
        if int(payload.get("browser_write_action_count") or 0) != 0:
            raise ValueError("浏览器只读回执不得包含写动作。")
        evidence.update(
            {
                "source_url": source_url,
                "page_title": str(payload.get("page_title") or "").strip()[:240],
                "http_method": "GET",
                "interactions": [
                    str(item)[:120]
                    for item in (payload.get("interactions") or [])[:20]
                    if str(item).strip()
                ],
                "browser_write_action_count": 0,
            }
        )
    else:
        if source_url:
            raise ValueError("Windows 本地测试回执不得伪造网页来源。")
        if int(payload.get("external_window_action_count") or 0) != 0:
            raise ValueError("Windows 本地测试回执不得包含外部软件或账号动作。")
        application_artifact = str(payload.get("application_artifact_ref") or "").strip()
        if application_artifact:
            artifact_path, clean_artifact_ref = _workspace_file(
                root, application_artifact, "本地测试应用"
            )
            evidence.update(
                {
                    "application_artifact_ref": clean_artifact_ref,
                    "application_artifact_sha256": _sha256(artifact_path),
                }
            )
        evidence.update(
            {
                "application": str(payload.get("application") or "").strip()[:120],
                "window_title": str(payload.get("window_title") or "").strip()[:240],
                "interactions": [
                    str(item)[:120]
                    for item in (payload.get("interactions") or [])[:20]
                    if str(item).strip()
                ],
                "typed_text_classification": str(payload.get("typed_text_classification") or "synthetic_non_sensitive"),
                "observed_status": str(payload.get("observed_status") or "").strip()[:400],
                "external_window_action_count": 0,
            }
        )

    identity = {
        "workspace_id": str(payload.get("workspace_id") or "local-workspace")[:120],
        "project_id": str(payload.get("project_id") or "runtime-acceptance")[:120],
        "task_id": str(payload.get("task_id") or "runtime-acceptance")[:120],
        "run_id": str(payload.get("run_id") or "")[:120],
        "execution_identity_id": str(payload.get("execution_identity_id") or "local-acceptance")[:120],
    }
    canonical = json.dumps(
        {"schema_version": 1, "action_class": action_class, "identity": identity, "evidence": evidence},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    receipt_id = "operator-receipt-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
    receipt = {
        "schema_version": 1,
        "receipt_id": receipt_id,
        "status": "read_only_observation_complete" if action_class == "browser_readonly" else "local_test_interaction_complete",
        "action_class": action_class,
        "captured_at": str(payload.get("captured_at") or "").strip()
        or datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "identity": identity,
        "evidence": evidence,
        "external_business_action_count": 0,
        "credential_count": 0,
        "approval_required": False,
        "receipt_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    output_dir = root / "outputs" / "operator_receipts"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{receipt_id}.json"
    if output_path.is_file():
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        return {**existing, "idempotent_reuse": True, "output_ref": output_path.relative_to(root).as_posix()}
    output_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {**receipt, "idempotent_reuse": False, "output_ref": output_path.relative_to(root).as_posix()}
