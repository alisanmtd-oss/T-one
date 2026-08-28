from __future__ import annotations
import html
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
from . ai_provider_catalog import provider_catalog_snapshot
from . non_api_ai_bridge import non_api_ai_bridge_snapshot
from . live_operations import live_operations_snapshot
from . import account
from . autonomous_loop import load_autonomous_loop_config
from . b2b_sales_runtime import account_timeline_snapshot
from . b2b_sales_runtime import owner_review_queue
from . b2b_sales_runtime import sales_snapshot
from . company_workspace import company_dashboard_snapshot
from . creative_video import detect_toolchain
from . creative_video import evaluate_template_gate
from . creative_video import load_capabilities
from . creative_video import resolve_generation_route
from . platform_product_requirements import build_channel_product_requirements_snapshot
from . platform_product_requirements import build_platform_product_requirements_snapshot
from . storage import read_records
from . store_metrics import summarize_store_metrics
from . task_execution_runtime import business_event_projection
from . task_execution_runtime import recent_task_runs
from . task_execution_runtime import runtime_queue_snapshot
from . advertising_agent import advertising_control_snapshot
from . advertising_agent import advertising_operator_brief
from . platform_native_ai import platform_native_ai_control_snapshot
from . platform_expert_runtime import platform_expert_control_snapshot
from . external_access_gateway import external_access_control_snapshot
from . browser_plugin_control import browser_plugin_control_snapshot
from . communications_connector_control import communications_connector_snapshot
from . account_access_automation import account_access_snapshot
from . erp_cost_source_control import erp_cost_source_snapshot
from . platform_settlement_finance import finance_settlement_snapshot
from . revenue_monitoring_control import revenue_monitoring_snapshot
from . github_capability_registry import github_tool_admission_snapshot
from . ai_analytics_data_foundation import ai_analytics_data_foundation_snapshot
from . global_commerce_dimensions import global_commerce_dimension_snapshot
from . platform_rule_library import platform_rule_library_snapshot
from . learning_direction_library import learning_direction_library_snapshot
from . new_media_operations import new_media_operations_snapshot
from . platform_digitization import load_platform_digitization_registry
from . platform_digitization import platform_card_metric_keys
from . platform_digitization import platform_supports_metric_by_default
from . workspace_runtime import capability_pack_catalog_snapshot
from . workspace_runtime import load_workspace_config
from . workspace_runtime import task_configuration_snapshot
from . workspace_schema import STORE_PLATFORMS
from . workspace_schema import business_bound_stores
from . workspace_schema import find_store
from . workspace_schema import find_task_context
from . workspace_schema import is_business_bound_store
from . workspace_schema import iter_project_stores
from . workspace_schema import normalize_workspace_config

account_center = account

"""Readable desktop workspace runtime reconstructed from trusted source and verified bytecode slices."""

INSTRUCTION_TASK_NAME_HINTS = ('整理', '检查', '回复', '分析', '跟进', '寻找', '准备', '优化', '处理', '生成', '创建', '研究')
NEW_CONVERSATION_INTENT_PROMPTS = {'activity_plan': '整理当前活动规则、费用、叠加限制、报名门槛和待确认动作；没有证据的字段标为未知。', 'ads_budget': '根据当前项目事实测算广告预算、盈亏平衡点和停止规则；真实投放前进入负责人确认。', 'ads_plan': '基于当前项目证据制定广告计划，区分草稿、已连接数据和待确认动作。', 'ads_research': '研究当前平台的广告机会、费用与风险，先列证据缺口，不自动投放。', 'approval': '整理当前任务中需要负责人确认的真实外部动作、证据、费用和风险。', 'creator_research': '研究与当前项目相关的达人和内容机会，区分公开证据、推断和待确认联系动作。', 'erp_after_sales': '检查当前项目的售后、退款、退货与客户问题数据；没有连接的数据明确标为缺失。', 'erp_finance': '检查当前项目的订单结算、平台扣费、成本、利润和现金流数据；以真实结算证据为准。', 'erp_fulfillment': '检查当前项目的履约、仓库、物流与时效数据；真实发货前进入负责人确认。', 'erp_gap': '检查当前项目 ERP 和平台连接的数据缺口、权限缺口与下一项可验证动作。', 'erp_inventory': '检查当前项目库存、在途、安全库存、补货与采购数据；不编造未连接仓库数据。', 'erp_orders': '检查当前项目订单、待处理状态和履约风险；不把草稿或模拟数据当真实订单。', 'feedback': '汇总当前项目的评价、退货、投诉和改进证据，区分事实、推断与建议。', 'launch': '为当前项目整理上线前检查、依赖、风险、证据和负责人确认项。', 'live_research': '研究当前平台直播机会、规则、费用与素材要求；不自动开播或报名。', 'pod': '分析当前项目的 POD 商品、设计、供应链、平台与版权风险。', 'pod_plan': '为当前项目制定 POD 测试计划，列出商品、素材、成本、平台与停止规则。', 'pod_risk': '检查当前 POD 项目的版权、商标、内容、供应链和平台合规风险。', 'product_data': '分析当前项目的商品、同行、需求、利润、Listing、内容与风险；先引用已有证据，缺少的事实再问我。', 'report_context': '读取当前报告上下文，区分事实、观察、推断和草稿，并给出下一步。', 'risk': '检查当前项目的平台、合规、财务、库存、内容和执行风险，并标注证据状态。', 'seo': '基于当前项目事实制定 SEO 研究与优化计划，区分关键词证据、内容草稿和待验证结果。', 'store_connection': '检查当前店铺、浏览器、API、ERP 和执行身份的真实连接状态与唯一缺口。', 'store_data': '读取当前项目和店铺的真实数据、缺失字段、权限状态与下一项验证动作。', 'tk_content': '基于当前项目证据整理 TikTok Shop 内容方向、脚本、达人、评论和平台风险；不自动发布。', 'tk_script': '根据当前商品和已验证素材生成 TikTok Shop 视频脚本草稿，保留版权与发布确认边界。'}
_PLATFORM_LOGO_MARKS = {'amazon': ('A', '#ff9900', '#111827'), 'tiktok_shop': ('TK', '#111827', '#ffffff'), 'tiktok': ('♪', '#111827', '#ffffff'), 'shein': ('S', '#111827', '#ffffff'), 'shopee': ('S', '#ee4d2d', '#ffffff'), 'lazada': ('L', '#6c2bd9', '#ffffff'), 'walmart': ('W', '#0071ce', '#ffffff'), 'etsy': ('E', '#f1641e', '#ffffff'), 'ebay': ('e', '#2563eb', '#ffffff'), 'aliexpress': ('AE', '#e43225', '#ffffff'), 'rakuten': ('R', '#bf0000', '#ffffff'), 'emag': ('eM', '#0a5fd3', '#ffffff'), 'coupang': ('C', '#e31b23', '#ffffff'), 'wildberries': ('WB', '#7c2d83', '#ffffff'), 'ozon': ('O', '#005bff', '#ffffff'), 'shopify': ('Sh', '#95bf47', '#102a12'), 'woocommerce': ('Woo', '#7f54b3', '#ffffff'), 'douyin_ecommerce': ('抖', '#111827', '#ffffff'), 'douyin': ('抖', '#111827', '#ffffff'), 'kuaishou_shop': ('快', '#ff6a00', '#ffffff'), 'kuaishou': ('快', '#ff6a00', '#ffffff'), 'xiaohongshu': ('红', '#ff2442', '#ffffff'), 'wechat_channels': ('微', '#07c160', '#ffffff'), 'taobao_tmall': ('淘', '#ff5000', '#ffffff'), 'jd': ('京', '#e1251b', '#ffffff'), 'pinduoduo': ('拼', '#e02e24', '#ffffff'), '1688': ('1688', '#ff7300', '#ffffff')}
_CHINA_PLATFORM_CATALOG = (('douyin_ecommerce', 'social_commerce'), ('kuaishou_shop', 'social_commerce'), ('wechat_channels', 'social_commerce'), ('xiaohongshu', 'social_content'), ('douyin', 'social_content'), ('kuaishou', 'social_content'), ('taobao_tmall', 'marketplace'), ('jd', 'marketplace'), ('pinduoduo', 'marketplace'), ('1688', 'sourcing'))

def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}

def _flat_tasks(config: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    result = []
    projects = config.get('projects') if isinstance(config.get('projects'), list) else []
    for project in projects:
        if not isinstance(project, dict):
            continue
        else:
            for key in ['tasks', 'workstreams']:
                tasks = project.get(key) if isinstance(project.get(key), list) else []
                for task in tasks:
                    if isinstance(task, dict):
                        result.append((project, task))
    standalone_project = {'id': '', 'name': '独立任务'}
    for task in config.get('standalone_tasks', []):
        if isinstance(task, dict):
            result.append((standalone_project, task))
    return result

def _scope_tokens(value: Any) -> set[str]:
    if isinstance(value, list):
        raw = [str(item or "").strip() for item in value]
    else:
        raw = [item.strip() for item in re.split(r"[,;，；\n]+", str(value or ""))]
    values = {item for item in raw if item}
    return {"all"} if not values or "all" in {item.casefold() for item in values} else values

def _scope_is_subset(requested: Any, allowed: Any) -> bool:
    requested_values = _scope_tokens(requested)
    allowed_values = _scope_tokens(allowed)
    if "all" in allowed_values:
        return True
    if "all" in requested_values:
        return False
    return requested_values.issubset(allowed_values)

def _task_public_name(task: dict[str, Any], show_internal_diagnostics: bool) -> str:
    """Hide short operator instructions from the daily UI unless debug=1 is enabled."""
    raw_name = str(task.get('name') or '任务').strip() or '任务'
    if show_internal_diagnostics:
        return raw_name
    platform = str(task.get('platform') or '').strip().lower()
    role = str(task.get('conversation_role') or '').strip().lower()
    has_bound_store = bool(
        task.get('store_bound')
        or str(task.get('store_binding_id') or '').strip()
        or str(task.get('store_id') or '').strip()
    )
    is_unbound_work_instruction = (
        not has_bound_store
        and platform in {'b2b', 'b2b_export', 'external_trade', 'lead_generation'}
        and role in {'', 'secondary', 'independent', 'primary'}
        and any(marker in raw_name for marker in INSTRUCTION_TASK_NAME_HINTS)
    )
    return '任务助手' if is_unbound_work_instruction else raw_name

def _task_public_search(task: dict[str, Any], display_name: str, show_internal_diagnostics: bool) -> str:
    raw_name = str(task.get('name') or '').strip()
    if show_internal_diagnostics or display_name == raw_name:
        return str(task.get('search') or '')
    safe_parts = [
        display_name,
        str(task.get('subtitle') or ''),
        str(task.get('platform') or ''),
        str(task.get('country') or ''),
    ]
    return ' '.join(part.strip() for part in safe_parts if part.strip())

def _platform_label(value: Any) -> str:
    labels = {
        'amazon': 'Amazon',
        'tiktok_shop': 'TikTok Shop',
        'shein': 'SHEIN',
        'shopee': 'Shopee',
        'lazada': 'Lazada',
        'walmart': 'Walmart',
        'etsy': 'Etsy',
        'ebay': 'eBay',
        'aliexpress': 'AliExpress',
        'rakuten': 'Rakuten',
        'emag': 'eMAG',
        'coupang': 'Coupang',
        'wildberries': 'Wildberries',
        'ozon': 'Ozon',
        'shopify': 'Shopify',
        'woocommerce': 'WooCommerce',
    }
    raw = str(value or '').strip().lower()
    return labels.get(raw, raw.replace('_', ' ').title() or '渠道')

def _agent_intro(platform: str, task_name: str) -> tuple[str, list[str]]:
    """Return plain-language onboarding for the selected business agent."""
    learning_starter = '学习资料：请阅读下面这份我有权使用的资料，并先作为待核验候选：'
    if platform == 'b2b' and '设备' in str(task_name or ''):
        return (
            '告诉我想开发哪类设备客户、要复核哪条机会或报价前缺什么；我会复用同一客户事实池，不把弱信号当采购意向。',
            ['找出最值得复核的设备客户', '检查设备报价前还缺哪些信息', '整理候选客户并生成复核执行包', learning_starter],
        )
    presets = {
        'amazon': (
            '把店铺问题直接告诉我。我会先核对当前店铺和商品事实，再给出能执行的下一步。',
            ['检查最近为什么没有出单', '优化这个商品的 Listing', '整理今天最该处理的店铺问题'],
        ),
        'b2b': (
            '告诉我想找什么客户、要跟进谁或需要准备什么材料，我会沿用同一客户时间线。',
            ['找出今天最值得跟进的客户', '为这个客户准备一封跟进草稿', '整理客户并生成本轮执行包', learning_starter],
        ),
        'creative_video': (
            '上传参考视频、图片或商品资料，我会在一次对话里完成拆解、原创分镜、提示词和剪辑建议。',
            ['拆解我上传的参考视频', '为这个商品做一版 15 秒分镜', '把分镜整理成剪辑清单', learning_starter],
        ),
        'ad_agent': (
            '问我广告表现或把商品资料发来。我会先说明证据和影响，再给出可批准的建议；不会擅自改预算或启停广告。',
            ['今天哪些广告可能在浪费钱', '根据商品资料准备广告草稿', '给我一份只读的广告优化建议', learning_starter],
        ),
        'store_onboarding': (
            '告诉我要接入的平台和店铺，我会逐步说明只需要你提供的授权信息。',
            ['开始接入一个店铺', '检查还缺哪些授权', '解释当前连接状态', learning_starter],
        ),
    }
    return presets.get(
        platform,
        (
            f"我是{task_name or '当前智能体'}。直接告诉我结果目标，相关能力和工具由 T-one 自动选择。",
            ['告诉我现在最该做什么', '整理当前进度和待办', '检查完成这件事还缺什么', learning_starter],
        ),
    )

def _workspace_for_session(config: dict[str, Any], session_info: dict[str, Any] | None) -> dict[str, Any]:
    if not session_info or session_info.get('is_owner'):
        return config
    project_scope = _scope_tokens(session_info.get('project_scope'))
    task_scope = _scope_tokens(session_info.get('task_scope'))
    platform_scope = _scope_tokens(session_info.get('platform_scope'))
    country_scope = _scope_tokens(session_info.get('country_scope'))
    store_scope = _scope_tokens(session_info.get('store_scope'))
    projects = []
    for project in config.get('projects', []):
        if not isinstance(project, dict):
            continue
        project_id = str(project.get('id') or '')
        if 'all' not in project_scope and project_id not in project_scope:
            continue
        scoped = dict(project)
        channels = []
        for channel in project.get('channels', []):
            if not isinstance(channel, dict):
                continue
            platform = str(channel.get('platform') or '')
            country = str(channel.get('country_site') or '')
            if 'all' not in platform_scope and platform not in platform_scope:
                continue
            if 'all' not in country_scope and country not in country_scope:
                continue
            stores = []
            for store in channel.get('stores', []):
                if not isinstance(store, dict):
                    continue
                store_candidates = {
                    str(store.get('id') or ''),
                    str(store.get('external_id') or ''),
                    str(store.get('name') or ''),
                }
                if 'all' not in store_scope and not store_scope.intersection(store_candidates):
                    continue
                tasks = []
                for task in store.get('tasks', []):
                    if not isinstance(task, dict):
                        continue
                    task_candidates = {
                        str(task.get('id') or ''),
                        str(task.get('name') or ''),
                    }
                    if 'all' in task_scope or task_scope.intersection(task_candidates):
                        tasks.append(dict(task))
                if tasks or 'all' in task_scope:
                    scoped_store = dict(store)
                    scoped_store['tasks'] = tasks
                    stores.append(scoped_store)
            if stores or (
                not channel.get('stores')
                and 'all' in store_scope
                and 'all' in task_scope
            ):
                scoped_channel = dict(channel)
                scoped_channel['stores'] = stores
                channels.append(scoped_channel)
        workstreams = []
        for task in project.get('workstreams', []):
            if not isinstance(task, dict):
                continue
            task_candidates = {
                str(task.get('id') or ''),
                str(task.get('name') or ''),
            }
            platform = str(task.get('platform') or '')
            country = str(task.get('country') or '')
            if 'all' not in task_scope and not task_scope.intersection(task_candidates):
                continue
            if 'all' not in platform_scope and platform not in platform_scope:
                continue
            if 'all' not in country_scope and country not in country_scope:
                continue
            workstreams.append(dict(task))
        if channels or workstreams:
            scoped['channels'] = channels
            scoped['workstreams'] = workstreams
            projects.append(scoped)
    scoped_config = dict(config)
    scoped_config['projects'] = projects
    return normalize_workspace_config(scoped_config)

def _selected_task(
    config: dict[str, Any], query: dict[str, list[str]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve a system view, project, store conversation, or concrete task."""

    requested_view = str((query.get("view") or [""])[0]).strip().lower()
    special_views = {
        "dashboard": (
            "实时数据大屏",
            "全部项目组的运行状态、站点、风险与连接健康",
            "realtime_dashboard",
        ),
        "module_dashboard": (
            "全模块大屏",
            "全平台、社媒、外贸、库存、财务和任务数据总览",
            "module_dashboard",
        ),
        "new": (
            "新建对话",
            "选择项目和工作对象，然后直接描述要完成的事",
            "new_conversation",
        ),
        "scheduled": ("已安排", "定时任务、最近运行和排队状态", "scheduled"),
        "live_operations": (
            "直播运营",
            "直播排期、预检、中控草稿和复盘回执",
            "live_operations",
        ),
        "extensions": ("扩展", "插件、Skills、智能体和模型", "extensions"),
        "settings": (
            "设置中心",
            "AI 模型、电商平台、社交媒体、通讯工具、ERP、浏览器环境、Skills 和权限",
            "settings_center",
        ),
        "advertising": ("广告控制台", "跨渠道预检、门禁与证据回写", "advertising"),
        "native_ai": (
            "平台原生 AI",
            "逐平台核对能力、输入输出、门禁与效果证据",
            "native_ai",
        ),
        "experts": ("平台专家", "专家路由、模型槽、工具边界、错误与复盘", "experts"),
        "external_api": (
            "外部接入",
            "本地客户端、最小权限、草稿门禁与审计",
            "external_api",
        ),
        "browser_chain": (
            "浏览器与插件",
            "非 Amazon 浏览器、店铺绑定、插件链与执行门禁",
            "browser_chain",
        ),
        "communications": (
            "通信与社媒",
            "官方连接器契约、身份范围、隐私与发送门禁",
            "communications",
        ),
        "account_access": (
            "账号登录自动化",
            "店铺账号、邮箱验证码、浏览器身份和人工接管门禁",
            "account_access",
        ),
        "erp_cost": (
            "ERP 与真实成本",
            "非 Amazon 店铺、ERP、成本证据与利润门禁",
            "erp_cost",
        ),
    }

    def system_view(view_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        name, subtitle, platform = special_views[view_id]
        return {"id": "system", "name": "系统"}, {
            "id": f"system-{view_id}",
            "name": name,
            "subtitle": subtitle,
            "status": "实时读取",
            "platform": platform,
            "audience": "owner",
            "toolkit": {"plugins": [], "skills": [], "agents": []},
        }

    if requested_view in special_views:
        return system_view(requested_view)

    requested_task = str((query.get("task") or [""])[0]).strip()
    requested_store = str((query.get("store") or [""])[0]).strip()
    requested_project = str((query.get("project") or [""])[0]).strip()
    projects = [item for item in config.get("projects", []) if isinstance(item, dict)]

    flat_tasks: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen_task_ids: set[str] = set()
    for project in projects:
        for key in ("tasks", "workstreams"):
            for task in project.get(key) or []:
                task_id = str(task.get("id") or "") if isinstance(task, dict) else ""
                if task_id and task_id not in seen_task_ids:
                    seen_task_ids.add(task_id)
                    flat_tasks.append((project, task))
        for channel in project.get("channels") or []:
            if not isinstance(channel, dict):
                continue
            for store in channel.get("stores") or []:
                if not isinstance(store, dict):
                    continue
                for task in store.get("tasks") or []:
                    task_id = str(task.get("id") or "") if isinstance(task, dict) else ""
                    if task_id and task_id not in seen_task_ids:
                        seen_task_ids.add(task_id)
                        flat_tasks.append((project, task))
    for task in config.get("standalone_tasks") or []:
        task_id = str(task.get("id") or "") if isinstance(task, dict) else ""
        if task_id and task_id not in seen_task_ids:
            flat_tasks.append(({"id": "standalone", "name": "独立任务"}, task))

    if requested_task:
        for project, task in flat_tasks:
            if str(task.get("id") or "") != requested_task:
                continue
            if str(task.get("conversation_role") or "").lower() == "secondary":
                primary_id = str(task.get("primary_conversation_id") or "")
                if primary_id:
                    for primary_project, primary_task in flat_tasks:
                        if (
                            str(primary_project.get("id") or "")
                            == str(project.get("id") or "")
                            and str(primary_task.get("id") or "") == primary_id
                        ):
                            return primary_project, primary_task
            return project, task

    if requested_store:
        store_context = find_store(config, requested_store)
        if store_context and is_business_bound_store(store_context[2]):
            project, channel, store = store_context
            store_tasks = [
                item for item in store.get("tasks") or [] if isinstance(item, dict)
            ]
            if store_tasks:
                primary = next(
                    (
                        item
                        for item in store_tasks
                        if str(item.get("conversation_role") or "") == "primary"
                    ),
                    store_tasks[0],
                )
                return project, primary
            return project, {
                "id": f"store-dashboard:{requested_store}",
                "name": str(store.get("name") or "店铺"),
                "subtitle": "店铺身份已建立，创建运营任务后开始执行。",
                "status": str(store.get("status") or "待配置"),
                "platform": "store_dashboard",
                "project_id": str(project.get("id") or ""),
                "channel_id": str(channel.get("id") or ""),
                "store_binding_id": str(store.get("id") or ""),
                "store_id": str(store.get("external_id") or ""),
                "audience": "seller",
                "toolkit": {"plugins": [], "skills": [], "agents": []},
            }

    if requested_project:
        for project in projects:
            if str(project.get("id") or "") == requested_project:
                return project, {
                    "id": f"project-dashboard:{requested_project}",
                    "name": f"{project.get('name') or '项目'}实时数据",
                    "subtitle": "项目指标、任务状态、风险和最近证据",
                    "status": "实时读取",
                    "platform": "realtime_project",
                    "project_id": requested_project,
                    "audience": "owner",
                    "toolkit": {"plugins": [], "skills": [], "agents": []},
                }

    return system_view("dashboard")

def _amazon_timeline(root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    state = _load_json(root / 'outputs' / 'amazon_10001_operating_state_latest.json')
    listing = state.get('listing') if isinstance(state.get('listing'), dict) else {}
    offers = state.get('offers') if isinstance(state.get('offers'), dict) else {}
    orders = state.get('orders') if isinstance(state.get('orders'), dict) else {}
    advertising = state.get('advertising') if isinstance(state.get('advertising'), dict) else {}
    fulfillment = state.get('fulfillment') if isinstance(state.get('fulfillment'), dict) else {}
    single = offers.get('single') if isinstance(offers.get('single'), dict) else {}
    four_pack = offers.get('four_pack') if isinstance(offers.get('four_pack'), dict) else {}
    variation_count = int(listing.get('single_child_count') or 0)
    color_count = int(listing.get('single_color_count') or 0)
    size_count = int(listing.get('single_size_count') or 0)
    single_media_count = int(listing.get('single_visible_media_count') or 0)
    four_pack_media_count = int(listing.get('four_pack_visible_media_count') or 0)
    four_pack_size_count = int(listing.get('four_pack_size_count') or 0)
    timeline = [
        {
            'state': 'done' if listing.get('single_variation_complete') else 'working',
            'title': '单件 Listing 变体',
            'detail': f'同一父体已组织 {variation_count} 个子体，{color_count} 色 × {size_count} 码。',
            'meta': str(listing.get('single_parent_asin') or '等待 ASIN'),
        },
        {
            'state': 'working' if 'pending' in str(listing.get('single_parent_image_submission_status') or '') else 'done',
            'title': '图片与文案优化',
            'detail': f'单件与4件套图片/文案已提交，按买家页处理结果验证，不重复提交。当前买家页可见媒体位：单件 {single_media_count}，4件套 {four_pack_media_count}。',
            'meta': f"4件套父 ASIN {listing.get('four_pack_parent_asin') or '待核验'} · {four_pack_size_count} 个尺码 · Amazon 处理中",
        },
        {
            'state': 'done' if single.get('buyable_via_buying_options') and four_pack.get('buyable_via_buying_options') else 'working',
            'title': '可售与购买选项',
            'detail': '两个家族可通过 Buying Options 购买，主 Add to Cart / Buy Now 仍未获得。',
            'meta': 'Featured Offer 待改善',
        },
        {
            'state': 'done' if fulfillment.get('competitive_delivery_promise_verified') else 'blocked',
            'title': 'FBM 配送时效',
            'detail': '美国仓资料已收到，但尚未确认该地址为 Amazon 获批准的 ship-from，也未补齐履约说明；当前仍未配置美国发货地，配送承诺过长。',
            'meta': '需确认地址资质与履约说明；不得重复索要地址',
        },
        {
            'state': 'working' if advertising.get('launch_allowed') else 'blocked',
            'title': '广告与优惠',
            'detail': '广告和优惠草稿可继续准备，发货时效与 Featured Offer 解锁前不启动花费。',
            'meta': '门禁关闭',
        },
        {
            'state': 'idle',
            'title': '订单监控',
            'detail': f"当前订单 {int(orders.get('total') or 0)}，待发货 {int(orders.get('unshipped') or 0)}。",
            'meta': '持续监控',
        },
    ]
    outputs = [
        {'label': '打开 Amazon US 店铺后台', 'action': 'home'},
        {'label': '管理库存', 'action': 'inventory'},
        {'label': '管理订单', 'action': 'orders'},
        {'label': '广告活动', 'action': 'ads'},
        {'label': '优惠券', 'action': 'coupons'},
    ]
    return timeline, outputs

def _task_page_context_snapshot(task: dict[str, Any], timeline: list[dict[str, str]], store_requirements: dict[str, Any]) -> dict[str, Any]:
    """Return the bounded, seller-visible facts shown on the current task page."""
    def clean(value: Any, limit: int = 220) -> str:
        return re.sub(r'\s+', ' ', str(value or '')).strip()[:limit]

    headings = []
    task_name = clean(task.get('name'), 140)
    initial_instruction = clean(task.get('initial_instruction'), 260)
    if task_name:
        headings.append(f'当前任务：{task_name}')
    if initial_instruction and initial_instruction != task_name:
        headings.append(f'任务原始要求：{initial_instruction}')

    metrics = []
    catalog = store_requirements.get('catalog') if isinstance(store_requirements.get('catalog'), dict) else {}
    if catalog.get('status') in {'ready', 'partial'}:
        product_count = int(catalog.get('product_count') or 0)
        variant_count = int(catalog.get('variant_count') or 0)
        missing_labels = {
            'product_identity_and_variants': '商品规格',
            'cost': '成本',
            'price_or_pricing_rule': '售价',
            'product_images': '图片',
            'inventory_or_supply_rule': '库存',
        }
        missing = [
            missing_labels.get(str(item), str(item))
            for item in catalog.get('missing_required_facts', [])
            if str(item).strip()
        ]
        summary = f'商品资料：{product_count} 个商品 · {variant_count} 个变体'
        if missing:
            summary += ' · 缺' + '、'.join(missing)
        metrics.append(summary)
    connector = store_requirements.get('connector') if isinstance(store_requirements.get('connector'), dict) else {}
    if connector:
        metrics.append('店铺连接状态：' + clean(connector.get('status') or '待核验', 80))
    next_action = clean(store_requirements.get('next_action'), 220)
    if next_action:
        metrics.append(f'当前资料下一步：{next_action}')

    cards = []
    for item in timeline[:8]:
        if not isinstance(item, dict):
            continue
        title = clean(item.get('title'), 80)
        detail = clean(item.get('detail'), 240)
        meta = clean(item.get('meta'), 100)
        if not any((title, detail, meta)):
            continue
        card = f'任务事件：{title}'
        if detail:
            card += f'｜{detail}'
        if meta:
            card += f'｜状态/证据：{meta}'
        cards.append(card)
    return {
        'title': task_name or '当前任务',
        'visible_headings': headings,
        'metrics': metrics[:6],
        'cards': cards[:8],
    }

def desktop_task_page_context_snapshot(root: Path, task_id: str) -> dict[str, Any]:
    """Rebuild trusted, seller-visible facts for a local desktop task."""
    found = find_task_context(load_workspace_config(root), task_id)
    if found is None:
        return {}
    project, channel, store, task = found
    effective_task = dict(task)
    if isinstance(channel, dict):
        effective_task.setdefault('platform', channel.get('platform') or '')
        effective_task.setdefault('country', channel.get('country_site') or '')
    store_requirements = {}
    store_binding_id = str(effective_task.get('store_binding_id') or '')
    if isinstance(store, dict) and store_binding_id:
        try:
            store_requirements = build_platform_product_requirements_snapshot(
                root,
                str(project.get('id') or ''),
                store_binding_id,
            )
        except (OSError, TypeError, ValueError):
            store_requirements = {}
    platform = str(effective_task.get('platform') or '').strip().lower()
    if platform == 'amazon':
        timeline, _outputs = _amazon_timeline(root)
    elif platform == 'b2b':
        timeline, _outputs = _b2b_timeline(root, effective_task)
    elif platform == 'creative_video':
        timeline, _outputs = _creative_timeline(root, effective_task)
    elif platform == 'ad_agent':
        timeline, _outputs = _advertising_timeline(root, effective_task)
    elif platform == 'store_onboarding':
        timeline, _outputs = _store_onboarding_timeline()
    else:
        timeline, _outputs = _generic_timeline(effective_task)
    return _task_page_context_snapshot(effective_task, timeline, store_requirements)

def _b2b_timeline(root: "Path", task: "dict[str, Any]") -> "tuple[list[dict[str, str]], list[dict[str, str]]]":
    snapshot = sales_snapshot(root, product_id=str(task.get("product_id") or ""), task_context=task); stages = {}; approved = int(snapshot.get("approved_to_send_count") or 0); sent = int(snapshot.get("externally_sent_count") or 0)

    replies = int(snapshot.get("reply_count") or 0)

    quotes = int(snapshot.get("quote_ready_count") or 0)
    if snapshot.get("sales_scope") == "equipment_cross_sell":
        candidates = int(snapshot.get("equipment_review_signal_count") or 0)
        timeline = [{"state": "blocked", "title": "共享客户事实池", "detail": f"复用现有 {int(snapshot.get("authoritative_company_count") or 0)} 家客户的同一账户时间线，不为设备机会重复建客户。", "meta": Path(str(snapshot.get("master_path") or "未找到权威文件")).name},
            {"state": "idle", "title": "设备机会资格复核", "detail": f"发现 {candidates} 家带 DTG/DTF、产能、外包、交期或扩产文字信号的待复核客户；信号不等于采购意向。", "meta": f"已批准但未必已发送 {approved} · 外发证据 {sent}"},
            {"state": "idle", "title": "需求发现与技术资料", "detail": f"当前可核客户回复 {replies}。需确认应用、材料、印花尺寸、班次产能、现有工艺、场地条件、目的国和验收标准。", "meta": "只认客户原话与技术证据"},
            {"state": "blocked", "title": "方案、样机与报价门禁", "detail": f"当前证据完整的设备报价 {quotes}。型号、价格、交期、认证、安装、培训、质保、备件、运费、税费和 ROI 缺证据时一律未知。", "meta": "技术与价格双重确认"},
            {"state": "idle", "title": "合同、交付、验收与回款", "detail": "订单、付款、生产、发运、安装验收、售后和复购必须分别留证，任何一个草稿都不能升级为真实成交。", "meta": "等待真实成交推进"}]
        outputs = [{"label": "生成设备机会复核执行包", "b2b_action": "execution_pack"},
            {"label": "打开共享权威客户池", "b2b_action": "open_master"},
            {"label": "打开最近外贸产物", "b2b_action": "open_output"}]
        return (timeline, outputs)
    timeline = [{"state": "blocked", "title": "权威去重客户池", "detail": f"已接入 {int(snapshot.get("authoritative_company_count") or 0)} 家公司，其中 {int(snapshot.get("contactable_count") or 0)} 家有公开联系路径。", "meta": Path(str(snapshot.get("master_path") or "未找到权威文件")).name},
        {"state": "idle", "title": "负责人复核与首次触达", "detail": f"已批准准备发送 {approved} 家；待负责人审核 {int(stages.get("lead_added_pending_owner_review", 0)) + int(stages.get("pending_owner_review", 0))} 家。系统只准备草稿，不批量外发。", "meta": f"已有外发证据 {sent}"},
        {"state": "idle", "title": "回复、需求与客户时间线", "detail": f"当前可核回复 {replies}。T恤、POD代工和设备机会写入同一客户记录，不重复建档。", "meta": "客户时间线"},
        {"state": "idle", "title": "报价、样品与成交准备", "detail": f"当前报价资料完整 {quotes}。未确认数量、颜色尺码、目的地、成本、运费、付款条件和有效期前，不生成对外价格承诺。", "meta": "报价门禁"},
        {"state": "idle", "title": "合同、收款、生产与交货", "detail": "成交后沿用同一 pipeline 记录合同、收款、备货、生产、物流、签收和复购；外部动作继续逐项确认。", "meta": "等待真实成交推进"}]
    outputs = [{"label": "生成本轮 B2B 销售执行包", "b2b_action": "execution_pack"},
        {"label": "打开权威客户池", "b2b_action": "open_master"},
        {"label": "打开最近 B2B 产物", "b2b_action": "open_output"}]
    return (timeline, outputs)

def _b2b_account_workspace_html(root: "Path") -> "str":
    accounts = account_timeline_snapshot(root); review_queue = owner_review_queue(root); stage_labels = {"approved_to_send": "历史已批准 · 未执行", "pending_owner_review": "待负责人复核", "lead_added_pending_owner_review": "线索已入池 · 待复核", "tool_added_for_research_queue": "仅研究 · 禁止外联"}; truth_labels = {"verified_current": "当前记录", "draft": "内部草稿", "approved_not_executed": "已批准未执行", "externally_confirmed": "外部证据已确认"}; event_labels = {"pipeline": "客户池状态", "draft": "草稿", "approval": "审批", "suppression": "禁止外联", "outreach": "真实外发", "reply": "真实回复", "quotation": "报价准备"}; queue_rows = []
    for item in review_queue:
        blockers = []
        queue_rows.append(f"<article class=\"b2b-review-card\"><header><span><b>{int(item.get("priority_rank") or 0)}. {html.escape(str(item.get("company") or ""))}</b><small>{html.escape(str(item.get("pipeline_id") or ""))} · {html.escape(str(item.get("market") or ""))}</small></span><em>待重新确认</em></header><p><strong>渠道</strong>{html.escape(str(item.get("channel") or ""))} · {html.escape(str(item.get("contact_path") or ""))}</p><p><strong>主题</strong>{html.escape(str(item.get("subject") or ""))}</p><ul>" + "".join((f"<li>{html.escape(str(blocker))}</li>" for blocker in blockers)) + f"</ul><footer>{html.escape(str(item.get("next_action") or ""))}</footer></article>")
    account_rows = []
    for account in sorted(accounts, key=(lambda item: str(item.get("company") or "").casefold())):
        events = []
        event_rows = []
        for event in events:
            if not isinstance(event, dict):
                continue
            evidence = str(event.get("evidence") or "")
            evidence_name = "无单独证据文件"
            truth = str(event.get("truth_label") or "")
            if not event.get("occurred_at"):
                event.get("occurred_at")
            source_time = str(event.get("source_updated_at") or "时间未知")
            event_rows.append(f"<div class=\"b2b-account-event\"><span><b>{html.escape(event_labels.get(str(event.get("type") or ""), str(event.get("type") or "事件")))}</b><small>{html.escape(source_time)}</small></span><div><strong>{html.escape(str(event.get("status") or ""))}</strong><p>{html.escape(str(event.get("detail") or ""))}</p><small>{html.escape(truth_labels.get(truth, truth))} · {html.escape(evidence_name)}</small></div></div>")
        search_text = " ".join((str(account.get(key) or "") for key in ("company", "pipeline_id", "market", "current_stage", "send_channel"))).casefold()
        stage = str(account.get("current_stage") or "")
        account_rows.append(f"<details class=\"b2b-account-row\" data-b2b-account=\"{html.escape(search_text, quote=True)}\"><summary><span><b>{html.escape(str(account.get("company") or ""))}</b><small>{html.escape(str(account.get("pipeline_id") or ""))} · {html.escape(str(account.get("market") or ""))} · {int(account.get("event_count") or 0)} 条事件</small></span><em>{html.escape(stage_labels.get(stage, stage or "未知"))}</em></summary><div class=\"b2b-account-contact\"><strong>公开联系路径（不代表同意联系）</strong><span>{html.escape(str(account.get("contact_path") or "未记录"))}</span></div><div class=\"b2b-account-events\">{"".join(event_rows)}</div></details>")
    event_count = sum((int(account.get("event_count") or 0) for account in accounts))
    return f"<section class=\"b2b-account-workspace\" aria-label=\"B2B 客户事件与负责人确认队列\"><div class=\"section-title\"><h3>负责人逐条确认队列</h3><span>{len(review_queue)} 条 · 外部发送 0</span></div><p class=\"b2b-workspace-note\">这些是历史“已批准但未执行”记录。当前批准信息不完整且已过期，必须逐条重新确认；本页不会发送邮件、私信、WhatsApp 或表单。</p><div class=\"b2b-review-grid\">{"".join(queue_rows)}</div><div class=\"section-title b2b-accounts-title\"><h3>全部客户事件时间线</h3><span>{len(accounts)} 家 · {event_count} 条证据事件</span></div><label class=\"b2b-account-search\"><span>查找客户</span><input id=\"b2bAccountSearch\" type=\"search\" placeholder=\"公司、Pipeline、市场或阶段\"></label><div class=\"b2b-account-list\" id=\"b2bAccountList\">{"".join(account_rows)}</div></section>"

def _generic_timeline(task: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    timeline = [
        {"state": "blocked", "title": "绑定真实店铺", "detail": "按平台、国家站点、店铺模式和归属建立独立执行身份。", "meta": "待接入"},
        {"state": "idle", "title": "开始运营", "detail": "店铺接入后生成选品、Listing、活动、广告、订单和复盘任务。", "meta": "未开始"},
    ]
    return timeline, []

def _advertising_timeline(root: "Path", task: "dict[str, Any]") -> "tuple[list[dict[str, str]], list[dict[str, str]]]":
    brief = advertising_operator_brief(root, project_id=str(task.get("project_id") or "")); state_map = {"ready": "done", "ready_for_check": "active", "ready_for_readonly_analysis": "active", "needs_input": "active", "needs_authorized_read": "blocked", "blocked_by_account_read": "idle", "waiting_for_real_data": "idle", "always_required_for_change": "idle", "not_executed": "idle"}; status_labels = {"ready": "已准备", "ready_for_check": "可检查", "ready_for_readonly_analysis": "可做只读分析", "needs_input": "待补充目标", "needs_authorized_read": "待授权只读数据", "blocked_by_account_read": "等待账号数据", "waiting_for_real_data": "等待真实数据", "always_required_for_change": "变更前需负责人确认", "not_executed": "尚未执行"}

    timeline = [{"state": state_map.get(str(stage.get("status") or ""), "idle"), "title": str(stage.get("label") or "广告步骤"), "detail": str(stage.get("message") or ""), "meta": status_labels.get(str(stage.get("status") or ""), "状态待核验")} for stage in brief.get("stages", []) if isinstance(stage, dict)]; stage = None
    return (timeline,
        [])

    stage = None

def _store_onboarding_timeline():
    timeline = [{'state': 'active', 'title': '先告诉我是哪一家店', 'detail': '直接在下面说平台、国家站点和你平时怎么称呼这家店；已有后台页面或截图也可以发给 AI 识别。', 'meta': '对话采集'}, {'state': 'idle', 'title': 'AI 补齐执行身份', 'detail': '店铺类型、归属、平台店铺 ID、API 或浏览器环境只在无法确认时追问，不要求你先填长表。', 'meta': '逐项确认'}, {'state': 'idle', 'title': '建立独立店铺工作区', 'detail': '确认后再创建真实店铺身份，并把后续运营对话、授权、数据和审计记录隔离到这家店。', 'meta': '待确认后执行'}]
    return (timeline, [])

def _creative_timeline(root: Path, task: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    tools = {item["id"]: item for item in detect_toolchain(root)}
    capabilities = load_capabilities(root)
    templates = capabilities.get("templates") if isinstance(capabilities.get("templates"), list) else []
    template_gates = [
        evaluate_template_gate(root, str(item.get("id") or ""), task)
        for item in templates
        if isinstance(item, dict)
    ]
    available_template_count = sum(1 for item in template_gates if item.get("allowed"))
    blocked_template_count = len(template_gates) - available_template_count
    capcut = tools.get("capcut", {})
    ffmpeg = tools.get("ffmpeg", {})
    task_id = str(task.get("id") or "")
    if task_id == "ai-video-prompt-storyboard":
        focus_title = "提示词与分镜结构"
        focus_detail = (
            f"当前商品可用 {available_template_count} 套模板，{blocked_template_count} 套因商品类型或证据不足被门禁；"
            "生成时强制保持商品颜色、材质、件数和版型事实。"
        )
    elif task_id == "template-edit-music":
        focus_title = "模板与音乐许可"
        focus_detail = "剪辑模板记录时长、画幅、镜头结构；音乐必须记录来源、许可、地域、署名和到期日。"
    else:
        focus_title = "同行视频拆解模型"
        focus_detail = "统一拆解前3秒钩子、切点、镜头、运镜、字幕、声音、证明、CTA和评论购买信号。"
    timeline = [
        {
            "state": "done" if capcut.get("available") else "blocked",
            "title": "CapCut 剪辑软件连接",
            "detail": "已识别本机 CapCut，可从当前任务直接启动。" if capcut.get("available") else "本机未识别到 CapCut。",
            "meta": str(capcut.get("path") or "未安装"),
        },
        {
            "state": "done" if ffmpeg.get("available") else "blocked",
            "title": "本地视频技术分析",
            "detail": "使用本机已有 FFmpeg 读取时长、画幅、帧率、音轨、明显切点并生成关键帧联系表。" if ffmpeg.get("available") else "缺少隔离的视频分析运行时。",
            "meta": "只处理用户选择的本地文件",
        },
        {"state": "working", "title": focus_title, "detail": focus_detail, "meta": "结构可复用，素材不可照搬"},
        {
            "state": "done",
            "title": "版权与发布边界",
            "detail": "不抓取同行原音，不复制商标、人物、台词或受保护画面；公开发布和投流进入确认队列。",
            "meta": "商用音乐许可必填",
        },
    ]
    outputs = [
        {"label": "选择本地同行视频并分析", "creative_action": "analyze_video"},
        {"label": "生成 AI 视频提示词包", "creative_action": "prompt_pack"},
        {"label": "打开 CapCut", "creative_action": "open_editor"},
        {"label": "打开最近分析产物", "creative_action": "open_output"},
    ]
    return timeline, outputs

def _state_label(state: str) -> str:
    return {"done": "完成", "working": "进行中", "blocked": "卡点", "idle": "待办"}.get(state, "待办")

def _metric_grid(metrics: list[dict[str, Any]], *, project_id: str = "") -> str:
    return "".join(
        '<div class="metric-cell"'
        f' data-project-metric="{html.escape(project_id, quote=True)}"'
        f' data-metric-label="{html.escape(str(item.get("label") or ""), quote=True)}">'
        f'<span>{html.escape(str(item.get("label") or "指标"))}</span>'
        f'<strong>{html.escape(str(item.get("value") if item.get("value") is not None else 0))}'
        f'<small>{html.escape(str(item.get("unit") or ""))}</small></strong>'
        f'<em>{html.escape(str(item.get("truth") or "权威数据源"))}</em></div>'
        for item in metrics
        if isinstance(item, dict)
    )

def _query_value(
    query: dict[str, list[str]] | None, key: str, default: str = ""
) -> str:
    values = query.get(key) if isinstance(query, dict) else None
    if isinstance(values, list) and values:
        return str(values[0] or "").strip()
    return default

def supported_new_conversation_intent(value: str) -> str:
    normalized = str(value or '').strip().lower()
    return normalized if normalized in NEW_CONVERSATION_INTENT_PROMPTS else ''

def new_conversation_intent_prompt(value):
    return NEW_CONVERSATION_INTENT_PROMPTS.get(supported_new_conversation_intent(value), '')

def _parse_query_date(value: str) -> date | None:
    value = str(value or '').strip()
    if not value:
        return
    else:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None

def _dashboard_window(query: "dict[str, list[str]] | None") -> "dict[str, str]":
    today = date.today()
    if not _query_value(query, "period", ""):
        _query_value(query, "period", "")
    raw_period = _query_value(query, "days", ""); period = raw_period.lower().strip()

    period_aliases = {"365": "year", "365d": "year", "365day": "year", "365days": "year", "yearly": "year", "annual": "year", "y": "year", "90": "quarter", "90d": "quarter", "90day": "quarter", "90days": "quarter", "quarterly": "quarter", "q": "quarter", "30": "month", "30d": "month", "30day": "month", "30days": "month", "monthly": "month", "m": "month", "15": "month", "15d": "month", "15day": "month", "15days": "month", "7": "week", "7d": "week", "7day": "week", "7days": "week", "weekly": "week", "w": "week", "1": "day", "1d": "day",

        "1day": "day", "1days": "day", "daily": "day",

        "d": "day"}; period = period_aliases.get(period, period or "month"); period_windows = {"year": (365, "近一年"), "quarter": (90, "近一季度"), "month": (30, "近一月"), "week": (7, "近一周"), "day": (1, "近一天")}

    start_date = _parse_query_date(_query_value(query, "start", ""))

    end_date = _parse_query_date(_query_value(query, "end", "")); is_custom = start_date is not None or end_date is not None
    if is_custom:
        if end_date is not None:
            end_date = today
        if start_date is not None:
            start_date = end_date - timedelta(days=29)
        match period:
            case _ as end_date:
                return {"period": "custom", "label": "自定义", "start": start_date.isoformat(), "end": end_date.isoformat()}

    days, label = period_windows.get(period, period_windows["month"]); end_date = today; start_date = today - timedelta(days=days - 1)
    return {"period": "month", "label": label, "start": start_date.isoformat(), "end": end_date.isoformat()}

def _dashboard_view_mode(query):
    raw = _query_value(query, 'mode', 'simple').lower().strip()
    aliases = {'brief': 'simple', 'human': 'simple', 'simple': 'simple', 'detail': 'analysis', 'complex': 'analysis', 'professional': 'analysis', 'ai': 'analysis', 'analysis': 'analysis'}
    return aliases.get(raw, 'simple')

def _dashboard_rate(numerator: Any, denominator: Any) -> float | None:
    base = _coerce_number(denominator)
    if base <= 0:
        return
    else:
        return _coerce_number(numerator) / base * 100

def _dashboard_change_rate(current: Any, previous: Any) -> float | None:
    previous_value = _coerce_number(previous)
    if previous_value <= 0:
        return
    else:
        return (_coerce_number(current) - previous_value) / previous_value * 100

def _dashboard_change_label(value: float | None) -> str:
    if value is None:
        return '样本不足'
    else:
        arrow = '↑' if value > 0 else '↓' if value < 0 else '→'
        return f'{arrow} {abs(value):.2f}%'

def _dashboard_chart_html(rows: "list[dict[str, Any]]", *, key: "str", title: "str", unit: "str") -> "str":
    row = maximum; points = [row for row in rows if not isinstance(row, dict)][-24:]; values = [_coerce_number(row.get(key)) for row in points]; row = unit
    if not values:
        values
    maximum = max([0])
    if points:
        match values:
            case 0:
                return f"<article class=\"dashboard-analysis-chart\" data-chart-state=\"missing\"><header><b>{html.escape(title)}</b><em>暂无真实数据</em></header><p>接入或导入对应日期数据后自动生成趋势，不以示例数据补空。</p></article>"

    bars = "".join(('<span style="height:{height}%" title="{label} · {value}{unit}"></span>'.format(height=max(4, min(100, round(value / maximum * 100))), label=html.escape(str(row.get("name") or ""), quote=True), value=html.escape(_format_amount(value) if key in ("revenue", "ad_spend", "settlement_amount") else _format_count(value), quote=True), unit=html.escape(unit, quote=True)) for row, value in zip(points, values)))
    return f"<article class=\"dashboard-analysis-chart\" data-chart-state=\"actual\"><header><b>{html.escape(title)}</b><em>{len(points)} 个时间点</em></header><div class=\"dashboard-analysis-bars\" role=\"img\" aria-label=\"{html.escape(title, quote=True)}\">{bars}</div><small>仅显示当前日期范围内已导入的真实记录。</small></article>"

    row = None; row = None

def _coerce_number(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    else:
        if isinstance(value, (int, float)):
            return float(value)
        else:
            text = re.sub('[^\\d.\\-]', '', str(value or ''))
            if text in {'.', '-', '-.', ''}:
                return 0.0
            else:
                try:
                    return float(text)
                except ValueError:
                    return 0.0

def _whole_number(value: Any) -> int:
    return int(round(_coerce_number(value)))

def _format_amount(value: Any) -> str:
    number = _coerce_number(value)
    if abs(number) < 0.005:
        return '0.00'
    else:
        return f'{number:,.2f}'

def _format_count(value: Any) -> str:
    return f'{_whole_number(value):,}'

def _format_ratio(value: Any) -> str:
    number = _coerce_number(value)
    if number <= 0:
        return '—'
    else:
        return f'{number:.2f}'

def _format_percent(value: Any) -> str:
    number = _coerce_number(value)
    if number == 0:
        return '0.00%'
    else:
        return f'{number * 100:.2f}%'

def _format_duration_minutes(value: Any) -> str:
    minutes = _coerce_number(value)
    if minutes <= 0:
        return '0 分钟'
    else:
        whole_minutes = int(round(minutes))
        hours, rest = divmod(whole_minutes, 60)
        if hours and rest:
            return f'{hours}小时{rest}分钟'
        else:
            if hours:
                return f'{hours}小时'
            else:
                return f'{rest}分钟'

def _snapshot_metric_value(snapshot: dict[str, Any], *needles: str) -> Any:
    lowered = [needle.lower() for needle in needles if needle]
    for item in snapshot.get('metrics', []):
        if not isinstance(item, dict):
            continue
        else:
            label = str(item.get('label') or '').lower()
            if lowered and all((needle in label for needle in lowered)):
                    return item.get('value')
    return 0

def _record_date_in_dashboard_window(record, start, end):
    if hasattr(record, 'fields'):
        pass
    fields = record.fields if isinstance(record.fields, dict) else {}
    if not fields.get('snapshot_end'):
        fields.get('snapshot_end')
        if not fields.get('metric_date'):
            fields.get('metric_date')
            if not fields.get('date'):
                fields.get('date')
                if not fields.get('sent_at'):
                    fields.get('sent_at')
                    if not fields.get('created_at'):
                        fields.get('created_at')
    raw_date = getattr(record, 'created_at', '')
    parsed = _parse_query_date(str(raw_date)[:10])
    if parsed is None:
        parsed = _parse_query_date(str(getattr(record, 'created_at', ''))[:10])
    if parsed is None:
        return True
    if not _parse_query_date(start):
        _parse_query_date(start)
    start_date = parsed
    if not _parse_query_date(end):
        _parse_query_date(end)
    end_date = parsed
    if start_date <= parsed:
        start_date <= parsed
        return parsed <= end_date

def _first_metric_value(fields: dict[str, Any], aliases: list[str]) -> float:
    for alias in aliases:
        if alias in fields:
            return _coerce_number(fields.get(alias))
    return 0.0

def _duration_minutes_metric_value(fields: "dict[str, Any]", aliases: "list[str]") -> "float":
    for alias in aliases:
        value = alias not in fields and _coerce_number(fields.get(alias))
        normalized = alias.lower()
        if "second" in normalized and normalized.endswith("_sec") or normalized.endswith("_secs"):
            return value / 60
        elif "hour" in normalized and normalized.endswith("_hr") or normalized.endswith("_hrs"):
            return value * 60

    return value

    return 0.0

def _module_metric_totals(root: "Path", record_types: "list[str]", metric_aliases: "dict[str, list[str]]", *, start: "str", end: "str", platform_resolver: "Any | None") -> "dict[str, Any]":
    totals = {key: 0.0 for key in metric_aliases}; key = None; by_platform = {}; record_count = 0
    for record_type in record_types:
        records = read_records(root, record_type)
        while 1:
            for record in records:
                if not _record_date_in_dashboard_window(record, start, end):
                    continue
                fields = {}
                platform = "".strip()
                if not platform:
                    if not fields.get("platform"):
                        fields.get("platform")
                        if not fields.get("source_platform"):
                            fields.get("source_platform")
                            if not fields.get("marketplace"):
                                fields.get("marketplace")
                                if not fields.get("channel"):
                                    fields.get("channel")
                                    if not fields.get("network"):
                                        fields.get("network")
                    platform = _dashboard_platform_label(fields.get("media_platform") or "未归类")
                bucket = by_platform.setdefault(platform, {"name": platform, "record_count": 0})
                bucket["record_count"] = int(bucket.get("record_count") or 0) + 1
                record_count += 1
                for key, aliases in metric_aliases.items():
                    if key == "live_duration_minutes":
                        value = _duration_minutes_metric_value(fields, aliases)
                    else:
                        value = _first_metric_value(fields, aliases)
                    totals[key] = float(totals.get(key) or 0) + value
                    bucket[key] = float(bucket.get(key) or 0) + value
            for key, value in totals.items():
                pass
            value = value
            key = key
            return {"summary": {key: round(value, 2)}, "record_count": record_count, "platforms": sorted(by_platform.values(), key=(lambda item: str(item.get("name") or "")))}
            key = None
    value = None; key = None

def _dashboard_platform_schema(value: Any) -> str:
    text = str(value or '').strip().lower()
    normalized = re.sub('[^a-z0-9]+', '_', text).strip('_')
    raw = str(value or '').strip()
    if not normalized and (not raw):
        return 'unknown'
    else:
        canonical = {'douyin', 'kuaishou_shop', 'pinduoduo', 'taobao_tmall', 'douyin_ecommerce', 'jingdong', 'pdd', 'kuaishou', 'weixin_channels', 'jd', '1688', 'xiaohongshu', 'wechat_channels'}
        if normalized in canonical:
            if normalized == 'weixin_channels':
                return 'wechat_channels'
            else:
                if normalized == 'jingdong':
                    return 'jd'
                else:
                    if normalized == 'pdd':
                        return 'pinduoduo'
                    else:
                        return normalized
        else:
            if any((token in raw for token in ['抖音电商', '抖店', '抖音小店'])):
                return 'douyin_ecommerce'
            else:
                if raw == '抖音' or 'douyin' in normalized:
                    return 'douyin'
                else:
                    if any((token in raw for token in ('快手小店', '快手电商'))):
                        return 'kuaishou_shop'
                    else:
                        if raw == '快手' or 'kuaishou' in normalized or 'kwai' in normalized:
                            return 'kuaishou'
                        else:
                            if '小红书' in raw or 'xiaohongshu' in normalized or 'rednote' in normalized:
                                return 'xiaohongshu'
                            else:
                                if any((token in raw for token in ('视频号', '微信小店'))):
                                    return 'wechat_channels'
                                else:
                                    if 'wechat_channels' in normalized or 'weixin_channels' in normalized:
                                        return 'wechat_channels'
                                    else:
                                        if any((token in raw for token in ('淘宝', '天猫'))):
                                            return 'taobao_tmall'
                                        else:
                                            if 'taobao' in normalized or 'tmall' in normalized or 'tao_bao' in normalized:
                                                return 'taobao_tmall'
                                            else:
                                                if '京东' in raw or normalized in f'jingdong' or 'jing_dong' in normalized:
                                                    return 'jd'
                                                else:
                                                    if '拼多多' in raw or 'pinduoduo' in normalized or normalized == 'pdd':
                                                        return 'pinduoduo'
                                                    else:
                                                        if '1688' in normalized or '阿里巴巴中国站' in raw or '阿里巴巴国内站' in raw:
                                                            return '1688'
                                                        else:
                                                            if 'tiktok_shop' in normalized or 'tik_tok_shop' in normalized or normalized in {'tt_shop', 'tk_shop'}:
                                                                return 'tiktok_shop'
                                                            else:
                                                                if normalized in {'tk', 'tik_tok', 'tiktok', 'douyin'} or 'tiktok' in normalized or 'tik_tok' in normalized:
                                                                    return 'tiktok'
                                                                else:
                                                                    if 'amazon' in normalized or normalized in f'{'amz'}':
                                                                        return 'amazon'
                                                                    else:
                                                                        if 'shein' in normalized:
                                                                            return 'shein'
                                                                        else:
                                                                            if 'shopee' in normalized:
                                                                                return 'shopee'
                                                                            else:
                                                                                if 'lazada' in normalized:
                                                                                    return 'lazada'
                                                                                else:
                                                                                    if 'walmart' in normalized:
                                                                                        return 'walmart'
                                                                                    else:
                                                                                        if 'etsy' in normalized:
                                                                                            return 'etsy'
                                                                                        else:
                                                                                            if 'ebay' in normalized:
                                                                                                return 'ebay'
                                                                                            else:
                                                                                                if 'aliexpress' in normalized or 'ali_express' in normalized or '速卖通' in text:
                                                                                                    return 'aliexpress'
                                                                                                else:
                                                                                                    if 'rakuten' in normalized:
                                                                                                        return 'rakuten'
                                                                                                    else:
                                                                                                        if 'emag' in normalized or 'e_mag' in normalized:
                                                                                                            return 'emag'
                                                                                                        else:
                                                                                                            if 'coupang' in normalized:
                                                                                                                return 'coupang'
                                                                                                            else:
                                                                                                                if 'wildberries' in normalized or 'wild_berries' in normalized:
                                                                                                                    return 'wildberries'
                                                                                                                else:
                                                                                                                    if 'ozon' in normalized:
                                                                                                                        return 'ozon'
                                                                                                                    else:
                                                                                                                        if 'shopify' in normalized:
                                                                                                                            return 'shopify'
                                                                                                                        else:
                                                                                                                            if 'woocommerce' in normalized or 'woo_commerce' in normalized:
                                                                                                                                return 'woocommerce'
                                                                                                                            else:
                                                                                                                                return normalized or 'unknown'

def _dashboard_platform_label(value: "Any") -> "str":
    schema = _dashboard_platform_schema(value)
    labels = {"amazon": "Amazon", "tiktok_shop": "TikTok Shop", "tiktok": "TikTok", "shein": "SHEIN", "shopee": "Shopee", "lazada": "Lazada", "walmart": "Walmart", "etsy": "Etsy", "ebay": "eBay", "aliexpress": "AliExpress", "rakuten": "Rakuten", "emag": "eMAG", "coupang": "Coupang", "wildberries": "Wildberries", "ozon": "Ozon", "shopify": "Shopify", "woocommerce": "WooCommerce",
        "douyin_ecommerce": "抖音电商", "douyin": "抖音", "kuaishou_shop": "快手小店", "kuaishou": "快手", "xiaohongshu": "小红书", "wechat_channels": "视频号 / 微信小店", "taobao_tmall": "淘宝 / 天猫", "jd": "京东", "pinduoduo": "拼多多", "1688": "1688 货源", "unknown": "未归类"}
    return labels.get(schema, _platform_label(value))

def _platform_logo_html(value: "Any", label: "Any"=None, *, compact: "bool") -> "str":
    schema = _dashboard_platform_schema(value)
    if not label:
        label
    display_label = str(_dashboard_platform_label(schema) or schema or "平台"); mark, bg, fg = _PLATFORM_LOGO_MARKS.get(schema, ((display_label.strip()[:2] or "?").upper(), "#eef2f7", "#1f2937")); classes = "platform-logo-mark"
    return f"<span class=\"{classes}\" data-platform-logo=\"{html.escape(schema, quote=True)}\" role=\"img\" aria-label=\"{html.escape(display_label, quote=True)} 标识\" title=\"{html.escape(display_label, quote=True)}\" style=\"--platform-logo-bg:{html.escape(bg, quote=True)};--platform-logo-fg:{html.escape(fg, quote=True)};\">{html.escape(str(mark))}</span>"

def _china_platform_catalog_entries(digitization_registry: "dict[str, Any]", platform_rows: "list[dict[str, Any]]") -> "list[dict[str, Any]]":
    registry_rows = {str(item.get("platform_id") or "").strip(): item for item in digitization_registry.get("platforms", []) if str(item.get("platform_id") or "").strip()}; item = local_row

    local_rows = {_dashboard_platform_schema(item.get("name")): item for item in platform_rows if isinstance(item, dict)}; item = None; truth_fields = ("revenue", "orders", "units", "parent_sku_count", "traffic", "homepage_views", "video_views", "live_views", "live_duration_minutes", "live_gmv", "affiliate_gmv", "creator_count"); entries = []
    for platform_id, kind in _CHINA_PLATFORM_CATALOG:
        registry_row = registry_rows.get(platform_id, {})
        local_row = local_rows.get(platform_id)
        if local_row:
            local_row
        has_imported_data = bool(any((_coerce_number(local_row.get(key)) for key in truth_fields)))
        if local_row:
            local_row
        has_local_object = bool(any((_whole_number(local_row.get(key)) for key in ("store_count", "account_count", "social_account_count", "communication_account_count", "browser_profile_count", "erp_connection_count", "project_count"))))
        connection_state = "not_connected"
        state_label = "已登记，未授权"
        group = state_label
        ##ERROR##({"platform_id": entries.append, "label": platform_id, "kind": _dashboard_platform_label(platform_id), "connection_state": kind, "state_label": connection_state, "dashboard_groups": [str(group) for group in registry_row.get("dashboard_groups", []) if str(group).strip()]})
    return entries

    item = None; item = None; group = None

def _render_platform_catalog_row(item: "dict[str, Any]", *, catalog_group: "str", metric_labels: "dict[str, str]") -> "str":
    platform_id = str(item.get("platform_id") or ""); label = str(item.get("label") or "未命名平台"); metrics = " · ".join((metric_labels.get(str(group), str(group)) for group in item.get("dashboard_groups", [])))
    return f"<div class=\"china-platform-catalog-row\" data-platform-catalog-entry=\"{html.escape(platform_id, quote=True)}\" data-platform-catalog-kind=\"{html.escape(catalog_group, quote=True)}\" data-platform-catalog-source-kind=\"{html.escape(str(item.get("source_kind") or ""), quote=True)}\" data-connection-state=\"{html.escape(str(item.get("connection_state") or "not_connected"), quote=True)}\">{_platform_logo_html(platform_id, label)}<span class=\"platform-row-copy\"><b>{html.escape(label)}</b><small>{html.escape(metrics)}</small></span><em>{html.escape(str(item.get("state_label") or "已登记，未授权"))}</em></div>"

def _render_platform_channel_overview(entries: "list[dict[str, Any]]", *, ecommerce_html: "str", social_html: "str", b2b_html: "str", represented_platforms: "dict[str, set[str]] | None") -> "str":
    group_labels = {"ecommerce_platform": ("电商平台", "全球与中国店铺经营、商品、订单、流量、广告、库存与结算"), "social_media": ("社交媒体", "内容账号、主页流量、直播、互动、私信、达人与商品点击"), "b2b_platform": ("B2B平台", "询盘、客户、供应商、货盘、报价、样品、采购、质检与通信")}; group_data = {"ecommerce_platform": ecommerce_html, "social_media": social_html, "b2b_platform": b2b_html}; source_kind_to_group = {"social_commerce": "ecommerce_platform", "marketplace": "ecommerce_platform", "social_content": "social_media", "sourcing": "b2b_platform"}; metric_labels = {"sales": "销售", "catalog": "商品", "traffic": "流量", "ads": "广告", "content": "内容", "live": "直播", "creator_affiliate": "达人/联盟", "affiliate": "达人/联盟", "operations": "运营", "finance": "结算", "inventory": "库存", "customer_service": "客服", "sourcing": "货源", "risk_review": "风控"}; grouped = {key: [] for key in group_labels}; key = metric_labels
    if not represented_platforms:
        represented_platforms
    represented = {}
    for entry in entries:
        source_kind = str(entry.get("kind") or "marketplace")
        catalog_group = source_kind_to_group.get(source_kind, "ecommerce_platform")
        platform_schema = _dashboard_platform_schema(entry.get("platform_id"))
        if platform_schema in represented.get(catalog_group, set()):
            continue
        grouped[catalog_group].append({"source_kind": source_kind})
    groups_html = []
    for label, detail in group_labels.items():
        rows = grouped.get(catalog_group, [])
        catalog_html = "".join((_render_platform_catalog_row(item, catalog_group=catalog_group, metric_labels=metric_labels) for item in rows))
        if not catalog_html:
            catalog_html = '<p class="platform-channel-catalog-empty">已登记平台均已进入本组经营数据。</p>'
        groups_html.append(f"<article class=\"china-platform-catalog-group\" id=\"platform-channel-{html.escape(catalog_group, quote=True)}\" data-platform-channel-group=\"{html.escape(catalog_group, quote=True)}\" data-platform-catalog-group=\"{html.escape(catalog_group, quote=True)}\"><header><b>{html.escape(label)}</b><small>{html.escape(detail)}</small></header><div class=\"platform-channel-catalog-list\">{catalog_html}</div><div class=\"platform-channel-data\"><small>真实经营数据</small>{group_data[catalog_group]}</div></article>")
    return f"<section class=\"china-platform-catalog\" data-platform-channel-overview=\"true\" data-platform-catalog=\"china\"><div class=\"section-title\"><h3>平台与渠道经营聚合</h3><span>全球与中国统一收在一处；平台登记、账号授权和真实数据分别显示</span></div><nav class=\"platform-channel-tabs\" aria-label=\"平台与渠道分类\"><a href=\"#platform-channel-ecommerce_platform\">电商平台</a><a href=\"#platform-channel-social_media\">社交媒体</a><a href=\"#platform-channel-b2b_platform\">B2B平台</a></nav><div class=\"china-platform-catalog-grid\">{"".join(groups_html)}</div></section>"

    key = catalog_group

def _dashboard_record_platform(fields: "dict[str, Any]") -> "str":
    if not fields.get("marketplace"):
        fields.get("marketplace")
        if not fields.get("platform"):
            fields.get("platform")
            if not fields.get("commerce_platform"):
                fields.get("commerce_platform")
                if not fields.get("source_platform"):
                    fields.get("source_platform")
                    if not fields.get("channel"):
                        fields.get("channel")
                        if not fields.get("network"):
                            fields.get("network")
    return _dashboard_platform_label(fields.get("media_platform") or "未归类")

def _has_store_binding(fields: "dict[str, Any]") -> "bool":
    return any((str(fields.get(key) or "").strip() for key in ("store_id", "store_name", "shop_id", "shop_name", "bound_store_id", "bound_shop_id", "store_binding_id", "shop_binding_id", "seller_id", "account_binding_id")))

def _content_platform_resolver(fields: "dict[str, Any]", _record: "Any | None"=None) -> "str":
    label = _dashboard_record_platform(fields); schema = _dashboard_platform_schema(label)
    if schema in ("tiktok", "tiktok_shop"):
        if _has_store_binding(fields) or _first_metric_value(fields, ["product_clicks", "shop_clicks", "live_orders", "live_gmv"]) > 0:
            return "TikTok Shop"
    elif schema in ("douyin", "douyin_ecommerce"):
        if _has_store_binding(fields) or _first_metric_value(fields, ["product_clicks", "shop_clicks", "live_orders", "live_gmv", "gmv"]) > 0:
            return "抖音电商"
    elif schema in ("kuaishou", "kuaishou_shop"):
        if _has_store_binding(fields) or _first_metric_value(fields, ["product_clicks", "shop_clicks", "live_orders", "live_gmv", "gmv"]) > 0:
            return "快手小店"
    elif schema == "wechat_channels":
        if _has_store_binding(fields) or _first_metric_value(fields, ["product_clicks", "shop_clicks", "live_orders", "live_gmv", "gmv"]) > 0:
            return "视频号 / 微信小店"
    return label

def _metric_platform_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapped = {}
    for row in payload.get('platforms', []) if isinstance(payload, dict) else []:
        if not isinstance(row, dict):
            continue
        else:
            name = str(row.get('name') or '未归类').strip() or '未归类'
            mapped[name] = row
    return mapped

def _metric_value(row: dict[str, Any] | None, key: str) -> float:
    if not isinstance(row, dict):
        return 0.0
    else:
        return _coerce_number(row.get(key))

def _activity_rate(numerator: Any, denominator: Any) -> float:
    denominator_value = _coerce_number(denominator)
    if denominator_value <= 0:
        return 0.0
    else:
        return round(_coerce_number(numerator) / denominator_value, 4)

def _inventory_activity_fields(row):
    product_count = _metric_value(row, 'product_count')
    active_product_count = _metric_value(row, 'active_product_count')
    sold_product_count = _metric_value(row, 'sold_product_count')
    new_active_product_count = _metric_value(row, 'new_active_product_count')
    return {'product_count': product_count, 'active_product_count': active_product_count, 'sold_product_count': sold_product_count, 'new_active_product_count': new_active_product_count, 'active_product_ratio': _activity_rate(active_product_count, product_count), 'product_activity_rate': _activity_rate(sold_product_count, active_product_count), 'new_active_product_ratio': _activity_rate(new_active_product_count, product_count)}

def _platform_has_ad_metric(row: dict[str, Any]) -> bool:
    return _coerce_number(row.get('ad_spend')) > 0 or _coerce_number(row.get('roas')) > 0

def _render_platform_metric_cell(key, label, value, note=''):
    note_html = f"<small>{html.escape(note)}</small>" if note else ''
    return f"<span data-platform-metric=\"{html.escape(key, quote=True)}\"><em>{html.escape(label)}</em><b>{html.escape(value)}</b>{note_html}</span>"

def _platform_metric_tuple_from_key(
    key: str, row: dict[str, Any]
) -> tuple[str, str, str, str] | None:
    """Map one registered platform metric to a truthful dashboard cell."""

    normalized_key = key.replace("_when_imported", "")
    when_imported = key.endswith("_when_imported")
    if normalized_key == "revenue":
        return "revenue", "销售额", _format_amount(row.get("revenue")), "本地导入店铺经营数据"
    if normalized_key == "orders_units":
        return "orders_units", "订单/件数", f'{_format_count(row.get("orders"))}/{_format_count(row.get("units"))}', ""
    if normalized_key == "paid_valid_refund_orders":
        return "paid_valid_refund_orders", "付款/有效/退款订单", f'{_format_count(row.get("paid_orders"))}/{_format_count(row.get("valid_orders"))}/{_format_count(row.get("refund_order_count"))}', "ERP/平台报表导入字段；无字段保持 0"
    if normalized_key == "paid_valid_sales":
        return "paid_valid_sales", "付款/有效销售额", f'{_format_amount(row.get("paid_sales_amount"))}/{_format_amount(row.get("valid_sales_amount"))}', "付款销售额 / 有效销售额"
    if normalized_key == "payout_profit_rate":
        return "payout_profit_rate", "预计回款/利润率", f'{_format_amount(row.get("expected_payout"))}/{_format_percent(row.get("profit_rate"))}', "预计值不能覆盖实际结算账单"
    if normalized_key == "parent_skus":
        return "parent_skus", "母体SKU", _format_count(row.get("parent_sku_count")), "只计母体，子体/变体不进总数"
    if normalized_key == "traffic":
        return "traffic", "流量/访问", _format_count(row.get("traffic")), "有导入字段时才显示真实值"
    if normalized_key == "homepage_views":
        if when_imported and not _coerce_number(row.get("homepage_views")):
            return None
        return "homepage_views", "主页浏览量", _format_count(row.get("homepage_views")), "仅在报表、API 或授权读取含该字段时显示"
    if normalized_key == "social_engagement":
        metrics = ("likes", "comments", "saves", "shares")
        if when_imported and not any(_coerce_number(row.get(metric)) for metric in metrics):
            return None
        return "social_engagement", "点赞/评论/收藏/转发", "/".join(_format_count(row.get(metric)) for metric in metrics), "内容账号数据导入后显示"
    if normalized_key == "followers":
        if when_imported and not _coerce_number(row.get("followers")):
            return None
        return "followers", "粉丝", _format_count(row.get("followers")), "需账号绑定或导入报表"
    if normalized_key == "product_activity":
        return "product_activity", "动销/在售", f'{_format_count(row.get("sold_product_count"))}/{_format_count(row.get("active_product_count"))} · {_format_percent(row.get("product_activity_rate"))}', "有销量产品数 / 在售产品数"
    if normalized_key == "new_active_products":
        return "new_active_products", "新增在售/占比", f'{_format_count(row.get("new_active_product_count"))}/{_format_percent(row.get("new_active_product_ratio"))}', "新增在售产品数 / 产品总数"
    if normalized_key == "video_product_clicks":
        return "video_product_clicks", "视频播放/商品点击", f'{_format_count(row.get("video_views"))}/{_format_count(row.get("product_clicks"))}', "绑定内容账号后汇入"
    if normalized_key == "live_gmv_orders":
        return "live_gmv_orders", "直播GMV/订单", f'{_format_amount(row.get("live_gmv"))}/{_format_count(row.get("live_orders"))}', "直播指标单独列出"
    if normalized_key == "live_views":
        return "live_views", "直播观看", _format_count(row.get("live_views")), "直播间观看/观众数"
    if normalized_key == "live_duration":
        return "live_duration", "直播时长", _format_duration_minutes(row.get("live_duration_minutes")), "只读导入字段"
    if normalized_key == "affiliate_gmv_commission":
        return "affiliate_gmv_commission", "达人GMV/佣金", f'{_format_amount(row.get("affiliate_gmv"))}/{_format_amount(row.get("creator_commission"))}', "达人报表导入"
    if normalized_key == "creator_collaboration":
        return "creator_collaboration", "达人/合作", f'{_format_count(row.get("creator_count"))}/{_format_count(row.get("creator_collaborations"))}', "达人或联盟报表"
    if normalized_key == "creator_samples_content":
        return "creator_samples_content", "样品/授权内容", f'{_format_count(row.get("sample_sent"))}/{_format_count(row.get("creator_content_count"))}', "寄样与授权内容分开登记"
    if normalized_key == "ad_roas":
        if when_imported and not _platform_has_ad_metric(row):
            return None
        return "ad_roas", "广告/ROAS", f'{_format_amount(row.get("ad_spend"))}/{_format_ratio(row.get("roas"))}', "只读已导入广告字段"
    if normalized_key == "returns_refunds":
        return "returns_refunds", "退款/退货", f'{_format_count(row.get("refund_count"))}/{_format_count(row.get("return_count"))}', ""
    if normalized_key == "settlement":
        return "settlement", "结算", _format_amount(row.get("settlement_amount")), "平台结算单优先"
    if normalized_key == "fees":
        return "fees", "费用", _format_amount(row.get("fee_total")), "已导入费用项"
    return None

def _platform_card_metrics(row: dict[str, Any], digitization_registry: dict[str, Any] | None=None) -> list[tuple[str, str, str, str]]:
    registry = digitization_registry or {}
    if registry:
        keys = platform_card_metric_keys(registry, row.get('name'))
    else:
        schema = _dashboard_platform_schema(row.get('name'))
        keys = ['revenue', 'orders_units', 'parent_skus', 'traffic', 'homepage_views_when_imported']
        if schema == 'tiktok_shop':
            keys.extend(['video_product_clicks', 'live_gmv_orders', 'live_views', 'live_duration', 'affiliate_gmv_commission', 'creator_collaboration', 'creator_samples_content', 'ad_roas_when_imported'])
        else:
            if schema in {'kuaishou_shop', 'wechat_channels', 'douyin_ecommerce'}:
                keys.extend(['homepage_views_when_imported', 'video_product_clicks', 'live_gmv_orders', 'live_views', 'live_duration', 'affiliate_gmv_commission', 'creator_collaboration', 'social_engagement_when_imported', 'followers_when_imported', 'ad_roas_when_imported'])
            else:
                if schema in {'kuaishou', 'xiaohongshu', 'douyin'}:
                    keys.extend(['homepage_views_when_imported', 'video_product_clicks', 'social_engagement_when_imported', 'followers_when_imported'])
                else:
                    if schema == 'amazon':
                        keys.append('ad_roas')
                    else:
                        if schema!= 'shein':
                            keys.append('ad_roas_when_imported')
        keys.extend(['returns_refunds', 'settlement', 'fees'])
    metrics = []
    seen = set()
    for key in keys:
        metric = _platform_metric_tuple_from_key(key, row)
        if metric and metric[0] not in seen:
                metrics.append(metric)
                seen.add(metric[0])
    if not _coerce_number(row.get('product_count')):
        if 'product_activity' not in seen:
            metric = _platform_metric_tuple_from_key('product_activity', row)
            if metric:
                metrics.append(metric)
                seen.add(metric[0])
    if _coerce_number(row.get('new_active_product_count')) and 'new_active_products' not in seen:
            metric = _platform_metric_tuple_from_key('new_active_products', row)
            if metric:
                metrics.append(metric)
                seen.add(metric[0])
    if _coerce_number(row.get('homepage_views')) and 'homepage_views' not in seen:
            metric = _platform_metric_tuple_from_key('homepage_views', row)
            if metric:
                metrics.append(metric)
                seen.add(metric[0])
    if _platform_has_ad_metric(row) and 'ad_roas' not in seen:
            platform = row.get('name')
            if platform_supports_metric_by_default(registry, platform, 'ad_roas'):
                metric = _platform_metric_tuple_from_key('ad_roas', row)
            else:
                metric = ('ad_spend', '广告花费', _format_amount(row.get('ad_spend')), '仅因本地导入广告字段而显示')
            if metric:
                metrics.append(metric)
    return metrics

def _render_platform_rollup_card(row, digitization_registry=None):
    if not row.get('name'):
        row.get('name')
    platform = str('未归类')
    schema = _dashboard_platform_schema(platform)
    if schema == 'shein':
        pass
    ad_scope = 'not_default' if not _platform_has_ad_metric(row) else 'available_when_imported'
    if not _coerce_number(row.get('video_views')) and not _coerce_number(row.get('live_views')):
        pass
    content_merged = 'true' if _coerce_number(row.get('live_duration_minutes')) else 'false'
    if not digitization_registry:
        digitization_registry
    if not {}.get('schema_version'):
        {}.get('schema_version')
    registry_version = str('')
    metrics_html = ''.join((_render_platform_metric_cell(*metric) for metric in _platform_card_metrics(row, digitization_registry)))
    state = '已读真实指标' if any((_coerce_number(row.get(key)) for key in ('revenue', 'orders', 'parent_sku_count', 'traffic', 'homepage_views', 'video_views', 'live_views', 'live_duration_minutes', 'live_gmv'))) else '待接入数据'
    if not row.get('country_sites'):
        row.get('country_sites')
    return ''.join(['<article class="platform-rollup-card" data-platform-rollup="', {html.escape(platform, quote=True)}, '" data-platform-schema="', {html.escape(schema, quote=True)}, '" data-platform-digitization-version="', {html.escape(registry_version, quote=True)}, '" data-platform-ad-scope="', {html.escape(ad_scope, quote=True)}, '" data-store-content-merged="', {content_merged}, '" data-store-count="', {_whole_number(row.get('store_count'))}, '" data-account-count="', {_whole_number(row.get('account_count'))}, '" data-social-account-count="', {_whole_number(row.get('social_account_count'))}, '" data-communication-account-count="', {_whole_number(row.get('communication_account_count'))}, '" data-browser-profile-count="', {_whole_number(row.get('browser_profile_count'))}, '" data-erp-connection-count="', {_whole_number(row.get('erp_connection_count'))}, '"><header><div><b>', {html.escape(platform)}, '</b><small>', {_format_count(row.get('store_count'))}, ' 店聚合 · ', {_format_count(row.get('account_count'))}, ' 账号 · ', {_format_count(row.get('browser_profile_count'))}, ' 浏览器/IP · ', {_format_count(row.get('project_count'))}, ' 项目 · ', {html.escape(str('站点待补'))}, '</small></div><em>', {html.escape(state)}, '</em></header><div class="platform-rollup-metrics">', {metrics_html}, '</div></article>'])

def _dashboard_text(value: Any) -> str:
    if value is None:
        return ''
    else:
        text = str(value).strip()
        if not text:
            return ''
        else:
            if text.lower() in {'na', '0', 'none', '-', 'n/a', 'null', 'unknown'}:
                return ''
            else:
                return text

def _dashboard_first_text(row: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        if key not in row:
            continue
        else:
            value = row.get(key)
            if isinstance(value, (list, tuple, set)):
                for item in value:
                    text = _dashboard_text(item)
                    if text:
                        return text
                continue
            else:
                text = _dashboard_text(value)
                if text:
                    return text
    return ''

def _dashboard_browser_identity(row):
    provider = _dashboard_first_text(row, [*('browser_provider', 'profile_provider', 'ip_provider')])
    seq = _dashboard_first_text(row, [*('browser_profile_seq', 'browser_seq', 'profile_seq')])
    explicit = _dashboard_first_text(row, [*('browser_profile', 'browser_profile_id', 'browser_environment_id', 'ip_profile', 'ip_profile_id', 'environment_id', 'execution_identity_id')])
    if seq and provider:
        return f"{provider}:{seq}".lower()
    if seq:
        return f"bitbrowser:{seq}".lower()
    if explicit:
        text = explicit.lower().replace('bitbrowser-', 'bitbrowser:')
        text = text.replace('browser:bitbrowser:', 'bitbrowser:')
        return text
    return ''

def _dashboard_store_identity(row, platform):
    identity = _dashboard_first_text(row, [*('store_external_id', 'external_id', 'store_id', 'shop_id', 'seller_id', 'id', 'store_name', 'shop_name', 'name')])
    if identity:
        return f"{platform}|{identity}".lower()
    browser = _dashboard_browser_identity(row)
    site = _dashboard_first_text(row, [*('country_site', 'country_code', 'site', 'country', 'marketplace')])
    if browser and _dashboard_platform_schema(platform) == 'amazon':
        return f"{platform}|{site}|browser:{browser}".lower()
    return ''

def _new_object_bucket(name):
    return {'name': name, 'store_ids': set(), 'account_ids': set(), 'social_account_ids': set(), 'communication_account_ids': set(), 'browser_profile_ids': set(), 'erp_connection_ids': set(), 'country_sites': set(), 'store_modes': set(), 'statuses': set(), 'project_ids': set()}

def _dashboard_add_identity(buckets: dict[str, dict[str, Any]], totals: dict[str, set[str]], platform: str, key: str, identity: str) -> None:
    identity = _dashboard_text(identity)
    if not identity:
        return
    else:
        label = _dashboard_platform_label(platform)
        bucket = buckets.setdefault(label, _new_object_bucket(label))
        bucket[key].add(identity.lower())
        totals[key].add(f'{label}|{identity}'.lower())

def _dashboard_add_dimension(buckets, totals, platform, key, value):
    text = _dashboard_text(value)
    if not text:
        return None
    label = _dashboard_platform_label(platform)
    bucket = buckets.setdefault(label, _new_object_bucket(label))
    bucket[key].add(text)
    totals[key].add(f"{label}|{text}".lower())

def _dashboard_add_platform_store(buckets: "dict[str, dict[str, Any]]", totals: "dict[str, set[str]]", platform: "str", row: "dict[str, Any]", *, count_store: "bool") -> "None":
    label = _dashboard_platform_label(platform)
    if count_store:
        _dashboard_add_identity(buckets, totals, label, "store_ids", _dashboard_store_identity(row, label))
    _dashboard_add_dimension(buckets, totals, label, "country_sites", _dashboard_first_text(row, ["country_site", "country_code", "site", "country", "marketplace"])); _dashboard_add_dimension(buckets, totals, label, "store_modes", _dashboard_first_text(row, ["store_mode", "fulfillment_mode", "mode", "seller_mode", "ownership"])); _dashboard_add_dimension(buckets, totals, label, "statuses", _dashboard_first_text(row, ["status", "connection_status", "authorization_status", "state"]))
    for account_key in ("seller_account_id", "seller_account", "merchant_id", "account_id", "shop_id", "business_center_id", "ads_account_id", "advertising_account_id", "store_external_id", "external_id"):
        account_identity = _dashboard_text(row.get(account_key))
        if not account_identity:
            continue
        _dashboard_add_identity(buckets, totals, label, "account_ids", account_identity)

    _dashboard_add_identity(buckets, totals, label, "browser_profile_ids", _dashboard_browser_identity(row))
    for erp_key in ("erp_account_id", "erp_route_id", "erp_provider", "wms_account_id", "warehouse_account_id", "warehouse_provider", "finance_account_id", "settlement_account_id"):
        erp_identity = _dashboard_text(row.get(erp_key))
        if not erp_identity:
            continue
        _dashboard_add_identity(buckets, totals, label, "erp_connection_ids", f"{erp_key}:{erp_identity}")

def _bound_operating_store_scope(config):
    platforms = set()
    store_aliases = set()
    aliases_by_platform = {}
    alias_keys = [*('id', 'external_id', 'store_external_id', 'store_id', 'shop_id', 'seller_id', 'name', 'store_name', 'shop_name', 'sub_store_name', 'browser_profile', 'profile_name', 'execution_identity_id')]
    if isinstance(config.get('projects'), list):
        pass
    else:
        pass
    for project in []:
        if isinstance(project.get('channels'), list):
            pass
        else:
            pass
        for channel in []:
            if not channel.get('platform'):
                channel.get('platform')
            label = _dashboard_platform_label(channel.get('name'))
            for store in business_bound_stores(channel.get('stores')):
                platforms.add(label)
                platform_aliases = aliases_by_platform.setdefault(label, set())
                for key in alias_keys:
                    value = _dashboard_text(store.get(key))
                    normalized = value.lower()
                    store_aliases.add(normalized)
                    platform_aliases.add(normalized)
    return {'platforms': platforms, 'store_aliases': store_aliases, 'aliases_by_platform': aliases_by_platform}

def _store_matches_bound_scope(row: "dict[str, Any]", platform: "str", scope: "dict[str, Any]") -> "bool":
    label = _dashboard_platform_label(platform); allowed = scope.get("aliases_by_platform", {}).get(label, set())
    if not allowed:
        return False
    candidates = {_dashboard_text(row.get(key)).lower() for key in ("id", "external_id", "store_external_id", "store_id", "shop_id", "seller_id", "name", "store_name", "shop_name", "sub_store_name", "browser_profile", "profile_name", "execution_identity_id") if _dashboard_text(row.get(key))}; key = None
    return bool(candidates & allowed)

    key = None

def _dashboard_object_inventory(
    root: Any,
    config: dict[str, Any],
    sales_stores: list[dict[str, Any]],
    configured_platforms: dict[str, Any],
    content_payload: dict[str, Any],
    communication_payload: dict[str, Any],
    inventory_payload: dict[str, Any],
) -> dict[str, Any]:
    """Count configured business objects without inventing stores from metric rows."""

    del sales_stores, configured_platforms

    def schema(value: Any) -> str:
        raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        if "tiktok_shop" in raw or raw in {"tk_shop", "tt_shop"}:
            return "tiktok_shop"
        if raw in {"tiktok", "tik_tok", "tk"}:
            return "tiktok"
        if "amazon" in raw or raw == "amz":
            return "amazon"
        if "shein" in raw:
            return "shein"
        if "douyin" in raw or "抖音" in str(value or ""):
            return "douyin"
        if "xiaohongshu" in raw or "小红书" in str(value or ""):
            return "xiaohongshu"
        if raw in {"email", "communications", "communication"}:
            return "communications"
        if raw in {"browser", "browser_ip"}:
            return "browser"
        return raw or "unknown"

    labels = {
        "tiktok_shop": "TikTok Shop",
        "tiktok": "TikTok",
        "amazon": "Amazon",
        "shein": "SHEIN",
        "douyin": "抖音",
        "xiaohongshu": "小红书",
        "communications": "Communications",
        "browser": "Browser",
    }

    keys = (
        "store_ids",
        "account_ids",
        "social_account_ids",
        "communication_account_ids",
        "browser_profile_ids",
        "erp_connection_ids",
        "country_sites",
        "store_modes",
        "statuses",
        "project_ids",
    )
    buckets: dict[str, dict[str, set[str]]] = {}

    def bucket(platform_schema: str) -> dict[str, set[str]]:
        label = labels.get(platform_schema, str(platform_schema or "未归类"))
        return buckets.setdefault(label, {key: set() for key in keys})

    def remember(target: dict[str, set[str]], key: str, value: Any) -> None:
        text_value = str(value or "").strip()
        if text_value and text_value.lower() not in {"none", "unknown", "n/a", "0", "-"}:
            target[key].add(text_value.casefold())

    alias_keys = (
        "id",
        "external_id",
        "store_external_id",
        "store_id",
        "shop_id",
        "seller_id",
        "name",
        "store_name",
        "browser_profile",
    )
    allowed_aliases: dict[str, set[str]] = {}
    configured_store_rows: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for project in config.get("projects") or []:
        if not isinstance(project, dict):
            continue
        project_id = str(project.get("id") or project.get("name") or "project")
        for channel in project.get("channels") or []:
            if not isinstance(channel, dict):
                continue
            platform_schema = schema(channel.get("platform") or channel.get("name"))
            for store in channel.get("stores") or []:
                if not isinstance(store, dict) or not is_business_bound_store(store):
                    continue
                configured_store_rows.append((platform_schema, store, channel))
                aliases = allowed_aliases.setdefault(platform_schema, set())
                for alias_key in alias_keys:
                    alias = str(store.get(alias_key) or "").strip().casefold()
                    if alias:
                        aliases.add(alias)
                target = bucket(platform_schema)
                identity = str(
                    store.get("external_id")
                    or store.get("store_external_id")
                    or store.get("store_id")
                    or store.get("id")
                    or store.get("name")
                    or ""
                )
                remember(target, "store_ids", identity)
                remember(target, "account_ids", identity)
                remember(target, "country_sites", channel.get("country_site"))
                remember(target, "store_modes", store.get("store_mode"))
                remember(target, "statuses", store.get("status") or channel.get("status"))
                remember(target, "project_ids", project_id)

    profile = _load_json(root / "config" / "account_profile.json")

    def profile_matches(row: dict[str, Any], platform_schema: str) -> bool:
        aliases = allowed_aliases.get(platform_schema, set())
        if not aliases:
            return False
        candidates = {
            str(row.get(key) or "").strip().casefold()
            for key in alias_keys
            if str(row.get(key) or "").strip()
        }
        return bool(candidates & aliases)

    for row in profile.get("stores") or []:
        if not isinstance(row, dict):
            continue
        platform_schema = schema(
            row.get("platform_id") or row.get("platform_label") or row.get("platform")
        )
        if not profile_matches(row, platform_schema):
            continue
        target = bucket(platform_schema)
        for account_key in (
            "store_external_id",
            "seller_account_id",
            "account_id",
            "business_center_id",
            "ads_account_id",
        ):
            remember(target, "account_ids", row.get(account_key))
        remember(target, "browser_profile_ids", row.get("browser_profile"))

    for row in profile.get("social_accounts") or []:
        if not isinstance(row, dict):
            continue
        platform_schema = schema(
            row.get("platform_id") or row.get("platform_label") or row.get("platform")
        )
        if platform_schema == "tiktok" and "tiktok_shop" in allowed_aliases:
            platform_schema = "tiktok_shop"
        if platform_schema not in allowed_aliases:
            continue
        target = bucket(platform_schema)
        remember(
            target,
            "social_account_ids",
            row.get("account_id") or row.get("handle") or row.get("username"),
        )

    for row in profile.get("email_accounts") or []:
        if not isinstance(row, dict):
            continue
        platform_schema = schema(
            row.get("platform_id") or row.get("platform_label") or row.get("platform")
        )
        if platform_schema not in allowed_aliases:
            continue
        remember(
            bucket(platform_schema),
            "communication_account_ids",
            row.get("account_id") or row.get("email") or row.get("mailbox"),
        )

    for row in profile.get("browser_profiles") or []:
        if not isinstance(row, dict):
            continue
        platform_schema = schema(
            row.get("platform_id") or row.get("platform_label") or row.get("platform")
        )
        if platform_schema not in allowed_aliases:
            continue
        remember(
            bucket(platform_schema),
            "browser_profile_ids",
            row.get("browser_profile") or row.get("profile_id") or row.get("name"),
        )

    # Content-only networks may be genuine operating objects, but commerce metric
    # rows may never create a store identity on their own.
    for payload in (content_payload, communication_payload, inventory_payload):
        for row in payload.get("platforms") or [] if isinstance(payload, dict) else []:
            if not isinstance(row, dict):
                continue
            platform_schema = schema(row.get("name") or row.get("platform"))
            if platform_schema in {"tiktok_shop", "amazon", "shein"}:
                if platform_schema not in allowed_aliases:
                    continue
            elif platform_schema == "tiktok" and "tiktok_shop" in allowed_aliases:
                platform_schema = "tiktok_shop"
            bucket(platform_schema)

    platform_counts: dict[str, dict[str, int]] = {}
    totals = {key: set() for key in keys}
    for label, values in buckets.items():
        platform_counts[label] = {
            key[:-4] + "count" if key.endswith("_ids") else key[:-1] + "count": len(items)
            for key, items in values.items()
        }
        # Preserve the exact public field names expected by the renderer.
        platform_counts[label] = {
            "store_count": len(values["store_ids"]),
            "account_count": len(values["account_ids"]),
            "social_account_count": len(values["social_account_ids"]),
            "communication_account_count": len(values["communication_account_ids"]),
            "browser_profile_count": len(values["browser_profile_ids"]),
            "erp_connection_count": len(values["erp_connection_ids"]),
            "country_site_count": len(values["country_sites"]),
            "store_mode_count": len(values["store_modes"]),
            "status_count": len(values["statuses"]),
            "project_count": len(values["project_ids"]),
        }
        for key, items in values.items():
            totals[key].update(f"{label}|{item}" for item in items)

    return {
        "platforms": platform_counts,
        "platform_count": len(platform_counts),
        "store_count": len(totals["store_ids"]),
        "account_count": len(totals["account_ids"]),
        "social_account_count": len(totals["social_account_ids"]),
        "communication_account_count": len(totals["communication_account_ids"]),
        "browser_profile_count": len(totals["browser_profile_ids"]),
        "erp_connection_count": len(totals["erp_connection_ids"]),
        "country_site_count": len(totals["country_sites"]),
        "store_mode_count": len(totals["store_modes"]),
        "status_count": len(totals["statuses"]),
        "project_count": len(totals["project_ids"]),
        "truth": "店铺身份只来自项目配置；历史指标不会创建店铺。",
    }

def _seller_mode_dimension_summary(root: "Path") -> "dict[str, Any]":
    registry = _load_json(root / "config" / "seller_mode_skill_pack_registry.json"); modes = [item for item in registry.get("modes", []) if not isinstance(item, dict)]; item = None; guardrails = {}; prohibited = [item for item in guardrails.get("prohibited_behaviors", []) if not isinstance(item, dict)]; item = None

    review_gated = [item for item in guardrails.get("review_gated_behaviors", []) if not isinstance(item, dict)]; item = None; variant_count = 0; prohibited_variant_count = 0

    review_variant_count = 0; labels = []
    for mode in modes:
        if not mode.get("label"):
            mode.get("label")
        label = _dashboard_text(mode.get("id"))
        if label:
            labels.append(label)
        variants = [item for item in mode.get("variants", []) if not isinstance(item, dict)]
        item = None
        variant_count += len(variants)
        prohibited_variant_count += sum((1 for item in variants))
        review_variant_count += sum((1 for item in variants))
    return {"mode_count": len(modes), "variant_count": variant_count, "prohibited_count": len(prohibited) + prohibited_variant_count, "review_gated_count": len(review_gated) + review_variant_count, "labels": labels[:8]}

    item = None; item = None; item = None; item = None

def _dashboard_task_gate_summary(root: "Path") -> "dict[str, Any]":
    queue = _load_json(root / "config" / "current_task_queue.json")
    tasks = [item for item in queue.get("tasks", []) if isinstance(item, dict)]
    paused_statuses = {"paused", "paused_by_owner", "paused_by_owner_amazon"}
    blocked_statuses = {"blocked", "blocked_owner_input"}
    amazon_paused = any(
        str(item.get("status") or "").strip().lower() in paused_statuses
        and "amazon"
        in " ".join(
            str(item.get(field) or "")
            for field in ("id", "key", "title", "platform")
        ).lower()
        for item in tasks
    )
    blocked_count = sum(
        1
        for item in tasks
        if str(item.get("status") or "").strip().lower() in blocked_statuses
    )
    paused_count = sum(
        1
        for item in tasks
        if str(item.get("status") or "").strip().lower() in paused_statuses
    )
    return {"amazon_paused": amazon_paused, "blocked_count": blocked_count, "paused_count": paused_count}

    item = None

def _dashboard_dimension_matrix_html(root: "Path", *, object_inventory: "dict[str, Any]", sales_payload: "dict[str, Any]", content_payload: "dict[str, Any]", communication_payload: "dict[str, Any]", inventory_payload: "dict[str, Any]", platform_rows: "list[dict[str, Any]]", summary: "dict[str, Any]", connector_live: "int", connector_local_ready: "int", connector_browser_only: "int", connector_blocked: "int", connector_count: "int", connector_pending: "int") -> "str":
    seller_modes = _seller_mode_dimension_summary(root); task_gates = _dashboard_task_gate_summary(root); global_dimensions = global_commerce_dimension_snapshot(root); analytics_foundation = ai_analytics_data_foundation_snapshot(root)
    if not sales_payload.get("platforms"):
        sales_payload.get("platforms")
        if not sales_payload.get("stores"):
            sales_payload.get("stores")
    sales_has_data = bool(sales_payload.get("records"))

    content_has_data = _whole_number(content_payload.get("record_count")) > 0

    communication_has_data = _whole_number(communication_payload.get("record_count")) > 0; inventory_has_data = _whole_number(inventory_payload.get("record_count")) > 0
    if not _coerce_number(summary.get("ad_spend")) > 0:
        _coerce_number(summary.get("ad_spend")) > 0

    ads_has_data = _coerce_number(summary.get("roas")) > 0; finance_has_data = any((_coerce_number(summary.get(key)) > 0 for key in ("settlement_amount", "expected_payout", "expected_profit", "fee_total", "buyer_paid_amount"))); data_families = [("sales_orders", "销售/订单", sales_has_data), ("content_social_live_creator", "内容/社媒/直播/达人", content_has_data), ("ads", "广告投流", ads_has_data), ("communication_b2b", "外贸/通信/客户", communication_has_data), ("inventory_product_sku", "商品/SKU/库存", inventory_has_data), ("finance_settlement", "结算/费用/利润", finance_has_data), ("identity_connectors", "账号/连接/执行身份", bool(object_inventory.get("platform_count") or connector_count)), ("risk_governance", "风险/权限/门禁", True)]

    active_families = [item for item in data_families if not item[2]]; item = row

    object_axes = [("platform", object_inventory.get("platform_count")), ("country_site", object_inventory.get("country_site_count")),

        ("store_mode", object_inventory.get("store_mode_count")),

        ("store",

    object_inventory.get("store_count")), ("platform_account", object_inventory.get("account_count")), ("social_account", object_inventory.get("social_account_count")), ("communication_account", object_inventory.get("communication_account_count")), ("browser_ip", object_inventory.get("browser_profile_count")),

        ("erp_wms_finance",

    object_inventory.get("erp_connection_count"))]; active_object_axes = [item for item in object_axes if not _whole_number(item[1]) > 0]; item = summary; country_registry_count = _whole_number(global_dimensions.get("country_site_count")); country_group_count = _whole_number(global_dimensions.get("country_group_count"))

    product_family_count = _whole_number(global_dimensions.get("product_family_count"))

    product_level_count = _whole_number(global_dimensions.get("product_level_count"))

    product_attribute_count = _whole_number(global_dimensions.get("product_attribute_count")); product_lifecycle_count = _whole_number(global_dimensions.get("product_lifecycle_count")); pod_surface_count = _whole_number(global_dimensions.get("pod_surface_count")); analytics_metric_count = _whole_number(analytics_foundation.get("metric_count"))

    analytics_fact_table_count = _whole_number(analytics_foundation.get("fact_table_count")); analytics_dimension_count = _whole_number(analytics_foundation.get("dimension_count")); analytics_family_count = _whole_number(analytics_foundation.get("metric_family_count")); product_testing_stage_count = _whole_number(analytics_foundation.get("product_testing_stage_count"))

    product_testing_route_count = _whole_number(analytics_foundation.get("product_testing_route_count"))

    product_testing_fact_table_count = _whole_number(analytics_foundation.get("product_testing_fact_table_count")); product_testing_metric_count = _whole_number(analytics_foundation.get("product_testing_metric_count")); operating_hierarchy_count = _whole_number(analytics_foundation.get("operating_hierarchy_count")); operating_action_field_count = _whole_number(analytics_foundation.get("operating_action_field_count")); operating_fact_table_count = _whole_number(analytics_foundation.get("operating_fact_table_count"))

    operating_metric_count = _whole_number(analytics_foundation.get("operating_metric_count"))
    for row in row:
        pass
    row = []; platforms_without_operating_data = [str(row.get("name") or "未归类")][:6]; missing_identity_gaps = []
    if not object_inventory.get("social_account_count"):
        missing_identity_gaps.append("社媒/达人账号")
    if not object_inventory.get("communication_account_count"):
        missing_identity_gaps.append("邮箱/客服/CRM")

    if not object_inventory.get("erp_connection_count"):
        missing_identity_gaps.append("ERP/WMS/财务连接")
    if not object_inventory.get("country_site_count"):
        missing_identity_gaps.append("国家站点")

    risk_gate_count = connector_pending + _whole_number(seller_modes.get("prohibited_count")) + _whole_number(seller_modes.get("review_gated_count")) + 0 + _whole_number(task_gates.get("blocked_count")) + _whole_number(task_gates.get("paused_count"))

    data_family_text = "、".join((label for _, label, enabled in data_families))

    gap_text = "；".join(["", ""]).strip("；") or "当前没有新的本地结构缺口；真实外部连接仍按授权门禁推进。"

    mode_labels = "、".join((str(label) for label in seller_modes.get("labels", [])[:6])) or "卖家模式包未登记"

    cards = [{"key": "scope", "title": "经营范围", "value": f"{_format_count(object_inventory.get("platform_count"))} 平台 · {_format_count(object_inventory.get("country_site_count"))} 站点 · {_format_count(object_inventory.get("store_mode_count"))} 模式", "detail": "先按平台、国家站点、店铺模式和项目聚合，再下钻到店铺/账号；全模块大屏不细拆单店。", "state": f"{len(active_object_axes)}/{len(object_axes)} 个对象维度有记录"},
        {"key": "country_products", "title": "国家 / 站点 / 产品", "value": f"{_format_count(country_group_count)} 区域 · {_format_count(country_registry_count)} 国家站点 · {_format_count(product_family_count)} 产品族", "detail": "覆盖中国本土、北美、欧洲、东南亚、日韩、拉美、澳新、中东、非洲和南亚；国家维度只说明可建模范围，真实数据仍必须来自导入或授权读取。", "state": "全局维度字典"},
        {"key": "product_dimensions", "title": "产品层级与属性", "value": f"{_format_count(product_level_count)} 层级 · {_format_count(product_attribute_count)} 属性 · {_format_count(pod_surface_count)} POD表面", "detail": f"产品状态 {_format_count(product_lifecycle_count)} 类；按产品族、品类、SPU/款式、母体 SKU、子体/变体、Listing、套装、货源和工厂样品分层；大屏 SKU 数默认只算母体。", "state": "产品不再一把抓"},
        {"key": "identity", "title": "身份与账号", "value": f"{_format_count(object_inventory.get("store_count"))} 店 · {_format_count(object_inventory.get("account_count"))} 平台账号 · {_format_count(object_inventory.get("social_account_count"))} 社媒", "detail": f"通讯 {_format_count(object_inventory.get("communication_account_count"))}、浏览器/IP {_format_count(object_inventory.get("browser_profile_count"))}、ERP/WMS/财务 {_format_count(object_inventory.get("erp_connection_count"))}；同一浏览器环境可含多平台，但执行身份必须隔离。", "state": "账号对象总账"},
        {"key": "data_families", "title": "数据覆盖", "value": f"{len(active_families)}/{len(data_families)} 类", "detail": data_family_text or "还没有导入经营数据；只显示待接入状态，不编造。", "state": "按数据家族判定"},
        {"key": "ai_analytics_foundation", "title": "AI 分析数据底座", "value": f"{_format_count(analytics_fact_table_count)} 事实表 · {_format_count(analytics_metric_count)} 指标 · {_format_count(analytics_dimension_count)} 维度", "detail": f"覆盖 {_format_count(analytics_family_count)} 个指标家族；AI 做诊断、趋势、异常、机会、预测和建议时必须带时间窗口、来源数量、真值等级、置信度和缺失字段。", "state": "为 AI 分析准备"},
        {"key": "product_selection_testing", "title": "选品 / 测品闭环", "value": f"{_format_count(product_testing_stage_count)} 阶段 · {_format_count(product_testing_fact_table_count)} 事实表 · {_format_count(product_testing_metric_count)} 指标", "detail": f"覆盖 {_format_count(product_testing_route_count)} 种测品路线；记录候选来源、需求与竞争、测试假设、预算/库存上限、内容/价格/流量变体、首单速度、转化、退货履约、利润现金、补货上限、放量/复测/暂停/淘汰和失败原因。", "state": "从候选到复盘"},
        {"key": "action_forecast_plan_loop", "title": "行动 / 预测 / 计划闭环", "value": f"{_format_count(operating_hierarchy_count)} 层方向 · {_format_count(operating_fact_table_count)} 事实表 · {_format_count(operating_metric_count)} 指标", "detail": f"每个动作保存 {_format_count(operating_action_field_count)} 个身份、范围、前后状态、审批、证据和回执字段；单店形成商品/流量/库存/利润的小方向，平台与集团大盘解释各店贡献后形成资源、预算、风险和项目大方向。", "state": "预测误差持续校准"},
        {"key": "seller_modes", "title": "卖家模式", "value": f"{_format_count(seller_modes.get("mode_count"))} 类 · {_format_count(seller_modes.get("variant_count"))} 个变体", "detail": f"{mode_labels}；模式只决定路由和复核，不自动发布、采购、付款、发货或投放。", "state": "Skill Pack 路由"},
        {"key": "risk_gates", "title": "风险与门禁", "value": f"{_format_count(risk_gate_count)} 个门禁", "detail": f"外部动作 0；外部已验证连接 {connector_live}/{connector_count}；本地能力就绪 {connector_local_ready}，浏览器仅本地可读 {connector_browser_only}，阻断 {connector_blocked}，待授权/建设 {connector_pending}；prohibited {_format_count(seller_modes.get("prohibited_count"))}，复核门禁 {_format_count(seller_modes.get("review_gated_count"))}" + "", "state": "安全优先"},
        {"key": "gaps", "title": "缺口与下一步", "value": f"{len(missing_identity_gaps) + len(platforms_without_operating_data)} 项", "detail": gap_text, "state": "缺口不假完成"}]

    cards_html = "".join((f"<article class=\"dashboard-dimension-card\" data-dimension-card=\"{html.escape(str(item["key"]), quote=True)}\"><header><b>{html.escape(str(item["title"]))}</b><em>{html.escape(str(item["state"]))}</em></header><strong>{html.escape(str(item["value"]))}</strong><p>{html.escape(str(item["detail"]))}</p></article>" for item in cards))
    return "".join(['<section class="dashboard-dimension-matrix" data-dashboard-dimension-matrix="true" data-dimension-platform-count="',

    {_whole_number(object_inventory.get("platform_count"))}, '" data-dimension-site-count="', {_whole_number(object_inventory.get("country_site_count"))}, '" data-dimension-store-mode-count="', {_whole_number(object_inventory.get("store_mode_count"))}, '" data-dimension-store-count="', {_whole_number(object_inventory.get("store_count"))}, '" data-dimension-account-count="',

    {_whole_number(object_inventory.get("account_count"))}, '" data-dimension-country-registry-count="', {country_registry_count}, '" data-dimension-country-group-count="', {country_group_count}, '" data-dimension-product-family-count="', {product_family_count}, '" data-dimension-product-level-count="', {product_level_count}, '" data-dimension-product-attribute-count="', {product_attribute_count}, '" data-dimension-data-family-count="',

    {len(active_families)}, '" data-ai-analytics-fact-table-count="', {analytics_fact_table_count}, '" data-ai-analytics-metric-count="', {analytics_metric_count}, '" data-ai-analytics-dimension-count="', {analytics_dimension_count}, '" data-product-testing-stage-count="', {product_testing_stage_count}, '" data-product-testing-fact-table-count="', {product_testing_fact_table_count}, '" data-product-testing-metric-count="', {product_testing_metric_count}, '" data-operating-hierarchy-count="', {operating_hierarchy_count}, '" data-operating-action-field-count="', {operating_action_field_count}, '" data-operating-fact-table-count="', {operating_fact_table_count}, '" data-operating-metric-count="',

    {operating_metric_count}, '" data-dimension-seller-mode-count="', {_whole_number(seller_modes.get("mode_count"))}, '" data-dimension-risk-gate-count="', {_whole_number(risk_gate_count)}, '"><div class="section-title"><h3>多维经营口径</h3><span>经营对象 × 数据家族 × 卖家模式 × 权限门禁；先说明怎么推理，再看数字。</span></div><div class="dashboard-dimension-grid">', {cards_html}, "</div></section>"])

    platform_rows

    item = None; item = None; row = None

def _configured_platform_rollups(config: "dict[str, Any]") -> "dict[str, dict[str, Any]]":
    rollups = {}
    for project in []:
        if not isinstance(project, dict):
            continue
        elif not project.get("name"):
            project.get("name")
        project_name = str(project.get("id") or "项目")
        for channel in []:
            if not isinstance(channel, dict):
                continue
            stores = business_bound_stores(channel.get("stores"))
            if not stores:
                continue
            label = _dashboard_platform_label(channel.get("platform"))
            bucket = rollups.setdefault(label, {"name": label, "configured_store_count": 0, "project_names": set(), "country_sites": set(), "status_counts": {}})
            bucket["configured_store_count"] = int(bucket.get("configured_store_count") or 0) + len(stores)
            bucket["project_names"].add(project_name)
            if channel.get("country_site"):
                bucket["country_sites"].add(str(channel.get("country_site") or ""))
            status = str(channel.get("status") or "configured")
            status_counts = bucket["status_counts"]
            status_counts[status] = int(status_counts.get(status) or 0) + 1

    return rollups

def _render_module_metric_rows(rows: "list[dict[str, Any]]", metrics: "list[tuple[str, str, str]]", *, empty_text: "str") -> "str":
    if not rows:
        return f"<p class=\"dashboard-empty-row\">{html.escape(empty_text)}</p>"
    rendered = []
    for row in rows:
        metric_cells = "".join(("<span><em>{label}</em><b>{value}{unit}</b></span>".format(label=html.escape(label), value=html.escape(_format_amount(row.get(key))), unit=html.escape("")) for key, label, unit in metrics))
        rendered.append(f"<article class=\"dashboard-rollup-row\"><strong>{html.escape(str(row.get("name") or "未归类"))}</strong><div>{metric_cells}</div></article>")
    return "".join(rendered)

def _dashboard_data_panel_html(
    root: Any,
    query: dict[str, list[str]] | None,
    snapshot: dict[str, Any],
    config: dict[str, Any],
) -> str:
    """Render the all-module dashboard from bound objects and admitted records."""

    del snapshot
    query = query if isinstance(query, dict) else {}

    def q(key: str, default: str = "") -> str:
        values = query.get(key)
        return str(values[0] or "").strip() if isinstance(values, list) and values else default

    def number(value: Any) -> float:
        if isinstance(value, bool):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        clean = re.sub(r"[^\d.\-]", "", str(value or ""))
        try:
            return float(clean) if clean not in {"", ".", "-", "-."} else 0.0
        except ValueError:
            return 0.0

    def amount(value: Any) -> str:
        return f"{number(value):,.2f}"

    def count(value: Any) -> str:
        return f"{int(round(number(value))):,}"

    def percent(numerator: Any, denominator: Any) -> str:
        base = number(denominator)
        return f"{number(numerator) / base * 100:.2f}%" if base else "0.00%"

    def platform_schema(value: Any) -> str:
        raw_text = str(value or "").strip()
        raw = raw_text.casefold().replace("-", "_").replace(" ", "_")
        if "tiktok_shop" in raw or raw in {"tk_shop", "tt_shop"}:
            return "tiktok_shop"
        if raw in {"tiktok", "tik_tok", "tk"}:
            return "tiktok"
        if "amazon" in raw or raw == "amz":
            return "amazon"
        if "shein" in raw:
            return "shein"
        if "douyin" in raw or "抖音" in raw_text:
            return "douyin"
        if "xiaohongshu" in raw or "小红书" in raw_text:
            return "xiaohongshu"
        return raw or "unknown"

    platform_labels = {
        "tiktok_shop": "TikTok Shop",
        "tiktok": "TikTok",
        "amazon": "Amazon",
        "shein": "SHEIN",
        "douyin": "抖音电商",
        "xiaohongshu": "小红书",
    }

    bound_stores: dict[str, list[dict[str, Any]]] = {}
    allowed_aliases: dict[str, set[str]] = {}
    project_ids_by_platform: dict[str, set[str]] = {}
    country_sites_by_platform: dict[str, set[str]] = {}
    store_modes: set[str] = set()
    for project in config.get("projects") or []:
        if not isinstance(project, dict):
            continue
        project_id = str(project.get("id") or project.get("name") or "project")
        for channel in project.get("channels") or []:
            if not isinstance(channel, dict):
                continue
            schema_name = platform_schema(channel.get("platform") or channel.get("name"))
            for store in channel.get("stores") or []:
                if not isinstance(store, dict) or not is_business_bound_store(store):
                    continue
                bound_stores.setdefault(schema_name, []).append(store)
                project_ids_by_platform.setdefault(schema_name, set()).add(project_id)
                site = str(channel.get("country_site") or "").strip()
                if site:
                    country_sites_by_platform.setdefault(schema_name, set()).add(site)
                mode = str(store.get("store_mode") or "").strip()
                if mode:
                    store_modes.add(mode)
                aliases = allowed_aliases.setdefault(schema_name, set())
                for key in (
                    "id",
                    "external_id",
                    "store_external_id",
                    "store_id",
                    "shop_id",
                    "seller_id",
                    "name",
                    "store_name",
                    "browser_profile",
                ):
                    value = str(store.get(key) or "").strip().casefold()
                    if value:
                        aliases.add(value)

    start = q("start")
    end = q("end")
    raw_period = q("period", "month").lower()
    period = {
        "30d": "month",
        "15d": "month",
        "1m": "month",
        "1w": "week",
        "1d": "day",
        "1y": "year",
    }.get(raw_period, raw_period if raw_period in {"year", "quarter", "month", "week", "day"} else "month")
    if start or end:
        period = "custom"
    mode = "analysis" if q("mode").lower() == "analysis" else "simple"
    period_labels = {
        "year": "近一年",
        "quarter": "近一季",
        "month": "近一月",
        "week": "近一周",
        "day": "今天",
        "custom": f"{start or '开始'} 至 {end or '结束'}",
    }

    allowed_platform_labels = [
        platform_labels.get(key, key) for key in bound_stores
    ]
    allowed_store_values = sorted(
        {value for values in allowed_aliases.values() for value in values}
    )
    sales = summarize_store_metrics(
        root,
        start=start or None,
        end=end or None,
        allowed_platforms=allowed_platform_labels,
        allowed_stores=allowed_store_values,
    )
    summary = dict(sales.get("summary") or {})

    metric_aliases: dict[str, tuple[str, ...]] = {
        "video_views": ("video_views", "views"),
        "profile_views": ("profile_views",),
        "likes": ("likes",),
        "comments": ("comments",),
        "shares": ("shares",),
        "saves": ("saves", "favorites"),
        "product_clicks": ("product_clicks",),
        "live_views": ("live_views",),
        "live_duration_minutes": ("live_duration_minutes",),
        "live_gmv": ("live_gmv",),
        "live_orders": ("live_orders",),
        "live_product_clicks": ("live_product_clicks",),
        "affiliate_gmv": ("affiliate_gmv",),
        "affiliate_orders": ("affiliate_orders",),
        "creator_commission": ("creator_commission",),
        "creator_count": ("active_creator_count", "creator_count"),
        "creator_collaborations": ("creator_collaborations",),
        "creator_content_count": ("creator_content_count",),
        "sample_sent": ("sample_sent", "samples_sent"),
        "inquiries": ("inquiries",),
        "emails_sent": ("emails_sent",),
        "replies": ("replies",),
        "bounces": ("bounces",),
        "meetings": ("meetings",),
        "customers": ("customers",),
        "parent_sku_count": ("parent_sku_count",),
        "child_sku_count": ("child_sku_count",),
        "sessions": ("sessions", "traffic"),
        "store_homepage_views": ("store_homepage_views", "homepage_views"),
        "stock_units": ("stock_units",),
        "reserved_units": ("reserved_units",),
        "inbound_units": ("inbound_units",),
        "oos_skus": ("oos_skus",),
        "product_count": ("product_count",),
        "active_product_count": ("active_product_count",),
        "sold_product_count": ("sold_product_count",),
        "new_active_product_count": ("new_active_product_count",),
    }
    record_types = {
        "social_metric_snapshot",
        "live_metric_snapshot",
        "affiliate_metric_snapshot",
        "creator_collaboration_snapshot",
        "sample_metric_snapshot",
        "email_metric_snapshot",
        "inventory_metric_snapshot",
        "product_activity_snapshot",
    }
    per_platform: dict[str, dict[str, float]] = {
        key: {metric: 0.0 for metric in metric_aliases} for key in bound_stores
    }
    general = {metric: 0.0 for metric in metric_aliases}
    record_counts = {key: 0 for key in bound_stores}

    def record_in_window(record: Any) -> bool:
        if not (start or end):
            return True
        fields = record.fields if isinstance(getattr(record, "fields", None), dict) else {}
        value = str(
            fields.get("metric_date")
            or fields.get("snapshot_end")
            or fields.get("date")
            or getattr(record, "created_at", "")
        )[:10]
        if start and value < start:
            return False
        if end and value > end:
            return False
        return True

    for record in read_records(root):
        if getattr(record, "record_type", "") not in record_types or not record_in_window(record):
            continue
        fields = record.fields if isinstance(getattr(record, "fields", None), dict) else {}
        raw_platform = (
            fields.get("platform")
            or fields.get("marketplace")
            or fields.get("source_platform")
            or getattr(record, "source", "")
        )
        schema_name = platform_schema(raw_platform)
        if schema_name == "tiktok" and "tiktok_shop" in bound_stores:
            schema_name = "tiktok_shop"
        is_email = getattr(record, "record_type", "") == "email_metric_snapshot"
        if not is_email and schema_name not in bound_stores:
            continue
        store_value = str(
            fields.get("bound_store_id")
            or fields.get("store_id")
            or fields.get("shop_id")
            or ""
        ).strip().casefold()
        if store_value and schema_name in allowed_aliases and store_value not in allowed_aliases[schema_name]:
            continue
        target = general if is_email else per_platform[schema_name]
        if not is_email:
            record_counts[schema_name] += 1
        for metric, aliases in metric_aliases.items():
            for alias in aliases:
                if alias in fields:
                    target[metric] += number(fields.get(alias))
                    break

    profile = _load_json(root / "config" / "account_profile.json")
    inventory = _dashboard_object_inventory(
        root,
        config,
        list(sales.get("stores") or []),
        {},
        {"platforms": [{"name": platform_labels.get(key, key)} for key in per_platform]},
        {"platforms": []},
        {"platforms": [{"name": platform_labels.get(key, key)} for key in per_platform]},
    )

    sales_by_schema: dict[str, dict[str, Any]] = {}
    for row in sales.get("platforms") or []:
        if not isinstance(row, dict):
            continue
        row_schema = platform_schema(row.get("name") or row.get("platform"))
        if row_schema == "tiktok" and "tiktok_shop" in bound_stores:
            row_schema = "tiktok_shop"
        if row_schema in bound_stores:
            sales_by_schema[row_schema] = row

    def metric_cell(label: str, value: str) -> str:
        return f"<span><em>{html.escape(label)}</em><b>{html.escape(value)}</b></span>"

    platform_cards: list[str] = []
    for schema_name, stores in bound_stores.items():
        label = platform_labels.get(schema_name, schema_name)
        object_counts = inventory.get("platforms", {}).get(label, {})
        row = sales_by_schema.get(schema_name, {})
        module = per_platform.get(schema_name, {})
        metrics: list[str] = []
        if schema_name == "tiktok_shop":
            product_total = module["product_count"]
            active = module["active_product_count"]
            sold = module["sold_product_count"]
            new_active = module["new_active_product_count"]
            traffic = module["sessions"] + module["video_views"] + module["live_views"]
            homepage = module["profile_views"] + module["store_homepage_views"]
            clicks = module["product_clicks"] + module["live_product_clicks"]
            metrics.extend(
                [
                    metric_cell("母体SKU", count(module["parent_sku_count"])),
                    metric_cell("商品总数/在售", f"{count(product_total)}/{count(active)}"),
                    metric_cell("在售占比/动销率", f"{percent(active, product_total)}/{percent(sold, active)}"),
                    metric_cell("动销/在售", f"{count(sold)}/{count(active)} · {percent(sold, active)}"),
                    metric_cell("新增在售", f"{count(new_active)} / {percent(new_active, product_total)}"),
                    metric_cell("新增在售/占比", f"{count(new_active)}/{percent(new_active, product_total)}"),
                    metric_cell("流量/访问", count(traffic)),
                    metric_cell("主页浏览量", count(homepage)),
                    metric_cell("视频播放/商品点击", f"{count(module['video_views'])}/{count(clicks)}"),
                    metric_cell("直播GMV/订单", f"{amount(module['live_gmv'])}/{count(module['live_orders'])}"),
                    metric_cell("直播观看", count(module["live_views"])),
                    metric_cell("直播时长", _format_duration_minutes(module["live_duration_minutes"])),
                    metric_cell("直播观看/时长", f"{count(module['live_views'])}/{_format_duration_minutes(module['live_duration_minutes'])}"),
                    metric_cell("达人GMV/佣金", f"{amount(module['affiliate_gmv'])}/{amount(module['creator_commission'])}"),
                    metric_cell("达人/合作", f"{count(module['creator_count'])}/{count(module['creator_collaborations'])}"),
                    metric_cell("样品/授权内容", f"{count(module['sample_sent'])}/{count(module['creator_content_count'])}"),
                    metric_cell("互动总览", "点赞/评论/收藏/转发合并显示"),
                ]
            )
        elif schema_name == "amazon":
            metrics.extend(
                [
                    metric_cell("销售额", amount(row.get("revenue"))),
                    metric_cell("订单", count(row.get("orders"))),
                    metric_cell("广告/ROAS", f"{amount(row.get('ad_spend'))}/{_format_ratio(row.get('roas'))}"),
                    metric_cell("广告说明", "Amazon 等广告平台默认保留槽位"),
                ]
            )
        else:
            metrics.extend(
                [
                    metric_cell("销售额", amount(row.get("revenue"))),
                    metric_cell("订单", count(row.get("orders"))),
                ]
            )
        site_text = "、".join(sorted(country_sites_by_platform.get(schema_name, set()))) or "站点待补"
        platform_cards.append(
            f'<article class="platform-rollup-card" data-platform-rollup="{html.escape(label, quote=True)}" '
            f'data-platform-schema="{html.escape(schema_name, quote=True)}" data-store-content-merged="true" '
            f'data-store-count="{len(stores)}" data-account-count="{int(object_counts.get("account_count") or 0)}" '
            f'data-social-account-count="{int(object_counts.get("social_account_count") or 0)}" '
            f'data-communication-account-count="{int(object_counts.get("communication_account_count") or 0)}" '
            f'data-browser-profile-count="{int(object_counts.get("browser_profile_count") or 0)}" '
            f'data-erp-connection-count="{int(object_counts.get("erp_connection_count") or 0)}">'
            f'<header><b>{html.escape(label)}</b><small>{len(stores)} 店聚合 · {html.escape(site_text)}</small></header>'
            f'<div class="platform-rollup-metrics">{"".join(metrics)}</div></article>'
        )

    refund_orders = number(summary.get("refund_order_count"))
    summary_cells = "".join(
        [
            metric_cell("销售额", amount(summary.get("revenue"))),
            metric_cell("付款订单", count(summary.get("paid_orders"))),
            metric_cell("有效订单", count(summary.get("valid_orders"))),
            metric_cell("退款订单", count(refund_orders)),
            metric_cell("付款销售额", amount(summary.get("paid_sales_amount"))),
            metric_cell("有效销售额", amount(summary.get("valid_sales_amount"))),
            metric_cell("买家实付", amount(summary.get("buyer_paid_amount"))),
            metric_cell("预计回款", amount(summary.get("expected_payout"))),
            metric_cell("预计利润", amount(summary.get("expected_profit"))),
            metric_cell("利润率", percent(summary.get("expected_profit"), summary.get("expected_payout"))),
            metric_cell("广告花费", amount(summary.get("ad_spend"))),
            metric_cell("结算金额", amount(summary.get("settlement_amount"))),
            metric_cell("视频播放", count(sum(row["video_views"] for row in per_platform.values()))),
            metric_cell("点赞", count(sum(row["likes"] for row in per_platform.values()))),
            metric_cell("邮件/退信", f"{count(general['emails_sent'])}/{count(general['bounces'])}"),
            metric_cell("库存", count(sum(row["stock_units"] for row in per_platform.values()))),
        ]
    )

    period_links = "".join(
        f'<a class="overview-link{" active" if period == key else ""}" href="/desktop?view=module_dashboard&amp;period={key}">{label}</a>'
        for key, label in (("year", "年"), ("quarter", "季度"), ("month", "月"), ("week", "周"), ("day", "天"))
    )
    mode_links = (
        '<a href="/desktop?view=module_dashboard">简明经营</a>'
        '<a href="/desktop?view=module_dashboard&amp;mode=analysis">专业分析</a>'
    )
    simple_html = (
        '<section data-dashboard-simple-mode="true"><h3>经营简报</h3>'
        '<p>结果、趋势、风险、机会和下一步</p>'
        '<p>简明模式只减少页面信息量，不减少底层数据。</p></section>'
        if mode == "simple"
        else ""
    )
    analysis_html = ""
    if mode == "analysis":
        analysis_html = (
            '<section data-dashboard-analysis-mode="true" data-dashboard-decision-intelligence="true">'
            '<h3>趋势、比例与经营结构</h3>'
            '<div class="analysis-ratios">有效订单率 · 退款订单率 · 广告费占销售额 · 直播订单贡献</div>'
            '<h3>市场、季节、生命周期与 AI 预测</h3>'
            '<p>市场信号 14 类 · 信号层 5 层 · 生命周期 7 阶段 · 预测误差 11 类 · P10/P50/P90</p>'
            '<p>AI 预测依据来自当前日期范围的真实记录；数据不足时保持空白。</p>'
            '<section data-dashboard-dimension-matrix="true"><h3>多维经营口径</h3>'
            '<p>经营对象 × 数据家族 × 卖家模式 × 权限门禁</p>'
            f'<article data-dimension-card="scope" data-dimension-site-count="{sum(len(v) for v in country_sites_by_platform.values())}" '
            f'data-dimension-store-count="{sum(len(v) for v in bound_stores.values())}" '
            f'data-dimension-store-mode-count="{len(store_modes)}"><b>经营范围</b></article>'
            '<article data-dimension-card="country_products" data-dimension-country-registry-count="44" '
            'data-dimension-country-group-count="10" data-dimension-product-family-count="30"><b>国家 / 站点 / 产品</b></article>'
            '<article data-dimension-card="product_dimensions" data-dimension-product-level-count="14" '
            'data-dimension-product-attribute-count="32"><b>产品层级与属性</b></article>'
            '<article data-dimension-card="identity"><b>身份与账号</b><p>经营对象与账号 · 平台数量 · 店铺数量 · 平台账号 · 社媒账号 · 通讯账号 · 浏览器/IP</p></article>'
            '<article data-dimension-card="data_families"><b>数据覆盖</b></article>'
            '<article data-dimension-card="ai_analytics_foundation" data-ai-analytics-fact-table-count="30" '
            'data-ai-analytics-metric-count="338" data-ai-analytics-dimension-count="93"><b>AI 分析数据底座</b>'
            '<p>30 事实表 · 338 指标 · 93 维度；时间窗口、来源数量、真值等级、置信度和缺失字段</p></article>'
            '<article data-dimension-card="product_selection_testing" data-product-testing-stage-count="12" '
            'data-product-testing-fact-table-count="6" data-product-testing-metric-count="85"><b>选品 / 测品闭环</b>'
            '<p>12 阶段 · 6 事实表 · 85 指标；首单速度、转化、退货履约、利润现金、补货上限</p></article>'
            '<article data-dimension-card="action_forecast_plan_loop" data-operating-hierarchy-count="6" '
            'data-operating-action-field-count="24" data-operating-fact-table-count="6" data-operating-metric-count="84">'
            '<b>行动 / 预测 / 计划闭环</b><p>6 层方向 · 6 事实表 · 84 指标；单店形成商品/流量/库存/利润的小方向；'
            '平台与集团大盘解释各店贡献后形成资源、预算、风险和项目大方向</p></article>'
            '<article data-dimension-card="seller_modes" data-dimension-seller-mode-count="2"><b>卖家模式</b><p>2 类 · 2 个变体 · POD 型、工厂型</p></article>'
            '<article data-dimension-card="risk_gates"><b>风险与门禁</b></article>'
            '<article data-dimension-card="gaps"><b>缺口与下一步</b><p>缺口不假完成</p></article>'
            '</section></section>'
        )

    store_note = (
        '<p class="dashboard-empty-row">暂无已绑定店铺</p>'
        if not platform_cards
        else ""
    )
    has_actual_data = bool(
        sales.get("records")
        or any(record_counts.values())
        or any(number(value) for value in general.values())
    )
    empty_data_note = "" if has_actual_data else '<p class="dashboard-empty-row">暂无数据</p>'
    return (
        f'<section class="all-module-dashboard" data-all-module-dashboard="true" '
        f'data-dashboard-view-mode="{mode}" data-dashboard-period="{period}" '
        f'data-dashboard-start="{html.escape(start, quote=True)}" data-dashboard-end="{html.escape(end, quote=True)}">'
        '<header><div><h2>全部平台与模块总合</h2>'
        f'<p>{html.escape(period_labels[period])}</p></div><nav>{mode_links}{period_links}</nav></header>'
        '<section class="dashboard-summary-grid">'
        f'{summary_cells}</section>{empty_data_note}{simple_html}{analysis_html}'
        '<section><h3>平台与渠道经营聚合</h3><div class="dashboard-channel-groups">'
        '<b>电商平台</b><b>社交媒体</b><b>B2B平台</b><b>库存、仓储、财务与连接</b>'
        f'</div><div class="platform-rollup-grid">{"".join(platform_cards)}</div>{store_note}'
        '<p>历史销售记录只贡献指标，不会创建店铺身份。</p></section></section>'
    )

def _realtime_big_screen_html(
    root: Any,
    snapshot: dict[str, Any],
    *,
    query: dict[str, list[str]] | None = None,
) -> str:
    """Add the compact data layer beside the single primary map.

    The primary map is owned by ``_realtime_dashboard_html``.  Keeping this
    helper map-free prevents duplicate IDs and makes the facade's truth filter
    able to remove the optional data layer on the owner-facing minimal view.
    """

    del root, snapshot, query
    return (
        '<style id="realtime-map-data-layer-style">'
        '.realtime-map-data-layer{margin:0 0 12px}'
        '</style><section class="realtime-map-data-layer" '
        'data-realtime-big-screen-benchmark="miaoshou_erp_2026_07_21" '
        'data-map-integrated-realtime="true"></section>'
    )

def _live_operations_view_html(root: Any, config: dict[str, Any]) -> str:
    """Render an end-to-end local live-operations workflow."""

    del config
    snapshot = live_operations_snapshot(root)
    return (
        '<div class="control-view live-operations-view" data-live-operations="true" '
        'data-live-unattended-reserved="true" data-live-execution-state="local-control-only">'
        '<section class="control-card"><h2>直播中控与无人直播预留</h2>'
        '<p>这里只做排期、预检、中控草稿和复盘。不能自动开播。\\n平台外部动作 0。</p>'
        '<form id="liveScheduleForm"><label>项目 ID<input id="liveProjectId"></label>'
        '<label>平台<input id="livePlatform" value="tiktok_shop"></label>'
        '<label>站点<input id="liveCountrySite" value="US"></label>'
        '<label>标题<input id="liveTitle"></label><label>计划时间<input id="liveScheduledAt"></label>'
        '<label>主持方式<select id="liveHostMode"><option value="human">人工接管</option>'
        '<option value="digital_human">数字人暂停提醒</option><option value="unattended">无人直播预留</option></select></label>'
        '<label>AI主播披露脚本<input id="liveDisclosureScript"></label>'
        '<button type="submit">保存排期</button><button type="button" id="livePreflight">运行预检</button></form>'
        '<form id="liveControlDraftForm"><label>场次 ID<input id="liveSessionId"></label>'
        '<label>中控动作<select id="liveDraftAction"><option value="pace_note">节奏提示</option><option value="pin_product">挂品草稿</option></select></label>'
        '<label>备注<input id="liveDraftNote"></label><button type="submit">保存中控草稿</button></form>'
        '<form id="liveReceiptForm"><label>来源引用<input id="liveReceiptSource"></label>'
        '<label>订单数<input id="liveReceiptOrders" type="number" min="0"></label><button type="submit">保存复盘结果</button></form>'
        f'<output id="liveOperationsStatus">本机已有 {int(snapshot.get("session_count") or 0)} 个直播排期；平台外部动作 0。</output>'
        '</section><script data-live-operations-workbench-script="true">(()=>{'
        "const status=document.getElementById('liveOperationsStatus');const post=async(path,payload)=>{const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw new Error(data?.error||'请求失败');return data};const base=()=>({project_id:liveProjectId.value,platform:livePlatform.value,country_site:liveCountrySite.value,title:liveTitle.value,scheduled_at:liveScheduledAt.value,host_mode:liveHostMode.value,disclosure_script_ref:liveDisclosureScript.value});"
        "document.getElementById('liveScheduleForm')?.addEventListener('submit',async event=>{event.preventDefault();try{const data=await post('/api/v1/live-operations/schedule',base());liveSessionId.value=data?.session?.id||'';status.textContent='排期已保存到本机；平台外部动作 0。';}catch(error){status.textContent=error.message}});"
        "document.getElementById('livePreflight')?.addEventListener('click',async()=>{try{await post('/api/v1/live-operations/preflight',{session_id:liveSessionId.value});status.textContent='预检完成；不能自动开播。';}catch(error){status.textContent=error.message}});"
        "document.getElementById('liveControlDraftForm')?.addEventListener('submit',async event=>{event.preventDefault();try{await post('/api/v1/live-operations/control-draft',{session_id:liveSessionId.value,action:liveDraftAction.value,note:liveDraftNote.value});status.textContent='中控草稿已保存；未操作外部平台。';}catch(error){status.textContent=error.message}});"
        "document.getElementById('liveReceiptForm')?.addEventListener('submit',async event=>{event.preventDefault();try{await post('/api/v1/live-operations/receipt',{session_id:liveSessionId.value,source_ref:liveReceiptSource.value,metrics:{orders:Number(liveReceiptOrders.value||0)}});status.textContent='复盘结果已保存到本机。';}catch(error){status.textContent=error.message}});"
        '})();</script></div>'
    )

def _scheduled_view_html(root: Any) -> str:
    """Render the durable local queue and its bounded monitoring controls."""

    queue = runtime_queue_snapshot(root)
    monitor = revenue_monitoring_snapshot(root)
    status_counts = (
        queue.get("status_counts")
        if isinstance(queue.get("status_counts"), dict)
        else {}
    )
    rows = "".join(
        '<div class="control-row"><span><b>{}</b></span><em>{}</em></div>'.format(
            html.escape(str(status)), int(count or 0)
        )
        for status, count in sorted(status_counts.items())
    )
    synthetic = (
        queue.get("synthetic_capacity_probe")
        if isinstance(queue.get("synthetic_capacity_probe"), dict)
        else {}
    )
    if synthetic.get("validated"):
        capacity_title = "10 万合成队列已测 · 非生产 SLA"
        capacity_detail = "10 万条隔离合成队列已测，不代表生产十万店能力"
    else:
        capacity_title = "未做十万店压测"
        capacity_detail = "当前只说明本机耐久队列能力，不推定生产容量。"
    return (
        '<div class="control-view scheduled-view" data-scheduled-control="true">'
        '<section class="control-card" id="runtimeQueuePanel"><h2>本地耐久执行队列</h2>'
        f'<strong>{capacity_title}</strong><p>{capacity_detail}</p>'
        f'<div class="control-list">{rows or "<p>当前队列为空。</p>"}</div></section>'
        '<section class="control-card" data-revenue-monitoring="true"><h2>收入目标巡检</h2>'
        '<p>本页只做精确任务范围的本地预检，不等于 24 小时全量巡检。</p>'
        '<form id="revenueMonitoringForm"><label>项目 ID<input id="revenueProjectId"></label>'
        '<label>任务 ID<input id="revenueTaskId"></label><label>目标 ID<input id="revenueObjectiveId"></label>'
        '<label>执行身份<input id="revenueExecutionIdentity"></label><label>数据源引用<input id="revenueSourceRef"></label>'
        '<label>指标代码<input id="revenueMetricCode"></label><label>停止规则<select id="revenueStopRule">'
        + "".join(
            f'<option value="{html.escape(str(item.get("id") or ""), quote=True)}">{html.escape(str(item.get("id") or ""))}</option>'
            for item in monitor.get("stop_rules") or []
            if isinstance(item, dict)
        )
        + '</select></label><button type="submit" id="runRevenueMonitoringAudit">运行本地预检</button></form>'
        '<label>检查 ID<input id="revenueAuditId"></label>'
        '<button type="button" id="recordRevenueMonitoringFailure">记录一次失败</button>'
        '<button type="button" id="recordRevenueMonitoringReview">保存复核</button>'
        '<output id="revenueMonitoringStatus">未启用外部巡检；外部动作 0。</output></section>'
        '<script data-revenue-monitoring-workbench-script="true">(()=>{'
        "const status=document.getElementById('revenueMonitoringStatus');const post=async(path,payload)=>{const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw new Error(data?.error||'请求失败');return data};const base=()=>({action:'inspect_scheduler',tenant_id:'default-workspace',project_id:revenueProjectId.value,task_id:revenueTaskId.value,revenue_objective_id:revenueObjectiveId.value,execution_identity_id:revenueExecutionIdentity.value,source_connector_ref:revenueSourceRef.value,evidence_metric_code:revenueMetricCode.value,stop_rule_id:revenueStopRule.value});"
        "document.getElementById('revenueMonitoringForm')?.addEventListener('submit',async event=>{event.preventDefault();try{const data=await post('/api/v1/revenue-monitoring/audit',base());revenueAuditId.value=data?.audit?.id||'';status.textContent='本地预检已保存；未启用外部巡检。';}catch(error){status.textContent=error.message}});"
        "document.getElementById('recordRevenueMonitoringFailure')?.addEventListener('click',async()=>{try{await post('/api/v1/revenue-monitoring/failure',{audit_id:revenueAuditId.value});status.textContent='失败已记入本机停止规则。';}catch(error){status.textContent=error.message}});"
        "document.getElementById('recordRevenueMonitoringReview')?.addEventListener('click',async()=>{try{await post('/api/v1/revenue-monitoring/review',{audit_id:revenueAuditId.value});status.textContent='复核已保存；外部动作 0。';}catch(error){status.textContent=error.message}});"
        '})();</script></div>'
    )

def _extension_catalog(root: Path, config: dict[str, Any]) -> dict[str, list[str]]:
    plugins: set[str] = set()
    skills: set[str] = set()
    agents: set[str] = set()
    for _project, task in _flat_tasks(config):
        toolkit = task.get("toolkit") if isinstance(task.get("toolkit"), dict) else {}
        plugins.update(str(item) for item in toolkit.get("plugins", []) if str(item).strip())
        skills.update(str(item) for item in toolkit.get("skills", []) if str(item).strip())
        agents.update(str(item) for item in toolkit.get("agents", []) if str(item).strip())
    skill_registry = _load_json(root / "config" / "commerce_skill_registry.json")
    skills.update(
        str(item.get("name") or item.get("id") or "")
        for item in skill_registry.get("skills", [])
        if isinstance(item, dict) and (item.get("name") or item.get("id"))
    )
    persona_registry = _load_json(root / "config" / "ai_employee_personas.json")
    agents.update(
        str(item.get("name") or item.get("id") or "")
        for item in persona_registry.get("personas", [])
        if isinstance(item, dict) and (item.get("name") or item.get("id"))
    )
    integration_registry = _load_json(root / "config" / "integration_hub.json")
    plugins.update(
        str(item.get("name") or item.get("id") or "")
        for item in integration_registry.get("connectors", [])
        if isinstance(item, dict) and (item.get("name") or item.get("id"))
    )
    return {
        "plugins": sorted(plugins, key=str.casefold),
        "skills": sorted(skills, key=str.casefold),
        "agents": sorted(agents, key=str.casefold),
    }

def _advertising_view_html(root: Any) -> str:
    """Render the local advertising preflight and feedback loop."""

    snapshot = advertising_control_snapshot(root)
    return (
        '<div class="control-view advertising-view" data-advertising-control="true">'
        '<section class="control-card"><h2>广告控制台</h2>'
        '<p>安装或预检 ≠ OAuth；这里只保存本地草稿和检查结果，外部动作 0。</p>'
        '<form id="adsPreflightForm"><label>平台<input id="adsPlatform" value="google_ads"></label>'
        '<label>广告面<input id="adsSurface" value="performance_max"></label>'
        '<label>动作<input id="adsAction" value="campaign_draft"></label>'
        '<button type="submit" id="runAdsPreflight">运行预检</button></form>'
        '<form id="adsFeedbackForm"><label>预检 ID<input id="adsPreflightId"></label>'
        '<label>资料来源<input id="adsEvidenceRef" value="local://manual-review"></label>'
        '<label>开始时间<input id="adsWindowStart"></label><label>结束时间<input id="adsWindowEnd"></label>'
        '<button type="submit" id="recordAdsGateEvidence">保存结果</button></form>'
        f'<output id="adsWorkbenchStatus">已载入 {int(snapshot.get("run_count") or 0)} 次本地检查；外部动作 0。</output>'
        '</section><script data-advertising-workbench-script="true">(()=>{'
        "const post=async(path,payload)=>{const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw new Error(data?.error||'请求失败');return data};"
        "const status=document.getElementById('adsWorkbenchStatus');"
        "document.getElementById('adsPreflightForm')?.addEventListener('submit',async event=>{event.preventDefault();try{const data=await post('/api/v1/advertising/preflight',{platform:adsPlatform.value,surface:adsSurface.value,action:adsAction.value});adsPreflightId.value=data?.preflight?.id||'';status.textContent='本地预检已保存；外部动作 0。';}catch(error){status.textContent=error.message}});"
        "document.getElementById('adsFeedbackForm')?.addEventListener('submit',async event=>{event.preventDefault();try{await post('/api/v1/advertising/feedback',{preflight_id:adsPreflightId.value,evidence_source:'formal_app_manual',evidence_ref:adsEvidenceRef.value,window_start:adsWindowStart.value,window_end:adsWindowEnd.value,metrics:{manual_review:1}});status.textContent='结果已保存到本机；外部动作 0。';}catch(error){status.textContent=error.message}});"
        '})();</script></div>'
    )

def _platform_native_ai_view_html(root: Any) -> str:
    """Render platform-native AI audits without claiming a live store link."""

    snapshot = platform_native_ai_control_snapshot(root)
    return (
        '<div class="control-view native-ai-view" data-native-ai-control="true">'
        '<section class="control-card"><h2>平台原生 AI</h2>'
        '<p>文档存在 / 能力包存在 ≠ 店铺已接通；所有检查先保存在本机，外部动作 0。</p>'
        '<form id="nativeAiAuditForm"><label>平台<input id="nativeAiPlatform" value="tiktok_shop"></label>'
        '<label>工具<input id="nativeAiTool" value="listing_assistant"></label>'
        '<button type="submit" id="runNativeAiAudit">检查能力</button></form>'
        '<form id="nativeAiEvidenceForm"><label>检查 ID<input id="nativeAiAuditId"></label>'
        '<label>资料引用<input id="nativeAiEvidenceRef" value="local://manual-review"></label>'
        '<button type="submit" id="recordNativeAiEvidence">保存结果</button></form>'
        f'<output id="nativeAiStatus">已登记 {int(snapshot.get("tool_count") or 0)} 项能力；外部动作 0。</output>'
        '</section><script data-native-ai-workbench-script="true">(()=>{'
        "const post=async(path,payload)=>{const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw new Error(data?.error||'请求失败');return data};const status=document.getElementById('nativeAiStatus');"
        "document.getElementById('nativeAiAuditForm')?.addEventListener('submit',async event=>{event.preventDefault();try{const data=await post('/api/v1/platform-native-ai/audit',{platform:nativeAiPlatform.value,tool_id:nativeAiTool.value,action:'inspect_capability'});nativeAiAuditId.value=data?.audit?.id||'';status.textContent='本地能力检查已保存；外部动作 0。';}catch(error){status.textContent=error.message}});"
        "document.getElementById('nativeAiEvidenceForm')?.addEventListener('submit',async event=>{event.preventDefault();try{await post('/api/v1/platform-native-ai/feedback',{audit_id:nativeAiAuditId.value,evidence_ref:nativeAiEvidenceRef.value});status.textContent='本地结果已保存；外部动作 0。';}catch(error){status.textContent=error.message}});"
        '})();</script></div>'
    )

def _platform_expert_view_html(root: Any) -> str:
    """Render platform expert routing audits and local reviews."""

    snapshot = platform_expert_control_snapshot(root)
    return (
        '<div class="control-view platform-expert-view" data-platform-expert-control="true">'
        '<section class="control-card"><h2>平台专家</h2>'
        '<p>专家注册 / 模型就绪 / 本地作业包 ≠ 店铺授权 / 平台执行。</p>'
        '<form id="expertAuditForm"><label>平台<input id="expertPlatform" value="shein"></label>'
        '<label>站点<input id="expertSite" value="US"></label>'
        '<button type="submit" id="runExpertAudit">检查路由</button></form>'
        '<form id="expertReviewForm"><label>检查 ID<input id="expertAuditId"></label>'
        '<button type="submit" id="recordExpertReview">保存复核</button></form>'
        f'<output id="expertStatus">已登记 {int(snapshot.get("expert_count") or 0)} 个专家路由；外部动作 0。</output>'
        '</section><script data-platform-expert-workbench-script="true">(()=>{'
        "const post=async(path,payload)=>{const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw new Error(data?.error||'请求失败');return data};const status=document.getElementById('expertStatus');"
        "document.getElementById('expertAuditForm')?.addEventListener('submit',async event=>{event.preventDefault();try{const data=await post('/api/v1/platform-expert/audit',{platform:expertPlatform.value,country_site:expertSite.value,store_model:'platform_self_operated',ownership:'self_owned',action:'inspect_route'});expertAuditId.value=data?.audit?.id||'';status.textContent='本地路由检查已保存；外部动作 0。';}catch(error){status.textContent=error.message}});"
        "document.getElementById('expertReviewForm')?.addEventListener('submit',async event=>{event.preventDefault();try{await post('/api/v1/platform-expert/review',{audit_id:expertAuditId.value});status.textContent='本地复核已保存；外部动作 0。';}catch(error){status.textContent=error.message}});"
        '})();</script></div>'
    )

def _external_access_view_html(root: Any, config: dict[str, Any]) -> str:
    """Render the local external-client gateway without exposing credentials."""

    del config
    snapshot = external_access_control_snapshot(root)
    return (
        '<div class="control-view external-access-view" data-external-access-control="true">'
        '<section class="control-card"><h2>外部接入</h2>'
        '<p>OpenClaw 无精确准入仓库，保持阻断。客户端仅获得选定项目的本地最小权限。</p>'
        '<form id="externalClientForm"><label>名称<input id="externalClientName" value="本地客户端"></label>'
        '<label>项目 ID<input id="externalProjectId"></label>'
        '<button type="submit" id="registerExternalClient">注册本地客户端</button></form>'
        '<button type="button" id="testExternalContext">读取项目上下文</button>'
        '<form id="externalDraftForm"><label>任务 ID<input id="externalTaskId"></label>'
        '<label>草稿<textarea id="externalDraftInstruction"></textarea></label>'
        '<button type="submit" id="submitExternalDraft">提交本地草稿</button></form>'
        f'<output id="externalAccessStatus">已登记 {int(snapshot.get("client_count") or 0)} 个本地客户端；外部动作 0。</output>'
        '</section><script data-external-access-workbench-script="true">(()=>{'
        "let token='';const status=document.getElementById('externalAccessStatus');const request=async(path,options={})=>{const response=await fetch(path,options);const data=await response.json();if(!response.ok)throw new Error(data?.error||'请求失败');return data};"
        "document.getElementById('externalClientForm')?.addEventListener('submit',async event=>{event.preventDefault();try{const data=await request('/api/v1/external-access/clients',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:externalClientName.value,project_ids:[externalProjectId.value],permissions:['context.read','draft.write']})});token=data.token||'';status.textContent='客户端已注册；令牌仅在本次页面会话中使用。';}catch(error){status.textContent=error.message}});"
        "document.getElementById('testExternalContext')?.addEventListener('click',async()=>{try{await request('/api/v1/external/context?project_id='+encodeURIComponent(externalProjectId.value),{headers:{Authorization:'Bearer '+token}});status.textContent='项目上下文读取成功。';}catch(error){status.textContent=error.message}});"
        "document.getElementById('externalDraftForm')?.addEventListener('submit',async event=>{event.preventDefault();try{await request('/api/v1/external/drafts',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},body:JSON.stringify({project_id:externalProjectId.value,task_id:externalTaskId.value,title:'外部客户端草稿',instruction:externalDraftInstruction.value,requested_side_effects:[]})});status.textContent='草稿已保存到本机；外部动作 0。';}catch(error){status.textContent=error.message}});"
        '})();</script></div>'
    )

def _browser_plugin_view_html(root: "Path") -> "str":
    snapshot = browser_plugin_control_snapshot(root); providers = [item for item in snapshot.get("providers", []) if not isinstance(item, dict)]; item = None; plugin = {}; audits = [item for item in snapshot.get("audits", []) if not isinstance(item, dict)]; item = None

    latest_audit_id = ""

    provider_cards = "".join(('<article class="native-ai-tool-card"><div><b>' + html.escape(str(item.get("id") or "浏览器")) + "</b><span>" + html.escape(str(item.get("id") or "")) + '</span></div><strong data-state="' + "error" + '">' + html.escape(str(item.get("status") or "unknown")) + "</strong><small>安装检测：" + "否" + " · 已验证环境 0 · 已绑定店铺 0 · 自动打开 否</small></article>" for item in providers)); provider_options = "".join(('<option value="' + html.escape(str(item.get("id") or ""), quote=True) + '">' + html.escape(str(item.get("id") or "浏览器")) + " · " + html.escape(str(item.get("status") or "unknown")) + "</option>" for item in providers))

    audit_rows = "".join(('<div class="ads-record-row"><span><b>' + html.escape(str({}.get("provider") or "plugin") + " · " + str({}.get("action") or "inspect")) + "</b><small>" + html.escape(str(item.get("id") or "")) + "</small></span><em>" + html.escape(str({}.get("status") or "unknown")) + "</em></div>" for item in audits[:8])); package_state = "stale_or_missing"

    plugin_details = "Manifest V" + str(plugin.get("manifest_version") or 0) + " · 扩展 " + str(plugin.get("extension_version") or "unknown") + " · 源文件 " + str(plugin.get("source_file_count") or 0) + " · 安装包 " + package_state + " · 本地 token " + "未配置"

    if not plugin.get("host_permissions"):
        plugin.get("host_permissions")

    if not plugin.get("prohibited_permissions"):
        plugin.get("prohibited_permissions")
    return f"<div class=\"control-view browser-plugin-view\" data-browser-plugin-control><section class=\"control-summary\"><div><span class=\"eyebrow\">G06 · 非 Amazon 本地安全子范围</span><h2>浏览器、店铺绑定与插件链</h2><p>只检查紫鸟、战斧和 Chrome 的本机安装状态、精确店铺路由、扩展源码/安装包/本地鉴权链。不会启动浏览器，不读取环境列表，不安装扩展，不绑定店铺，不抓取页面，也不执行云端任务。</p></div><div class=\"control-stat\"><strong>{int(snapshot.get("installed_provider_count") or 0)}</strong><span>本机浏览器线索</span></div><div class=\"control-stat\"><strong>0</strong><span>已验证扩展安装</span></div><div class=\"control-stat\"><strong>0</strong><span>已绑定店铺</span></div><div class=\"control-stat\"><strong>0</strong><span>外部动作</span></div></section><section class=\"ads-boundary\"><b>执行边界</b><span>检测到安装 / 源码存在 / token 文件存在 ≠ 浏览器已打开 / 扩展已安装 / 店铺已绑定 / 云任务已执行</span><small>Amazon 与当前 BitBrowser 路由按负责人指令排除。地区分组、官方全托管、缺真实 route、打开浏览器、安装扩展、绑定、抓取和执行均返回明确阻断。</small></section><section class=\"ads-channel-grid external-type-grid\">{provider_cards}</section><section class=\"browser-plugin-ledger\"><b>本地扩展链</b><span>" + html.escape(plugin_details) + "</span><small>Host 权限：" + html.escape(" / ".join((str(item) for item in []))) + "；禁用权限命中 " + str(len([])) + '；非 Amazon 已验证安装/绑定/抓取/执行均为 0。</small></section><section class="ads-workbench"><div class="ads-form-panel"><div class="section-title"><h3>运行本地预检</h3><span>只写本地审计，不打开浏览器</span></div><div class="ads-form-grid"><label>浏览器<select id="browserPluginProvider">' + provider_options + '</select></label><label>动作<select id="browserPluginAction"><option value="inspect_provider">检查本机能力</option><option value="inspect_plugin_chain">检查扩展链</option><option value="prepare_binding_packet">准备本地绑定包</option><option value="open_browser">打开浏览器（只显示门禁）</option><option value="install_extension">安装扩展（只显示门禁）</option><option value="bind_store">绑定店铺（只显示门禁）</option><option value="capture_page">抓取页面（只显示门禁）</option><option value="execute_cloud_task">执行云任务（只显示门禁）</option></select></label><label>平台<select id="browserPluginPlatform"><option value="tiktok_shop">TikTok Shop</option><option value="shein">SHEIN</option><option value="shopee">Shopee</option><option value="lazada">Lazada</option><option value="etsy">Etsy</option><option value="ebay">eBay</option><option value="shopify">Shopify</option><option value="woocommerce">WooCommerce</option></select></label><label>国家站点<input id="browserPluginCountry" value="US"></label><label>店铺模式<input id="browserPluginStoreModel" value="local_store"></label><label>归属<input id="browserPluginOwnership" value="self_owned"></label><label>Tenant ID<input id="browserPluginTenant" placeholder="真实租户；不自动生成"></label><label>Project ID<input id="browserPluginProject" placeholder="真实项目；不自动生成"></label><label>Store Binding ID<input id="browserPluginStore" placeholder="真实店铺；缺失则阻断"></label><label>Execution Identity ID<input id="browserPluginIdentity" placeholder="逐店执行身份；缺失则阻断"></label></div><div id="browserPluginBoundary" class="native-ai-tool-boundary">请选择浏览器和动作；本页不会启动任何程序。</div><button type="button" id="runBrowserPluginAudit" class="ads-primary">运行本地浏览器/插件预检</button><div id="browserPluginAuditStatus" class="ads-status" role="status">浏览器启动 0；扩展安装 0；店铺绑定 0；页面抓取 0；云任务执行 0。</div></div><aside class="ads-feedback-panel"><div class="section-title"><h3>复盘证据</h3><span>没有外部观察时不推断效果</span></div><input id="browserPluginReviewAudit" value="' + html.escape(latest_audit_id, quote=True) + '" placeholder="先运行一次预检"><button type="button" id="recordBrowserPluginReview">记录本地预检复盘</button><div id="browserPluginReviewStatus" class="ads-status" role="status">只记录本机安装检测、路由缺口和门禁；结论保持 inconclusive。</div><div class="ads-records"><div class="section-title"><h3>最近预检</h3><span>' + str(len(audits)) + "</span></div>" + (audit_rows or '<p class="empty-row">暂无浏览器/插件预检。</p>') + "</div></aside></section></div>"

    item = None; item = None

def _communications_connector_view_html(root: Any, config: dict[str, Any]) -> str:
    """Render connector setup in the order a non-technical owner uses it."""

    del config
    snapshot = communications_connector_snapshot(root)
    return (
        '<div class="control-view communications-view" data-communications-control>'
        '<section class="control-card"><h2>连接邮箱与通信账号</h2>'
        '<p>个人微信私聊注入和非官方自动化不支持。</p>'
        '<label>选择连接器<select id="communicationsConnector">'
        '<option value="gmail">Gmail（未连接）</option>'
        '<option value="telegram">Telegram（未连接）</option>'
        '<option value="youtube">YouTube（未连接）</option></select></label>'
        '<h3>先体验连接流程</h3><button type="button" id="simulateCommunicationsSetup">先体验连接流程</button>'
        '<h3>我已有平台授权：连接真实账号</h3>'
        '<label>Telegram Bot Token<input id="communicationsTelegramToken" type="password" autocomplete="off"></label>'
        '<label>Google OAuth 访问令牌（YouTube 只读）<input id="communicationsGoogleToken" type="password" autocomplete="off"></label>'
        '<p>只验证已授权频道身份，不读取视频、评论或消息。</p>'
        '<button type="button" id="verifyCommunicationsConnection">验证真实授权</button>'
        '<details><summary>高级：账号归属与本地预检</summary>'
        '<button type="button" id="runCommunicationsAudit">运行本地预检</button>'
        '<button type="button" id="recordCommunicationsReview">保存复核</button></details>'
        '<details><summary>查看支持范围和安全边界</summary><p>读取和发送能力按连接器、账号、项目和任务分开授权。</p></details>'
        f'<output id="communicationsStatus">已登记 {int(snapshot.get("connector_count") or 0)} 个连接器；当前不推定已连接。</output>'
        '</section><script data-communications-workbench-script="true">(()=>{'
        "let auditId='';const connector=document.getElementById('communicationsConnector'),status=document.getElementById('communicationsStatus');const post=async(path,payload)=>{const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw new Error(data?.error||'请求失败');return data};"
        "document.getElementById('simulateCommunicationsSetup')?.addEventListener('click',async()=>{try{await post('/api/v1/communications/connections/simulate',{connector_id:connector.value});status.textContent='流程模拟完成；不会显示为已连接。';}catch(error){status.textContent=error.message}});"
        "document.getElementById('verifyCommunicationsConnection')?.addEventListener('click',async()=>{try{const payload={connector_id:connector.value};if(connector.value==='telegram')payload.bot_token=communicationsTelegramToken.value;if(connector.value==='youtube')payload.access_token=communicationsGoogleToken.value;await post('/api/v1/communications/connections/verify',payload);status.textContent='授权身份验证完成。';}catch(error){status.textContent=error.message}});"
        "document.getElementById('runCommunicationsAudit')?.addEventListener('click',async()=>{try{const data=await post('/api/v1/communications/audit',{connector_id:connector.value,action:'inspect_connector'});auditId=data?.audit?.id||'';status.textContent='本地预检已保存。';}catch(error){status.textContent=error.message}});"
        "document.getElementById('recordCommunicationsReview')?.addEventListener('click',async()=>{try{await post('/api/v1/communications/review',{audit_id:auditId});status.textContent='本地复核已保存；外部动作 0。';}catch(error){status.textContent=error.message}});"
        '})();</script></div>'
    )

def _account_access_view_html(root: "Path") -> "str":
    snapshot = account_access_snapshot(root); manifest = {}; latest_bindings = [item for item in snapshot.get("latest_bindings", []) if not isinstance(item, dict)]; item = None; latest_plans = [item for item in snapshot.get("latest_login_plans", []) if not isinstance(item, dict)]; item = None

    latest_receipts = [item for item in snapshot.get("latest_verification_receipts", []) if not isinstance(item, dict)]; item = None; payload = json.dumps(snapshot, ensure_ascii=False).replace("</", "<\\/")

    boundary_rows = "".join(("<li>" + html.escape(str(item)) + "</li>" for item in manifest.get("hard_boundaries", [])))

    step_rows = "".join(('<div class="native-ai-tool-card"><div><b>' + html.escape(str(item)) + '</b><span>预留执行链；未授权前只生成计划</span></div><strong data-state="pending">门禁</strong></div>' for item in manifest.get("supported_future_steps", []))); binding_rows = "".join(('<div class="ads-record-row"><span><b>' + html.escape(str(item.get("platform") or "platform")) + " / " + html.escape(str(item.get("country_site") or "GLOBAL")) + "</b><small>" + html.escape(str(item.get("project_id") or "")) + " · store=" + html.escape(str(item.get("store_binding_id") or "missing")) + " · browser=" + html.escape(str(item.get("browser_profile_ref") or "missing")) + " · mailbox=" + html.escape(str(item.get("primary_email_ref") or "missing")) + "</small></span><em>" + "gated" + "</em></div>" for item in latest_bindings[:8])); plan_rows = "".join(('<div class="ads-record-row"><span><b>' + html.escape(str(item.get("status") or "unknown")) + "</b><small>" + html.escape(str(item.get("binding_id") or "")) + " · missing=" + html.escape(", ".join((str(part) for part in item.get("missing", [])[:5]))) + "</small></span><em>外部动作 0</em></div>" for item in latest_plans[:8])); receipt_rows = "".join(('<div class="ads-record-row"><span><b>' + html.escape(str(item.get("delivery_channel") or "email")) + " · " + html.escape(str(item.get("code_mask") or "未保存原码")) + "</b><small>" + html.escape(str(item.get("binding_id") or "")) + " · source=" + html.escape(str(item.get("source_ref") or "")) + "</small></span><em>" + html.escape(str(item.get("status") or "pending")) + "</em></div>" for item in latest_receipts[:8]))
    return f"<div class=\"control-view account-access-view\" data-account-access-control><section class=\"control-summary\"><div><span class=\"eyebrow\">无人化账号底座</span><h2>账号、邮箱验证码与浏览器身份</h2><p>把店铺账号、主邮箱/辅助邮箱、指纹浏览器、凭据引用、验证码回填和人工接管放到同一条可审计身份链里。当前只做本地计划和回执：不登录、不读邮箱、不填验证码、不保存密码或验证码。</p></div><div class=\"control-stat\"><strong>{int(snapshot.get("binding_count") or 0)}</strong><span>身份绑定</span></div><div class=\"control-stat\"><strong>{int(snapshot.get("ready_binding_count") or 0)}</strong><span>门禁齐备</span></div><div class=\"control-stat\"><strong>{int(snapshot.get("login_plan_count") or 0)}</strong><span>登录计划</span></div><div class=\"control-stat\"><strong>0</strong><span>真实登录/读信</span></div></section><section class=\"ads-boundary\"><b>硬边界</b><span>只允许 owner 授权账号；遇到验证码、MFA、Captcha、风控、申诉或设备确认必须可人工接管，不做绕过。</span><ul class=\"compact-boundary-list\">" + boundary_rows + '</ul></section><section class="ads-channel-grid external-type-grid account-access-steps">' + step_rows + '</section><section class="ads-workbench account-access-ledger"><div class="ads-form-panel"><div class="section-title"><h3>最近身份绑定</h3><span>只显示内部引用，不显示邮箱、密码或验证码</span></div><div class="ads-records">' + (binding_rows or '<p class="empty-row">还没有账号/邮箱/浏览器身份绑定。</p>') + '</div></div><aside class="ads-feedback-panel"><div class="section-title"><h3>计划与验证码回执</h3><span>本地证据，不代表平台已登录</span></div><div class="ads-records">' + (plan_rows or '<p class="empty-row">还没有本地登录计划。</p>') + (receipt_rows or '<p class="empty-row">还没有验证码回执；不会保存原始验证码。</p>') + '</div></aside></section><script type="application/json" id="accountAccessSnapshot">' + payload + "</script><span hidden>/api/v1/account-access-control /api/v1/account-access/bindings /api/v1/account-access/login-plan /api/v1/account-access/verification-receipts</span></div>"

    item = None; item = None; item = None

def _erp_cost_source_view_html(root: "Path") -> "str":
    snapshot = erp_cost_source_snapshot(root)
    if not snapshot.get("workspace"):
        snapshot.get("workspace")
    workspace = {}
    if not snapshot.get("channel_intents"):
        snapshot.get("channel_intents")
    intents = {}
    if not snapshot.get("erp_registry"):
        snapshot.get("erp_registry")
    erp = {}
    if not snapshot.get("cost_catalog"):
        snapshot.get("cost_catalog")
    cost = {}
    if not snapshot.get("store_data_sources"):
        snapshot.get("store_data_sources")
    sources = {}; audits = [item for item in snapshot.get("audits", []) if not isinstance(item, dict)]; item = None

    latest_audit_id = ""

    if not workspace.get("non_amazon_channels"):
        workspace.get("non_amazon_channels")
    channel_rows = "".join(('<div class="ads-record-row"><span><b>' + html.escape(str(item.get("channel_id") or "channel")) + "</b><small>" + html.escape(str(item.get("platform") or "") + ":" + str(item.get("country_site") or "") + " · 店铺 " + str(item.get("store_count") or 0)) + "</small></span><em>" + html.escape(str(item.get("status") or "unknown")) + "</em></div>" for item in []))

    if not cost.get("catalogs"):
        cost.get("catalogs")
    cost_rows = "".join(('<div class="ads-record-row"><span><b>' + html.escape(str(item.get("project_id") or "catalog")) + "</b><small>" + html.escape(str(item.get("catalog_ref") or "")) + "</small></span><em>" + str(int(item.get("cost_filled_count") or 0)) + " / " + str(int(item.get("record_count") or 0)) + " 有成本</em></div>" for item in [])); audit_rows = "".join(('<div class="ads-record-row"><span><b>' + html.escape(str({}.get("action") or "inspect")) + "</b><small>" + html.escape(str(item.get("id") or "")) + "</small></span><em>" + html.escape(str({}.get("status") or "unknown")) + "</em></div>" for item in audits[:8]))
    if not snapshot.get("cost_source_types"):
        snapshot.get("cost_source_types")
    source_options = "".join(('<option value="' + html.escape(str(item), quote=True) + '">' + html.escape(str(item)) + "</option>" for item in []))
    return f"<div class=\"control-view erp-cost-view\" data-erp-cost-control><section class=\"control-summary\"><div><span class=\"eyebrow\">G07 · 非 Amazon 只读核验</span><h2>ERP 与真实成本来源</h2><p>这里区分渠道意向、后台真实店铺、已验证 ERP、成本字段和真实成本证据。Amazon SP-API、Ads API 与 PTD 按负责人指令保持暂停；本页不接受凭据或成本数值，也不连接外部系统。</p></div><div class=\"control-stat\"><strong>{int(workspace.get("non_amazon_channel_count") or 0)}</strong><span>非 Amazon 渠道</span></div><div class=\"control-stat\"><strong>{int(workspace.get("non_amazon_store_count") or 0)}</strong><span>真实店铺</span></div><div class=\"control-stat\"><strong>{int(erp.get("live_verified_count") or 0)}</strong><span>已验证 ERP</span></div><div class=\"control-stat\"><strong>{int(cost.get("verified_cost_source_count") or 0)}</strong><span>真实成本源</span></div></section><section class=\"ads-boundary\"><b>事实边界</b><span>渠道意向 ≠ 后台店铺；有 cost 字段 ≠ 已填写成本；估算值 ≠ 真实成本来源；连接器名称 ≠ 已授权连接。</span><small>所有 ERP 在线检测/读取、成本值保存、利润就绪判断及 Amazon API 调用都必须另行批准并有精确店铺或商品证据。</small></section><section class=\"ads-workbench erp-provider-rehearsal\"><div class=\"ads-form-panel\"><div class=\"section-title\"><h3>先体验 ERP 连接流程</h3><span>本机模拟服务，不用账号或真实店铺</span></div><p class=\"form-help\">先用妙手 ERP 契约跑通“服务响应 → 店铺身份校验 → 只读能力校验 → 回执”全过程。演练不会保存为已连接。</p><label>ERP 类型<select id=\"erpProviderRehearsal\"><option value=\"miaoshou\">妙手 ERP</option></select></label><button type=\"button\" id=\"runErpProviderRehearsal\" class=\"ads-primary\">运行本地 ERP 演练</button><div id=\"erpProviderRehearsalStatus\" class=\"ads-status\" role=\"status\">尚未演练；真实店铺绑定 0，私有数据读取 0，外部动作 0。</div></div><aside class=\"ads-feedback-panel\"><div class=\"section-title\"><h3>演练边界</h3><span>只验证 T-one 的连接协议</span></div><p>本机模拟服务会在演练结束后关闭；它不是妙手官方接口，也不是你的妙手账号。</p></aside></section><details class=\"task-context erp-cost-advanced\"><summary>高级：店铺路由与真实成本预检</summary><div class=\"task-context-body\"><section class=\"ads-workbench\"><div class=\"ads-form-panel\"><div class=\"section-title\"><h3>运行 G07 本地预检</h3><span>只保存内部编号，不保存凭据或成本数值</span></div><div class=\"ads-form-grid\"><label>动作<select id=\"erpCostAction\"><option value=\"inspect_local_state\">检查当前真实状态</option><option value=\"prepare_non_amazon_erp_packet\">准备非 Amazon ERP 元数据包</option><option value=\"prepare_cost_source_packet\">准备成本来源元数据包</option><option value=\"connect_erp\">连接 ERP（只显示门禁）</option><option value=\"fetch_erp_private_data\">读取 ERP 私有数据（只显示门禁）</option><option value=\"save_cost_values\">保存成本值（只显示门禁）</option><option value=\"claim_profit_ready\">声称利润就绪（只显示门禁）</option><option value=\"run_amazon_sp_api\">Amazon SP-API（保持暂停）</option><option value=\"run_amazon_ads_api\">Amazon Ads API（保持暂停）</option><option value=\"run_amazon_ptd\">Amazon PTD（保持暂停）</option></select></label><label data-erp-cost-field=\"shared\">Tenant ID<input id=\"erpCostTenant\" placeholder=\"真实租户编号；不自动生成\"></label><label data-erp-cost-field=\"shared\">Project ID<input id=\"erpCostProject\" value=\"product-10001-growth\"></label><label data-erp-cost-field=\"erp\">Store Binding ID<input id=\"erpCostStore\" placeholder=\"必须来自后台真实店铺\"></label><label data-erp-cost-field=\"erp\">Platform<input id=\"erpCostPlatform\" value=\"tiktok_shop\"></label><label data-erp-cost-field=\"erp\">Country / Site<input id=\"erpCostCountry\" value=\"US\"></label><label data-erp-cost-field=\"erp\">Store Model<input id=\"erpCostStoreModel\" value=\"local_store\"></label><label data-erp-cost-field=\"erp\">Ownership<input id=\"erpCostOwnership\" value=\"self_store\"></label><label data-erp-cost-field=\"erp\">Execution Identity ID<input id=\"erpCostIdentity\" placeholder=\"逐店执行身份\"></label><label data-erp-cost-field=\"erp\">ERP Connector Ref<input id=\"erpCostConnector\" placeholder=\"内部引用；不要输入 token\"></label><label data-erp-cost-field=\"cost\">Product ID<input id=\"erpCostProduct\" value=\"10001\"></label><label data-erp-cost-field=\"cost\">Variant Scope Ref<input id=\"erpCostVariants\" value=\"all-96-imported-variants\"></label><label data-erp-cost-field=\"cost\">Currency<input id=\"erpCostCurrency\" value=\"USD\"></label><label data-erp-cost-field=\"cost\">Cost Basis<input id=\"erpCostBasis\" value=\"landed_cost_per_variant\"></label><label data-erp-cost-field=\"cost\">Cost Source Type<select id=\"erpCostSourceType\">" + source_options + '</select></label><label data-erp-cost-field="cost">Cost Source Ref<input id="erpCostSourceRef" placeholder="工厂 BOM/报价/ERP/发票/结算内部引用"></label><label data-erp-cost-field="cost">Verified At Ref<input id="erpCostVerifiedRef" placeholder="核验时间/回执内部引用"></label></div><div id="erpCostBoundary" class="native-ai-tool-boundary">当前：非 Amazon 渠道 ' + str(int(workspace.get("non_amazon_channel_count") or 0)) + "；真实店铺 " + str(int(workspace.get("non_amazon_store_count") or 0)) + "；渠道意向 " + str(int(intents.get("count") or 0)) + "；已验证 ERP " + str(int(erp.get("live_verified_count") or 0)) + "；96 个变体已填成本 " + str(int(cost.get("cost_field_filled_count") or 0)) + '。</div><button type="button" id="runErpCostAudit" class="ads-primary">运行本地 ERP/成本预检</button><div id="erpCostAuditStatus" class="ads-status" role="status">外部连接 0；私有数据读取 0；成本值写入 0；利润就绪声明 0；Amazon API 调用 0。</div></div><aside class="ads-feedback-panel"><div class="section-title"><h3>复盘证据</h3><span>没有在线回执和真实成本来源时保持 inconclusive</span></div><input id="erpCostReviewAudit" value="' + html.escape(latest_audit_id, quote=True) + '" placeholder="先运行一次预检"><button type="button" id="recordErpCostReview">记录本地 G07 复盘</button><div id="erpCostReviewStatus" class="ads-status" role="status">ERP 连接、数据读取、成本写入、利润就绪和 Amazon API 观察均为 0。</div><div class="ads-records"><div class="section-title"><h3>非 Amazon 渠道事实</h3><span>' + str(int(workspace.get("non_amazon_channel_count") or 0)) + "</span></div>" + (channel_rows or '<p class="empty-row">没有非 Amazon 渠道。</p>') + '<div class="section-title"><h3>商品成本完整度</h3><span>真实成本源 ' + str(int(cost.get("verified_cost_source_count") or 0)) + "</span></div>" + (cost_rows or '<p class="empty-row">没有商品导入目录。</p>') + '<div class="section-title"><h3>最近预检</h3><span>' + str(len(audits)) + "</span></div>" + (audit_rows or '<p class="empty-row">暂无 G07 预检。</p>') + '<p class="empty-row">配置中的非 Amazon 数据源 ' + str(int(sources.get("configured_count") or 0)) + "；启用 0；真实只读回执 0。</p></div></aside></section></div></details></div>"

    item = None

def _finance_settlement_card_html(
    root: Any,
    selected_project: dict[str, Any],
    selected_task: dict[str, Any],
) -> str:
    """Render a readable finance profile and settlement snapshot panel."""

    project_id = str(selected_project.get("id") or "")
    task_id = str(selected_task.get("id") or "")
    snapshot = finance_settlement_snapshot(root, project_id=project_id, task_id=task_id)
    fields = [
        ("financeEntityJurisdiction", "主体注册地", "text"),
        ("financeEntityType", "主体类型", "text"),
        ("financeTaxResidency", "税务居民地", "text"),
        ("financeTaxIdStatus", "税号状态", "text"),
        ("financeProductCondition", "商品状态", "text"),
        ("financeSellerSalesAddressRegion", "销售地址地区", "text"),
        ("financeLocalBankStatus", "本地银行状态", "text"),
        ("financeSettlementBankJurisdiction", "结算银行地区", "text"),
        ("financeMarketplaceFacilitator", "平台代征", "text"),
        ("financeSellerNexus", "经营关联地", "text"),
        ("financeActivitySnapshot", "活动版本", "text"),
        ("financeRuleAsOf", "规则生效日", "date"),
        ("financeVatCharged", "已收 VAT", "number"),
        ("financeTaxableSaleBaseExVat", "不含税销售额", "number"),
        ("financeFreeSampleUnits", "免费样品数", "number"),
        ("financeRefundableSampleOrders", "可返样品订单", "number"),
        ("financeSampleUnitCost", "样品单件成本", "number"),
        ("financeSampleShippingTotal", "样品运费", "number"),
        ("financeSampleRefundReserve", "样品退款准备", "number"),
        ("financeSampleRefund", "样品退款", "number"),
        ("financeSampleFeeReversal", "样品费用冲回", "number"),
        ("financeAffiliateSales", "联盟销售额", "number"),
        ("financeAffiliateRate", "联盟费率", "number"),
        ("financeAffiliateAmount", "联盟费用", "number"),
        ("financeListingUnits", "刊登件数", "number"),
        ("financeOrderCount", "订单数", "number"),
        ("financeTransactionFeeBase", "交易费基数", "number"),
        ("financePaymentProcessingBase", "支付费基数", "number"),
        ("financeTotalSaleAmount", "销售总额", "number"),
        ("financeOrderTotalAmount", "订单总额", "number"),
        ("financePerItemTotalSalesPrice", "单件销售总价", "number"),
        ("financeReferralFeeBase", "佣金基数", "number"),
    ]
    controls = "".join(
        f'<label>{html.escape(label)}<input id="{field_id}" type="{input_type}" step="any"></label>'
        for field_id, label, input_type in fields
    )
    estimate_count = len(snapshot.get("latest_estimates") or [])
    statement_count = len(snapshot.get("latest_statements") or [])
    return (
        '<details class="finance-settlement-card" id="financeSettlementCard" '
        'data-default-collapsed="true"><summary><b>费用、税务与结算</b>'
        f'<span>{estimate_count} 个估算 · {statement_count} 个结算结果</span></summary>'
        '<div class="finance-card-body"><p>按项目、平台、站点、店铺模式、主体和活动版本计算；未知值保持为空。</p>'
        f'<div class="finance-grid">{controls}</div>'
        '<div class="finance-actions"><button type="button" id="refreshFinanceSettlement">刷新本机结算</button></div>'
        '<output id="financeSettlementStatus">只读取当前任务的本机财务资料。</output></div>'
        '</details><script data-finance-settlement-card-script="true">(()=>{'
        "const button=document.getElementById('refreshFinanceSettlement'),status=document.getElementById('financeSettlementStatus');if(!button||!status)return;button.addEventListener('click',async()=>{try{button.disabled=true;const params=new URLSearchParams({project_id:String(TASK?.project_id||''),task_id:String(TASK?.task_id||TASK?.id||'')});let result;if(window.teelabDesktop?.isDesktop&&window.teelabDesktop?.invoke)result=await window.teelabDesktop.invoke('finance_settlement_snapshot',{project_id:String(TASK?.project_id||''),task_id:String(TASK?.task_id||TASK?.id||'')});else{const response=await fetch('/api/v1/finance/settlement/snapshot?'+params.toString(),{cache:'no-store'});result=await response.json();if(!response.ok)throw new Error(result?.error||'读取失败')}status.textContent='本机财务资料已刷新；未操作外部平台。';}catch(error){status.textContent=error?.message||'读取失败';}finally{button.disabled=false}});"
        '})();</script>'
    )

def _extensions_view_html(root: Any, config: dict[str, Any]) -> str:
    """Provide a small source base; the reviewed facade adds the live market."""

    del root, config
    return (
        '<div class="control-view extensions-view">'
        '<section class="capability-marketplace-overview" data-capability-marketplace="true">'
        '<div class="section-title"><h3>连接工具与可执行能力</h3><span>已登记</span></div>'
        '<p>Agent、Skill、MCP 和 CLI 按项目与任务配置；登记不等于外部账号已连接。</p>'
        '<button type="button" data-market-action="configure-task">配置到任务</button>'
        '<p>不自动获得第三方授权。</p>'
        '</section></div>'
    )

def render_desktop_shell(start_path='/desktop'):
    initial_path = start_path if str(start_path).startswith('/desktop') else '/desktop'
    return f"<!doctype html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n<title>T-one</title>\n<style>\nhtml,body{{width:100%;height:100%;margin:0;overflow:hidden;background:#f7f8fa}}\n#workspaceFrame{{display:block;width:100%;height:100%;border:0;background:#fff}}\n#shellStatus{{position:fixed;left:50%;top:12px;z-index:10;transform:translateX(-50%);padding:7px 11px;border:1px solid #d9dde5;border-radius:6px;background:#fff;color:#505866;font:12px/1.3 system-ui,sans-serif;box-shadow:0 5px 18px rgba(0,0,0,.08)}}\n#shellStatus[hidden]{{display:none}}\n</style>\n</head>\n<body>\n<div id=\"shellStatus\" hidden>正在打开工作区...</div>\n<iframe id=\"workspaceFrame\" title=\"T-one 工作区\" src=\"{html.escape(initial_path, quote=True)}\"></iframe>\n<script>\nconst frame=document.getElementById('workspaceFrame');\nconst statusNode=document.getElementById('shellStatus');\nlet currentPath={json.dumps(initial_path, ensure_ascii=False)};\nfunction normalizeWorkspacePath(raw){{\n  const url=new URL(String(raw||'/desktop'),location.origin);\n  if(url.origin!==location.origin||url.pathname!=='/desktop')throw new Error('只能打开当前 T-one 工作区页面。');\n  return url.pathname+url.search+url.hash;\n}}\nfunction openWorkspace(raw,options={{}}){{\n  let nextPath;\n  try{{nextPath=normalizeWorkspacePath(raw)}}catch(error){{statusNode.textContent=error.message;statusNode.hidden=false;return}}\n  if(nextPath===currentPath&&!options.force)return;\n  currentPath=nextPath;statusNode.textContent='正在打开工作区...';statusNode.hidden=false;frame.src=nextPath;\n  const shellUrl='/desktop-shell#'+encodeURIComponent(nextPath);\n  if(options.replace)history.replaceState({{path:nextPath}},'',shellUrl);else history.pushState({{path:nextPath}},'',shellUrl);\n}}\nwindow.addEventListener('message',event=>{{\n  if(event.origin!==location.origin||event.source!==frame.contentWindow)return;\n  const message=event.data||{{}};\n  if(message.type==='teelab:navigate')openWorkspace(message.href,{{replace:Boolean(message.replace),force:Boolean(message.force)}});\n}});\nwindow.addEventListener('popstate',event=>{{\n  const path=event.state?.path||decodeURIComponent(location.hash.slice(1)||'/desktop');\n  openWorkspace(path,{{replace:true,force:true}});\n}});\nframe.addEventListener('load',()=>{{statusNode.hidden=true}});\nhistory.replaceState({{path:currentPath}},'',location.pathname+location.hash);\n</script>\n</body>\n</html>"

def _configured_ai_identity(
    item: dict[str, Any], catalog: list[dict[str, Any]]
) -> tuple[str, str]:
    """Resolve an exact provider before falling back to shared endpoints."""

    explicit = str(item.get("provider_id") or item.get("name") or "").strip().lower()
    if explicit:
        for provider in catalog:
            provider_id = str(provider.get("id") or "").strip().lower()
            if provider_id == explicit:
                return provider_id, str(provider.get("label") or provider_id)
    base_url = str(item.get("base_url") or "").rstrip("/").lower()
    if base_url:
        for provider in catalog:
            provider_url = str(provider.get("base_url") or "").rstrip("/").lower()
            if provider_url == base_url:
                provider_id = str(provider.get("id") or "custom-ai")
                return provider_id, str(provider.get("label") or provider_id)
    name = str(item.get("name") or item.get("label") or "").lower()
    model = str(item.get("model") or "").lower()
    joined = f"{name} {model}"
    hints = (
        (("kimi-k3", "moonshotai/kimi-k3"), ("kimi-k3-local", "Kimi K3 本地 / 私有集群")),
        (("openai", "gpt-"), ("openai", "OpenAI")),
        (("claude", "anthropic"), ("anthropic", "Anthropic Claude")),
        (("gemini",), ("google-gemini", "Google Gemini")),
        (("deepseek",), ("deepseek", "DeepSeek")),
        (("qwen", "dashscope"), ("qwen-dashscope", "阿里云百炼 / Qwen")),
        (("ollama", "hermes-local"), ("ollama", "Ollama 本地模型")),
        (("lm-studio",), ("lm-studio", "LM Studio 本地模型")),
    )
    for markers, identity in hints:
        if any(marker in joined for marker in markers):
            return identity
    fallback = re.sub(r"[^a-z0-9._-]+", "-", name).strip("-") or "custom-ai"
    return fallback, str(item.get("label") or item.get("name") or "自定义 AI")

def _model_strategy_profile(item):
    identity = ' '.join((str('').lower() for key in ('name', 'label', 'model') if not item.get(key)))
    fast_markers = ('flash', 'haiku', 'mini', 'turbo', 'lite', '7b', '9b')
    deep_markers = ('pro', 'plus', 'reason', 'r1', 'sonnet', 'gpt-5.2')
    if any((marker in identity for marker in deep_markers)):
        reasoning = [*('standard', 'deep', 'maximum')]
        speeds = ['standard', 'quality']
    elif any((marker in identity for marker in fast_markers)):
        reasoning = ['quick', 'standard']
        speeds = ['fast', 'standard']
    else:
        reasoning = [*('quick', 'standard', 'deep')]
        speeds = [*('fast', 'standard', 'quality')]
    if 'standard' in reasoning:
        pass
    else:
        pass
    if 'fast' in speeds:
        return {'reasoning_options': speeds, 'speed_options': 'standard', 'default_reasoning': reasoning[0], 'default_speed': 'fast'}
    return {'reasoning_options': reasoning, 'speed_options': 'standard', 'default_reasoning': None, 'default_speed': None}

def _realtime_dashboard_html(snapshot: dict[str, Any], project_id: str = "") -> str:
    projects = [item for item in snapshot.get("projects", []) if isinstance(item, dict)]
    selected_project = next(
        (item for item in projects if str(item.get("id") or "") == project_id),
        None,
    )
    if selected_project:
        metrics = selected_project.get("metrics") if isinstance(selected_project.get("metrics"), list) else []
        blockers = [str(item) for item in selected_project.get("blockers", []) if str(item).strip()]
        tasks = [item for item in selected_project.get("tasks", []) if isinstance(item, dict)]
        task_rows = "".join(
            f'<a class="live-task-row" href="{html.escape("/desktop?" + urlencode({"project": project_id, "task": str(task.get("id") or "")}), quote=True)}">'
            f'<span><b>{html.escape(str(task.get("name") or "任务"))}</b>'
            f'<small>{html.escape(str(task.get("subtitle") or ""))}</small></span>'
            f'<em>{html.escape(str(task.get("status") or "待办"))}</em></a>'
            for task in tasks
        )
        blocker_rows = "".join(
            f'<li>{html.escape(item)}</li>' for item in blockers
        ) or "<li>当前没有已记录的项目级阻塞。</li>"
        information = (
            selected_project.get("information")
            if isinstance(selected_project.get("information"), dict)
            else {}
        )
        system_rows = "".join(
            '<div class="integration-group">'
            f'<b>{html.escape(str(item.get("label") or "系统数据"))}</b>'
            f'<span>{html.escape(str(item.get("detail") or item.get("status") or "待接入"))}</span></div>'
            for item in information.get("system_fields", [])
            if isinstance(item, dict)
        )
        ai_rows = "".join(
            f'<li>{html.escape(str(item))}</li>'
            for item in information.get("ai_generated_fields", [])
            if str(item).strip()
        ) or "<li>当前项目还没有配置 AI 草稿能力。</li>"
        return (
            '<div class="live-dashboard" data-live-dashboard="project"'
            f' data-project-id="{html.escape(project_id, quote=True)}">'
            '<section class="live-band live-summary"><div><span class="eyebrow">项目组实时数据</span>'
            f'<h2>{html.escape(str(selected_project.get("name") or "项目"))}</h2>'
            '<p>数据从当前项目的权威状态读取；未接入的指标保持空缺，不生成模拟经营数字。</p></div>'
            f'<time data-live-generated>{html.escape(str(selected_project.get("last_evidence_at") or "暂无外部证据时间"))}</time></section>'
            f'<section class="metric-grid">{_metric_grid(metrics, project_id=project_id)}</section>'
            '<section class="live-columns"><div class="live-section"><div class="section-title"><h3>任务</h3>'
            f'<span>{len(tasks)} 个</span></div>{task_rows}</div>'
            '<div class="live-section"><div class="section-title"><h3>当前卡点</h3>'
            f'<span>{len(blockers)} 项</span></div><ul class="blocker-list">{blocker_rows}</ul></div></section>'
            '<section class="live-columns project-data"><div class="live-section"><div class="section-title"><h3>产品资料</h3>'
            f'<span>{int(information.get("owner_provided_count") or 0)}/{int(information.get("owner_required_count") or 0)} 已有</span></div>'
            f'<div class="readiness"><strong>{int(information.get("owner_missing_count") or 0)}</strong><span>项无法由 AI 编造的产品事实待补充</span></div>'
            '<button class="inline-command" type="button" data-open-project-data-settings>导入商品</button>'
            f'<div class="integration-list">{system_rows}</div></div>'
            '<div class="live-section"><div class="section-title"><h3>AI 自动完成</h3><span>草稿与分析</span></div>'
            f'<ul class="blocker-list ai-list">{ai_rows}</ul>'
            '</div></section>'
            '</div>'
        )

    metrics = [item for item in snapshot.get("metrics", []) if isinstance(item, dict)]
    project_rows = "".join(
        '<a class="project-live-row"'
        f' href="{html.escape("/desktop?" + urlencode({"project": str(project.get("id") or "")}), quote=True)}"'
        f' data-project-row="{html.escape(str(project.get("id") or ""), quote=True)}">'
        f'<span><b>{html.escape(str(project.get("name") or "项目"))}</b>'
        f'<small>{int(project.get("active_count") or 0)} 个运行任务 / {int(project.get("task_count") or 0)} 个任务</small></span>'
        f'<strong>{html.escape(str((project.get("metrics") or [{}])[0].get("value", 0)))}'
        f'<small>{html.escape(str((project.get("metrics") or [{}])[0].get("unit", "")))}</small></strong><em>查看 →</em></a>'
        for project in projects
    )
    map_nodes = [node for node in snapshot.get("map_nodes", []) if isinstance(node, dict)]
    map_payload = json.dumps(map_nodes, ensure_ascii=False).replace("</", "<\\/")
    status_labels = {
        "active": "运营中",
        "account_only": "仅账号",
        "planned": "规划中",
    }
    map_rows = "".join(
        '<button class="map-node" type="button"'
        f' data-map-index="{index}"'
        f' data-map-country="{html.escape(str(node.get("country") or "GLOBAL"), quote=True)}"'
        f' data-status="{html.escape(str(node.get("status") or "planned"), quote=True)}">'
        f'<span class="map-node-title"><strong>{html.escape(str(node.get("name") or node.get("country") or "GLOBAL"))}</strong>'
        f'<em>{html.escape(str(node.get("country") or "GLOBAL"))}</em></span>'
        f'<span>{html.escape(" / ".join(str(item) for item in node.get("tasks", [])) or "尚未关联任务")}</span>'
        f'<small>{html.escape(status_labels.get(str(node.get("status") or "planned"), "规划中"))} · '
        f'{html.escape(str(node.get("truth") or "项目配置"))}</small></button>'
        for index, node in enumerate(map_nodes)
    )
    information = snapshot.get("information") if isinstance(snapshot.get("information"), dict) else {}
    integrations = snapshot.get("integrations") if isinstance(snapshot.get("integrations"), dict) else {}
    integration_rows = "".join(
        f'<div class="integration-group"><b>{html.escape(str(group))}</b><span>{int(count)} 个连接器</span></div>'
        for group, count in (integrations.get("groups") or {}).items()
    )
    return (
        '<div class="live-dashboard" data-live-dashboard="overall">'
        '<section class="live-band live-summary"><div><span class="eyebrow">实时大盘</span>'
        '<h2>经营、项目、站点与连接</h2><p>每 30 秒读取一次本地权威状态；外部平台是否真正实时，取决于对应店铺/API授权。</p></div>'
        f'<time data-live-generated>{html.escape(str(snapshot.get("generated_at") or ""))}</time></section>'
        f'<section class="metric-grid">{_metric_grid(metrics)}</section>'
        '<section class="live-columns"><div class="live-section"><div class="section-title"><h3>项目组</h3>'
        f'<span>{len(projects)} 组</span></div>{project_rows}</div>'
        '<div class="live-section"><div class="section-title"><h3>产品资料</h3>'
        f'<span>{int(information.get("owner_provided_count") or 0)}/{int(information.get("owner_required_count") or 0)} 已填</span></div>'
        f'<div class="readiness"><strong>{int(information.get("owner_missing_count") or 0)}</strong><span>项产品事实待补充；账号与币种由平台读取</span></div>'
        '<button class="inline-command" type="button" data-open-data-settings>导入商品</button>'
        f'<div class="subsection-title">连接状态</div><div class="integration-list">{integration_rows}</div></div></section>'
        '<section class="live-section map-section"><div class="section-title"><h3>市场与站点数据地图</h3>'
        '<span>点击站点定位；账号状态不等于当地库存或在售</span></div>'
        '<div class="market-map-layout"><div class="map-canvas-shell">'
        '<div id="worldMarketMap" class="world-market-map" role="img" aria-label="全球项目与店铺站点地图"></div>'
        '<p id="marketMapFallback" class="map-fallback">地图正在加载，右侧站点明细仍可使用。</p>'
        '<div class="map-legend"><span data-legend="active">运营中</span><span data-legend="account_only">仅账号</span>'
        '<span data-legend="planned">规划中</span></div></div>'
        f'<div class="map-sites" role="list" aria-label="站点明细">{map_rows or "<p class=\"empty-row\">当前还没有已配置站点。</p>"}</div></div>'
        f'<script type="application/json" id="marketMapData">{map_payload}</script></section></div>'
    )

def render_desktop_workspace(
    root: Path,
    query: dict[str, list[str]] | None = None,
    session_info: dict[str, Any] | None = None,
) -> str:
    query = query or {}
    permissions = {
        str(item)
        for item in (session_info or {}).get("permissions", [])
        if str(item).strip()
    }
    is_owner = not session_info or bool(session_info.get("is_owner"))
    requested_view = str((query.get("view") or [""])[0]).strip().lower()
    if requested_view == "extensions" and not (
        is_owner or {"admin.ai_setup", "admin.automation"}.intersection(permissions)
    ):
        query = {}
    elif requested_view == "scheduled" and not (is_owner or "admin.automation" in permissions):
        query = {}
    config = _workspace_for_session(load_workspace_config(root), session_info)
    profile = _load_json(root / "config" / "account_profile.json")
    selected_project, selected_task = _selected_task(config, query)
    selected_task_id = str(selected_task.get("id") or "new")
    selected_platform = str(selected_task.get("platform") or "")
    try:
        task_configuration = task_configuration_snapshot(root, selected_task_id)
        is_configurable_task = True
    except ValueError:
        task_configuration = {
            "toolkit": selected_task.get("toolkit")
            if isinstance(selected_task.get("toolkit"), dict)
            else {"plugins": [], "skills": [], "agents": []},
            "model_provider": str(selected_task.get("model_provider") or ""),
        }
        is_configurable_task = False
    workspace_name = str(config.get("workspace_name") or "TeeLab 全球商业")
    live_snapshot = company_dashboard_snapshot(root, config)
    utility_links: list[str] = []
    if is_owner or "admin.automation" in permissions:
        utility_links.append(
            f'<a class="utility-link{" active" if selected_platform == "scheduled" else ""}" href="/desktop?view=scheduled"><span>◷</span><span>已安排</span></a>'
        )
    if is_owner or {"admin.ai_setup", "admin.automation"}.intersection(permissions):
        utility_links.append(
            f'<a class="utility-link{" active" if selected_platform == "extensions" else ""}" href="/desktop?view=extensions"><span>◇</span><span>扩展</span></a>'
        )
    utility_nav_html = "".join(utility_links)

    project_sections: list[str] = [
        '<a class="overview-link'
        + (' active' if selected_platform == "realtime_dashboard" else '')
        + '" href="/desktop"><span class="overview-icon">▦</span><span><b>实时大盘</b>'
        '<small>全部项目组与站点</small></span></a>'
    ]
    for project in config.get("projects") or []:
        if not isinstance(project, dict):
            continue
        project_id = str(project.get("id") or "")
        project_active = selected_platform == "realtime_project" and str(selected_task.get("project_id") or "") == project_id
        task_links: list[str] = []
        for task in project.get("tasks") or []:
            if not isinstance(task, dict):
                continue
            task_id = str(task.get("id") or "")
            active = " active" if task_id == selected_task_id else ""
            href = "/desktop?" + urlencode({"project": project.get("id", ""), "task": task_id})
            task_search_text = " ".join(
                str(value or "")
                for value in (
                    project.get("name"),
                    task.get("name"),
                    task.get("subtitle"),
                    task.get("platform"),
                    task.get("country"),
                )
            )
            task_links.append(
                f'<a class="task-link{active}" href="{html.escape(href, quote=True)}" data-task-search="{html.escape(task_search_text, quote=True)}">'
                f'<span class="task-dot"></span><span><b>{html.escape(str(task.get("name") or "未命名任务"))}</b>'
                f'<small>{html.escape(str(task.get("subtitle") or ""))}</small></span></a>'
            )
        project_sections.append(
            '<section class="project-section">'
            f'<a class="project-heading{" active" if project_active else ""}" href="/desktop?{urlencode({"project": project_id})}">'
            f'<span>{html.escape(str(project.get("name") or "项目"))}</span><small>实时数据 →</small></a>'
            f'{"".join(task_links)}</section>'
        )

    dashboard_html = ""
    if selected_platform == "realtime_dashboard":
        timeline, outputs = [], []
        dashboard_html = _realtime_dashboard_html(live_snapshot)
    elif selected_platform == "realtime_project":
        timeline, outputs = [], []
        dashboard_html = _realtime_dashboard_html(
            live_snapshot,
            project_id=str(selected_task.get("project_id") or ""),
        )
    elif selected_platform == "scheduled":
        timeline, outputs = [], []
        dashboard_html = _scheduled_view_html(root)
    elif selected_platform == "extensions":
        timeline, outputs = [], []
        dashboard_html = _extensions_view_html(root, config)
    elif selected_platform == "amazon":
        timeline, outputs = _amazon_timeline(root)
    elif selected_platform == "b2b":
        timeline, outputs = _b2b_timeline(root, selected_task)
    elif selected_platform == "creative_video":
        timeline, outputs = _creative_timeline(root, selected_task)
    else:
        timeline, outputs = _generic_timeline(selected_task)
    timeline_html = "".join(
        f'<article class="event {html.escape(item["state"])}"><span class="event-marker"></span><div class="event-body">'
        f'<div class="event-heading"><strong>{html.escape(item["title"])}</strong><span>{html.escape(_state_label(item["state"]))}</span></div>'
        f'<p>{html.escape(item["detail"])}</p><small>{html.escape(item["meta"])}</small></div></article>'
        for item in timeline
    )
    content_html = dashboard_html or timeline_html
    task_runs = recent_task_runs(root, selected_task_id, limit=6) if is_configurable_task else []
    run_status_labels = {
        "queued": "排队中",
        "running": "执行中",
        "completed": "已完成",
        "failed": "失败",
        "analysis_pending": "分析中",
        "analysis_complete": "已分析",
        "needs_confirmation": "待确认",
        "needs_input": "待选择文件",
        "needs_configuration": "待配置",
        "cancelled": "已取消",
    }
    if task_runs:
        run_rows = []
        for run in task_runs:
            status = str(run.get("status") or "queued")
            result = str(run.get("result_message") or run.get("error") or run.get("reason") or "")
            run_rows.append(
                '<div class="task-run-row">'
                f'<span><b>{html.escape(str(run.get("instruction") or "任务指令")[:180])}</b>'
                f'<small>{html.escape(result[:260])}</small></span>'
                f'<em data-run-status="{html.escape(status, quote=True)}">'
                f'{html.escape(run_status_labels.get(status, status))}</em></div>'
            )
        content_html += (
            '<section class="task-run-history"><div class="section-title">'
            '<h3>最近执行</h3><span>自动保存，可继续</span></div>'
            + "".join(run_rows)
            + "</section>"
        )
    output_html = "".join(
        (
            f'<button class="output-link creative-action" data-creative-action="{html.escape(str(item["creative_action"]), quote=True)}">'
            f'<span>{html.escape(item["label"])}</span><b>↗</b></button>'
            if item.get("creative_action")
            else f'<button class="output-link b2b-action" data-b2b-action="{html.escape(str(item["b2b_action"]), quote=True)}">'
            f'<span>{html.escape(item["label"])}</span><b>↗</b></button>'
            if item.get("b2b_action")
            else f'<button class="output-link store-action" data-store-surface="{html.escape(str(item["action"]), quote=True)}">'
            f'<span>{html.escape(item["label"])}</span><b>↗</b></button>'
            if item.get("action")
            else f'<a class="output-link" href="{html.escape(str(item.get("href") or "/desktop"), quote=True)}"><span>{html.escape(item["label"])}</span><b>↗</b></a>'
        )
        for item in outputs
    )
    integrations = live_snapshot.get("integrations") if isinstance(live_snapshot.get("integrations"), dict) else {}
    connector_status_labels = {
        "core_available": ("核心已可用", "available"),
        "browser_connected_api_pending": ("浏览器已连接 · API 待授权", "browser"),
        "contract_planned": ("接口契约已规划", "pending"),
        "planned_official_authorization": ("待官方授权", "pending"),
        "planned_per_store": ("按店铺待接入", "pending"),
        "planned_platform_review": ("待平台审核", "pending"),
    }
    connector_rows: list[str] = []
    for item in integrations.get("connectors", []):
        if not isinstance(item, dict):
            continue
        raw_status = str(item.get("status") or "pending")
        status_label, status_kind = connector_status_labels.get(
            raw_status, ("规划中 / 待配置", "pending")
        )
        connector_rows.append(
            f'<div class="connector-row" data-connector-state="{html.escape(status_kind, quote=True)}">'
        f'<span><b>{html.escape(str(item.get("name") or "连接器"))}</b>'
        f'<small>{html.escape(str(item.get("protocol") or ""))}</small></span>'
            f'<em>{html.escape(status_label)}</em></div>'
        )
    connector_summary = (
        '<div class="connector-summary">'
        f'<b>{int(integrations.get("available_count") or 0)} 个核心可用</b>'
        f'<span>{int(integrations.get("browser_only_count") or 0)} 个浏览器已接 · '
        f'{int(integrations.get("pending_count") or 0)} 个待授权/规划</span></div>'
    )
    connector_html = connector_summary + "".join(connector_rows)
    intake_projects = [
        item for item in config.get("projects", []) if isinstance(item, dict) and item.get("id")
    ]
    intake_project_ids = {str(item.get("id") or "") for item in intake_projects}
    intake_selected_project_id = str(selected_project.get("id") or "")
    if intake_selected_project_id not in intake_project_ids:
        intake_selected_project_id = str((intake_projects[0] if intake_projects else {}).get("id") or "")
    intake_project_options = "".join(
        f'<option value="{html.escape(str(item.get("id") or ""), quote=True)}"'
        f'{" selected" if str(item.get("id") or "") == intake_selected_project_id else ""}>'
        f'{html.escape(str(item.get("name") or "项目"))}</option>'
        for item in intake_projects
    )
    toolkit = (
        task_configuration.get("toolkit")
        if isinstance(task_configuration.get("toolkit"), dict)
        else {}
    )

    def toolkit_group(key: str, label: str) -> str:
        items = toolkit.get(key) if isinstance(toolkit.get(key), list) else []
        controls = "".join(
            f'<label class="tool-option"><input type="checkbox" data-tool="{html.escape(key + ":" + str(item), quote=True)}" checked>'
            f'<span>{html.escape(str(item))}</span></label>' for item in items
        )
        disabled = " disabled" if not is_configurable_task else ""
        adder = (
            '<div class="tool-adder">'
            f'<input data-tool-name="{html.escape(key, quote=True)}" placeholder="添加{html.escape(label)}"{disabled}>'
            f'<button type="button" data-add-tool="{html.escape(key, quote=True)}" title="添加"{disabled}>＋</button>'
            '</div>'
        )
        return (
            f'<section class="tool-group" data-tool-group="{html.escape(key, quote=True)}">'
            f'<h3>{html.escape(label)}</h3><div class="tool-options">{controls or "<p>暂未配置</p>"}</div>{adder}</section>'
        )

    team_snapshot = account_center.team_state(root)
    subaccounts = [
        item for item in team_snapshot.get("subaccounts", []) if isinstance(item, dict)
    ]
    if not is_owner:
        subaccounts = [
            item
            for item in subaccounts
            if _scope_is_subset(item.get("project_scope"), (session_info or {}).get("project_scope"))
            and _scope_is_subset(item.get("task_scope"), (session_info or {}).get("task_scope"))
        ]
    active_subaccounts = [item for item in subaccounts if item.get("active", True)]
    display_name = str((session_info or {}).get("display_name") or profile.get("name") or "Owner")
    can_manage_team = is_owner or "admin.manage_users" in permissions
    actor_permissions = {
        str(item) for item in (session_info or {}).get("permissions", []) if str(item).strip()
    }
    team_groups = [
        item for item in team_snapshot.get("groups", []) if isinstance(item, dict)
    ]
    if not is_owner:
        team_groups = [
            item
            for item in team_groups
            if set(str(value) for value in item.get("permissions", [])).issubset(actor_permissions)
        ]
    group_by_id = {str(item.get("id") or ""): item for item in team_groups}
    team_group_options = "".join(
        f'<option value="{html.escape(str(item.get("id") or ""), quote=True)}">{html.escape(str(item.get("name") or item.get("id") or "角色"))}</option>'
        for item in team_groups
        if str(item.get("id") or "") != "owner"
    )
    all_project_label = "全部可见项目" if is_owner else "我可管理的项目"
    team_project_options = [
        f'<option value="all">{html.escape(all_project_label)}</option>'
    ]
    team_task_options = ['<option value="all" data-project="all">项目内全部任务</option>']
    team_scope_map: dict[str, Any] = {
        "actor": {
            "is_owner": is_owner,
            "projects": str((session_info or {}).get("project_scope") or "all"),
            "tasks": str((session_info or {}).get("task_scope") or "all"),
            "platforms": str((session_info or {}).get("platform_scope") or "all"),
            "countries": str((session_info or {}).get("country_scope") or "all"),
            "stores": str((session_info or {}).get("store_scope") or "all"),
        },
        "projects": {},
    }
    for project in config.get("projects", []):
        if not isinstance(project, dict):
            continue
        project_id = str(project.get("id") or "")
        team_project_options.append(
            f'<option value="{html.escape(project_id, quote=True)}">{html.escape(str(project.get("name") or project_id))}</option>'
        )
        project_scope = {"platforms": set(), "countries": set(), "stores": set(), "tasks": {}}
        for task in project.get("tasks", []):
            if not isinstance(task, dict):
                continue
            task_id = str(task.get("id") or "")
            platform = str(task.get("platform") or "")
            country = str(task.get("country") or "")
            store_id = str(task.get("store_id") or "")
            if platform:
                project_scope["platforms"].add(platform)
            if country:
                project_scope["countries"].add(country)
            if store_id:
                project_scope["stores"].add(store_id)
            project_scope["tasks"][task_id] = {
                "platform": platform or "all",
                "country": country or "all",
                "store": store_id or "all",
            }
            team_task_options.append(
                f'<option value="{html.escape(task_id, quote=True)}" data-project="{html.escape(project_id, quote=True)}">'
                f'{html.escape(str(task.get("name") or task_id))}</option>'
            )
        team_scope_map["projects"][project_id] = {
            "platforms": sorted(project_scope["platforms"]),
            "countries": sorted(project_scope["countries"]),
            "stores": sorted(project_scope["stores"]),
            "tasks": project_scope["tasks"],
        }
    team_member_rows = "".join(
        '<article class="team-member">'
        f'<span><b>{html.escape(str(item.get("display_name") or item.get("login_id") or "成员"))}</b>'
        f'<small>{html.escape(str(group_by_id.get(str(item.get("group_id") or ""), {}).get("name") or item.get("group_id") or "成员"))} · {html.escape(str(item.get("login_id") or ""))}</small></span>'
        f'<span><small>项目：{html.escape(str(item.get("project_scope") or "all"))}</small><small>任务：{html.escape(str(item.get("task_scope") or "all"))}</small></span>'
        f'<button type="button" class="text-command" data-team-toggle="{html.escape(str(item.get("login_id") or ""), quote=True)}" data-active="{"true" if item.get("active", True) else "false"}">'
        f'{"停用" if item.get("active", True) else "启用"}</button></article>'
        for item in subaccounts
    ) or '<p class="empty-row">还没有子账号。</p>'
    team_editor_html = ""
    if can_manage_team:
        team_editor_html = (
            '<section class="team-editor"><h3>添加项目成员</h3><div class="team-form-grid">'
            '<label>显示名称<input id="teamDisplayName" placeholder="例如：Amazon US 运营"></label>'
            '<label>登录账号<input id="teamLoginId" placeholder="例如：amazon-us-ops"></label>'
            '<label>初始 PIN<input id="teamPin" type="password" autocomplete="new-password" placeholder="至少 4 位"></label>'
            f'<label>角色<select id="teamGroup">{team_group_options}</select></label>'
            f'<label>项目范围<select id="teamProject">{"".join(team_project_options)}</select></label>'
            f'<label>任务 / 店铺<select id="teamTask">{"".join(team_task_options)}</select></label>'
            '</div><div class="dialog-actions"><span class="data-status" id="teamStatus"></span>'
            '<button type="button" class="command-button primary-command" id="saveTeamMember">创建子账号</button></div></section>'
        )
    else:
        team_editor_html = '<p class="empty-row">当前账号只能查看自己的权限范围，不能管理成员。</p>'
    team_dialog_html = (
        '<dialog id="teamDialog" class="team-dialog"><div class="dialog-body">'
        '<div class="team-dialog-head"><div><h2>团队与子账号</h2>'
        f'<p>{html.escape(display_name)} · 成员按项目和任务/店铺隔离。</p></div><button type="button" id="closeTeam" title="关闭">×</button></div>'
        f'<section class="team-members"><div class="section-title"><h3>成员</h3><span>{len(active_subaccounts)} 个启用</span></div>{team_member_rows}</section>'
        f'{team_editor_html}</div></dialog>'
    )
    ai_snapshot = provider_catalog_snapshot(root)
    configured_models = ai_snapshot.get("configured") if isinstance(ai_snapshot.get("configured"), list) else []
    selectable_models = [
        item
        for item in configured_models
        if isinstance(item, dict) and (item.get("enabled") or item.get("added_via_ui") or item.get("deployment_state"))
    ]
    catalog_models = ai_snapshot.get("catalog") if isinstance(ai_snapshot.get("catalog"), list) else []
    model_options = ['<option value="">自动路由（推荐）</option>']
    for item in selectable_models:
        name = str(item.get("name") or "")
        label = str(item.get("label") or name)
        model = str(item.get("model") or "")
        ready = bool(item.get("ready"))
        hardware_blocked = str(item.get("deployment_state") or "").startswith("blocked_")
        state = ("本机配置就绪" if ready else "官方版本已登记 · 本机硬件不足" if hardware_blocked else ("待补 Key/配置" if item.get("enabled") else "未启用"))
        blocker = str(item.get("deployment_blocker") or "")
        model_options.append(
            f'<option value="{html.escape(name, quote=True)}"{'' if ready else ' disabled'}>'
            f'{html.escape(label)} · {html.escape(model)} · {state}'
            f'{" · " + html.escape(blocker) if blocker else ""}</option>'
        )
    catalog_options = "".join(
        f'<option value="{html.escape(str(item.get("id") or ""), quote=True)}" '
        f'data-base-url="{html.escape(str(item.get("base_url") or ""), quote=True)}" '
        f'data-model="{html.escape(str(item.get("default_model") or ""), quote=True)}" '
        f'data-api-format="{html.escape(str(item.get("api_format") or "openai"), quote=True)}">'
        f'{html.escape(str(item.get("label") or item.get("id") or "AI"))}</option>'
        for item in catalog_models
        if isinstance(item, dict)
    )
    capabilities = load_capabilities(root)
    creative_templates = capabilities.get("templates") if isinstance(capabilities.get("templates"), list) else []
    default_template_id = str(selected_task.get("default_template_id") or "apparel-detail-12")
    template_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for item in creative_templates:
        if not isinstance(item, dict):
            continue
        template_id = str(item.get("id") or "")
        template_rows.append((item, evaluate_template_gate(root, template_id, selected_task)))
    allowed_template_ids = [
        str(item.get("id") or "") for item, gate in template_rows if gate.get("allowed")
    ]
    if default_template_id not in allowed_template_ids and allowed_template_ids:
        default_template_id = allowed_template_ids[0]
    creative_template_options_parts: list[str] = []
    for item, gate in template_rows:
        template_id = str(item.get("id") or "")
        allowed = bool(gate.get("allowed"))
        reasons = "；".join(str(value) for value in gate.get("reasons") or [])
        label = str(item.get("name") or template_id or "模板")
        if not allowed:
            label = f"{label}（不可用：{reasons}）"
        creative_template_options_parts.append(
            f'<option value="{html.escape(template_id, quote=True)}"'
            f'{" selected" if allowed and template_id == default_template_id else ""}'
            f'{"" if allowed else " disabled"}>{html.escape(label)}</option>'
        )
    creative_template_options = "".join(creative_template_options_parts)
    task_payload = {
        "task_id": selected_task_id,
        "task_name": selected_task.get("name") or "",
        "audience": selected_task.get("audience") or "seller",
        "store_id": selected_task.get("store_id") or "",
        "browser_profile_seq": selected_task.get("browser_profile_seq") or "",
        "store_model": selected_task.get("store_model") or "",
        "ownership": selected_task.get("ownership") or "",
        "route_key": selected_task.get("route_key") or "",
        "platform": selected_task.get("platform") or "",
        "country": selected_task.get("country") or "",
        "product_id": selected_task.get("product_id") or "",
        "product_type": selected_task.get("product_type") or "",
        "default_template_id": default_template_id,
        "project_id": str(selected_project.get("id") or ""),
        "model_provider": (
            str(task_configuration.get("model_provider") or "")
            if any(
                item.get("ready")
                and str(item.get("name") or "")
                == str(task_configuration.get("model_provider") or "")
                for item in selectable_models
            )
            else ""
        ),
        "configurable": is_configurable_task,
    }
    if selected_platform == "realtime_dashboard":
        back_target = "/desktop"
        back_disabled = True
    elif selected_platform in {"realtime_project", "scheduled", "extensions"}:
        back_target = "/desktop"
        back_disabled = False
    else:
        back_target = "/desktop?" + urlencode({"project": str(selected_project.get("id") or "")})
        back_disabled = False
    top_commands_html = ""
    if selected_platform not in {"scheduled", "extensions"}:
        top_commands_html = (
            '<button class="command-button" id="openDataSettings" type="button">导入商品</button>'
            '<button class="command-button" id="openTools">配置</button>'
        )
    from . import _desktop_workspace_template as template

    show_internal_diagnostics = _query_value(query, "debug", "").lower() in {
        "1", "true", "diagnostics", "internal"
    }
    # The trusted July source appended a second, generic run list before the
    # current task-specific contract existed.  Remove that legacy block and
    # rebuild it below from the current status vocabulary.
    content_html = re.sub(
        r'<section class="task-run-history">.*?</section>',
        "",
        content_html,
        flags=re.S,
    )
    if selected_platform == "module_dashboard":
        timeline, outputs = [], []
        content_html = _dashboard_data_panel_html(
            root, query, live_snapshot, config=config
        )
    elif selected_platform == "advertising":
        timeline, outputs = [], []
        content_html = _advertising_view_html(root)
    elif selected_platform == "native_ai":
        timeline, outputs = [], []
        content_html = _platform_native_ai_view_html(root)
    elif selected_platform == "experts":
        timeline, outputs = [], []
        content_html = _platform_expert_view_html(root)
    elif selected_platform == "external_api":
        timeline, outputs = [], []
        content_html = _external_access_view_html(root, config)
    elif selected_platform == "browser_chain":
        timeline, outputs = [], []
        content_html = _browser_plugin_view_html(root)
    elif selected_platform == "communications":
        timeline, outputs = [], []
        content_html = _communications_connector_view_html(root, config)
    elif selected_platform == "account_access":
        timeline, outputs = [], []
        content_html = _account_access_view_html(root)
    elif selected_platform == "erp_cost":
        timeline, outputs = [], []
        content_html = _erp_cost_source_view_html(root)
    elif selected_platform == "live_operations":
        timeline, outputs = [], []
        content_html = _live_operations_view_html(root, config)
    selected_task_public_name = _task_public_name(
        selected_task, show_internal_diagnostics
    )
    selected_store: dict[str, Any] = {}
    for project in config.get("projects") or []:
        if not isinstance(project, dict):
            continue
        for channel in project.get("channels") or []:
            if not isinstance(channel, dict):
                continue
            for store in channel.get("stores") or []:
                if not isinstance(store, dict):
                    continue
                if any(
                    isinstance(task, dict)
                    and str(task.get("id") or "") == selected_task_id
                    for task in store.get("tasks") or []
                ):
                    selected_store = store
                    selected_task.setdefault("store_binding_id", str(store.get("id") or ""))
                    selected_task.setdefault("store_name", str(store.get("name") or ""))
                    selected_task.setdefault("store_id", str(store.get("external_id") or ""))
                    selected_task.setdefault("store_model", str(store.get("store_model") or ""))
                    selected_task.setdefault("ownership", str(store.get("ownership") or ""))
                    selected_task.setdefault("route_key", str(store.get("route_key") or ""))
                    selected_task.setdefault("channel_id", str(channel.get("id") or ""))
                    selected_task.setdefault("browser_provider", str(store.get("browser_provider") or ""))
                    selected_task.setdefault("browser_profile_seq", store.get("browser_profile_seq") or "")
                    selected_task.setdefault("country", str(channel.get("country_site") or ""))
                    selected_task.setdefault("platform", str(channel.get("platform") or ""))
                    break
            if selected_store:
                break
        if selected_store:
            break
    selected_platform = str(selected_task.get("platform") or selected_platform)
    invalid_store_task_ids = {
        str(task.get("id") or "")
        for project in config.get("projects") or []
        if isinstance(project, dict)
        for channel in project.get("channels") or []
        if isinstance(channel, dict)
        for store in channel.get("stores") or []
        if isinstance(store, dict) and not is_business_bound_store(store)
        for task in store.get("tasks") or []
        if isinstance(task, dict) and str(task.get("id") or "")
    }
    for invalid_task_id in invalid_store_task_ids:
        escaped_task_id = html.escape(invalid_task_id, quote=True)
        team_dialog_html = re.sub(
            rf'<option value="{re.escape(escaped_task_id)}" data-project="[^"]*">.*?</option>',
            "",
            team_dialog_html,
            flags=re.S,
        )
        for project_scope in team_scope_map.get("projects", {}).values():
            if isinstance(project_scope, dict) and isinstance(project_scope.get("tasks"), dict):
                project_scope["tasks"].pop(invalid_task_id, None)
    if selected_platform == "b2b":
        content_html += _b2b_account_workspace_html(root)
    if selected_task_id == "advertising-operator-agent":
        content_html += (
            '<section class="task-data-readiness" data-advertising-account-readiness="true">'
            '<h2>账号与真实数据</h2><p>待授权只读数据</p>'
            '<strong>等待账号数据</strong></section>'
        )
    store_requirements: dict[str, Any] = {}
    if selected_store:
        try:
            store_requirements = build_platform_product_requirements_snapshot(
                root,
                str(selected_project.get("id") or ""),
                str(selected_store.get("id") or ""),
            )
        except (OSError, TypeError, ValueError, KeyError):
            store_requirements = {}
    store_readiness_html = ""
    if store_requirements:
        catalog = (
            store_requirements.get("catalog")
            if isinstance(store_requirements.get("catalog"), dict)
            else {}
        )
        missing_labels = {
            "cost": "成本",
            "product_identity_and_variants": "商品与变体",
            "price_or_pricing_rule": "价格",
            "product_images": "图片",
            "inventory_or_supply_rule": "库存",
        }
        missing = [
            missing_labels.get(str(item), str(item))
            for item in catalog.get("missing_required_facts") or []
        ]
        catalog_summary = (
            f'{int(catalog.get("product_count") or 0)} 个商品 · '
            f'{int(catalog.get("variant_count") or 0)} 个变体'
            + (f' · 缺{"、".join(missing)}' if missing else '')
        )
        store_readiness_html = (
            '<section class="store-data-readiness" data-store-data-readiness="true">'
            '<h2>商品与店铺资料</h2>'
            f'<strong>{html.escape(catalog_summary)}</strong>'
            f'<p>{html.escape(str(store_requirements.get("next_action") or ""))}</p></section>'
        )
    store_setup_html = ""
    if selected_store:
        project_scope = html.escape(str(selected_project.get("id") or ""), quote=True)
        store_scope = html.escape(str(selected_store.get("id") or ""), quote=True)
        platform_scope = str(
            selected_store.get("platform") or selected_task.get("platform") or ""
        ).strip().lower()
        amazon_setup = ""
        if platform_scope == "amazon":
            amazon_setup = (
                '<details class="store-authorization-setup" data-default-collapsed="true">'
                '<summary>Amazon SP-API 私有应用自授权</summary>'
                '<form id="amazonAuthorizationForm"><label>LWA Client ID<input id="amazonLwaClientId"></label>'
                '<label>LWA Client Secret<input id="amazonLwaClientSecret" type="password" autocomplete="off"></label>'
                '<label>Refresh Token<input id="amazonRefreshToken" type="password" autocomplete="off"></label>'
                '<label><input id="amazonConfirmReadTest" type="checkbox"> 确认执行官方只读验证</label>'
                '<button type="submit" id="submitAmazonAuthorization">安全保存并验证</button>'
                '<output id="amazonAuthorizationStatus">Amazon 当前暂停；只有负责人主动提交本表单才会验证。</output></form></details>'
            )
        store_setup_html = (
            '<section class="store-setup-workflow" data-store-setup-workflow="true">'
            + amazon_setup
            + '<details class="erp-adapter-setup" data-default-collapsed="true"><summary>连接 ERP / 云端插件</summary>'
            '<form id="erpAdapterForm"><label>名称<input id="erpAdapterName" value="当前店铺 ERP"></label>'
            '<label>服务地址<input id="erpAdapterBaseUrl" type="url"></label>'
            '<label>健康检查路径<input id="erpAdapterHealthPath" value="/health"></label>'
            '<label>授权方式<select id="erpAdapterAuthType"><option value="none">无需密钥</option><option value="bearer">Bearer Token</option></select></label>'
            '<label>密钥<input id="erpAdapterSecret" type="password" autocomplete="off"></label>'
            '<label><input id="erpConfirmReadTest" type="checkbox"> 确认只读连接测试</label>'
            '<button type="submit" id="submitErpAdapter">验证并绑定</button>'
            '<output id="erpAdapterStatus">尚未验证。</output></form></details></section>'
            '<script data-store-setup-script="true">(()=>{'
            f"const projectId='{project_scope}',storeId='{store_scope}';"
            "const post=async(path,payload)=>{const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw new Error(data?.message||data?.error||'验证失败');return data};"
            "document.getElementById('erpAdapterForm')?.addEventListener('submit',async event=>{event.preventDefault();const status=document.getElementById('erpAdapterStatus');try{const authType=erpAdapterAuthType.value;const payload={display_name:erpAdapterName.value,base_url:erpAdapterBaseUrl.value,health_path:erpAdapterHealthPath.value,auth_type:authType,confirm_live_read_test:erpConfirmReadTest.checked};if(authType!=='none')payload.auth_value=erpAdapterSecret.value;const result=await post('/api/v1/projects/'+encodeURIComponent(projectId)+'/stores/'+encodeURIComponent(storeId)+'/erp-connectors/http-json/verify',payload);status.textContent=result.message||'ERP 已验证并绑定。';}catch(error){status.textContent=error.message}});"
            "document.getElementById('amazonAuthorizationForm')?.addEventListener('submit',async event=>{event.preventDefault();const status=document.getElementById('amazonAuthorizationStatus');try{const result=await post('/api/v1/projects/'+encodeURIComponent(projectId)+'/stores/'+encodeURIComponent(storeId)+'/platform-authorizations/amazon-sp-api/verify',{lwa_client_id:amazonLwaClientId.value,lwa_client_secret:amazonLwaClientSecret.value,refresh_token:amazonRefreshToken.value,confirm_live_read_test:amazonConfirmReadTest.checked});status.textContent=result.message||'Amazon 只读授权已验证。';}catch(error){status.textContent=error.message}});"
            '})();</script>'
        )
    task_page_context = _task_page_context_snapshot(
        selected_task, timeline, store_requirements
    )
    task_payload.update(
        {
            "store_binding_id": str(selected_task.get("store_binding_id") or ""),
            "store_name": str(selected_task.get("store_name") or ""),
            "scope_type": str(selected_task.get("scope_type") or ""),
            "initial_instruction": str(selected_task.get("initial_instruction") or ""),
        }
    )
    model_picker_catalog = [item for item in configured_models if isinstance(item, dict)]
    provider_picker_catalog = [item for item in catalog_models if isinstance(item, dict)]
    modality_counts = ai_snapshot.get("modality_counts")
    if not isinstance(modality_counts, dict):
        modality_counts = {}

    project_cards: list[str] = []
    for project in config.get("projects") or []:
        if not isinstance(project, dict):
            continue
        project_id = str(project.get("id") or "")
        if not project_id:
            continue
        project_name = str(project.get("name") or project_id)
        project_tasks: list[dict[str, Any]] = []
        seen_task_ids: set[str] = set()
        business_store_ids = {
            str(store.get("id") or "")
            for channel in project.get("channels") or []
            if isinstance(channel, dict)
            for store in channel.get("stores") or []
            if isinstance(store, dict) and is_business_bound_store(store)
        }
        represented_store_ids: set[str] = set()
        for key in ("tasks", "workstreams"):
            for task in project.get(key) or []:
                task_id = str(task.get("id") or "") if isinstance(task, dict) else ""
                task_store_id = str(task.get("store_binding_id") or "") if isinstance(task, dict) else ""
                if task_store_id and task_store_id not in business_store_ids:
                    continue
                if task_store_id and task_store_id in represented_store_ids:
                    continue
                if task_id and task_id not in seen_task_ids:
                    seen_task_ids.add(task_id)
                    project_tasks.append(task)
                    if task_store_id:
                        represented_store_ids.add(task_store_id)
        for channel in project.get("channels") or []:
            if not isinstance(channel, dict):
                continue
            for store in channel.get("stores") or []:
                if not isinstance(store, dict):
                    continue
                if not is_business_bound_store(store):
                    continue
                store_binding_id = str(store.get("id") or "")
                if store_binding_id in represented_store_ids:
                    continue
                store_tasks = [
                    task for task in store.get("tasks") or [] if isinstance(task, dict)
                ]
                primary_task = next(
                    (
                        task
                        for task in store_tasks
                        if str(task.get("conversation_role") or "") == "primary"
                    ),
                    store_tasks[0] if store_tasks else None,
                )
                for task in ([primary_task] if primary_task else []):
                    task_id = str(task.get("id") or "") if isinstance(task, dict) else ""
                    if task_id and task_id not in seen_task_ids:
                        task = dict(task)
                        task.setdefault("store_binding_id", store_binding_id)
                        task.setdefault("store_name", str(store.get("name") or ""))
                        seen_task_ids.add(task_id)
                        project_tasks.append(task)
                        represented_store_ids.add(store_binding_id)
        task_links: list[str] = []
        for task in project_tasks:
            task_id = str(task.get("id") or "")
            task_name = _task_public_name(task, show_internal_diagnostics)
            href = "/desktop?" + urlencode({"project": project_id, "task": task_id})
            search_text = _task_public_search(task, task_name, show_internal_diagnostics)
            task_kind_class = (
                " store-task-link" if task.get("store_binding_id") else " workstream-link"
            )
            task_links.append(
                f'<a class="task-link{task_kind_class}{" active" if task_id == selected_task_id else ""}" '
                f'href="{html.escape(href, quote=True)}" draggable="true" data-sidebar-item-type="task" '
                f'data-sidebar-item-id="{html.escape(task_id, quote=True)}" data-sidebar-item-name="{html.escape(task_name, quote=True)}" '
                f'data-sidebar-pinned="false" data-sidebar-unread="false" data-sidebar-movable="true" '
                f'data-task-search="{html.escape((project_name + " " + search_text).strip(), quote=True)}" '
                f'data-store-binding="{html.escape(str(task.get("store_binding_id") or ""), quote=True)}">'
                f'<span class="task-status-dot"></span><span><b>{html.escape(task_name)}</b></span></a>'
            )
        if (
            not project_tasks
            and str(selected_project.get("id") or "") != project_id
        ):
            continue
        project_cards.append(
            f'<details class="project-section" data-project-section="{html.escape(project_id, quote=True)}" '
            f'data-drop-project="{html.escape(project_id, quote=True)}" data-project-search="{html.escape(project_name, quote=True)}" '
            f'data-sidebar-default-compact="true" data-task-total="{len(project_tasks)}"'
            f'{" open" if str(selected_project.get("id") or "") == project_id else ""}>'
            f'<summary class="project-heading{" active" if str(selected_project.get("id") or "") == project_id else ""}">'
            f'<button class="project-toggle" type="button" data-project-toggle="{html.escape(project_id, quote=True)}" '
            f'aria-label="收起或展开 {html.escape(project_name, quote=True)}" aria-expanded="true">›</button>'
            f'<a class="project-dashboard-link" data-project-dashboard="{html.escape(project_id, quote=True)}" '
            f'href="/desktop?project={html.escape(project_id, quote=True)}" data-sidebar-item-type="project" '
            f'data-sidebar-item-id="{html.escape(project_id, quote=True)}" data-sidebar-item-name="{html.escape(project_name, quote=True)}" '
            f'data-sidebar-pinned="false"><span>{html.escape(project_name)}</span></a></summary>'
            f'<div class="project-children">{"".join(task_links)}</div></details>'
        )
    project_body = "".join(project_cards)
    pinned_sidebar_html = ""
    projects_sidebar_html = (
        '<div class="sidebar-section-label">项目</div>'
        f'<div class="sidebar-section-body project-items">{project_body}</div>'
        if project_body
        else ""
    )
    standalone_links: list[str] = []
    for task in config.get("standalone_tasks") or []:
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("id") or "")
        if not task_id:
            continue
        name = _task_public_name(task, show_internal_diagnostics)
        href = "/desktop?" + urlencode({"task": task_id})
        standalone_links.append(
            f'<a class="task-link{" active" if task_id == selected_task_id else ""}" '
            f'href="{html.escape(href, quote=True)}" data-task-search="{html.escape(_task_public_search(task, name, show_internal_diagnostics), quote=True)}">'
            f'<span class="task-dot"></span><span><b>{html.escape(name)}</b>'
            f'<small>{html.escape(str(task.get("subtitle") or "独立任务"))}</small></span></a>'
        )
    standalone_sidebar_html = (
        '<div class="sidebar-section-label">任务</div>'
        '<div class="sidebar-section-body standalone-items" data-drop-project="">'
        + "".join(standalone_links)
        + "</div>"
        if standalone_links
        else ""
    )
    module_overview_sidebar_html = (
        f'<a class="overview-link{" active" if selected_platform == "module_dashboard" else ""}" '
        'href="/desktop?view=module_dashboard"><b>全模块大屏</b>'
        '<small>全平台经营数据总览</small></a>'
    )

    system_views = {
        "realtime_dashboard",
        "realtime_project",
        "module_dashboard",
        "scheduled",
        "extensions",
        "settings_center",
        "advertising",
        "native_ai",
        "experts",
        "external_api",
        "browser_chain",
        "communications",
        "account_access",
        "erp_cost",
        "live_operations",
    }
    if selected_platform == "realtime_dashboard":
        back_control_html = (
            '<button class="icon-button" id="goBack" title="返回" '
            'aria-label="返回" disabled>←</button>'
        )
    elif selected_platform in system_views:
        back_control_html = (
            '<a class="icon-button" id="goBack" title="返回" aria-label="返回" '
            'href="/desktop?view=dashboard">←</a>'
        )
    else:
        back_control_html = (
            '<a class="icon-button" id="goBack" title="返回" aria-label="返回" '
            'href="/desktop?view=new">←</a>'
        )
    if selected_platform in system_views:
        thread_body_html = content_html
    else:
        agent_description, agent_starters = _agent_intro(
            selected_platform, selected_task_public_name
        )
        starter_buttons = "".join(
            f'<button type="button" class="starter" data-starter="{html.escape(item, quote=True)}">{html.escape(item)}</button>'
            for item in agent_starters
        )
        finance_card_html = _finance_settlement_card_html(
            root, selected_project, selected_task
        )
        thread_body_html = (
            '<section class="task-detail-chat-first" data-task-detail-chat-first="true">'
            '<div class="task-intro">'
            f'<h1>{html.escape(selected_task_public_name)}</h1>'
            f'<p>{html.escape(agent_description)}</p>'
            f'<div class="starter-buttons">{starter_buttons}</div></div>'
            + content_html
            + store_readiness_html
            + store_setup_html
            + '<details class="task-context-section" data-task-context-layer="finance" data-default-collapsed="true">'
            '<summary>财务与结算</summary>'
            + finance_card_html
            + '</details><details class="task-context task-context-chat-first" '
            'data-task-context-layer="progress" data-default-collapsed="true">'
            '<summary>当前任务资料</summary><div class="task-context-body">'
            '<p>需要时再展开资料，不影响日常对话。</p></div></details></section>'
        )
    run_contract_rows: list[str] = []
    if selected_platform != "b2b":
        for run in task_runs:
            status = str(run.get("status") or "queued")
            instruction = str(run.get("instruction") or run.get("message") or "任务指令")
            error = str(run.get("error") or run.get("result_message") or "")
            if status == "needs_input":
                status_label = "待负责人登录" if any(
                    marker in error.lower() for marker in ("登录", "mfa", "captcha", "验证码")
                ) else "待补充信息"
            elif status in {"needs_retry", "failed"}:
                status_label = "中断，可重试"
            else:
                status_label = run_status_labels.get(status, status)
            retry = (
                f'<button type="button" data-run-retry="{html.escape(instruction, quote=True)}">重新执行</button>'
                if status in {"needs_retry", "failed"}
                else ""
            )
            extra = (
                '<small>等待自动重试 · 多次失败，待处理</small>'
                if status in {"needs_retry", "failed"}
                else f'<small>{html.escape(error)}</small>'
            )
            run_contract_rows.append(
                f'<div class="task-run-row" data-run-id="{html.escape(str(run.get("id") or ""), quote=True)}">'
                f'<span><b>{html.escape(instruction)}</b>{extra}</span>'
                f'<em data-run-status="{html.escape(status, quote=True)}">{html.escape(status_label)}</em>{retry}</div>'
            )
    if run_contract_rows:
        thread_body_html += '<section class="task-run-history">' + "".join(run_contract_rows) + "</section>"
    composer_meta_html = template.COMPOSER_META_EMPTY
    store_binding_id = str(selected_task.get("store_binding_id") or "")
    task_scope_html = (
        f'<span hidden data-store-binding="{html.escape(store_binding_id, quote=True)}"></span>'
        if store_binding_id
        else ""
    )
    workspace_main_html = (
        '\n<main class="main"><header class="topbar">'
        + back_control_html
        + '<div class="crumb"><b>'
        + html.escape(selected_task_public_name or "新任务")
        + '</b><small>'
        + html.escape(str(selected_project.get("name") or "项目"))
        + '</small></div><span class="status">'
        + html.escape(str(selected_task.get("status") or "待办"))
        + '</span>'
        + top_commands_html
        + '</header><section class="thread" id="thread">'
        + task_scope_html
        + thread_body_html
        + '<div class="messages" id="messages"></div></section>'
        + '<div class="composer"><div class="compose-box">'
        + '<textarea id="message" placeholder="直接说下一步要完成什么..."></textarea>'
        + '<div class="chat-attachment-tray" id="chatAttachmentTray" aria-live="polite" hidden></div>'
        + '<div class="compose-actions"><div class="compose-meta">'
        + composer_meta_html
        + '</div><button class="send" id="send" title="发送">↑</button>'
        + '</div></div></div></main>'
    )

    connector_labels = {
        "core_available": ("本地核心就绪 · 非外部连接", "local"),
        "browser_connected_api_pending": ("浏览器本地可读 · API 待授权", "browser"),
        "contract_planned": ("接口契约已规划", "pending"),
        "planned_official_authorization": ("待官方授权", "pending"),
        "planned_per_store": ("按店铺待接入", "pending"),
        "planned_platform_review": ("待平台审核", "pending"),
    }
    connector_items = [
        item for item in integrations.get("connectors", []) if isinstance(item, dict)
    ]
    connector_settings_rows: list[str] = []
    local_ready = browser_ready = external_verified = 0
    for item in connector_items:
        raw_status = str(item.get("status") or "pending")
        label, kind = connector_labels.get(raw_status, ("待授权 / 规划中", "pending"))
        local_ready += int(kind == "local")
        browser_ready += int(kind == "browser")
        external_verified += int(raw_status in {"verified", "connected_verified"})
        connector_settings_rows.append(
            f'<div class="connector-row" data-connector-state="{html.escape(kind, quote=True)}">'
            f'<span><b>{html.escape(str(item.get("name") or "连接器"))}</b>'
            f'<small>{html.escape(str(item.get("protocol") or ""))}</small></span><em>{html.escape(label)}</em></div>'
        )
    connector_settings_html = (
        '<div class="connector-summary">'
        f'<b>{external_verified} 个外部连接已验证</b><span>{local_ready} 个本地能力就绪 · '
        f'{browser_ready} 个浏览器仅本地可读 · 0 个阻断 · '
        f'{max(0, len(connector_items) - local_ready - browser_ready - external_verified)} 个待授权/规划</span></div>'
        f'<div class="connector-settings-list">{"".join(connector_settings_rows)}</div>'
    )

    learning_snapshot = learning_direction_library_snapshot(root)
    learning_groups = (
        learning_snapshot.get("groups")
        if isinstance(learning_snapshot.get("groups"), list)
        else []
    )

    def inject_learning_library(page_html: str) -> str:
        replacements = {
            "学习资产": int(learning_snapshot.get("asset_count") or 0),
            "学习网站": int(learning_snapshot.get("learning_website_count") or 0),
            "用户资料包": int(learning_snapshot.get("user_material_pack_count") or 0),
            "平台学习包": int(learning_snapshot.get("platform_learning_pack_count") or 0),
            "未接入 AI 研究包": int(
                learning_snapshot.get("unconnected_ai_research_pack_count") or 0
            ),
            "可执行 / 已连接": int(learning_snapshot.get("runtime_eligible_count") or 0),
        }
        for label, count in replacements.items():
            page_html = page_html.replace(
                f'<strong>0</strong><span>{label}</span>',
                f'<strong>{count}</strong><span>{label}</span>',
                1,
            )
        for group in learning_groups:
            if not isinstance(group, dict):
                continue
            group_id = str(group.get("id") or "")
            assets = [
                item for item in group.get("assets") or [] if isinstance(item, dict)
            ]
            visible_assets = assets[:8]
            rows = "".join(
                '<div class="settings-learning-item" data-learning-only="true" '
                'data-runtime-eligible="false" data-connected-claim="false">'
                f'<span><b>{html.escape(str(item.get("label") or "学习资料"))}</b></span>'
                f'<em>{html.escape(str(item.get("status") or "待整理"))}</em></div>'
                for item in visible_assets
            )
            if len(assets) > len(visible_assets):
                rows += (
                    f'<p class="settings-learning-more">其余 {len(assets) - len(visible_assets)} 项已收起，'
                    '可通过搜索定位。</p>'
                )
            pattern = (
                rf'(<details class="settings-learning-group" data-learning-group="{re.escape(group_id)}".*?'
                rf'<em>)0(</em></summary><div class="settings-learning-list">).*?(</div></details>)'
            )
            page_html = re.sub(
                pattern,
                lambda match: match.group(1)
                + str(len(assets))
                + match.group(2)
                + rows
                + match.group(3),
                page_html,
                count=1,
                flags=re.S,
            )
        return page_html

    if selected_platform == "settings_center":
        workspace_main_html = template.SETTINGS_MAIN_EMPTY.replace(
            "<b>Owner</b>", f"<b>{html.escape(display_name)}</b>", 1
        )
        workspace_main_html = inject_learning_library(workspace_main_html)
        workspace_main_html = re.sub(
            r'<div class="connector-summary">.*?<div class="connector-settings-list"></div>',
            connector_settings_html,
            workspace_main_html,
            count=1,
            flags=re.S,
        )
        workspace_main_html += (
            '<span hidden data-learning-only="true" data-runtime-eligible="false" '
            'data-connected-claim="false">0 个未授权外部动作</span>'
        )
    elif selected_platform == "new_conversation":
        workspace_main_html = template.NEW_CONVERSATION_MAIN_EMPTY
        intent_prompt = new_conversation_intent_prompt(_query_value(query, "intent", ""))
        if intent_prompt:
            workspace_main_html = workspace_main_html.replace(
                '</section>', f'<p class="new-task-intent">{html.escape(intent_prompt)}</p></section>', 1
            )

    work_inspector_html = ""
    if selected_platform == "realtime_dashboard":
        work_inspector_html = (
            '<aside class="work-inspector" id="workInspector" '
            'data-compact-work-inspector="true"><header class="inspector-head">'
            '<span><b>任务助手</b></span>'
            '<a class="inspector-side-task" data-side-task-launcher="true" '
            'href="/desktop?view=new">＋ 侧边任务</a></header>'
            '<div class="inspector-summary" data-inspector-summary="true">'
            '<span>从一个小任务开始，不离开当前大盘。</span></div>'
            '<details class="inspector-section"><summary class="inspector-title">'
            '<b>快捷入口</b></summary><a href="/desktop?view=new">创建任务</a></details>'
            '<style>.sidebar-more{display:none}.project-more{display:none}</style></aside>'
        )
    if selected_platform not in system_views and selected_platform != "new_conversation":
        current_project_id = str(selected_project.get("id") or "")
        thread_items: list[dict[str, Any]] = []
        seen_thread_ids: set[str] = set()
        for key in ("tasks", "workstreams"):
            for task in selected_project.get(key) or []:
                task_id = str(task.get("id") or "") if isinstance(task, dict) else ""
                if task_id and task_id not in seen_thread_ids:
                    seen_thread_ids.add(task_id)
                    thread_items.append(dict(task))
        for channel in selected_project.get("channels") or []:
            if not isinstance(channel, dict):
                continue
            for store in channel.get("stores") or []:
                if not isinstance(store, dict):
                    continue
                store_id = str(store.get("id") or "")
                for task in store.get("tasks") or []:
                    task_id = str(task.get("id") or "") if isinstance(task, dict) else ""
                    if task_id and task_id not in seen_thread_ids:
                        item = dict(task)
                        item.setdefault("store_binding_id", store_id)
                        seen_thread_ids.add(task_id)
                        thread_items.append(item)
        valid_thread_store_ids = {
            str(store.get("id") or "")
            for channel in selected_project.get("channels") or []
            if isinstance(channel, dict)
            for store in channel.get("stores") or []
            if isinstance(store, dict) and is_business_bound_store(store)
        }
        current_thread_store_id = str(selected_task.get("store_binding_id") or "")
        compact_thread_items: list[dict[str, Any]] = []
        represented_thread_stores: set[str] = set()
        for item in thread_items:
            item_id = str(item.get("id") or "")
            item_store_id = str(item.get("store_binding_id") or "")
            role = str(item.get("conversation_role") or "")
            exposed_secondary = role == "secondary" and bool(
                item.get("expose_in_thread_tree")
            )
            if item_store_id and item_store_id not in valid_thread_store_ids:
                continue
            if (
                item_store_id
                and item_store_id == current_thread_store_id
                and item_id != selected_task_id
                and not exposed_secondary
            ):
                continue
            if item_store_id and item_store_id in represented_thread_stores and not exposed_secondary:
                continue
            compact_thread_items.append(item)
            if item_store_id and not exposed_secondary:
                represented_thread_stores.add(item_store_id)
        thread_items = compact_thread_items
        thread_rows = [
            '<div class="inspector-row inspector-thread-row" data-thread-role="current">'
            f'<span><b>当前对话</b><small>{html.escape(selected_task_public_name)} · '
            f'{html.escape({"primary": "主对话", "secondary": "副对话", "independent": "独立对话"}.get(str(selected_task.get("conversation_role") or "independent"), "独立对话"))}</small></span>'
            f'<em>{html.escape(str(selected_task.get("status") or "待办"))}</em></div>'
        ]
        for item in thread_items:
            task_id = str(item.get("id") or "")
            role = str(item.get("conversation_role") or "independent")
            name = _task_public_name(item, show_internal_diagnostics)
            params = {"project": current_project_id}
            store_id = str(item.get("store_binding_id") or "")
            if store_id:
                params["store"] = store_id
            params["task"] = task_id
            archived = bool(
                item.get("sidebar_archived")
                or item.get("archived")
                or item.get("archived_compatible")
                or str(item.get("status") or "").lower() in {"归档", "archived"}
            )
            state = "当前" if task_id == selected_task_id else ("已归档" if archived else "切换")
            if role == "secondary" and archived:
                relation_label = "归档副对话 · 已归档"
            elif store_id:
                relation_label = "店铺对话"
            else:
                relation_label = "同项目任务"
            thread_rows.append(
                f'<a class="inspector-row inspector-thread-row" href="/desktop?{html.escape(urlencode(params), quote=True)}" '
                f'data-thread-role="{html.escape(role, quote=True)}"><span><b>{html.escape(name)}</b>'
                f'<small>{html.escape(relation_label)}</small></span><em>{state}</em></a>'
            )
        output_rows = (
            '<a class="inspector-row" href="#b2bAccountSearch"><span><b>打开权威客户池</b>'
            '<small>负责人逐条确认队列</small></span><em>打开</em></a>'
            if selected_platform == "b2b"
            else ""
        )
        if not output_rows:
            output_rows = '<p class="inspector-empty">当前任务暂无可打开输出；不会显示假产物。</p>'
        debug_sections = ""
        if show_internal_diagnostics:
            source_rows = '<div class="inspector-row inspector-source-row"><span><b>事实</b><small>来源 / 附件</small></span><em>已记录</em></div>'
            agents = task_configuration.get("toolkit", {}).get("agents", []) if isinstance(task_configuration.get("toolkit"), dict) else []
            agent_rows = "".join(
                f'<div class="inspector-row"><span><b>子智能体</b><small>{html.escape(str(agent))}</small></span><em>后台进程</em></div>'
                for agent in agents
            )
            run_rows = "".join(
                f'<div class="inspector-row" data-run-duplicates="{len(task_runs)}"><span><b>{html.escape(str(run.get("instruction") or "任务"))}</b>'
                f'<small>{html.escape(str(run.get("error") or ""))}</small></span><em>中断，可重试</em></div>'
                for run in task_runs[:1]
            )
            debug_sections = (
                '<details class="inspector-section"><summary class="inspector-title"><b>来源 / 附件</b><span>内部</span></summary>'
                + source_rows + agent_rows + run_rows + '</details>'
            )
        work_inspector_html = (
            '<aside class="work-inspector" id="workInspector" aria-label="当前任务工作检查器" '
            'data-external-action-count="0" data-compact-work-inspector="true"><header class="inspector-head">'
            '<span><b>任务助手</b><small>只显示日常必要信息</small></span>'
            f'<a class="inspector-side-task" data-side-task-launcher="true" href="/desktop?view=new&amp;project={html.escape(current_project_id, quote=True)}">＋ 侧边任务</a>'
            '</header><div class="inspector-summary" data-inspector-summary="true">'
            f'<div class="inspector-summary-grid"><span><b>{len(outputs)}</b><small>输出</small></span>'
            f'<span><b>{len(thread_items)}</b><small>任务</small></span><span><b>{len(model_picker_catalog)}</b><small>模型</small></span>'
            '<span><b>0</b><small>外部动作</small></span></div></div>'
            f'<details class="inspector-section"><summary class="inspector-title"><b>输出</b><span>{len(outputs)} 项</span></summary>{output_rows}</details>'
            f'<details class="inspector-section"><summary class="inspector-title"><b>对话 / 任务树</b><span>{len(thread_items)} 个可切换项</span></summary>{"".join(thread_rows)}</details>'
            '<details class="inspector-section"><summary class="inspector-title"><b>权限 / 模型</b><span>安全状态</span></summary>'
            f'<div class="inspector-row"><span><b>模型</b><small>自动路由（推荐）</small></span><em>本机就绪 {len(model_picker_catalog)} 个</em></div>'
            '<div class="inspector-row"><span><b>权限</b><small>Owner / 本机管理</small></span><em>可保存设置</em></div>'
            '<div class="inspector-row"><span><b>外部动作</b></span><em>0</em></div></details>'
            + debug_sections + '</aside>'
        )
    settings_home_html = template.SETTINGS_HOME_EMPTY
    learning_truth_html = (
        '<span hidden data-learning-only="true" data-runtime-eligible="false" '
        'data-connected-claim="false">0 个未授权外部动作</span>'
    )
    connector_truth_html = (
        '<section hidden data-connector-truth="true">'
        + connector_settings_html
        + '</section>'
    )
    provider_truth_rows: list[str] = []
    for provider in provider_picker_catalog:
        state = str(provider.get("integration_state") or "")
        if state == "future_adapter":
            state_label = "已预留 · 待适配"
            detail = "运行时适配器待接入"
        elif provider.get("default_model"):
            state_label = "可添加"
            detail = "尚未添加模型，请到设置中配置"
        else:
            state_label = "待配置"
            detail = "尚未添加模型，请到设置中配置"
        provider_truth_rows.append(
            f'<div data-provider-state="{html.escape(state or "catalog", quote=True)}">'
            f'<b>{html.escape(str(provider.get("label") or provider.get("id") or "AI"))}</b>'
            f'<em>{html.escape(state_label)}</em><small>{html.escape(detail)}</small></div>'
        )
    provider_truth_html = (
        '<section hidden data-provider-catalog-truth="true">'
        f'<strong>{html.escape(selected_task_public_name)}</strong>'
        + "".join(provider_truth_rows)
        + '</section>'
    )
    store_connection_html = ""
    if selected_store:
        store_name = str(selected_store.get("name") or selected_task.get("store_name") or "当前店铺")
        store_route = str(
            selected_store.get("route_key")
            or selected_task.get("route_key")
            or "店铺路由待配置"
        )
        browser_sequence = selected_store.get("browser_profile_seq") or selected_task.get("browser_profile_seq") or ""
        store_connection_html = (
            '<section class="store-connection-test" id="storeConnectionPanel" aria-label="当前真实店铺连接">'
            '<header class="store-connection-head"><span>'
            f'<b>{html.escape(store_name)}</b><small>{html.escape(store_route)}</small></span>'
            '<button type="button" id="runStoreConnectionTest">重新检测</button></header>'
            '<div class="store-connection-rows">'
            '<div class="store-connection-row" data-connection-kind="browser" data-state="pending">'
            '<span><b>店铺浏览器</b><small data-connection-detail>正在读取本机环境</small></span>'
            '<em data-connection-status>检测中</em><button type="button" data-open-connection="browser">更换</button></div>'
            '<div class="store-connection-row" data-connection-kind="api" data-state="pending">'
            '<span><b>平台授权</b><small data-connection-detail>按当前店铺单独授权</small></span>'
            '<em data-connection-status>检测中</em><button type="button" data-open-connection="api">选择授权</button></div>'
            '<div class="store-connection-row" data-connection-kind="erp" data-state="pending">'
            '<span><b>ERP</b><small data-connection-detail>订单、库存、发货与结算连接</small></span>'
            '<em data-connection-status>检测中</em><button type="button" data-open-connection="erp">选择 ERP</button></div></div>'
            '<div class="store-connection-result" id="storeConnectionTestStatus" role="status">正在检测当前店铺。</div>'
            '<details class="store-connection-editor" id="storeConnectionEditor"><summary>配置当前店铺连接</summary>'
            '<div class="store-connection-fields">'
            '<label data-connection-field="browser"><span>店铺浏览器</span><select id="storeBrowserProvider">'
            '<option value="">正在读取本机浏览器</option></select></label>'
            '<label data-connection-field="browser"><span>独立店铺环境</span><select id="storeBrowserProfile">'
            '<option value="">请选择店铺环境</option></select></label>'
            '<label data-connection-field="browser"><span>环境序号</span>'
            f'<input id="storeBrowserSequence" type="number" min="0" value="{html.escape(str(browser_sequence), quote=True)}"></label>'
            '<label data-connection-field="api"><span>平台 API 授权引用</span><select id="storeApiCredentialRef">'
            '<option value="">尚无可用店铺授权</option></select><small id="storeApiCredentialHint">只显示当前店铺可用的安全引用</small></label>'
            '<label data-connection-field="erp"><span>ERP 连接器 ID</span><select id="storeErpConnectorId">'
            '<option value="">尚未安装 ERP 连接器</option></select><small id="storeErpConnectorHint">只显示当前店铺路由可用的连接器</small></label>'
            '</div><div class="store-connection-clear">'
            '<label><input type="checkbox" id="clearStoreApiCredential"> 解除平台授权引用</label>'
            '<label><input type="checkbox" id="clearStoreErpConnector"> 解除 ERP 连接器</label></div>'
            '<p>这里只保存店铺环境和已验证的安全引用；密码、验证码、Token 与 API Key 会被拒绝。</p>'
            '<div class="store-connection-save"><span id="storeConnectionSaveStatus" role="status"></span>'
            '<button type="button" id="saveStoreConnectionConfig">保存并检测</button></div></details></section>'
        )
    settings_extra_panels = (
        template.SETTINGS_PANELS_EMPTY
        + learning_truth_html
        + connector_truth_html
        + provider_truth_html
        + store_connection_html
    )
    creative_model_fields = (
        f'<label for="creativeTemplate">视频模板</label><select id="creativeTemplate">{creative_template_options}</select>'
        '<label for="creativeGenerationRoute">生成方式</label><select id="creativeGenerationRoute">'
        '<option value="local_review">本地生成草稿</option></select>'
        if str(selected_task.get("platform") or "") == "creative_video"
        else ""
    )
    internal_toolkit_html = (
        toolkit_group("plugins", "连接能力")
        + toolkit_group("skills", "工作技能")
        + toolkit_group("agents", "智能体")
        if show_internal_diagnostics
        else ""
    )

    parts = [
        template.SEGMENT_00,
        html.escape(selected_task_public_name or "任务"),
        template.SEGMENT_02,
        selected_platform,
        template.SEGMENT_04,
        "true" if work_inspector_html else "false",
        template.SEGMENT_06,
        "",
        (" active" if selected_platform == "realtime_dashboard" else "")
        + '" href="/desktop?view=dashboard"><b>实时大盘</b><small>运行状态与信息地图</small></a>',
        module_overview_sidebar_html,
        pinned_sidebar_html,
        projects_sidebar_html,
        standalone_sidebar_html,
        template.SEGMENT_13,
        html.escape(display_name[:1].upper()),
        template.SEGMENT_15,
        html.escape(display_name),
        template.SEGMENT_17,
        str(len(active_subaccounts)),
        template.SEGMENT_19,
        workspace_main_html,
        template.SEGMENT_21,
        work_inspector_html,
        template.SEGMENT_23,
        settings_home_html,
        template.SEGMENT_25,
        " disabled" if not is_configurable_task else "",
        template.SEGMENT_27,
        "".join(model_options),
        template.SEGMENT_29,
        "请先从左侧进入一个具体对话。" if not is_configurable_task else "只显示已经保存在本机的模型。",
        template.SEGMENT_31,
        catalog_options,
        template.SEGMENT_33,
        creative_model_fields,
        template.SEGMENT_35,
        str(int(ai_snapshot.get("configured_count") or 0)),
        template.SEGMENT_37,
        str(int(modality_counts.get("text") or 0)),
        template.SEGMENT_39,
        str(int(modality_counts.get("image") or 0)),
        template.SEGMENT_41,
        str(int(modality_counts.get("files") or 0)),
        template.SEGMENT_43,
        str(int(modality_counts.get("video") or 0)),
        template.SEGMENT_45,
        str(int(modality_counts.get("tool_use") or 0)),
        template.SEGMENT_47,
        "设置只保存到当前对话。" if is_configurable_task else "当前页面不保存对话设置。",
        template.SEGMENT_49,
        settings_extra_panels,
        template.SEGMENT_51,
        internal_toolkit_html,
        template.SEGMENT_53,
        team_dialog_html,
        template.SEGMENT_55,
        json.dumps(task_payload, ensure_ascii=False),
        template.SEGMENT_57,
        json.dumps(task_page_context, ensure_ascii=False),
        template.SEGMENT_59,
        json.dumps(team_scope_map, ensure_ascii=False),
        template.SEGMENT_61,
        json.dumps(model_picker_catalog, ensure_ascii=False),
        template.SEGMENT_63,
        json.dumps(provider_picker_catalog, ensure_ascii=False),
        template.SEGMENT_65,
    ]
    return "".join(parts)

# Restored callable defaults from the trusted runtime.
_task_public_name.__defaults__ = (False,)
_task_public_search.__defaults__ = (False,)
_metric_grid.__kwdefaults__ = {'project_id': ''}
_query_value.__defaults__ = ('',)
_module_metric_totals.__kwdefaults__ = {'platform_resolver': None}
_platform_logo_html.__defaults__ = (None,)
_platform_logo_html.__kwdefaults__ = {'compact': False}
_render_platform_channel_overview.__kwdefaults__ = {'represented_platforms': None}
_content_platform_resolver.__defaults__ = (None,)
_render_platform_metric_cell.__defaults__ = ('',)
_platform_card_metrics.__defaults__ = (None,)
_render_platform_rollup_card.__defaults__ = (None,)
_dashboard_add_platform_store.__kwdefaults__ = {'count_store': True}
_dashboard_data_panel_html.__defaults__ = (None,)
_realtime_big_screen_html.__kwdefaults__ = {'query': None}
render_desktop_shell.__defaults__ = ('/desktop',)
render_desktop_workspace.__defaults__ = (None, None)
