from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

from .storage import newest, read_records, write_report
from .types import IntakeRecord


SECTION_NAMES = {
    "money_case": "真实赚钱/亏钱案例",
    "influencer_cooperation": "达人合作数据",
    "selection_playbook": "选品SOP/方法论",
    "hot_link": "爆款链接库",
    "platform_ranking_signal": "多平台原生榜单",
    "store_profile": "多国家店铺档案",
    "supply_chain": "供应链数据",
    "culture_label": "美国文化标签",
    "holiday_opportunity": "节日机会",
    "tk_rule_update": "TK 规则更新",
    "store_health_event": "店铺健康/封店事件",
    "store_operation_event": "店铺后台执行路径",
    "viral_content_signal": "爆款内容信号",
    "creator_spike_event": "达人异动监控",
    "video_breakdown": "视频拆解样本",
    "video_script": "视频脚本资产",
    "social_account_profile": "视频账号/AIP绑定矩阵",
    "video_publish_plan": "视频发布计划",
    "creative_inspiration": "素材灵感/原创方向",
    "industry_research_asset": "跨境行业研究资产",
    "strategy_memory": "AI策略记忆",
    "compliance_term": "违禁词/侵权风险库",
    "review_insight": "评论差评/投诉洞察",
    "feedback_ticket": "投诉建议/产品反馈",
    "collection_job": "平台数据采集任务",
    "store_metric_snapshot": "实时销售/退货数据",
}

SECTION_NAMES["ip_image_risk"] = "全平台图片/视频/Listing/TRO侵权风险库"

STORE_DATA_GAP_IMPACTS = [
    {
        "label": "订单/销售",
        "fields": ["order_count", "orders", "total_revenue", "revenue", "net_revenue", "unit_count", "units"],
        "impact": "影响成交判断、爆品识别、国家站点优先级和投流 ROI；没有订单只保留观察建议。",
        "next": "后台 AI 先读取订单号/订单量、销售额、件数、国家/站点、商品/SKU 和时间。",
    },
    {
        "label": "广告/投流",
        "fields": ["ad_spend", "ads_spend", "roas", "roi", "cpa", "campaign_id", "ad_group_id"],
        "impact": "影响 ROAS、止损线、放量节奏和素材胜负判断；没有广告账号或报表时只生成预算前置缺口清单。",
        "next": "后台 AI 先读取广告花费、ROAS、广告组、素材、点击/转化和归属账号。",
    },
    {
        "label": "退款/售后",
        "fields": ["refund_amount", "refund_count", "return_count", "returns", "refund_reason", "return_reason"],
        "impact": "影响退款率、质量问题、物流问题和商品页改法；没有售后证据不做大额放量。",
        "next": "后台 AI 先读取退款金额、退款/退货数量、原因、订单/SKU 和责任归因。",
    },
    {
        "label": "库存",
        "record_types": ["inventory_ledger"],
        "fields": ["sku", "warehouse", "available_inventory", "available_qty", "stock_qty", "inventory_qty"],
        "impact": "影响活动库存门槛、补货计划和断货风险；没有库存时不建议报名高峰活动。",
        "next": "后台 AI 先读取 SKU、仓库、可售库存、锁定库存、补货/断货状态。",
    },
    {
        "label": "结算/财务",
        "record_types": ["finance_transaction"],
        "fields": ["settlement_amount", "fee_total", "platform_fee", "commission", "transaction_fee", "shipping_fee", "tax"],
        "impact": "影响真实利润、平台费、广告费和账期判断；没有结算不做利润型决策。",
        "next": "后台 AI 先读取结算金额、平台费用、广告费、退款、物流/生产成本和账期。",
    },
    {
        "label": "商品状态",
        "record_types": ["listing_snapshot"],
        "fields": ["listing_status", "product_name", "sku", "price", "product_url", "audit_status"],
        "impact": "影响能不能上架、改价、推广告和同步平台；没有商品状态只做策略草稿。",
        "next": "后台 AI 先读取商品/SKU、标题、价格、上架状态、平台链接和审核/违规状态。",
    },
    {
        "label": "活动报名/优惠状态",
        "record_types": ["store_operation_event"],
        "fields": ["activity_type", "campaign_status", "promotion_status", "discount_rule", "coupon_rule", "operation_type"],
        "keywords": ["活动", "优惠", "折扣", "coupon", "campaign", "promotion", "discount"],
        "impact": "影响活动报名、优惠叠加和广告联动；真实报名、发券、改价和投放必须确认。",
        "next": "后台 AI 先生成活动、优惠券、广告联动和叠加校验草稿，等待负责人确认。",
    },
]


def generate_daily_report(root: Path, report_date: str | None = None) -> tuple[str, Path]:
    report_date = report_date or date.today().isoformat()
    records = [record for record in read_records(root) if record.review_status != "pending"]
    grouped: dict[str, list[IntakeRecord]] = defaultdict(list)
    for record in records:
        grouped[record.record_type].append(record)

    lines: list[str] = [
        "# AI Ecommerce Director Daily Report",
        "",
        f"日期：{report_date}",
        "",
        "## 今日总判断",
        "",
    ]
    if not records:
        lines.extend(
            [
                "今天还没有真实战场数据。优先投喂赚钱案例、达人结果、爆款链接和供应链库存。",
                "",
            ]
        )
    else:
        lines.extend(build_executive_summary(grouped))

    lines.extend(build_store_data_gap_impact_section(grouped))
    lines.extend(build_action_items(grouped))
    lines.extend(build_section("Amazon BS/NEW 版块", newest(amazon_bs_new_records(grouped.get("platform_ranking_signal", [])), 5)))
    for record_type, title in SECTION_NAMES.items():
        lines.extend(build_section(title, newest(grouped.get(record_type, []), 5)))

    content = "\n".join(lines).rstrip() + "\n"
    path = write_report(root, report_date, content)
    return content, path


def build_store_data_gap_impact_section(grouped: dict[str, list[IntakeRecord]]) -> list[str]:
    lines = ["## 店铺数据缺口影响", ""]
    store_metrics = grouped.get("store_metric_snapshot", [])
    ready_count = 0
    rows: list[str] = []
    for spec in STORE_DATA_GAP_IMPACTS:
        evidence_count, evidence_text = store_gap_evidence_for_spec(spec, grouped, store_metrics)
        if evidence_count:
            ready_count += 1
            status = f"可分析（{evidence_text}）"
        else:
            status = "待读取"
        rows.append(
            f"- {spec['label']}：{status}。影响：{spec['impact']} 下一步：{spec['next']}"
        )
    lines.append(f"真实数据清单：{ready_count} 项可分析 / {len(STORE_DATA_GAP_IMPACTS) - ready_count} 项待读取。")
    lines.append("后台 AI 只把证据足够的部分用于经营判断；证据不完整时，只生成安全草稿和待确认动作，不自动执行真实店铺动作。")
    lines.extend(rows)
    lines.append("")
    return lines


def store_gap_evidence_for_spec(
    spec: dict[str, object],
    grouped: dict[str, list[IntakeRecord]],
    store_metrics: list[IntakeRecord],
) -> tuple[int, str]:
    record_types = [str(item) for item in spec.get("record_types", [])] if isinstance(spec.get("record_types"), list) else []
    candidate_records = list(store_metrics)
    for record_type in record_types:
        candidate_records.extend(grouped.get(record_type, []))
    fields = [str(item) for item in spec.get("fields", [])] if isinstance(spec.get("fields"), list) else []
    matched_fields: set[str] = set()
    for record in candidate_records:
        for field in fields:
            if record_field_has_value(record, field):
                matched_fields.add(field)
    keywords = [str(item).lower() for item in spec.get("keywords", [])] if isinstance(spec.get("keywords"), list) else []
    keyword_matches = 0
    if keywords:
        for record in candidate_records:
            blob = " ".join(
                [
                    str(record.record_type or ""),
                    " ".join(str(value) for value in record.fields.values()),
                    " ".join(str(value) for value in record.score.values()),
                    " ".join(record.director_notes),
                ]
            ).lower()
            if any(keyword in blob for keyword in keywords):
                keyword_matches += 1
    evidence_count = len(matched_fields) + keyword_matches
    evidence_parts: list[str] = []
    if matched_fields:
        evidence_parts.append("字段 " + "、".join(sorted(matched_fields)[:4]))
    if keyword_matches:
        evidence_parts.append(f"{keyword_matches} 条活动/优惠线索")
    return evidence_count, "；".join(evidence_parts)


def record_field_has_value(record: IntakeRecord, field: str) -> bool:
    value = record.fields.get(field)
    if value in (None, "", [], {}):
        value = record.score.get(field)
    if value in (None, "", [], {}):
        return False
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip()
    if not text:
        return False
    return text not in {"0", "0.0", "$0", "$0.00"}


def build_executive_summary(grouped: dict[str, list[IntakeRecord]]) -> list[str]:
    money_cases = grouped.get("money_case", [])
    selection_playbooks = grouped.get("selection_playbook", [])
    influencers = grouped.get("influencer_cooperation", [])
    hot_links = grouped.get("hot_link", [])
    platform_rankings = grouped.get("platform_ranking_signal", [])
    supply = grouped.get("supply_chain", [])
    risk_rules = grouped.get("tk_rule_update", [])
    store_health = grouped.get("store_health_event", [])
    store_profiles = grouped.get("store_profile", [])
    store_operations = grouped.get("store_operation_event", [])
    viral_content = grouped.get("viral_content_signal", [])
    creator_spikes = grouped.get("creator_spike_event", [])
    video_breakdowns = grouped.get("video_breakdown", [])
    video_scripts = grouped.get("video_script", [])
    social_accounts = grouped.get("social_account_profile", [])
    publish_plans = grouped.get("video_publish_plan", [])
    creative_inspirations = grouped.get("creative_inspiration", [])
    industry_research = grouped.get("industry_research_asset", [])
    strategy_memories = grouped.get("strategy_memory", [])
    compliance_terms = grouped.get("compliance_term", [])
    review_insights = grouped.get("review_insight", [])
    feedback_tickets = grouped.get("feedback_ticket", [])
    collection_jobs = grouped.get("collection_job", [])
    store_metrics = grouped.get("store_metric_snapshot", [])

    lines = [
        f"- 爆款内容信号：{len(viral_content)} 条",
        f"- 达人异动：{len(creator_spikes)} 条",
        f"- 视频拆解：{len(video_breakdowns)} 条",
        f"- 视频脚本：{len(video_scripts)} 条",
        f"- 视频账号/AIP矩阵：{len(social_accounts)} 条",
        f"- 视频发布计划：{len(publish_plans)} 条",
        f"- 素材灵感/原创方向：{len(creative_inspirations)} 条",
        f"- 跨境行业研究资产：{len(industry_research)} 条",
        f"- AI策略记忆：{len(strategy_memories)} 条",
        f"- 违禁词/侵权风险：{len(compliance_terms)} 条",
        f"- 评论差评/投诉洞察：{len(review_insights)} 条",
        f"- 投诉建议/产品反馈：{len(feedback_tickets)} 条",
        f"- 平台数据采集任务：{len(collection_jobs)} 条",
        f"- 实时销售/退货快照：{len(store_metrics)} 条",
        f"- 店铺健康事件：{len(store_health)} 条",
        f"- 店铺档案：{len(store_profiles)} 条",
        f"- 店铺执行路径：{len(store_operations)} 条",
        f"- 真实案例：{len(money_cases)} 条",
        f"- 选品SOP：{len(selection_playbooks)} 条",
        f"- 达人合作：{len(influencers)} 条",
        f"- 爆款链接：{len(hot_links)} 条",
        f"- 平台原生榜单：{len(platform_rankings)} 条",
        f"- 供应链记录：{len(supply)} 条",
        f"- TK 规则：{len(risk_rules)} 条",
        "",
    ]

    top_health = top_by_priority(store_health)
    if top_health:
        status = top_health.fields.get("account_status") or top_health.fields.get("health_status") or "待确认"
        action = top_health.score.get("recommended_action", "先处理店铺健康。")
        lines.append(f"- 今日最高风险店铺：{record_name(top_health)}，状态：{status}，动作：{action}")
    top_operation = top_by_priority(store_operations)
    if top_operation:
        lines.append(f"- 今日重点后台路径：{record_name(top_operation)}")
    incomplete_profiles = [
        record
        for record in store_profiles
        if not record.score.get("adaptation_ready")
    ]
    if incomplete_profiles:
        lines.append(f"- 店铺适配缺项：{len(incomplete_profiles)} 个店铺档案还需要确认国家、平台、登录环境窗口、访问区域或履约模式。")
    top_video = top_by_priority([*viral_content, *video_breakdowns])
    if top_video:
        lines.append(f"- 今日优先拆解爆款内容：{record_name(top_video)}")
    top_script = top_by_priority(video_scripts)
    if top_script:
        channel = top_script.score.get("script_channel", "待定")
        lines.append(f"- 今日优先拍摄脚本：{record_name(top_script)}，类型：{channel}")
    top_publish_plan = top_by_priority(publish_plans)
    if top_publish_plan:
        ready = "可进入发布确认" if top_publish_plan.score.get("publish_ready") else "先补发布包/音乐检查"
        lines.append(f"- 今日优先视频发布计划：{record_name(top_publish_plan)}，状态：{ready}")
    top_creative = top_by_priority(creative_inspirations)
    if top_creative:
        lines.append(f"- 今日优先原创素材方向：{record_name(top_creative)}")
    top_research = top_by_priority(industry_research)
    if top_research:
        asset_type = top_research.score.get("research_asset_type", top_research.fields.get("research_asset_type", "general_research"))
        status = top_research.score.get("research_status", "needs_validation_task")
        lines.append(f"- 今日优先行业研究资产：{record_name(top_research)}，类型：{asset_type}，状态：{status}")
    top_memory = top_by_priority(strategy_memories)
    if top_memory:
        track = top_memory.fields.get("learning_track_name") or top_memory.fields.get("memory_type") or "strategy_memory"
        learned = top_memory.fields.get("what_we_learned") or top_memory.fields.get("rule_summary") or "已沉淀为策略记忆。"
        lines.append(f"- 今日AI自学记忆：{track}，结论：{learned}")
    top_compliance = top_by_priority(compliance_terms)
    if top_compliance:
        lines.append(f"- 今日优先风控词：{record_name(top_compliance)}，自动发布阻断：{top_compliance.score.get('blocks_auto_publish', False)}")
    top_review = top_by_priority(review_insights)
    if top_review:
        lines.append(f"- 今日优先差评痛点：{record_name(top_review)}")
    top_feedback = top_by_priority(feedback_tickets)
    if top_feedback:
        category = top_feedback.score.get("feedback_category", "feedback")
        lines.append(f"- 今日优先产品反馈：{record_name(top_feedback)}，类型：{category}")
    top_collection = top_by_priority(collection_jobs)
    if top_collection:
        lines.append(f"- 今日优先采集任务：{record_name(top_collection)}")
    top_metric = top_by_priority(store_metrics)
    if top_metric:
        revenue = top_metric.score.get("revenue", top_metric.fields.get("total_revenue", "待确认"))
        roas = top_metric.score.get("roas", top_metric.fields.get("roi", "待确认"))
        lines.append(f"- 今日优先店铺数据：{record_name(top_metric)}，销售额：{revenue}，ROAS：{roas}")
    top_creator_spike = top_by_priority(creator_spikes)
    if top_creator_spike:
        grade = top_creator_spike.score.get("creator_watch_grade", "watch")
        lines.append(f"- 今日疑似爆款达人：{record_name(top_creator_spike)}，等级：{grade}")
    top_money = top_by_priority(money_cases)
    if top_money:
        lines.append(f"- 今日优先复盘案例：{record_name(top_money)}")
    top_playbook = top_by_priority(selection_playbooks)
    if top_playbook:
        lines.append(f"- 当前选品方法论：{record_name(top_playbook)}")
    top_influencer = top_by_priority(influencers)
    if top_influencer:
        grade = top_influencer.score.get("grade", "待定")
        lines.append(f"- 今日优先达人：{record_name(top_influencer)}，等级 {grade}")
    top_link = top_by_priority(hot_links)
    if top_link:
        lines.append(f"- 今日优先拆解爆款：{record_name(top_link)}")
    top_ranking = top_by_priority(platform_rankings)
    if top_ranking:
        lines.append(f"- 今日优先平台榜单：{record_name(top_ranking)}")
    top_amazon_bs_new = top_by_priority(amazon_bs_new_records(platform_rankings))
    if top_amazon_bs_new:
        lines.append(f"- 今日优先 Amazon BS/NEW：{record_name(top_amazon_bs_new)}")
    lines.append("")
    return lines


def build_action_items(grouped: dict[str, list[IntakeRecord]]) -> list[str]:
    lines = ["## 今日行动清单", ""]
    actions: list[str] = [
        "按店铺数据缺口影响判断：缺订单不判成交，缺广告不启动投放，缺库存不报名高峰活动，缺结算不做利润决策；证据不完整时不自动执行真实店铺动作。"
    ]

    if grouped.get("store_health_event"):
        top_health = top_by_priority(grouped["store_health_event"])
        if top_health and top_health.score.get("store_operable") is False:
            actions.append("先处理封店/停用店铺：进入店铺健康页查看违规原因、申诉窗口和恢复路径，暂停该店增长动作。")
        else:
            actions.append("先检查店铺健康待办：待整改违规、可申诉违规、低库存、待发货和售后。")
    if grouped.get("store_operation_event"):
        actions.append("按后台执行路径检查商品上架、图片/标题/描述、折扣设置、活动报名和达人联盟配置。")
    if grouped.get("store_profile"):
        actions.append("检查多国家店铺档案：国家、平台、币种、时区、语言、登录环境窗口、访问区域和履约模式是否完整。")
    if grouped.get("viral_content_signal") or grouped.get("video_breakdown"):
        actions.append("优先拆解爆款视频：按 0-2 秒钩子、镜头结构、人群身份、场景、情绪、评论区购买原因和复刻版本输出。")
    if grouped.get("video_script"):
        actions.append("把视频脚本分两条线执行：店铺自播脚本检查产品展示点、主图/详情页承接和复拍成本；达人脚本检查达人类型、寄样重点、自由发挥边界、禁区和挂车 CTA。")
    if grouped.get("social_account_profile"):
        actions.append("检查每个店铺的视频账号矩阵：1个官方号负责品牌信任，4个渠道号负责角度测试；AIP发视频权限、登录入口和绑定状态必须进入确认队列。")
    if grouped.get("video_publish_plan"):
        actions.append("执行视频发布前检查：标题、标签、产品卡、AIP账号、音乐授权和音量比例全部通过后，才允许进入人工确认发布。")
    if grouped.get("creative_inspiration"):
        actions.append("用素材灵感库生成原创素材：结合过往脚本、标题、标签、评论痛点和销售结果，只复用结构和情绪，不复制同行画面、音乐、品牌元素或完整话术。")
    if grouped.get("industry_research_asset"):
        actions.append("更新跨境行业研究库：把品牌库、产品库、痛点库、关键词库、内容账号库、竞品网站库、知识地图和机会清单里的资料转成可验证任务，再决定是否进入选品、内容、达人或 Listing 执行。")
    if grouped.get("strategy_memory"):
        actions.append("复盘AI策略记忆：把空闲学习沉淀出的可执行规律，用于选品、脚本、Listing、达人、风控和投流策略；仍然只生成草稿和待确认动作。")
    if grouped.get("collection_job"):
        actions.append("执行只读平台数据采集任务：优先 API，其次浏览器插件/平台巡检，采集历史和当前榜单、爆款视频、评论、达人、关键词、店铺健康与销售数据，并写入对应数据库。")
    if grouped.get("store_metric_snapshot"):
        actions.append("复盘实时销售大盘：按时间段、平台和店铺检查销售额、订单、广告花费、ROAS、退款和退货，把异常店铺交给投流、客服、Listing 和产品质量模块继续分析。")
    if grouped.get("compliance_term"):
        actions.append("扫描违禁词/侵权风险库：生成 Listing、标签、图片文案、视频脚本和达人 brief 前先做风险词扫描；命中高风险词时阻止自动发布，进入人工复核。")
    if grouped.get("review_insight"):
        actions.append("拆解同行差评和自己店铺投诉：提取高频痛点、退款原因、产品缺陷、详情页误导点和素材解释缺口，生成产品/Listing/脚本优化草稿。")
    if grouped.get("feedback_ticket"):
        actions.append("处理投诉建议中心：按 bug、数据偏差、界面体验、功能建议、运营策略问题归类；有截图/标注图的优先复核并生成修复草稿。")
    if grouped.get("creator_spike_event"):
        actions.append("检查疑似爆款达人：对比历史均播、最新爆款视频、评论区购买意向，并决定是否进入 A/B 观察或寄样名单。")
    if grouped.get("money_case"):
        actions.append("把最高优先级赚钱/亏钱案例拆成产品、关键词、达人、素材和风控规则。")
    if grouped.get("selection_playbook"):
        actions.append("用选品SOP校验候选产品：趋势、榜单、维度指标、亚马逊反推、风险和细节项。")
    if grouped.get("influencer_cooperation"):
        actions.append("复盘 A 级达人并加入复投名单，C 级达人加入观察或黑名单。")
    if grouped.get("hot_link"):
        actions.append("对新增爆款链接做竞品拆解，提取人群、钩子、标题和关键词。")
    if grouped.get("platform_ranking_signal"):
        actions.append("对 Amazon / TikTok Shop / Etsy / Walmart / SHEIN 等平台原生榜单做拆解，区分长期需求、新品爆发和短期异动。")
    if amazon_bs_new_records(grouped.get("platform_ranking_signal", [])):
        actions.append("对 Amazon BS/NEW 版块单独拆解：Best Sellers 看长期需求，New Releases 看新品爆发，优先反推关键词、价格带、评论痛点和可复制品类。")
    if grouped.get("supply_chain"):
        actions.append("用有库存、低成本、快发货的供应链记录反推今日可测产品。")
    if grouped.get("tk_rule_update"):
        actions.append("检查 TK 高风险规则是否影响当前选品、Listing、广告和达人合作。")
    if not actions:
        actions.append("先投喂 1 条真实赚钱案例或 1 条爆款链接，启动数据飞轮。")

    lines.extend(f"- {action}" for action in actions)
    lines.append("")
    return lines


def build_section(title: str, records: list[IntakeRecord]) -> list[str]:
    lines = [f"## {title}", ""]
    if not records:
        lines.extend(["暂无记录。", ""])
        return lines

    sorted_records = sorted(records, key=lambda item: float(item.score.get("priority", 0) or 0), reverse=True)
    for index, record in enumerate(sorted_records, 1):
        lines.append(f"### {index}. {record_name(record)}")
        lines.append("")
        lines.append(f"- 优先级：{record.score.get('priority', '待定')}")
        for key, value in compact_fields(record.fields).items():
            lines.append(f"- {key}：{value}")
        for note in record.director_notes[:3]:
            lines.append(f"- 运营判断：{note}")
        lines.append("")
    return lines


def top_by_priority(records: list[IntakeRecord]) -> IntakeRecord | None:
    if not records:
        return None
    return max(records, key=lambda record: (float(record.score.get("priority", 0) or 0), record.created_at))


def amazon_bs_new_records(records: list[IntakeRecord]) -> list[IntakeRecord]:
    result: list[IntakeRecord] = []
    for record in records:
        fields = record.fields
        marketplace = str(fields.get("marketplace") or fields.get("source_platform") or "").lower()
        ranking_type = str(fields.get("ranking_type") or "").lower()
        ranking_page = str(fields.get("ranking_page") or fields.get("url") or fields.get("page_url") or "").lower()
        text = f"{marketplace} {ranking_type} {ranking_page}"
        if "amazon" not in text and "亚马逊" not in text:
            continue
        if any(
            signal in text
            for signal in [
                "bsr",
                "bs.new",
                "bs/new",
                "best sellers",
                "best-sellers",
                "new releases",
                "new-releases",
                "amazon bs/new",
                "amazon bs.new",
            ]
        ):
            result.append(record)
    return result


def record_name(record: IntakeRecord) -> str:
    fields = record.fields
    if record.record_type == "influencer_cooperation" and fields.get("influencer_handle"):
        return str(fields["influencer_handle"])
    if record.record_type == "platform_ranking_signal":
        fields = record.fields
        parts = [
            str(fields.get("marketplace") or fields.get("source_platform") or "").strip(),
            str(fields.get("ranking_type") or "").strip(),
            f"#{fields.get('rank_position')}" if fields.get("rank_position") not in {"", None} else "",
            str(fields.get("product_name") or fields.get("page_title") or fields.get("url") or "").strip(),
        ]
        name = " ".join(part for part in parts if part)
        if name:
            return name
    for key in ["feedback_text", "module_area", "creative_angle", "publish_title", "target_account_handle", "account_handle", "aip_provider", "learning_track_name", "memory_type", "term", "pain_point", "review_source", "collection_target", "platform_list", "video_url", "creator_handle", "product_theme", "content_theme", "hook_text", "research_asset_type", "opportunity", "knowledge_node", "brand_name", "content_account", "competitor_site_url", "playbook_name", "platform_name", "admin_url", "base_url", "operation_type", "operation_path", "store_id", "store_name", "browser_profile", "marketplace", "country_code", "ranking_type", "product_name", "influencer_handle", "english_label", "holiday_name", "url", "summary"]:
        if fields.get(key):
            return str(fields[key])
    return record.record_id[:8]


def compact_fields(fields: dict[str, object], limit: int = 8) -> dict[str, object]:
    compacted: dict[str, object] = {}
    for key, value in list(fields.items())[:limit]:
        if value is None:
            continue
        if isinstance(value, str) and not value:
            continue
        if isinstance(value, list):
            compacted[key] = f"{len(value)} items" if len(str(value)) > 180 else value
        elif isinstance(value, dict):
            compacted[key] = f"{len(value)} fields" if len(str(value)) > 180 else value
        else:
            compacted[key] = value
    return compacted
