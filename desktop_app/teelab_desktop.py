from __future__ import annotations

import argparse
import json
import hashlib
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urlsplit
from pathlib import Path

from ai_ecommerce_director.desktop_backend_compatibility import (
    DESKTOP_RUNTIME_VERSION,
    backend_source_signature,
)

try:
    import webview
except ModuleNotFoundError:
    # Electron only imports DesktopApi through bridge.py. PyWebView is optional
    # unless this legacy standalone launcher is started directly.
    webview = None


APP_TITLE = "T-one"
DEFAULT_PORT = 8767
DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DesktopApi:
    STORE_SURFACES = {"home", "inventory", "orders", "ads", "coupons"}

    def __init__(self, root: Path, port: int = DEFAULT_PORT) -> None:
        self.root = root
        self.port = int(port)
        self.window: webview.Window | None = None
        self.latest_creative_output: Path | None = None
        self.latest_b2b_output: Path | None = None
        self.instance_id = f"desktop-{os.getpid()}-{uuid.uuid4().hex[:10]}"
        runtime_policy = self._task_execution_module().runtime_worker_policy(self.root)
        self._worker_count = int(runtime_policy["max_workers"])
        self._worker_pending_limit = int(runtime_policy["max_pending_in_memory"])
        self._worker_submit_limit = int(runtime_policy["max_submitted_in_memory"])
        self._recovery_batch_limit = int(runtime_policy["recovery_batch_limit"])
        self._recovery_poll_seconds = int(runtime_policy["poll_seconds"])
        self._worker_queue: queue.Queue[tuple[str, dict[str, object], bool]] = queue.Queue(
            maxsize=max(1, self._worker_pending_limit)
        )
        self._workers: dict[str, threading.Thread] = {}
        self._worker_threads: list[threading.Thread] = []
        self._scheduled_run_ids: set[str] = set()
        self._active_run_ids: set[str] = set()
        self._worker_stop = threading.Event()
        self._workers_lock = threading.RLock()
        self._recovery_stop = threading.Event()
        self._recovery_thread: threading.Thread | None = None
        self._deepseek_harness_processes: dict[str, subprocess.Popen[object]] = {}
        self._deepseek_harness_urls: dict[str, str] = {}

    def _creative_module(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from ai_ecommerce_director import creative_video

        return creative_video

    def _content_feedback_module(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from ai_ecommerce_director import content_feedback_loop

        return content_feedback_loop

    def _b2b_module(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from ai_ecommerce_director import b2b_sales_runtime

        return b2b_sales_runtime

    def _provider_module(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from ai_ecommerce_director import ai_provider_catalog

        return ai_provider_catalog

    def _non_api_ai_bridge_module(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from ai_ecommerce_director import non_api_ai_bridge

        return non_api_ai_bridge

    def _cli_ai_connector_module(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from ai_ecommerce_director import cli_ai_connector

        return cli_ai_connector

    def _browser_ai_connector_module(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from ai_ecommerce_director import browser_ai_connector

        return browser_ai_connector

    def _multi_ai_collaboration_module(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from ai_ecommerce_director import multi_ai_collaboration

        return multi_ai_collaboration

    def _project_capability_profiles_module(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from ai_ecommerce_director import project_capability_profiles

        return project_capability_profiles

    def _company_module(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from ai_ecommerce_director import company_workspace

        return company_workspace

    def _product_intake_module(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from ai_ecommerce_director import product_data_intake

        return product_data_intake

    def _learning_distillation_module(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from ai_ecommerce_director import external_ai_distillation

        return external_ai_distillation

    def _workspace_runtime_module(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from ai_ecommerce_director import workspace_runtime

        return workspace_runtime

    def _deepseek_harness_module(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from ai_ecommerce_director import deepseek_harness_runtime

        return deepseek_harness_runtime

    def _platform_finance_module(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from ai_ecommerce_director import platform_settlement_finance

        return platform_settlement_finance

    def _operating_expense_module(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from ai_ecommerce_director import operating_expense_ledger

        return operating_expense_ledger

    def _browser_environment_module(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from ai_ecommerce_director import browser_environments

        return browser_environments

    def _desktop_control_module(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from ai_ecommerce_director import desktop_control

        return desktop_control

    def _task_execution_module(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from ai_ecommerce_director import task_execution_runtime

        return task_execution_runtime

    def _spawn_task_worker(
        self,
        run_id: str,
        payload: dict[str, object],
        *,
        recovered: bool = False,
    ) -> bool:
        run_id = str(run_id or "").strip().lower()
        if not run_id:
            return False
        self._ensure_worker_pool()
        with self._workers_lock:
            if run_id in self._scheduled_run_ids:
                return False
            if len(self._scheduled_run_ids) >= self._worker_submit_limit:
                return False
            self._scheduled_run_ids.add(run_id)
            try:
                self._worker_queue.put_nowait((run_id, dict(payload), recovered))
            except queue.Full:
                self._scheduled_run_ids.discard(run_id)
                return False
            return True

    def _ensure_worker_pool(self) -> None:
        with self._workers_lock:
            if self._worker_threads:
                return
            self._worker_stop.clear()
            for index in range(self._worker_count):
                worker = threading.Thread(
                    target=self._worker_loop,
                    name=f"teelab-shared-worker-{index + 1}",
                    daemon=True,
                )
                self._worker_threads.append(worker)
                worker.start()

    def _worker_loop(self) -> None:
        while not self._worker_stop.is_set():
            try:
                run_id, payload, recovered = self._worker_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if self._worker_stop.is_set():
                with self._workers_lock:
                    self._scheduled_run_ids.discard(run_id)
                self._worker_queue.task_done()
                break
            current = threading.current_thread()
            with self._workers_lock:
                self._active_run_ids.add(run_id)
                self._workers[run_id] = current
            try:
                self._execute_task_run(run_id, payload, recovered)
            finally:
                with self._workers_lock:
                    self._workers.pop(run_id, None)
                    self._active_run_ids.discard(run_id)
                    self._scheduled_run_ids.discard(run_id)
                self._worker_queue.task_done()

    def _recover_incomplete_task_runs(self) -> None:
        runtime = self._task_execution_module()
        runtime.mark_stale_analysis_runs(self.root)
        for run in runtime.recoverable_task_runs(
            self.root,
            limit=self._recovery_batch_limit,
        ):
            payload = run.get("execution_payload")
            self._spawn_task_worker(
                str(run.get("id") or ""),
                dict(payload) if isinstance(payload, dict) else {},
                recovered=True,
            )

    def _recovery_loop(self) -> None:
        while not self._recovery_stop.is_set():
            try:
                self._recover_incomplete_task_runs()
            except (OSError, RuntimeError, TypeError, ValueError):
                pass
            self._recovery_stop.wait(self._recovery_poll_seconds)

    def start_runtime_recovery(self) -> None:
        if self._recovery_thread and self._recovery_thread.is_alive():
            return
        self._recovery_stop.clear()
        self._ensure_worker_pool()
        self._recovery_thread = threading.Thread(
            target=self._recovery_loop,
            name="teelab-runtime-recovery",
            daemon=True,
        )
        self._recovery_thread.start()

    def stop_runtime_recovery(self) -> None:
        self._recovery_stop.set()
        self._worker_stop.set()
        if self._recovery_thread and self._recovery_thread.is_alive():
            self._recovery_thread.join(timeout=2)
        deadline = time.monotonic() + 2
        for worker in self._worker_threads:
            remaining = max(0.0, deadline - time.monotonic())
            if remaining <= 0:
                break
            if worker.is_alive():
                worker.join(timeout=remaining)
        for key, process in list(self._deepseek_harness_processes.items()):
            if process.poll() is None:
                self._deepseek_harness_module().DeepSeekHarnessRuntime.stop_project_web(process)
            self._deepseek_harness_processes.pop(key, None)
            self._deepseek_harness_urls.pop(key, None)

    def runtime_queue_snapshot(self) -> dict[str, object]:
        runtime = self._task_execution_module()
        snapshot = runtime.runtime_queue_snapshot(self.root)
        with self._workers_lock:
            scheduled_count = len(self._scheduled_run_ids)
            active_count = len(self._active_run_ids)
        snapshot["local_worker_pool"] = {
            "max_workers": self._worker_count,
            "max_pending_in_memory": self._worker_pending_limit,
            "max_submitted_in_memory": self._worker_submit_limit,
            "active_count": active_count,
            "scheduled_in_memory_count": scheduled_count,
            "backpressure_active": scheduled_count >= self._worker_submit_limit,
            "durable_overflow_behavior": "leave_run_in_sqlite_queue_for_recovery",
        }
        return snapshot

    def _account_module(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        from ai_ecommerce_director import account

        return account

    def _desktop_owner_session(self) -> dict[str, object]:
        account = self._account_module()
        try:
            session = account.current_session(self.root, account.session_token(self.root))
        except (OSError, TypeError, ValueError):
            session = None
        return dict(session or {
            "is_owner": True,
            "login_id": "desktop-owner",
            "permissions": [item["id"] for item in account.PERMISSION_CATALOG],
            "project_scope": "all",
            "task_scope": "all",
            "platform_scope": "all",
            "country_scope": "all",
            "store_scope": "all",
        })

    def create_workspace_task(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        try:
            return self._workspace_runtime_module().create_workspace_task(
                self.root, dict(payload or {}), actor="desktop-owner"
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def open_workspace_item_folder(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        data = dict(payload or {})
        try:
            folder, relative_folder = self._workspace_runtime_module().workspace_item_local_folder(
                self.root,
                str(data.get("item_type") or ""),
                str(data.get("item_id") or ""),
            )
            subprocess.Popen(["explorer.exe", str(folder)])
            return {
                "ok": True,
                "local_folder": relative_folder,
                "message": f"已打开：{relative_folder}",
                "external_actions": 0,
            }
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def get_workspace_item_context(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        data = dict(payload or {})
        try:
            result = self._workspace_runtime_module().workspace_item_context(
                self.root,
                str(data.get("item_type") or ""),
                str(data.get("item_id") or ""),
            )
            return {"ok": True, **result, "external_actions": 0}
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def deepseek_harness_snapshot(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        data = dict(payload or {})
        try:
            runtime = self._deepseek_harness_module().DeepSeekHarnessRuntime.discover()
            result: dict[str, object] = dict(runtime.status())
            item_type = str(data.get("item_type") or "").strip().lower()
            item_id = str(data.get("item_id") or "").strip().lower()
            if item_type and item_id:
                folder, relative_folder = self._workspace_runtime_module().workspace_item_local_folder(
                    self.root, item_type, item_id
                )
                integration_root = folder / ".tone" / "deepseek-harness"
                result["item_type"] = item_type
                result["item_id"] = item_id
                result["local_folder"] = relative_folder
                result["project_enabled"] = (
                    (integration_root / "tone-mcp.patch.yml").is_file()
                    and (integration_root / "integration.json").is_file()
                )
            else:
                result["project_enabled"] = False
            result["tool_count"] = len(
                self._deepseek_harness_module().DeepSeekHarnessToolGateway(self.root).list_tools()
            )
            result["desktop_method_count"] = len(
                self._deepseek_harness_module().DeepSeekHarnessToolGateway(self.root)._desktop_methods()
            )
            result["external_actions"] = 0
            return result
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc), "external_actions": 0}

    def prepare_deepseek_harness_project(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        data = dict(payload or {})
        try:
            item_type = str(data.get("item_type") or "project").strip().lower()
            item_id = str(data.get("item_id") or "").strip().lower()
            folder, relative_folder = self._workspace_runtime_module().workspace_item_local_folder(
                self.root, item_type, item_id
            )
            runtime = self._deepseek_harness_module().DeepSeekHarnessRuntime.discover()
            result = runtime.prepare_project(folder)
            return {
                **result,
                "ok": True,
                "item_type": item_type,
                "item_id": item_id,
                "local_folder": relative_folder,
                "external_actions": 0,
            }
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc), "external_actions": 0}

    def open_deepseek_harness(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        data = dict(payload or {})
        if data.get("owner_confirmed") is not True:
            return {"ok": False, "error": "启动本机 DeepSeek Harness 需要负责人确认。"}
        prepared = self.prepare_deepseek_harness_project(data)
        if prepared.get("ok") is not True:
            return prepared
        key = str(prepared.get("project_root") or "").casefold()
        current = self._deepseek_harness_processes.get(key)
        if current is not None and current.poll() is None:
            return {
                "ok": True,
                "pid": current.pid,
                "url": self._deepseek_harness_urls.get(key, "http://127.0.0.1:3080"),
                "project_root": str(prepared.get("project_root") or ""),
                "reused": True,
                "external_actions": 0,
            }
        try:
            runtime = self._deepseek_harness_module().DeepSeekHarnessRuntime.discover()
            process, result = runtime.start_project_web(
                Path(str(prepared["project_root"])),
                patch_path=Path(str(prepared["patch_path"])),
                preferred_port=int(data.get("port") or 3080),
            )
            self._deepseek_harness_processes[key] = process
            self._deepseek_harness_urls[key] = str(result.get("url") or "")
            return {**result, "item_type": prepared.get("item_type"), "item_id": prepared.get("item_id")}
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc), "external_actions": 0}

    def prepare_shein_manual_workspace(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        """Prepare and optionally open a task-local, zero-store-write workspace."""

        try:
            from ai_ecommerce_director.shein_manual_operator import (
                prepare_shein_manual_workspace,
            )

            data = dict(payload or {})
            result = prepare_shein_manual_workspace(self.root, data)
            if data.get("open_folder") is not False:
                subprocess.Popen(["explorer.exe", str(result["absolute_folder"])])
            return result
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def browser_environment_snapshot(self) -> dict[str, object]:
        try:
            return self._browser_environment_module().browser_environment_snapshot(self.root)
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def desktop_control_snapshot(self) -> dict[str, object]:
        try:
            return self._desktop_control_module().desktop_control_snapshot()
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def _desktop_control_result(self, result: dict[str, object]) -> dict[str, object]:
        if result.get("ok"):
            result["receipt_path"] = self._desktop_control_module().append_desktop_control_receipt(
                self.root, result
            )
        return result

    def desktop_mouse_action(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        try:
            result = self._desktop_control_module().desktop_mouse_action(dict(payload or {}))
            return self._desktop_control_result(result)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def desktop_keyboard_action(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        try:
            result = self._desktop_control_module().desktop_keyboard_action(dict(payload or {}))
            return self._desktop_control_result(result)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def desktop_window_action(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        try:
            result = self._desktop_control_module().desktop_window_action(dict(payload or {}))
            return self._desktop_control_result(result)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def desktop_browser_action(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        request = dict(payload or {})
        try:
            if str(request.get("action") or "").strip().lower() == "prepare_profile":
                if request.get("owner_confirmed") is not True:
                    raise ValueError("本次受控浏览器操作需要负责人明确确认。")
                result = self._browser_environment_module().prepare_browser_environment(
                    self.root, request
                )
            else:
                result = self._desktop_control_module().desktop_browser_action(request)
            return self._desktop_control_result(dict(result or {}))
        except (ConnectionError, OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def prepare_browser_environment(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        try:
            return self._browser_environment_module().prepare_browser_environment(
                self.root, dict(payload or {})
            )
        except (ConnectionError, OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def navigate_desktop(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        href = str(dict(payload or {}).get("href") or "").strip()
        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc or not parsed.path.startswith("/") or href.startswith("//"):
            return {"ok": False, "error": "只能打开当前 T-one 工作区页面。"}
        target = f"http://127.0.0.1:{self.port}{parsed.path}"
        if parsed.query:
            target += f"?{parsed.query}"
        if parsed.fragment:
            target += f"#{parsed.fragment}"

        def load_target() -> None:
            try:
                if self.window is not None:
                    self.window.load_url(target)
            except Exception:
                return

        threading.Timer(0.08, load_target).start()
        return {"ok": True, "href": href}

    def create_workspace_project(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        try:
            return self._workspace_runtime_module().create_workspace_project(
                self.root, dict(payload or {}), actor="desktop-owner"
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def create_workspace_store(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        try:
            return self._workspace_runtime_module().create_workspace_store(
                self.root, dict(payload or {}), actor="desktop-owner"
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def save_workspace_commerce_profile(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        try:
            return self._workspace_runtime_module().save_workspace_commerce_profile(
                self.root, dict(payload or {}), actor="desktop-owner"
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def update_workspace_item(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        try:
            return self._workspace_runtime_module().update_workspace_item(
                self.root, dict(payload or {}), actor="desktop-owner"
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def save_task_configuration(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        try:
            return self._workspace_runtime_module().save_task_configuration(
                self.root, dict(payload or {}), actor="desktop-owner"
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def finance_settlement_snapshot(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        data = dict(payload or {})
        try:
            return self._platform_finance_module().finance_settlement_snapshot(
                self.root,
                project_id=str(data.get("project_id") or ""),
                task_id=str(data.get("task_id") or ""),
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def save_settlement_estimate(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        try:
            return self._platform_finance_module().save_pre_operation_estimate(
                self.root,
                dict(payload or {}),
                actor="desktop-owner",
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def import_settlement_statement(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        try:
            return self._platform_finance_module().import_platform_settlement_statement(
                self.root,
                dict(payload or {}),
                actor="desktop-owner",
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def import_settlement_statement_file(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        try:
            return self._platform_finance_module().import_settlement_statement_file(
                self.root,
                dict(payload or {}),
                actor="desktop-owner",
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def import_communications_message_file(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        try:
            from ai_ecommerce_director.communications_connector_control import (
                import_communications_message_file,
            )

            return import_communications_message_file(
                self.root,
                dict(payload or {}),
                actor="desktop-owner",
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def reconcile_settlement(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        try:
            return self._platform_finance_module().reconcile_estimate_with_statement(
                self.root,
                dict(payload or {}),
                actor="desktop-owner",
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def save_collection_payout_estimate(
        self,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        try:
            return self._platform_finance_module().save_collection_payout_estimate(
                self.root,
                dict(payload or {}),
                actor="desktop-owner",
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def import_collection_payout_statement(
        self,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        try:
            return self._platform_finance_module().import_collection_payout_statement(
                self.root,
                dict(payload or {}),
                actor="desktop-owner",
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def reconcile_collection_payout(
        self,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        try:
            return self._platform_finance_module().reconcile_collection_payout(
                self.root,
                dict(payload or {}),
                actor="desktop-owner",
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def run_fictional_finance_demo(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        try:
            return self._platform_finance_module().run_fictional_finance_demo(
                self.root,
                dict(payload or {}),
                actor="desktop-owner",
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def create_operating_expense_draft(
        self,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        try:
            return self._operating_expense_module().create_operating_expense_draft(
                self.root,
                dict(payload or {}),
                actor="desktop-owner",
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def confirm_operating_expense(
        self,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        try:
            return self._operating_expense_module().confirm_operating_expense(
                self.root,
                dict(payload or {}),
                actor="desktop-owner",
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def operating_expense_snapshot(
        self,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        data = dict(payload or {})
        try:
            return self._operating_expense_module().operating_expense_snapshot(
                self.root,
                project_id=str(data.get("project_id") or ""),
                task_id=str(data.get("task_id") or ""),
                status=str(data.get("status") or ""),
                start_date=str(data.get("start_date") or ""),
                end_date=str(data.get("end_date") or ""),
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def export_operating_expenses(
        self,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        try:
            return self._operating_expense_module().export_operating_expenses(
                self.root,
                dict(payload or {}),
                actor="desktop-owner",
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def install_capability_pack(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        data = dict(payload or {})
        try:
            session = self._desktop_owner_session()
            task_id = str(data.get("task_id") or "")
            runtime = self._workspace_runtime_module()
            if not runtime.session_can_manage_task(self.root, task_id, session):
                raise ValueError("当前账号不能修改这个任务的能力。")
            actor = str(session.get("display_name") or session.get("login_id") or "desktop-owner")
            return runtime.install_capability_pack(self.root, data, actor=actor)
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def save_subaccount(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        data = dict(payload or {})
        try:
            state = self._account_module().save_subaccount(
                self.root,
                login_id=str(data.get("login_id") or ""),
                display_name=str(data.get("display_name") or ""),
                pin=str(data.get("pin") or ""),
                group_id=str(data.get("group_id") or "operator"),
                platform_scope=str(data.get("platform_scope") or ""),
                store_scope=str(data.get("store_scope") or ""),
                country_scope=str(data.get("country_scope") or ""),
                project_scope=str(data.get("project_scope") or ""),
                task_scope=str(data.get("task_scope") or ""),
                note=str(data.get("note") or ""),
                actor_session=self._desktop_owner_session(),
            )
            return {"ok": True, "team": state}
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def set_subaccount_active(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        data = dict(payload or {})
        try:
            state = self._account_module().set_subaccount_active(
                self.root,
                str(data.get("login_id") or ""),
                bool(data.get("active")),
                actor_session=self._desktop_owner_session(),
            )
            return {"ok": True, "team": state}
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def save_product_intake(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        try:
            result = self._product_intake_module().save_product_data_intake(
                self.root, dict(payload or {})
            )
            return {
                **result,
                "message": (
                    f"已导入 {int(result.get('saved_file_count') or 0)} 个文件，"
                    f"识别 {int(result.get('row_count') or 0)} 行；"
                    f"仍缺 {int(result.get('owner_missing_count') or 0)} 项。"
                ),
            }
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def process_learning_text(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        data = dict(payload or {})
        try:
            result = self._learning_distillation_module().process_text_learning_intake(
                self.root,
                project_id=str(data.get("project_id") or ""),
                task_id=str(data.get("task_id") or ""),
                source_text=str(data.get("source_text") or ""),
                model_provider=str(data.get("model_provider") or ""),
                source_id=str(data.get("source_id") or ""),
                title=str(data.get("title") or "负责人提供的学习资料"),
                source_url=str(data.get("source_url") or ""),
                rights_basis=str(
                    data.get("rights_basis") or "user_provided_with_permission"
                ),
            )
            return result
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc), "external_actions": []}

    def approve_learning_candidate(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        data = dict(payload or {})
        try:
            refs = data.get("source_verification_refs")
            result = self._learning_distillation_module().approve_distillation_candidate(
                self.root,
                candidate_record_id=str(data.get("candidate_record_id") or ""),
                project_id=str(data.get("project_id") or ""),
                task_id=str(data.get("task_id") or ""),
                reviewer="desktop-owner",
                source_verification_refs=(
                    [str(item) for item in refs] if isinstance(refs, list) else []
                ),
            )
            return {
                "ok": True,
                **result.to_dict(),
                "message": (
                    "已加入当前智能体的学习记忆；它仍是经核对的经验，不是平台官方规则，"
                    "也没有获得任何外部执行权限。"
                ),
            }
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc), "external_actions": []}

    def learning_memory_snapshot(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        data = dict(payload or {})
        try:
            result = self._learning_distillation_module().resolve_approved_expert_learning_memory(
                self.root,
                project_id=str(data.get("project_id") or ""),
                task_id=str(data.get("task_id") or ""),
            )
            return {"ok": True, **result}
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc), "external_actions": []}

    def task_history_context_snapshot(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        """Return retained history for one exact task without rebuilding old chats."""

        data = dict(payload or {})
        task_id = str(data.get("task_id") or "").strip().lower()
        project_id = str(data.get("project_id") or "").strip()
        if not task_id:
            return {"ok": False, "error": "请先选择一个具体任务。", "external_actions": []}
        try:
            limit = max(1, min(int(data.get("limit") or 20), 50))
            runtime = self._task_execution_module()
            retained = runtime.recent_task_runs(self.root, task_id, limit=limit)
            history = []
            for item in retained:
                history.append(
                    {
                        "run_id": str(item.get("id") or ""),
                        "instruction": str(
                            item.get("instruction") or item.get("message") or ""
                        )[:4000],
                        "result_message": str(item.get("result_message") or "")[:8000],
                        "status": str(item.get("status") or "unknown"),
                        "platform": str(item.get("platform") or ""),
                        "created_at": str(item.get("created_at") or ""),
                        "updated_at": str(item.get("updated_at") or ""),
                    }
                )
            memory = {
                "memory_count": 0,
                "items": [],
                "cross_task_memory_loaded": False,
                "external_action_authorized": False,
            }
            if project_id:
                try:
                    memory = self._learning_distillation_module().resolve_approved_expert_learning_memory(
                        self.root,
                        project_id=project_id,
                        task_id=task_id,
                        limit=12,
                    )
                except (OSError, RuntimeError, TypeError, ValueError):
                    memory = {
                        "memory_count": 0,
                        "items": [],
                        "cross_task_memory_loaded": False,
                        "external_action_authorized": False,
                    }
            return {
                "ok": True,
                "task_id": task_id,
                "project_id": project_id,
                "history_count": len(history),
                "history": history,
                "memory_count": int(memory.get("memory_count") or 0),
                "memory": list(memory.get("items") or []),
                "cross_task_memory_loaded": False,
                "deleted_conversations_rebuilt": False,
                "external_actions": [],
            }
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc), "external_actions": []}

    def save_company_profile(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        try:
            snapshot = self._company_module().save_company_verified_values(
                self.root, dict(payload or {})
            )
            return {
                "ok": True,
                "snapshot": snapshot,
                "message": (
                    f"已保存 {int(snapshot.get('owner_provided_count') or 0)}/"
                    f"{int(snapshot.get('owner_required_count') or 0)} 项负责人事实。"
                ),
            }
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def _focus_process(process_id: int) -> None:
        if not process_id:
            return
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            handles: list[int] = []
            callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            @callback_type
            def enum_window(hwnd: int, _lparam: int) -> bool:
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value == process_id and user32.IsWindowVisible(hwnd):
                    handles.append(hwnd)
                return True

            user32.EnumWindows(enum_window, 0)
            if handles:
                user32.ShowWindow(handles[0], 9)
                user32.SetForegroundWindow(handles[0])
        except Exception:
            return

    @staticmethod
    def _sanitized_shein_order_summary(value: object) -> dict[str, object]:
        raw = value if isinstance(value, dict) else {}

        def count_from_value(value: object) -> int:
            try:
                return max(0, min(int(value or 0), 1_000_000_000))
            except (TypeError, ValueError):
                return 0

        def count(key: str) -> int:
            return count_from_value(raw.get(key))

        def amount_from_value(value: object) -> str:
            text = str(value or "0").strip().replace(",", "")[:40]
            if not text or any(char not in "0123456789.-" for char in text):
                return "0"
            try:
                float(text)
            except ValueError:
                return "0"
            return text

        def amount(key: str) -> str:
            return amount_from_value(raw.get(key))

        def date_value(key: str) -> str:
            text = str(raw.get(key) or "").strip()[:24]
            return text if all(char in "0123456789/:- TZ" for char in text) else ""

        product_links: list[dict[str, object]] = []
        raw_links = raw.get("product_links") if isinstance(raw.get("product_links"), list) else []
        for item in raw_links[:50]:
            if not isinstance(item, dict):
                continue
            parsed = urlsplit(str(item.get("url") or "").strip())
            hostname = (parsed.hostname or "").lower()
            if (
                parsed.scheme != "https"
                or not hostname.endswith("shein.com")
                or hostname.startswith("sellerhub.")
                or not parsed.path
            ):
                continue
            product_links.append(
                {
                    "url": f"https://{hostname}{parsed.path}",
                    "title": str(item.get("title") or "商品链接").strip()[:120],
                    "order_count": count_from_value(item.get("order_count")),
                    "gross_sales": amount_from_value(item.get("gross_sales")),
                }
            )

        return {
            "data_returned": raw.get("data_returned") is True,
            "order_count": count("order_count"),
            "unit_count": count("unit_count"),
            "gross_sales": amount("gross_sales"),
            "expected_income": amount("expected_income"),
            "window_start": date_value("window_start"),
            "window_end": date_value("window_end"),
            "product_links": product_links,
            "source": "seller_hub_visible_aggregate",
            "contains_order_ids_or_customer_pii": False,
        }

    def _persist_shein_order_summary(
        self,
        task_context: dict[str, object],
        summary: dict[str, object],
    ) -> str:
        task_id = str(task_context.get("task_id") or task_context.get("id") or "").strip()
        if not task_id:
            return ""
        folder_context = dict(task_context)
        folder_context["id"] = task_id
        folder, relative_folder = self._workspace_runtime_module().ensure_task_local_folder(
            self.root, folder_context
        )
        result = {
            "schema_version": 1,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "project_id": str(task_context.get("project_id") or ""),
            "task_id": task_id,
            "platform": "shein",
            "country_site": str(
                task_context.get("country_site") or task_context.get("country") or ""
            ),
            "store_binding_id": str(task_context.get("store_binding_id") or ""),
            "store_id": str(task_context.get("store_id") or ""),
            "order_summary": summary,
            "read_only": True,
            "external_store_write_actions": 0,
        }
        destination = folder / "results" / "shein-order-summary-latest.json"
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(destination)
        history = folder / "results" / "shein-order-summary-history.jsonl"
        with history.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
        return f"{relative_folder}/results/{destination.name}"

    def open_store_surface(
        self,
        surface: str = "home",
        task_context: dict[str, object] | None = None,
    ) -> dict[str, object]:
        task_context = task_context if isinstance(task_context, dict) else {}
        surface = str(surface or "home").strip().lower()
        if surface not in self.STORE_SURFACES:
            return {"ok": False, "error": "未授权的店铺页面。"}
        platform = str(task_context.get("platform") or "").strip().lower()
        if platform not in {"amazon", "shein"}:
            return {
                "ok": False,
                "code": "needs_store_connection",
                "error": "当前任务还没有对应平台的真实店铺连接，未打开其他店铺。",
            }
        store_id = str(task_context.get("store_id") or "").strip()
        if task_context and not store_id:
            return {
                "ok": False,
                "code": "needs_store_connection",
                "error": "当前任务缺少真实店铺编号，请先在配置中绑定店铺。",
            }
        try:
            profile_seq = int(
                task_context.get("browser_profile_seq")
                or task_context.get("browser_profile_sequence")
                or 0
            )
        except (TypeError, ValueError):
            return {"ok": False, "code": "needs_store_connection", "error": "浏览器环境编号无效。"}
        if profile_seq <= 0:
            return {
                "ok": False,
                "code": "needs_store_connection",
                "error": "当前店铺没有绑定浏览器环境，请先在配置中完成绑定。",
            }
        script_ref = str(task_context.get("store_surface_connector_script") or "").strip()
        script_path = Path(script_ref)
        if not script_ref or script_path.is_absolute() or ".." in script_path.parts:
            return {
                "ok": False,
                "code": "needs_store_connection",
                "error": "当前店铺没有配置安全的本地页面连接器。",
            }
        script = (self.root / script_path).resolve()
        try:
            script.relative_to(self.root.resolve())
        except ValueError:
            return {
                "ok": False,
                "code": "needs_store_connection",
                "error": "店铺页面连接器不在当前工作区内。",
            }
        if not script.exists():
            return {"ok": False, "code": "needs_store_connection", "error": "店铺连接器不存在。"}
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Surface", surface, "-ProfileSeq", str(profile_seq)],
                cwd=str(self.root), capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=45, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False,
            )
            if result.returncode != 0:
                raw_detail = (result.stderr or result.stdout or "未知错误").strip()
                detail_lines = [line.strip() for line in raw_detail.splitlines() if line.strip()]
                detail = next(
                    (
                        line
                        for line in detail_lines
                        if not line.startswith(("At ", "+", "CategoryInfo", "FullyQualifiedErrorId"))
                    ),
                    detail_lines[0] if detail_lines else "未知错误",
                )
                return {"ok": False, "error": detail}
            last_line = next((line for line in reversed(result.stdout.splitlines()) if line.strip().startswith("{")), "{}")
            payload = json.loads(last_line)
            if task_context.get("background_refresh") is not True:
                self._focus_process(int(payload.get("process_id") or 0))
            observed_url = str(payload.get("observed_url") or "")
            external_store_write_actions = int(
                payload.get("external_store_write_actions") or 0
            )
            order_summary = (
                self._sanitized_shein_order_summary(payload.get("order_summary"))
                if platform == "shein" and surface == "orders"
                else {}
            )
            if bool(payload.get("auth_required")):
                return {
                    "ok": False,
                    "code": "needs_store_login",
                    "surface": surface,
                    "store_id": store_id,
                    "browser_profile_seq": profile_seq,
                    "observed_url": observed_url,
                    "page_state": str(payload.get("page_state") or "needs_login"),
                    "auth_required": True,
                    "error": (
                        f"已打开 BitBrowser {profile_seq} 的 {platform.upper()} 环境，但当前停在登录页。"
                        "请负责人完成密码或 MFA 后重试；系统不会代填或绕过账号安全步骤。"
                    ),
                }
            shein_receipt_matches = (
                platform != "shein"
                or (
                    str(payload.get("platform") or "").lower() == "shein"
                    and int(payload.get("profile_seq") or 0) == profile_seq
                    and str(payload.get("surface") or "").lower() == surface
                    and observed_url.startswith("https://sellerhub.shein.com")
                    and payload.get("surface_verified") is True
                    and external_store_write_actions == 0
                    and (
                        surface != "orders"
                        or order_summary.get("data_returned") is True
                    )
                )
            )
            if (
                not bool(payload.get("ok"))
                or str(payload.get("page_state") or "") != "opened"
                or not shein_receipt_matches
            ):
                return {
                    "ok": False,
                    "code": "unverified_store_surface",
                    "surface": surface,
                    "store_id": store_id,
                    "browser_profile_seq": profile_seq,
                    "observed_url": observed_url,
                    "page_title": str(payload.get("page_title") or ""),
                    "page_state": str(payload.get("page_state") or "unverified"),
                    "auth_required": bool(payload.get("auth_required")),
                    "error": (
                        f"BitBrowser {profile_seq} 已执行只读页面检查，但 CDP 未确认当前标签页是可用的 {platform.upper()} 页面。"
                        "不会把未验证页面记为成功；请检查店铺标签页后重试。"
                    ),
                }
            surface_labels = {
                "home": "首页",
                "inventory": "库存",
                "orders": "订单",
                "ads": "广告",
                "coupons": "优惠券",
            }
            response = {
                "ok": True,
                "code": "opened",
                "surface": surface,
                "store_id": store_id,
                "browser_profile_seq": profile_seq,
                "observed_url": observed_url,
                "page_title": str(payload.get("page_title") or ""),
                "page_state": str(payload.get("page_state") or "opened"),
                "surface_verified": bool(payload.get("surface_verified")),
                "auth_required": False,
                "reused_existing_session": bool(
                    payload.get("reused_existing_session")
                ),
                "external_store_write_actions": external_store_write_actions,
                "message": (
                    f"已通过 BitBrowser {profile_seq} 打开并验证 {platform.upper()} {surface_labels[surface]}页面；"
                    "连接器已确认当前未停在登录页。"
                ),
            }
            if surface == "orders" and platform == "shein":
                response["order_summary"] = order_summary
                try:
                    response["order_summary_path"] = self._persist_shein_order_summary(
                        task_context, order_summary
                    )
                except (OSError, TypeError, ValueError) as exc:
                    response["order_summary_path"] = ""
                    response["local_persist_error"] = str(exc)
            return response
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "error": str(exc)}

    def open_store_surfaces_parallel(
        self,
        surface: str = "orders",
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Open every verified SHEIN store in one project without mixing identities."""

        data = dict(payload or {})
        surface = str(surface or "orders").strip().lower()
        if surface not in {"home", "inventory", "orders"}:
            return {"ok": False, "code": "unsupported_surface", "error": "批量模式只允许只读首页、商品页或订单页。"}
        project_id = str(data.get("project_id") or "").strip().lower()
        if not project_id:
            return {"ok": False, "code": "needs_project", "error": "请先选择一个已绑定店铺的项目。"}

        workspace = self._workspace_runtime_module().load_workspace_config(self.root)
        project = next(
            (
                item
                for item in workspace.get("projects", [])
                if isinstance(item, dict)
                and str(item.get("id") or "").strip().lower() == project_id
            ),
            None,
        )
        if project is None:
            return {"ok": False, "code": "needs_project", "error": "当前项目不存在或已被移除。"}

        tasks_by_store = {
            str(task.get("store_binding_id") or "").strip().lower(): task
            for task in project.get("tasks", [])
            if isinstance(task, dict)
            and str(task.get("platform") or "").strip().lower() == "shein"
            and str(task.get("store_binding_id") or "").strip()
        }
        targets: list[dict[str, object]] = []
        seen_profiles: set[int] = set()
        seen_store_ids: set[str] = set()
        seen_execution_identities: set[str] = set()
        for channel in project.get("channels", []):
            if not isinstance(channel, dict) or str(channel.get("platform") or "").strip().lower() != "shein":
                continue
            for store in channel.get("stores", []):
                if not isinstance(store, dict) or str(store.get("status") or "") != "connected_read_only":
                    continue
                binding_id = str(store.get("id") or "").strip().lower()
                task = tasks_by_store.get(binding_id)
                # Legacy base+runtime collisions can surface a previously verified
                # binding as profile_selected.  It may enter the live probe, but
                # only the connector's fresh CDP proof below can make it succeed.
                if task is None or str(store.get("browser_binding_status") or "") not in {
                    "verified_read_only",
                    "profile_selected",
                }:
                    continue
                store_id = str(store.get("external_id") or task.get("store_id") or "").strip()
                try:
                    profile_seq = int(
                        store.get("browser_profile_seq")
                        or store.get("browser_profile_sequence")
                        or task.get("browser_profile_seq")
                        or task.get("browser_profile_sequence")
                        or 0
                    )
                except (TypeError, ValueError):
                    continue
                execution_identity = str(
                    store.get("execution_identity_id")
                    or task.get("execution_identity_id")
                    or store.get("browser_profile_id")
                    or task.get("browser_profile_id")
                    or ""
                ).strip()
                if (
                    not store_id
                    or profile_seq <= 0
                    or not execution_identity
                    or store_id in seen_store_ids
                    or profile_seq in seen_profiles
                    or execution_identity in seen_execution_identities
                ):
                    continue
                task_context = dict(task)
                task_context.update(
                    {
                        "platform": "shein",
                        "project_id": project_id,
                        "store_binding_id": binding_id,
                        "store_id": store_id,
                        "browser_profile_seq": profile_seq,
                        "browser_profile_sequence": profile_seq,
                        "execution_identity_id": execution_identity,
                        "store_surface_connector_script": str(
                            store.get("store_surface_connector_script")
                            or task.get("store_surface_connector_script")
                            or ""
                        ),
                        "background_refresh": True,
                    }
                )
                targets.append(task_context)
                seen_store_ids.add(store_id)
                seen_profiles.add(profile_seq)
                seen_execution_identities.add(execution_identity)

        if not targets:
            return {
                "ok": False,
                "code": "needs_store_connection",
                "error": "当前项目没有可并行处理的已验证 SHEIN 指纹环境。",
                "amazon_touched": False,
            }
        if len(targets) > 8:
            return {
                "ok": False,
                "code": "parallel_limit_exceeded",
                "error": "一次最多并行处理 8 个已验证指纹环境，请分批执行。",
                "target_count": len(targets),
                "amazon_touched": False,
            }

        try:
            requested_parallel = int(data.get("max_parallel") or len(targets))
        except (TypeError, ValueError):
            requested_parallel = len(targets)
        max_parallel = max(1, min(8, len(targets), requested_parallel))
        started_at = datetime.now(timezone.utc)
        indexed_results: dict[int, dict[str, object]] = {}
        with ThreadPoolExecutor(
            max_workers=max_parallel,
            thread_name_prefix="t-one-bitbrowser",
        ) as executor:
            future_to_index = {
                executor.submit(self.open_store_surface, surface, target): index
                for index, target in enumerate(targets)
            }
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    result = future.result()
                except Exception as exc:  # Keep one failed window from hiding all other receipts.
                    result = {"ok": False, "code": "parallel_worker_failed", "error": str(exc)}
                indexed_results[index] = {
                    "task_id": str(targets[index].get("id") or targets[index].get("task_id") or ""),
                    "store_binding_id": str(targets[index].get("store_binding_id") or ""),
                    "store_id": str(targets[index].get("store_id") or ""),
                    "browser_profile_seq": int(targets[index].get("browser_profile_seq") or 0),
                    "execution_identity_id": str(targets[index].get("execution_identity_id") or ""),
                    "result": result,
                }
        store_results = [indexed_results[index] for index in range(len(targets))]
        success_count = sum(1 for item in store_results if item["result"].get("ok") is True)
        external_writes = sum(
            int(item["result"].get("external_store_write_actions") or 0)
            for item in store_results
        )
        finished_at = datetime.now(timezone.utc)
        receipt = {
            "schema_version": 1,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "elapsed_ms": max(0, int((finished_at - started_at).total_seconds() * 1000)),
            "project_id": project_id,
            "platform": "shein",
            "surface": surface,
            "parallel_execution": True,
            "max_parallel": max_parallel,
            "target_count": len(targets),
            "success_count": success_count,
            "failed_count": len(targets) - success_count,
            "stores": store_results,
            "external_store_write_actions": external_writes,
            "amazon_touched": False,
        }
        receipt_path = self.root / "outputs" / "qa" / f"bitbrowser_parallel_shein_{surface}_latest.json"
        try:
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = receipt_path.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(receipt_path)
            relative_receipt = receipt_path.relative_to(self.root).as_posix()
        except (OSError, ValueError):
            relative_receipt = ""
        all_ok = success_count == len(targets) and external_writes == 0
        return {
            "ok": all_ok,
            "code": "opened_all" if all_ok else "partial_failure",
            "message": (
                f"已并行打开并验证 {success_count}/{len(targets)} 个 SHEIN 指纹环境；店铺写入 {external_writes}。"
            ),
            **receipt,
            "receipt_path": relative_receipt,
        }

    def start_task_instruction(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        data = dict(payload or {})
        try:
            runtime = self._task_execution_module()
            data["_runtime_instance_id"] = self.instance_id
            run = runtime.create_task_run(self.root, data, actor="desktop-owner")
            if run.get("mode") != "tool":
                return {"ok": True, "run": run, "message": str(run.get("label") or "指令已记录。")}
            scheduled = self._spawn_task_worker(str(run.get("id") or ""), data)
            return {
                "ok": True,
                "run": run,
                "scheduled_in_memory": scheduled,
                "message": (
                    str(run.get("label") or "已加入本机执行队列。")
                    if scheduled
                    else "任务已持久化排队；共享 worker 当前已满，将由恢复循环继续领取。"
                ),
            }
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def _execute_task_run(
        self,
        run_id: str,
        payload: dict[str, object],
        recovered: bool = False,
    ) -> None:
        runtime = self._task_execution_module()
        heartbeat_stop = threading.Event()
        heartbeat: threading.Thread | None = None
        fencing_token = 0
        try:
            run = runtime.claim_task_run(
                self.root,
                run_id,
                self.instance_id,
                recovered=recovered,
            )
            if run is None:
                return
            fencing_token = int(run.get("fencing_token") or 0)

            def keep_lease_alive() -> None:
                while not heartbeat_stop.wait(10):
                    try:
                        if not runtime.renew_task_run_lease(
                            self.root,
                            run_id,
                            self.instance_id,
                            fencing_token=fencing_token,
                        ):
                            return
                    except (OSError, TypeError, ValueError):
                        return

            heartbeat = threading.Thread(
                target=keep_lease_alive,
                name=f"teelab-heartbeat-{run_id[-8:]}",
                daemon=True,
            )
            heartbeat.start()
            stored_payload = run.get("execution_payload")
            execution_payload = dict(stored_payload) if isinstance(stored_payload, dict) else {}
            # Persisted store identity is authoritative during recovery. A retry
            # must never move an execution onto another platform/profile.
            route_fields = {
                "tenant_id", "project_id", "store_binding_id", "platform",
                "country_code", "country_site", "store_model", "ownership",
                "route_key", "store_id", "browser_profile_seq",
            }
            execution_payload.update({
                key: value for key, value in payload.items() if key not in route_fields
            })
            action = str(run.get("action") or "")
            if action == "open_store_surface":
                result = self.open_store_surface(str(run.get("surface") or "home"), execution_payload)
            elif action == "create_b2b_sales_execution_pack":
                result = self.create_b2b_sales_execution_pack(execution_payload)
            elif action == "open_b2b_customer_pool":
                result = self.open_b2b_customer_pool()
            elif action == "open_b2b_output":
                result = self.open_b2b_output()
            elif action == "create_video_prompt_pack":
                result = self.create_video_prompt_pack(execution_payload)
            elif action == "open_video_editor":
                result = self.open_video_editor()
            elif action == "open_creative_output":
                result = self.open_creative_output()
            elif action == "analyze_video_path":
                result = self.analyze_video_file(
                    str(execution_payload.get("input_path") or ""),
                    {**execution_payload, "run_id": run_id},
                )
            else:
                result = {"ok": False, "error": "当前任务动作没有对应的本机执行器。"}
            evidence_paths = [
                str(result.get(key) or "")
                for key in ("path", "output_dir", "report_path", "semantic_path")
                if str(result.get(key) or "").strip()
            ]
            connector_evidence = {}
            if action == "open_store_surface":
                connector_evidence = {
                    key: result.get(key)
                    for key in (
                        "code",
                        "surface",
                        "observed_url",
                        "page_state",
                        "auth_required",
                        "browser_profile_seq",
                    )
                    if result.get(key) not in (None, "")
                }
            if result.get("ok"):
                runtime.update_task_run(
                    self.root,
                    run_id,
                    {
                        "status": "completed",
                        "result_message": str(result.get("message") or "本机动作已完成。"),
                        "evidence_paths": evidence_paths,
                        "connector_evidence": connector_evidence,
                        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                        "lease_owner": "",
                        "lease_expires_at": "",
                    },
                    worker_id=self.instance_id,
                    fencing_token=fencing_token,
                )
            else:
                status_by_code = {
                    "needs_store_connection": "needs_configuration",
                    "needs_store_login": "needs_input",
                    "unverified_store_surface": "needs_input",
                }
                status = status_by_code.get(str(result.get("code") or ""), "failed")
                runtime.update_task_run(
                    self.root,
                    run_id,
                    {
                        "status": status,
                        "error": str(result.get("error") or "本机动作执行失败。"),
                        "connector_evidence": connector_evidence,
                        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                        "lease_owner": "",
                        "lease_expires_at": "",
                    },
                    worker_id=self.instance_id,
                    fencing_token=fencing_token,
                )
        except (OSError, RuntimeError, TypeError, ValueError, subprocess.SubprocessError) as exc:
            try:
                runtime.update_task_run(
                    self.root,
                    run_id,
                    {
                        "status": "failed",
                        "error": str(exc),
                        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                        "lease_owner": "",
                        "lease_expires_at": "",
                    },
                    worker_id=self.instance_id,
                    fencing_token=fencing_token,
                )
            except (OSError, ValueError):
                return
        finally:
            heartbeat_stop.set()
            if heartbeat and heartbeat.is_alive():
                heartbeat.join(timeout=1)

    def get_task_instruction_status(self, run_id: str) -> dict[str, object]:
        try:
            runtime = self._task_execution_module()
            runtime.mark_stale_analysis_runs(self.root)
            run = runtime.task_run(self.root, run_id)
            if run is None:
                return {"ok": False, "error": "执行记录不存在。"}
            return {
                "ok": True,
                "run": run,
                "events": runtime.task_run_events(self.root, run_id, limit=20),
            }
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def complete_task_instruction(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        data = dict(payload or {})
        status = str(data.get("status") or "analysis_complete").strip().lower()
        if status not in {"analysis_complete", "failed", "needs_retry", "cancelled"}:
            status = "analysis_complete"
        try:
            run = self._task_execution_module().update_task_run(
                self.root,
                str(data.get("run_id") or ""),
                {
                    "status": status,
                    "result_message": str(data.get("result_message") or ""),
                    "error": str(data.get("error") or ""),
                    "model_provider": str(data.get("model_provider") or ""),
                    "model": str(data.get("model") or ""),
                    "latency_ms": data.get("latency_ms") or 0,
                    "fact_validated": bool(data.get("fact_validated")),
                    "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "lease_owner": "",
                    "lease_expires_at": "",
                },
            )
            return {"ok": True, "run": run}
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def choose_video_file(self) -> dict[str, object]:
        if self.window is None:
            return {"ok": False, "error": "桌面窗口尚未准备好。"}
        try:
            dialog_enum = getattr(webview, "FileDialog", None)
            dialog_type = dialog_enum.OPEN if dialog_enum is not None else webview.OPEN_DIALOG
            selected = self.window.create_file_dialog(
                dialog_type,
                allow_multiple=False,
                file_types=("视频文件 (*.mp4;*.mov;*.mkv;*.webm;*.avi;*.m4v)",),
            )
            if not selected:
                return {"ok": False, "error": "没有选择视频。"}
            path = selected[0] if isinstance(selected, (tuple, list)) else selected
            return {"ok": True, "path": str(path)}
        except (OSError, RuntimeError) as exc:
            return {"ok": False, "error": str(exc)}

    def analyze_video_file(
        self,
        path: str,
        task_context: dict[str, object] | None = None,
    ) -> dict[str, object]:
        candidate = Path(str(path or "")).expanduser()
        if not candidate.exists() or not candidate.is_file():
            return {"ok": False, "error": "没有找到所选视频文件。"}
        if candidate.suffix.lower() not in {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}:
            return {"ok": False, "error": "当前文件不是支持的视频格式。"}
        try:
            result = self._creative_module().analyze_video(
                self.root,
                str(candidate.resolve()),
                task_context if isinstance(task_context, dict) else {},
            )
            if not result.get("ok"):
                return result
            self.latest_creative_output = Path(str(result.get("output_dir") or ""))
            metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
            semantics = result.get("visual_semantics") if isinstance(result.get("visual_semantics"), dict) else {}
            semantic_message = (
                f"视觉模型提取了 {len(semantics.get('observations') or [])} 条可见观察，"
                f"推断 {len(semantics.get('inferences') or [])} 条，已分开保存。"
                if semantics.get("status") == "model_observations_extracted"
                else f"画面语义状态：{semantics.get('status') or '待人工复核'}。"
            )
            return {
                **result,
                "message": (
                    f"视频分析完成：{metadata.get('duration_seconds', 0)} 秒，"
                    f"{metadata.get('width', 0)}×{metadata.get('height', 0)}，"
                    f"检测到 {len(result.get('scene_cut_seconds') or [])} 个明显切点，"
                    f"已生成 {len(result.get('frame_files') or [])} 张关键帧和创意裂变提示词。"
                    f"{semantic_message} 本次没有调用原生视频模型，也没有执行上传或发布。"
                ),
            }
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            return {"ok": False, "error": str(exc)}

    def choose_and_analyze_video(self) -> dict[str, object]:
        selected = self.choose_video_file()
        if not selected.get("ok"):
            return selected
        return self.analyze_video_file(str(selected.get("path") or ""))

    def create_video_prompt_pack(self, task_context: dict[str, object] | None = None) -> dict[str, object]:
        task_context = task_context if isinstance(task_context, dict) else {}
        platform = str(task_context.get("platform") or "TikTok Shop")
        country = str(task_context.get("country") or "US")
        product_id = str(task_context.get("product_id") or "")
        product = str(task_context.get("product_name") or product_id or "当前商品").strip()
        template_id = str(task_context.get("template_id") or task_context.get("default_template_id") or "ugc-pain-solution-15")
        if platform == "creative_video":
            platform = "Amazon / TikTok Shop / B2B"
        try:
            generation_route = self._creative_module().resolve_generation_route(
                self.root, str(task_context.get("generation_route_id") or "")
            )
            content = self._creative_module().build_prompt_pack(
                self.root,
                template_id=template_id,
                product=product,
                platform=platform,
                country=country,
                task_context=task_context,
            )
            stamp = time.strftime("%Y%m%d-%H%M%S")
            output_dir = self.root / "outputs" / "creative_video" / "prompt_packs"
            output_dir.mkdir(parents=True, exist_ok=True)
            target = output_dir / f"ai_video_prompt_pack_{stamp}.md"
            target.write_text(content, encoding="utf-8")
            experiment = self._content_feedback_module().build_content_experiment(
                experiment_id=f"content-exp-{stamp}",
                template_id=template_id,
                platform=platform,
                country_site=country,
                primary_metric=str(task_context.get("primary_metric") or "views"),
                account_baseline_ref=str(task_context.get("account_baseline_ref") or ""),
            )
            experiment_path = output_dir / f"content_experiment_{stamp}.json"
            experiment_path.write_text(
                json.dumps(experiment, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self.latest_creative_output = output_dir
            return {
                "ok": True,
                "path": str(target),
                "report_path": str(experiment_path),
                "experiment_id": experiment["experiment_id"],
                "prediction_sha256": experiment["prediction_sha256"],
                "generation_route": generation_route,
                "external_generation_performed": False,
                "message": (
                    f"AI 视频提示词、分镜和发布前盲预测已生成：{target.name}；"
                    "需要真实发布回执和同窗口数据后才能校准。"
                ),
            }
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def record_creative_feedback(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        data = dict(payload or {})
        try:
            runtime = self._task_execution_module()
            run_id = str(data.get("run_id") or "").strip()
            if not run_id:
                task_id = str(data.get("task_id") or "").strip().lower()
                recent = runtime.recent_task_runs(self.root, task_id, limit=20)
                match = next(
                    (
                        item for item in recent
                        if str(item.get("platform") or "") == "creative_video"
                        and str(item.get("status") or "") in {"completed", "analysis_complete"}
                    ),
                    None,
                )
                if match is None:
                    raise ValueError("当前任务还没有可回写的已完成视觉运行记录。")
                run_id = str(match.get("id") or "")
            data["run_id"] = run_id
            recorded = runtime.record_creative_feedback(
                self.root, data, actor="desktop-owner"
            )
            return {
                "ok": True,
                "run_id": run_id,
                "feedback": recorded.get("feedback") or {},
                "message": "素材效果已回写到原视觉任务；未执行发布、投流或外部生成。",
            }
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def configure_ai_provider(self, payload: dict[str, object] | None = None) -> dict[str, object]:
        try:
            result = self._provider_module().configure_provider(self.root, dict(payload or {}))
            provider = result.get("provider") if isinstance(result.get("provider"), dict) else {}
            name = str(provider.get("name") or "AI")
            model = str(provider.get("model") or "")
            return {
                "ok": True,
                **result,
                "message": f"已保存 {name} / {model}；API Key 已由 Windows 加密并仅保存在本机。",
            }
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def test_ai_provider(self, provider_name: str) -> dict[str, object]:
        try:
            result = self._provider_module().test_provider(self.root, provider_name)
            if result.get("status") == "ok":
                return {"ok": True, **result, "message": f"{provider_name} 连接正常，耗时 {int(result.get('latency_ms') or 0)} ms。"}
            return {"ok": False, **result, "message": str(result.get("error") or "模型连接未通过。")}
        except (OSError, RuntimeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def non_api_ai_bridge_snapshot(self) -> dict[str, object]:
        try:
            return self._non_api_ai_bridge_module().non_api_ai_bridge_snapshot(self.root)
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def cli_ai_connector_snapshot(self) -> dict[str, object]:
        try:
            return self._cli_ai_connector_module().cli_ai_connector_snapshot(
                self.root, live_probe=True
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def run_cli_ai_roundtrip(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        try:
            return self._cli_ai_connector_module().run_cli_ai_roundtrip(
                self.root, dict(payload or {})
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def browser_ai_connector_snapshot(self) -> dict[str, object]:
        try:
            return self._browser_ai_connector_module().browser_ai_connector_snapshot(
                self.root
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def run_browser_ai_roundtrip(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        try:
            return self._browser_ai_connector_module().run_browser_ai_roundtrip(
                self.root, dict(payload or {})
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def multi_ai_collaboration_snapshot(self) -> dict[str, object]:
        try:
            return self._multi_ai_collaboration_module().multi_ai_collaboration_snapshot(
                self.root, live_probe=True
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def run_multi_ai_collaboration(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        try:
            return self._multi_ai_collaboration_module().run_multi_ai_collaboration(
                self.root, dict(payload or {})
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def project_capability_profile_snapshot(self) -> dict[str, object]:
        try:
            return self._project_capability_profiles_module().project_capability_profile_snapshot(
                self.root
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def save_project_capability_profile(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        try:
            return self._project_capability_profiles_module().save_project_capability_profile(
                self.root, dict(payload or {}), actor="desktop-owner"
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def prepare_task_skill_packages(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        try:
            return self._project_capability_profiles_module().prepare_task_skill_packages(
                self.root, dict(payload or {})
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def build_non_api_ai_handoff(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        try:
            return self._non_api_ai_bridge_module().build_non_api_ai_handoff(
                self.root, dict(payload or {})
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def smart_capability_context_preview(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        """Preview the same bounded Agent/Skill selection used by task runs."""

        data = dict(payload or {})
        task_id = str(data.get("task_id") or "").strip().lower()
        instruction = str(data.get("message") or data.get("instruction") or "").strip()
        if not task_id or not instruction:
            return {"ok": False, "error": "请选择任务并输入本轮指令。", "external_actions": []}
        try:
            runtime = self._task_execution_module()
            from ai_ecommerce_director.capability_context_manager import (
                resolve_task_capability_context,
            )

            task = runtime._task(self.root, task_id)
            result = resolve_task_capability_context(self.root, task, instruction)
            return {"ok": True, **result, "external_actions": []}
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc), "external_actions": []}

    def record_non_api_ai_result(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        try:
            return self._non_api_ai_bridge_module().record_non_api_ai_result(
                self.root, dict(payload or {})
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def evaluate_non_api_ai_delivery(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        try:
            return self._non_api_ai_bridge_module().evaluate_non_api_ai_delivery(
                self.root, dict(payload or {})
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def review_non_api_ai_result(
        self, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        try:
            return self._non_api_ai_bridge_module().review_non_api_ai_result(
                self.root, dict(payload or {})
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def non_api_ai_bridge_recovery_snapshot(self) -> dict[str, object]:
        try:
            return self._non_api_ai_bridge_module().non_api_ai_bridge_recovery_snapshot(
                self.root
            )
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def create_b2b_sales_execution_pack(self, task_context: dict[str, object] | None = None) -> dict[str, object]:
        task_context = task_context if isinstance(task_context, dict) else {}
        try:
            result = self._b2b_module().write_sales_execution_pack(
                self.root,
                product_id=str(task_context.get("product_id") or ""),
                task_context=task_context,
            )
            self.latest_b2b_output = Path(str(result.get("output_dir") or ""))
            snapshot = result.get("snapshot") if isinstance(result.get("snapshot"), dict) else {}
            return {
                "ok": True,
                **result,
                "message": (
                    f"{str(snapshot.get('scope_label') or 'B2B')} 执行包已生成："
                    f"总客户池 {int(snapshot.get('authoritative_company_count') or 0)} 家，"
                    f"当前范围 {int(snapshot.get('scope_candidate_count') or 0)} 家，"
                    f"{int(snapshot.get('approved_to_send_count') or 0)} 家已批准但仍需核对执行证据，"
                    f"真实外发 {int(snapshot.get('externally_sent_count') or 0)}。"
                ),
            }
        except OSError as exc:
            return {"ok": False, "error": str(exc)}

    def open_b2b_customer_pool(self) -> dict[str, object]:
        target = self._b2b_module().master_pipeline_path(self.root)
        if not target or not target.exists():
            return {"ok": False, "error": "没有找到 B2B 权威客户池。"}
        try:
            subprocess.Popen(["explorer.exe", str(target)])
            return {"ok": True, "message": f"已打开权威客户池：{target.name}"}
        except OSError as exc:
            return {"ok": False, "error": str(exc)}

    def open_b2b_output(self) -> dict[str, object]:
        target = self.latest_b2b_output or (self.root / "outputs" / "b2b_sales_agent")
        if not target.exists():
            return {"ok": False, "error": "还没有 B2B 执行产物，请先生成本轮执行包。"}
        try:
            subprocess.Popen(["explorer.exe", str(target)])
            return {"ok": True, "message": "已打开最近的 B2B 销售产物。"}
        except OSError as exc:
            return {"ok": False, "error": str(exc)}

    def open_video_editor(self) -> dict[str, object]:
        capcut = self._creative_module().find_capcut()
        if not capcut:
            return {"ok": False, "error": "本机没有找到 CapCut。"}
        try:
            subprocess.Popen([str(capcut)], cwd=str(capcut.parent))
            return {"ok": True, "message": "已打开 CapCut，可以继续导入分析后的关键帧、分镜和素材。"}
        except OSError as exc:
            return {"ok": False, "error": str(exc)}

    def open_creative_output(self) -> dict[str, object]:
        target = self.latest_creative_output or (self.root / "outputs" / "creative_video")
        if not target.exists():
            return {"ok": False, "error": "还没有视觉分析产物，请先分析视频或生成提示词包。"}
        try:
            subprocess.Popen(["explorer.exe", str(target)])
            return {"ok": True, "message": "已打开最近的视觉分析产物。"}
        except OSError as exc:
            return {"ok": False, "error": str(exc)}


def executable_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def load_runtime_config() -> dict[str, object]:
    candidates = [
        executable_dir() / "teelab-agent-root.json",
        Path(__file__).resolve().parent / "app-config.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(payload, dict):
                return payload
        except (OSError, ValueError):
            continue
    return {}


def project_root(config: dict[str, object]) -> Path:
    configured = str(os.environ.get("TEELAB_AGENT_ROOT") or config.get("project_root") or "").strip()
    if configured:
        root = Path(configured).expanduser()
        if not root.is_absolute():
            root = executable_dir() / root
    else:
        root = DEFAULT_PROJECT_ROOT
    return root.resolve()


def backend_port(config: dict[str, object]) -> int:
    try:
        return int(config.get("backend_port") or DEFAULT_PORT)
    except (TypeError, ValueError):
        return DEFAULT_PORT


def workspace_signature(root: Path) -> str:
    normalized = str(root.resolve()).casefold().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:16]


def backend_status(port: int) -> dict[str, object] | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1.2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except (OSError, ValueError):
        return None


def backend_healthy(port: int, root: Path | None = None) -> bool:
    payload = backend_status(port)
    if not payload or not payload.get("ok"):
        return False
    if int(payload.get("desktop_runtime_version") or 0) != DESKTOP_RUNTIME_VERSION:
        return False
    if root is not None and payload.get("workspace_signature") != workspace_signature(root):
        return False
    if root is not None and payload.get("backend_source_signature") != backend_source_signature(root):
        return False
    return True


def port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def select_backend_port(root: Path, preferred_port: int) -> int:
    for port in range(preferred_port, preferred_port + 50):
        if backend_healthy(port, root):
            return port
        if not port_is_open(port):
            return port
    raise RuntimeError("没有找到可用的 TeeLab 本地服务端口。")


def backend_launch_command(root: Path, port: int) -> list[str]:
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        return [
            str(executable),
            "--serve-backend",
            "--root",
            str(root),
            "--port",
            str(port),
        ]
    return [
        str(Path(sys.executable).resolve()),
        str(Path(__file__).resolve()),
        "--serve-backend",
        "--root",
        str(root),
        "--port",
        str(port),
    ]


def run_backend_only(root: Path, port: int) -> int:
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from ai_ecommerce_director.server import run_server

    run_server(root, host="127.0.0.1", port=port)
    return 0


def start_backend(root: Path, port: int) -> subprocess.Popen[bytes] | None:
    if backend_healthy(port, root):
        return None
    if port_is_open(port):
        raise RuntimeError(f"本地端口 {port} 已被其他程序占用。")
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "desktop-backend.log"
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with log_path.open("ab") as log_file:
        process = subprocess.Popen(
            backend_launch_command(root, port),
            cwd=str(root),
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
    deadline = time.monotonic() + 18
    while time.monotonic() < deadline:
        if backend_healthy(port, root):
            return process
        if process.poll() is not None:
            break
        time.sleep(0.25)
    if process.poll() is None:
        process.terminate()
    raise RuntimeError("本地 AI 服务没有在规定时间内启动。")


def stop_backend(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def mark_desktop_surface(window: webview.Window) -> None:
    script = """
      if (location.pathname !== '/desktop') {
        location.replace('/desktop');
      }
      document.documentElement.classList.add('desktop-shell');
      document.body.dataset.desktopApp = 'true';
      const style = document.createElement('style');
      style.textContent = `
        html.desktop-shell .topbar { padding-left: 20px !important; }
        html.desktop-shell .account-card { padding-bottom: 14px; }
      `;
      document.head.appendChild(style);
    """
    try:
        window.evaluate_js(script)
    except Exception:
        pass


def main() -> int:
    if "--serve-backend" in sys.argv[1:]:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--serve-backend", action="store_true")
        parser.add_argument("--root", required=True)
        parser.add_argument("--port", type=int, required=True)
        args = parser.parse_args()
        return run_backend_only(Path(args.root).resolve(), args.port)

    if webview is None:
        raise RuntimeError("当前 Python 环境未安装 PyWebView，无法启动旧版独立窗口。")

    config = load_runtime_config()
    root = project_root(config)
    port = select_backend_port(root, backend_port(config))
    if not (root / "ai_ecommerce_director" / "server.py").exists():
        raise RuntimeError(f"找不到 T-one 项目：{root}")

    backend_process = start_backend(root, port)
    start_path = "/desktop-shell"
    if not start_path.startswith("/"):
        start_path = "/" + start_path
    desktop_api = DesktopApi(root, port=port)
    desktop_api.start_runtime_recovery()
    window = webview.create_window(
        APP_TITLE,
        f"http://127.0.0.1:{port}{start_path}",
        js_api=desktop_api,
        width=1500,
        height=920,
        min_size=(900, 640),
        resizable=True,
        text_select=True,
        confirm_close=False,
        background_color="#f5f7f8",
    )
    desktop_api.window = window
    try:
        webview.start(
            gui="edgechromium",
            debug=False,
            private_mode=False,
            storage_path=str(root / "data" / "desktop_webview2"),
        )
    finally:
        desktop_api.stop_runtime_recovery()
        stop_backend(backend_process)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, str(exc), f"{APP_TITLE}启动失败", 0x10)
        finally:
            raise
