from __future__ import annotations

import json
import os
import base64
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .parser import canonical_record_type, normalize_fields
from .scoring import score_record
from .storage import append_record
from .types import IntakeRecord


API_SOURCE_CONFIG = Path("config") / "api_sources.json"
API_REPORT_PREFIX = "api_sources"


@dataclass(slots=True)
class ApiRunResult:
    run_date: str
    statuses: list[dict[str, Any]]
    records: list[IntakeRecord]
    report: str
    report_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "statuses": self.statuses,
            "records": [record.to_dict() for record in self.records],
            "report": self.report,
            "report_path": str(self.report_path),
        }


def run_api_sources(root: Path, run_date: str | None = None) -> ApiRunResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    statuses: list[dict[str, Any]] = []
    records: list[IntakeRecord] = []

    for source in load_api_sources(root):
        status, source_records = collect_api_source(root, source, report_date)
        statuses.append(status)
        records.extend(source_records)

    report = build_api_report(report_date, statuses, records)
    report_path = write_api_report(root, report_date, report)
    return ApiRunResult(report_date, statuses, records, report, report_path)


def load_api_sources(root: Path) -> list[dict[str, Any]]:
    path = root / API_SOURCE_CONFIG
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    sources = payload.get("sources", []) if isinstance(payload, dict) else []
    return [source for source in sources if isinstance(source, dict)]


def collect_api_source(root: Path, source: dict[str, Any], run_date: str) -> tuple[dict[str, Any], list[IntakeRecord]]:
    source_id = str(source.get("id") or source.get("name") or "unnamed-api").strip()
    if not source.get("enabled", False):
        return {"source_id": source_id, "status": "skipped", "provider": source.get("provider") or "", "reason": "source disabled"}, []

    auth_type = str(source.get("auth_type") or "bearer").lower()
    if auth_type in {"oauth", "signed"}:
        return {
            "source_id": source_id,
            "status": "needs_integration",
            "provider": source.get("provider") or "",
            "reason": str(source.get("integration_notes") or "This API needs OAuth/signature setup before it can run."),
        }, []

    api_key_env = str(source.get("api_key_env") or "").strip()
    api_key = os.getenv(api_key_env) if api_key_env else str(source.get("api_key") or "").strip()
    if auth_type == "oauth_client_credentials" and not api_key:
        try:
            api_key = request_client_credentials_token(source)
        except Exception as exc:  # noqa: BLE001 - report credential/token issues clearly.
            return {
                "source_id": source_id,
                "status": "missing_api_key",
                "provider": source.get("provider") or "",
                "reason": str(exc),
            }, []
    if auth_type == "basic":
        basic_username_env = str(source.get("basic_username_env") or "").strip()
        basic_password_env = str(source.get("basic_password_env") or "").strip()
        basic_username = os.getenv(basic_username_env) if basic_username_env else str(source.get("basic_username") or "").strip()
        basic_password = os.getenv(basic_password_env) if basic_password_env else str(source.get("basic_password") or "").strip()
        if not basic_username or not basic_password:
            missing = ", ".join(
                name
                for name, value in [
                    (basic_username_env or "basic_username", basic_username),
                    (basic_password_env or "basic_password", basic_password),
                ]
                if not value
            )
            return {
                "source_id": source_id,
                "status": "missing_api_key",
                "provider": source.get("provider") or "",
                "reason": f"Please set Basic Auth credentials: {missing}.",
            }, []
        api_key = base64.b64encode(f"{basic_username}:{basic_password}".encode("utf-8")).decode("ascii")
    if source.get("requires_api_key", True) and not api_key:
        return {
            "source_id": source_id,
            "status": "missing_api_key",
            "provider": source.get("provider") or "",
            "reason": f"Please set environment variable {api_key_env}." if api_key_env else "Please configure an API key.",
        }, []

    try:
        payload = request_api_source(source, api_key)
    except Exception as exc:  # noqa: BLE001 - source-level failures belong in the report.
        return {
            "source_id": source_id,
            "status": "failed",
            "provider": source.get("provider") or "",
            "reason": str(exc),
            "endpoint": render_endpoint_for_status(source),
        }, []

    items = select_items(payload, str(source.get("items_path") or ""))
    limit = int(source.get("limit", 20) or 20)
    records: list[IntakeRecord] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        fields = map_api_item_to_fields(source, item, payload)
        record_type = canonical_record_type(str(source.get("record_type") or "hot_link"))
        fields = normalize_fields(fields)
        score, notes = score_record(record_type, fields)
        record = IntakeRecord(
            record_type=record_type,
            fields=fields,
            raw_text=json.dumps({"source_id": source_id, "item": item}, ensure_ascii=False),
            source=f"api:{source.get('provider') or source_id}",
            score=score,
            director_notes=notes,
            metadata={
                "api_source_id": source_id,
                "api_provider": source.get("provider"),
                "api_run_date": run_date,
                "api_safe_mode": "read_only",
            },
        )
        append_record(root, record)
        records.append(record)

    return {
        "source_id": source_id,
        "status": "collected",
        "provider": source.get("provider") or "",
        "item_count": len(items),
        "saved_records": len(records),
        "endpoint": render_endpoint_for_status(source),
    }, records


def request_api_source(source: dict[str, Any], api_key: str) -> Any:
    base_url = str(source.get("base_url") or "").rstrip("/")
    path = str(source.get("path") or "").lstrip("/")
    if not base_url:
        raise ValueError("missing base_url")
    url = f"{base_url}/{path}" if path else base_url
    params = dict(source.get("params") or {})
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)

    headers = {str(key): str(value) for key, value in dict(source.get("headers") or {}).items()}
    auth_type = str(source.get("auth_type") or "bearer").lower()
    if api_key:
        if auth_type == "x-api-key":
            headers[str(source.get("api_key_header") or "X-API-Key")] = api_key
        elif auth_type == "basic":
            headers["Authorization"] = f"Basic {api_key}"
        elif auth_type == "query":
            key_name = str(source.get("api_key_param") or "api_key")
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode({key_name: api_key})
        else:
            headers["Authorization"] = f"Bearer {api_key}"

    method = str(source.get("method") or "GET").upper()
    data = None
    if method != "GET":
        data = json.dumps(source.get("body") or {}, ensure_ascii=False).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    timeout = int(source.get("timeout_seconds", 30) or 30)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(int(source.get("max_bytes", 2_000_000) or 2_000_000))
    return json.loads(raw.decode("utf-8", errors="replace"))


def select_items(payload: Any, items_path: str) -> list[Any]:
    value = get_path(payload, items_path) if items_path else payload
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ["items", "data", "products", "videos", "creators", "results", "list"]:
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
    return []


def map_api_item_to_fields(source: dict[str, Any], item: dict[str, Any], payload: Any) -> dict[str, Any]:
    fields = dict(source.get("fields") or {})
    field_map = source.get("field_map") if isinstance(source.get("field_map"), dict) else {}
    for target, path in field_map.items():
        value = get_path(item, str(path))
        if value is not None and value != "":
            fields[str(target)] = value
    fields.setdefault("source_platform", source.get("source_platform") or source.get("provider") or "API")
    fields.setdefault("product_name", item.get("title") or item.get("name") or item.get("product_name") or item.get("productName") or "")
    fields.setdefault("url", item.get("url") or item.get("product_url") or item.get("productUrl") or item.get("video_url") or "")
    fields.setdefault("visible_growth_signal", source.get("notes") or "API source snapshot.")
    fields["api_raw_keys"] = sorted(str(key) for key in item.keys())[:40]
    if isinstance(payload, dict) and payload.get("selectedChannel"):
        fields.setdefault("api_selected_channel", payload.get("selectedChannel"))
    return fields


def request_client_credentials_token(source: dict[str, Any]) -> str:
    client_id_env = str(source.get("client_id_env") or "").strip()
    client_secret_env = str(source.get("client_secret_env") or "").strip()
    client_id = os.getenv(client_id_env) if client_id_env else str(source.get("client_id") or "").strip()
    client_secret = os.getenv(client_secret_env) if client_secret_env else str(source.get("client_secret") or "").strip()
    token_url = str(source.get("oauth_token_url") or "").strip()
    if not token_url:
        raise ValueError("Missing oauth_token_url for client credentials source.")
    if not client_id or not client_secret:
        missing = ", ".join(name for name, value in [(client_id_env or "client_id", client_id), (client_secret_env or "client_secret", client_secret)] if not value)
        raise ValueError(f"Please set OAuth client credentials: {missing}.")

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": "Basic "
        + base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii"),
    }
    body = {
        "grant_type": "client_credentials",
    }
    scope = str(source.get("oauth_scope") or "").strip()
    if scope:
        body["scope"] = scope
    request = urllib.request.Request(
        token_url,
        data=urllib.parse.urlencode(body).encode("utf-8"),
        method="POST",
        headers=headers,
    )
    timeout = int(source.get("timeout_seconds", 30) or 30)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise ValueError("OAuth token response did not include access_token.")
    return token


def get_path(payload: Any, path: str) -> Any:
    if not path:
        return payload
    current = payload
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            current = current[index] if 0 <= index < len(current) else None
        else:
            return None
        if current is None:
            return None
    return current


def render_endpoint_for_status(source: dict[str, Any]) -> str:
    base_url = str(source.get("base_url") or "").rstrip("/")
    path = str(source.get("path") or "").lstrip("/")
    return f"{base_url}/{path}" if path else base_url


def build_api_report(run_date: str, statuses: list[dict[str, Any]], records: list[IntakeRecord]) -> str:
    lines = [
        "# API 数据源巡检报告",
        "",
        f"日期：{run_date}",
        "",
        "## 结论",
        "",
    ]
    if not statuses:
        lines.append("- 暂无 API 数据源配置。")
    for status in statuses:
        lines.append(
            f"- {status.get('source_id')}：{status.get('status')}，保存 {status.get('saved_records', 0)} 条，"
            f"{status.get('reason') or status.get('endpoint') or ''}"
        )

    lines.extend(["", "## 新增记录", ""])
    if not records:
        lines.append("- 暂无新增 API 记录。")
    for record in records[:30]:
        fields = record.fields
        name = fields.get("product_name") or fields.get("video_url") or fields.get("url") or record.record_id[:8]
        lines.append(f"- {name}｜{record.record_type}｜优先级 {record.score.get('priority', '待定')}")
    return "\n".join(lines).rstrip() + "\n"


def write_api_report(root: Path, run_date: str, content: str) -> Path:
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{API_REPORT_PREFIX}_{run_date}.md"
    path.write_text(content, encoding="utf-8")
    return path


def latest_api_report(root: Path) -> tuple[str, Path | None]:
    output_dir = root / "outputs"
    paths = sorted(output_dir.glob(f"{API_REPORT_PREFIX}_*.md"), reverse=True)
    if not paths:
        return "还没有 API 数据源巡检报告。", None
    path = paths[0]
    return path.read_text(encoding="utf-8"), path


def api_source_display_label(status: dict[str, Any]) -> str:
    provider = str(status.get("provider") or "").strip()
    source_id = str(status.get("source_id") or "").strip()
    if provider:
        suffix = "（候选，待确认接口）" if "placeholder" in source_id.lower() else ""
        return f"{provider}{suffix}"
    return source_id.replace("-placeholder", "（候选，待确认接口）") or "未命名平台连接"


def api_status_display_label(status: str) -> str:
    labels = {
        "skipped": "未启用",
        "missing_api_key": "待配置密钥/授权",
        "needs_integration": "待接 OAuth/签名流程",
        "failed": "连接失败，需复核接口",
        "collected": "已只读采集",
    }
    return labels.get(status, status or "待检查")


def api_status_customer_reason(status: dict[str, Any]) -> str:
    state = str(status.get("status") or "")
    reason = str(status.get("reason") or "").strip()
    endpoint = str(status.get("endpoint") or "").strip()
    if state == "skipped":
        return "当前只是候选连接，未启用，不会采集或操作真实店铺。"
    if state == "missing_api_key":
        return "缺少密钥或账号授权，只能保留为待接入来源。"
    if state == "needs_integration":
        return reason or "需要开发者应用、OAuth 或签名流程，不能直接运行。"
    if state == "failed":
        if "replace-with" in endpoint:
            return "接口地址仍是待确认模板，不能当作已接通。"
        return reason or "接口返回异常，需要复核账号、权限、站点和请求参数。"
    if state == "collected":
        return f"只读保存 {status.get('saved_records', 0)} 条；不会发布、改价、发货或投广告。"
    return reason or endpoint or "待检查。"


def build_api_report(run_date: str, statuses: list[dict[str, Any]], records: list[IntakeRecord]) -> str:
    lines = [
        "# 平台连接体检报告",
        "",
        f"日期：{run_date}",
        "",
        "## 结论",
        "",
        "- 这里只做只读采集和连接体检；不会发布商品、改价、发货、报名活动、修改广告预算或操作真实店铺。",
        "- 候选接口、占位接口、未授权接口会显示为待接入，不当作已经接通。",
        "- 官方店铺 API、广告 API、第三方榜单 API 必须按平台、国家站点、店铺模式和执行身份隔离。",
        "",
    ]
    if not statuses:
        lines.append("- 暂无平台连接配置。")
    for status in statuses:
        source_label = api_source_display_label(status)
        state_label = api_status_display_label(str(status.get("status") or ""))
        reason = api_status_customer_reason(status)
        lines.append(f"- {source_label}：{state_label}；保存 {status.get('saved_records', 0)} 条；{reason}")

    lines.extend(["", "## 新增记录", ""])
    if not records:
        lines.append("- 暂无新增平台连接记录。")
    for record in records[:30]:
        fields = record.fields
        name = fields.get("product_name") or fields.get("video_url") or fields.get("url") or record.record_id[:8]
        lines.append(f"- {name} / {record.record_type} / 优先级 {record.score.get('priority', '待定')}")
    return "\n".join(lines).rstrip() + "\n"


def latest_api_report(root: Path) -> tuple[str, Path | None]:
    output_dir = root / "outputs"
    paths = sorted(output_dir.glob(f"{API_REPORT_PREFIX}_*.md"), reverse=True)
    if not paths:
        return "还没有平台连接体检报告。", None
    path = paths[0]
    return path.read_text(encoding="utf-8"), path
