from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


LOCALIZATION_CONFIG = Path("config") / "localization.json"

DEFAULT_LOCALIZATION_CONFIG = {
    "default_locale": "zh-CN",
    "supported_locales": ["zh-CN", "en-US", "es-MX", "de-DE", "fr-FR"],
    "fallback_locale": "zh-CN",
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "zh-CN": {
        "dashboard": "首页",
        "manual_capture_center": "后台数据导入",
        "api_application_center": "API申请中心",
        "pod_platform_center": "POD专属通道",
        "pod_admin_details": "POD 管理端",
        "pod_ip_risk": "全平台侵权/TRO风险",
        "selection_results": "选品结果",
        "today_report": "今日报告",
        "control_console": "控制台",
        "download_capture_extension": "下载采集插件",
        "multi_ai_brain": "多 AI 大脑",
        "api_sources": "API 数据源",
        "auto_mode": "安全自动模式",
        "today_workbench": "今日工作台",
        "chat_feed": "店铺 AI 顾问",
        "workflow_check": "工作流自检",
        "manual_capture_subtitle": "管理员使用：导入授权店铺、商品、竞品、视频素材、截图和表格；用户端只看整理后的报告和下一步动作。",
        "daily_use": "每日流程",
        "open_platform": "打开平台",
        "open_platform_body": "打开 Amazon、TikTok Shop、FastMoss、Kalodata、Etsy、Walmart、SHEIN 或店铺后台；优先使用已登录的浏览器窗口。",
        "human_verify": "人工通过验证",
        "human_verify_body": "登录、滑块、短信、人脸、授权和账号提示由你处理；工具只在授权访问后读取页面。",
        "extension_capture": "插件采集",
        "extension_capture_body": "选择采集类型，填写店铺、国家、浏览器/IP 备注，然后采集当前页面。",
        "ai_process": "AI 处理",
        "ai_process_body": "查看选品结果、今日报告、内容脚本、达人方向、风险提示和待确认动作。",
        "recommended_tasks": "推荐采集任务",
        "recent_manual_captures": "最近采集",
        "safe_boundary": "安全边界",
        "safe_boundary_body": "不会绕过验证、提交表单、上架商品、改价、报名活动、联系达人、付款、退款、发货或下架商品。真实业务动作都会先进入待确认队列。",
        "platform_page": "平台 / 页面",
        "plugin_type": "采集类型",
        "notes_to_write": "备注要写什么",
        "after_capture": "采集后进入",
        "time": "时间",
        "type": "类型",
        "name": "名称",
        "platform": "平台",
        "link": "链接",
        "open": "打开",
        "no_manual_records": "还没有采集记录。先安装插件，打开平台页面后采集当前页面。",
        "api_app_subtitle": "记录哪些 API 可以申请、需要哪些材料、Key 应该放在哪里，以及接入后能读取什么。",
        "total_apis": "API 总数",
        "ready_to_apply": "可申请",
        "needs_store_review": "需要店铺 / 审核",
        "vendor_contact_needed": "需要联系服务商",
        "application_checklist": "申请清单",
        "priority": "优先级",
        "provider": "服务商",
        "status": "状态",
        "best_for": "适合用途",
        "required_materials": "所需材料",
        "environment_vars": "环境变量",
        "next_step": "下一步",
        "what_i_can_do": "我接下来能做什么",
        "api_action_1": "打开申请页面并准备草稿；提交会发送店铺、邮箱、电话或公司资料，需要你确认。",
        "api_action_2": "拿到平台连接密钥后，我可以写入本地安全配置并开启对应只读数据源。",
        "api_action_3": "官方 API 批下来前，继续用采集插件读取榜单、视频、评论和后台路径。",
        "secret_warning": "不要把 API 密钥、密码、短信码或账号凭据写进聊天或普通配置文件。",
        "pod_subtitle": "POD 是老板专属铺货通道：选品、设计、生图、生视频、标题 Listing、IP 审核、渠道草稿和待确认发布集中在这里；详细资料和权限配置仅由负责人查看。",
        "project": "项目",
        "read_only_safe_mode": "只读安全模式",
        "portals": "端口",
        "pod_modules": "POD运营模块",
        "channel_fulfillment": "多渠道履约",
        "risk_and_pending_actions": "风险与待确认动作",
        "recent_pod_snapshots": "最近 POD 快照",
        "ip_risk_subtitle": "收集商标、版权、品牌、角色、明星、图片、Listing、广告、视频脚本、TRO 案件、证据、授权证明和疑似链接。",
        "risk_elements": "风险元素",
        "delist_review": "下架复审",
        "tro_cases": "TRO / 案件",
        "high_priority": "高优先级",
        "capture_format": "采集格式",
        "capture_format_body": "建议字段：平台、风险元素、类目、权利方/原告、证据 URL/图片、疑似链接/视频/广告、授权状态/证明、通知/TRO 信息和复审优先级。",
        "risk_library": "风险元素库",
        "element_time": "元素 / 时间",
        "rights_owner_tro": "权利方 / TRO",
        "evidence": "证据",
        "suspected_link": "疑似链接",
        "action": "动作",
        "pending_delist_review": "等待下架复审",
        "scan_block": "扫描并拦截",
        "no_ip_risks": "还没有全平台侵权 / TRO 风险元素。商品、Listing、图片、视频、广告、脚本或店铺风险都用 ip_image_risk 采集。",
        "language": "语言",
        "report_language": "报告语言",
        "chinese": "中文",
        "english": "English",
        "language_note": "多语言只切换界面说明；客户数据保持安全隔离。",
    },
    "en-US": {
        "dashboard": "Home",
        "manual_capture_center": "Back-Office Data Import",
        "api_application_center": "API Application Center",
        "pod_platform_center": "POD Owner Channel",
        "pod_admin_details": "POD Admin",
        "pod_ip_risk": "Platform IP / TRO Risk",
        "selection_results": "Product Reports",
        "today_report": "Today Report",
        "control_console": "Console",
        "download_capture_extension": "Download Capture Extension",
        "multi_ai_brain": "Multi-AI Brain",
        "api_sources": "API Sources",
        "auto_mode": "Safe Auto Mode",
        "today_workbench": "Today Workspace",
        "chat_feed": "Store AI Advisor",
        "workflow_check": "Workflow Check",
        "manual_capture_subtitle": "Admin use only: import authorized store, product, competitor, video, screenshot, and spreadsheet data. Users only see reports and next actions.",
        "daily_use": "Daily Workflow",
        "open_platform": "Open Platform",
        "open_platform_body": "Open Amazon, TikTok Shop, FastMoss, Kalodata, Etsy, Walmart, SHEIN, or your store backend in an already logged-in browser.",
        "human_verify": "Human Verification",
        "human_verify_body": "You handle login, sliders, SMS, face checks, authorization, and account prompts. The tool reads only after access is granted.",
        "extension_capture": "Extension Capture",
        "extension_capture_body": "Choose a record type, fill store/country/browser/IP notes, and capture the current page.",
        "ai_process": "AI Processing",
        "ai_process_body": "Review product reports, daily reports, content scripts, creator direction, risk alerts, and pending actions.",
        "recommended_tasks": "Recommended Capture Tasks",
        "recent_manual_captures": "Recent Captures",
        "safe_boundary": "Safety Boundary",
        "safe_boundary_body": "This mode does not bypass verification, submit forms, list products, change prices, join campaigns, contact creators, pay money, refund, ship, or delist products. Real business actions stay pending until you confirm.",
        "platform_page": "Platform / Page",
        "plugin_type": "Capture Type",
        "notes_to_write": "What To Write In Notes",
        "after_capture": "After Capture",
        "time": "Time",
        "type": "Type",
        "name": "Name",
        "platform": "Platform",
        "link": "Link",
        "open": "Open",
        "no_manual_records": "No captures yet. Install the extension, open a platform page, and capture the current page.",
        "api_app_subtitle": "Track which APIs can be applied for, what materials are needed, where keys should live, and what the integration can read.",
        "total_apis": "Total APIs",
        "ready_to_apply": "Ready To Apply",
        "needs_store_review": "Needs Store / Review",
        "vendor_contact_needed": "Vendor Contact Needed",
        "application_checklist": "Application Checklist",
        "priority": "Priority",
        "provider": "Provider",
        "status": "Status",
        "best_for": "Best For",
        "required_materials": "Required Materials",
        "environment_vars": "Environment Variables",
        "next_step": "Next Step",
        "what_i_can_do": "What I Can Do Next",
        "api_action_1": "Open application pages and prepare draft answers. Submission needs your confirmation because store, email, phone, or company data may be sent.",
        "api_action_2": "After you get keys or tokens, I can save them in local secure config and enable the matching read-only source.",
        "api_action_3": "Before official APIs are approved, keep using the capture extension for rankings, videos, reviews, and backend paths.",
        "secret_warning": "Do not paste API secrets, passwords, SMS codes, or account credentials into chat or normal config files.",
        "pod_subtitle": "Dedicated owner channel for POD scaling: product ideas, design, images, videos, listings, IP review, channel drafts, and approval queues. Internal ingestion, training, and source materials stay in admin.",
        "project": "Project",
        "read_only_safe_mode": "Read-only safe mode",
        "portals": "Portals",
        "pod_modules": "POD Operating Modules",
        "channel_fulfillment": "Multi-Channel Fulfillment",
        "risk_and_pending_actions": "Risks And Pending Actions",
        "recent_pod_snapshots": "Recent POD Snapshots",
        "ip_risk_subtitle": "Collect trademark, copyright, brand, character, celebrity, artwork, listing, ad, video/script, TRO case, evidence, authorization proof, and suspected URLs.",
        "risk_elements": "Risk Elements",
        "delist_review": "Delist Review",
        "tro_cases": "TRO / Cases",
        "high_priority": "High Priority",
        "capture_format": "Capture Format",
        "capture_format_body": "Recommended fields: platform, risk element, category, rights owner/plaintiff, evidence URL/image, suspected listing/video/ad URL, authorization status/proof, notice/TRO info, and review priority.",
        "risk_library": "Risk Element Library",
        "element_time": "Element / Time",
        "rights_owner_tro": "Rights Owner / TRO",
        "evidence": "Evidence",
        "suspected_link": "Suspected Link",
        "action": "Action",
        "pending_delist_review": "Pending delist review",
        "scan_block": "Scan and block",
        "no_ip_risks": "No platform IP/TRO risks yet. Use ip_image_risk for product, listing, image, video, ad, script, or store risks.",
        "language": "Language",
        "report_language": "Report Language",
        "chinese": "中文",
        "english": "English",
        "language_note": "Language switching only changes interface copy; customer data stays isolated.",
    },
}

FIELD_LABELS_ZH: dict[str, str] = {
    "record_type": "数据类型",
    "source_platform": "来源平台",
    "platform_ranking_signal": "平台榜单信号",
    "viral_content_signal": "爆款内容信号",
    "video_breakdown": "视频拆解",
    "video_script": "视频脚本",
    "creator_spike_event": "达人爆发信号",
    "review_insight": "评论痛点",
    "hot_link": "爆款链接",
    "store_sales_snapshot": "店铺销售快照",
    "store_health_event": "店铺健康事件",
    "store_operation_event": "店铺操作路径",
    "ip_image_risk": "侵权图片 / 元素风险",
    "compliance_term": "合规 / 违禁词",
    "learning_event": "学习事件",
    "strategy_memory": "策略记忆",
    "evidence_claim": "证据声明",
    "quality_score": "质量评分",
    "signal_event": "市场信号",
    "hypothesis": "商业假设",
    "experiment": "实验计划",
    "priority_score": "优先级评分",
    "UNKNOWN": "未知",
    "unknown": "未知",
    "true": "是",
    "false": "否",
    "YES": "可以",
    "NO": "不可以",
    "Content Stage": "内容阶段",
    "Hook": "开头钩子",
    "CTA": "引导动作",
    "Brief": "拍摄简报",
    "Script": "脚本",
    "Score": "分数",
    "Evidence": "证据",
    "Next Step": "下一步",
}

FIELD_LABELS_EN: dict[str, str] = {
    "后台数据导入": "Back-office Data Import",
    "今日工作台": "Today Workspace",
    "经营大屏": "Business Dashboard",
    "选品报告": "Product Report",
    "TK内容策略": "TikTok Content Strategy",
    "待确认动作": "Pending Actions",
    "店铺 AI 顾问": "Store AI Advisor",
    "一句话结论": "One-Line Conclusion",
    "证据完整度": "Evidence Completeness",
    "下一步": "Next Step",
    "完整证据": "Full Evidence",
    "阅读方式": "How To Read",
    "先看上面的结论、证据完整度和下一步。完整证据只用于复核，不作为日常阅读入口。": "Read the conclusion, evidence completeness, and next step first. Full evidence is for review only.",
}

COMMON_HUMAN_REPLACEMENTS: tuple[tuple[str, str], ...] = tuple(
    sorted(
        {
            **FIELD_LABELS_ZH,
            "AI Ecommerce Director Daily Report": "AI 电商运营总监日报",
            "AI Ecommerce Director": "AI 电商运营总监",
            "Store advisor": "店铺 AI 顾问",
            "video_script": "视频脚本",
            "video_breakdown": "视频拆解",
            "viral_content_signal": "爆款内容信号",
            "creator_spike_event": "达人爆发信号",
            "platform_ranking_signal": "平台榜单信号",
            "review_painpoint_snapshot": "评论痛点快照",
            "keyword_trend_snapshot": "关键词趋势快照",
            "market_signal": "市场信号",
            "market_hypothesis": "市场假设",
            "category_growth_snapshot": "类目增长快照",
            "selection_category_ranking": "选品类目榜单",
            "buyer_video_shop_competitor": "TikTok 买家侧竞品",
            "fastmoss_tiktok_product_rank": "FastMoss TikTok 商品榜",
            "kalodata_tiktok_product_rank": "Kalodata TikTok 商品榜",
            "amazon_keyword": "Amazon 关键词",
            "etsy_keyword": "Etsy 关键词",
            "shein_keyword": "SHEIN 关键词",
            "logged_in_capture_required": "需要用已登录窗口采集",
            "pending_confirmation": "等待确认",
            "approved_pending_manual_execution": "已批准，等待人工执行",
        }.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )
)


def load_locale(root: Path, requested: str | None = None) -> str:
    config = load_localization_config(root)
    supported = config.get("supported_locales") if isinstance(config.get("supported_locales"), list) else ["zh-CN"]
    supported = [str(item) for item in supported]
    default = str(config.get("default_locale") or "zh-CN")
    if requested and requested in supported:
        return requested
    return default if default in supported else "zh-CN"


def load_localization_config(root: Path) -> dict[str, Any]:
    path = root / LOCALIZATION_CONFIG
    if not path.exists():
        return dict(DEFAULT_LOCALIZATION_CONFIG)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return dict(DEFAULT_LOCALIZATION_CONFIG)
    if not isinstance(payload, dict):
        return dict(DEFAULT_LOCALIZATION_CONFIG)
    merged = dict(DEFAULT_LOCALIZATION_CONFIG)
    merged.update(payload)
    return merged


class Translator:
    def __init__(self, locale: str) -> None:
        fallback = str(DEFAULT_LOCALIZATION_CONFIG["fallback_locale"])
        self.locale = locale if locale in TRANSLATIONS else fallback

    def t(self, key: str) -> str:
        fallback = str(DEFAULT_LOCALIZATION_CONFIG["fallback_locale"])
        return TRANSLATIONS.get(self.locale, {}).get(key) or TRANSLATIONS.get(fallback, {}).get(key) or TRANSLATIONS["en-US"].get(key) or key


def translator(root: Path, requested: str | None = None) -> Translator:
    return Translator(load_locale(root, requested))


def humanize_system_text(text: str, locale: str = "zh-CN") -> str:
    if not text:
        return text
    result = text
    if locale.lower().startswith("en"):
        for old, new in sorted(FIELD_LABELS_EN.items(), key=lambda item: len(item[0]), reverse=True):
            result = result.replace(old, new)
        return result
    for old, new in COMMON_HUMAN_REPLACEMENTS:
        result = result.replace(old, new)
    result = re.sub(r"\bUNKNOWN\b", "未知", result)
    result = re.sub(r"\bNone\b", "无", result)
    return result


def report_language_links(base_path: str, report_ref: str = "") -> str:
    from urllib.parse import urlencode

    zh_query = {"lang": "zh-CN"}
    en_query = {"lang": "en-US"}
    if report_ref:
        zh_query["id"] = report_ref
        en_query["id"] = report_ref
    return (
        "<div class='language-switch'>"
        f"<a href='{base_path}?{urlencode(zh_query)}'>中文</a>"
        f"<a href='{base_path}?{urlencode(en_query)}'>English</a>"
        "</div>"
    )
