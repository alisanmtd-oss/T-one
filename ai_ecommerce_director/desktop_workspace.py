"""Reviewed facade for the readable desktop workspace runtime.

The runtime was reconstructed from the verified local behavior baseline and
is now kept as ordinary Python source in ``_desktop_workspace_runtime.py``.
This facade layers the newer owner-facing workflows on that source module.
"""

from __future__ import annotations

from contextvars import ContextVar as _ContextVar
from html import escape as _html_escape
import json as _json
from pathlib import Path as _Path
import re as _re
from types import ModuleType as _ModuleType
import sys as _sys


from . import _desktop_workspace_runtime as _legacy_runtime
from .agent_skill_marketplace import (
    agent_skill_marketplace_snapshot as _agent_skill_marketplace_snapshot,
)
from .company_workspace import skip_sales_output_scan as _skip_sales_output_scan

_LEGACY_EXPORT_NAMES = tuple(
    name for name in _legacy_runtime.__dict__ if not name.startswith("__")
)
for _name in _LEGACY_EXPORT_NAMES:
    globals()[_name] = getattr(_legacy_runtime, _name)

_legacy_render_desktop_workspace = _legacy_runtime.render_desktop_workspace
_legacy_realtime_dashboard_html = _legacy_runtime._realtime_dashboard_html
_full_company_dashboard_snapshot = _legacy_runtime.company_dashboard_snapshot
_RENDER_VIEW: _ContextVar[str] = _ContextVar("desktop_workspace_render_view", default="")
_FAST_NON_OPERATIONAL_VIEWS = frozenset(
    {
        "new",
        "new_conversation",
        "settings",
        "settings_center",
        "extensions",
    }
)


_OWNER_UI_CLEANUP_CSS = """
<style data-owner-ui-cleanup="true">
body[data-desktop-ui="true"] :is(a,button,input,select,textarea,label,span,b,small,em,p,h3,h4,summary,li,time,output,td,th){font-size:14px!important}
body[data-desktop-ui="true"] .sidebar-section-label{font-size:14px!important}
body[data-desktop-ui="true"] .settings-page-nav-label{font-size:14px!important}
body[data-desktop-ui="true"] :is(.overview-link,.task-link,.store-summary,.account,.crumb) small,
body[data-desktop-ui="true"] .task-intro p{display:none!important}
body[data-view="module_dashboard"] .dashboard-data-head p,
body[data-view="module_dashboard"] .dashboard-data-head small,
body[data-view="module_dashboard"] .dashboard-kpi-card em,
body[data-view="module_dashboard"] .dashboard-ratio-card em,
body[data-view="module_dashboard"] .dashboard-decision-intelligence,
body[data-view="module_dashboard"] .dashboard-dimension-matrix{display:none!important}
body[data-view="module_dashboard"] .dashboard-module-card p,
body[data-view="module_dashboard"] .dashboard-truth-note,
body[data-view="module_dashboard"] .section-title span,
body[data-view="module_dashboard"] .dashboard-data-panel>p,
body[data-view="module_dashboard"] .dashboard-data-panel footer{display:none!important}
body[data-view="module_dashboard"] :is(p,small,em){display:none!important}
body[data-view="realtime_project"] :is(p,small,em,time){display:none!important}
body[data-desktop-ui="true"] .task-intro p{display:none!important}
body[data-desktop-ui="true"] .agent-welcome p{display:none!important}
body[data-desktop-ui="true"] .task-history-context>summary small,
body[data-desktop-ui="true"] .u15-settlement-import>summary span{display:none!important}
body[data-desktop-ui="true"] .task-workflow-guide header p,
body[data-desktop-ui="true"] .task-workflow-step span span,
body[data-desktop-ui="true"] .task-brief-form>p,
body[data-desktop-ui="true"] .task-context-chat-first>summary small,
body[data-desktop-ui="true"] .task-context-note,
body[data-desktop-ui="true"] .task-context-section>summary small{display:none!important}
body[data-view="extensions"] .agent-skill-market small{display:none!important}
body[data-view="extensions"] .smart-capability-manager-note,
body[data-view="extensions"] .agent-skill-market>p,
body[data-view="extensions"] #agentSkillMarketStatus:not([data-state]),
body[data-view="extensions"] #agentSkillMarketStatus[data-state=""]{display:none!important}
body[data-view="extensions"] .agent-skill-item,
body[data-view="extensions"] .agent-skill-connection,
body[data-view="extensions"] .project-ai-item{min-height:54px;align-items:center}
body[data-view="settings_center"] .settings-section-lead,
body[data-view="settings_center"] .settings-option-row small,
body[data-view="settings_center"] .settings-page-section>p,
body[data-view="settings_center"] .data-acquisition-heading p{display:none!important}
body[data-view="settings_center"] :is(p:not([role="status"]),small){display:none!important}
body[data-view="settings_center"] .settings-option-row{min-height:62px}
</style>
"""

_OWNER_UI_COPY_DISTILLATION = """
<script data-owner-ui-copy-distillation="true">
(()=>{
  const replacements=[
    ['权威运行证据','当前状态'],['证据','资料'],['样本','数据'],['回执','结果'],
    ['门禁','条件'],['指标口径','计算方式'],['事实表','数据表'],['维度字典','字段说明'],
    ['真值等级','数据状态'],['置信度','可靠度'],['外部动作 0','未操作外部平台'],
    ['prohibited','不可执行'],['source_ref','资料来源']
  ];
  const distill=root=>{
    const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode(node){
      return node.parentElement?.closest('script,style,noscript')?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT;
    }});
    while(walker.nextNode()){
      const node=walker.currentNode;let value=node.nodeValue||'';
      replacements.forEach(([from,to])=>{value=value.split(from).join(to);});
      if(value!==node.nodeValue)node.nodeValue=value;
    }
  };
  distill(document.body);
  new MutationObserver(records=>records.forEach(record=>record.addedNodes.forEach(node=>{
    if(node.nodeType===Node.TEXT_NODE){const parent=node.parentElement;if(parent&&!parent.closest('script,style,noscript'))distill(parent);}
    else if(node.nodeType===Node.ELEMENT_NODE)distill(node);
  }))).observe(document.body,{childList:true,subtree:true});
})();
</script>
"""


def _ensure_owner_ui_cleanup(html: str) -> str:
    """Keep daily screens focused on names, current results and usable actions."""

    if 'data-desktop-ui="true"' not in html:
        return html
    if 'data-owner-ui-cleanup="true"' not in html:
        html = html.replace(
            'data-desktop-ui="true"',
            'data-desktop-ui="true" data-owner-ui-cleanup="true"',
            1,
        )
        html = html.replace("</head>", _OWNER_UI_CLEANUP_CSS + "</head>", 1)
    html = html.replace("样本不足", "暂无数据")
    html = html.replace("权威运行证据", "当前状态")
    html = html.replace("历史上下文", "历史记录")
    html = html.replace(
        "async function browserEnvironmentSnapshotRequest(){if(window.pywebview?.api?.browser_environment_snapshot)return window.pywebview.api.browser_environment_snapshot();const response=await fetch('/api/v1/browser-environments',{cache:'no-store'});",
        "async function browserEnvironmentSnapshotRequest(){if(window.pywebview?.api?.browser_environment_snapshot)return window.pywebview.api.browser_environment_snapshot();if(window.teelabDesktop?.isDesktop&&window.teelabDesktop?.invoke)return window.teelabDesktop.invoke('browser_environment_snapshot');const response=await fetch('/api/v1/browser-environments',{cache:'no-store'});",
    )
    html = html.replace(
        "async function prepareBrowserEnvironmentRequest(payload){if(window.pywebview?.api?.prepare_browser_environment)return window.pywebview.api.prepare_browser_environment(payload);const response=await fetch('/api/v1/browser-environments/prepare'",
        "async function prepareBrowserEnvironmentRequest(payload){if(window.pywebview?.api?.prepare_browser_environment)return window.pywebview.api.prepare_browser_environment(payload);if(window.teelabDesktop?.isDesktop&&window.teelabDesktop?.invoke)return window.teelabDesktop.invoke('prepare_browser_environment',payload);const response=await fetch('/api/v1/browser-environments/prepare'",
    )
    if 'data-view="extensions"' in html:
        html = html.replace("Amazon 证据化运营与多模态蒸馏", "Amazon 运营工具")
    if 'data-owner-ui-copy-distillation="true"' not in html:
        html = html.replace("</body>", _OWNER_UI_COPY_DISTILLATION + "</body>", 1)
    return html


_TASK_CONVERSATION_CLEANUP = """
<script data-task-conversation-cleanup="true">
(()=>{
  const isAcceptanceText=value=>/\\bTONE-[A-Z0-9-]*(?:ROUNDTRIP|BROWSER-TEST)[A-Z0-9-]*\\b/i.test(String(value||''));
  document.querySelectorAll('#messages .message').forEach(row=>{if(isAcceptanceText(row.textContent))row.remove();});
  const messages=document.getElementById('messages');if(messages&&!messages.children.length)messages.style.display='none';
  try{
    const key='commerce_ai_chat_page_history_v2:'+encodeURIComponent((location.pathname+location.search).slice(0,180));
    const raw=localStorage.getItem(key);if(!raw)return;
    const parsed=typeof dataCodec==='object'&&dataCodec?.parse?dataCodec.parse(raw):JSON.parse(raw);
    if(!Array.isArray(parsed))return;
    const cleaned=parsed.filter(item=>!isAcceptanceText(item?.text));
    if(cleaned.length!==parsed.length)localStorage.setItem(key,typeof dataCodec==='object'&&dataCodec?.stringify?dataCodec.stringify(cleaned):JSON.stringify(cleaned));
  }catch(_error){}
})();
</script>
"""


def _simplify_task_conversation(html: str, query_map: dict[str, object]) -> str:
    """Remove test chat residue without deleting task operations or history."""

    raw_task = query_map.get("task") or [""]
    task_id = str(raw_task[0] if isinstance(raw_task, (list, tuple)) else raw_task).strip()
    if not task_id or "const TASK=" not in html:
        return html
    if 'data-task-conversation-cleanup="true"' not in html:
        html = html.replace("</body>", _TASK_CONVERSATION_CLEANUP + "</body>", 1)
    return html


def _company_snapshot_for_current_view(root, workspace_config=None):
    """Keep configuration screens complete while avoiding sales-file scans."""

    if _RENDER_VIEW.get() in _FAST_NON_OPERATIONAL_VIEWS:
        with _skip_sales_output_scan():
            return _full_company_dashboard_snapshot(root, workspace_config)
    return _full_company_dashboard_snapshot(root, workspace_config)


# The recovered renderer resolves this global at call time.  A ContextVar keeps
# concurrent requests isolated while preserving the verified bytecode renderer.
_legacy_runtime.company_dashboard_snapshot = _company_snapshot_for_current_view


def _realtime_source_status_text(item: dict) -> str:
    state = str(item.get("freshness_state") or "")
    if state == "stale_snapshot":
        return "历史快照 · 未连接自动同步"
    if state == "recent_snapshot":
        return "本地快照 · 未连接自动同步"
    if state == "current_local_activity":
        return "本地操作记录 · 随本地操作更新"
    if state == "stale_local_activity":
        return "较早的本地操作记录"
    if state == "configuration_only":
        return "仅配置 · 不是经营数据"
    return "未接入"


def _realtime_source_truth_payload(snapshot: dict) -> str:
    ledger = [
        item
        for item in (snapshot.get("source_ledger") or [])
        if isinstance(item, dict)
        and item.get("source_type") == "external_live_sync"
        and item.get("freshness_state") in {"live", "current"}
    ]
    live = bool(snapshot.get("live_data_available") and ledger)
    status_label = "实时数据" if live else "未连接实时数据"
    business_as_of = str(snapshot.get("business_data_as_of") or "") if live else ""
    summaries = [
        item
        for item in (snapshot.get("live_store_summaries") or [])
        if isinstance(item, dict)
    ]
    tasks = [
        item for item in (snapshot.get("live_store_tasks") or []) if isinstance(item, dict)
    ]
    truth_payload = {
        "data_status_label": status_label,
        "business_data_as_of": business_as_of,
        "live_data_available": live,
        "source_ledger": ledger,
        "live_store_summaries": summaries,
        "live_store_tasks": tasks,
    }
    payload = _html_escape(
        _json.dumps(truth_payload, ensure_ascii=False).replace("</", r"<\/"),
        quote=False,
    )
    return f'<script type="application/json" id="realtimeSourceTruthPayload">{payload}</script>'


_REALTIME_SOURCE_TRUTH_STYLE = """
<style data-realtime-source-truth-style="true">
body[data-view="realtime_dashboard"] .realtime-map-primary .market-map-layout{grid-template-columns:1fr}body[data-view="realtime_dashboard"] .realtime-map-primary .map-side{display:none}body[data-view="realtime_dashboard"] .realtime-map-primary .map-legend [data-legend="planned"]{display:none}
.realtime-core-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin-top:12px;border:1px solid #dfe7e6;border-radius:12px;overflow:hidden;background:#fff}.realtime-core-metric{padding:14px 16px;border-right:1px solid #e4eae9}.realtime-core-metric:last-child{border-right:0}.realtime-core-metric span,.realtime-core-metric em{display:block;color:var(--muted);font-size:11px;font-style:normal}.realtime-core-metric strong{display:block;margin:6px 0 4px;font-size:24px;line-height:1.1}.realtime-core-metric strong small{margin-left:3px;font-size:12px;font-weight:500}
.realtime-simple-section{margin-top:14px;border:1px solid #dfe7e6;border-radius:12px;background:#fff;padding:14px}.realtime-simple-section>header{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:10px}.realtime-simple-section h3{margin:0;font-size:14px}.realtime-simple-section header span{color:var(--muted);font-size:11px}.realtime-store-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.realtime-store-card{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;padding:12px;border:1px solid #e3e9e8;border-radius:9px;background:#fafcfc;color:var(--text)}.realtime-store-card b,.realtime-store-card small{display:block}.realtime-store-card b{font-size:13px}.realtime-store-card small{margin-top:4px;color:var(--muted);font-size:11px}.realtime-store-card dl{display:grid;grid-template-columns:repeat(3,auto);gap:12px;margin:0}.realtime-store-card dt{color:var(--muted);font-size:10px}.realtime-store-card dd{margin:3px 0 0;font-size:12px;font-weight:700;text-align:right}
.realtime-link-empty{margin:0;padding:18px;border:1px dashed #d8e2e0;border-radius:9px;color:var(--muted);font-size:12px;text-align:center}.realtime-link-table{width:100%;border-collapse:collapse;font-size:12px}.realtime-link-table th,.realtime-link-table td{padding:9px;border-bottom:1px solid #edf1f0;text-align:left}.realtime-link-table th{color:var(--muted);font-weight:500}.realtime-link-table td:nth-last-child(-n+2),.realtime-link-table th:nth-last-child(-n+2){text-align:right}.realtime-link-table a{color:#0f766e;word-break:break-all}
.realtime-trend-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.realtime-trend-card{border:1px solid #e3e9e8;border-radius:9px;padding:12px;background:#fafcfc}.realtime-trend-card header{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}.realtime-trend-card h4{margin:0;font-size:12px}.realtime-trend-card header strong{font-size:15px}.realtime-trend-card svg{display:block;width:100%;height:105px;margin-top:8px}.realtime-trend-card footer{display:flex;justify-content:space-between;gap:8px;color:var(--muted);font-size:10px}.realtime-trend-card p{margin:7px 0 0;color:#4b575b;font-size:11px;line-height:1.45}.realtime-chart-grid-line{stroke:#e7edec;stroke-width:1}.realtime-chart-line{fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}.realtime-chart-point{stroke:#fff;stroke-width:1.5}
@media(max-width:900px){.realtime-core-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.realtime-core-metric:nth-child(2){border-right:0}.realtime-core-metric:nth-child(-n+2){border-bottom:1px solid #e4eae9}.realtime-trend-grid{grid-template-columns:1fr}}@media(max-width:760px){.realtime-store-grid{grid-template-columns:1fr}.realtime-store-card{grid-template-columns:1fr}.realtime-store-card dl{justify-content:start}.realtime-store-card dd{text-align:left}}
</style>
"""


_REALTIME_SOURCE_TRUTH_SCRIPT = """
<script data-realtime-source-truth-script="true">
(()=>{
  const payloadNode=document.getElementById('realtimeSourceTruthPayload');if(!payloadNode)return;
  let payload={};try{payload=JSON.parse(payloadNode.textContent||'{}');}catch(_error){}
  const tasks=Array.isArray(payload.live_store_tasks)?payload.live_store_tasks:[];
  const invoke=async task=>{if(window.pywebview?.api?.open_store_surface)return await window.pywebview.api.open_store_surface('orders',task);if(window.teelabDesktop?.isDesktop&&window.teelabDesktop?.invoke)return await window.teelabDesktop.invoke('open_store_surface','orders',task);throw new Error('请在 T One 桌面版刷新店铺数据。');};
  let running=false;
  async function refresh(){if(running||!tasks.length)return;const canInvoke=Boolean(window.pywebview?.api?.open_store_surface||(window.teelabDesktop?.isDesktop&&window.teelabDesktop?.invoke));if(!canInvoke)return;const last=Number(sessionStorage.getItem('tOneLiveStoreSyncAt')||0);if(Date.now()-last<55000)return;running=true;let ok=0;for(const task of tasks){try{const result=await invoke({...task,background_refresh:true});if(result?.ok)ok+=1;}catch(_error){}}sessionStorage.setItem('tOneLiveStoreSyncAt',String(Date.now()));if(ok){location.reload();return;}running=false;}
  setTimeout(()=>refresh(false),900);
  setInterval(()=>{if(document.visibilityState==='visible')refresh(false);},60000);
})();
</script>
"""


def _realtime_money(value: object) -> str:
    try:
        return f"{max(0.0, float(value or 0)):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _realtime_time_label(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "等待数据"
    try:
        from datetime import datetime as _DateTime

        parsed = _DateTime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.astimezone().strftime("%m-%d %H:%M")
    except ValueError:
        return text[:16]


def _realtime_trend_svg(summaries: list[dict], field: str) -> tuple[str, int, str, str, str]:
    colors = ("#0f766e", "#2563eb", "#d97706", "#9333ea")
    series: list[tuple[str, list[dict]]] = []
    all_values: list[float] = []
    all_times: list[str] = []
    for item in summaries:
        points = [point for point in item.get("trend_points", []) if isinstance(point, dict)]
        clean: list[dict] = []
        for point in points:
            try:
                value = max(0.0, float(point.get(field) or 0))
            except (TypeError, ValueError):
                continue
            captured_at = str(point.get("captured_at") or "")
            clean.append({"value": value, "captured_at": captured_at})
            all_values.append(value)
            if captured_at:
                all_times.append(captured_at)
        if clean:
            series.append((str(item.get("store_id") or "店铺"), clean))
    maximum = max(all_values, default=0.0)
    scale_max = maximum if maximum > 0 else 1.0
    shapes = [
        '<line class="realtime-chart-grid-line" x1="12" y1="24" x2="308" y2="24"/>',
        '<line class="realtime-chart-grid-line" x1="12" y1="60" x2="308" y2="60"/>',
        '<line class="realtime-chart-grid-line" x1="12" y1="96" x2="308" y2="96"/>',
    ]
    rising = falling = stable = 0
    for index, (_store_id, points) in enumerate(series):
        coords: list[tuple[float, float]] = []
        for point_index, point in enumerate(points):
            x = 160.0 if len(points) == 1 else 14.0 + point_index * 292.0 / (len(points) - 1)
            y = 96.0 - point["value"] * 72.0 / scale_max
            coords.append((x, y))
        color = colors[index % len(colors)]
        if len(coords) > 1:
            shapes.append(
                '<polyline class="realtime-chart-line" stroke="{}" points="{}"/>'.format(
                    color,
                    " ".join(f"{x:.1f},{y:.1f}" for x, y in coords),
                )
            )
            delta = points[-1]["value"] - points[0]["value"]
            if abs(delta) < 0.0001:
                stable += 1
            elif delta > 0:
                rising += 1
            else:
                falling += 1
        for x, y in coords:
            shapes.append(
                f'<circle class="realtime-chart-point" fill="{color}" cx="{x:.1f}" cy="{y:.1f}" r="3.2"/>'
            )
    point_count = sum(len(points) for _store_id, points in series)
    if not any(len(points) > 1 for _store_id, points in series):
        analysis = "真实数据点不足；继续刷新后形成趋势。"
    elif rising == 0 and falling == 0:
        analysis = "当前区间各店铺持平。"
    else:
        analysis = f"上升 {rising} 家 · 下降 {falling} 家 · 持平 {stable} 家"
    start = min(all_times, default="")
    end = max(all_times, default="")
    return (
        '<svg viewBox="0 0 320 108" role="img" aria-label="真实店铺趋势曲线">{}</svg>'.format("".join(shapes)),
        point_count,
        start,
        end,
        analysis,
    )


def _realtime_live_metrics_html(snapshot: dict) -> str:
    summaries = [
        item for item in (snapshot.get("live_store_summaries") or []) if isinstance(item, dict)
    ]
    if not summaries:
        return '<section class="metric-grid realtime-map-metrics" hidden></section>'
    total_orders = sum(max(0, int(item.get("order_count") or 0)) for item in summaries)
    total_units = sum(max(0, int(item.get("unit_count") or 0)) for item in summaries)
    total_gmv = sum(float(item.get("gross_sales") or 0) for item in summaries)
    total_income = sum(float(item.get("expected_income") or 0) for item in summaries)
    latest_at = max((str(item.get("captured_at") or "") for item in summaries), default="")
    metrics = (
        ("GMV / 商品总价", _realtime_money(total_gmv), "", "原币汇总"),
        ("订单", str(total_orders), "单", "实时店铺汇总"),
        ("商品件数", str(total_units), "件", "实时店铺汇总"),
        ("预计收入", _realtime_money(total_income), "", "平台可见汇总"),
    )
    metric_html = "".join(
        '<div class="realtime-core-metric"><span>{}</span><strong>{}<small>{}</small></strong><em>{}</em></div>'.format(
            _html_escape(label), _html_escape(value), _html_escape(unit), _html_escape(note)
        )
        for label, value, unit, note in metrics
    )
    store_cards: list[str] = []
    for item in summaries:
        store_id = str(item.get("store_id") or "店铺")
        href = "/desktop?project={}&task={}".format(
            _html_escape(str(item.get("project_id") or ""), quote=True),
            _html_escape(str(item.get("task_id") or ""), quote=True),
        )
        store_cards.append(
            '<a class="realtime-store-card" href="{}"><span><b>{} · {}</b><small>{} · 只读实时连接 · {}</small></span>'
            '<dl><div><dt>订单</dt><dd>{} 单</dd></div><div><dt>GMV</dt><dd>{}</dd></div><div><dt>预计收入</dt><dd>{}</dd></div></dl></a>'.format(
                href,
                _html_escape(str(item.get("platform") or "").upper()),
                _html_escape(store_id),
                _html_escape(str(item.get("country_site") or "GLOBAL")),
                _html_escape(_realtime_time_label(item.get("captured_at"))),
                max(0, int(item.get("order_count") or 0)),
                _realtime_money(item.get("gross_sales")),
                _realtime_money(item.get("expected_income")),
            )
        )
    link_rows: list[str] = []
    for item in summaries:
        for link in item.get("product_links", []):
            if not isinstance(link, dict):
                continue
            link_rows.append(
                '<tr><td>{}</td><td><a href="{}" target="_blank" rel="noopener noreferrer">{}</a></td><td>{}</td><td>{}</td></tr>'.format(
                    _html_escape(str(item.get("store_id") or "店铺")),
                    _html_escape(str(link.get("url") or ""), quote=True),
                    _html_escape(str(link.get("title") or link.get("url") or "商品链接")),
                    max(0, int(link.get("order_count") or 0)),
                    _realtime_money(link.get("gross_sales")),
                )
            )
    if link_rows:
        links_html = '<table class="realtime-link-table"><thead><tr><th>店铺</th><th>出单商品链接</th><th>订单</th><th>销售额</th></tr></thead><tbody>{}</tbody></table>'.format("".join(link_rows))
    else:
        links_html = '<p class="realtime-link-empty">链接级数据未连接</p>'
    trend_cards: list[str] = []
    for title, field, total, unit in (
        ("GMV 趋势", "gross_sales", _realtime_money(total_gmv), ""),
        ("订单趋势", "order_count", str(total_orders), " 单"),
        ("预计收入趋势", "expected_income", _realtime_money(total_income), ""),
    ):
        svg, count, start, end, analysis = _realtime_trend_svg(summaries, field)
        trend_cards.append(
            '<article class="realtime-trend-card" data-real-point-count="{}"><header><h4>{}</h4><strong>{}{}</strong></header>{}'
            '<footer><span>{}</span><span>{}</span></footer><p>{}</p></article>'.format(
                count,
                _html_escape(title),
                _html_escape(total),
                _html_escape(unit),
                svg,
                _html_escape(_realtime_time_label(start)),
                _html_escape(_realtime_time_label(end)),
                _html_escape(analysis),
            )
        )
    return (
        '<section class="realtime-map-metrics" data-simple-realtime-business="true">'
        '<div class="realtime-core-metrics">{}</div>'
        '<section class="realtime-simple-section"><header><h3>店铺</h3><span>{} 家正在回传 · {}</span></header><div class="realtime-store-grid">{}</div></section>'
        '<section class="realtime-simple-section"><header><h3>出单链接与销售额</h3><span>只显示店铺真实返回的链接级数据</span></header>{}</section>'
        '<section class="realtime-simple-section"><header><h3>趋势曲线</h3><span>只使用每次真实店铺读取留下的数据点</span></header><div class="realtime-trend-grid">{}</div></section>'
        '</section>'
    ).format(metric_html, len(summaries), _html_escape(_realtime_time_label(latest_at)), "".join(store_cards), links_html, "".join(trend_cards))


def _realtime_render_snapshot(snapshot: dict) -> dict:
    """Keep the live page limited to fresh store reads, not historical project evidence."""

    rendered = dict(snapshot)
    if "live_store_tasks" not in snapshot and "live_store_summaries" not in snapshot:
        rendered["source_ledger"] = [
            dict(item)
            for item in snapshot.get("source_ledger", [])
            if isinstance(item, dict)
            and item.get("source_type") == "external_live_sync"
            and item.get("freshness_state") in {"live", "current"}
        ]
        return rendered
    summaries = [
        item for item in (snapshot.get("live_store_summaries") or []) if isinstance(item, dict)
    ]
    live_store_ids = {str(item.get("store_id") or "") for item in summaries}
    live_task_ids = {str(item.get("task_id") or "") for item in summaries}
    live_project_ids = {str(item.get("project_id") or "") for item in summaries}
    captured_by_project = {
        project_id: max(
            (
                str(item.get("captured_at") or "")
                for item in summaries
                if str(item.get("project_id") or "") == project_id
            ),
            default="",
        )
        for project_id in live_project_ids
    }
    nodes: list[dict] = []
    for raw_node in snapshot.get("map_nodes", []):
        if not isinstance(raw_node, dict):
            continue
        stores = [
            dict(item)
            for item in raw_node.get("stores", [])
            if isinstance(item, dict)
            and any(store_id and store_id in str(item.get("name") or "") for store_id in live_store_ids)
        ]
        if not stores:
            continue
        task_details = [
            dict(item)
            for item in raw_node.get("task_details", [])
            if isinstance(item, dict) and str(item.get("id") or "") in live_task_ids
        ]
        projects = [
            {
                **dict(item),
                "evidence_status": "live",
                "last_evidence_at": captured_by_project.get(str(item.get("id") or ""), ""),
            }
            for item in raw_node.get("projects", [])
            if isinstance(item, dict) and str(item.get("id") or "") in live_project_ids
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
                    if isinstance(item, dict) and str(item.get("platform") or "").lower() == "shein"
                ],
                "task_details": task_details,
                "evidence_refs": [],
            }
        )
        nodes.append(node)
    rendered["map_nodes"] = nodes
    rendered["metrics"] = []
    rendered["source_ledger"] = [
        dict(item)
        for item in snapshot.get("source_ledger", [])
        if isinstance(item, dict)
        and item.get("source_type") == "external_live_sync"
        and item.get("freshness_state") in {"live", "current"}
    ]
    rendered["projects"] = [
        {
            "id": project_id,
            "name": project_id,
            "task_count": sum(1 for item in summaries if str(item.get("project_id") or "") == project_id),
            "store_count": sum(1 for item in summaries if str(item.get("project_id") or "") == project_id),
            "metrics": [],
            "blockers": [],
            "evidence_refs": [],
            "last_evidence_at": captured_by_project.get(project_id, ""),
        }
        for project_id in sorted(live_project_ids)
    ]
    rendered["amazon"] = {}
    return rendered


def _apply_realtime_dashboard_truth(html: str, snapshot: dict) -> str:
    if 'id="realtimeSourceTruthPayload"' in html:
        return html
    html = html.replace("全球订单与站点热力图", "店铺地图")
    html = html.replace("<span>指标、站点与项目同屏；账号存在不等于当地库存或在售</span>", "")
    html = html.replace("地图正在加载，右侧站点明细仍可使用。", "地图正在加载。")
    insert_marker = '<section class="live-section map-section'
    insert_at = html.find(insert_marker)
    if insert_at >= 0:
        html = html[:insert_at] + _realtime_source_truth_payload(snapshot) + html[insert_at:]
    html = _re.sub(
        r'<section class="metric-grid realtime-map-metrics">.*?</section>',
        _realtime_live_metrics_html(snapshot),
        html,
        count=1,
        flags=_re.S,
    )
    html = _re.sub(
        r'<section class="live-band live-summary">.*?</section>',
        "",
        html,
        count=1,
        flags=_re.S,
    )
    # The legacy dashboard appended an ERP-style data layer and project/readiness
    # columns after the map.  They are not realtime store truth and must not be
    # kept (even hidden) on this deliberately small operating surface.
    legacy_layer_start = html.find('<style id="realtime-map-data-layer-style">')
    supporting_start = html.find('<section class="live-columns realtime-supporting-sections">')
    if 0 <= legacy_layer_start < supporting_start:
        html = html[:legacy_layer_start] + html[supporting_start:]
    supporting_start = html.find('<section class="live-columns realtime-supporting-sections">')
    if supporting_start >= 0 and html.endswith("</section></div>"):
        html = html[:supporting_start] + "</div>"
    return html + _REALTIME_SOURCE_TRUTH_STYLE + _REALTIME_SOURCE_TRUTH_SCRIPT


def _realtime_dashboard_html(
    snapshot: dict | None,
    project_id: str = "",
    *,
    root: _Path | None = None,
    query: dict | None = None,
) -> str:
    """Render the project or company live view from readable, current state.

    The previous facade still delegated this surface to the recovered runtime.
    That kept an obsolete signature and could show account-only map nodes as
    operating stores.  Keep the renderer here so the public source contains the
    complete behavior and the live page only presents scope-matched work.
    """

    del root, query  # Accepted for the normal workspace renderer call contract.
    safe_snapshot = snapshot if isinstance(snapshot, dict) else {}
    selected_id = str(project_id or "").strip()
    projects = [
        item for item in (safe_snapshot.get("projects") or []) if isinstance(item, dict)
    ]
    selected_project = next(
        (item for item in projects if str(item.get("id") or "") == selected_id),
        None,
    )
    if selected_project is not None:
        tasks = [
            item
            for item in (selected_project.get("tasks") or [])
            if isinstance(item, dict)
        ]
        blockers = [
            str(item)
            for item in (selected_project.get("blockers") or [])
            if str(item).strip()
        ]
        task_rows = "".join(
            '<a class="live-task-row" href="/desktop?project={}&amp;task={}">'
            '<span><b>{}</b><small>{}</small></span><em>{}</em></a>'.format(
                _html_escape(selected_id, quote=True),
                _html_escape(str(task.get("id") or ""), quote=True),
                _html_escape(str(task.get("name") or "任务")),
                _html_escape(str(task.get("subtitle") or "")),
                _html_escape(str(task.get("status") or "待办")),
            )
            for task in tasks
        ) or '<p class="empty-row">当前没有任务。</p>'
        blocker_rows = "".join(
            f"<li>{_html_escape(item)}</li>" for item in blockers
        ) or "<li>当前没有项目卡点。</li>"
        metrics = [
            item
            for item in (selected_project.get("metrics") or [])
            if isinstance(item, dict)
        ]
        information = (
            selected_project.get("information")
            if isinstance(selected_project.get("information"), dict)
            else {}
        )
        system_rows = "".join(
            '<div class="integration-group"><b>{}</b><span>{}</span></div>'.format(
                _html_escape(str(item.get("label") or "系统数据")),
                _html_escape(str(item.get("detail") or item.get("status") or "待接入")),
            )
            for item in (information.get("system_fields") or [])
            if isinstance(item, dict)
        )
        ai_rows = "".join(
            f"<li>{_html_escape(str(item))}</li>"
            for item in (information.get("ai_generated_fields") or [])
            if str(item).strip()
        ) or "<li>当前项目还没有配置 AI 草稿能力。</li>"
        return (
            '<div class="live-dashboard" data-live-dashboard="project" '
            f'data-project-id="{_html_escape(selected_id, quote=True)}">'
            '<section class="live-band live-summary"><div>'
            '<span class="eyebrow">项目组实时数据</span>'
            f'<h2>{_html_escape(str(selected_project.get("name") or "项目"))}</h2>'
            '</div></section>'
            f'<section class="metric-grid">{_metric_grid(metrics, project_id=selected_id)}</section>'
            '<section class="live-columns"><div class="live-section">'
            f'<div class="section-title"><h3>任务</h3><span>{len(tasks)} 个</span></div>{task_rows}</div>'
            '<div class="live-section"><div class="section-title"><h3>当前卡点</h3>'
            f'<span>{len(blockers)} 项</span></div><ul class="blocker-list">{blocker_rows}</ul>'
            '</div></section>'
            '<section class="live-columns project-data"><div class="live-section">'
            '<div class="section-title"><h3>产品资料</h3>'
            f'<span>{int(information.get("owner_provided_count") or 0)}/'
            f'{int(information.get("owner_required_count") or 0)} 已有</span></div>'
            f'<div class="readiness"><strong>{int(information.get("owner_missing_count") or 0)}</strong>'
            '<span>项产品资料待补充</span></div>'
            '<button class="inline-command" type="button" data-open-project-data-settings>导入商品</button>'
            f'<div class="integration-list">{system_rows}</div></div>'
            '<div class="live-section"><div class="section-title"><h3>AI 自动完成</h3>'
            f'<span>草稿与分析</span></div><ul class="blocker-list ai-list">{ai_rows}</ul>'
            '</div></section></div>'
        )

    rendered_snapshot = _realtime_render_snapshot(safe_snapshot)
    map_nodes: list[dict] = []
    for item in rendered_snapshot.get("map_nodes") or []:
        if not isinstance(item, dict):
            continue
        aggregates = item.get("aggregates") if isinstance(item.get("aggregates"), dict) else {}
        has_work = any(
            int(aggregates.get(field) or 0) > 0
            for field in ("bound_store_count", "project_count", "task_count")
        )
        if has_work:
            map_nodes.append(dict(item))
    map_payload = _json.dumps(map_nodes, ensure_ascii=False).replace("</", r"<\/")
    status_labels = {
        "active": "运营中",
        "account_only": "仅账号",
        "planned": "规划中",
    }
    map_rows = "".join(
        '<button class="map-node" type="button" data-map-index="{}" '
        'data-map-country="{}" data-status="{}">'
        '<span class="map-node-title"><strong>{}</strong><em>{}</em></span>'
        '<span>{}</span><small>{} · {}</small></button>'.format(
            index,
            _html_escape(str(node.get("country") or "GLOBAL"), quote=True),
            _html_escape(str(node.get("status") or "planned"), quote=True),
            _html_escape(str(node.get("name") or node.get("country") or "GLOBAL")),
            _html_escape(str(node.get("country") or "GLOBAL")),
            _html_escape(" / ".join(str(value) for value in (node.get("tasks") or [])) or "当前业务"),
            _html_escape(status_labels.get(str(node.get("status") or "planned"), "规划中")),
            _html_escape(str(node.get("truth") or "已关联业务")),
        )
        for index, node in enumerate(map_nodes)
    ) or '<p class="empty-row">当前还没有正在回传数据的店铺。</p>'
    live_ledger = [
        item
        for item in (safe_snapshot.get("source_ledger") or [])
        if isinstance(item, dict)
        and item.get("source_type") == "external_live_sync"
        and item.get("freshness_state") in {"live", "current"}
    ]
    live = bool(safe_snapshot.get("live_data_available") and live_ledger)
    status_text = "实时数据" if live else "未连接实时数据"
    return (
        '<div class="live-dashboard" data-live-dashboard="overall" '
        'data-realtime-big-screen-benchmark="miaoshou_erp_2026_07_21">'
        f'{_realtime_source_truth_payload(safe_snapshot)}'
        '<section class="live-section map-section realtime-map-primary" '
        'data-primary-realtime-map="true"><div class="section-title">'
        f'<h3>店铺地图</h3><span>{status_text}</span></div>'
        '<div class="market-map-layout"><div class="map-canvas-shell">'
        '<div id="worldMarketMap" class="world-market-map" role="img" '
        'aria-label="店铺站点地图"></div>'
        '<p id="marketMapFallback" class="map-fallback">地图正在加载。</p>'
        '<div class="map-legend"><span data-legend="active">运营中</span>'
        '<span data-legend="account_only">仅账号</span></div></div>'
        f'<div class="map-sites" role="list" aria-label="站点明细">{map_rows}</div></div>'
        f'<script type="application/json" id="marketMapData">{map_payload}</script></section>'
        f'{_realtime_live_metrics_html(safe_snapshot)}'
        '</div>'
        + _REALTIME_SOURCE_TRUTH_STYLE
        + _REALTIME_SOURCE_TRUTH_SCRIPT
    )


_legacy_runtime._realtime_dashboard_html = _realtime_dashboard_html
_LEGACY_STRATEGY_OPTIONS_JS = (
    "function strategyOptions(record){return record?"
    "{reasoning:record.reasoning_options||['standard'],"
    "speed:record.speed_options||['standard'],"
    "defaultReasoning:record.default_reasoning||'standard',"
    "defaultSpeed:record.default_speed||'standard'}:"
    "{reasoning:['quick','standard','deep'],"
    "speed:['fast','standard','quality'],"
    "defaultReasoning:'standard',defaultSpeed:'standard'};}"
)
_DAILY_UI_READABILITY_CSS = """
body[data-view="realtime_dashboard"] .thread :not(:has(*)),
body[data-view="module_dashboard"] .thread :not(:has(*)),
body .task-context-body :not(:has(*)){font-size:14px!important}
"""
_REVIEWED_STRATEGY_OPTIONS_JS = (
    "function strategyOptions(record){"
    "const reasoning=[...new Set((record?.reasoning_options||['standard']).filter(Boolean))];"
    "const speed=[...new Set((record?.speed_options||['standard']).filter(Boolean))];"
    "if(!reasoning.length)reasoning.push('standard');"
    "if(!speed.length)speed.push('standard');"
    "const defaultReasoning=reasoning.includes(record?.default_reasoning)"
    "?record.default_reasoning:'standard';"
    "const defaultSpeed=speed.includes(record?.default_speed)"
    "?record.default_speed:'standard';"
    "return {reasoning,speed,defaultReasoning,defaultSpeed};}"
)
_ACCOUNT_ACCESS_SETTINGS_SECTION = (
    '<section class="settings-page-section" id="settings-account-access" hidden '
    'data-settings-page-section="账号登录与验证码 账号 店铺 邮箱 浏览器 执行身份 MFA OTP 验证码">'
    '<h1>账号登录与验证码</h1>'
    '<div class="settings-section-group"><h2>登录身份与验证码边界</h2>'
    '<div class="settings-option-list">'
    '<div class="settings-option-row"><span><b>平台账号与执行身份</b>'
    '<small>开发者授权、平台账号、国家站点、店铺、浏览器环境和执行身份必须逐项匹配；登记不等于已连接。</small>'
    '</span><em>强隔离</em></div>'
    '<div class="settings-option-row"><span><b>邮箱、MFA 与验证码</b>'
    '<small>验证码只用于当前登录流程，不进入聊天、长期记忆或普通运行日志；需要人工接管时保持原平台边界。</small>'
    '</span><em>不留存</em></div>'
    '<div class="settings-option-row"><span><b>真实连接状态</b>'
    '<small>以电商平台、通讯工具和浏览器环境页面的真实检测为准；本页不把候选账号或测试数据标为已连接。</small>'
    '</span><em>不推定已连接</em></div>'
    '<div class="settings-option-row"><span><b>账号执行身份链</b>'
    '<small>查看项目、平台、站点、店铺模式、账号、浏览器、网络/IP、邮箱与验证码回执的隔离状态。</small>'
    '</span><a id="u19OpenAccountAccess" href="/desktop?view=account_access&amp;project=system&amp;task=system-settings">打开 →</a></div>'
    '</div></div></section>'
)
_DATA_ACQUISITION_SETTINGS_BLOCK = """
<div class="settings-section-group data-acquisition-settings" data-data-acquisition-settings="true">
  <div class="data-acquisition-heading">
    <span>
      <h2>数据采集工具</h2>
      <p>接收 Web Scraper、八爪鱼、妙手采集和外贸工具导出的本地文件。导入后先核验，不代表外部账号、插件、ERP 或 API 已连接。</p>
    </span>
    <em id="dataAcquisitionTruth">正在读取真实状态</em>
  </div>
  <div class="data-acquisition-form">
    <label>采集工具
      <select id="dataAcquisitionProvider" aria-label="采集工具"></select>
    </label>
    <label>数据层
      <select id="dataAcquisitionSourceLayer"><option value="market_observation">市场 / 选品观察</option><option value="owned_operating_truth">自有经营导出候选</option></select>
    </label>
    <label>数据类型
      <input id="dataAcquisitionDatasetType" type="text" value="公开商品与市场资料" maxlength="120" autocomplete="off">
    </label>
    <label>Project ID<input id="dataAcquisitionProject" autocomplete="off"></label>
    <label>平台<input id="dataAcquisitionPlatform" autocomplete="off" placeholder="例如 SHEIN / Meta Ads"></label>
    <label>国家 / 站点<input id="dataAcquisitionCountrySite" autocomplete="off" placeholder="例如 US"></label>
    <label>采集时间<input id="dataAcquisitionCollectedAt" autocomplete="off" placeholder="2026-08-07T10:00:00+08:00"></label>
    <label>Store Binding ID<input id="dataAcquisitionStore" autocomplete="off" placeholder="仅自有经营导出必填"></label>
    <label>Account ID<input id="dataAcquisitionAccount" autocomplete="off" placeholder="仅自有经营导出必填"></label>
    <label>Execution Identity ID<input id="dataAcquisitionIdentity" autocomplete="off" placeholder="仅自有经营导出必填"></label>
    <label><span>来源确认</span><span><input id="dataAcquisitionOwnerAttested" type="checkbox"> 负责人确认是自有账号导出</span></label>
    <label class="data-acquisition-wide">来源页面（可选）
      <input id="dataAcquisitionSourceUrl" type="url" maxlength="2048" placeholder="https://..." autocomplete="off">
    </label>
    <label class="data-acquisition-wide">本地导出文件
      <input id="dataAcquisitionFile" type="file" accept=".csv,.xlsx,.json">
      <small id="dataAcquisitionFileHint">支持的格式会随采集工具更新。</small>
    </label>
    <button id="dataAcquisitionImport" type="button">导入本地导出文件</button>
  </div>
  <p class="data-acquisition-status" id="dataAcquisitionStatus" role="status" aria-live="polite">尚未选择文件。市场观察不能进入自有经营真值；不会自动登录、安装插件或提交外部表单。</p>
  <div class="data-acquisition-provider-list" id="dataAcquisitionProviders" aria-label="采集工具连接状态"></div>
</div>
"""
_DATA_ACQUISITION_SETTINGS_CSS = """
/* data-t-one-data-acquisition-style=true */
.data-acquisition-settings{margin-top:18px}.data-acquisition-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;padding-bottom:14px;border-bottom:1px solid var(--line)}
.data-acquisition-heading h2{margin:0 0 5px;font-size:15px}.data-acquisition-heading p{max-width:760px;margin:0;color:var(--muted);font-size:12px;line-height:1.65}.data-acquisition-heading em{flex:none;border:1px solid #a9d7ce;border-radius:999px;padding:5px 9px;background:#edf8f5;color:#17685e;font-size:11px;font-style:normal}
.data-acquisition-form{display:grid;grid-template-columns:minmax(180px,1fr) minmax(180px,1fr);gap:12px 14px;padding:16px 0}.data-acquisition-form label{display:grid;gap:6px;color:var(--muted);font-size:11px}.data-acquisition-form input,.data-acquisition-form select{min-width:0;border:1px solid var(--line);border-radius:7px;padding:9px 10px;background:#fff;color:var(--text);font:inherit;outline:none}.data-acquisition-form input:focus,.data-acquisition-form select:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(15,118,110,.1)}.data-acquisition-form input[type=file]{padding:7px}.data-acquisition-form small{line-height:1.5}.data-acquisition-wide{grid-column:1/-1}.data-acquisition-form button{justify-self:start;border:1px solid #111;border-radius:7px;padding:9px 13px;background:#111;color:#fff;cursor:pointer}.data-acquisition-form button:disabled{cursor:wait;opacity:.55}
.data-acquisition-status{margin:0 0 12px;color:var(--muted);font-size:12px;line-height:1.6}.data-acquisition-status[data-state=success]{color:#17685e}.data-acquisition-status[data-state=error]{color:#a3342b}.data-acquisition-provider-list{border-top:1px solid var(--line)}.data-acquisition-provider-row{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:10px 0;border-bottom:1px solid var(--line);font-size:12px}.data-acquisition-provider-row span{display:grid;gap:3px}.data-acquisition-provider-row small{color:var(--muted)}.data-acquisition-provider-row a{color:var(--accent);text-decoration:none}.data-acquisition-provider-row em{font-style:normal;color:#17685e;white-space:nowrap}
@media(max-width:760px){.data-acquisition-heading{display:grid}.data-acquisition-heading em{justify-self:start}.data-acquisition-form{grid-template-columns:1fr}.data-acquisition-wide{grid-column:auto}.data-acquisition-provider-row{align-items:flex-start}}
"""
_DATA_ACQUISITION_SETTINGS_JS = """
<script data-t-one-data-acquisition-script="true">
(()=>{
  const root=document.querySelector('[data-data-acquisition-settings="true"]');
  if(!root)return;
  const providerSelect=document.getElementById('dataAcquisitionProvider');
  const sourceLayer=document.getElementById('dataAcquisitionSourceLayer');
  const datasetType=document.getElementById('dataAcquisitionDatasetType');
  const sourceUrl=document.getElementById('dataAcquisitionSourceUrl');
  const fileInput=document.getElementById('dataAcquisitionFile');
  const fileHint=document.getElementById('dataAcquisitionFileHint');
  const importButton=document.getElementById('dataAcquisitionImport');
  const status=document.getElementById('dataAcquisitionStatus');
  const truth=document.getElementById('dataAcquisitionTruth');
  const providerList=document.getElementById('dataAcquisitionProviders');
  let providers=[];

  function setStatus(message,state=''){
    status.textContent=message;
    if(state)status.dataset.state=state;else delete status.dataset.state;
  }
  function selectedProvider(){return providers.find(item=>item.id===providerSelect.value)||null;}
  function syncFormats(){
    const provider=selectedProvider();
    const formats=(provider?.supported_file_formats||[]).map(value=>String(value).toLowerCase());
    fileInput.accept=formats.map(value=>'.'+value).join(',');
    fileHint.textContent=formats.length?'当前支持：'+formats.map(value=>value.toUpperCase()).join(' / '):'当前没有可导入格式。';
  }
  function renderProviderRows(){
    providerList.replaceChildren();
    providers.forEach(provider=>{
      const row=document.createElement('div');row.className='data-acquisition-provider-row';
      const copy=document.createElement('span');
      const name=document.createElement('b');name.textContent=provider.name||provider.id;
      const details=document.createElement('small');details.textContent=(provider.supported_file_formats||[]).map(value=>String(value).toUpperCase()).join(' / ')+' 本地导入';
      copy.append(name,details);
      const state=document.createElement('em');state.textContent=provider.connected?'已连接':'可导入，未连接';
      const urls=Array.isArray(provider.official_urls)?provider.official_urls:[];
      if(urls[0]){
        const link=document.createElement('a');link.href=urls[0];link.target='_blank';link.rel='noopener noreferrer';link.textContent='官网';
        copy.append(link);
      }
      row.append(copy,state);providerList.append(row);
    });
  }
  async function loadProviders(preserveStatus=false){
    try{
      const response=await fetch('/api/data-acquisition-connectors',{credentials:'same-origin'});
      const payload=await response.json();
      if(!response.ok||!payload.ok)throw new Error(payload.error||'采集工具状态读取失败。');
      providers=Array.isArray(payload.providers)?payload.providers:[];
      providerSelect.replaceChildren();
      providers.forEach(provider=>{
        const option=document.createElement('option');option.value=provider.id;option.textContent=provider.name||provider.id;providerSelect.append(option);
      });
      truth.textContent='本地导入可用 '+Number(payload.local_import_available_count||0)+'；外部账号已连接 '+Number(payload.connected_count||0);
      renderProviderRows();syncFormats();
      if(!preserveStatus)setStatus('尚未选择文件。导入后先核验，不会自动写入店铺。');
    }catch(error){
      truth.textContent='状态读取失败';
      setStatus(error instanceof Error?error.message:'采集工具状态读取失败。','error');
    }
  }
  function readFile(file){
    return new Promise((resolve,reject)=>{
      const reader=new FileReader();
      reader.onload=()=>resolve(String(reader.result||''));
      reader.onerror=()=>reject(new Error('本地文件读取失败。'));
      reader.readAsDataURL(file);
    });
  }
  providerSelect.addEventListener('change',syncFormats);
  importButton.addEventListener('click',async()=>{
    const file=fileInput.files?.[0];
    if(!selectedProvider()){setStatus('请先选择采集工具。','error');return;}
    if(!file){setStatus('请选择 CSV、XLSX 或 JSON 本地导出文件。','error');return;}
    importButton.disabled=true;setStatus('正在校验并导入本地文件...');
    try{
      const params=new URLSearchParams(location.search);
      const content=await readFile(file);
      const response=await fetch('/api/data-acquisition-connectors/import',{
        method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          provider_id:providerSelect.value,
          source_layer:sourceLayer.value,
          dataset_type:datasetType.value.trim()||'general_public_data',
          source_url:sourceUrl.value.trim(),
          collected_at:document.getElementById('dataAcquisitionCollectedAt').value.trim(),
          filename:file.name,
          content_base64:content,
          project_id:document.getElementById('dataAcquisitionProject').value.trim()||params.get('project')||'',
          platform:document.getElementById('dataAcquisitionPlatform').value.trim(),
          country_site:document.getElementById('dataAcquisitionCountrySite').value.trim(),
          store_binding_id:document.getElementById('dataAcquisitionStore').value.trim()||params.get('store')||params.get('store_binding')||'',
          account_id:document.getElementById('dataAcquisitionAccount').value.trim(),
          execution_identity_id:document.getElementById('dataAcquisitionIdentity').value.trim(),
          owner_attested_source:document.getElementById('dataAcquisitionOwnerAttested').checked
        })
      });
      const payload=await response.json();
      if(!response.ok||!payload.ok)throw new Error(payload.error||'本地文件导入失败。');
      const receipt=payload.receipt||{};
      const digest=String(receipt.sha256||'').slice(0,12);
      const layer=receipt.source_layer==='market_observation'?'市场观察（不进入自有经营真值）':'自有经营候选（仍待字段校验）';
      setStatus('已导入 '+Number(receipt.row_count||0)+' 行、'+Number(receipt.column_count||0)+' 列；'+layer+'；校验码 '+digest+'；外部账号仍未连接。','success');
      fileInput.value='';
      await loadProviders(true);
    }catch(error){
      setStatus(error instanceof Error?error.message:'本地文件导入失败。','error');
    }finally{importButton.disabled=false;}
  });
  loadProviders();
})();
</script>
"""
_LEGACY_SIDEBAR_RENAME_JS = (
    "if(action==='rename'){const nextName=window.prompt('修改名称',name);"
    "if(nextName===null)return;if(!nextName.trim())throw new Error('名称不能为空。');"
    "payload.name=nextName.trim();}"
)
_REVIEWED_SIDEBAR_RENAME_JS = (
    "if(action==='rename'){const nextName=await requestSidebarRename(name);"
    "if(nextName===null)return;if(!nextName.trim())throw new Error('名称不能为空。');"
    "payload.name=nextName.trim();}"
)
_SIDEBAR_RENAME_DIALOG_CSS = """
.sidebar-rename-dialog{width:min(420px,calc(100vw - 32px));border:1px solid #d9dddf;border-radius:12px;padding:0;box-shadow:0 24px 70px rgba(20,30,36,.25);color:var(--text);background:#fff}
.sidebar-rename-dialog::backdrop{background:rgba(20,30,36,.34);backdrop-filter:blur(2px)}
.sidebar-rename-form{display:grid;gap:14px;padding:20px}.sidebar-rename-form h2{margin:0;font-size:16px}.sidebar-rename-form label{display:grid;gap:7px;font-size:11px;color:var(--muted)}
.sidebar-rename-form input{width:100%;border:1px solid var(--line);border-radius:7px;padding:9px 10px;color:var(--text);background:#fff;outline:none}.sidebar-rename-form input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(15,118,110,.1)}
.sidebar-rename-actions{display:flex;justify-content:flex-end;gap:8px}.sidebar-rename-actions button{border:1px solid var(--line);border-radius:7px;padding:8px 13px;background:#fff;color:var(--text);cursor:pointer}.sidebar-rename-actions button[value="save"]{border-color:#111;background:#111;color:#fff}
"""
_SIDEBAR_RENAME_DIALOG = """
<dialog class="sidebar-rename-dialog" id="sidebarRenameDialog" aria-labelledby="sidebarRenameTitle">
  <form class="sidebar-rename-form" method="dialog">
    <h2 id="sidebarRenameTitle">重命名</h2>
    <label>新名称<input id="sidebarRenameInput" name="sidebar_rename" maxlength="100" required autocomplete="off"></label>
    <div class="sidebar-rename-actions">
      <button type="submit" value="cancel" formnovalidate>取消</button>
      <button type="submit" value="save">保存</button>
    </div>
  </form>
</dialog>
<script data-t-one-sidebar-rename-dialog="true">
function requestSidebarRename(currentName){
  const dialog=document.getElementById('sidebarRenameDialog');
  const input=document.getElementById('sidebarRenameInput');
  if(!dialog||!input||typeof dialog.showModal!=='function')return Promise.reject(new Error('当前窗口不支持重命名对话框。'));
  input.value=String(currentName||'');dialog.returnValue='cancel';
  return new Promise(resolve=>{
    dialog.addEventListener('close',()=>resolve(dialog.returnValue==='save'?input.value:null),{once:true});
    dialog.showModal();requestAnimationFrame(()=>{input.focus();input.select();});
  });
}
</script>
"""
_WORKSPACE_FOLDER_ACCESS_SCRIPT = """
<script data-t-one-workspace-folder-access="true">
async function openWorkspaceItemFolderRequest(itemType,itemId){
  const payload={item_type:String(itemType||''),item_id:String(itemId||'')};
  if(window.pywebview?.api?.open_workspace_item_folder)return await window.pywebview.api.open_workspace_item_folder(payload);
  if(window.teelabDesktop?.isDesktop&&window.teelabDesktop?.invoke)return await window.teelabDesktop.invoke('open_workspace_item_folder',payload);
  throw new Error('请在 T One Windows 桌面版中打开本地文件夹。');
}
(function(){
  const buttons=[...document.querySelectorAll('[data-workspace-open-folder="true"]')];
  if(!buttons.length){const legacy=document.getElementById('workspaceOpenFolder');if(legacy)buttons.push(legacy);}
  if(!buttons.length)return;
  const selection=()=>{
    const params=new URLSearchParams(location.search);
    const taskId=String(params.get('task')||'').trim();
    const projectId=String(params.get('project')||'').trim();
    if(taskId)return {itemType:'task',itemId:taskId};
    if(projectId&&projectId!=='system')return {itemType:'project',itemId:projectId};
    return null;
  };
  if(!selection())return;
  buttons.forEach(button=>{button.hidden=false;
  button.addEventListener('click',async()=>{
    const selected=selection();if(!selected)return;
    try{
      button.disabled=true;
      const opened=await openWorkspaceItemFolderRequest(selected.itemType,selected.itemId);
      if(!opened?.ok)throw new Error(opened?.error||'文件夹没有打开。');
      showNavigationStatus(opened.message||'已打开本地文件夹');
    }catch(error){showNavigationStatus(error?.message||'文件夹没有打开。');}
    finally{button.disabled=false;}
  });});
})();
</script>
"""
_WORKSPACE_CREATION_CSS = """
body[data-view="new_conversation"] .new-task-stage{place-items:center;padding:54px 32px 72px}
body[data-view="new_conversation"] .new-task-shell{width:min(740px,100%)}
body[data-view="new_conversation"] .new-task-shell h1{margin:0 0 26px;font-size:28px;font-weight:500;letter-spacing:-.02em}
body[data-view="new_conversation"] .new-task-box{position:relative;border:1px solid #dfe2e5;border-radius:18px;padding:13px 14px 11px;box-shadow:0 8px 28px rgba(15,23,42,.07)}
body[data-view="new_conversation"] .new-task-box>textarea{height:100px;padding:5px 4px 14px;font-size:15px;resize:none}
body[data-view="new_conversation"] .new-task-context{gap:9px}
body[data-view="new_conversation"] .new-task-context .attach-button{border:0;border-radius:50%;background:#f4f5f6}
body[data-view="new_conversation"] .new-task-context .composer-model-picker{margin-left:auto}
body[data-view="new_conversation"] .new-task-context .composer-model-picker>summary{background:transparent;font-size:12px}
body[data-view="new_conversation"] .new-task-context .send{margin-left:0}
body[data-view="new_conversation"] .new-context-more{display:none}
body[data-view="new_conversation"] .new-task-status{display:none}
body[data-view="new_conversation"] .new-task-status[data-state="error"]{display:block}
.new-project-picker{position:relative;margin:0 0 8px 10px;z-index:8}
.new-project-picker-button{display:inline-flex;align-items:center;gap:8px;max-width:min(430px,80vw);border:0;border-radius:9px;background:#f1f2f3;padding:7px 10px;color:#2f3439;cursor:pointer}
.new-project-picker-button span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.new-project-picker-button small{color:#7d858c}
.new-project-picker-panel{position:absolute;left:0;bottom:calc(100% + 8px);width:min(350px,calc(100vw - 64px));padding:8px;border:1px solid #dfe2e5;border-radius:13px;background:#fff;box-shadow:0 18px 48px rgba(15,23,42,.16)}
.new-project-picker-panel[hidden]{display:none}.new-project-picker-panel input{width:100%;border:0;border-bottom:1px solid #eceff1;padding:9px 8px 10px;outline:0;background:#fff}
.new-project-list{max-height:220px;overflow:auto;padding:5px 0}.new-project-option{display:flex;width:100%;align-items:center;gap:8px;border:0;border-radius:8px;background:#fff;padding:9px;text-align:left;cursor:pointer}.new-project-option:hover,.new-project-option[aria-selected="true"]{background:#f0f1f2}.new-project-option span{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.new-project-option b{font-weight:500}
.new-project-picker-actions{border-top:1px solid #eceff1;padding-top:5px}.new-project-picker-actions button{display:block;width:100%;border:0;border-radius:8px;background:#fff;padding:9px;text-align:left;cursor:pointer}.new-project-picker-actions button:hover{background:#f0f1f2}
.inline-project-create{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:7px;padding:7px 4px 2px}.inline-project-create[hidden]{display:none}.inline-project-create input{border:1px solid #dfe2e5;border-radius:8px;padding:8px}.inline-project-create button{border:0;border-radius:8px;background:#111;color:#fff;padding:8px 11px;cursor:pointer}
@media(max-width:760px){body[data-view="new_conversation"] .new-task-stage{padding:30px 14px 48px}body[data-view="new_conversation"] .new-task-shell h1{margin-top:10vh;font-size:23px}.new-project-picker{margin-left:2px}}
"""
_WORKSPACE_CREATION_DIALOGS = """
<script data-t-one-workspace-creation="true">
(()=>{
  const taskButton=document.getElementById('newTask');
  if(taskButton)taskButton.onclick=()=>location.assign('/desktop?view=new');
  if(document.body.dataset.view!=='new_conversation')return;
  document.body.dataset.codexNewConversationUi='true';
  const shell=document.querySelector('.new-task-shell'),box=document.querySelector('.new-task-box'),project=document.getElementById('newProject'),heading=document.getElementById('newTaskHeading'),message=document.getElementById('message');
  if(!shell||!box||!project)return;
  heading.textContent='要在 T One 里完成什么？';
  message.placeholder='随心输入';
  const picker=document.createElement('div');picker.className='new-project-picker';picker.innerHTML=`<button type="button" class="new-project-picker-button" id="newProjectPickerButton" aria-expanded="false"><span id="newProjectPickerLabel"></span><small>⌄</small></button><div class="new-project-picker-panel" id="newProjectPickerPanel" hidden><input id="newProjectSearch" type="search" placeholder="搜索项目" autocomplete="off"><div class="new-project-list" id="newProjectList"></div><div class="new-project-picker-actions"><button type="button" id="showInlineProjectCreate">＋ 新建项目</button></div><div class="inline-project-create" id="inlineProjectCreate" hidden><input id="inlineProjectName" maxlength="100" placeholder="项目名称"><button type="button" id="saveInlineProject">创建</button></div></div>`;
  box.before(picker);
  const button=document.getElementById('newProjectPickerButton'),panel=document.getElementById('newProjectPickerPanel'),label=document.getElementById('newProjectPickerLabel'),list=document.getElementById('newProjectList'),search=document.getElementById('newProjectSearch'),create=document.getElementById('inlineProjectCreate'),name=document.getElementById('inlineProjectName');
  async function createRecord(method,payload,endpoint){
    if(window.pywebview?.api?.[method])return await window.pywebview.api[method](payload);
    if(window.teelabDesktop?.isDesktop&&window.teelabDesktop?.invoke)return await window.teelabDesktop.invoke(method,payload);
    const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const result=await response.json();
    if(!response.ok&&!result?.error)result.error='创建失败。';
    return result;
  }
  function sync(){label.textContent=project.value?(project.selectedOptions[0]?.textContent||'选择项目'):'不在项目中工作';}
  function render(){const query=search.value.trim().toLowerCase();list.replaceChildren();[...project.options].forEach(option=>{const text=option.value?option.textContent:'不在项目中工作';if(query&&!text.toLowerCase().includes(query))return;const row=document.createElement('button');row.type='button';row.className='new-project-option';row.dataset.projectId=option.value;row.setAttribute('aria-selected',String(option.value===project.value));row.innerHTML='<span><b></b></span><small></small>';row.querySelector('b').textContent=text;row.querySelector('small').textContent=option.value===project.value?'已选择':'';row.onclick=()=>{project.value=option.value;project.dispatchEvent(new Event('change',{bubbles:true}));sync();panel.hidden=true;button.setAttribute('aria-expanded','false');};list.append(row);});
  }
  button.onclick=event=>{event.stopPropagation();panel.hidden=!panel.hidden;button.setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden){render();requestAnimationFrame(()=>search.focus());}};
  search.oninput=render;document.getElementById('showInlineProjectCreate').onclick=()=>{create.hidden=false;name.focus();};
  document.getElementById('saveInlineProject').onclick=async()=>{const projectName=name.value.replace(/\\s+/g,' ').trim();if(!projectName)return name.focus();const save=document.getElementById('saveInlineProject');try{save.disabled=true;const result=await createRecord('create_workspace_project',{name:projectName,description:''},'/api/v1/workspace/projects');if(!result?.ok||!result.project?.id)throw new Error(result?.error||'项目没有创建成功。');project.append(new Option(result.project.name||projectName,result.project.id));project.value=result.project.id;project.dispatchEvent(new Event('change',{bubbles:true}));name.value='';create.hidden=true;sync();render();}catch(error){const status=document.getElementById('newTaskStatus');status.textContent=error.message||'项目没有创建成功。';status.dataset.state='error';}finally{save.disabled=false;}};
  document.addEventListener('click',event=>{if(!picker.contains(event.target)){panel.hidden=true;button.setAttribute('aria-expanded','false');}});sync();
})();
</script>
"""
_COMMERCE_PROFILE_EDITOR_CSS = """
.u12-commerce-editor{margin:12px 0;padding:12px;border:1px solid var(--line);border-radius:10px;background:#fbfcfc;display:grid;gap:10px}
.u12-commerce-editor h3{margin:0;font-size:13px}.u12-commerce-editor>p{margin:0;color:var(--muted);font-size:10px;line-height:1.5}
.u12-commerce-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.u12-commerce-grid label{display:grid;gap:5px;color:var(--muted);font-size:10px}.u12-commerce-grid .wide{grid-column:1/-1}
.u12-commerce-grid input,.u12-commerce-grid select{width:100%;min-width:0;border:1px solid var(--line);border-radius:7px;background:#fff;color:var(--text);padding:8px;font-size:11px}.u12-commerce-grid select[multiple]{min-height:92px}
.u12-commerce-actions{display:flex;align-items:center;gap:9px}.u12-commerce-actions button{border:1px solid #111;border-radius:7px;background:#111;color:#fff;padding:8px 12px;cursor:pointer;font-size:11px}.u12-commerce-actions [role=status]{font-size:10px;color:var(--muted)}.u12-commerce-actions [data-state=ok]{color:var(--accent)}.u12-commerce-actions [data-state=error]{color:#b91c1c}
@media(max-width:760px){.u12-commerce-grid{grid-template-columns:1fr}.u12-commerce-grid .wide{grid-column:auto}}
"""
_U16_MESSAGE_IMPORT_CSS = """
.u16-message-import{margin:12px 0;padding:12px;border:1px solid var(--line);border-radius:9px;background:#fbfcfc}.u16-message-import h3{margin:0 0 5px;font-size:13px}.u16-message-import>p{margin:0;color:var(--muted);font-size:10px;line-height:1.55}.u16-message-import-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:10px}.u16-message-import-grid label{display:grid;gap:4px;color:var(--muted);font-size:9px}.u16-message-import-grid input,.u16-message-import-grid select{min-width:0;border:1px solid var(--line);border-radius:6px;background:#fff;padding:7px;font:inherit}.u16-message-import-grid .wide{grid-column:1/-1}.u16-message-import-actions{display:flex;align-items:center;gap:9px;margin-top:9px}.u16-message-import-actions button{border:1px solid #111;border-radius:6px;background:#111;color:#fff;padding:7px 9px;font-size:10px;cursor:pointer}.u16-message-import-actions span{font-size:9px;color:var(--muted)}.u16-message-import-actions span[data-state=error]{color:#a3342b}.u16-message-import-actions span[data-state=ok]{color:#17685e}@media(max-width:760px){.u16-message-import-grid{grid-template-columns:1fr}.u16-message-import-grid .wide{grid-column:auto}}
"""
_U15_SETTLEMENT_IMPORT_CSS = """
.u15-settlement-import{margin:12px 0;border:1px solid var(--line);border-radius:10px;background:#fbfcfc}.u15-settlement-import>summary{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:11px 12px;cursor:pointer;list-style:none}.u15-settlement-import>summary::-webkit-details-marker{display:none}.u15-settlement-import>summary b{font-size:12px}.u15-settlement-import>summary span{color:var(--muted);font-size:9px}.u15-settlement-body{border-top:1px solid var(--line);padding:12px}.u15-settlement-body>p{margin:0;color:var(--muted);font-size:10px;line-height:1.55}.u15-settlement-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:10px}.u15-settlement-grid label{display:grid;gap:4px;color:var(--muted);font-size:9px}.u15-settlement-grid input,.u15-settlement-grid select{min-width:0;border:1px solid var(--line);border-radius:6px;background:#fff;padding:7px;font:inherit}.u15-settlement-grid .wide{grid-column:1/-1}.u15-settlement-actions{display:flex;align-items:center;gap:9px;margin-top:10px}.u15-settlement-actions button{border:1px solid #111;border-radius:6px;background:#111;color:#fff;padding:7px 10px;font-size:10px;cursor:pointer}.u15-settlement-actions span{font-size:9px;color:var(--muted)}.u15-settlement-actions span[data-state=error]{color:#a3342b}.u15-settlement-actions span[data-state=ok]{color:#17685e}@media(max-width:820px){.u15-settlement-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:560px){.u15-settlement-grid{grid-template-columns:1fr}.u15-settlement-grid .wide{grid-column:auto}}
"""
_PROJECT_TOGGLE_A11Y_SYNC = (
    '<script data-t-one-project-toggle-a11y="true">'
    'document.querySelectorAll("details[data-project-section]").forEach(section=>{'
    'const toggle=section.querySelector("[data-project-toggle]");'
    'if(!toggle)return;'
    'const sync=()=>toggle.setAttribute("aria-expanded", section.open ? "true" : "false");'
    'section.addEventListener("toggle", sync);sync();'
    '});'
    '</script>'
)


def _add_global_platform_catalog(html: str, root: _Path) -> str:
    """Keep real store rollups and remove unconnected registry rows from daily UI."""

    del root
    return _remove_html_elements_by_attribute(
        html,
        "data-connection-state",
        "not_connected",
    )


def _ensure_composer_strategy_choices(html: str) -> str:
    """Keep T One conversation strategies available for every AI provider."""

    if _REVIEWED_STRATEGY_OPTIONS_JS in html:
        return html
    return html.replace(
        _LEGACY_STRATEGY_OPTIONS_JS,
        _REVIEWED_STRATEGY_OPTIONS_JS,
        1,
    )


def _ensure_daily_ui_readability(html: str) -> str:
    if _DAILY_UI_READABILITY_CSS.strip() in html:
        return html
    return html.replace("</style>", _DAILY_UI_READABILITY_CSS + "</style>", 1)


def _remove_empty_sidebar_sections(html: str) -> str:
    """Hide legacy sidebar headings only when their section is empty."""

    empty_sections = (
        '<div class="sidebar-section-label">置顶</div>'
        '<div class="sidebar-section-body pinned-items"></div>',
        '<div class="sidebar-section-label">任务</div>'
        '<div class="sidebar-section-body standalone-items" data-drop-project=""></div>',
    )
    for section in empty_sections:
        html = html.replace(section, "", 1)
    return html


def _ensure_account_access_settings_section(html: str) -> str:
    """Give every settings navigation entry a real, non-executing section."""

    if 'id="settings-account-access"' in html:
        return html
    marker = '<section class="settings-page-section" id="settings-erp-finance"'
    if marker not in html:
        return html
    return html.replace(marker, _ACCOUNT_ACCESS_SETTINGS_SECTION + marker, 1)


def _ensure_data_acquisition_settings_section(html: str) -> str:
    """Attach the truthful local-import workflow to the existing ERP settings page."""

    if 'data-data-acquisition-settings="true"' in html:
        return html
    marker = '<section class="settings-page-section" id="settings-erp-finance"'
    start = html.find(marker)
    if start < 0:
        return html
    next_section = html.find('<section class="settings-page-section"', start + len(marker))
    if next_section < 0:
        return html
    end = html.rfind("</section>", start, next_section)
    if end < 0:
        return html
    updated = html[:end] + _DATA_ACQUISITION_SETTINGS_BLOCK + html[end:]
    if "data-t-one-data-acquisition-style=true" not in updated:
        updated = updated.replace("</style>", _DATA_ACQUISITION_SETTINGS_CSS + "</style>", 1)
    if 'data-t-one-data-acquisition-script="true"' not in updated:
        updated = updated.replace("</body>", _DATA_ACQUISITION_SETTINGS_JS + "</body>", 1)
    return updated


_OPEN_TOOL_SETTINGS_CSS = """
/* data-t-one-open-tools-style=true */
.open-tool-intro{display:flex;align-items:flex-start;justify-content:space-between;gap:18px}.open-tool-intro p{margin:4px 0 0;color:var(--muted);font-size:12px;line-height:1.6}.open-tool-intro em{white-space:nowrap}
.open-tool-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px 14px;margin-top:14px}.open-tool-form label{display:grid;gap:6px;color:var(--muted);font-size:11px}.open-tool-form input,.open-tool-form select{min-width:0;border:1px solid var(--line);border-radius:7px;padding:9px 10px;background:#fff;color:var(--text);font:inherit}.open-tool-wide{grid-column:1/-1}.open-tool-store-scope{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px 14px;grid-column:1/-1}.open-tool-form button{justify-self:start;border:1px solid #111;border-radius:7px;padding:9px 13px;background:#111;color:#fff;cursor:pointer}.open-tool-status{margin:12px 0 0;color:var(--muted);font-size:12px}.open-tool-status[data-state=error]{color:#a3342b}.open-tool-status[data-state=success]{color:#17685e}.open-tool-list{margin-top:14px;border-top:1px solid var(--line)}.open-tool-row{display:flex;justify-content:space-between;gap:16px;padding:10px 0;border-bottom:1px solid var(--line);font-size:12px}.open-tool-row span{display:grid;gap:3px}.open-tool-row small{color:var(--muted)}.open-tool-row em{color:#17685e;font-style:normal;white-space:nowrap}
.desktop-control{margin-top:18px;border-top:1px solid var(--line);padding-top:16px}.desktop-control>summary{cursor:pointer;font-size:13px;font-weight:650}.desktop-control-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 12px;margin-top:12px}.desktop-control-grid label{display:grid;gap:5px;color:var(--muted);font-size:11px}.desktop-control-grid input,.desktop-control-grid select{min-width:0;border:1px solid var(--line);border-radius:7px;padding:8px 9px;background:#fff;color:var(--text);font:inherit}.desktop-control-wide{grid-column:1/-1}.desktop-control-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;grid-column:1/-1}.desktop-control-actions button{border:1px solid #111;border-radius:7px;padding:8px 11px;background:#111;color:#fff;cursor:pointer}.desktop-control-actions button.secondary{background:#fff;color:#111}.desktop-control-status{margin:10px 0 0;color:var(--muted);font-size:11px;line-height:1.55}.desktop-control-status[data-state=success]{color:#17685e}.desktop-control-status[data-state=error]{color:#a3342b}
@media(max-width:760px){.open-tool-intro{display:grid}.open-tool-form,.open-tool-store-scope,.desktop-control-grid{grid-template-columns:1fr}.open-tool-wide,.desktop-control-wide{grid-column:auto}.open-tool-row{align-items:flex-start}}
"""

_OPEN_TOOL_SETTINGS_JS = """
<script data-t-one-open-tools-script="true">
(()=>{
  const root=document.querySelector('[data-open-tool-registry="true"]');if(!root)return;
  const byId=id=>document.getElementById(id),scope=byId('openToolScope'),storeFields=byId('openToolStoreScope'),status=byId('openToolStatus'),list=byId('openToolList'),save=byId('openToolSave');
  function setStatus(message,state=''){status.textContent=message;if(state)status.dataset.state=state;else delete status.dataset.state;}
  function syncScope(){storeFields.hidden=scope.value!=='store';storeFields.querySelectorAll('input').forEach(input=>input.required=scope.value==='store');}
  function render(tools){list.replaceChildren();tools.forEach(tool=>{const row=document.createElement('div');row.className='open-tool-row';const copy=document.createElement('span');const name=document.createElement('b');name.textContent=tool.name||tool.id;const detail=document.createElement('small');const route=tool.scope?.mode==='store'?[tool.scope.platform,tool.scope.country_site,tool.scope.store_mode,tool.scope.store_binding_id].filter(Boolean).join(' / '):'通用范围';detail.textContent=(tool.kind||'工具')+' · '+route+(tool.availability_note?' · '+tool.availability_note:'');copy.append(name,detail);const state=document.createElement('em');state.textContent=tool.connected===true?'已连接':tool.installation_status==='not_installed'?'待安装':'未连接';state.dataset.state=tool.connected===true?'connected':tool.installation_status==='not_installed'?'pending-install':'disconnected';row.append(copy,state);list.append(row);});if(!tools.length){const empty=document.createElement('p');empty.className='open-tool-status';empty.textContent='还没有用户添加的工具。';list.append(empty);}}
  async function load(){try{const response=await fetch('/api/v1/tools',{credentials:'same-origin'});const payload=await response.json();if(!response.ok||!payload.ok)throw new Error(payload.error||'工具列表读取失败。');render(Array.isArray(payload.tools)?payload.tools:[]);}catch(error){setStatus(error instanceof Error?error.message:'工具列表读取失败。','error');}}
  scope.addEventListener('change',syncScope);syncScope();
  save.addEventListener('click',async()=>{const payload={name:byId('openToolName').value.trim(),kind:byId('openToolKind').value.trim(),connection_ref:byId('openToolConnection').value.trim(),credential_ref:byId('openToolCredential').value.trim(),capabilities:byId('openToolCapabilities').value.trim(),scope_mode:scope.value};['project_id','platform','country_site','store_mode','store_binding_id','account_id','execution_identity_ref'].forEach(key=>{const field=byId('openTool_'+key);payload[key]=field?field.value.trim():'';});if(!payload.name||!payload.kind||!payload.connection_ref){setStatus('请填写工具名称、类型和连接地址或本地路径。','error');return;}try{save.disabled=true;setStatus('正在保存本地工具记录...');const response=await fetch('/api/v1/tools',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const result=await response.json();if(!response.ok||!result.ok)throw new Error(result.error||'保存失败。');setStatus(result.deduplicated?'已合并重复记录；仍为未连接状态。':'已添加；验证连接前不会显示为已连接。','success');await load();}catch(error){setStatus(error instanceof Error?error.message:'保存失败。','error');}finally{save.disabled=false;}});
  const control=byId('desktopControl'),controlStatus=byId('desktopControlStatus');
  async function desktopCall(method,payload,withoutPayload=false){const api=window.pywebview?.api?.[method];if(typeof api==='function')return withoutPayload?await api():await api(payload);if(window.teelabDesktop?.isDesktop&&typeof window.teelabDesktop.invoke==='function')return withoutPayload?await window.teelabDesktop.invoke(method):await window.teelabDesktop.invoke(method,payload);throw new Error('请在 T One Windows 应用中使用本机控制。');}
  function setControlStatus(message,state=''){controlStatus.textContent=message;if(state)controlStatus.dataset.state=state;else delete controlStatus.dataset.state;}
  async function probeDesktop(){try{const snapshot=await desktopCall('desktop_control_snapshot',null,true);if(!snapshot?.ok||!snapshot?.available)throw new Error(snapshot?.error||'当前系统不支持本机控制。');byId('desktopMouseX').value=String(snapshot.cursor?.x??'');byId('desktopMouseY').value=String(snapshot.cursor?.y??'');control.dataset.available='true';setControlStatus('Windows 本机控制可用 · 鼠标、键盘、默认浏览器；受控店铺浏览器继续按具体环境隔离。','success');}catch(error){control.dataset.available='false';setControlStatus(error?.message||'本机控制检测失败。','error');}}
  byId('desktopControlProbe').addEventListener('click',probeDesktop);
  byId('desktopMouseRun').addEventListener('click',async()=>{try{setControlStatus('将在 1 秒后执行一次鼠标动作…');const result=await desktopCall('desktop_mouse_action',{action:byId('desktopMouseAction').value,x:Number(byId('desktopMouseX').value),y:Number(byId('desktopMouseY').value),delay_ms:1000,owner_confirmed:true});if(!result?.ok)throw new Error(result?.error||'鼠标动作失败。');setControlStatus('鼠标动作已执行一次 · '+String(result.receipt_path||''),'success');}catch(error){setControlStatus(error?.message||'鼠标动作失败。','error');}});
  byId('desktopKeyboardRun').addEventListener('click',async()=>{const text=byId('desktopKeyboardText').value;if(!text){setControlStatus('请输入要键入的文字。','error');return;}try{setControlStatus('3 秒内切换到目标输入框…');const result=await desktopCall('desktop_keyboard_action',{action:'type',text,delay_ms:3000,owner_confirmed:true});if(!result?.ok)throw new Error(result?.error||'键盘输入失败。');setControlStatus('键盘输入已执行一次 · '+String(result.receipt_path||''),'success');}catch(error){setControlStatus(error?.message||'键盘输入失败。','error');}});
  byId('desktopBrowserRun').addEventListener('click',async()=>{const url=byId('desktopBrowserUrl').value.trim();try{setControlStatus('正在交给默认浏览器打开…');const result=await desktopCall('desktop_browser_action',{action:'open_url',url,owner_confirmed:true});if(!result?.ok)throw new Error(result?.error||'浏览器打开失败。');setControlStatus('浏览器已接受地址 · '+String(result.receipt_path||''),'success');}catch(error){setControlStatus(error?.message||'浏览器打开失败。','error');}});
  load();
  probeDesktop();
})();
</script>
"""

_CLI_AI_ROUNDTRIP_CSS = """
/* data-t-one-cli-ai-roundtrip-style=true */
.cli-ai-roundtrip{margin-top:18px;border-top:1px solid var(--line);padding-top:18px}.cli-ai-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:18px}.cli-ai-heading h2{margin:0 0 5px;font-size:15px}.cli-ai-heading p{max-width:760px;margin:0;color:var(--muted);font-size:12px;line-height:1.65}.cli-ai-heading em{flex:none;border:1px solid #dfe5e7;border-radius:999px;padding:5px 9px;background:#f7f9f9;color:var(--muted);font-size:11px;font-style:normal}.cli-ai-heading em[data-state=success]{border-color:#a9d7ce;background:#edf8f5;color:#17685e}.cli-ai-heading em[data-state=error]{border-color:#e3b7b2;background:#fff4f2;color:#a3342b}
.cli-ai-form{display:grid;grid-template-columns:minmax(180px,.6fr) minmax(260px,1.4fr);gap:12px 14px;margin-top:16px}.cli-ai-form label{display:grid;gap:6px;color:var(--muted);font-size:11px}.cli-ai-form select,.cli-ai-form textarea{min-width:0;border:1px solid var(--line);border-radius:7px;padding:9px 10px;background:#fff;color:var(--text);font:inherit;outline:none}.cli-ai-form textarea{min-height:96px;resize:vertical;line-height:1.55}.cli-ai-form select:focus,.cli-ai-form textarea:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(15,118,110,.1)}.cli-ai-prompt{grid-column:1/-1}.cli-ai-actions{grid-column:1/-1;display:flex;align-items:center;gap:12px;flex-wrap:wrap}.cli-ai-actions button{border:1px solid #111;border-radius:7px;padding:9px 13px;background:#111;color:#fff;cursor:pointer}.cli-ai-actions button:disabled{cursor:wait;opacity:.55}.cli-ai-actions small{color:var(--muted);line-height:1.5}.cli-ai-result{grid-column:1/-1;margin:0;border:1px solid var(--line);border-radius:8px;padding:12px;background:#f8faf9;color:var(--text);font:12px/1.65 "Segoe UI","Microsoft YaHei",sans-serif;white-space:pre-wrap;overflow-wrap:anywhere}.cli-ai-result:empty{display:none}
.multi-ai-collaboration{grid-column:1/-1;margin-top:4px;border-top:1px solid var(--line);padding-top:16px}.multi-ai-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.multi-ai-head h3{margin:0 0 4px;font-size:13px}.multi-ai-head p{margin:0;color:var(--muted);font-size:11px;line-height:1.55}.multi-ai-head em{font-style:normal;font-size:10px;color:var(--muted)}.multi-ai-head em[data-state=success]{color:#17685e}.multi-ai-head em[data-state=error]{color:#a3342b}.multi-ai-participants{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px}.multi-ai-participant{display:flex!important;grid-template-columns:none!important;flex-direction:row;align-items:flex-start;gap:8px!important;border:1px solid var(--line);border-radius:8px;padding:9px;background:#fff;color:var(--text)!important}.multi-ai-participant input{margin-top:2px}.multi-ai-participant span{display:grid;gap:2px}.multi-ai-participant small{color:var(--muted);font-size:10px}.multi-ai-participant[data-callable=false]{opacity:.62;background:#f7f8f8}.multi-ai-result{margin-top:12px;max-height:360px;overflow:auto}
.multi-ai-configured{margin-top:10px;border:1px solid var(--line);border-radius:8px;background:#fafbfb}.multi-ai-configured>summary{display:flex;align-items:center;gap:8px;padding:9px 10px;cursor:pointer;color:var(--muted);font-size:10px;list-style:none}.multi-ai-configured>summary::-webkit-details-marker{display:none}.multi-ai-configured>summary b{color:var(--text);font-size:11px}.multi-ai-configured>summary span{margin-left:auto}.multi-ai-configured .multi-ai-participants{margin:0;padding:0 8px 8px}.multi-ai-configured[hidden]{display:none}
.existing-login-web-ai{grid-column:1/-1;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.existing-login-web-ai article{border:1px solid var(--line);border-radius:8px;padding:10px;background:#fafbfb}.existing-login-web-ai b{display:block;font-size:12px}.existing-login-web-ai small{display:block;margin-top:4px;color:var(--muted);font-size:10px;line-height:1.5}.existing-login-web-ai em{display:inline-block;margin-top:6px;color:#17685e;font-size:10px;font-style:normal}
@media(max-width:760px){.cli-ai-heading,.cli-ai-form,.multi-ai-head{display:grid}.cli-ai-heading em{justify-self:start}.cli-ai-form,.multi-ai-participants{grid-template-columns:1fr}.cli-ai-prompt,.cli-ai-actions,.cli-ai-result,.multi-ai-collaboration{grid-column:auto}}
"""

_CLI_AI_ROUNDTRIP_JS = """
<script data-t-one-cli-ai-roundtrip-script="true">
(()=>{
  const root=document.querySelector('[data-cli-ai-roundtrip="true"]');if(!root)return;
  const project=document.getElementById('cliAiProject'),task=document.getElementById('multiAiTask'),prompt=document.getElementById('cliAiPrompt'),run=document.getElementById('cliAiRun'),status=document.getElementById('cliAiStatus'),result=document.getElementById('cliAiResult'),multiRun=document.getElementById('multiAiRun'),multiStatus=document.getElementById('multiAiStatus'),primaryParticipants=document.getElementById('multiAiPrimaryParticipants'),configuredDetails=document.getElementById('multiAiConfiguredDetails'),configuredParticipants=document.getElementById('multiAiConfiguredParticipants'),configuredCount=document.getElementById('multiAiConfiguredCount'),multiResult=document.getElementById('multiAiResult');
  function setStatus(message,state=''){status.textContent=message;if(state)status.dataset.state=state;else delete status.dataset.state;}
  async function call(method,payload,withoutPayload=false){const api=window.pywebview?.api?.[method];if(typeof api==='function')return withoutPayload?await api():await api(payload);if(window.teelabDesktop?.isDesktop&&typeof window.teelabDesktop.invoke==='function')return withoutPayload?await window.teelabDesktop.invoke(method):await window.teelabDesktop.invoke(method,payload);throw new Error('请在 T One 桌面应用中使用本机 AI 连接。');}
  async function probe(){try{setStatus('正在检测本机 Codex CLI…');const snapshot=await call('cli_ai_connector_snapshot',null,true);root.dataset.cliInstalled=String(Boolean(snapshot?.installed));root.dataset.cliReady=String(Boolean(snapshot?.ready));if(!snapshot?.ok||!snapshot?.ready)throw new Error(snapshot?.error||snapshot?.authentication_status||'Codex CLI 尚未登录。');setStatus('Codex CLI 已连接 · '+String(snapshot.version||'已登录')+' · 只读沙箱','success');run.disabled=false;}catch(error){root.dataset.cliReady='false';run.disabled=true;setStatus(error?.message||'Codex CLI 检测失败。','error');}}
  function syncTaskOptions(){const selected=task.value;let first='';[...task.options].forEach(option=>{const visible=!option.dataset.project||option.dataset.project===project.value;option.hidden=!visible;option.disabled=!visible;if(visible&&!first)first=option.value;});if(task.selectedOptions[0]?.disabled)task.value=first;else task.value=selected;}
  function selectedParticipants(){return [...root.querySelectorAll('.multi-ai-participants input[type=checkbox]:checked')].map(input=>input.value);}
  function syncMultiRun(){multiRun.disabled=selectedParticipants().length<2;}
  function renderParticipants(snapshot){const roles={operator:'执行分析',reviewer:'独立复核',analyst:'补充分析',coordinator:'协调汇总'},states={verified_callable:'近期实测可用',configured_callable_requires_live_result:'已配置，调用时实测',installed_no_automated_return_interface:'已安装，暂无自动回传接口',not_installed:'未安装',not_ready:'未就绪'};primaryParticipants.replaceChildren();configuredParticipants.replaceChildren();const recommended=new Set(snapshot?.recommended_participant_ids||[]),configured=[];for(const item of snapshot?.participants||[]){const primary=item.status==='verified_callable'||!(item.callable&&item.ready),target=primary?primaryParticipants:configuredParticipants;const label=document.createElement('label');label.className='multi-ai-participant';label.dataset.callable=String(Boolean(item.callable&&item.ready));const input=document.createElement('input');input.type='checkbox';input.value=String(item.id||'');input.disabled=!(item.callable&&item.ready);input.checked=input.disabled?false:recommended.has(input.value);const copy=document.createElement('span');const name=document.createElement('b');name.textContent=String(item.name||item.id||'AI');const detail=document.createElement('small');detail.textContent=[item.model,roles[item.role]||item.role,states[item.status]||item.status].filter(Boolean).join(' · ');copy.append(name,detail);label.append(input,copy);target.append(label);if(!primary)configured.push(item);}configuredCount.textContent=String(configured.length)+' 个';configuredDetails.hidden=configured.length===0;root.querySelectorAll('.multi-ai-participants input').forEach(input=>input.addEventListener('change',syncMultiRun));syncMultiRun();}
  async function probeMulti(){try{multiStatus.textContent='正在读取可调用 AI…';const snapshot=await call('multi_ai_collaboration_snapshot',null,true);if(!snapshot?.ok)throw new Error(snapshot?.error||'多 AI 状态读取失败。');renderParticipants(snapshot);const participants=Array.isArray(snapshot.participants)?snapshot.participants:[],verified=participants.filter(item=>item.callable&&item.ready&&item.status==='verified_callable').length,configured=participants.filter(item=>item.callable&&item.ready&&item.status!=='verified_callable').length,unavailable=participants.filter(item=>!(item.callable&&item.ready)).length;multiStatus.textContent='近期实测 '+verified+'；已配置待调用 '+configured+'；不可自动 '+unavailable;multiStatus.dataset.state=verified>=2?'success':'error';}catch(error){multiRun.disabled=true;multiStatus.textContent=error?.message||'多 AI 状态读取失败。';multiStatus.dataset.state='error';}}
  run.addEventListener('click',async()=>{const message=prompt.value.trim();if(!project.value){setStatus('请先选择本地项目。','error');return;}if(!message){setStatus('请输入要回传给 AI 的信息。','error');return;}run.disabled=true;result.textContent='';setStatus('正在通过 Codex CLI 发送，并等待结果回传到本页面…');try{const response=await call('run_cli_ai_roundtrip',{provider_id:'codex-cli',project_id:project.value,task_id:'t-one-page-roundtrip',message,owner_confirmed:true});if(!response?.ok)throw new Error(response?.error||'Codex CLI 没有返回可用结果。');result.textContent=String(response.message||'已收到空结果。');const receipt=response.run?.receipt_path||response.run?.result_path||'';setStatus('双向回传成功'+(receipt?' · 回执：'+receipt:''),'success');}catch(error){setStatus(error?.message||'双向回传失败。','error');}finally{run.disabled=root.dataset.cliReady!=='true';}});
  multiRun.addEventListener('click',async()=>{const message=prompt.value.trim(),participantIds=selectedParticipants();if(!project.value){multiStatus.textContent='请先选择本地项目。';multiStatus.dataset.state='error';return;}if(!message){multiStatus.textContent='请输入要交给多 AI 的信息。';multiStatus.dataset.state='error';return;}if(participantIds.length<2){multiStatus.textContent='至少选择两个可调用的 AI。';multiStatus.dataset.state='error';return;}multiRun.disabled=true;multiResult.textContent='';multiStatus.textContent='正在并行发送，等待各 AI 回传…';delete multiStatus.dataset.state;try{const response=await call('run_multi_ai_collaboration',{project_id:project.value,task_id:task.value,message,participant_ids:participantIds,owner_confirmed:true});if(!response?.ok)throw new Error(response?.error||'多 AI 没有返回可用结果。');multiResult.textContent=String(response.message||'已收到空结果。');multiStatus.textContent='已收到 '+Number(response.successful_participant_count||0)+'/'+Number(response.participant_count||0)+' 个结果'+(response.receipt_path?' · 回执：'+response.receipt_path:'');multiStatus.dataset.state=response.status==='completed'?'success':'error';}catch(error){multiStatus.textContent=error?.message||'多 AI 协作失败。';multiStatus.dataset.state='error';}finally{syncMultiRun();}});
  project.addEventListener('change',syncTaskOptions);syncTaskOptions();probe();probeMulti();
})();
</script>
"""

_TASK_AI_ROUNDTRIP_JS = """
<script data-t-one-task-ai-roundtrip-script="true">
(()=>{
  const provider=document.getElementById('taskAiProviderQuick'),model=document.getElementById('taskModelByAiQuick'),summary=document.getElementById('modelPickerSummary'),status=document.getElementById('modelPickerStatus'),send=document.getElementById('send'),box=document.getElementById('message');
  if(!provider||!model||!send||!box||typeof TASK!=='object'||!TASK.project_id||!(TASK.task_id||TASK.id))return;
  const projectId=String(TASK.project_id),taskId=String(TASK.task_id||TASK.id),routes=new Set(['codex-cli','codex-luna-cli','project-multi-ai']),preferenceKey='tOneTaskAiRoundtripRoute:v1:'+projectId+':'+taskId;
  let running=false,profileSnapshot=null,multiSnapshot=null,cliSnapshot=null;
  async function call(method,payload,withoutPayload=false){const api=window.pywebview?.api?.[method];if(typeof api==='function')return withoutPayload?await api():await api(payload);if(window.teelabDesktop?.isDesktop&&typeof window.teelabDesktop.invoke==='function')return withoutPayload?await window.teelabDesktop.invoke(method):await window.teelabDesktop.invoke(method,payload);throw new Error('请在 T One Windows 桌面版中使用项目 AI 回传。');}
  function route(){return routes.has(provider.value)?provider.value:'';}
  function ensureOption(value,label){let option=[...provider.options].find(item=>item.value===value);if(!option){option=new Option(label,value);provider.append(option);}option.textContent=label;return option;}
  function selectedProfile(){return (profileSnapshot?.projects||[]).find(item=>String(item.id||'')===projectId)||{};}
  function routeLabel(value){if(value==='codex-cli')return 'Codex CLI';if(value==='codex-luna-cli')return 'GPT-5.6 Luna';const count=(selectedProfile().participant_ids||[]).length;return '项目多 AI 协作'+(count?' · '+count+' 个':'');}
  function applyRouteUi(){const selected=route();if(!selected)return;const isCli=selected==='codex-cli'||selected==='codex-luna-cli',isLuna=selected==='codex-luna-cli';model.disabled=false;model.replaceChildren(new Option(isLuna?'GPT-5.6 Luna · Codex 当前登录':isCli?'Codex CLI · 当前登录':'按项目保存的 AI 组合',selected));model.value=selected;if(typeof taskModelQuick!=='undefined'&&taskModelQuick)taskModelQuick.value='';if(typeof taskModel!=='undefined'&&taskModel)taskModel.value='';if(summary)summary.textContent=routeLabel(selected)+' · 真实回传';if(status)status.textContent=isLuna?'T One 项目对话 → GPT-5.6 Luna；回答会返回当前对话。':isCli?'T One 项目对话 → Codex CLI；回答会返回当前对话。':'同一条项目消息并行发送给已保存的 AI 组合，各结果返回当前对话。';try{localStorage.setItem(preferenceKey,selected);}catch(_error){}}
  function restoreNormalRoute(){try{localStorage.removeItem(preferenceKey);}catch(_error){}}
  function setResult(node,text,metaText,state='connected'){node.replaceChildren(document.createTextNode(String(text||'没有拿到可用结果。')));const meta=document.createElement('small');meta.className='message-meta';meta.dataset.modelState=state;meta.textContent=metaText;node.appendChild(meta);}
  async function messageWithAttachments(message){let text=message;if(typeof pendingChatAttachments==='undefined'||!pendingChatAttachments.length)return text;const snapshot=[...pendingChatAttachments];if(typeof saveChatAttachments!=='function'||typeof chatAttachmentInstruction!=='function')throw new Error('当前附件不能交给本机 AI，请先只发送文字。');const intake=await saveChatAttachments(projectId,snapshot);text=chatAttachmentInstruction(message||'请读取本轮项目附件并返回分析结果。',intake,snapshot);if(typeof clearChatAttachments==='function')clearChatAttachments();return text;}
  async function runSelected(){const selected=route();if(!selected||running)return false;const typed=box.value.trim();if(!typed&&(typeof pendingChatAttachments==='undefined'||!pendingChatAttachments.length))return true;running=true;send.disabled=true;let pending=null;try{const message=await messageWithAttachments(typed);if(typeof addMessage!=='function')throw new Error('当前对话回显组件不可用。');addMessage('user',typed||'请读取本轮项目附件并返回分析结果。');box.value='';const isCli=selected==='codex-cli'||selected==='codex-luna-cli',isLuna=selected==='codex-luna-cli';pending=addMessage('assistant',isCli?'正在通过 '+(isLuna?'GPT-5.6 Luna':'Codex CLI')+' 发送，并等待结果回传到当前对话…':'正在并行发送给项目 AI 组合，并等待各结果回传…');let response;if(isCli){response=await call('run_cli_ai_roundtrip',{provider_id:selected,model:isLuna?'gpt-5.6-luna':'',project_id:projectId,task_id:taskId,message,owner_confirmed:true});if(!response?.ok)throw new Error(response?.error||(isLuna?'GPT-5.6 Luna':'Codex CLI')+' 没有返回可用结果。');const receipt=response.run?.receipt_path||response.run?.result_path||'';setResult(pending,response.message,'真实回传 · '+(isLuna?'GPT-5.6 Luna':'Codex CLI')+' · 结果和回执已保存到当前项目文件夹'+(receipt?' · '+receipt:''));}else{response=await call('run_multi_ai_collaboration',{project_id:projectId,task_id:taskId,message,participant_ids:selectedProfile().participant_ids||[],owner_confirmed:true});if(!response?.ok)throw new Error(response?.error||'项目多 AI 没有返回可用结果。');setResult(pending,response.message,'真实回传 · '+Number(response.successful_participant_count||0)+'/'+Number(response.participant_count||0)+' 个 AI · 结果和回执已保存到当前项目文件夹'+(response.receipt_path?' · '+response.receipt_path:''),response.status==='completed'?'connected':'local');}}catch(error){if(!pending&&typeof addMessage==='function')pending=addMessage('assistant','');if(pending)setResult(pending,'AI 回传失败：'+String(error?.message||error)+'；未执行真实店铺动作。','回传失败 · 外部店铺动作 0','local');}finally{running=false;send.disabled=false;}return true;}
  async function probe(){try{[cliSnapshot,multiSnapshot,profileSnapshot]=await Promise.all([call('cli_ai_connector_snapshot',null,true),call('multi_ai_collaboration_snapshot',null,true),call('project_capability_profile_snapshot',null,true)]);const cli=ensureOption('codex-cli','Codex CLI · '+(cliSnapshot?.ready?'已连接':'未就绪'));cli.disabled=!cliSnapshot?.ready;const lunaParticipant=(multiSnapshot?.participants||[]).find(item=>String(item.id||'')==='codex-luna-cli')||{};const luna=ensureOption('codex-luna-cli','GPT-5.6 Luna · '+(lunaParticipant.callable&&lunaParticipant.ready?'已连接':'未就绪'));luna.disabled=!(lunaParticipant.callable&&lunaParticipant.ready);const profile=selectedProfile(),ids=profile.participant_ids||[],available=new Set((multiSnapshot?.participants||[]).filter(item=>item.callable&&item.ready).map(item=>String(item.id||''))),readyCount=ids.filter(id=>available.has(String(id))).length;const multi=ensureOption('project-multi-ai','项目多 AI 协作 · '+(ids.length>=2&&readyCount===ids.length?ids.length+' 个可调用':'配置不足'));multi.disabled=!(ids.length>=2&&readyCount===ids.length);let saved='';try{saved=localStorage.getItem(preferenceKey)||'';}catch(_error){}if(routes.has(saved)&&![...provider.options].find(item=>item.value===saved)?.disabled){provider.value=saved;applyRouteUi();}}catch(error){ensureOption('codex-cli','Codex CLI · 检测失败').disabled=true;ensureOption('codex-luna-cli','GPT-5.6 Luna · 检测失败').disabled=true;ensureOption('project-multi-ai','项目多 AI 协作 · 检测失败').disabled=true;if(status)status.textContent=String(error?.message||'项目 AI 回传检测失败。');}}
  provider.addEventListener('change',()=>{if(route())applyRouteUi();else restoreNormalRoute();});
  const originalSend=send.onclick;send.onclick=event=>route()?(event?.preventDefault(),runSelected()):originalSend?.call(send,event);
  box.addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&route()){event.preventDefault();event.stopImmediatePropagation();runSelected();}},true);
  probe();
})();
</script>
"""

_BROWSER_AI_ROUNDTRIP_JS = """
<script data-t-one-browser-ai-roundtrip-script="true">
(()=>{
  const provider=document.getElementById('taskAiProviderQuick'),model=document.getElementById('taskModelByAiQuick'),summary=document.getElementById('modelPickerSummary'),status=document.getElementById('modelPickerStatus'),send=document.getElementById('send'),box=document.getElementById('message');
  if(!provider||!model||!send||!box||typeof TASK!=='object'||!TASK.project_id||!(TASK.task_id||TASK.id))return;
  const routes=new Map([['chatgpt-browser','ChatGPT 网页 · 已登录标签页'],['gemini-browser','Gemini 网页 · 已登录谷歌账号']]);
  let running=false;
  async function call(method,payload,withoutPayload=false){const api=window.pywebview?.api?.[method];if(typeof api==='function')return withoutPayload?await api():await api(payload);if(window.teelabDesktop?.isDesktop&&typeof window.teelabDesktop.invoke==='function')return withoutPayload?await window.teelabDesktop.invoke(method):await window.teelabDesktop.invoke(method,payload);throw new Error('请在 T One Windows 桌面版中使用已登录网页 AI 回传。');}
  function selected(){return routes.has(provider.value)?provider.value:'';}
  function ensureOption(value,label){let option=[...provider.options].find(item=>item.value===value);if(!option){option=new Option(label,value);provider.append(option);}option.textContent=label;return option;}
  function apply(){const route=selected();if(!route)return;model.disabled=false;model.replaceChildren(new Option(routes.get(route),route));model.value=route;if(summary)summary.textContent=routes.get(route)+' · 任务同一对话回传';if(status)status.textContent='复用当前任务在现有登录标签页的同一对话；共享当前店铺与本轮 Agent/Skill；不读取 Cookie/密码，不打开会员页。';}
  function result(node,text,metaText,state='connected'){node.replaceChildren(document.createTextNode(String(text||'没有拿到可用结果。')));const meta=document.createElement('small');meta.className='message-meta';meta.dataset.modelState=state;meta.textContent=metaText;node.appendChild(meta);}
  async function run(){const route=selected();if(!route||running)return false;const message=box.value.trim();if(!message)return true;running=true;send.disabled=true;let pending=null;try{if(typeof addMessage!=='function')throw new Error('当前对话回显组件不可用。');addMessage('user',message);box.value='';pending=addMessage('assistant','正在把当前店铺、任务和本轮 Agent/Skill 一起发送到同一个已登录 '+(route==='chatgpt-browser'?'ChatGPT':'Gemini')+' 对话，并等待回复回传…');const response=await call('run_browser_ai_roundtrip',{provider_id:route,project_id:String(TASK.project_id),task_id:String(TASK.task_id||TASK.id),message,owner_confirmed:true,timeout_seconds:300});if(!response?.ok)throw new Error(response?.error||'网页 AI 没有返回可用结果。');const receipt=response.job?.result_id||response.job?.id||'';const scope=response.job?.task_context_shared?' · 已共享店铺/Agent/Skill':' · 未找到任务上下文';const thread=response.job?.conversation_reused?' · 复用同一对话':' · 已绑定当前对话';result(pending,response.message,'真实回传 · '+routes.get(route)+thread+scope+' · 结果和回执已保存到当前项目文件夹'+(receipt?' · '+receipt:''));}catch(error){if(!pending&&typeof addMessage==='function')pending=addMessage('assistant','');if(pending)result(pending,'网页 AI 回传失败：'+String(error?.message||error)+'；未执行真实店铺动作。','回传失败 · 外部店铺动作 0','local');}finally{running=false;send.disabled=false;}return true;}
  async function probe(){try{const snapshot=await call('browser_ai_connector_snapshot',null,true);for(const [id,label] of routes){const state=snapshot?.providers?.[id]||{};const option=ensureOption(id,label+' · '+(state.ready?'已连接':'未连接'));option.disabled=!state.ready;}}catch(_error){for(const [id,label] of routes)ensureOption(id,label+' · 检测失败').disabled=true;}}
  provider.addEventListener('change',()=>{if(selected())apply();});
  send.addEventListener('click',event=>{if(!selected())return;event.preventDefault();event.stopImmediatePropagation();run();},true);
  box.addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&selected()){event.preventDefault();event.stopImmediatePropagation();run();}},true);
  probe();
})();
</script>
"""

def _replace_settings_section(html: str, section_id: str, replacement: str) -> str:
    marker = f'id="{section_id}"'
    marker_index = html.find(marker)
    if marker_index < 0:
        return html
    start = html.rfind("<section", 0, marker_index)
    if start < 0:
        return html
    end = html.find('<section class="settings-page-section"', marker_index)
    if end < 0:
        end = html.find("</main>", marker_index)
    if end < 0:
        return html
    return html[:start] + replacement + html[end:]


def _replace_ai_model_settings(html: str, root: _Path) -> str:
    """Keep one flat, provider-neutral model selector in the daily settings UI."""

    if 'id="settings-ai-models"' not in html:
        return html
    try:
        from .ai_provider_catalog import provider_catalog_snapshot

        snapshot = provider_catalog_snapshot(root)
    except (OSError, TypeError, ValueError, KeyError):
        snapshot = {}
    catalog = sorted(
        [item for item in snapshot.get("catalog", []) if isinstance(item, dict)],
        key=lambda item: str(item.get("label") or item.get("id") or "").casefold(),
    )
    options = "".join(
        '<option value="{value}">{label} · {state}</option>'.format(
            value=_html_escape(str(item.get("id") or ""), quote=True),
            label=_html_escape(str(item.get("label") or item.get("id") or "")),
            state=(
                "当前可用"
                if item.get("verification_state") == "verified"
                else "待适配"
                if item.get("integration_state") == "future_adapter"
                else "暂不可用"
                if item.get("verification_state") == "blocked"
                or item.get("integration_state") == "hardware_gated"
                else "可添加"
            ),
        )
        for item in catalog
    )
    replacement = f"""
<section class="settings-page-section" id="settings-ai-models" hidden data-settings-page-section="AI 模型 服务商 自定义接口 本地模型">
  <h1>AI 模型</h1>
  <div class="settings-section-group">
    <h2>模型服务</h2>
    <div class="settings-option-list">
      <div class="settings-option-row"><span><b>配置模型</b><small>可添加任意兼容 API、本地模型或私有部署；列表不按国家和地区分组。</small></span><button type="button" data-settings-view="models">添加或管理 →</button></div>
      <div class="settings-option-row"><span><b>当前可用</b><small>只显示现在可以被任务选择的精确模型。</small></span><em>{int(snapshot.get('runtime_eligible_count') or 0)} 个</em></div>
    </div>
  </div>
  <div class="settings-section-group ai-provider-directory" data-flat-ai-provider-directory="true">
    <h2>服务列表</h2>
    <p class="settings-section-lead">所有服务平铺显示；可在模型管理页填写自定义地址和精确模型 ID。</p>
    <label for="flatAiProviderCatalog">模型服务</label>
    <select id="flatAiProviderCatalog">{options}</select>
  </div>
</section>"""
    return _replace_settings_section(html, "settings-ai-models", replacement)


def _replace_open_tool_settings(html: str, root: _Path) -> str:
    """Put provider-neutral tool registration into the existing extension area."""

    if 'id="settings-skills-agents"' not in html:
        return html
    try:
        from .open_tool_registry import open_tool_registry_snapshot

        snapshot = open_tool_registry_snapshot(root)
    except (OSError, TypeError, ValueError):
        snapshot = {"registered_count": 0}
    replacement = f"""
<section class="settings-page-section" id="settings-skills-agents" hidden data-settings-page-section="工具 扩展 API MCP 本地程序 命令行 Skill Plugin Agent 自动化">
  <h1>工具与扩展</h1>
  <div class="settings-section-group" data-open-tool-registry="true">
    <div class="open-tool-intro"><span><h2>添加工具</h2><p>API、MCP、本地程序、命令行、Skill、Plugin、Agent 和其他工具都可添加。保存只登记，不会假装已经连接。</p></span><em>{int(snapshot.get('registered_count') or 0)} 个已添加</em></div>
    <details><summary>添加一个工具</summary>
      <div class="open-tool-form">
        <label>工具名称<input id="openToolName" maxlength="120" autocomplete="off"></label>
        <label>类型<input id="openToolKind" list="openToolKinds" maxlength="64" autocomplete="off"><datalist id="openToolKinds"><option value="API"><option value="MCP"><option value="本地程序"><option value="命令行"><option value="Skill"><option value="Plugin"><option value="Agent"><option value="自动化"><option value="其他"></datalist></label>
        <label class="open-tool-wide">连接地址或本地路径<input id="openToolConnection" maxlength="2048" autocomplete="off" placeholder="https://... / C:\\... / package-or-command"></label>
        <label>能力（逗号分隔）<input id="openToolCapabilities" maxlength="1200" autocomplete="off" placeholder="搜索, 数据读取, 图片生成"></label>
        <label>凭据引用（可选）<input id="openToolCredential" maxlength="240" autocomplete="off" placeholder="只填安全引用，不粘贴密钥"></label>
        <label>使用范围<select id="openToolScope"><option value="shared">通用工具</option><option value="store">指定店铺</option></select></label>
        <div class="open-tool-store-scope" id="openToolStoreScope" hidden>
          <label>项目<input id="openTool_project_id" maxlength="160"></label><label>平台<input id="openTool_platform" maxlength="160"></label>
          <label>国家 / 站点<input id="openTool_country_site" maxlength="160"></label><label>店铺模式<input id="openTool_store_mode" maxlength="160"></label>
          <label>具体店铺<input id="openTool_store_binding_id" maxlength="160"></label><label>执行账号<input id="openTool_account_id" maxlength="160"></label>
          <label class="open-tool-wide">执行身份引用<input id="openTool_execution_identity_ref" maxlength="160"></label>
        </div>
        <button id="openToolSave" type="button">保存工具</button>
      </div>
    </details>
    <p class="open-tool-status" id="openToolStatus" role="status" aria-live="polite">添加后可单独验证连接；未验证时保持“未连接”。</p>
    <div class="open-tool-list" id="openToolList"></div>
    <details class="desktop-control" id="desktopControl" data-desktop-control="true">
      <summary>本机电脑与浏览器控制</summary>
      <div class="desktop-control-grid">
        <div class="desktop-control-actions"><button id="desktopControlProbe" class="secondary" type="button">检测本机能力</button></div>
        <label>鼠标动作<select id="desktopMouseAction"><option value="move">移动</option><option value="click">单击</option><option value="double_click">双击</option><option value="right_click">右键</option></select></label>
        <label>坐标 X<input id="desktopMouseX" type="number"></label><label>坐标 Y<input id="desktopMouseY" type="number"></label>
        <div class="desktop-control-actions"><button id="desktopMouseRun" type="button">1 秒后执行鼠标动作</button></div>
        <label class="desktop-control-wide">键盘输入<input id="desktopKeyboardText" maxlength="4000" placeholder="点击后有 3 秒切换到目标输入框"></label>
        <div class="desktop-control-actions"><button id="desktopKeyboardRun" type="button">3 秒后输入</button></div>
        <label class="desktop-control-wide">浏览器地址<input id="desktopBrowserUrl" value="https://" maxlength="2048"></label>
        <div class="desktop-control-actions"><button id="desktopBrowserRun" type="button">用默认浏览器打开</button></div>
      </div>
      <p class="desktop-control-status" id="desktopControlStatus" role="status" aria-live="polite">等待检测。每次点击只执行一次，不在后台记录键盘。</p>
    </details>
  </div>
</section>"""
    updated = _replace_settings_section(html, "settings-skills-agents", replacement)
    updated = updated.replace(">Skills / Agents</a>", ">工具与扩展</a>", 1)
    if "data-t-one-open-tools-style=true" not in updated:
        updated = updated.replace("</style>", _OPEN_TOOL_SETTINGS_CSS + "</style>", 1)
    if 'data-t-one-open-tools-script="true"' not in updated:
        updated = updated.replace("</body>", _OPEN_TOOL_SETTINGS_JS + "</body>", 1)
    return updated


def _ensure_cli_ai_roundtrip_settings(html: str, root: _Path) -> str:
    """Add the verified local CLI transport beside the open tool registry."""

    if 'data-cli-ai-roundtrip="true"' in html:
        return html
    section_start = html.find('id="settings-skills-agents"')
    if section_start < 0:
        return html
    insertion_index = html.find("</section>", section_start)
    if insertion_index < 0:
        return html
    try:
        from .workspace_runtime import load_workspace_config

        workspace = load_workspace_config(root)
    except (OSError, TypeError, ValueError, KeyError):
        workspace = {"projects": []}
    try:
        from .non_api_ai_bridge import non_api_ai_bridge_snapshot

        browser_snapshot = non_api_ai_bridge_snapshot(root)
    except (OSError, TypeError, ValueError, KeyError):
        browser_snapshot = {"providers": []}
    browser_cards = []
    for provider in browser_snapshot.get("providers", []):
        if not isinstance(provider, dict):
            continue
        if not str(provider.get("current_status") or "").startswith("manually_verified_"):
            continue
        verification = (
            provider.get("manual_verification")
            if isinstance(provider.get("manual_verification"), dict)
            else {}
        )
        evidence = str(verification.get("evidence_path") or "")
        state = (
            "文件回传已实测"
            if verification.get("project_file_roundtrip")
            else "消息回传已实测"
        )
        browser_cards.append(
            '<article data-web-ai-provider="{provider_id}"><b>{name}</b>'
            '<small>复用现有登录浏览器；不会新建账号、Profile 或保存 Cookie。</small>'
            '<em>{state} · 尚未标记为全自动连接</em><small>{evidence}</small></article>'.format(
                provider_id=_html_escape(str(provider.get("id") or ""), quote=True),
                name=_html_escape(str(provider.get("name") or provider.get("id") or "网页 AI")),
                state=_html_escape(state),
                evidence=_html_escape(evidence),
            )
        )
    browser_status = (
        '<div class="existing-login-web-ai" data-existing-login-web-ai="true">'
        + "".join(browser_cards)
        + "</div>"
        if browser_cards
        else ""
    )
    options = []
    task_options = ['<option value="">项目级协作</option>']
    for project in workspace.get("projects", []):
        if not isinstance(project, dict):
            continue
        project_id = str(project.get("id") or "").strip()
        if not project_id:
            continue
        options.append(
            '<option value="{value}">{label}</option>'.format(
                value=_html_escape(project_id, quote=True),
                label=_html_escape(str(project.get("name") or project_id)),
            )
        )
        for task in project.get("tasks", []):
            if not isinstance(task, dict):
                continue
            task_id = str(task.get("id") or "").strip()
            if not task_id:
                continue
            task_options.append(
                '<option value="{value}" data-project="{project}">{label}</option>'.format(
                    value=_html_escape(task_id, quote=True),
                    project=_html_escape(project_id, quote=True),
                    label=_html_escape(str(task.get("name") or task_id)),
                )
            )
    if not options:
        options.append('<option value="" disabled selected>暂无本地项目</option>')
    block = f"""
<div class="settings-section-group cli-ai-roundtrip" data-cli-ai-roundtrip="true" data-cli-installed="false" data-cli-ready="false">
  <div class="cli-ai-heading"><span><h2>本机 AI 双向回传</h2><p>把本地项目信息通过已登录的 Codex CLI 发给 AI，再将回答和回执保存回项目文件夹并显示在本页。当前连接使用只读沙箱，不会操作店铺。</p></span><em id="cliAiStatus" role="status" aria-live="polite">等待检测本机 Codex CLI…</em></div>
  <div class="cli-ai-form">
    {browser_status}
    <label>本地项目<select id="cliAiProject">{''.join(options)}</select></label>
    <label>连接方式<select id="cliAiProvider"><option value="codex-cli">Codex CLI · stdin / JSONL</option></select></label>
    <label>协作任务<select id="multiAiTask">{''.join(task_options)}</select></label>
    <label class="cli-ai-prompt">发送给 AI 的信息<textarea id="cliAiPrompt" maxlength="12000" placeholder="输入项目资料、问题或任务。密钥等敏感字段会先脱敏。"></textarea></label>
    <div class="cli-ai-actions"><button id="cliAiRun" type="button" disabled>发送并回传结果</button><small>点击即确认本次发送；每次重新发送都需要再次点击。外部店铺动作保持为 0。</small></div>
    <pre class="cli-ai-result" id="cliAiResult" aria-label="AI 回传结果"></pre>
    <div class="multi-ai-collaboration" data-multi-ai-collaboration="true">
      <div class="multi-ai-head"><span><h3>多 AI 并行协作</h3><p>同一份脱敏任务并行发给不同的已验证 AI；每个结果单独回传，失败不会被隐藏。Claude 桌面已安装时也会显示，但没有自动回传接口前不能勾选。</p></span><em id="multiAiStatus" role="status" aria-live="polite">等待检测协作者…</em></div>
      <div class="multi-ai-participants" id="multiAiPrimaryParticipants"></div>
      <details class="multi-ai-configured" id="multiAiConfiguredDetails" hidden><summary><b>其他已配置 AI</b><small>需要时展开，调用结果决定是否可用</small><span id="multiAiConfiguredCount">0 个</span></summary><div class="multi-ai-participants" id="multiAiConfiguredParticipants"></div></details>
      <div class="cli-ai-actions"><button id="multiAiRun" type="button" disabled>并行协作并回传</button><small>点击即确认本次外部 AI 调用；所有协作者均无店铺写入权限。</small></div>
      <pre class="cli-ai-result multi-ai-result" id="multiAiResult" aria-label="多 AI 回传结果"></pre>
    </div>
  </div>
</div>
"""
    updated = html[:insertion_index] + block + html[insertion_index:]
    if "data-t-one-cli-ai-roundtrip-style=true" not in updated:
        updated = updated.replace("</style>", _CLI_AI_ROUNDTRIP_CSS + "</style>", 1)
    if 'data-t-one-cli-ai-roundtrip-script="true"' not in updated:
        updated = updated.replace("</body>", _CLI_AI_ROUNDTRIP_JS + "</body>", 1)
    return updated


def _ensure_task_ai_roundtrip(html: str) -> str:
    """Connect the existing task composer to verified CLI and project AI routes."""

    if (
        'data-task-ai-roundtrip="true"' in html
        or 'id="message"' not in html
        or 'id="send"' not in html
        or 'id="taskAiProviderQuick"' not in html
    ):
        return html
    updated = html.replace(
        '<details class="composer-model-picker" id="composerModelPicker">',
        '<details class="composer-model-picker" id="composerModelPicker" data-task-ai-roundtrip="true">',
        1,
    )
    updated = updated.replace(
        '<select id="taskAiProviderQuick" aria-label="选择 AI"></select>',
        '<select id="taskAiProviderQuick" aria-label="选择 AI"><option value="codex-cli">Codex CLI</option><option value="codex-luna-cli">GPT-5.6 Luna</option><option value="project-multi-ai">项目多 AI 协作</option></select>',
        1,
    )
    return updated.replace(
        "</body>",
        _TASK_AI_ROUNDTRIP_JS + _BROWSER_AI_ROUNDTRIP_JS + "</body>",
        1,
    )


def _ensure_project_toggle_a11y_sync(html: str) -> str:
    """Keep the visible project disclosure state available to assistive UI."""

    if 'data-t-one-project-toggle-a11y="true"' in html:
        return html
    return html.replace("</body>", _PROJECT_TOGGLE_A11Y_SYNC + "</body>", 1)


def _simplify_daily_workspace_copy(html: str) -> str:
    """Keep implementation-only query language out of the daily task UI."""

    replacements = (
        (
            "\u4f4e\u9891\u8d44\u6599\u9ed8\u8ba4\u6536\u8d77\uff1b\u8c03\u8bd5\u4fe1\u606f\u9700 debug=1",
            "\u9700\u8981\u65f6\u518d\u5c55\u5f00\u8d44\u6599\uff0c\u4e0d\u5f71\u54cd\u65e5\u5e38\u5bf9\u8bdd\u3002",
        ),
        ("真实店铺、接口与成本证据仍需负责人授权", "真实店铺、接口与成本数据仍需负责人授权"),
        ("暂无外部证据时间", "暂无更新时间"),
        ("状态/证据：", "状态："),
        ("调用证据和结果回执", "连接验证和结果"),
        ("预测和数据证据", "预测和数据来源"),
        ("证据事件", "进度事件"),
        ("已有外发证据 0", "已外发 0"),
        ("没有真实外发证据", "未外发"),
        ("已记录内部草稿或批次草稿引用；没有外发证据。", "内部草稿已保存，未外发。"),
        (
            "直接告诉我结果目标，相关能力和工具由 T-one 自动选择。",
            "先确认任务目标；需要时可在下方查看或调整 Agent、Skill 和工具。",
        ),
        (
            ">学习资料：请阅读下面这份我有权使用的资料，并先作为待核验候选：</button>",
            ">读取任务资料</button>",
        ),
        ("自动路由 · 推荐 · 标准 · 标准", "自动选择 AI · 标准"),
        (
            "历史批准没有当前执行时间、精确收件人、渠道、草稿版本和附件版本的完整证据",
            "历史批准信息不完整",
        ),
        (
            "addSection('证据来源',node.evidence_refs,(row,item)=>{row.textContent=String(item);});",
            "",
        ),
    )
    for source, target in replacements:
        html = html.replace(source, target)
    return html


def _ensure_sidebar_rename_dialog(html: str) -> str:
    """Replace Electron's unsupported native prompt with an in-app dialog."""

    if 'id="sidebarRenameDialog"' in html:
        return html
    updated = html.replace(
        _LEGACY_SIDEBAR_RENAME_JS,
        _REVIEWED_SIDEBAR_RENAME_JS,
        1,
    )
    if updated == html:
        return html
    updated = updated.replace(
        "</style>",
        _SIDEBAR_RENAME_DIALOG_CSS + "</style>",
        1,
    )
    return updated.replace("</body>", _SIDEBAR_RENAME_DIALOG + "</body>", 1)


def _ensure_workspace_folder_access(html: str) -> str:
    """Expose the durable project/task folder from the existing sidebar menu."""

    if 'data-t-one-workspace-folder-access="true"' in html:
        return html
    separator = '<span class="sidebar-context-separator"></span>'
    if separator not in html:
        return html
    updated = html.replace(
        separator,
        '<button type="button" data-sidebar-menu-action="open-folder">打开文件夹</button>\n  '
        + separator,
        1,
    )
    copy_handler = "if(action==='copy-id'){await copySidebarText(itemId);showNavigationStatus('已复制 ID');return;}"
    if copy_handler not in updated:
        return html
    updated = updated.replace(
        copy_handler,
        "if(action==='open-folder'){const opened=await openWorkspaceItemFolderRequest(type,itemId);"
        "if(!opened?.ok)throw new Error(opened?.error||'文件夹没有打开。');"
        "showNavigationStatus(opened.message||'已打开本地文件夹');return;}\n    "
        + copy_handler,
        1,
    )
    updated = _re.sub(
        r"<a\b[^>]*\bdata-side-task-launcher=[\"']true[\"'][^>]*>\s*侧边任务\s*</a>",
        "",
        updated,
        count=1,
        flags=_re.IGNORECASE,
    )
    if 'id="workspaceOpenFolder"' not in updated:
        button = (
            '<button type="button" class="command-button" '
            'data-workspace-open-folder="true" id="workspaceOpenFolder" hidden>打开文件夹</button>'
        )
        topbar_start = updated.find('<header class="topbar">')
        topbar_end = updated.find("</header>", topbar_start)
        if topbar_start >= 0 and topbar_end >= 0:
            updated = updated[:topbar_end] + button + updated[topbar_end:]
        else:
            updated = updated.replace("</body>", button + "</body>", 1)
    return updated.replace("</body>", _WORKSPACE_FOLDER_ACCESS_SCRIPT + "</body>", 1)


def _runtime_created_sidebar_projects(root: _Path) -> list[dict[str, str]]:
    runtime_path = root / "data" / "workspace_runtime.json"
    try:
        payload = _json.loads(runtime_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    projects = payload.get("projects") if isinstance(payload, dict) else []
    records: list[dict[str, str]] = []
    for item in projects if isinstance(projects, list) else []:
        if not isinstance(item, dict):
            continue
        project_id = str(item.get("id") or "").strip().lower()
        name = " ".join(str(item.get("name") or "").split()).strip()
        if not _re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", project_id) or not name:
            continue
        records.append({"id": project_id, "name": name})
    return records


def _ensure_workspace_creation_controls(html: str, root: _Path) -> str:
    """Open one goal-first conversation surface from the sidebar."""

    if 'data-t-one-workspace-creation="true"' in html:
        return html
    legacy_actions = (
        '<div class="side-actions"><button class="side-action" id="newTask">'
        '＋ 新建对话</button><button class="side-action icon-only" id="focusSearch" '
        'title="搜索项目、店铺和对话" aria-label="搜索项目、店铺和对话">⌕</button></div>'
    )
    if legacy_actions not in html:
        return html
    unified_actions = (
        '<div class="side-actions"><button class="side-action" id="newTask" '
        'type="button">＋ 新建</button><button class="side-action icon-only" id="focusSearch" '
        'title="搜索项目、店铺和对话" aria-label="搜索项目、店铺和对话">⌕</button></div>'
    )
    updated = html.replace(legacy_actions, unified_actions, 1)
    project_list_marker = '<div class="sidebar-section-body project-items">'
    if project_list_marker in updated:
        missing_projects: list[str] = []
        for project in _runtime_created_sidebar_projects(root):
            project_id = project["id"]
            if f'data-project-dashboard="{project_id}"' in updated:
                continue
            escaped_id = _html_escape(project_id, quote=True)
            escaped_name = _html_escape(project["name"])
            missing_projects.append(
                '<details class="project-section" data-project-section="{id}" '
                'data-drop-project="{id}" data-project-search="{name}" '
                'data-sidebar-default-compact="true" data-task-total="0">'
                '<summary class="project-heading"><button class="project-toggle" '
                'type="button" data-project-toggle="{id}" aria-label="收起或展开 {name}" '
                'aria-expanded="false">›</button><a class="project-dashboard-link" '
                'data-project-dashboard="{id}" href="/desktop?project={id}" '
                'data-sidebar-item-type="project" data-sidebar-item-id="{id}" '
                'data-sidebar-item-name="{name}" data-sidebar-pinned="false">'
                '<span>{name}</span></a></summary><div class="project-children"></div></details>'.format(
                    id=escaped_id,
                    name=escaped_name,
                )
            )
        if missing_projects:
            updated = updated.replace(
                project_list_marker,
                project_list_marker + "".join(missing_projects),
                1,
            )
    updated = updated.replace("</style>", _WORKSPACE_CREATION_CSS + "</style>", 1)
    return updated.replace("</body>", _WORKSPACE_CREATION_DIALOGS + "</body>", 1)


def _select_options(records: list[dict[str, object]]) -> str:
    return "".join(
        '<option value="{value}">{label}</option>'.format(
            value=_html_escape(str(item.get("id") or ""), quote=True),
            label=_html_escape(
                str(
                    item.get("chinese_label")
                    or item.get("label")
                    or item.get("id")
                    or ""
                )
            ),
        )
        for item in records
        if str(item.get("id") or "").strip()
    )


def _ensure_commerce_profile_editor(html: str, root: _Path) -> str:
    """Add the U12 local project classification editor to platform settings."""

    if 'data-u12-commerce-profile-editor="true"' in html:
        return html
    if '<body data-desktop-ui="true" data-view="settings_center"' in html:
        section_index = html.find('id="settings-commerce"')
        next_section_index = html.find(
            '<section class="settings-page-section"', section_index + 1
        )
        insertion_index = html.rfind(
            "</section>",
            section_index,
            next_section_index if next_section_index >= 0 else len(html),
        )
    else:
        panel_index = html.find('<div class="tool-panel" id="panel-commerce">')
        insertion_index = html.find(
            '<section class="store-connection-test">', panel_index
        )
    if insertion_index < 0:
        return html
    try:
        from .global_commerce_dimensions import commerce_model_taxonomy
        from .workspace_runtime import load_workspace_config, seller_mode_options

        taxonomy = commerce_model_taxonomy(root)
        workspace = load_workspace_config(root)
        seller_modes = seller_mode_options(root)
    except (OSError, TypeError, ValueError):
        return html

    projects = [
        item
        for item in workspace.get("projects", [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    ]
    project_options = '<option value="__new__">新建项目</option>' + "".join(
        '<option value="{value}">{label}</option>'.format(
            value=_html_escape(str(item.get("id") or ""), quote=True),
            label=_html_escape(str(item.get("name") or item.get("id") or "")),
        )
        for item in projects
    )
    project_profiles = {
        str(item.get("id") or ""): {
            "name": str(item.get("name") or ""),
            "relationship_model": str(item.get("relationship_model") or ""),
            "secondary_relationship_models": [
                str(value)
                for value in item.get("secondary_relationship_models", [])
                if str(value).strip()
            ],
            "commerce_forms": [
                str(value)
                for value in item.get("commerce_forms", [])
                if str(value).strip()
            ],
            "seller_mode": str(item.get("seller_mode") or ""),
        }
        for item in projects
    }
    relationship_records = list(taxonomy.get("relationship_models", {}).values())
    commerce_form_records = list(taxonomy.get("commerce_forms", {}).values())
    relationship_options = _select_options(relationship_records)
    commerce_form_options = _select_options(commerce_form_records)
    seller_mode_html = _select_options(seller_modes)
    profiles_json = _json.dumps(project_profiles, ensure_ascii=False).replace("</", "<\\/")
    editor = f"""
<section class="u12-commerce-editor" data-u12-commerce-profile-editor="true">
  <h3>经营关系 / 电商形态 / 卖家模式</h3>
  <p>这些字段只用于本地项目分析与能力路由；保存不会连接平台、创建店铺、投放、付款或发货。</p>
  <div class="u12-commerce-grid">
    <label class="wide">项目<select id="u12CommerceProject">{project_options}</select></label>
    <label class="wide">项目名称（新建时填写）<input id="u12CommerceProjectName" maxlength="100" autocomplete="off" placeholder="例如：东南亚品牌增长"></label>
    <label>主要经营关系<select id="u12RelationshipModel"><option value="">请选择</option>{relationship_options}</select></label>
    <label>卖家模式<select id="u12SellerMode"><option value="">请选择</option>{seller_mode_html}</select></label>
    <label>次要经营关系（可多选）<select id="u12SecondaryRelationshipModels" multiple>{relationship_options}</select></label>
    <label>电商形态（可多选）<select id="u12CommerceForms" multiple>{commerce_form_options}</select></label>
  </div>
  <div class="u12-commerce-actions"><button id="u12SaveCommerceProfile" type="button">创建并保存</button><span id="u12CommerceProfileStatus" role="status">尚未保存。</span></div>
</section>
<script data-u12-commerce-profile-script="true">
(()=>{{
const profiles={profiles_json};
const project=document.getElementById('u12CommerceProject');
const name=document.getElementById('u12CommerceProjectName');
const relationship=document.getElementById('u12RelationshipModel');
const secondary=document.getElementById('u12SecondaryRelationshipModels');
const forms=document.getElementById('u12CommerceForms');
const seller=document.getElementById('u12SellerMode');
const save=document.getElementById('u12SaveCommerceProfile');
const status=document.getElementById('u12CommerceProfileStatus');
if(!project||!name||!relationship||!secondary||!forms||!seller||!save||!status)return;
const selectMany=(control,values)=>{{const chosen=new Set(values||[]);[...control.options].forEach(option=>option.selected=chosen.has(option.value));}};
const currentValues=control=>[...control.selectedOptions].map(option=>option.value).filter(Boolean);
function loadProfile(){{const creating=project.value==='__new__';const profile=profiles[project.value]||{{}};name.value=creating?'':(profile.name||'');name.readOnly=!creating;relationship.value=profile.relationship_model||'';selectMany(secondary,profile.secondary_relationship_models);selectMany(forms,profile.commerce_forms);seller.value=profile.seller_mode||'';save.textContent=creating?'创建并保存':'保存修改';status.dataset.state='';status.textContent=creating?'填写项目与经营分类。':'已载入；修改后点保存。';}}
async function invoke(method,payload,endpoint){{if(window.pywebview?.api?.[method])return await window.pywebview.api[method](payload);if(window.teelabDesktop?.isDesktop&&window.teelabDesktop?.invoke)return await window.teelabDesktop.invoke(method,payload);const response=await fetch(endpoint,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload)}});const result=await response.json();if(!response.ok&&!result.error)result.error='保存失败。';return result;}}
project.addEventListener('change',loadProfile);
save.addEventListener('click',async()=>{{const creating=project.value==='__new__';const payload={{relationship_model:relationship.value,secondary_relationship_models:currentValues(secondary),commerce_forms:currentValues(forms),seller_mode:seller.value}};if(creating)payload.name=name.value.trim();else payload.project_id=project.value;if(!payload.relationship_model||!payload.seller_mode||!payload.commerce_forms.length||(creating&&!payload.name)){{status.dataset.state='error';status.textContent='项目名称、主要经营关系、至少一种电商形态和卖家模式必须明确。';return;}}try{{save.disabled=true;status.dataset.state='';status.textContent='正在保存本地经营分类...';const result=creating?await invoke('create_workspace_project',payload,'/api/v1/workspace/projects'):await invoke('save_workspace_commerce_profile',payload,'/api/v1/workspace/commerce-profile');if(!result?.ok)throw new Error(result?.error||'保存失败。');const projectId=result.project?.id||result.project_id||project.value;status.dataset.state='ok';status.dataset.projectId=projectId;status.textContent='已保存；重启后仍会从本地工作区恢复。外部动作 0。';}}catch(error){{status.dataset.state='error';status.textContent=error.message||'保存失败。';}}finally{{save.disabled=false;}}}});
loadProfile();
}})();
</script>
"""
    updated = html[:insertion_index] + editor + html[insertion_index:]
    if _COMMERCE_PROFILE_EDITOR_CSS.strip() not in updated:
        updated = updated.replace(
            "</style>", _COMMERCE_PROFILE_EDITOR_CSS + "</style>", 1
        )
    return updated


def _ensure_u16_message_file_import(html: str) -> str:
    if 'data-u16-message-file-import="true"' in html or 'data-view="communications"' not in html:
        return html
    marker = '<div class="control-view communications-view" data-communications-control>'
    insertion_index = html.find(marker)
    if insertion_index < 0:
        return html
    insertion_index += len(marker)
    section = """
<section class="u16-message-import" data-u16-message-file-import="true">
  <h3>读取本地 EML 消息元数据</h3>
  <p>用于先验证项目 / 任务 / 店铺 / 通信账号隔离和解析错误。只保存哈希、时间、发件域名和数量，不保存地址、主题、正文或附件；不会显示为已连接。</p>
  <div class="u16-message-import-grid">
    <label>范围<select id="u16MessageScopeKind"><option value="project_task">项目 + 任务</option><option value="store">项目 + 任务 + 店铺</option></select></label>
    <label>Tenant ID<input id="u16MessageTenant" autocomplete="off"></label>
    <label>Project ID<input id="u16MessageProject" autocomplete="off"></label>
    <label>Task ID<input id="u16MessageTask" autocomplete="off"></label>
    <label>Store Binding ID<input id="u16MessageStore" autocomplete="off" placeholder="店铺范围时必填"></label>
    <label>Execution Identity ID<input id="u16MessageIdentity" autocomplete="off"></label>
    <label>Connector Account Ref<input id="u16MessageAccount" autocomplete="off" placeholder="内部引用，不填邮箱"></label>
    <label class="wide">本地 EML 文件<input id="u16MessageFile" type="file" accept=".eml,message/rfc822"></label>
  </div>
  <div class="u16-message-import-actions"><button type="button" id="u16ImportMessage">读取本地文件</button><span id="u16MessageImportStatus" role="status">尚未选择文件；真实账号连接 0，外部动作 0。</span></div>
</section>
<script data-u16-message-file-import-script="true">
(()=>{const button=document.getElementById('u16ImportMessage');const status=document.getElementById('u16MessageImportStatus');if(!button||!status)return;const value=id=>String(document.getElementById(id)?.value||'').trim();const read=file=>new Promise((resolve,reject)=>{const reader=new FileReader();reader.onerror=()=>reject(new Error('无法读取所选 EML 文件。'));reader.onload=()=>resolve(String(reader.result||''));reader.readAsDataURL(file);});async function invoke(payload){if(window.pywebview?.api?.import_communications_message_file)return await window.pywebview.api.import_communications_message_file(payload);if(window.teelabDesktop?.isDesktop&&window.teelabDesktop?.invoke)return await window.teelabDesktop.invoke('import_communications_message_file',payload);const response=await fetch('/api/v1/communications/import-file',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const result=await response.json();if(!response.ok)throw new Error(result.error||'EML 读取失败。');return result;}button.addEventListener('click',async()=>{try{const file=document.getElementById('u16MessageFile')?.files?.[0];if(!file)throw new Error('请选择一个 EML 文件。');button.disabled=true;status.dataset.state='';status.textContent='正在本地解析并校验精确作用域…';const payload={filename:file.name,content_base64:await read(file),scope_kind:value('u16MessageScopeKind'),tenant_id:value('u16MessageTenant'),project_id:value('u16MessageProject'),task_id:value('u16MessageTask'),store_binding_id:value('u16MessageStore'),execution_identity_id:value('u16MessageIdentity'),connector_account_ref:value('u16MessageAccount')};const result=await invoke(payload);if(!result?.ok)throw new Error(result?.error||'EML 读取失败。');const message=result.message?.message||{};status.dataset.state='ok';status.textContent='已读取 1 条本地消息元数据；发件域名 '+String(message.sender_domain||'unknown')+'；附件 '+String(message.attachment_count||0)+'；不会显示为已连接；外部动作 0。';}catch(error){status.dataset.state='error';status.textContent=error.message||'EML 读取失败。';}finally{button.disabled=false;}});})();
</script>
"""
    updated = html[:insertion_index] + section + html[insertion_index:]
    if _U16_MESSAGE_IMPORT_CSS.strip() not in updated:
        updated = updated.replace("</style>", _U16_MESSAGE_IMPORT_CSS + "</style>", 1)
    return updated.replace("复盘证据", "连接状态").replace("最近预检", "最近本地预检")


def _ensure_u15_settlement_file_import(html: str) -> str:
    """Expose the existing local settlement importer inside a real task.

    The backend and desktop bridge were already complete, but the task page had
    no usable hand-off from a platform CSV/JSON file to the reconciliation
    result.  Keep the operation local and never offer Amazon while it is paused.
    """

    if (
        'data-u15-settlement-import="true"' in html
        or "const TASK=" not in html
        or not _re.search(
            r'<body\b[^>]*\bdata-view="(?:task_detail|b2b|store_operations)"', html
        )
    ):
        return html
    marker_match = _re.search(r'<section\b[^>]*\bclass="[^"]*\bthread\b[^"]*"[^>]*>', html)
    if marker_match is None:
        return html
    insertion_index = marker_match.end()
    section = """
<details class="u15-settlement-import" data-u15-settlement-import="true">
  <summary><b>导入平台结算文件</b><span>本地 CSV / JSON → 实际结算 → 可选对账</span></summary>
  <div class="u15-settlement-body">
    <p>选择平台下载的结算明细，并明确站点、店铺与币种。文件只在本机解析；不会登录平台、修改店铺、付款或发起银行操作。</p>
    <div class="u15-settlement-grid">
      <label>平台<select id="u15SettlementPlatform"><option value="">请选择</option><option value="SHEIN">SHEIN</option><option value="TikTok Shop">TikTok Shop</option><option value="Shopee">Shopee</option><option value="Etsy">Etsy</option><option value="eBay">eBay</option><option value="Walmart">Walmart</option><option value="Shopify">Shopify</option><option value="other">其他平台</option></select></label>
      <label>站点<input id="u15SettlementSite" autocomplete="off" placeholder="例如 US"></label>
      <label>店铺模式<input id="u15SettlementStoreMode" autocomplete="off" placeholder="例如 self_operated"></label>
      <label>店铺 ID<input id="u15SettlementStore" autocomplete="off"></label>
      <label>币种<input id="u15SettlementCurrency" autocomplete="off" value="USD" maxlength="8"></label>
      <label>估算 ID（可选）<input id="u15SettlementEstimate" autocomplete="off" placeholder="填写后自动对账"></label>
      <label class="wide">结算明细文件<input id="u15SettlementFile" type="file" accept=".csv,.json,text/csv,application/json"></label>
    </div>
    <div class="u15-settlement-actions"><button type="button" id="u15ImportSettlement">读取并保存实际结算</button><span id="u15SettlementStatus" role="status">尚未选择文件。</span></div>
  </div>
</details>
<script data-u15-settlement-import-script="true">
(()=>{const init=()=>{const button=document.getElementById('u15ImportSettlement'),status=document.getElementById('u15SettlementStatus'),fileInput=document.getElementById('u15SettlementFile');if(!button||!status||!fileInput||typeof TASK!=='object')return;const value=id=>String(document.getElementById(id)?.value||'').trim();const params=new URLSearchParams(location.search);const projectId=String(TASK.project_id||params.get('project')||'').trim(),taskId=String(TASK.task_id||TASK.id||params.get('task')||'').trim();const knownPlatform=String(TASK.platform||'').trim();if(knownPlatform&&knownPlatform.toLowerCase()!=='amazon'){const select=document.getElementById('u15SettlementPlatform');if([...select.options].some(option=>option.value.toLowerCase()===knownPlatform.toLowerCase()))select.value=[...select.options].find(option=>option.value.toLowerCase()===knownPlatform.toLowerCase()).value;}const read=file=>new Promise((resolve,reject)=>{const reader=new FileReader();reader.onerror=()=>reject(new Error('无法读取所选结算文件。'));reader.onload=()=>resolve(String(reader.result||''));reader.readAsDataURL(file);});async function invoke(payload){if(window.pywebview?.api?.import_settlement_statement_file)return await window.pywebview.api.import_settlement_statement_file(payload);if(window.teelabDesktop?.isDesktop&&window.teelabDesktop?.invoke)return await window.teelabDesktop.invoke('import_settlement_statement_file',payload);const response=await fetch('/api/v1/finance/settlement/import-file',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const result=await response.json();if(!response.ok)throw new Error(result.error||'结算文件导入失败。');return result;}button.addEventListener('click',async()=>{try{const file=fileInput.files?.[0];if(!file)throw new Error('请选择 CSV 或 JSON 结算文件。');if(file.size>10*1024*1024)throw new Error('结算文件不能超过 10 MB。');const platform=value('u15SettlementPlatform'),site=value('u15SettlementSite'),storeMode=value('u15SettlementStoreMode'),storeId=value('u15SettlementStore'),currency=value('u15SettlementCurrency').toUpperCase();if(!platform||!site||!storeMode||!storeId||!currency)throw new Error('请完整填写平台、站点、店铺模式、店铺 ID 和币种。');button.disabled=true;status.dataset.state='';status.textContent='正在本地解析结算明细…';const payload={filename:file.name,content_base64:await read(file),estimate_id:value('u15SettlementEstimate'),scope:{project_id:projectId,task_id:taskId,platform,site,store_mode:storeMode,store_id:storeId,currency}};const result=await invoke(payload);if(!result?.ok)throw new Error(result?.error||'结算文件导入失败。');const statement=result.statement||{},difference=result.reconciliation?.settlement_difference;status.dataset.state='ok';status.textContent='已保存 '+String(result.file?.row_count||0)+' 行；实际结算 '+String(statement.actual_platform_settlement??'未知')+' '+currency+(difference===undefined?'':'；与估算差额 '+String(difference))+'。外部动作 0。';}catch(error){status.dataset.state='error';status.textContent=error?.message||'结算文件导入失败。';}finally{button.disabled=false;}});};if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();})();
</script>
"""
    updated = html[:insertion_index] + section + html[insertion_index:]
    if _U15_SETTLEMENT_IMPORT_CSS.strip() not in updated:
        updated = updated.replace("</style>", _U15_SETTLEMENT_IMPORT_CSS + "</style>", 1)
    return updated


_AGENT_SKILL_MARKET_CSS = """
.agent-skill-market{margin:16px 0;padding:16px;border:1px solid #dce3e5;border-radius:12px;background:#fff}
.market-return-task{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 0 12px;padding:10px 12px;border:1px solid #bfe0da;border-radius:9px;background:#f2fbf9}.market-return-task[hidden]{display:none}.market-return-task span{min-width:0}.market-return-task b,.market-return-task small{display:block}.market-return-task b{font-size:12px}.market-return-task small{margin-top:3px;color:var(--muted);font-size:11px}.market-return-task a{flex:0 0 auto;border:1px solid #0f766e;border-radius:8px;background:#fff;color:#0f766e;padding:8px 11px;font-size:11px;font-weight:700}
.agent-skill-market-toolbar,.agent-skill-market-actions{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.capability-type-nav{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:0 0 10px}.capability-type-nav button{display:grid;gap:3px;text-align:left;border:1px solid #dce3e5;border-radius:10px;background:#f8faf9;padding:10px 12px;color:#344047;cursor:pointer}.capability-type-nav button b{font-size:13px}.capability-type-nav button small{font-size:11px;color:var(--muted)}.capability-type-nav button[aria-pressed="true"]{border-color:#0f766e;background:#edf8f6;color:#0f766e;box-shadow:inset 0 0 0 1px #0f766e}.capability-type-nav button[aria-pressed="true"] small{color:#0f766e}
.capability-category-bar{display:flex;align-items:end;justify-content:space-between;gap:10px;margin:8px 0 12px;flex-wrap:wrap}.capability-category-bar label{display:grid;gap:4px;color:var(--muted);font-size:11px}.capability-category-bar select,.capability-category-bar input{min-height:36px;min-width:220px;border:1px solid #d7dde0;border-radius:8px;background:#fff;padding:7px 9px}.capability-category-bar span{color:var(--muted);font-size:11px}
.capability-connection-guide{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 0 10px;padding:10px 12px;border:1px solid #cfe0dd;border-radius:9px;background:#f4faf8}.capability-connection-guide[hidden]{display:none}.capability-connection-guide b,.capability-connection-guide small{display:block}.capability-connection-guide b{font-size:12px}.capability-connection-guide small{margin-top:3px;color:var(--muted);font-size:11px}.capability-connection-guide a{flex:0 0 auto;border:0;border-radius:8px;background:#0f766e;color:#fff;padding:8px 11px;font-size:11px;font-weight:700}
.agent-skill-connections{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:14px}.agent-skill-connection{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:center;padding:11px;border:1px solid #dfe5e7;border-radius:9px;background:#f8faf9}.agent-skill-connection b,.agent-skill-connection small{display:block}.agent-skill-connection b{font-size:12px}.agent-skill-connection small{margin-top:4px;color:var(--muted);font-size:11px;line-height:1.45}.agent-skill-connection a{border:1px solid #cfd9da;border-radius:7px;background:#fff;padding:7px 9px;color:#0f766e;font-size:11px;font-weight:700;white-space:nowrap}
.project-ai-composer{margin:0 0 10px;padding:10px 12px;border:1px solid #dfe5e7;border-radius:9px;background:#fbfcfc}.project-ai-composer>summary{display:flex;align-items:center;justify-content:space-between;gap:10px;cursor:pointer;list-style:none}.project-ai-composer>summary::-webkit-details-marker{display:none}.project-ai-composer>summary b{font-size:12px}.project-ai-composer>summary small{color:var(--muted);font-size:11px}.project-ai-head,.project-ai-actions{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}.project-ai-head{margin-top:11px}.project-ai-head b,.project-ai-head small{display:block}.project-ai-head b{font-size:13px}.project-ai-head small{margin-top:3px;color:var(--muted);font-size:11px}.project-ai-head select{min-height:36px;min-width:min(350px,75vw);border:1px solid #d7dde0;border-radius:8px;background:#fff;padding:7px 9px}.project-ai-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-top:10px}.project-ai-item{display:grid;grid-template-columns:auto minmax(0,1fr);gap:7px;padding:8px;border:1px solid #e3e8e9;border-radius:8px;background:#fff}.project-ai-item b,.project-ai-item small{display:block}.project-ai-item b{font-size:12px}.project-ai-item small{margin-top:3px;color:var(--muted);font-size:11px;line-height:1.4}.project-ai-item[data-selectable="false"]{opacity:.58}.project-ai-actions{margin-top:10px}.project-ai-actions label{font-size:11px;color:#39444a}.project-ai-actions button{border:0;border-radius:8px;background:#111;color:#fff;padding:8px 12px;font-size:11px;font-weight:700;cursor:pointer}.project-ai-actions span{flex:1;min-width:220px;color:var(--muted);font-size:11px;line-height:1.45}.project-ai-actions span[data-state="ok"]{color:#0f766e}.project-ai-actions span[data-state="error"]{color:#b45309}
.deepseek-harness-panel{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 10px;padding:11px 12px;border:1px solid #bfe0da;border-radius:9px;background:#f2fbf9}.deepseek-harness-panel[hidden]{display:none}.deepseek-harness-panel span{min-width:180px;flex:1}.deepseek-harness-panel b,.deepseek-harness-panel small{display:block}.deepseek-harness-panel b{font-size:13px}.deepseek-harness-panel small{margin-top:3px;color:var(--muted);font-size:11px}.deepseek-harness-panel select{min-height:36px;max-width:330px;border:1px solid #cfd9da;border-radius:8px;background:#fff;padding:7px 9px}.deepseek-harness-panel button{border:0;border-radius:8px;background:#0f766e;color:#fff;padding:8px 11px;font-size:11px;font-weight:700}.deepseek-harness-panel button:disabled{opacity:.5}.deepseek-harness-panel output{flex-basis:100%;color:var(--muted);font-size:11px}.deepseek-harness-panel output[data-state="ok"]{color:#0f766e}.deepseek-harness-panel output[data-state="error"]{color:#b45309}
.agent-skill-market-toolbar{margin-top:14px}.agent-skill-market-toolbar label{display:grid;gap:4px;color:var(--muted);font-size:11px}.agent-skill-market-toolbar select,.agent-skill-market-toolbar input{min-height:36px;border:1px solid #d7dde0;border-radius:8px;background:#fff;padding:7px 9px;color:var(--text)}
.agent-skill-market-toolbar select{min-width:min(430px,78vw)}.agent-skill-market-toolbar input{min-width:min(260px,70vw)}
.agent-skill-market-filters{display:flex;gap:6px;margin:12px 0}.agent-skill-market-filters button{border:1px solid #d8dfe1;border-radius:999px;background:#fff;padding:6px 10px;color:#4f5a61;cursor:pointer}.agent-skill-market-filters button[aria-pressed="true"]{border-color:#0f766e;background:#edf8f6;color:#0f766e;font-weight:700}
.agent-skill-market-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;max-height:430px;overflow:auto;padding:2px}
.agent-skill-item{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:start;gap:9px;padding:10px;border:1px solid #e2e7e9;border-radius:9px;background:#fafbfb}.agent-skill-item[hidden]{display:none}.agent-skill-item input{margin-top:3px}.agent-skill-item b{display:block;font-size:12px}.agent-skill-item small{display:block;margin-top:3px;color:var(--muted);font-size:11px;line-height:1.45}.agent-skill-item em{font-style:normal;font-size:11px;color:#0f766e;white-space:nowrap}.agent-skill-item[data-enabled="false"]{opacity:.62}.agent-skill-item[data-enabled="false"] em{color:#8a5a18}
.capability-connection-item{grid-template-columns:minmax(0,1fr) auto;align-items:center}.market-assignment-panel[hidden],.project-ai-composer[hidden],.deepseek-harness-panel[hidden],.shein-manual-operator[hidden]{display:none!important}
.agent-skill-market-actions{margin:0 0 10px}.agent-skill-market-actions button{border:0;border-radius:8px;background:#0f766e;color:#fff;padding:8px 13px;font-size:12px;font-weight:700;cursor:pointer}.agent-skill-market-actions button:disabled{opacity:.55;cursor:wait}.agent-skill-market-actions span{flex:1;min-width:240px;color:var(--muted);font-size:11px;line-height:1.5}.agent-skill-market-actions span[data-state="ok"]{color:#0f766e}.agent-skill-market-actions span[data-state="error"]{color:#b45309}
.smart-capability-manager-note{margin:0 0 10px;padding:8px 10px;border:1px solid #dfe7e5;border-radius:8px;background:#f8fbfa;color:#3f4b50;font-size:11px;line-height:1.5}.smart-capability-manager-note b{color:#0f766e}
.shein-manual-operator{margin-top:12px;padding:12px;border:1px solid #bfe0da;border-radius:9px;background:#f2fbf9}.shein-manual-operator[hidden]{display:none}.shein-manual-operator b,.shein-manual-operator small{display:block}.shein-manual-operator small{margin-top:4px;color:var(--muted);font-size:11px;line-height:1.45}.shein-manual-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:9px}.shein-manual-actions button{border:1px solid #0f766e;border-radius:8px;background:#fff;color:#0f766e;padding:8px 11px;font-size:11px;font-weight:700;cursor:pointer}.shein-manual-actions button:disabled{opacity:.55;cursor:wait}.shein-manual-operator span{display:block;margin-top:8px;color:var(--muted);font-size:11px}.shein-manual-operator span[data-state="ok"]{color:#0f766e}.shein-manual-operator span[data-state="error"]{color:#b45309}
@media(max-width:820px){.agent-skill-market-grid,.agent-skill-connections,.project-ai-grid,.capability-type-nav{grid-template-columns:1fr}.agent-skill-market-toolbar{align-items:stretch}.agent-skill-market-toolbar label,.agent-skill-market-toolbar select,.agent-skill-market-toolbar input,.project-ai-head select,.capability-category-bar select{width:100%;min-width:0}.capability-connection-guide,.market-return-task{align-items:flex-start;flex-direction:column}}
"""


def _remove_html_element_by_class(html: str, class_name: str) -> str:
    """Remove one recovered-runtime element without touching its backend capability."""

    class_match = _re.search(
        rf'<(?P<tag>[a-zA-Z][\w:-]*)\b[^>]*\bclass=["\'][^"\']*\b{_re.escape(class_name)}\b[^"\']*["\'][^>]*>',
        html,
    )
    if class_match is None:
        return html
    tag = class_match.group("tag")
    depth = 0
    for match in _re.finditer(rf'</?{_re.escape(tag)}\b[^>]*>', html[class_match.start():], _re.IGNORECASE):
        token = match.group(0)
        if token.startswith("</"):
            depth -= 1
            if depth == 0:
                return html[:class_match.start()] + html[class_match.start() + match.end():]
        elif not token.rstrip().endswith("/>"):
            depth += 1
    return html


def _remove_html_elements_by_attribute(html: str, attribute: str, value: str) -> str:
    """Remove recovered-runtime rows that are registry metadata, not live results."""

    opening = _re.compile(
        rf'<(?P<tag>[a-zA-Z][\w:-]*)\b(?=[^>]*\b{_re.escape(attribute)}=["\']{_re.escape(value)}["\'])[^>]*>',
        _re.IGNORECASE,
    )
    while True:
        element_match = opening.search(html)
        if element_match is None:
            return html
        tag = element_match.group("tag")
        depth = 0
        removed = False
        for match in _re.finditer(
            rf'</?{_re.escape(tag)}\b[^>]*>',
            html[element_match.start():],
            _re.IGNORECASE,
        ):
            token = match.group(0)
            if token.startswith("</"):
                depth -= 1
                if depth == 0:
                    html = html[:element_match.start()] + html[element_match.start() + match.end():]
                    removed = True
                    break
            elif not token.rstrip().endswith("/>"):
                depth += 1
        if not removed:
            return html


def _remove_details_with_summary(html: str, summary: str) -> str:
    summary_index = html.find(summary)
    if summary_index < 0:
        return html
    summary_open = html.rfind("<summary", 0, summary_index)
    summary_close = html.find("</summary>", summary_open)
    if summary_open < 0 or summary_close < summary_index:
        return html
    details_index = html.rfind("<details", 0, summary_open)
    if details_index < 0:
        return html
    depth = 0
    for match in _re.finditer(r"</?details\b[^>]*>", html[details_index:], _re.IGNORECASE):
        if match.group(0).startswith("</"):
            depth -= 1
            if depth == 0:
                return html[:details_index] + html[details_index + match.end():]
        else:
            depth += 1
    return html


def _ensure_agent_skill_marketplace(html: str, root: _Path) -> str:
    """Turn the existing extensions route into one task-scoped capability market."""

    if 'data-agent-skill-market="true"' in html:
        return html
    marker = '<div class="control-view extensions-view">'
    insertion_index = html.find(marker)
    if insertion_index < 0:
        return html

    snapshot = _agent_skill_marketplace_snapshot(root)
    tasks = snapshot.get("tasks", [])
    agents = snapshot.get("agents", [])
    skills = snapshot.get("skills", [])
    connections = snapshot.get("connections", {})
    mcp_tools = connections.get("mcp", []) if isinstance(connections, dict) else []
    external_agents = connections.get("external_agents", []) if isinstance(connections, dict) else []
    cli = connections.get("cli", {}) if isinstance(connections, dict) else {}
    cli_tools = connections.get("cli_tools", []) if isinstance(connections, dict) else []
    harness = connections.get("deepseek_harness", {}) if isinstance(connections, dict) else {}
    taxonomy = snapshot.get("taxonomy", {})
    category_labels = taxonomy.get("category_labels", {}) if isinstance(taxonomy, dict) else {}
    platform_labels = taxonomy.get("platform_labels", {}) if isinstance(taxonomy, dict) else {}

    def category_label(kind: str, category: object) -> str:
        labels = category_labels.get(kind, {}) if isinstance(category_labels, dict) else {}
        category_id = str(category or "other")
        return str(labels.get(category_id) or category_id) if isinstance(labels, dict) else category_id

    def item_platform_ids(item: dict[str, object]) -> list[str]:
        values = item.get("platforms") if isinstance(item.get("platforms"), list) else []
        result = [str(value).strip() for value in values if str(value).strip()]
        return result or ["general"]

    def item_platform_label(item: dict[str, object]) -> str:
        return " / ".join(
            str(platform_labels.get(value) or value)
            for value in item_platform_ids(item)
        )
    connected_mcp = [item for item in mcp_tools if isinstance(item, dict) and item.get("connected")]
    if connected_mcp:
        mcp_status = "｜".join(
            f"{item.get('name') or 'MCP'} 已连接（已启用 {int(item.get('enabled_tool_count') or 0)} / 发现 {int(item.get('discovered_tool_count') or 0)}）"
            for item in connected_mcp
        )
    elif mcp_tools:
        mcp_status = f"已登记 {len(mcp_tools)} 个，尚未验证连接"
    else:
        mcp_status = "尚未登记 MCP，可添加 HTTP 或本地 MCP 配置"
    cli_installed = bool(cli.get("installed")) if isinstance(cli, dict) else False
    cli_ready = bool(cli.get("ready")) if isinstance(cli, dict) else False
    cli_status = (
        "Codex CLI 已连接并可回传"
        if cli_ready
        else (
            "Codex CLI 已安装；连接与登录状态需实时检测"
            if cli_installed
            else "Codex CLI 未检测到；可先安装后回到连接检测"
        )
    )
    connection_href = _html_escape(
        str(connections.get("settings_href") or "/desktop?view=settings#settings-skills-agents"),
        quote=True,
    )
    project_ai = snapshot.get("project_ai", {})
    ai_projects = project_ai.get("projects", []) if isinstance(project_ai, dict) else []
    ai_participants = project_ai.get("participants", []) if isinstance(project_ai, dict) else []
    ai_project_options = "".join(
        '<option value="{}">{}</option>'.format(
            _html_escape(str(item.get("id") or ""), quote=True),
            _html_escape(str(item.get("name") or item.get("id") or "")),
        )
        for item in ai_projects
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    )
    harness_target_options = "".join(
        [
            '<option value="project|{}">项目 · {}</option>'.format(
                _html_escape(str(item.get("id") or ""), quote=True),
                _html_escape(str(item.get("name") or item.get("id") or "")),
            )
            for item in ai_projects
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        ]
        + [
            '<option value="task|{}">任务 · {}</option>'.format(
                _html_escape(str(item.get("id") or ""), quote=True),
                _html_escape(str(item.get("label") or item.get("name") or item.get("id") or "")),
            )
            for item in tasks
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        ]
    )
    ai_status_labels = {
        "verified_callable": "近期实测可用",
        "configured_callable_requires_live_result": "已配置待实测",
        "not_checked": "已安装待检测",
        "installed_no_automated_return_interface": "已安装·不可自动",
        "installed_requires_live_verification": "已安装·待回传验证",
        "not_installed": "未安装",
    }
    ai_cards: list[str] = []
    for item in ai_participants:
        if not isinstance(item, dict):
            continue
        participant_id = str(item.get("id") or "").strip()
        kind = str(item.get("kind") or "").strip()
        selectable = bool(item.get("installed")) and kind != "desktop_gui"
        status_label = ai_status_labels.get(
            str(item.get("status") or ""), str(item.get("status") or "unknown")
        )
        ai_cards.append(
            '<label class="project-ai-item" data-selectable="{}"><input type="checkbox" '
            'data-project-ai-choice value="{}"{}><span><b>{}</b><small>{}{}</small></span></label>'.format(
                "true" if selectable else "false",
                _html_escape(participant_id, quote=True),
                "" if selectable else " disabled",
                _html_escape(str(item.get("name") or participant_id)),
                _html_escape(status_label),
                (
                    " · " + _html_escape(str(item.get("model") or ""))
                    if str(item.get("model") or "").strip()
                    else ""
                ),
            )
        )
    task_options = "".join(
        '<option value="{}">{}</option>'.format(
            _html_escape(str(item.get("id") or ""), quote=True),
            _html_escape(str(item.get("label") or item.get("id") or "")),
        )
        for item in tasks
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    )

    cards: list[str] = []
    for item in agents:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "").strip()
        platforms = " ".join(item_platform_ids(item))
        platform_text = item_platform_label(item)
        cards.append(
            '<label class="agent-skill-item" data-market-kind="agent" '
            'data-market-id="{}" data-category="{}" data-platforms="{}" data-enabled="true" data-search="{}"><input type="checkbox" '
            'data-agent-skill-choice="agent" value="{}"><span><b>{}</b>'
            '<small>平台：{} · 用途：{}</small></span><em>可用于任务</em></label>'.format(
                _html_escape(item_id, quote=True),
                _html_escape(str(item.get("category") or "management_automation"), quote=True),
                _html_escape(platforms, quote=True),
                _html_escape(
                    f"{item_id} {item.get('name') or ''} {item.get('description') or ''} {platform_text}".lower(),
                    quote=True,
                ),
                _html_escape(item_id, quote=True),
                _html_escape(str(item.get("name") or item_id)),
                _html_escape(platform_text),
                _html_escape(category_label("agent", item.get("category"))),
            )
        )
    for item in skills:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "").strip()
        enabled = bool(item.get("enabled"))
        executable = bool(item.get("executable"))
        platforms = " ".join(item_platform_ids(item))
        platform_text = item_platform_label(item)
        status = "可执行" if executable else "可用于任务"
        if not enabled:
            status = "未启用"
        cards.append(
            '<label class="agent-skill-item" data-market-kind="skill" '
            'data-market-id="{}" data-category="{}" data-platforms="{}" data-enabled="{}" data-search="{}"><input type="checkbox" '
            'data-agent-skill-choice="skill" value="{}"{}><span><b>{}</b>'
            '<small>平台：{} · 用途：{}</small></span><em>{}</em></label>'.format(
                _html_escape(item_id, quote=True),
                _html_escape(str(item.get("category") or "other"), quote=True),
                _html_escape(platforms, quote=True),
                "true" if enabled else "false",
                _html_escape(
                    f"{item_id} {item.get('name') or ''} {item.get('description') or ''} {platform_text}".lower(),
                    quote=True,
                ),
                _html_escape(item_id, quote=True),
                "" if enabled else " disabled",
                _html_escape(str(item.get("name") or item_id)),
                _html_escape(platform_text),
                _html_escape(category_label("skill", item.get("category"))),
                status,
            )
        )

    connection_status_labels = {
        "connected_verified": "已连接并验证",
        "verified_callable": "近期实测可用",
        "registered_unverified": "已登记待验证",
        "installed_requires_live_verification": "已安装待回传验证",
        "installed_requires_project_enablement": "已安装 · 选择项目启用",
        "not_checked": "已安装待检测",
        "not_installed": "未安装",
        "configured_in_codex_unverified_in_t_one": "Codex 已配置 · T One 待验证",
        "catalog_candidate_unverified": "可连接候选 · 未安装/未验证",
        "unknown": "状态未知",
    }
    for item in external_agents:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "").strip()
        category = str(item.get("category") or "management_automation")
        platforms = " ".join(item_platform_ids(item))
        platform_text = item_platform_label(item)
        status_key = str(item.get("status") or "registered_unverified")
        detail = connection_status_labels.get(status_key, status_key)
        capabilities = "、".join(str(value) for value in item.get("capabilities", [])[:3])
        if capabilities:
            detail += " · " + capabilities
        cards.insert(0,
            '<article class="agent-skill-item capability-connection-item" data-market-kind="agent" '
            'data-market-id="{}" data-category="{}" data-platforms="{}" data-enabled="{}" data-search="{}"><span><b>{}</b>'
            '<small>平台：{} · {}</small></span><em>未安装 · 不可用于任务</em></article>'.format(
                _html_escape(item_id, quote=True),
                _html_escape(category, quote=True),
                _html_escape(platforms, quote=True),
                "true" if item.get("installed") else "false",
                _html_escape(f"{item_id} {item.get('name') or ''} {capabilities} {category_label('agent', category)} {platform_text}".lower(), quote=True),
                _html_escape(str(item.get("name") or "Agent")),
                _html_escape(platform_text),
                _html_escape(detail),
            )
        )
    for item in mcp_tools:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "").strip()
        category = str(item.get("category") or "general_tools")
        platforms = " ".join(item_platform_ids(item))
        platform_text = item_platform_label(item)
        status_key = str(item.get("status") or "unknown")
        detail = connection_status_labels.get(status_key, status_key)
        if item.get("connected"):
            detail += f" · 已启用 {int(item.get('enabled_tool_count') or 0)} / 发现 {int(item.get('discovered_tool_count') or 0)}"
        cards.append(
            '<article class="agent-skill-item capability-connection-item" data-market-kind="mcp" '
            'data-market-id="{}" data-category="{}" data-platforms="{}" data-enabled="true" data-search="{}"><span><b>{}</b>'
            '<small>平台：{} · {}</small></span><em>{}</em></article>'.format(
                _html_escape(item_id, quote=True),
                _html_escape(category, quote=True),
                _html_escape(platforms, quote=True),
                _html_escape(f"{item_id} {item.get('name') or ''} {category_label('mcp', category)} {platform_text}".lower(), quote=True),
                _html_escape(str(item.get("name") or "MCP")),
                _html_escape(platform_text),
                _html_escape(detail),
                _html_escape(category_label("mcp", category)),
            )
        )
    for item in cli_tools:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "").strip()
        category = str(item.get("category") or "general_tools")
        platforms = " ".join(item_platform_ids(item))
        platform_text = item_platform_label(item)
        status_key = str(item.get("status") or "unknown")
        detail = connection_status_labels.get(status_key, status_key)
        if str(item.get("model") or "").strip():
            detail += " · " + str(item.get("model") or "").strip()
        cards.append(
            '<article class="agent-skill-item capability-connection-item" data-market-kind="cli" '
            'data-market-id="{}" data-category="{}" data-platforms="{}" data-enabled="true" data-search="{}"><span><b>{}</b>'
            '<small>平台：{} · {}</small></span><em>{}</em></article>'.format(
                _html_escape(item_id, quote=True),
                _html_escape(category, quote=True),
                _html_escape(platforms, quote=True),
                _html_escape(f"{item_id} {item.get('name') or ''} {item.get('model') or ''} {category_label('cli', category)} {platform_text}".lower(), quote=True),
                _html_escape(str(item.get("name") or item_id)),
                _html_escape(platform_text),
                _html_escape(detail),
                _html_escape(category_label("cli", category)),
            )
        )

    encoded_snapshot = _json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )
    section = f"""
<section class="agent-skill-market" data-agent-skill-market="true" aria-label="选择任务能力和管理工具连接">
  <div class="market-return-task" id="marketReturnTask" hidden><span><b id="marketReturnTaskTitle">正在配置当前任务</b><small>保存后直接回到任务继续执行。</small></span><a id="marketReturnTaskLink" data-return-to-task="true" href="/desktop?view=new">返回任务</a></div>
  <nav class="capability-type-nav" aria-label="能力类型"><button type="button" data-capability-type="agent" data-market-connection="agent" aria-pressed="false"><b>Agent</b><small>岗位与外部 · {len(agents) + len(external_agents)}</small></button><button type="button" data-capability-type="skill" data-market-connection="skill" aria-pressed="true"><b>Skill</b><small>规则与流程 · {len(skills)}</small></button><button type="button" data-capability-type="mcp" data-market-connection="mcp" aria-pressed="false"><b>MCP</b><small>工具连接 · {len(mcp_tools)}</small></button><button type="button" data-capability-type="cli" data-market-connection="cli" aria-pressed="false"><b>CLI</b><small>本地执行 · {len(cli_tools)}</small></button></nav>
  <div class="capability-category-bar"><label>业务平台<select id="capabilityPlatform" aria-label="按业务平台分类"><option value="all">全部平台</option></select></label><label>用途分类<select id="capabilityCategory" aria-label="按用途分类"><option value="all">全部用途</option></select></label><label>搜索当前分类<input id="agentSkillSearch" type="search" placeholder="输入名称、编号、平台或用途" autocomplete="off"></label><span id="capabilityVisibleCount" aria-live="polite"></span></div>
  <div class="capability-connection-guide" id="marketConnectionGuide" data-market-connection-guide="true" hidden><span><b id="marketConnectionGuideTitle">管理工具连接</b><small>安装、验证和账号配置统一在连接设置中完成。</small></span><a href="{connection_href}">统一管理连接</a></div>
  <details class="project-ai-composer" data-project-ai-composer="true" data-market-type-panel="cli" hidden><summary><b>按项目搭配 AI</b><small>展开设置</small></summary><div class="project-ai-head"><span><b>项目 AI 组合</b><small>只保存组合，不会自动调用。</small></span><select id="projectAiTarget" aria-label="选择 AI 组合所属项目">{ai_project_options}</select></div><div class="project-ai-grid">{''.join(ai_cards)}</div><div class="project-ai-actions"><label><input type="checkbox" id="projectSkillAutoDownload"> Skill 按需下载</label><button type="button" id="saveProjectAiBundle"{' disabled' if not ai_project_options else ''}>保存项目 AI 组合</button><span id="projectAiStatus" role="status" aria-live="polite">选择项目查看组合。</span></div></details>
  <section class="deepseek-harness-panel" id="deepseekHarnessPanel" data-market-type-panel="cli" hidden><span><b>DeepSeek Harness 官方开源底座</b><small>{_html_escape(('已安装 ' + str(harness.get('version') or '') + ' · MIT') if harness.get('installed') else '本机未安装')}</small></span><select id="deepseekHarnessTarget" aria-label="选择 Harness 使用的项目或任务">{harness_target_options}</select><button type="button" id="prepareDeepseekHarness"{' disabled' if not harness.get('installed') or not harness_target_options else ''}>给此文件夹启用</button><button type="button" id="openDeepseekHarness"{' disabled' if not harness.get('installed') or not harness_target_options else ''}>启用并打开</button><output id="deepseekHarnessStatus" aria-live="polite">共用一套 Harness；每个文件夹只保存小型接线。</output></section>
  <div class="market-assignment-panel" id="marketAssignmentPanel"><div class="agent-skill-market-toolbar"><label>用于哪个任务<select id="agentSkillTargetTask" aria-label="选择要使用这些能力的任务">{task_options}</select></label></div>
    <section class="shein-manual-operator" id="sheinManualOperator" data-shein-manual-operator="true" hidden><b>SHEIN 人工操作台</b><small>按当前任务和店铺隔离本地材料；订单刷新只读取店铺级汇总，不回传订单号、客户姓名、电话或地址。</small><div class="shein-manual-actions"><button type="button" data-shein-manual-action="collect">打开采集任务夹</button><button type="button" data-shein-manual-action="keywords">生成去重词库</button><button type="button" data-shein-manual-action="batch-listing">打开批量上架预检</button><button type="button" data-shein-store-surface="inventory">打开当前店铺商品页（只读）</button><button type="button" data-shein-store-surface="orders">刷新当前店铺订单（只读）</button><button type="button" data-shein-parallel-surface="orders">并行刷新本项目全部 SHEIN 店铺</button></div><span id="sheinManualStatus" role="status" aria-live="polite">本地准备，店铺写入 0。</span></section>
  </div>
  <div class="agent-skill-market-actions market-assignment-panel" id="marketAssignmentActions"><button type="button" id="saveAgentSkillSelection"{' disabled' if not task_options else ''}>保存任务搭配</button><span id="agentSkillMarketStatus" role="status" aria-live="polite">勾选 Agent 或 Skill 后保存。</span></div>
  <p class="smart-capability-manager-note market-assignment-panel" data-smart-capability-manager="true"><b>智能管理已开启</b>：任务保留能力清单；每轮最多选择 2 个 Agent 和 3 个 Skill，不把全部 Skill 正文塞进上下文。</p>
  <div class="agent-skill-market-grid" id="agentSkillMarketGrid">{''.join(cards)}</div>
</section>
<script type="application/json" id="agentSkillMarketData">{encoded_snapshot}</script>
<script data-agent-skill-market-script="true">
(()=>{{
const dataNode=document.getElementById('agentSkillMarketData');const target=document.getElementById('agentSkillTargetTask');const search=document.getElementById('agentSkillSearch');const save=document.getElementById('saveAgentSkillSelection');const status=document.getElementById('agentSkillMarketStatus');const sheinOperator=document.getElementById('sheinManualOperator');const sheinStatus=document.getElementById('sheinManualStatus');const platform=document.getElementById('capabilityPlatform');const category=document.getElementById('capabilityCategory');const visibleCount=document.getElementById('capabilityVisibleCount');const assignmentPanel=document.getElementById('marketAssignmentPanel');const assignmentActions=document.getElementById('marketAssignmentActions');const projectAiComposer=document.querySelector('[data-project-ai-composer="true"]');const connectionGuide=document.getElementById('marketConnectionGuide');const connectionGuideTitle=document.getElementById('marketConnectionGuideTitle');const returnPanel=document.getElementById('marketReturnTask');const returnTitle=document.getElementById('marketReturnTaskTitle');const returnLink=document.getElementById('marketReturnTaskLink');
if(!dataNode||!target||!search||!save||!status||!platform||!category)return;const data=JSON.parse(dataNode.textContent||'{{}}');const tasks=new Map((data.tasks||[]).map(item=>[item.id,item]));const known={{skill:new Set((data.skills||[]).map(item=>item.id)),agent:new Set((data.agents||[]).map(item=>item.id))}};let filter='skill';
const routeParams=new URLSearchParams(location.search);const requestedTask=String(routeParams.get('target_task')||'');const returnProject=String(routeParams.get('return_project')||'');const returnTask=String(routeParams.get('return_task')||'');const safeId=value=>/^[a-z0-9][a-z0-9._-]{{0,159}}$/i.test(value);let returnHref='';if(requestedTask&&[...target.options].some(option=>option.value===requestedTask))target.value=requestedTask;if(safeId(returnTask)){{returnHref='/desktop?'+(safeId(returnProject)?'project='+encodeURIComponent(returnProject)+'&':'')+'task='+encodeURIComponent(returnTask);if(returnPanel&&returnLink){{returnPanel.hidden=false;returnLink.href=returnHref;const selected=tasks.get(target.value);if(returnTitle)returnTitle.textContent='正在配置：'+String(selected?.label||selected?.name||target.selectedOptions[0]?.textContent||'当前任务');save.textContent='保存并返回任务';}}}}
const projectAiTarget=document.getElementById('projectAiTarget');const projectAiStatus=document.getElementById('projectAiStatus');const projectAiSave=document.getElementById('saveProjectAiBundle');const projectAutoDownload=document.getElementById('projectSkillAutoDownload');const projectProfiles=new Map((data.project_ai?.projects||[]).map(item=>[item.id,item]));const harnessPanel=document.getElementById('deepseekHarnessPanel');const harnessTarget=document.getElementById('deepseekHarnessTarget');const harnessPrepare=document.getElementById('prepareDeepseekHarness');const harnessOpen=document.getElementById('openDeepseekHarness');const harnessStatus=document.getElementById('deepseekHarnessStatus');
const choices=kind=>[...document.querySelectorAll('[data-agent-skill-choice="'+kind+'"]')];const unique=items=>[...new Set(items.map(value=>String(value||'').trim()).filter(Boolean))];
function currentTask(){{return tasks.get(target.value)||{{toolkit:{{plugins:[],skills:[],agents:[]}}}};}}
 function renderProjectAi(){{if(!projectAiTarget)return;const profile=projectProfiles.get(projectAiTarget.value)||{{}};const selected=new Set(profile.participant_ids||[]);document.querySelectorAll('[data-project-ai-choice]').forEach(input=>input.checked=selected.has(input.value));if(projectAutoDownload)projectAutoDownload.checked=Boolean(profile.auto_download_skills);if(projectAiStatus){{delete projectAiStatus.dataset.state;projectAiStatus.textContent='已选择 '+selected.size+' 个 AI；Skill 使用共享存储。';}}}}
 function renderSelection(){{const task=currentTask();const toolkit=task.toolkit||{{}};for(const kind of ['skill','agent']){{const selected=new Set(toolkit[kind+'s']||[]);choices(kind).forEach(input=>input.checked=selected.has(input.value));}}const customSkills=(toolkit.skills||[]).filter(value=>!known.skill.has(value));const customAgents=(toolkit.agents||[]).filter(value=>!known.agent.has(value));status.dataset.state='';status.textContent='已载入任务配置；保留自定义 Skill '+customSkills.length+' 项、Agent '+customAgents.length+' 项。';if(sheinOperator){{sheinOperator.hidden=filter!=='skill'||String(task.platform||'').toLowerCase()!=='shein';if(sheinStatus&&!sheinOperator.hidden){{delete sheinStatus.dataset.state;sheinStatus.textContent='当前店铺 '+String(task.store_id||'未绑定')+'；本地准备。';}}}}if(projectAiTarget&&task.project_id&&projectProfiles.has(task.project_id)){{projectAiTarget.value=task.project_id;renderProjectAi();}}if(harnessTarget&&task.id&&[...harnessTarget.options].some(option=>option.value==='task|'+task.id))harnessTarget.value='task|'+task.id;}}
function renderCategories(){{const labels=data.taxonomy?.category_labels?.[filter]||{{}};const current=category.value;category.innerHTML='<option value="all">全部用途</option>'+Object.entries(labels).map(([value,label])=>'<option value="'+value+'">'+label+'</option>').join('');if([...category.options].some(option=>option.value===current))category.value=current;}}
function renderPlatforms(){{const labels=data.taxonomy?.platform_labels||{{}};const available=new Set([...document.querySelectorAll('.agent-skill-item')].filter(row=>row.dataset.marketKind===filter).flatMap(row=>String(row.dataset.platforms||'general').split(/\\s+/).filter(Boolean)));const current=platform.value;platform.innerHTML='<option value="all">全部平台</option>'+Object.entries(labels).filter(([value])=>available.has(value)).map(([value,label])=>'<option value="'+value+'">'+label+'</option>').join('');if([...platform.options].some(option=>option.value===current))platform.value=current;}}
function applyFilter(){{const query=search.value.trim().toLowerCase();let shown=0;document.querySelectorAll('.agent-skill-item').forEach(row=>{{const typeMatch=row.dataset.marketKind===filter;const platformMatch=platform.value==='all'||String(row.dataset.platforms||'general').split(/\\s+/).includes(platform.value);const categoryMatch=category.value==='all'||row.dataset.category===category.value;const searchMatch=!query||String(row.dataset.search||'').includes(query);row.hidden=!(typeMatch&&platformMatch&&categoryMatch&&searchMatch);if(!row.hidden)shown+=1;}});if(visibleCount)visibleCount.textContent='显示 '+shown+' 项';const assignable=filter==='agent'||filter==='skill';const connectable=filter==='mcp'||filter==='cli';if(assignmentPanel)assignmentPanel.hidden=!assignable;if(assignmentActions)assignmentActions.hidden=!assignable;if(connectionGuide)connectionGuide.hidden=!connectable;if(connectionGuideTitle&&connectable)connectionGuideTitle.textContent=filter==='mcp'?'管理 MCP 连接':'管理 CLI 工具';if(projectAiComposer)projectAiComposer.hidden=filter!=='cli';if(harnessPanel)harnessPanel.hidden=filter!=='cli';renderSelection();}}
function selectType(next){{filter=next;document.querySelectorAll('[data-capability-type]').forEach(item=>item.setAttribute('aria-pressed',String(item.dataset.capabilityType===filter)));renderPlatforms();renderCategories();applyFilter();}}
document.querySelectorAll('[data-capability-type]').forEach(button=>button.addEventListener('click',()=>selectType(button.dataset.capabilityType||'skill')));platform.addEventListener('change',applyFilter);category.addEventListener('change',applyFilter);search.addEventListener('input',applyFilter);target.addEventListener('change',renderSelection);
 if(projectAiTarget)projectAiTarget.addEventListener('change',renderProjectAi);if(projectAiSave)projectAiSave.addEventListener('click',async()=>{{try{{const participantIds=[...document.querySelectorAll('[data-project-ai-choice]:checked')].map(input=>input.value);if(participantIds.length&&participantIds.length<2)throw new Error('项目多 AI 组合至少选择 2 个 AI。');projectAiSave.disabled=true;projectAiStatus.textContent='正在保存…';let result;if(window.pywebview?.api?.save_project_capability_profile)result=await window.pywebview.api.save_project_capability_profile({{project_id:projectAiTarget.value,participant_ids:participantIds,auto_download_skills:Boolean(projectAutoDownload?.checked)}});else if(window.teelabDesktop?.isDesktop&&window.teelabDesktop?.invoke)result=await window.teelabDesktop.invoke('save_project_capability_profile',{{project_id:projectAiTarget.value,participant_ids:participantIds,auto_download_skills:Boolean(projectAutoDownload?.checked)}});else throw new Error('请在 T One 桌面版保存项目 AI 组合。');if(!result?.ok)throw new Error(result?.error||'项目 AI 组合没有保存。');const profile=projectProfiles.get(projectAiTarget.value)||{{id:projectAiTarget.value}};profile.participant_ids=participantIds;profile.auto_download_skills=Boolean(projectAutoDownload?.checked);projectProfiles.set(projectAiTarget.value,profile);projectAiStatus.dataset.state='ok';projectAiStatus.textContent='已保存；Skill 按需下载 '+(profile.auto_download_skills?'已开启。':'已关闭。');}}catch(error){{projectAiStatus.dataset.state='error';projectAiStatus.textContent=error.message||'项目 AI 组合没有保存。';}}finally{{projectAiSave.disabled=!projectAiTarget?.value;}}}});
async function callHarness(method,payload){{if(window.pywebview?.api?.[method])return await window.pywebview.api[method](payload);if(window.teelabDesktop?.isDesktop&&window.teelabDesktop?.invoke)return await window.teelabDesktop.invoke(method,payload);throw new Error('请在 T One Windows 桌面版使用 DeepSeek Harness。');}}
async function runHarness(openAfter){{const raw=String(harnessTarget?.value||'');const split=raw.indexOf('|');const itemType=split>0?raw.slice(0,split):'';const itemId=split>0?raw.slice(split+1):'';if(!itemType||!itemId)throw new Error('请先选择项目或任务。');const button=openAfter?harnessOpen:harnessPrepare;try{{button.disabled=true;delete harnessStatus.dataset.state;harnessStatus.textContent=openAfter?'正在启动官方 Harness…':'正在给文件夹启用…';const method=openAfter?'open_deepseek_harness':'prepare_deepseek_harness_project';const result=await callHarness(method,{{item_type:itemType,item_id:itemId,owner_confirmed:Boolean(openAfter)}});if(!result?.ok)throw new Error(result?.error||'DeepSeek Harness 未能启用。');harnessStatus.dataset.state='ok';harnessStatus.textContent=openAfter?'已打开；当前文件夹和 T One 工具已经接入。':'已启用：'+String(result.local_folder||itemId);if(openAfter&&result.url){{if(window.teelabDesktop?.openExternal)await window.teelabDesktop.openExternal(result.url);else window.open(result.url,'_blank','noopener');}}}}catch(error){{harnessStatus.dataset.state='error';harnessStatus.textContent=error.message||'DeepSeek Harness 未能启用。';}}finally{{button.disabled=false;}}}}
if(harnessPrepare)harnessPrepare.addEventListener('click',()=>runHarness(false));if(harnessOpen)harnessOpen.addEventListener('click',()=>runHarness(true));
async function persist(payload){{if(window.pywebview?.api?.save_task_configuration)return await window.pywebview.api.save_task_configuration(payload);if(window.teelabDesktop?.isDesktop&&window.teelabDesktop?.invoke)return await window.teelabDesktop.invoke('save_task_configuration',payload);const response=await fetch('/api/v1/task-configuration',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload)}});const result=await response.json();if(!response.ok)throw new Error(result.error||'任务能力没有保存。');return result;}}
async function prepareSkillPackages(taskId,skillIds){{const payload={{task_id:taskId,skill_ids:skillIds}};if(window.pywebview?.api?.prepare_task_skill_packages)return await window.pywebview.api.prepare_task_skill_packages(payload);if(window.teelabDesktop?.isDesktop&&window.teelabDesktop?.invoke)return await window.teelabDesktop.invoke('prepare_task_skill_packages',payload);const response=await fetch('/api/v1/task-skills/prepare',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload)}});const result=await response.json();if(!response.ok)throw new Error(result.error||'Skill 按需准备失败。');return result;}}
async function prepareSheinWorkspace(taskId,action){{const payload={{task_id:taskId,action,open_folder:true}};if(window.pywebview?.api?.prepare_shein_manual_workspace)return await window.pywebview.api.prepare_shein_manual_workspace(payload);if(window.teelabDesktop?.isDesktop&&window.teelabDesktop?.invoke)return await window.teelabDesktop.invoke('prepare_shein_manual_workspace',payload);throw new Error('请在 T One 桌面版打开 SHEIN 人工操作台。');}}
 document.querySelectorAll('[data-shein-manual-action]').forEach(button=>button.addEventListener('click',async()=>{{const task=currentTask();const action=button.dataset.sheinManualAction||'';try{{if(String(task.platform||'').toLowerCase()!=='shein')throw new Error('请先选择 SHEIN 店铺任务。');button.disabled=true;sheinStatus.textContent='正在准备当前任务的本地材料…';const result=await prepareSheinWorkspace(task.id,action);if(!result?.ok)throw new Error(result?.error||'SHEIN 本地工作台未能准备。');sheinStatus.dataset.state='ok';const terms=Number(result.keyword_stats?.terms||0);sheinStatus.textContent=action==='keywords'?'已生成 '+terms+' 条去重词；尚未生成可上架商品。':'已打开 '+String(result.local_folder||'任务文件夹')+'。';}}catch(error){{sheinStatus.dataset.state='error';sheinStatus.textContent=error.message||'SHEIN 本地工作台未能准备。';}}finally{{button.disabled=false;}}}}));
 document.querySelectorAll('[data-shein-store-surface]').forEach(button=>button.addEventListener('click',async()=>{{const task=currentTask();const surface=String(button.dataset.sheinStoreSurface||'inventory');try{{if(String(task.platform||'').toLowerCase()!=='shein')throw new Error('请先选择 SHEIN 店铺任务。');button.disabled=true;sheinStatus.textContent=surface==='orders'?'正在只读刷新当前店铺订单汇总…':'正在打开当前店铺商品页（只读）…';let result;if(window.pywebview?.api?.open_store_surface)result=await window.pywebview.api.open_store_surface(surface,task);else if(window.teelabDesktop?.isDesktop&&window.teelabDesktop?.invoke)result=await window.teelabDesktop.invoke('open_store_surface',surface,task);else throw new Error('请在 T One 桌面版打开店铺。');if(!result?.ok)throw new Error(result?.error||(surface==='orders'?'订单数据没有通过只读检查。':'店铺商品页没有通过只读检查。'));sheinStatus.dataset.state='ok';if(surface==='orders'){{const summary=result.order_summary||{{}};sheinStatus.textContent='已回传 '+String(result.store_id||task.store_id||'当前店铺')+'：订单 '+Number(summary.order_count||0)+'，商品 '+Number(summary.unit_count||0)+'，商品总价 '+String(summary.gross_sales||'0')+'，预计收入 '+String(summary.expected_income||'0')+'；'+String(summary.window_start||'未标日期')+' 至 '+String(summary.window_end||'未标日期')+'。店铺写入 0。';}}else{{sheinStatus.textContent='已打开 '+String(result.store_id||task.store_id||'当前店铺')+' 商品页（只读）。';}}}}catch(error){{sheinStatus.dataset.state='error';sheinStatus.textContent=error.message||(surface==='orders'?'订单数据没有通过只读检查。':'店铺商品页没有通过只读检查。');}}finally{{button.disabled=false;}}}}));
 document.querySelectorAll('[data-shein-parallel-surface]').forEach(button=>button.addEventListener('click',async()=>{{const task=currentTask();const surface=String(button.dataset.sheinParallelSurface||'orders');try{{if(String(task.platform||'').toLowerCase()!=='shein'||!task.project_id)throw new Error('请先选择已归属项目的 SHEIN 店铺任务。');button.disabled=true;sheinStatus.textContent='正在并行处理本项目全部已验证 SHEIN 指纹环境…';let result;if(window.pywebview?.api?.open_store_surfaces_parallel)result=await window.pywebview.api.open_store_surfaces_parallel(surface,{{project_id:task.project_id,max_parallel:8}});else if(window.teelabDesktop?.isDesktop&&window.teelabDesktop?.invoke)result=await window.teelabDesktop.invoke('open_store_surfaces_parallel',surface,{{project_id:task.project_id,max_parallel:8}});else throw new Error('请在 T One 桌面版并行打开店铺。');if(!result?.ok)throw new Error(result?.error||result?.message||'批量店铺检查未全部通过。');sheinStatus.dataset.state='ok';sheinStatus.textContent='已并行完成 '+Number(result.success_count||0)+'/'+Number(result.target_count||0)+' 个指纹环境；店铺写入 '+Number(result.external_store_write_actions||0)+'。回执：'+String(result.receipt_path||'已保存');}}catch(error){{sheinStatus.dataset.state='error';sheinStatus.textContent=error.message||'批量店铺检查失败。';}}finally{{button.disabled=false;}}}}));
 save.addEventListener('click',async()=>{{try{{const task=currentTask();if(!task.id)throw new Error('请先选择任务。');const old=task.toolkit||{{}};const customSkills=(old.skills||[]).filter(value=>!known.skill.has(value));const customAgents=(old.agents||[]).filter(value=>!known.agent.has(value));const selectedSkills=choices('skill').filter(input=>input.checked&&!input.disabled).map(input=>input.value);const selectedAgents=choices('agent').filter(input=>input.checked&&!input.disabled).map(input=>input.value);save.disabled=true;status.dataset.state='';status.textContent='正在保存任务搭配…';const prepared=await prepareSkillPackages(task.id,selectedSkills);if(!prepared?.ok)throw new Error(prepared?.error||'Skill 按需准备失败。');const result=await persist({{task_id:task.id,toolkit:{{plugins:unique(old.plugins||[]),skills:unique([...customSkills,...selectedSkills]),agents:unique([...customAgents,...selectedAgents])}}}});if(!result?.ok)throw new Error(result?.error||'任务搭配没有保存。');task.toolkit=result.toolkit||task.toolkit;status.dataset.state='ok';status.textContent='已保存：Skill '+selectedSkills.length+' 项，Agent '+selectedAgents.length+' 项；新下载 '+Number(prepared.downloaded_count||0)+' 个。';if(returnHref)setTimeout(()=>{{if(typeof desktopNavigate==='function')desktopNavigate(returnHref);else location.assign(returnHref);}},350);}}catch(error){{status.dataset.state='error';status.textContent=error.message||'任务搭配没有保存。';}}finally{{save.disabled=!target.value;}}}});renderProjectAi();renderSelection();selectType('skill');
}})();
</script>
"""
    insertion_index += len(marker)
    updated = html[:insertion_index] + section + html[insertion_index:]
    for legacy_class in (
        "control-summary",
        "capability-marketplace-overview",
        "extension-tasks",
        "pack-installer",
        "extension-registry-layout",
    ):
        updated = _remove_html_element_by_class(updated, legacy_class)
    if _AGENT_SKILL_MARKET_CSS.strip() not in updated:
        updated = updated.replace("</style>", _AGENT_SKILL_MARKET_CSS + "</style>", 1)
    replacements = (
        ("<title>扩展 · T-one</title>", "<title>能力市场 · T-one</title>"),
        ('<div class="crumb"><b>扩展</b>', '<div class="crumb"><b>能力市场</b>'),
        ('<div class="task-intro"><h1>扩展</h1><p>插件、Skills、智能体和模型</p></div>', ""),
    )
    for old, new in replacements:
        updated = updated.replace(old, new, 1)
    return updated.replace("打开能力中心", "打开能力市场").replace(
        "连接工具、插件、Skills、可执行智能体和能力包在这里分类",
        "Agent、Skill、插件和能力包在这里按任务配置",
    )


def _rename_capability_market_links(html: str) -> str:
    return html.replace("打开能力中心", "打开能力市场").replace(
        "连接工具、插件、Skills、可执行智能体和能力包在这里分类",
        "Agent、Skill、插件和能力包在这里按任务配置",
    )


def _ensure_capability_market_sidebar_link(html: str) -> str:
    if 'data-capability-market-nav="true"' in html:
        return html
    module_link = 'href="/desktop?view=module_dashboard"'
    module_index = html.find(module_link)
    closing_index = html.find("</a>", module_index)
    if module_index < 0 or closing_index < 0:
        return html
    active = " active" if 'data-view="extensions"' in html else ""
    link = (
        f'<a class="overview-link{active}" data-capability-market-nav="true" '
        'href="/desktop?view=extensions&amp;project=system&amp;task=system-extensions">'
        '<b>能力市场</b><small>选择任务能力，管理工具连接</small></a>'
    )
    insertion_index = closing_index + len("</a>")
    return html[:insertion_index] + link + html[insertion_index:]


def _ensure_settings_section_deep_link(html: str) -> str:
    if (
        'data-t-one-settings-deep-link="true"' in html
        or 'data-view="settings_center"' not in html
    ):
        return html
    script = """
<script data-t-one-settings-deep-link="true">
(()=>{const requested=String(location.hash||'').replace(/^#/, '');if(!requested)return;requestAnimationFrame(()=>{if(typeof focusSettingsSection==='function')focusSettingsSection(requested);});})();
</script>
"""
    return html.replace("</body>", script + "</body>", 1)


_TASK_HISTORY_CONTEXT_CSS = """
.task-history-context{margin-top:16px;border:1px solid #dce5e4;border-radius:10px;background:#f8fbfa}
.task-history-context>summary{display:flex;align-items:center;gap:12px;padding:12px 14px;cursor:pointer;list-style:none}.task-history-context>summary::-webkit-details-marker{display:none}.task-history-context>summary span{min-width:0;flex:1}.task-history-context>summary b,.task-history-context>summary small{display:block}.task-history-context>summary b{font-size:12px}.task-history-context>summary small{margin-top:3px;color:var(--muted);font-size:11px}.task-history-context>summary em{color:var(--accent);font-size:11px;font-style:normal;white-space:nowrap}
.task-history-context-body{border-top:1px solid #e2eae8;padding:0 14px 12px}.task-history-context-note{margin:10px 0;color:var(--muted);font-size:11px;line-height:1.55}.task-history-context-list{display:grid;gap:8px}.task-history-row{padding:10px;border:1px solid #e2e7e9;border-radius:8px;background:#fff}.task-history-row header{display:flex;align-items:center;gap:8px}.task-history-row header b{flex:1;font-size:12px}.task-history-row header time,.task-history-row header em{font-size:10px;color:var(--muted);font-style:normal}.task-history-row p{margin:7px 0 0;color:#394148;font-size:11px;line-height:1.55;white-space:pre-wrap}.task-history-row p+small{display:block;margin-top:7px;color:var(--muted);font-size:10px;line-height:1.5;white-space:pre-wrap}.task-history-empty{margin:10px 0 0;color:var(--muted);font-size:11px}
"""


_TASK_HISTORY_CONTEXT_SCRIPT = """
<script data-t-one-task-history-context="true">
(()=>{
  const panel=document.querySelector('[data-history-context="true"]'),list=document.getElementById('taskHistoryContextList'),count=document.getElementById('taskHistoryContextCount');
  if(!panel||!list||!count||typeof TASK!=='object'||!(TASK.task_id||TASK.id))return;
  let loaded=false,loading=false;
  const clean=value=>String(value||'').trim();
  const statusLabel=value=>({analysis_complete:'已分析',completed:'已完成',failed:'失败',needs_retry:'待重试',needs_input:'待补资料',needs_confirmation:'待确认'}[clean(value)]||clean(value)||'未知');
  const formatTime=value=>{if(!value)return'';const date=new Date(value);return Number.isNaN(date.getTime())?clean(value):date.toLocaleString('zh-CN',{hour12:false});};
  const append=(tag,className,text)=>{const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node;};
  async function call(payload){if(window.pywebview?.api?.task_history_context_snapshot)return await window.pywebview.api.task_history_context_snapshot(payload);if(window.teelabDesktop?.isDesktop&&window.teelabDesktop?.invoke)return await window.teelabDesktop.invoke('task_history_context_snapshot',payload);throw new Error('请在 T One Windows 桌面版查看历史上下文。');}
  function render(result){
    list.replaceChildren();const history=Array.isArray(result.history)?result.history:[],memory=Array.isArray(result.memory)?result.memory:[];
    count.textContent=history.length+' 条记录'+(memory.length?' · '+memory.length+' 条记忆':'');
    history.forEach(item=>{const row=append('article','task-history-row');const head=append('header');head.append(append('b','',clean(item.instruction)||'未记录指令'));head.append(append('em','',statusLabel(item.status)));head.append(append('time','',formatTime(item.updated_at||item.created_at)));row.append(head);if(clean(item.result_message))row.append(append('p','',clean(item.result_message)));list.append(row);});
    memory.forEach(item=>{const row=append('article','task-history-row');const head=append('header');head.append(append('b','','已确认任务记忆'));head.append(append('em','',item.trust_state==='reviewed_local_experience_memory'?'已复核':'本地记忆'));row.append(head);row.append(append('p','',clean(item.summary)||'已保留该任务的确认记忆。'));list.append(row);});
    if(!history.length&&!memory.length)list.append(append('p','task-history-empty','当前任务还没有可显示的保留记录。'));
  }
  async function load(){if(loaded||loading)return;loading=true;count.textContent='正在读取…';try{const result=await call({task_id:String(TASK.task_id||TASK.id),project_id:String(TASK.project_id||''),limit:20});if(!result?.ok)throw new Error(result?.error||'历史上下文读取失败。');render(result);loaded=true;}catch(error){list.replaceChildren(append('p','task-history-empty',clean(error?.message)||'历史上下文读取失败。'));count.textContent='读取失败';}finally{loading=false;}}
  panel.addEventListener('toggle',()=>{if(panel.open)load();});
})();
</script>
"""


def _ensure_task_history_context(html: str) -> str:
    if 'data-history-context="true"' in html or "const TASK=" not in html:
        return html
    marker = '<details class="task-context task-context-chat-first"'
    marker_index = html.find(marker)
    if marker_index < 0:
        return html
    block = """
<details class="task-history-context" data-history-context="true">
  <summary><span><b>历史上下文</b><small>查看当前任务已保留的运行记录和确认记忆。</small></span><em id="taskHistoryContextCount">点击查看</em></summary>
  <div class="task-history-context-body"><p class="task-history-context-note">只读取当前任务的保留记录；已删除的旧会话不会重建，也不会混入其他项目或店铺。</p><div class="task-history-context-list" id="taskHistoryContextList" aria-live="polite"></div></div>
</details>"""
    updated = html[:marker_index] + block + html[marker_index:]
    if _TASK_HISTORY_CONTEXT_CSS.strip() not in updated:
        updated = updated.replace("</style>", _TASK_HISTORY_CONTEXT_CSS + "</style>", 1)
    return updated.replace("</body>", _TASK_HISTORY_CONTEXT_SCRIPT + "</body>", 1)


_TASK_WORKFLOW_GUIDE_CSS = """
.task-workflow-guide{margin:16px 0 0;border:1px solid #cfe0dd;border-radius:11px;background:#f7fbfa;padding:13px 14px}.task-workflow-guide header{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}.task-workflow-guide h2{margin:0;font-size:14px}.task-workflow-guide header p{margin:5px 0 0;color:#435057;font-size:12px;line-height:1.5;white-space:pre-wrap}.task-workflow-guide header em{flex:0 0 auto;border-radius:999px;background:#e6f5f1;color:#0f766e;padding:5px 9px;font-size:11px;font-style:normal}
.task-workflow-steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:11px}.task-workflow-step{display:flex;align-items:center;justify-content:space-between;gap:8px;min-width:0;border:1px solid #d9e4e2;border-radius:8px;background:#fff;padding:9px 10px;color:var(--text);cursor:pointer;text-align:left}.task-workflow-step:hover,.task-workflow-step:focus-visible{border-color:#0f766e;outline:none}.task-workflow-step b,.task-workflow-step span{display:block}.task-workflow-step b{font-size:12px}.task-workflow-step span{margin-top:2px;color:var(--muted);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.task-workflow-step[data-ready="true"] span{color:#0f766e}
.task-brief-dialog{width:min(520px,calc(100vw - 32px));border:1px solid #d9dddf;border-radius:13px;padding:0;box-shadow:0 24px 70px rgba(20,30,36,.25);color:var(--text);background:#fff}.task-brief-dialog::backdrop{background:rgba(20,30,36,.34);backdrop-filter:blur(2px)}.task-brief-form{display:grid;gap:12px;padding:20px}.task-brief-form h2{margin:0;font-size:17px}.task-brief-form>p{margin:-4px 0 0;color:var(--muted);font-size:12px;line-height:1.5}.task-brief-form label{display:grid;gap:7px;color:#475158;font-size:12px}.task-brief-form textarea{width:100%;min-height:120px;border:1px solid var(--line);border-radius:8px;padding:10px;background:#fff;color:var(--text);font:inherit;line-height:1.5;resize:vertical;outline:none}.task-brief-form textarea:focus{border-color:#0f766e;box-shadow:0 0 0 3px rgba(15,118,110,.1)}.task-brief-actions{display:flex;align-items:center;justify-content:flex-end;gap:8px}.task-brief-actions button{border:1px solid var(--line);border-radius:8px;background:#fff;padding:8px 13px;color:var(--text);cursor:pointer}.task-brief-actions button[data-primary="true"]{border-color:#111;background:#111;color:#fff}.task-brief-status{min-height:18px;margin:0;color:var(--muted);font-size:11px}.task-brief-status[data-state="error"]{color:#a3342b}.task-brief-status[data-state="ok"]{color:#0f766e}
@media(max-width:850px){.task-workflow-steps{grid-template-columns:repeat(2,minmax(0,1fr))}.task-workflow-guide header{display:grid}.task-workflow-guide header em{justify-self:start}}
"""


_TASK_WORKFLOW_GUIDE = """
<section class="task-workflow-guide" data-task-workflow-guide="true" aria-labelledby="taskWorkflowTitle">
  <header><span><h2 id="taskWorkflowTitle">完成这项任务</h2><p id="taskWorkflowObjective">正在读取任务目标…</p></span><em id="taskWorkflowProgress">准备中</em></header>
  <div class="task-workflow-steps" aria-label="任务步骤">
    <button class="task-workflow-step" id="taskWorkflowEditGoal" type="button"><span><b>1　明确目标</b><span id="taskWorkflowGoalState">查看或修改</span></span></button>
    <a class="task-workflow-step" id="taskWorkflowCapabilities" href="/desktop?view=extensions"><span><b>2　选择能力</b><span id="taskWorkflowCapabilityState">Agent / Skill</span></span></a>
    <button class="task-workflow-step" id="taskWorkflowStart" type="button"><span><b>3　开始执行</b><span>在下方输入</span></span></button>
    <button class="task-workflow-step" id="taskWorkflowResults" type="button"><span><b>4　查看结果</b><span>历史与记忆</span></span></button>
  </div>
</section>
<dialog class="task-brief-dialog" id="taskBriefDialog" aria-labelledby="taskBriefDialogTitle">
  <form class="task-brief-form" id="taskBriefForm">
    <h2 id="taskBriefDialogTitle">任务目标</h2>
    <p>写清要完成什么、范围和交付结果；内容只保存到当前任务文件夹。</p>
    <label>目标与要求<textarea id="taskBriefInstruction" maxlength="2000" required placeholder="例如：整理本周订单，按店铺汇总数量与收入，不修改店铺数据。"></textarea></label>
    <p class="task-brief-status" id="taskBriefStatus" role="status" aria-live="polite"></p>
    <div class="task-brief-actions"><button id="cancelTaskBrief" type="button">取消</button><button id="saveTaskBrief" type="submit" data-primary="true">保存目标</button></div>
  </form>
</dialog>
<script data-t-one-task-workflow-guide-script="true">
(()=>{
  const root=document.querySelector('[data-task-workflow-guide="true"]'),objective=document.getElementById('taskWorkflowObjective'),progress=document.getElementById('taskWorkflowProgress'),goalState=document.getElementById('taskWorkflowGoalState'),edit=document.getElementById('taskWorkflowEditGoal'),capabilities=document.getElementById('taskWorkflowCapabilities'),start=document.getElementById('taskWorkflowStart'),results=document.getElementById('taskWorkflowResults'),history=document.querySelector('[data-history-context="true"]'),dialog=document.getElementById('taskBriefDialog'),form=document.getElementById('taskBriefForm'),input=document.getElementById('taskBriefInstruction'),status=document.getElementById('taskBriefStatus'),cancel=document.getElementById('cancelTaskBrief'),save=document.getElementById('saveTaskBrief');
  if(!root||typeof TASK!=='object'||!(TASK.task_id||TASK.id))return;
  const taskId=String(TASK.task_id||TASK.id),projectId=String(TASK.project_id||'');
  const clean=value=>String(value||'').trim();
  function refresh(){const brief=clean(TASK.initial_instruction),counts=TASK.toolkit_counts&&typeof TASK.toolkit_counts==='object'?TASK.toolkit_counts:{};const agents=Number(counts.agents||0),skills=Number(counts.skills||0);objective.textContent=brief||'还没有填写任务目标。';goalState.textContent=brief?'已记录':'需要补充';edit.dataset.ready=String(Boolean(brief));capabilities.dataset.ready=String(agents+skills>0);document.getElementById('taskWorkflowCapabilityState').textContent=agents+' Agent · '+skills+' Skill';progress.textContent=brief?'目标已记录':'先补充目标';}
  const marketParams=new URLSearchParams({view:'extensions',project:'system',task:'system-extensions',target_task:taskId,return_task:taskId});if(projectId)marketParams.set('return_project',projectId);capabilities.href='/desktop?'+marketParams.toString();
  edit.addEventListener('click',()=>{input.value=clean(TASK.initial_instruction);status.textContent='';delete status.dataset.state;dialog.showModal();requestAnimationFrame(()=>input.focus());});
  cancel.addEventListener('click',()=>dialog.close());
  form.addEventListener('submit',async event=>{event.preventDefault();const instruction=clean(input.value);if(!instruction){status.dataset.state='error';status.textContent='请填写任务目标。';return;}try{save.disabled=true;status.textContent='正在保存到当前任务…';delete status.dataset.state;const payload={item_type:'task',item_id:taskId,action:'update_brief',initial_instruction:instruction};let response;if(typeof updateWorkspaceItemRequest==='function')response=await updateWorkspaceItemRequest(payload);else if(window.teelabDesktop?.isDesktop&&window.teelabDesktop?.invoke)response=await window.teelabDesktop.invoke('update_workspace_item',payload);else{const request=await fetch('/api/v1/workspace/items',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});response=await request.json();if(!request.ok)throw new Error(response?.error||'任务目标没有保存。');}if(!response?.ok)throw new Error(response?.error||'任务目标没有保存。');TASK.initial_instruction=instruction;refresh();status.dataset.state='ok';status.textContent='已保存到当前任务文件夹。';setTimeout(()=>dialog.close(),350);}catch(error){status.dataset.state='error';status.textContent=error?.message||'任务目标没有保存。';}finally{save.disabled=false;}});
  start.addEventListener('click',()=>{if(!clean(TASK.initial_instruction)){edit.click();return;}const composer=document.getElementById('message');if(!composer)return;if(!clean(composer.value)){composer.value=clean(TASK.initial_instruction);composer.dispatchEvent(new Event('input',{bubbles:true}));}composer.scrollIntoView({behavior:'smooth',block:'center'});setTimeout(()=>composer.focus(),250);});
  results.addEventListener('click',()=>{if(!history)return;history.open=true;history.scrollIntoView({behavior:'smooth',block:'start'});});
  refresh();
})();
</script>
"""


def _ensure_task_workflow_guide(html: str, root: _Path) -> str:
    """Connect task intent, capabilities, execution and retained results."""

    if 'data-task-workflow-guide="true"' in html or "const TASK=" not in html:
        return html
    task_match = _re.search(r"const TASK=(\{.*?\});", html)
    if task_match is not None:
        try:
            task_context = _json.loads(task_match.group(1))
            task_id = str(task_context.get("task_id") or task_context.get("id") or "")
            from .workspace_runtime import find_task_context, load_workspace_config

            found = find_task_context(load_workspace_config(root), task_id)
            task = found[3] if found is not None else {}
            toolkit = task.get("toolkit") if isinstance(task, dict) else {}
            if not isinstance(toolkit, dict):
                toolkit = {}
            clean_toolkit = {
                kind: [str(item) for item in toolkit.get(kind, []) if str(item).strip()]
                for kind in ("agents", "skills", "plugins")
            }
            task_context["toolkit_counts"] = {
                kind: len(clean_toolkit[kind]) for kind in ("agents", "skills", "plugins")
            }
            encoded = _json.dumps(task_context, ensure_ascii=False).replace("</", "<\\/")
            html = html[: task_match.start(1)] + encoded + html[task_match.end(1) :]
        except (OSError, TypeError, ValueError):
            pass
    marker = '<details class="task-history-context"'
    marker_index = html.find(marker)
    if marker_index < 0:
        return html
    updated = html[:marker_index] + _TASK_WORKFLOW_GUIDE + html[marker_index:]
    script_marker = '<script data-t-one-task-workflow-guide-script="true">'
    script_start = updated.find(script_marker)
    script_end = updated.find("</script>", script_start)
    workflow_script = ""
    if script_start >= 0 and script_end >= script_start:
        script_end += len("</script>")
        workflow_script = updated[script_start:script_end]
        updated = updated[:script_start] + updated[script_end:]
    if _TASK_WORKFLOW_GUIDE_CSS.strip() not in updated:
        updated = updated.replace(
            "</style>", _TASK_WORKFLOW_GUIDE_CSS + "</style>", 1
        )
    return updated.replace("</body>", workflow_script + "</body>", 1)


def _ensure_null_safe_workspace_bindings(html: str) -> str:
    """Do not bind optional team selectors unless the whole control set exists."""

    return html.replace(
        "if(teamProject){teamProject.onchange=refreshTeamStores;teamStore.onchange=refreshTeamTasks;refreshTeamStores();}",
        "if(teamProject&&teamStore&&teamTask){teamProject.onchange=refreshTeamStores;teamStore.onchange=refreshTeamTasks;refreshTeamStores();}",
    )


def render_desktop_workspace(root, query=None, *args, **kwargs):
    """Render the legacy workspace plus reviewed, registry-backed UI slices."""

    query_map = query if isinstance(query, dict) else {}
    raw_view = query_map.get("view") or [""]
    if isinstance(raw_view, (list, tuple)):
        requested_view = str(raw_view[0] if raw_view else "")
    else:
        requested_view = str(raw_view)
    token = _RENDER_VIEW.set(requested_view)
    try:
        html = _legacy_render_desktop_workspace(root, query, *args, **kwargs)
    finally:
        _RENDER_VIEW.reset(token)
    if _re.search(r'<body\b[^>]*\bdata-view="realtime_dashboard"', html):
        live_store_data = '"live_data_available": true' in html
        html = _re.sub(
            r'<div class="task-intro">.*?</div>',
            "",
            html,
            count=1,
            flags=_re.S,
        )
        html = html.replace("经营数据快照", "实时经营数据")
        html = html.replace("实时大盘", "实时经营数据")
        html = html.replace("实时数据大屏", "实时经营数据")
        html = html.replace(
            "全部项目组的真实经营数据、站点、风险与连接状态",
            "只显示已连接店铺刚刚返回的数据；未连接时不显示历史数据。",
        )
        html = html.replace(
            "全部项目组的运行状态、站点、风险与连接健康",
            "只显示已连接店铺刚刚返回的数据；未连接时不显示历史数据。",
        )
        html = _re.sub(
            r'<span class="status">[^<]*</span>',
            '<span class="status">{}</span>'.format(
                "实时读取" if live_store_data else "未连接实时数据"
            ),
            html,
            count=1,
        )
    html = _add_global_platform_catalog(html, _Path(root))
    html = _ensure_composer_strategy_choices(html)
    html = _ensure_account_access_settings_section(html)
    html = _ensure_data_acquisition_settings_section(html)
    html = _ensure_u15_settlement_file_import(html)
    html = _ensure_u16_message_file_import(html)
    html = _ensure_commerce_profile_editor(html, _Path(root))
    html = _replace_ai_model_settings(html, _Path(root))
    html = _replace_open_tool_settings(html, _Path(root))
    html = _ensure_cli_ai_roundtrip_settings(html, _Path(root))
    html = _ensure_task_ai_roundtrip(html)
    html = _ensure_task_history_context(html)
    html = _ensure_task_workflow_guide(html, _Path(root))
    html = _simplify_task_conversation(html, query_map)
    html = _ensure_agent_skill_marketplace(html, _Path(root))
    html = _rename_capability_market_links(html)
    html = _ensure_capability_market_sidebar_link(html)
    html = _ensure_settings_section_deep_link(html)
    html = _ensure_project_toggle_a11y_sync(html)
    html = _simplify_daily_workspace_copy(html)
    html = _remove_html_element_by_class(html, "finance-coverage-list")
    html = _remove_details_with_summary(html, "全平台与广告财务覆盖")
    html = _remove_details_with_summary(html, "来源、附件和同源记录")
    html = _ensure_daily_ui_readability(html)
    html = _ensure_workspace_creation_controls(html, _Path(root))
    html = _ensure_workspace_folder_access(html)
    html = _ensure_sidebar_rename_dialog(html)
    html = _remove_empty_sidebar_sections(html)
    html = _ensure_null_safe_workspace_bindings(html)
    return _ensure_owner_ui_cleanup(html)


class _WorkspaceFacadeModule(_ModuleType):
    """Keep test and dependency injection assignments visible to legacy code."""

    def __getattr__(self, name: str):
        return getattr(_legacy_runtime, name)

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(dir(_legacy_runtime)))

    def __setattr__(self, name: str, value) -> None:
        super().__setattr__(name, value)
        if name in _LEGACY_EXPORT_NAMES:
            setattr(_legacy_runtime, name, value)


_sys.modules[__name__].__class__ = _WorkspaceFacadeModule
__all__ = _LEGACY_EXPORT_NAMES
