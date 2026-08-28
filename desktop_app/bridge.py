from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from desktop_app.teelab_desktop import DesktopApi


RESPONSE_PREFIX = "__TEELAB_BRIDGE__"
ALLOWED_METHODS = {
    "analyze_video_file",
    "browser_environment_snapshot",
    "choose_and_analyze_video",
    "choose_video_file",
    "cli_ai_connector_snapshot",
    "browser_ai_connector_snapshot",
    "multi_ai_collaboration_snapshot",
    "project_capability_profile_snapshot",
    "prepare_task_skill_packages",
    "complete_task_instruction",
    "confirm_operating_expense",
    "configure_ai_provider",
    "create_b2b_sales_execution_pack",
    "create_operating_expense_draft",
    "create_video_prompt_pack",
    "deepseek_harness_snapshot",
    "desktop_browser_action",
    "desktop_control_snapshot",
    "desktop_keyboard_action",
    "desktop_mouse_action",
    "desktop_window_action",
    "create_workspace_task",
    "get_workspace_item_context",
    "open_workspace_item_folder",
    "prepare_shein_manual_workspace",
    "create_workspace_project",
    "create_workspace_store",
    "update_workspace_item",
    "finance_settlement_snapshot",
    "export_operating_expenses",
    "get_task_instruction_status",
    "import_collection_payout_statement",
    "import_communications_message_file",
    "import_settlement_statement_file",
    "import_settlement_statement",
    "install_capability_pack",
    "open_b2b_customer_pool",
    "open_b2b_output",
    "open_creative_output",
    "open_deepseek_harness",
    "open_store_surface",
    "open_store_surfaces_parallel",
    "open_video_editor",
    "operating_expense_snapshot",
    "prepare_browser_environment",
    "prepare_deepseek_harness_project",
    "process_learning_text",
    "approve_learning_candidate",
    "learning_memory_snapshot",
    "task_history_context_snapshot",
    "build_non_api_ai_handoff",
    "evaluate_non_api_ai_delivery",
    "non_api_ai_bridge_snapshot",
    "non_api_ai_bridge_recovery_snapshot",
    "record_creative_feedback",
    "record_non_api_ai_result",
    "review_non_api_ai_result",
    "reconcile_collection_payout",
    "reconcile_settlement",
    "runtime_queue_snapshot",
    "run_cli_ai_roundtrip",
    "run_browser_ai_roundtrip",
    "run_multi_ai_collaboration",
    "save_project_capability_profile",
    "run_fictional_finance_demo",
    "save_collection_payout_estimate",
    "save_company_profile",
    "save_product_intake",
    "save_settlement_estimate",
    "save_workspace_commerce_profile",
    "save_subaccount",
    "save_task_configuration",
    "smart_capability_context_preview",
    "set_subaccount_active",
    "start_task_instruction",
    "test_ai_provider",
}


def configure_utf8_stdio() -> None:
    """Keep Electron's JSONL bridge Unicode-safe on every Windows code page."""

    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="strict")


def dispatch(api: DesktopApi, method: str, args: list[Any]) -> Any:
    method = str(method or "").strip()
    if method not in ALLOWED_METHODS:
        raise ValueError(f"Desktop method is not allowed: {method}")
    target = getattr(api, method, None)
    if not callable(target):
        raise ValueError(f"Desktop method is unavailable: {method}")
    return target(*args)


def emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(RESPONSE_PREFIX + json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def run(root: Path) -> int:
    configure_utf8_stdio()
    api = DesktopApi(root.resolve())
    api.start_runtime_recovery()
    try:
        emit({"type": "ready", "ok": True})
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            request_id = ""
            try:
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise ValueError("Bridge request must be an object.")
                request_id = str(request.get("id") or "")
                args = request.get("args")
                if not isinstance(args, list):
                    args = []
                result = dispatch(api, str(request.get("method") or ""), args)
                emit({"id": request_id, "ok": True, "result": result})
            except Exception as exc:
                traceback.print_exc(file=sys.stderr)
                emit({"id": request_id, "ok": False, "error": str(exc)})
    finally:
        api.stop_runtime_recovery()
    return 0


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    return run(Path(args.root))


if __name__ == "__main__":
    raise SystemExit(main())
