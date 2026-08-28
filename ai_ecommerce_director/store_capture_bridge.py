from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4


_STORE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{2,64}$")


def _workspace(root: Path) -> dict[str, Any]:
    path = root / "config" / "workspace_projects.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("工作区店铺配置无效。")
    return payload


def _store_scope(root: Path, *, platform: str, country_site: str, store_id: str) -> dict[str, str]:
    matches: list[dict[str, str]] = []
    for project in _workspace(root).get("projects") or []:
        if not isinstance(project, dict):
            continue
        for channel in project.get("channels") or []:
            if not isinstance(channel, dict):
                continue
            channel_platform = str(channel.get("platform") or "").strip().lower()
            channel_site = str(channel.get("country_site") or "").strip().upper()
            for store in channel.get("stores") or []:
                if not isinstance(store, dict):
                    continue
                external_id = str(store.get("external_id") or "").strip()
                store_platform = str(store.get("platform") or channel_platform).strip().lower()
                store_site = str(store.get("country_site") or channel_site).strip().upper()
                if (store_platform, store_site, external_id) != (platform, country_site, store_id):
                    continue
                tasks = [item for item in (store.get("tasks") or []) if isinstance(item, dict)]
                if len(tasks) != 1 or not str(tasks[0].get("id") or "").strip():
                    raise ValueError("该店铺没有唯一的实时数据任务，不能自动归档。")
                matches.append(
                    {
                        "project_id": str(project.get("id") or "").strip(),
                        "task_id": str(tasks[0].get("id") or "").strip(),
                        "store_binding_id": str(store.get("id") or "").strip(),
                        "store_id": external_id,
                    }
                )
    if len(matches) != 1 or not all(matches[0].values()):
        raise ValueError("没有找到唯一匹配的平台、站点和店铺绑定。")
    return matches[0]


def _count(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} 不是有效数量。")
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 不是有效数量。") from exc
    if not math.isfinite(number) or number < 0 or not number.is_integer():
        raise ValueError(f"{field} 必须是非负整数。")
    return int(number)


def _amount(value: Any, field: str) -> str:
    try:
        number = Decimal(str(value).replace(",", "").strip() or "0")
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} 不是有效金额。") from exc
    if not number.is_finite() or number < 0:
        raise ValueError(f"{field} 必须是非负金额。")
    normalized = format(number, "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def _public_product_links(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        parsed = urlsplit(str(item.get("url") or "").strip())
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not host.endswith(".shein.com") or host == "sellerhub.shein.com":
            continue
        url = urlunsplit(("https", parsed.netloc, parsed.path or "/", "", ""))
        rows.append(
            {
                "url": url,
                "title": str(item.get("title") or "").strip()[:160],
                "order_count": _count(item.get("order_count") or 0, "链接订单数"),
                "gross_sales": _amount(item.get("gross_sales") or 0, "链接销售额"),
            }
        )
        if len(rows) >= 100:
            break
    return rows


def _validate_shein_order_page(value: Any) -> str:
    parsed = urlsplit(str(value or "").strip())
    fragment = parsed.fragment.lower()
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").lower() != "sellerhub.shein.com"
        or not fragment.startswith("/gsp/order-management/list")
        or any(token in fragment for token in ("login", "signin", "sso", "identity", "verification"))
    ):
        raise ValueError("当前页面不是已登录的 SHEIN 订单管理页。")
    return urlunsplit(("https", "sellerhub.shein.com", parsed.path or "/", "", parsed.fragment))


def persist_store_capture(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("采集数据格式无效。")
    platform = str(payload.get("platform") or "").strip().lower()
    country_site = str(payload.get("country_site") or "").strip().upper()
    store_id = str(payload.get("store_id") or "").strip()
    if platform != "shein" or country_site != "US":
        raise ValueError("当前插件只接收 SHEIN US 店铺数据。")
    if not _STORE_ID_RE.fullmatch(store_id):
        raise ValueError("店铺 ID 格式无效。")
    source_page = _validate_shein_order_page(payload.get("page_url"))
    summary = payload.get("order_summary")
    if not isinstance(summary, dict) or summary.get("data_returned") is not True:
        raise ValueError("页面没有返回可验证的订单汇总，未保存。")
    if summary.get("contains_order_ids_or_customer_pii") is not False:
        raise ValueError("插件不得回传订单号或客户资料。")
    scope = _store_scope(
        root,
        platform=platform,
        country_site=country_site,
        store_id=store_id,
    )
    captured_at = datetime.now(timezone.utc).isoformat()
    record = {
        "schema_version": 1,
        "capture_id": f"store-plugin-{uuid4().hex}",
        "captured_at": captured_at,
        "project_id": scope["project_id"],
        "task_id": scope["task_id"],
        "platform": platform,
        "country_site": country_site,
        "store_binding_id": scope["store_binding_id"],
        "store_id": store_id,
        "source": "browser_extension_visible_aggregate",
        "source_page": source_page,
        "order_summary": {
            "data_returned": True,
            "order_count": _count(summary.get("order_count") or 0, "订单数"),
            "unit_count": _count(summary.get("unit_count") or 0, "商品件数"),
            "gross_sales": _amount(summary.get("gross_sales") or 0, "商品总价"),
            "expected_income": _amount(summary.get("expected_income") or 0, "预计收入"),
            "window_start": str(summary.get("window_start") or "").strip()[:32],
            "window_end": str(summary.get("window_end") or "").strip()[:32],
            "product_links": _public_product_links(summary.get("product_links")),
            "contains_order_ids_or_customer_pii": False,
        },
        "read_only": True,
        "external_store_write_actions": 0,
    }
    result_dir = root / "projects" / scope["project_id"] / "tasks" / scope["task_id"] / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    latest_path = result_dir / "shein-order-summary-latest.json"
    history_path = result_dir / "shein-order-summary-history.jsonl"
    temporary_path = latest_path.with_suffix(".json.tmp")
    temporary_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(latest_path)
    with history_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {
        "ok": True,
        "capture_id": record["capture_id"],
        "captured_at": captured_at,
        "project_id": scope["project_id"],
        "task_id": scope["task_id"],
        "store_binding_id": scope["store_binding_id"],
        "store_id": store_id,
        "order_summary": record["order_summary"],
        "result_path": latest_path.relative_to(root).as_posix(),
        "history_path": history_path.relative_to(root).as_posix(),
        "read_only": True,
        "external_store_write_actions": 0,
    }
