from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from uuid import uuid4

from .erp_connector_registry import verify_erp_http_json_connection


STATE_RELATIVE_PATH = Path("data") / "erp_provider_rehearsal_runtime.json"
MAX_RECEIPTS = 100
PROVIDER_CONTRACTS = {
    "miaoshou": {
        "name": "妙手 ERP",
        "protocol": "T-one ERP HTTP JSON v1",
        "real_authorization": "妙手提供或批准的接口、精确店铺授权与只读权限",
        "identity_fields": [
            "platform",
            "country_site",
            "store_model",
            "ownership",
            "remote_store_id",
        ],
        "first_real_capability": "health_read",
    }
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_state(root: Path) -> dict[str, Any]:
    try:
        payload = json.loads((root / STATE_RELATIVE_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = {}
    receipts = payload.get("receipts") if isinstance(payload, dict) else []
    return {
        "schema_version": 1,
        "receipts": [item for item in receipts or [] if isinstance(item, dict)],
    }


def _save_state(root: Path, state: dict[str, Any]) -> None:
    path = root / STATE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    state["receipts"] = list(state.get("receipts") or [])[-MAX_RECEIPTS:]
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def erp_provider_rehearsal_snapshot(root: Path) -> dict[str, Any]:
    state = _read_state(root)
    return {
        "schema_version": 1,
        "providers": [
            {"id": provider_id, **contract}
            for provider_id, contract in PROVIDER_CONTRACTS.items()
        ],
        "receipts": list(state["receipts"])[-20:][::-1],
        "real_connection_count": 0,
        "private_read_count": 0,
        "credential_saved_count": 0,
        "external_action_count": 0,
    }


def run_erp_provider_rehearsal(
    root: Path, payload: dict[str, Any], *, actor: str = "owner"
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("ERP 连接演练请求必须是对象。")
    forbidden = {
        "token",
        "api_key",
        "password",
        "secret",
        "auth_value",
        "cookie",
        "store_id",
    }
    if any(str(key).strip().casefold() in forbidden for key in payload):
        raise ValueError("本地 ERP 演练不接收账号、Token、密码或真实店铺编号。")
    provider_id = str(payload.get("provider_id") or "miaoshou").strip().casefold()
    contract = PROVIDER_CONTRACTS.get(provider_id)
    if not contract:
        raise ValueError("请选择已经审核过的 ERP 演练契约。")

    expected_scope = {
        "project_id": "rehearsal-project",
        "store_binding_id": "rehearsal-store",
        "platform": "non_amazon_demo",
        "country_site": "GLOBAL",
        "store_model": "local_store",
        "ownership": "self_store",
    }
    response_payload = {
        "ok": True,
        "service": f"{provider_id}-contract-rehearsal",
        "connection_identity": {
            "scope": expected_scope,
            "remote_store_id": f"rehearsal-{provider_id}-store",
            "capabilities": ["health_read"],
        },
    }
    request_observed = {"count": 0, "path": ""}

    class RehearsalHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            request_observed["count"] += 1
            request_observed["path"] = self.path
            if self.path != "/health":
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(response_payload).encode("utf-8"))

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), RehearsalHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    stopped = False
    try:
        verified = verify_erp_http_json_connection(
            base_url=f"http://127.0.0.1:{server.server_port}",
            health_path="/health",
            auth_type="none",
            expected_scope=expected_scope,
            allow_loopback=True,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        stopped = not thread.is_alive()

    receipt = {
        "id": f"erp-provider-rehearsal-{uuid4().hex[:16]}",
        "created_at": _now(),
        "actor": str(actor or "owner")[:120],
        "provider_id": provider_id,
        "provider_name": str(contract["name"]),
        "status": "local_mock_contract_verified",
        "protocol": str(contract["protocol"]),
        "identity_fields_verified": list(contract["identity_fields"]),
        "capabilities_verified": list(verified.get("capabilities") or []),
        "request_count": int(request_observed["count"]),
        "request_path": str(request_observed["path"]),
        "mock_server_stopped": stopped,
        "next_step": (
            "负责人获得妙手批准的接口后，选择真实店铺并用只读 health_read 权限验证；"
            "演练结果不能迁移为真实连接。"
        ),
        "connection_state": "not_configured",
        "real_store_bound": False,
        "credential_saved": False,
        "private_data_read": False,
        "orders_read": False,
        "inventory_read": False,
        "external_action_count": 0,
    }
    state = _read_state(root)
    state["receipts"].append(receipt)
    _save_state(root, state)
    return {
        "ok": True,
        "status": receipt["status"],
        "receipt": receipt,
        "connected": False,
        "external_action_count": 0,
    }


__all__ = [
    "erp_provider_rehearsal_snapshot",
    "run_erp_provider_rehearsal",
]
