from __future__ import annotations

import json
import socket
import threading
import time
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse

from .scoring import score_record
from .storage import append_record
from .types import IntakeRecord


# Building a POD-admin snapshot probes a local admin server over the network
# (detect_pod_base_url tries several URLs). When that server is not running the
# probes block ~7s on connection timeouts. Several status pages (/workflow,
# /solo, /pod, /pod-admin) build this snapshot on every render, so we cache the
# read-only (persist=False) result briefly to avoid re-probing on each load.
_POD_SNAPSHOT_TTL_SECONDS = 60.0
_POD_SNAPSHOT_LOCK = threading.Lock()
_POD_SNAPSHOT_CACHE: dict[str, tuple[float, "PodAdminSnapshot"]] = {}


POD_CONFIG = Path("config") / "pod_admin.json"


@dataclass(slots=True)
class PodAdminConfig:
    enabled: bool
    platform_name: str
    project_path: Path | None
    preferred_base_url: str
    candidate_base_urls: list[str]
    admin_path: str
    admin_finance_path: str
    factory_path: str
    designer_path: str
    channel_analytics_path: str
    safe_mode: bool
    notes: str


@dataclass(slots=True)
class PodAdminSnapshot:
    fields: dict[str, Any]
    status: dict[str, Any]


def load_pod_admin_config(root: Path) -> PodAdminConfig:
    path = root / POD_CONFIG
    if not path.exists():
        discovered_path = discover_pod_project_path()
        return PodAdminConfig(
            enabled=False,
            platform_name="POD Platform",
            project_path=discovered_path,
            preferred_base_url="",
            candidate_base_urls=[],
            admin_path="/admin.html",
            admin_finance_path="/admin-finance.html",
            factory_path="/factory.html",
            designer_path="/studio.html",
            channel_analytics_path="/api/admin/channel-analytics?channel=all&days=30",
            safe_mode=True,
            notes="No POD admin config found.",
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    project_path = str(payload.get("project_path") or "").strip()
    project_path_obj = Path(project_path) if project_path else None
    if project_path_obj and not project_path_obj.exists():
        project_path_obj = discover_pod_project_path() or project_path_obj
    elif not project_path_obj:
        project_path_obj = discover_pod_project_path()
    return PodAdminConfig(
        enabled=bool(payload.get("enabled", False)),
        platform_name=str(payload.get("platform_name") or "POD Platform"),
        project_path=project_path_obj,
        preferred_base_url=str(payload.get("preferred_base_url") or "").rstrip("/"),
        candidate_base_urls=[str(item).rstrip("/") for item in payload.get("candidate_base_urls", []) if str(item).strip()],
        admin_path=str(payload.get("admin_path") or "/admin.html"),
        admin_finance_path=str(payload.get("admin_finance_path") or "/admin-finance.html"),
        factory_path=str(payload.get("factory_path") or "/factory.html"),
        designer_path=str(payload.get("designer_path") or "/studio.html"),
        channel_analytics_path=str(payload.get("channel_analytics_path") or "/api/admin/channel-analytics?channel=all&days=30"),
        safe_mode=bool(payload.get("safe_mode", True)),
        notes=str(payload.get("notes") or ""),
    )


def discover_pod_project_path() -> Path | None:
    search_roots = [Path.home() / "Desktop", Path.home() / "Documents"]
    for search_root in search_roots:
        if not search_root.exists():
            continue
        try:
            package_files = search_root.rglob("package.json")
            for package_file in package_files:
                try:
                    text = package_file.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if "pod-platform" in text or "POD T-shirt platform" in text or "TeeLab" in text:
                    return package_file.parent
        except OSError:
            continue
    return None


def build_pod_admin_snapshot(root: Path, *, persist: bool = True) -> tuple[PodAdminSnapshot, IntakeRecord | None]:
    cache_key = str(root.resolve())
    if not persist:
        with _POD_SNAPSHOT_LOCK:
            cached = _POD_SNAPSHOT_CACHE.get(cache_key)
            if cached is not None and (time.monotonic() - cached[0]) < _POD_SNAPSHOT_TTL_SECONDS:
                return cached[1], None
    config = load_pod_admin_config(root)
    status: dict[str, Any] = {
        "enabled": config.enabled,
        "safe_mode": config.safe_mode,
        "project_path": str(config.project_path or ""),
    }
    base_url = detect_pod_base_url(config)
    status["base_url"] = base_url
    page_status = fetch_portal_status(config, base_url) if base_url else {}
    db_summary = read_pod_db_summary(config)
    channel_analytics = fetch_channel_analytics(config, base_url) if base_url else default_channel_analytics_fields("", "missing_base_url")
    fields: dict[str, Any] = {
        "platform_name": config.platform_name,
        "project_path": str(config.project_path or ""),
        "base_url": base_url,
        "admin_url": urljoin(base_url + "/", config.admin_path.lstrip("/")) if base_url else "",
        "admin_finance_url": urljoin(base_url + "/", config.admin_finance_path.lstrip("/")) if base_url else "",
        "factory_url": urljoin(base_url + "/", config.factory_path.lstrip("/")) if base_url else "",
        "designer_url": urljoin(base_url + "/", config.designer_path.lstrip("/")) if base_url else "",
        "safe_mode": config.safe_mode,
        "portal_status": page_status,
        **db_summary,
        **channel_analytics,
    }
    fields["risk_summary"] = build_risk_summary(fields)
    fields["recommended_actions"] = build_recommended_actions(fields)
    snapshot = PodAdminSnapshot(fields=fields, status=status)
    with _POD_SNAPSHOT_LOCK:
        _POD_SNAPSHOT_CACHE[cache_key] = (time.monotonic(), snapshot)
    if not persist:
        return snapshot, None
    score, notes = score_record("pod_admin_snapshot", fields)
    record = IntakeRecord(
        record_type="pod_admin_snapshot",
        fields=fields,
        raw_text=json.dumps(
            {
                "platform_name": config.platform_name,
                "base_url": base_url,
                "project_path": str(config.project_path or ""),
                "date": date.today().isoformat(),
            },
            ensure_ascii=False,
        ),
        source="pod_admin_connector",
        score=score,
        director_notes=notes,
        metadata={"safe_mode": config.safe_mode, "connector": "pod_admin"},
    )
    append_record(root, record)
    return snapshot, record


def detect_pod_base_url(config: PodAdminConfig) -> str:
    candidates = []
    if config.preferred_base_url:
        candidates.append(config.preferred_base_url)
    candidates.extend(item for item in config.candidate_base_urls if item not in candidates)
    for base_url in candidates:
        if can_read_url(urljoin(base_url + "/", config.admin_path.lstrip("/"))):
            return base_url
    return ""


def can_read_url(url: str) -> bool:
    return bool(probe_url(url).get("ok"))


def probe_url(url: str) -> dict[str, Any]:
    socket_probe = probe_url_port(url)
    if socket_probe.get("ok"):
        return socket_probe
    if socket_probe.get("refused"):
        # The port actively refused the connection (nothing is listening), so an
        # HTTP HEAD/GET to the same host:port cannot succeed and would only burn
        # ~3s of timeouts per candidate. Skip straight to "not reachable".
        return socket_probe
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "AI-Ecommerce-Director/0.1"}, method="HEAD")
        with urllib.request.urlopen(request, timeout=1.5) as response:
            return {"ok": 200 <= response.status < 400, "status": response.status}
    except Exception as head_exc:  # noqa: BLE001 - fallback for servers without HEAD.
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "AI-Ecommerce-Director/0.1"})
            with urllib.request.urlopen(request, timeout=1.5) as response:
                return {"ok": 200 <= response.status < 400, "status": response.status}
        except Exception as get_exc:  # noqa: BLE001 - diagnostic only.
            return {"ok": False, "error": str(get_exc or head_exc)}


def probe_url_port(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return {"ok": False, "error": "missing host"}
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return {"ok": True, "status": "port_open"}
    except ConnectionRefusedError as exc:
        return {"ok": False, "refused": True, "error": str(exc)}
    except OSError as exc:
        # Timeout / unreachable / filtered: inconclusive, let the HTTP probe try.
        return {"ok": False, "refused": False, "error": str(exc)}


def fetch_portal_status(config: PodAdminConfig, base_url: str) -> dict[str, Any]:
    paths = {
        "admin": config.admin_path,
        "admin_finance": config.admin_finance_path,
        "factory": config.factory_path,
        "designer": config.designer_path,
    }
    status: dict[str, Any] = {}
    for name, path in paths.items():
        url = urljoin(base_url + "/", path.lstrip("/"))
        probe = probe_url(url)
        status[name] = {
            "url": url,
            "ok": bool(probe.get("ok")),
            "status": probe.get("status", ""),
            "title": "",
            "error": probe.get("error", ""),
        }
    return status


def extract_title(html: str) -> str:
    lower = html.lower()
    start = lower.find("<title>")
    end = lower.find("</title>")
    if start == -1 or end == -1 or end <= start:
        return ""
    return html[start + len("<title>"):end].strip()


def read_pod_db_summary(config: PodAdminConfig) -> dict[str, Any]:
    if not config.project_path:
        return {"db_status": "missing_project_path"}
    db_path = config.project_path / "data" / "db.json"
    if not db_path.exists():
        return {"db_status": "missing_db", "db_path": str(db_path)}
    try:
        data = json.loads(db_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001 - snapshot should still render.
        return {"db_status": "read_error", "db_path": str(db_path), "db_error": str(exc)}
    users = list_value(data, "users")
    factories = list_value(data, "factories")
    blanks = list_value(data, "blanks")
    designs = list_value(data, "designs")
    orders = list_value(data, "orders")
    print_jobs = list_value(data, "printJobs")
    aftersales = list_value(data, "aftersales")
    activity_enrollments = list_value(data, "activityEnrollments")
    platform_stores = list_value(data, "platformStores")
    reviews = list_value(data, "reviews")
    comments = list_value(data, "comments")
    posts = list_value(data, "posts")
    business_leads = list_value(data, "businessLeads")
    activities = list_value(data, "activities")
    settings = data.get("settings") if isinstance(data.get("settings"), dict) else {}
    channel_metrics = settings.get("channelMetrics") if isinstance(settings.get("channelMetrics"), dict) else {}
    return {
        "db_status": "ok",
        "db_path": str(db_path),
        "user_count": len(users),
        "admin_count": count_where(users, role="admin"),
        "designer_count": count_where(users, role="designer"),
        "factory_user_count": count_where(users, role="factory"),
        "customer_count": count_where(users, role="customer"),
        "factory_count": len(factories),
        "active_factory_count": count_where(factories, status="active"),
        "blank_count": len(blanks),
        "active_blank_count": count_active(blanks),
        "design_count": len(designs),
        "listed_design_count": count_where(designs, status="listed"),
        "pending_design_count": count_status_contains(designs, ["pending", "review", "审核"]),
        "order_count": len(orders),
        "print_job_count": len(print_jobs),
        "pending_print_job_count": count_status_contains(print_jobs, ["pending", "待确认", "pending_print"]),
        "printing_job_count": count_status_contains(print_jobs, ["printing", "生产"]),
        "shipped_job_count": count_status_contains(print_jobs, ["shipped", "发货"]),
        "exception_job_count": count_status_contains(print_jobs, ["exception", "异常", "rejected", "退回"]),
        "aftersale_count": len(aftersales),
        "activity_enrollment_count": len(activity_enrollments),
        "review_count": len(reviews),
        "community_post_count": len(posts),
        "community_comment_count": len(comments),
        "business_lead_count": len(business_leads),
        "platform_store_count": len(platform_stores),
        "activity_count": len(activities),
        "platform_ops_opt_in_count": count_platform_ops_opt_in(designs),
        "platform_ops_pending_count": count_platform_ops_status(designs, ["pending_review", "pending"]),
        "platform_ops_below_target_count": count_platform_ops_status(designs, ["below_target"]),
        "low_stock_sku_count": low_stock_sku_count(factories),
        "configured_channel_metric_count": len(channel_metrics),
        "settings_keys": sorted(str(key) for key in settings.keys()),
    }


def fetch_channel_analytics(config: PodAdminConfig, base_url: str) -> dict[str, Any]:
    url = urljoin(base_url + "/", config.channel_analytics_path.lstrip("/"))
    fallback = default_channel_analytics_fields(url, "not_collected")
    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "AI-Ecommerce-Director/0.1",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=1.2) as response:
            payload = json.loads(response.read(500_000).decode("utf-8", errors="replace"))
    except HTTPError as exc:
        status = "requires_admin_session" if exc.code in {401, 403} else f"http_{exc.code}"
        return {**fallback, "channel_analytics_status": status, "channel_analytics_http_status": exc.code}
    except Exception as exc:  # noqa: BLE001 - optional read-only endpoint.
        return {**fallback, "channel_analytics_status": "unavailable", "channel_analytics_error": str(exc)}
    if not isinstance(payload, dict):
        return {**fallback, "channel_analytics_status": "invalid_payload"}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    channels = payload.get("channels") if isinstance(payload.get("channels"), list) else []
    trend = payload.get("trend") if isinstance(payload.get("trend"), list) else []
    top_products = payload.get("topProducts") if isinstance(payload.get("topProducts"), list) else []
    return {
        **fallback,
        "channel_analytics_status": "ok",
        "channel_selected": payload.get("selectedChannel") or "all",
        "channel_days": payload.get("days") or 30,
        "channel_summary": compact_channel_summary(summary),
        "channel_count": len(channels),
        "channel_connected_count": count_bool(channels, "connected"),
        "channel_enabled_count": count_bool(channels, "enabled"),
        "channel_names": [str(item.get("name") or item.get("id") or "") for item in channels if isinstance(item, dict)][:20],
        "channel_trend_days": len(trend),
        "channel_top_product_count": len(top_products),
        "channel_top_products": compact_top_products(top_products),
        "channel_pending_listing_count": int(summary.get("pendingListings") or 0),
        "channel_pending_shipment_count": int(summary.get("pendingShipments") or 0),
        "channel_sales": float(summary.get("sales") or 0),
        "channel_orders": int(summary.get("orders") or 0),
        "channel_units": int(summary.get("units") or 0),
        "channel_roas": float(summary.get("roas") or 0),
        "channel_conversion_rate": float(summary.get("conversionRate") or 0),
    }


def default_channel_analytics_fields(url: str, status: str) -> dict[str, Any]:
    return {
        "channel_analytics_url": url,
        "channel_analytics_status": status,
        "supported_channels": supported_pod_channels(),
        "supported_channel_count": len(supported_pod_channels()),
        "channel_count": 0,
        "channel_connected_count": 0,
        "channel_enabled_count": 0,
        "channel_trend_days": 0,
        "channel_top_product_count": 0,
        "channel_pending_listing_count": 0,
        "channel_pending_shipment_count": 0,
        "channel_sales": 0,
        "channel_orders": 0,
        "channel_units": 0,
        "channel_roas": 0,
        "channel_conversion_rate": 0,
    }


def list_value(data: dict[str, Any], key: str) -> list[Any]:
    value = data.get(key)
    return value if isinstance(value, list) else []


def count_where(items: list[Any], **expected: str) -> int:
    count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        if all(str(item.get(key) or "").lower() == value.lower() for key, value in expected.items()):
            count += 1
    return count


def count_active(items: list[Any]) -> int:
    count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "active").lower()
        if status in {"active", "listed", "enabled", "on"}:
            count += 1
    return count


def count_status_contains(items: list[Any], signals: list[str]) -> int:
    count = 0
    lowered_signals = [signal.lower() for signal in signals]
    for item in items:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or item.get("reviewStatus") or item.get("state") or "").lower()
        if any(signal in status for signal in lowered_signals):
            count += 1
    return count


def count_platform_ops_opt_in(designs: list[Any]) -> int:
    count = 0
    for design in designs:
        if not isinstance(design, dict):
            continue
        platform_ops = design.get("platformOps")
        if isinstance(platform_ops, dict) and platform_ops.get("optedIn"):
            count += 1
    return count


def count_platform_ops_status(designs: list[Any], statuses: list[str]) -> int:
    count = 0
    accepted = {status.lower() for status in statuses}
    for design in designs:
        if not isinstance(design, dict):
            continue
        platform_ops = design.get("platformOps")
        if not isinstance(platform_ops, dict) or not platform_ops.get("optedIn"):
            continue
        status = str(platform_ops.get("status") or "").lower()
        if status in accepted:
            count += 1
    return count


def count_bool(items: list[Any], key: str) -> int:
    return sum(1 for item in items if isinstance(item, dict) and bool(item.get(key)))


def supported_pod_channels() -> list[str]:
    return [
        "ownsite",
        "tiktok",
        "shein",
        "shopee",
        "lazada",
        "amazon",
        "etsy",
        "walmart",
        "ebay",
        "shopify",
        "woocommerce",
        "facebook",
        "instagram",
    ]


def compact_channel_summary(summary: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "orders",
        "units",
        "sales",
        "listedProducts",
        "pendingListings",
        "syncedListings",
        "pendingShipments",
        "syncedShipments",
        "aftersales",
        "visits",
        "clicks",
        "adSpend",
        "conversionRate",
        "roas",
    ]
    return {key: summary.get(key, 0) for key in keys if key in summary}


def compact_top_products(top_products: list[Any]) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    for product in top_products[:10]:
        if not isinstance(product, dict):
            continue
        compacted.append(
            {
                "id": product.get("id") or "",
                "title": product.get("title") or "",
                "units": product.get("units") or 0,
                "sales": product.get("sales") or 0,
            }
        )
    return compacted


def low_stock_sku_count(factories: list[Any], threshold: int = 10) -> int:
    count = 0
    for factory in factories:
        if not isinstance(factory, dict):
            continue
        stock = factory.get("stock")
        if not isinstance(stock, dict):
            continue
        for qty in stock.values():
            try:
                if float(qty) <= threshold:
                    count += 1
            except (TypeError, ValueError):
                continue
    return count


def build_risk_summary(fields: dict[str, Any]) -> list[str]:
    risks: list[str] = []
    if not fields.get("base_url"):
        risks.append("POD 管理员端当前未检测到可访问端口。")
    if fields.get("db_status") != "ok":
        risks.append("POD 本地数据库暂不可读。")
    if int(fields.get("exception_job_count") or 0) > 0:
        risks.append("存在异常/退回工单，需要管理员复盘。")
    if int(fields.get("pending_print_job_count") or 0) > 0:
        risks.append("存在待处理生产工单，可能影响履约时效。")
    if int(fields.get("low_stock_sku_count") or 0) > 0:
        risks.append("存在低库存 SKU，选品和接单前要看库存。")
    if int(fields.get("channel_pending_listing_count") or 0) > 0:
        risks.append("存在渠道待上架/待同步商品，需要检查 Listing、主图、价格和渠道状态。")
    if int(fields.get("channel_pending_shipment_count") or 0) > 0:
        risks.append("存在渠道发货同步待处理，可能影响平台履约评分。")
    if int(fields.get("platform_ops_below_target_count") or 0) > 0:
        risks.append("存在平台代运营商品未达销售目标，需要复盘是否下架、改素材或换渠道。")
    if fields.get("channel_analytics_status") == "requires_admin_session":
        risks.append("渠道分析接口需要管理员登录态；当前只记录接口结构，未读取真实渠道数据。")
    if not risks:
        risks.append("暂无明显 POD 管理端风险。")
    return risks


def build_recommended_actions(fields: dict[str, Any]) -> list[str]:
    actions = [
        "把 POD 底板、成本、库存和工厂履约能力并入 AI 选品判断。",
        "把爆款内容方向映射到可生产底板，再生成 Listing、主图和脚本建议。",
    ]
    if int(fields.get("pending_design_count") or 0) > 0:
        actions.append("优先复核待审核作品，避免好素材卡在审核队列。")
    if int(fields.get("pending_print_job_count") or 0) > 0:
        actions.append("查看待确认/待生产工单，确认是否需要派单或催生产。")
    if int(fields.get("low_stock_sku_count") or 0) > 0:
        actions.append("低库存 SKU 不要作为今天重点打品承接款，除非确认补货。")
    if fields.get("channel_analytics_status") == "ok":
        actions.append("用渠道分析数据判断 TikTok/SHEIN/Shopee/Lazada/Amazon/Etsy/Walmart/eBay/Shopify/WooCommerce 的上架优先级、广告素材和达人打法。")
    else:
        actions.append("渠道分析接口已预留；等管理员登录态或授权读取方式确认后，再自动读取各渠道销量、广告、达人和上架状态。")
    if int(fields.get("platform_ops_pending_count") or 0) > 0:
        actions.append("平台代运营待审核商品先生成渠道 Listing 草稿和目标销售计划，审核发布前必须等你确认。")
    actions.append("执行审核、派单、改价、财务、上下架前必须等待用户确认。")
    return actions
