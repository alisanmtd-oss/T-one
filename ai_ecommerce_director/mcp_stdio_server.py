from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, TextIO

from .external_access_gateway import (
    authenticate_external_client,
    read_external_draft,
    read_external_project_context,
    submit_external_draft,
)
from .local_secret_vault import read_protected_credential


LATEST_PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18")
SERVER_NAME = "t-one-scoped-local-gateway"
SERVER_VERSION = "0.1.0"
TOKEN_ENV_NAME = "TONE_MCP_BEARER_TOKEN"


class McpProtocolError(Exception):
    def __init__(self, code: int, message: str, data: Any | None = None) -> None:
        super().__init__(message)
        self.code = int(code)
        self.message = str(message)
        self.data = data


def _error_response(request_id: Any, error: McpProtocolError) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": error.code, "message": error.message},
    }
    if error.data is not None:
        payload["error"]["data"] = error.data
    return payload


def _success_response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _required_string(arguments: dict[str, Any], key: str, limit: int) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required.")
    return value.strip()[:limit]


def _optional_string_list(arguments: dict[str, Any], key: str, limit: int) -> list[str]:
    value = arguments.get(key, [])
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError(f"{key} must be an array with at most {limit} items.")
    return [str(item).strip()[:240] for item in value if str(item).strip()]


def _tool_result(data: dict[str, Any], text: str, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": data,
        "isError": bool(is_error),
    }


class ToneMcpStdioServer:
    def __init__(self, root: Path, raw_token: str) -> None:
        self.root = Path(root).resolve()
        self._authorization = "Bearer " + str(raw_token or "").strip()
        client = self._client()
        if str(client.get("client_type") or "") != "mcp_client":
            raise PermissionError("The bearer token is not registered for an MCP client.")
        self._initialize_seen = False
        self._initialized = False
        self._protocol_version = ""

    def _client(self) -> dict[str, Any]:
        client = authenticate_external_client(self.root, self._authorization)
        if str(client.get("client_type") or "") != "mcp_client":
            raise PermissionError("The bearer token is not registered for an MCP client.")
        return client

    def _tool_definitions(self) -> list[dict[str, Any]]:
        scopes = {str(item) for item in self._client().get("scopes") or []}
        tools: list[dict[str, Any]] = []
        if "context.read" in scopes:
            tools.append({
                "name": "tone.read_project_context",
                "title": "Read scoped T-one project context",
                "description": (
                    "Read sanitized project/task/store context within this MCP client's explicit route. "
                    "Never returns credentials, browser sessions, or external store identifiers."
                ),
                "inputSchema": {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string", "minLength": 1, "maxLength": 128}
                    },
                    "required": ["project_id"],
                    "additionalProperties": False,
                },
                "annotations": {
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": False,
                },
                "execution": {"taskSupport": "forbidden"},
            })
        if "draft.submit" in scopes:
            tools.append({
                "name": "tone.submit_owner_review_draft",
                "title": "Submit a T-one owner-review draft",
                "description": (
                    "Save a scoped, idempotent local draft. The draft always remains "
                    "owner_review_required and not_enqueued; it never executes a task or external action."
                ),
                "inputSchema": {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string", "minLength": 1, "maxLength": 128},
                        "task_id": {"type": "string", "minLength": 1, "maxLength": 128},
                        "title": {"type": "string", "minLength": 1, "maxLength": 160},
                        "instruction": {"type": "string", "minLength": 1, "maxLength": 8000},
                        "evidence_refs": {
                            "type": "array",
                            "maxItems": 20,
                            "items": {"type": "string", "maxLength": 240},
                        },
                        "idempotency_key": {"type": "string", "minLength": 8, "maxLength": 128},
                    },
                    "required": ["project_id", "task_id", "title", "instruction", "idempotency_key"],
                    "additionalProperties": False,
                },
                "annotations": {
                    "readOnlyHint": False,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": False,
                },
                "execution": {"taskSupport": "forbidden"},
            })
        if "result.read" in scopes:
            tools.append({
                "name": "tone.read_draft_status",
                "title": "Read same-client T-one draft status",
                "description": "Read one draft receipt created by this exact MCP client.",
                "inputSchema": {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "type": "object",
                    "properties": {
                        "draft_id": {"type": "string", "minLength": 1, "maxLength": 128}
                    },
                    "required": ["draft_id"],
                    "additionalProperties": False,
                },
                "annotations": {
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": False,
                },
                "execution": {"taskSupport": "forbidden"},
            })
        return tools

    def _initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        if self._initialize_seen:
            raise McpProtocolError(-32600, "initialize may only be sent once.")
        requested = str(params.get("protocolVersion") or "").strip()
        if not requested:
            raise McpProtocolError(-32602, "protocolVersion is required.")
        if not isinstance(params.get("capabilities"), dict) or not isinstance(
            params.get("clientInfo"), dict
        ):
            raise McpProtocolError(-32602, "capabilities and clientInfo objects are required.")
        negotiated = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else LATEST_PROTOCOL_VERSION
        self._initialize_seen = True
        self._protocol_version = negotiated
        return {
            "protocolVersion": negotiated,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {
                "name": SERVER_NAME,
                "title": "T-one Scoped Local Gateway",
                "version": SERVER_VERSION,
                "description": "Local stdio adapter for sanitized context and owner-review drafts only.",
            },
            "instructions": (
                "All tools are restricted to the registered client's project/task/store scope. "
                "No tool can enqueue work, execute a model or tool, access credentials, call a platform, "
                "or cause an external side effect."
            ),
        }

    def _call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        name = str(params.get("name") or "").strip()
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            raise McpProtocolError(-32602, "tools/call arguments must be an object.")
        available = {str(item["name"]) for item in self._tool_definitions()}
        if name not in available:
            raise McpProtocolError(-32602, "Unknown or unavailable tool.", {"name": name})
        try:
            client = self._client()
            if name == "tone.read_project_context":
                project_id = _required_string(arguments, "project_id", 128)
                result = read_external_project_context(self.root, client, project_id)
                project = result.get("project") if isinstance(result.get("project"), dict) else {}
                workstreams = project.get("workstreams") if isinstance(project.get("workstreams"), list) else []
                channels = project.get("channels") if isinstance(project.get("channels"), list) else []
                return _tool_result(
                    result,
                    f"已读取脱敏项目上下文：{project_id}；任务 {len(workstreams)}，渠道 {len(channels)}，外部动作 0。",
                )
            if name == "tone.submit_owner_review_draft":
                payload = {
                    "project_id": _required_string(arguments, "project_id", 128),
                    "task_id": _required_string(arguments, "task_id", 128),
                    "title": _required_string(arguments, "title", 160),
                    "instruction": _required_string(arguments, "instruction", 8000),
                    "evidence_refs": _optional_string_list(arguments, "evidence_refs", 20),
                    "requested_side_effects": [],
                }
                result = submit_external_draft(
                    self.root,
                    client,
                    payload,
                    idempotency_key=_required_string(arguments, "idempotency_key", 128),
                )
                draft = result.get("draft") if isinstance(result.get("draft"), dict) else {}
                return _tool_result(
                    result,
                    f"草稿 {draft.get('id', '')} 已保存为 owner_review_required / not_enqueued；外部动作 0。",
                )
            draft_id = _required_string(arguments, "draft_id", 128)
            result = read_external_draft(self.root, client, draft_id)
            draft = result.get("draft") if isinstance(result.get("draft"), dict) else {}
            return _tool_result(
                result,
                f"草稿 {draft_id}：{draft.get('status', 'unknown')} / {draft.get('execution_state', 'unknown')}。",
            )
        except (PermissionError, ValueError) as exc:
            return _tool_result(
                {"ok": False, "error": str(exc), "external_side_effect_count": 0},
                str(exc),
                is_error=True,
            )

    def dispatch(self, message: Any) -> dict[str, Any] | None:
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            raise McpProtocolError(-32600, "Invalid JSON-RPC request.")
        method = message.get("method")
        if not isinstance(method, str) or not method:
            raise McpProtocolError(-32600, "method is required.")
        is_notification = "id" not in message
        request_id = message.get("id")
        params = message.get("params", {})
        if not isinstance(params, dict):
            raise McpProtocolError(-32602, "params must be an object.")

        if method == "ping":
            result: dict[str, Any] = {}
        elif method == "initialize":
            if is_notification:
                return None
            result = self._initialize(params)
        elif method == "notifications/initialized":
            if not self._initialize_seen:
                return None
            self._initialized = True
            return None
        else:
            if not self._initialized:
                raise McpProtocolError(-32002, "Server has not received notifications/initialized.")
            if method == "tools/list":
                result = {"tools": self._tool_definitions()}
            elif method == "tools/call":
                result = self._call_tool(params)
            else:
                if is_notification:
                    return None
                raise McpProtocolError(-32601, "Method not found.", {"method": method})
        if is_notification:
            return None
        return _success_response(request_id, result)

    def handle_line(self, line: str) -> dict[str, Any] | None:
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            return _error_response(None, McpProtocolError(-32700, "Parse error."))
        try:
            return self.dispatch(message)
        except McpProtocolError as exc:
            return _error_response(message.get("id") if isinstance(message, dict) else None, exc)
        except (PermissionError, ValueError) as exc:
            return _error_response(
                message.get("id") if isinstance(message, dict) else None,
                McpProtocolError(-32602, str(exc)),
            )
        except Exception:
            return _error_response(
                message.get("id") if isinstance(message, dict) else None,
                McpProtocolError(-32603, "Internal error."),
            )

    def serve(self, stdin: TextIO, stdout: TextIO) -> None:
        for raw_line in stdin:
            line = raw_line.rstrip("\r\n")
            if not line:
                continue
            response = self.handle_line(line)
            if response is None:
                continue
            stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local T-one MCP stdio adapter.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--token-env", default=TOKEN_ENV_NAME)
    parser.add_argument("--credential-file", type=Path)
    args = parser.parse_args()
    raw_token = ""
    if args.credential_file:
        try:
            raw_token, _ = read_protected_credential(args.credential_file)
        except (OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if not raw_token:
        raw_token = os.environ.get(str(args.token_env), "")
    if not raw_token:
        print(
            f"Missing protected credential file or bearer token environment variable: {args.token_env}",
            file=sys.stderr,
        )
        return 2
    try:
        server = ToneMcpStdioServer(args.root, raw_token)
    except (PermissionError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    server.serve(sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
