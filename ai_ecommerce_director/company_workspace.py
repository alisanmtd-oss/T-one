from __future__ import annotations

import json
import re
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .workspace_schema import (
    business_bound_stores,
    business_visible_project_tasks,
    normalize_workspace_config,
)


SECRET_ASSIGNMENT = re.compile(
    r"(?i)(password|passphrase|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"client[_-]?secret|private[_-]?key)\s*[:=]"
)

REALTIME_DASHBOARD_EVIDENCE_REFS = (
    "outputs/amazon_10001_operating_state_latest.json",
    "outputs/b2b_10001_master_sales_pipeline_2026-07-11_0506.csv",
    "data/task_execution_runtime.sqlite3",
    "config/workspace_projects.json",
)
LOCAL_SNAPSHOT_RECENT_SECONDS = 24 * 60 * 60
LOCAL_RUNTIME_RECENT_SECONDS = 5 * 60
LIVE_STORE_RECENT_SECONDS = 5 * 60


# One desktop/API render asks for the same B2B snapshot through the company,
# project and dashboard projections.  Keep that reuse request-local so a new
# settlement/import file is visible on the next request, while avoiding five
# complete walks of the large outputs directory in a single request.
_SALES_SNAPSHOT_REQUEST_CACHE: ContextVar[dict[str, dict[str, Any]] | None] = (
    ContextVar("company_workspace_sales_snapshot_request_cache", default=None)
)
_SKIP_SALES_OUTPUT_SCAN: ContextVar[bool] = ContextVar(
    "company_workspace_skip_sales_output_scan", default=False
)


@contextmanager
def skip_sales_output_scan():
    """Keep configuration views fast without hiding connector diagnostics."""

    token = _SKIP_SALES_OUTPUT_SCAN.set(True)
    try:
        yield
    finally:
        _SKIP_SALES_OUTPUT_SCAN.reset(token)


MARKET_SITE_METADATA: dict[str, dict[str, Any]] = {
    "GLOBAL": {"name": "全球", "coords": None},
    "US": {"name": "美国", "coords": [37.0902, -95.7129]},
    "CA": {"name": "加拿大", "coords": [56.1304, -106.3468]},
    "MX": {"name": "墨西哥", "coords": [23.6345, -102.5528]},
    "BR": {"name": "巴西", "coords": [-14.235, -51.9253]},
    "AR": {"name": "阿根廷", "coords": [-38.4161, -63.6167]},
    "CL": {"name": "智利", "coords": [-35.6751, -71.543]},
    "CO": {"name": "哥伦比亚", "coords": [4.5709, -74.2973]},
    "PE": {"name": "秘鲁", "coords": [-9.19, -75.0152]},
    "GB": {"name": "英国", "coords": [55.3781, -3.436]},
    "UK": {"name": "英国", "coords": [55.3781, -3.436]},
    "IE": {"name": "爱尔兰", "coords": [53.1424, -7.6921]},
    "DE": {"name": "德国", "coords": [51.1657, 10.4515]},
    "FR": {"name": "法国", "coords": [46.2276, 2.2137]},
    "IT": {"name": "意大利", "coords": [41.8719, 12.5674]},
    "ES": {"name": "西班牙", "coords": [40.4637, -3.7492]},
    "NL": {"name": "荷兰", "coords": [52.1326, 5.2913]},
    "SE": {"name": "瑞典", "coords": [60.1282, 18.6435]},
    "PL": {"name": "波兰", "coords": [51.9194, 19.1451]},
    "TR": {"name": "土耳其", "coords": [38.9637, 35.2433]},
    "SG": {"name": "新加坡", "coords": [1.3521, 103.8198]},
    "MY": {"name": "马来西亚", "coords": [4.2105, 101.9758]},
    "TH": {"name": "泰国", "coords": [15.87, 100.9925]},
    "VN": {"name": "越南", "coords": [14.0583, 108.2772]},
    "PH": {"name": "菲律宾", "coords": [12.8797, 121.774]},
    "ID": {"name": "印度尼西亚", "coords": [-0.7893, 113.9213]},
    "TW": {"name": "中国台湾", "coords": [23.6978, 120.9605]},
    "JP": {"name": "日本", "coords": [36.2048, 138.2529]},
    "KR": {"name": "韩国", "coords": [35.9078, 127.7669]},
    "IN": {"name": "印度", "coords": [20.5937, 78.9629]},
    "AU": {"name": "澳大利亚", "coords": [-25.2744, 133.7751]},
    "NZ": {"name": "新西兰", "coords": [-40.9006, 174.886]},
    "AE": {"name": "阿联酋", "coords": [23.4241, 53.8478]},
    "SA": {"name": "沙特阿拉伯", "coords": [23.8859, 45.0792]},
    "ZA": {"name": "南非", "coords": [-30.5595, 22.9375]},
    "NG": {"name": "尼日利亚", "coords": [9.082, 8.6753]},
    "KE": {"name": "肯尼亚", "coords": [-0.0236, 37.9062]},
    "EG": {"name": "埃及", "coords": [26.8206, 30.8025]},
}


def _market_site_node(
    country: str,
    tasks: list[str],
    *,
    status: str,
    truth: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    code = str(country or "GLOBAL").strip().upper() or "GLOBAL"
    metadata = MARKET_SITE_METADATA.get(code, {})
    coords = metadata.get("coords")
    node = {
        "country": code,
        "name": str(metadata.get("name") or code),
        "coords": list(coords) if isinstance(coords, list) else None,
        "tasks": [str(item) for item in tasks if str(item).strip()],
        "status": status,
        "truth": truth,
    }
    if isinstance(details, dict):
        node.update(details)
    return node


def _project_evidence_refs(root: Path, project: dict[str, Any]) -> list[str]:
    platforms = {
        str(item.get("platform") or "").strip().lower()
        for item in business_visible_project_tasks(project)
        if isinstance(item, dict)
    }
    candidates: list[str] = []
    if "amazon" in platforms:
        candidates.append("outputs/amazon_10001_operating_state_latest.json")
    if "b2b" in platforms:
        candidates.append("outputs/b2b_10001_master_sales_pipeline_2026-07-11_0506.csv")
    if "creative_video" in platforms:
        candidates.append("data/task_execution_runtime.sqlite3")
    return [reference for reference in candidates if (root / reference).exists()]


def _build_market_map_nodes(
    root: Path,
    projects: list[dict[str, Any]],
    project_rows: list[dict[str, Any]],
    account: dict[str, Any],
) -> list[dict[str, Any]]:
    rows_by_id = {str(item.get("id") or ""): item for item in project_rows}
    buckets: dict[str, dict[str, Any]] = {}

    def bucket_for(country: str) -> dict[str, Any]:
        code = str(country or "GLOBAL").strip().upper() or "GLOBAL"
        return buckets.setdefault(
            code,
            {
                "projects": {},
                "stores": [],
                "channels": [],
                "tasks": [],
                "evidence_refs": set(),
            },
        )

    for project in projects:
        project_id = str(project.get("id") or "")
        project_name = str(project.get("name") or project_id or "项目")
        project_row = rows_by_id.get(project_id, {})
        project_refs = _project_evidence_refs(root, project)
        project_countries: set[str] = set()
        for task in business_visible_project_tasks(project):
            if not isinstance(task, dict):
                continue
            country = str(task.get("country") or task.get("country_site") or "GLOBAL").upper()
            project_countries.add(country)
            bucket = bucket_for(country)
            bucket["tasks"].append(
                {
                    "id": str(task.get("id") or ""),
                    "name": str(task.get("name") or "任务"),
                    "project_id": project_id,
                    "project_name": project_name,
                    "platform": str(task.get("platform") or ""),
                    "status": str(task.get("status") or "待办"),
                    "scope_type": str(task.get("scope_type") or "project_task"),
                    "store_bound": bool(task.get("store_binding_id")),
                }
            )
        for channel in project.get("channels", []):
            if not isinstance(channel, dict):
                continue
            country = str(channel.get("country_site") or "GLOBAL").upper()
            project_countries.add(country)
            bucket = bucket_for(country)
            stores = business_bound_stores(channel.get("stores"))
            if not stores:
                continue
            channel_status = str(channel.get("status") or "planned")
            bucket["channels"].append(
                {
                    "id": str(channel.get("id") or ""),
                    "name": str(channel.get("name") or channel.get("id") or "渠道"),
                    "project_id": project_id,
                    "platform": str(channel.get("platform") or ""),
                    "status": channel_status,
                    "store_count": len(stores),
                    "truth": (
                        "缺后台真实店铺"
                        if channel_status == "needs_platform_store" and not stores
                        else "真实店铺绑定"
                        if stores
                        else "项目渠道配置"
                    ),
                }
            )
            for store in stores:
                bucket["stores"].append(
                    {
                        "name": str(store.get("name") or "店铺"),
                        "project_id": project_id,
                        "project_name": project_name,
                        "platform": str(channel.get("platform") or ""),
                        "status": str(store.get("status") or "configured"),
                        "store_model": str(store.get("store_model") or ""),
                        "ownership": str(store.get("ownership") or ""),
                        "task_count": len(
                            [item for item in store.get("tasks", []) if isinstance(item, dict)]
                        ),
                    }
                )
        for country in project_countries or {"GLOBAL"}:
            bucket = bucket_for(country)
            bucket["evidence_refs"].update(project_refs)
            bucket["projects"][project_id] = {
                "id": project_id,
                "name": project_name,
                "task_count": sum(
                    1
                    for item in bucket["tasks"]
                    if str(item.get("project_id") or "") == project_id
                ),
                "store_count": sum(
                    1
                    for item in bucket["stores"]
                    if str(item.get("project_id") or "") == project_id
                ),
                "evidence_status": "verified" if project_refs else "configured",
                "last_evidence_at": str(project_row.get("last_evidence_at") or ""),
                "href": "/desktop?project=" + project_id,
            }

    nodes: list[dict[str, Any]] = []
    for code, bucket in sorted(buckets.items()):
        projects_for_country = list(bucket["projects"].values())
        stores = list(bucket["stores"])
        channels = list(bucket["channels"])
        tasks = list(bucket["tasks"])
        evidence_refs = sorted(str(item) for item in bucket["evidence_refs"])
        verified_project_count = sum(
            1 for item in projects_for_country if item.get("evidence_status") == "verified"
        )
        operating_store_count = sum(
            1 for item in stores if str(item.get("status") or "") in {"operating", "active"}
        )
        pending_channel_count = sum(
            1 for item in channels if str(item.get("status") or "") == "needs_platform_store"
        )
        status = "active" if verified_project_count or operating_store_count else "planned"
        truth_parts = [
            f"{len(projects_for_country)} 个项目",
            f"{len(stores)} 个真实店铺",
            f"{verified_project_count} 个有可用数据",
        ]
        if pending_channel_count:
            truth_parts.append(f"{pending_channel_count} 个渠道缺真实店铺")
        nodes.append(
            _market_site_node(
                code,
                [str(item.get("name") or "任务") for item in tasks],
                status=status,
                truth=" · ".join(truth_parts),
                details={
                    "aggregates": {
                        "project_count": len(projects_for_country),
                        "task_count": len(tasks),
                        "verified_project_count": verified_project_count,
                        "bound_store_count": len(stores),
                        "operating_store_count": operating_store_count,
                        "pending_channel_count": pending_channel_count,
                    },
                    "projects": projects_for_country,
                    "stores": stores,
                    "channels": channels,
                    "task_details": tasks,
                    "evidence_refs": evidence_refs,
                    "status_rule": "active_requires_verified_project_evidence_or_operating_store",
                },
            )
        )

    return sorted(nodes, key=lambda item: (item.get("country") == "GLOBAL", item.get("country")))


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _provided(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _redacted_value(field: dict[str, Any], value: Any) -> Any:
    if field.get("sensitive") and _provided(value):
        return "已提供安全引用"
    return value


def _amazon_state(root: Path) -> dict[str, Any]:
    return _load_json(root / "outputs" / "amazon_10001_operating_state_latest.json")


def _sales_snapshot(root: Path, task_context: dict[str, Any] | None = None) -> dict[str, Any]:
    if _SKIP_SALES_OUTPUT_SCAN.get():
        return {}
    context = task_context if isinstance(task_context, dict) else {}
    cache = _SALES_SNAPSHOT_REQUEST_CACHE.get()
    cache_key = "|".join(
        (
            str(root.resolve()),
            json.dumps(context, ensure_ascii=False, sort_keys=True, default=str),
        )
    )
    if cache is not None and cache_key in cache:
        return cache[cache_key]
    try:
        from .b2b_sales_runtime import sales_snapshot

        snapshot = sales_snapshot(
            root,
            product_id=str(context.get("product_id") or "10001"),
            task_context=context,
        )
    except (OSError, ValueError):
        snapshot = {}
    if cache is not None:
        cache[cache_key] = snapshot
    return snapshot


def _provider_snapshot(root: Path) -> dict[str, Any]:
    try:
        from .ai_provider_catalog import provider_catalog_snapshot

        return provider_catalog_snapshot(root)
    except (OSError, ValueError):
        return {}


def _path_timestamp(path_value: Any) -> str:
    path = Path(str(path_value or ""))
    if not path.exists():
        return ""
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).astimezone().isoformat(
        timespec="seconds"
    )


def _evidence_source_ledger(root: Path, references: list[str]) -> list[dict[str, Any]]:
    ledger: list[dict[str, Any]] = []
    checked_at = datetime.now(timezone.utc).astimezone()
    for reference in references:
        path = root / reference
        exists = path.exists() and path.is_file()
        source_type = (
            "workspace_configuration"
            if reference.startswith("config/")
            else "local_runtime_audit"
            if reference.startswith("data/")
            else "local_authoritative_evidence"
        )
        as_of = _path_timestamp(path) if exists else ""
        age_seconds: int | None = None
        if as_of:
            try:
                parsed_as_of = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
                age_seconds = max(0, int((checked_at - parsed_as_of).total_seconds()))
            except ValueError:
                age_seconds = None
        if not exists:
            freshness_state = "missing"
            status_label = "未接入"
        elif source_type == "workspace_configuration":
            freshness_state = "configuration_only"
            status_label = "仅配置，不是经营数据"
        elif source_type == "local_runtime_audit":
            freshness_state = (
                "current_local_activity"
                if age_seconds is not None and age_seconds <= LOCAL_RUNTIME_RECENT_SECONDS
                else "stale_local_activity"
            )
            status_label = "本地操作记录" if freshness_state == "current_local_activity" else "较早的本地操作记录"
        else:
            freshness_state = (
                "recent_snapshot"
                if age_seconds is not None and age_seconds <= LOCAL_SNAPSHOT_RECENT_SECONDS
                else "stale_snapshot"
            )
            status_label = "本地快照" if freshness_state == "recent_snapshot" else "历史快照"
        ledger.append(
            {
                "ref": reference,
                "status": "available" if exists else "missing",
                "as_of": as_of,
                "source_type": source_type,
                "freshness_state": freshness_state,
                "age_seconds": age_seconds,
                "updates_automatically": source_type == "local_runtime_audit",
                "status_label": status_label,
            }
        )
    return ledger


def _nonnegative_float(value: object) -> float:
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def _live_store_trend_points(
    path: Path,
    *,
    project_id: str,
    task_id: str,
    store_binding_id: str,
    store_id: str,
    limit: int = 240,
) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-max(1, limit) :]
    except (FileNotFoundError, OSError, UnicodeError):
        return []
    points: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in lines:
        try:
            payload = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        summary = payload.get("order_summary") if isinstance(payload, dict) and isinstance(payload.get("order_summary"), dict) else {}
        captured_at = str(payload.get("captured_at") or "").strip() if isinstance(payload, dict) else ""
        if (
            not captured_at
            or captured_at in seen
            or payload.get("read_only") is not True
            or int(payload.get("external_store_write_actions") or 0) != 0
            or str(payload.get("project_id") or "") != project_id
            or str(payload.get("task_id") or "") != task_id
            or str(payload.get("store_binding_id") or "") != store_binding_id
            or str(payload.get("store_id") or "") != store_id
            or summary.get("data_returned") is not True
            or summary.get("contains_order_ids_or_customer_pii") is not False
        ):
            continue
        try:
            datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
            order_count = max(0, int(summary.get("order_count") or 0))
            gross_sales = _nonnegative_float(summary.get("gross_sales"))
            expected_income = _nonnegative_float(summary.get("expected_income"))
        except (TypeError, ValueError):
            continue
        seen.add(captured_at)
        points.append(
            {
                "captured_at": captured_at,
                "order_count": order_count,
                "gross_sales": gross_sales,
                "expected_income": expected_income,
            }
        )
    return points


def _public_product_link_sales(value: object) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    result: list[dict[str, Any]] = []
    for item in rows[:50]:
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
        try:
            order_count = max(0, int(item.get("order_count") or 0))
            gross_sales = _nonnegative_float(item.get("gross_sales"))
        except (TypeError, ValueError):
            continue
        result.append(
            {
                "url": f"https://{hostname}{parsed.path}",
                "title": str(item.get("title") or "商品链接").strip()[:120],
                "order_count": order_count,
                "gross_sales": gross_sales,
            }
        )
    return result


def _live_store_order_sources(
    root: Path, workspace: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Read only fresh, scope-matched store summaries produced by a live connector."""

    checked_at = datetime.now(timezone.utc).astimezone()
    ledger: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    refresh_tasks: list[dict[str, Any]] = []
    for project in workspace.get("projects", []):
        if not isinstance(project, dict):
            continue
        project_id = str(project.get("id") or "").strip()
        for channel in project.get("channels", []):
            if not isinstance(channel, dict):
                continue
            for store in channel.get("stores", []):
                if not isinstance(store, dict):
                    continue
                platform = str(store.get("platform") or channel.get("platform") or "").strip().lower()
                country_site = str(store.get("country_site") or channel.get("country_site") or "").strip()
                store_binding_id = str(store.get("id") or "").strip()
                store_id = str(store.get("external_id") or store.get("store_id") or "").strip()
                connector_script = str(store.get("store_surface_connector_script") or "").strip()
                try:
                    profile_seq = int(
                        store.get("browser_profile_seq")
                        or store.get("browser_profile_sequence")
                        or 0
                    )
                except (TypeError, ValueError):
                    profile_seq = 0
                if (
                    str(store.get("status") or "") == "connected_read_only"
                    and platform == "shein"
                    and project_id
                    and store_binding_id
                    and store_id
                    and profile_seq > 0
                    and connector_script
                ):
                    for task in store.get("tasks", []):
                        if not isinstance(task, dict):
                            continue
                        task_id = str(task.get("id") or "").strip()
                        if not task_id:
                            continue
                        refresh_tasks.append(
                            {
                                "id": task_id,
                                "task_id": task_id,
                                "project_id": project_id,
                                "platform": platform,
                                "country_site": country_site,
                                "store_binding_id": store_binding_id,
                                "store_id": store_id,
                                "browser_profile_seq": profile_seq,
                                "store_surface_connector_script": connector_script,
                                "background_refresh": True,
                            }
                        )
                        path = (
                            root
                            / "projects"
                            / project_id
                            / "tasks"
                            / task_id
                            / "results"
                            / "shein-order-summary-latest.json"
                        )
                        payload = _load_json(path)
                        summary = payload.get("order_summary") if isinstance(payload.get("order_summary"), dict) else {}
                        if (
                            payload.get("read_only") is not True
                            or int(payload.get("external_store_write_actions") or 0) != 0
                            or str(payload.get("platform") or "").lower() != platform
                            or str(payload.get("project_id") or "") != project_id
                            or str(payload.get("task_id") or "") != task_id
                            or str(payload.get("store_binding_id") or "") != store_binding_id
                            or str(payload.get("store_id") or "") != store_id
                            or summary.get("data_returned") is not True
                            or summary.get("contains_order_ids_or_customer_pii") is not False
                        ):
                            continue
                        captured_at = str(payload.get("captured_at") or "").strip()
                        try:
                            captured = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
                            if captured.tzinfo is None:
                                captured = captured.replace(tzinfo=timezone.utc)
                            age_seconds = max(0, int((checked_at - captured.astimezone()).total_seconds()))
                        except ValueError:
                            continue
                        freshness_state = "live" if age_seconds <= LIVE_STORE_RECENT_SECONDS else "stale_live_read"
                        reference = path.relative_to(root).as_posix()
                        ledger.append(
                            {
                                "ref": reference,
                                "status": "available",
                                "as_of": captured.astimezone().isoformat(timespec="seconds"),
                                "source_type": "external_live_sync",
                                "freshness_state": freshness_state,
                                "age_seconds": age_seconds,
                                "updates_automatically": True,
                                "status_label": "实时店铺读取" if freshness_state == "live" else "店铺读取已过期",
                                "store_id": store_id,
                            }
                        )
                        if freshness_state == "live":
                            history_path = path.with_name("shein-order-summary-history.jsonl")
                            trend_points = _live_store_trend_points(
                                history_path,
                                project_id=project_id,
                                task_id=task_id,
                                store_binding_id=store_binding_id,
                                store_id=store_id,
                            )
                            if not trend_points or trend_points[-1].get("captured_at") != captured_at:
                                trend_points.append(
                                    {
                                        "captured_at": captured_at,
                                        "order_count": int(summary.get("order_count") or 0),
                                        "gross_sales": _nonnegative_float(summary.get("gross_sales")),
                                        "expected_income": _nonnegative_float(summary.get("expected_income")),
                                    }
                                )
                            summaries.append(
                                {
                                    "project_id": project_id,
                                    "task_id": task_id,
                                    "store_binding_id": store_binding_id,
                                    "store_id": store_id,
                                    "platform": platform,
                                    "country_site": country_site,
                                    "captured_at": captured.astimezone().isoformat(timespec="seconds"),
                                    "order_count": int(summary.get("order_count") or 0),
                                    "unit_count": int(summary.get("unit_count") or 0),
                                    "gross_sales": str(summary.get("gross_sales") or "0"),
                                    "expected_income": str(summary.get("expected_income") or "0"),
                                    "window_start": str(summary.get("window_start") or ""),
                                    "window_end": str(summary.get("window_end") or ""),
                                    "product_links": _public_product_link_sales(summary.get("product_links")),
                                    "trend_points": trend_points[-240:],
                                    "external_store_write_actions": 0,
                                }
                            )
    return ledger, summaries, refresh_tasks


def _dashboard_data_truth(source_ledger: list[dict[str, Any]]) -> dict[str, Any]:
    business_sources = [
        item
        for item in source_ledger
        if item.get("source_type") == "local_authoritative_evidence"
        and item.get("status") == "available"
        and str(item.get("as_of") or "")
    ]
    live_sources = [
        item
        for item in source_ledger
        if item.get("source_type") == "external_live_sync"
        and item.get("freshness_state") in {"live", "current"}
    ]
    live_data_available = bool(live_sources)
    business_data_as_of = max(
        (
            str(item.get("as_of") or "")
            for item in (live_sources if live_data_available else business_sources)
        ),
        default="",
    )
    if live_data_available:
        data_status_label = "实时同步"
    elif business_sources and all(
        item.get("freshness_state") == "stale_snapshot" for item in business_sources
    ):
        data_status_label = "历史快照"
    elif business_sources:
        data_status_label = "本地快照"
    else:
        data_status_label = "未接入经营数据"
    return {
        "dashboard_mode": "live_sync" if live_data_available else "local_state",
        "live_data_available": live_data_available,
        "data_status_label": data_status_label,
        "business_data_as_of": business_data_as_of,
        "refresh_behavior": "source_sync" if live_data_available else "page_poll_only",
    }


def company_information_snapshot(root: Path) -> dict[str, Any]:
    schema = _load_json(root / "config" / "company_information_schema.json")
    profile = _load_json(root / "config" / "company_operating_profile.json")
    values = profile.get("verified_values") if isinstance(profile.get("verified_values"), dict) else {}
    fields = schema.get("owner_verified_required") if isinstance(schema.get("owner_verified_required"), list) else []

    rendered_fields: list[dict[str, Any]] = []
    provided_count = 0
    for field in fields:
        if not isinstance(field, dict):
            continue
        field_id = str(field.get("id") or "")
        value = values.get(field_id)
        is_provided = _provided(value)
        provided_count += int(is_provided)
        rendered_fields.append(
            {
                **field,
                "provided": is_provided,
                "value": _redacted_value(field, value),
                "editable_value": "" if field.get("sensitive") else value,
            }
        )

    amazon = _amazon_state(root)
    route = amazon.get("route") if isinstance(amazon.get("route"), dict) else {}
    fulfillment = amazon.get("fulfillment") if isinstance(amazon.get("fulfillment"), dict) else {}
    orders = amazon.get("orders") if isinstance(amazon.get("orders"), dict) else {}
    advertising = amazon.get("advertising") if isinstance(amazon.get("advertising"), dict) else {}
    b2b = _sales_snapshot(root)
    providers = _provider_snapshot(root)
    integrations = integration_hub_snapshot(root)

    system_fields = [
        {
            "id": "store_routes",
            "label": "店铺路线",
            "status": "configured" if route.get("operation_scope_key") else "missing",
            "detail": str(route.get("operation_scope_key") or "待授权"),
        },
        {
            "id": "orders_inventory_settlement",
            "label": "订单 / 库存 / 结算",
            "status": "verified" if orders.get("last_confirmed_at") else "missing",
            "detail": f"Amazon 订单 {int(orders.get('total') or 0)}；结算 API 待接入",
        },
        {
            "id": "advertising_accounts",
            "label": "广告账号",
            "status": "configured" if advertising.get("single_preset") else "missing",
            "detail": "草稿已准备；Ads API、权限和花费门禁未开放",
        },
        {
            "id": "customer_pipeline",
            "label": "客户管线",
            "status": "verified" if b2b.get("authoritative_company_count") else "missing",
            "detail": f"{int(b2b.get('authoritative_company_count') or 0)} 家去重客户",
        },
        {
            "id": "fulfillment_status",
            "label": "履约与物流",
            "status": "verified" if fulfillment.get("competitive_delivery_promise_verified") else "blocked",
            "detail": (
                "美国仓和时效已核验"
                if fulfillment.get("competitive_delivery_promise_verified")
                else "美国仓发货地 / 时效仍未核验"
            ),
        },
        {
            "id": "connector_health",
            "label": "连接器健康",
            "status": "live" if integrations.get("live_count") else "not_connected",
            "detail": (
                f"外部真实连接 {int(integrations.get('live_count') or 0)}；"
                f"本地能力就绪 {int(integrations.get('local_ready_count', integrations.get('available_count')) or 0)}；"
                f"浏览器已连但 API 待接 {int(integrations.get('browser_only_count') or 0)}；"
                f"阻断 {int(integrations.get('blocked_count') or 0)}；"
                f"待授权或建设 {int(integrations.get('pending_count') or 0)}"
            ),
        },
        {
            "id": "ai_models",
            "label": "AI 模型",
            "status": "live" if providers.get("ready_count") else "configured",
            "detail": (
                f"已配置 {int(providers.get('configured_count') or 0)}；"
                f"可用 {int(providers.get('ready_count') or 0)}"
            ),
        },
    ]

    owner_blockers = [item["label"] for item in rendered_fields if not item.get("provided")]

    return {
        "schema_version": 1,
        "updated_at": str(profile.get("updated_at") or ""),
        "owner_required_count": len(rendered_fields),
        "owner_provided_count": provided_count,
        "owner_missing_count": max(0, len(rendered_fields) - provided_count),
        "owner_fields": rendered_fields,
        "owner_blockers": owner_blockers,
        "system_fields": system_fields,
        "system_ready_count": sum(
            1 for item in system_fields if item["status"] in {"verified", "live"}
        ),
        "system_partial_count": sum(
            1 for item in system_fields if item["status"] in {"configured", "blocked", "stale"}
        ),
        "ai_generated_fields": schema.get("ai_generated_draft") or [],
        "rules": schema.get("rules") or [],
    }


def _normalize_profile_value(field: dict[str, Any], value: Any) -> Any:
    value_type = str(field.get("value_type") or "text")
    if value_type == "boolean":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    if value_type == "number":
        if value in {"", None}:
            return ""
        number = float(value)
        if number < 0:
            raise ValueError(f"{field.get('label')}不能小于 0。")
        return int(number) if number.is_integer() else round(number, 4)

    text = str(value or "").strip()
    if len(text) > 300:
        raise ValueError(f"{field.get('label')}过长。")
    if SECRET_ASSIGNMENT.search(text):
        raise ValueError("普通公司资料中不能保存密码、API Key、令牌或私钥。")
    return text


def save_company_verified_values(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    schema = _load_json(root / "config" / "company_information_schema.json")
    fields = {
        str(item.get("id") or ""): item
        for item in schema.get("owner_verified_required", [])
        if isinstance(item, dict) and item.get("id")
    }
    profile_path = root / "config" / "company_operating_profile.json"
    profile = _load_json(profile_path) or {"schema_version": 1, "verified_values": {}}
    current_values = profile.get("verified_values")
    values = dict(current_values) if isinstance(current_values, dict) else {}

    for key, raw_value in payload.items():
        field = fields.get(str(key))
        if field is None:
            continue
        normalized = _normalize_profile_value(field, raw_value)
        if normalized == "":
            values.pop(str(key), None)
        else:
            values[str(key)] = normalized

    profile["schema_version"] = 1
    profile["updated_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    profile["verified_values"] = values
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return company_information_snapshot(root)


def _project_type(project: dict[str, Any]) -> str:
    explicit = str(project.get("project_type") or "").strip().lower()
    if explicit in {"commerce", "b2b", "creative"}:
        return explicit
    platforms = {
        str(item.get("platform") or "").strip().lower()
        for item in business_visible_project_tasks(project)
        if isinstance(item, dict)
    }
    if "b2b" in platforms:
        return "b2b"
    if "creative_video" in platforms:
        return "creative"
    return "commerce"


def _project_schema_fields(
    schema: dict[str, Any], project_type: str
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    common = [
        item
        for item in schema.get("common_required", [])
        if isinstance(item, dict) and item.get("id")
    ]
    types = schema.get("project_types") if isinstance(schema.get("project_types"), dict) else {}
    type_schema = types.get(project_type) if isinstance(types.get(project_type), dict) else {}
    specific = [
        item
        for item in type_schema.get("required", [])
        if isinstance(item, dict) and item.get("id")
    ]
    ai_fields = [str(item) for item in type_schema.get("ai_generated_draft", []) if str(item)]
    optional_settings = [
        str(item) for item in type_schema.get("optional_settings", []) if str(item)
    ]
    return common + specific, ai_fields, optional_settings


def project_information_snapshot(root: Path, project: dict[str, Any]) -> dict[str, Any]:
    project_id = str(project.get("id") or "").strip()
    project_type = _project_type(project)
    schema = _load_json(root / "config" / "project_information_schema.json")
    profiles = _load_json(root / "config" / "project_operating_profiles.json")
    project_profiles = (
        profiles.get("projects") if isinstance(profiles.get("projects"), dict) else {}
    )
    profile = (
        project_profiles.get(project_id)
        if isinstance(project_profiles.get(project_id), dict)
        else {}
    )
    values = profile.get("verified_values") if isinstance(profile.get("verified_values"), dict) else {}
    fields, ai_fields, optional_settings = _project_schema_fields(schema, project_type)

    rendered_fields: list[dict[str, Any]] = []
    provided_count = 0
    for field in fields:
        field_id = str(field.get("id") or "")
        value = values.get(field_id)
        is_provided = _provided(value)
        provided_count += int(is_provided)
        rendered_fields.append(
            {
                **field,
                "provided": is_provided,
                "value": _redacted_value(field, value),
                "editable_value": "" if field.get("sensitive") else value,
            }
        )

    tasks = business_visible_project_tasks(project)
    evidence_status = "missing"
    evidence_detail = "暂无项目级权威运行证据"
    if project_type == "commerce":
        platforms = {str(item.get("platform") or "") for item in tasks}
        if "amazon" in platforms and _amazon_state(root):
            evidence_status = "verified"
            evidence_detail = "Amazon 10001 权威运营状态已接入"
        elif any(str(item.get("status") or "") not in {"待接入", ""} for item in tasks):
            evidence_status = "configured"
            evidence_detail = "任务已配置，但真实店铺/API 证据仍待接入"
    elif project_type == "b2b":
        b2b = _sales_snapshot(root)
        if b2b.get("authoritative_company_count"):
            evidence_status = "verified"
            evidence_detail = f"已读取 {int(b2b.get('authoritative_company_count') or 0)} 家去重客户"
    elif project_type == "creative":
        evidence_status = "configured"
        evidence_detail = "视觉能力已配置；发布和营收必须回写到 Amazon 或 B2B 项目"

    system_fields = [
        {
            "id": "task_configuration",
            "label": "任务配置",
            "status": "configured" if tasks else "missing",
            "detail": f"{len(tasks)} 个任务",
        },
        {
            "id": "authoritative_evidence",
            "label": "权威运行证据",
            "status": evidence_status,
            "detail": evidence_detail,
        },
    ]
    return {
        "schema_version": 1,
        "project_id": project_id,
        "project_type": project_type,
        "updated_at": str(profile.get("updated_at") or ""),
        "owner_required_count": len(rendered_fields),
        "owner_provided_count": provided_count,
        "owner_missing_count": max(0, len(rendered_fields) - provided_count),
        "owner_fields": rendered_fields,
        "owner_blockers": [
            str(item.get("label") or item.get("id") or "项目事实")
            for item in rendered_fields
            if not item.get("provided")
        ],
        "system_fields": system_fields,
        "system_ready_count": sum(
            1 for item in system_fields if item.get("status") in {"verified", "live"}
        ),
        "ai_generated_fields": ai_fields,
        "optional_settings": optional_settings,
        "rules": schema.get("rules") or [],
    }


def save_project_verified_values(
    root: Path, project_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    workspace = _load_json(root / "config" / "workspace_projects.json")
    project = next(
        (
            item
            for item in workspace.get("projects", [])
            if isinstance(item, dict) and str(item.get("id") or "") == project_id
        ),
        None,
    )
    if project is None:
        raise ValueError("项目不存在。")

    schema = _load_json(root / "config" / "project_information_schema.json")
    fields, _ai_fields, _optional_settings = _project_schema_fields(
        schema, _project_type(project)
    )
    field_map = {str(item.get("id") or ""): item for item in fields}
    profile_path = root / "config" / "project_operating_profiles.json"
    profiles = _load_json(profile_path) or {"schema_version": 1, "projects": {}}
    projects = profiles.get("projects") if isinstance(profiles.get("projects"), dict) else {}
    project_profile = (
        dict(projects.get(project_id)) if isinstance(projects.get(project_id), dict) else {}
    )
    current_values = project_profile.get("verified_values")
    values = dict(current_values) if isinstance(current_values, dict) else {}

    for key, raw_value in payload.items():
        field = field_map.get(str(key))
        if field is None:
            continue
        normalized = _normalize_profile_value(field, raw_value)
        if normalized == "":
            values.pop(str(key), None)
        else:
            values[str(key)] = normalized

    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    project_profile["updated_at"] = now
    project_profile["verified_values"] = values
    projects[project_id] = project_profile
    profiles["schema_version"] = 1
    profiles["updated_at"] = now
    profiles["projects"] = projects
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        json.dumps(profiles, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return project_information_snapshot(root, project)


def integration_hub_snapshot(root: Path) -> dict[str, Any]:
    config = _load_json(root / "config" / "integration_hub.json")
    connectors = [item for item in config.get("connectors", []) if isinstance(item, dict)]
    acquisition_config = _load_json(
        root / "config" / "data_acquisition_connectors.json"
    )
    existing_ids = {str(item.get("id") or "") for item in connectors}
    for provider in acquisition_config.get("providers", []):
        if not isinstance(provider, dict):
            continue
        provider_id = str(provider.get("id") or "").strip()
        if not provider_id or provider_id in existing_ids:
            continue
        connectors.append(
            {
                **provider,
                "id": provider_id,
                "kind": "data_acquisition",
                "connection_truth": "not_connected",
            }
        )
        existing_ids.add(provider_id)
    live_statuses = {"live_verified", "externally_verified"}
    local_ready_statuses = {
        "core_available",
        "local_rest_and_stdio_mcp_available",
        "local_control_available_unconnected",
        "local_file_import_available",
    }
    live = [
        item for item in connectors if str(item.get("status") or "") in live_statuses
    ]
    local_ready = [
        item
        for item in connectors
        if str(item.get("status") or "") in local_ready_statuses
    ]
    browser_only = [
        item
        for item in connectors
        if str(item.get("status") or "") == "browser_connected_api_pending"
    ]
    blocked = [
        item
        for item in connectors
        if str(item.get("status") or "").startswith("blocked_")
    ]
    classified_ids = {
        id(item)
        for item in [*live, *local_ready, *browser_only, *blocked]
    }
    pending = [item for item in connectors if id(item) not in classified_ids]
    groups: dict[str, int] = {}
    for item in connectors:
        group = str(item.get("group") or "其他")
        groups[group] = groups.get(group, 0) + 1
    return {
        "connector_count": len(connectors),
        # Compatibility alias: local capability readiness, never an authenticated
        # external account or store connection.
        "available_count": len(local_ready),
        "local_ready_count": len(local_ready),
        "live_count": len(live),
        "browser_only_count": len(browser_only),
        "blocked_count": len(blocked),
        "pending_count": len(pending),
        "groups": groups,
        "connectors": connectors,
        "open_api": config.get("open_api") or {},
    }


def company_dashboard_snapshot(
    root: Path, workspace_config: dict[str, Any] | None = None
) -> dict[str, Any]:
    from .organization_operating import organization_operating_snapshot
    from .task_execution_runtime import business_event_projection

    if isinstance(workspace_config, dict):
        workspace = normalize_workspace_config(workspace_config)
    else:
        # The desktop lets users add project/store tasks at runtime. Reuse the
        # same merged workspace here so the 30-second refresh cannot erase them.
        from .workspace_runtime import load_workspace_config

        workspace = load_workspace_config(root)
    amazon = _amazon_state(root)
    listing = amazon.get("listing") if isinstance(amazon.get("listing"), dict) else {}
    offers = amazon.get("offers") if isinstance(amazon.get("offers"), dict) else {}
    orders = amazon.get("orders") if isinstance(amazon.get("orders"), dict) else {}
    account = amazon.get("account") if isinstance(amazon.get("account"), dict) else {}
    b2b = _sales_snapshot(root)
    providers = _provider_snapshot(root)
    workspace_event_projection = business_event_projection(root, limit=100)
    organization = organization_operating_snapshot(root, workspace)

    projects = [item for item in workspace.get("projects", []) if isinstance(item, dict)]
    project_rows: list[dict[str, Any]] = []
    active_statuses = {"运营中", "进行中", "可使用"}
    for project in projects:
        tasks = business_visible_project_tasks(project)
        channels = [
            item for item in project.get("channels", []) if isinstance(item, dict)
        ]
        store_count = sum(
            len(business_bound_stores(channel.get("stores")))
            for channel in channels
        )
        pending_channel_count = sum(
            1
            for channel in channels
            if business_bound_stores(channel.get("stores"))
            and str(channel.get("status") or "") == "needs_platform_store"
        )
        project_rows.append(
            {
                "id": str(project.get("id") or ""),
                "name": str(project.get("name") or "项目"),
                "task_count": len(tasks),
                "store_count": store_count,
                "pending_channel_count": pending_channel_count,
                "active_count": sum(
                    1 for item in tasks if str(item.get("status") or "") in active_statuses
                ),
                "tasks": tasks,
            }
        )

    single = offers.get("single") if isinstance(offers.get("single"), dict) else {}
    four_pack = offers.get("four_pack") if isinstance(offers.get("four_pack"), dict) else {}
    offer_rows = (single, four_pack)
    fulfillment = amazon.get("fulfillment") if isinstance(amazon.get("fulfillment"), dict) else {}
    gates = amazon.get("gates") if isinstance(amazon.get("gates"), dict) else {}
    for project_row in project_rows:
        platforms = {
            str(task.get("platform") or "")
            for task in project_row.get("tasks", [])
            if isinstance(task, dict)
        }
        if "amazon" in platforms:
            project_row["metrics"] = [
                {"label": "订单", "value": int(orders.get("total") or 0), "unit": "单"},
                {
                    "label": "可购买家族",
                    "value": sum(1 for item in offer_rows if item.get("buyable_via_buying_options")),
                    "unit": "个",
                },
                {
                    "label": "主购买框",
                    "value": sum(1 for item in offer_rows if item.get("has_primary_add_to_cart")),
                    "unit": "个",
                },
                {
                    "label": "美国站",
                    "value": str(account.get("us_store_status") or "unknown"),
                    "unit": "",
                },
            ]
            project_row["blockers"] = [
                item
                for item in [
                    "美国仓发货地和配送时效未核验"
                    if not fulfillment.get("competitive_delivery_promise_verified")
                    else "",
                    "Featured Offer 未获得"
                    if not all(item.get("has_primary_add_to_cart") for item in offer_rows)
                    else "",
                    "广告和优惠尚未解锁：销售权限、银行验证、美国仓配送与主购买框需全部通过"
                    if not gates.get("spend_gate_open")
                    else "",
                ]
                if item
            ]
            project_row["last_evidence_at"] = str(
                orders.get("last_confirmed_at") or amazon.get("updated_at") or ""
            )
        elif "b2b" in platforms:
            equipment_task = next(
                (
                    task for task in project_row.get("tasks", [])
                    if isinstance(task, dict)
                    and str(task.get("sales_scope") or "") == "equipment_cross_sell"
                ),
                None,
            )
            project_b2b = _sales_snapshot(root, equipment_task) if equipment_task else b2b
            if project_b2b.get("sales_scope") == "equipment_cross_sell":
                project_row["metrics"] = [
                    {
                        "label": "共享客户总池",
                        "value": int(project_b2b.get("authoritative_company_count") or 0),
                        "unit": "家",
                    },
                    {
                        "label": "设备信号待复核",
                        "value": int(project_b2b.get("equipment_review_signal_count") or 0),
                        "unit": "家",
                    },
                    {
                        "label": "真实外发",
                        "value": int(project_b2b.get("externally_sent_count") or 0),
                        "unit": "次",
                    },
                    {"label": "真实回复", "value": int(project_b2b.get("reply_count") or 0), "unit": "条"},
                    {
                        "label": "报价资料完整",
                        "value": int(project_b2b.get("quote_ready_count") or 0),
                        "unit": "家",
                    },
                ]
                project_row["blockers"] = list(project_b2b.get("blockers") or [])
                project_row["last_evidence_at"] = _path_timestamp(project_b2b.get("master_path"))
            else:
                project_row["metrics"] = [
                    {
                        "label": "去重客户",
                        "value": int(project_b2b.get("authoritative_company_count") or 0),
                        "unit": "家",
                    },
                    {
                        "label": "待触达",
                        "value": int(project_b2b.get("approved_to_send_count") or 0),
                        "unit": "家",
                    },
                    {
                        "label": "真实外发",
                        "value": int(project_b2b.get("externally_sent_count") or 0),
                        "unit": "次",
                    },
                    {"label": "回复", "value": int(project_b2b.get("reply_count") or 0), "unit": "条"},
                    {
                        "label": "可报价",
                        "value": int(project_b2b.get("quote_ready_count") or 0),
                        "unit": "家",
                    },
                ]
                project_row["blockers"] = [
                    "当前没有真实外发或客户回复证据"
                    if not project_b2b.get("externally_sent_count") and not project_b2b.get("reply_count")
                    else "",
                    "正式报价仍需数量、目的地、成本、运费和付款条件"
                    if not project_b2b.get("quote_ready_count")
                    else "",
                ]
                project_row["blockers"] = [item for item in project_row["blockers"] if item]
                project_row["last_evidence_at"] = _path_timestamp(project_b2b.get("master_path"))
        elif "creative_video" in platforms:
            project_row["metrics"] = [
                {
                    "label": "可用任务",
                    "value": int(project_row.get("active_count") or 0),
                    "unit": "个",
                },
                {
                    "label": "营收归属",
                    "value": "支持层",
                    "unit": "",
                },
            ]
            project_row["blockers"] = ["视觉内容必须绑定 Amazon 或 B2B 的真实商品 / 客户任务"]
            project_row["last_evidence_at"] = ""
        else:
            project_row["metrics"] = [
                {"label": "已授权店铺", "value": 0, "unit": "个"},
                {"label": "待接入任务", "value": int(project_row.get("task_count") or 0), "unit": "个"},
            ]
            project_row["blockers"] = ["没有真实店铺授权，暂不生成运营数字"]
            project_row["last_evidence_at"] = ""
        project_config = next(
            (
                item
                for item in projects
                if str(item.get("id") or "") == str(project_row.get("id") or "")
            ),
            {},
        )
        project_row["evidence_refs"] = _project_evidence_refs(root, project_config)
        project_events = business_event_projection(
            root,
            project_id=str(project_row.get("id") or ""),
            limit=30,
        )
        project_row["event_counts"] = project_events.get("counts") or {}
        project_row["recent_events"] = project_events.get("events") or []
        project_row["event_projection_source"] = str(
            project_events.get("source") or ""
        )
        project_information = project_information_snapshot(root, project_config)
        project_row["information"] = project_information
        missing_count = int(project_information.get("owner_missing_count") or 0)
        if missing_count:
            project_row.setdefault("blockers", []).append(
                f"项目必填资料仍缺 {missing_count} 项"
            )
    metrics = [
        {
            "label": "Amazon 订单",
            "value": int(orders.get("total") or 0),
            "unit": "单",
            "truth": "权威店铺状态",
        },
        {
            "label": "可购买家族",
            "value": sum(1 for item in offer_rows if item.get("buyable_via_buying_options")),
            "unit": "个",
            "truth": "Buying Options",
        },
        {
            "label": "主购买框",
            "value": sum(1 for item in offer_rows if item.get("has_primary_add_to_cart")),
            "unit": "个",
            "truth": "Featured Offer",
        },
        {
            "label": "B2B 去重客户",
            "value": int(b2b.get("authoritative_company_count") or 0),
            "unit": "家",
            "truth": "权威客户池",
        },
        {
            "label": "已批准待触达",
            "value": int(b2b.get("approved_to_send_count") or 0),
            "unit": "家",
            "truth": "负责人队列",
        },
        {
            "label": "真实外发 / 回复",
            "value": (
                f"{int(b2b.get('externally_sent_count') or 0)}/"
                f"{int(b2b.get('reply_count') or 0)}"
            ),
            "unit": "",
            "truth": "本地记录",
        },
        {
            "label": "已验证 AI 模型",
            "value": int(providers.get("ready_count") or 0),
            "unit": "个",
            "truth": "本机真实调用",
        },
        {
            "label": "项目 / 任务",
            "value": f"{len(projects)}/{sum(item['task_count'] for item in project_rows)}",
            "unit": "",
            "truth": "工作区配置",
        },
    ]

    map_nodes = _build_market_map_nodes(root, projects, project_rows, account)
    source_ledger = _evidence_source_ledger(root, list(REALTIME_DASHBOARD_EVIDENCE_REFS))
    live_source_ledger, live_store_summaries, live_store_tasks = _live_store_order_sources(
        root, workspace
    )
    source_ledger.extend(live_source_ledger)
    data_truth = _dashboard_data_truth(source_ledger)

    return {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        **data_truth,
        "source_ledger": source_ledger,
        "live_store_summaries": live_store_summaries,
        "live_store_tasks": live_store_tasks,
        "metrics": metrics,
        "projects": project_rows,
        "map_nodes": map_nodes,
        "event_projection": workspace_event_projection,
        "organization": organization,
        "information": company_information_snapshot(root),
        "integrations": integration_hub_snapshot(root),
        "amazon": {
            "single_parent_asin": str(listing.get("single_parent_asin") or ""),
            "four_pack_parent_asin": str(listing.get("four_pack_parent_asin") or ""),
            "store_status": str(account.get("us_store_status") or "unknown"),
            "featured_offer_blocked": not bool(
                single.get("has_primary_add_to_cart")
                and four_pack.get("has_primary_add_to_cart")
            ),
        },
    }


def realtime_dashboard_api_snapshot(root: Path) -> dict[str, Any]:
    from .workspace_runtime import load_workspace_config

    workspace = load_workspace_config(root)
    snapshot = company_dashboard_snapshot(root, workspace)
    information = snapshot.get("information") if isinstance(snapshot.get("information"), dict) else {}
    integrations = snapshot.get("integrations") if isinstance(snapshot.get("integrations"), dict) else {}
    event_projection = (
        snapshot.get("event_projection")
        if isinstance(snapshot.get("event_projection"), dict)
        else {}
    )
    organization = (
        snapshot.get("organization")
        if isinstance(snapshot.get("organization"), dict)
        else {}
    )

    def safe_event(event: dict[str, Any]) -> dict[str, Any]:
        return {
            "event_id": str(event.get("event_id") or ""),
            "kind": str(event.get("kind") or ""),
            "project_id": str(event.get("project_id") or ""),
            "task_id": str(event.get("task_id") or ""),
            "conversation_id": str(event.get("conversation_id") or ""),
            "run_id": str(event.get("run_id") or ""),
            "statement": str(event.get("statement") or ""),
            "status": str(event.get("status") or ""),
            "created_at": str(event.get("created_at") or ""),
            "source_refs": [
                str(item) for item in event.get("source_refs", []) if str(item)
            ],
            "business_object_refs": event.get("business_object_refs") or [],
        }
    source_ledger = (
        snapshot.get("source_ledger")
        if isinstance(snapshot.get("source_ledger"), list)
        else _evidence_source_ledger(root, list(REALTIME_DASHBOARD_EVIDENCE_REFS))
    )
    data_truth = _dashboard_data_truth(source_ledger)
    available_refs = [
        str(item.get("ref") or "")
        for item in source_ledger
        if item.get("status") == "available"
    ]
    safe_projects: list[dict[str, Any]] = []
    for project in snapshot.get("projects", []):
        if not isinstance(project, dict):
            continue
        safe_projects.append(
            {
                "id": str(project.get("id") or ""),
                "name": str(project.get("name") or "项目"),
                "task_count": int(project.get("task_count") or 0),
                "store_count": int(project.get("store_count") or 0),
                "pending_channel_count": int(project.get("pending_channel_count") or 0),
                "active_count": int(project.get("active_count") or 0),
                "metrics": project.get("metrics") or [],
                "blockers": project.get("blockers") or [],
                "last_evidence_at": str(project.get("last_evidence_at") or ""),
                "evidence_refs": [
                    str(item) for item in project.get("evidence_refs", []) if str(item)
                ],
                "event_counts": project.get("event_counts") or {},
                "recent_events": [
                    safe_event(event)
                    for event in project.get("recent_events", [])
                    if isinstance(event, dict)
                ],
                "event_projection_source": str(
                    project.get("event_projection_source") or ""
                ),
                "information": {
                    "project_type": str(
                        (project.get("information") or {}).get("project_type") or ""
                    ),
                    "owner_required_count": int(
                        (project.get("information") or {}).get("owner_required_count") or 0
                    ),
                    "owner_provided_count": int(
                        (project.get("information") or {}).get("owner_provided_count") or 0
                    ),
                    "owner_missing_count": int(
                        (project.get("information") or {}).get("owner_missing_count") or 0
                    ),
                    "system_fields": (project.get("information") or {}).get("system_fields") or [],
                    "ai_generated_fields": (
                        project.get("information") or {}
                    ).get("ai_generated_fields") or [],
                    "optional_settings": (
                        project.get("information") or {}
                    ).get("optional_settings") or [],
                },
                "tasks": [
                    {
                        "id": str(task.get("id") or ""),
                        "name": str(task.get("name") or "任务"),
                        "subtitle": str(task.get("subtitle") or ""),
                        "status": str(task.get("status") or "待办"),
                        "platform": str(task.get("platform") or ""),
                        "country": str(task.get("country") or "GLOBAL"),
                    }
                    for task in project.get("tasks", [])
                    if isinstance(task, dict)
                ],
            }
        )
    api_source_ledger = source_ledger
    api_refs = available_refs
    api_metrics = snapshot.get("metrics") or []
    api_projects = safe_projects
    api_map_nodes = snapshot.get("map_nodes") or []
    live_summaries = [
        item
        for item in snapshot.get("live_store_summaries", [])
        if isinstance(item, dict)
    ]
    if data_truth.get("live_data_available") and live_summaries:
        live_store_ids = {str(item.get("store_id") or "") for item in live_summaries}
        live_task_ids = {str(item.get("task_id") or "") for item in live_summaries}
        live_project_ids = {str(item.get("project_id") or "") for item in live_summaries}
        live_captured_by_project = {
            project_id: max(
                (
                    str(item.get("captured_at") or "")
                    for item in live_summaries
                    if str(item.get("project_id") or "") == project_id
                ),
                default="",
            )
            for project_id in live_project_ids
        }
        live_nodes: list[dict[str, Any]] = []
        for raw_node in api_map_nodes:
            if not isinstance(raw_node, dict):
                continue
            stores = [
                dict(item)
                for item in raw_node.get("stores", [])
                if isinstance(item, dict)
                and any(
                    store_id and store_id in str(item.get("name") or "")
                    for store_id in live_store_ids
                )
            ]
            if not stores:
                continue
            task_details = [
                dict(item)
                for item in raw_node.get("task_details", [])
                if isinstance(item, dict)
                and str(item.get("id") or "") in live_task_ids
            ]
            projects = [
                {
                    "id": str(item.get("id") or ""),
                    "name": str(item.get("name") or "项目"),
                    "task_count": sum(
                        1
                        for summary in live_summaries
                        if str(summary.get("project_id") or "")
                        == str(item.get("id") or "")
                    ),
                    "store_count": sum(
                        1
                        for summary in live_summaries
                        if str(summary.get("project_id") or "")
                        == str(item.get("id") or "")
                    ),
                    "evidence_status": "live",
                    "last_evidence_at": live_captured_by_project.get(
                        str(item.get("id") or ""), ""
                    ),
                    "href": str(item.get("href") or ""),
                }
                for item in raw_node.get("projects", [])
                if isinstance(item, dict)
                and str(item.get("id") or "") in live_project_ids
            ]
            node = dict(raw_node)
            node.update(
                {
                    "tasks": [str(item.get("name") or "") for item in task_details],
                    "truth": f"{len(stores)} 家实时店铺",
                    "aggregates": {
                        "project_count": len(projects),
                        "task_count": len(task_details),
                        "verified_project_count": len(projects),
                        "bound_store_count": len(stores),
                        "operating_store_count": len(stores),
                        "pending_channel_count": 0,
                    },
                    "projects": projects,
                    "stores": stores,
                    "channels": [
                        dict(item)
                        for item in raw_node.get("channels", [])
                        if isinstance(item, dict)
                        and str(item.get("platform") or "").lower() == "shein"
                    ],
                    "task_details": task_details,
                    "evidence_refs": [],
                }
            )
            live_nodes.append(node)
        api_map_nodes = live_nodes
        api_metrics = []
        api_projects = [
            item for item in safe_projects if str(item.get("id") or "") in live_project_ids
        ]
        api_source_ledger = [
            item
            for item in source_ledger
            if item.get("source_type") == "external_live_sync"
            and item.get("freshness_state") in {"live", "current"}
        ]
        api_refs = [str(item.get("ref") or "") for item in api_source_ledger]
    return {
        "schema_version": 1,
        "workspace_id": str(workspace.get("workspace_id") or "teelab-global-commerce"),
        "scope": "workspace_read_only",
        "data_status": (
            "mixed_verified_and_configured"
            if any(
                str(item.get("status") or "") in {"planned", "account_only"}
                for item in api_map_nodes
                if isinstance(item, dict)
            )
            else "verified_snapshot"
        ),
        "as_of": "",
        "freshness_seconds": None,
        "freshness_policy": "per_source_ledger",
        "source_id": "teelab-local-authoritative-state",
        "source_type": "mixed_local_authoritative_and_configuration",
        "evidence_refs": api_refs,
        "source_ledger": api_source_ledger,
        "generated_at": str(snapshot.get("generated_at") or ""),
        **data_truth,
        "live_store_summaries": live_summaries if data_truth.get("live_data_available") else [],
        "live_store_tasks": (
            snapshot.get("live_store_tasks", [])
            if data_truth.get("live_data_available")
            and isinstance(snapshot.get("live_store_tasks"), list)
            else []
        ),
        "metrics": api_metrics,
        "projects": api_projects,
        "map_nodes": api_map_nodes,
        "event_projection": {
            "schema_version": int(event_projection.get("schema_version") or 1),
            "source": str(event_projection.get("source") or ""),
            "counts": event_projection.get("counts") or {},
            "total": int(event_projection.get("total") or 0),
            "latest_event_at": str(event_projection.get("latest_event_at") or ""),
            "events": [
                safe_event(event)
                for event in event_projection.get("events", [])
                if isinstance(event, dict)
            ],
        },
        "organization": {
            "schema_version": int(organization.get("schema_version") or 1),
            "organization_name": str(organization.get("organization_name") or ""),
            "hierarchy": organization.get("hierarchy") or [],
            "event_projection_source": str(
                organization.get("event_projection_source") or ""
            ),
            "business_group_count": int(
                organization.get("business_group_count") or 0
            ),
            "department_count": int(organization.get("department_count") or 0),
            "shared_service_count": int(
                organization.get("shared_service_count") or 0
            ),
            "active_member_count": int(organization.get("active_member_count") or 0),
            "management_event_count": int(
                organization.get("management_event_count") or 0
            ),
            "agent_handoff_count": int(organization.get("agent_handoff_count") or 0),
            "open_agent_handoff_count": int(
                organization.get("open_agent_handoff_count") or 0
            ),
            "agent_handoffs": organization.get("agent_handoffs") or [],
            "known_agents": organization.get("known_agents") or [],
            "missing_management_roles": organization.get("missing_management_roles") or [],
            "business_groups": organization.get("business_groups") or [],
            "shared_services": organization.get("shared_services") or [],
            "external_action_count": 0,
        },
        "information": {
            "owner_required_count": int(information.get("owner_required_count") or 0),
            "owner_provided_count": int(information.get("owner_provided_count") or 0),
            "owner_missing_count": int(information.get("owner_missing_count") or 0),
            "system_fields": information.get("system_fields") or [],
        },
        "integrations": {
            "connector_count": int(integrations.get("connector_count") or 0),
            "available_count": int(integrations.get("available_count") or 0),
            "local_ready_count": int(
                integrations.get("local_ready_count", integrations.get("available_count")) or 0
            ),
            "live_count": int(integrations.get("live_count") or 0),
            "browser_only_count": int(integrations.get("browser_only_count") or 0),
            "blocked_count": int(integrations.get("blocked_count") or 0),
            "pending_count": int(integrations.get("pending_count") or 0),
            "groups": integrations.get("groups") or {},
        },
    }


def project_realtime_api_snapshot(root: Path, project_id: str) -> dict[str, Any] | None:
    dashboard = realtime_dashboard_api_snapshot(root)
    project = next(
        (item for item in dashboard.get("projects", []) if item.get("id") == project_id),
        None,
    )
    if not project:
        return None
    return {
        "schema_version": dashboard["schema_version"],
        "workspace_id": dashboard["workspace_id"],
        "project_id": project_id,
        "scope": "project_read_only",
        "data_status": "verified_snapshot" if project.get("evidence_refs") else "configured",
        "as_of": str(project.get("last_evidence_at") or dashboard.get("as_of") or ""),
        "freshness_seconds": None,
        "freshness_policy": "per_source_ledger",
        "source_id": dashboard["source_id"],
        "source_type": dashboard["source_type"],
        "evidence_refs": project.get("evidence_refs") or [],
        "source_ledger": [
            item
            for item in dashboard.get("source_ledger", [])
            if item.get("ref") in set(project.get("evidence_refs") or [])
        ],
        "project": project,
    }


_company_dashboard_snapshot_uncached = company_dashboard_snapshot


def company_dashboard_snapshot(
    root: Path, workspace_config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build one company snapshot with request-local derived-data reuse."""

    existing_cache = _SALES_SNAPSHOT_REQUEST_CACHE.get()
    if existing_cache is not None:
        return _company_dashboard_snapshot_uncached(root, workspace_config)
    token = _SALES_SNAPSHOT_REQUEST_CACHE.set({})
    try:
        return _company_dashboard_snapshot_uncached(root, workspace_config)
    finally:
        _SALES_SNAPSHOT_REQUEST_CACHE.reset(token)
