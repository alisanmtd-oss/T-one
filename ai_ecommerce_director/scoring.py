from __future__ import annotations

from typing import Any


def score_record(record_type: str, fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    if record_type == "money_case":
        return score_money_case(fields)
    if record_type == "influencer_cooperation":
        return score_influencer(fields)
    if record_type == "supply_chain":
        return score_supply_chain(fields)
    if record_type == "selection_playbook":
        return score_selection_playbook(fields)
    if record_type == "hot_link":
        return score_hot_link(fields)
    if record_type == "platform_ranking_signal":
        return score_platform_ranking(fields)
    if record_type == "tk_rule_update":
        return score_tk_rule(fields)
    if record_type == "store_health_event":
        return score_store_health(fields)
    if record_type == "store_profile":
        return score_store_profile(fields)
    if record_type == "store_operation_event":
        return score_store_operation(fields)
    if record_type == "viral_content_signal":
        return score_viral_content(fields)
    if record_type == "creator_spike_event":
        return score_creator_spike(fields)
    if record_type == "video_breakdown":
        return score_video_breakdown(fields)
    if record_type == "video_script":
        return score_video_script(fields)
    if record_type == "social_account_profile":
        return score_social_account_profile(fields)
    if record_type == "video_publish_plan":
        return score_video_publish_plan(fields)
    if record_type == "creative_inspiration":
        return score_creative_inspiration(fields)
    if record_type == "industry_research_asset":
        return score_industry_research_asset(fields)
    if record_type == "compliance_term":
        return score_compliance_term(fields)
    if record_type == "ip_image_risk":
        return score_ip_image_risk(fields)
    if record_type == "review_insight":
        return score_review_insight(fields)
    if record_type == "feedback_ticket":
        return score_feedback_ticket(fields)
    if record_type == "collection_job":
        return score_collection_job(fields)
    if record_type == "pod_admin_snapshot":
        return score_pod_admin_snapshot(fields)
    if record_type == "store_metric_snapshot":
        return score_store_metric_snapshot(fields)
    if record_type in {"culture_label", "holiday_opportunity"}:
        return score_knowledge_asset(fields)
    return {"priority": 50}, ["已记录，等待后续补充字段。"]


def score_store_metric_snapshot(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    revenue = _number(fields.get("total_revenue")) or _number(fields.get("gmv")) or 0
    orders = _number(fields.get("order_count")) or _number(fields.get("orders")) or 0
    ad_spend = _number(fields.get("ad_spend")) or 0
    return_count = _number(fields.get("return_count")) or 0
    refund_count = _number(fields.get("refund_count")) or 0
    issue_count = max(return_count, refund_count)
    roas = revenue / ad_spend if ad_spend > 0 else None
    refund_rate = issue_count / orders if orders > 0 else 0

    score = 58
    notes: list[str] = ["店铺实时指标快照已进入销售、退货和投流分析大盘。"]
    if revenue > 0 or orders > 0:
        score += 12
        notes.append(f"本窗口销售额 {revenue:.2f}，订单 {int(orders)}，可用于当天投流复盘。")
    if roas is not None:
        if roas >= 3:
            score += 12
            notes.append(f"ROAS {roas:.2f}，可优先复盘素材、达人、关键词和商品承接。")
        elif roas < 1.2:
            score += 10
            notes.append(f"ROAS {roas:.2f} 偏低，建议检查广告消耗、转化率、主图和详情页承接。")
        else:
            score += 5
            notes.append(f"ROAS {roas:.2f}，继续观察不同时间段和平台差异。")
    if refund_rate >= 0.08:
        score += 14
        notes.append(f"退款/退货率 {refund_rate:.1%} 偏高，需要结合差评、客服投诉和产品质量排查。")
    elif issue_count > 0:
        score += 5
        notes.append(f"发现退款/退货 {int(issue_count)} 单，进入售后原因归档。")
    if fields.get("store_id") or fields.get("store_name"):
        score += 3
    if fields.get("marketplace") or fields.get("source_platform"):
        score += 3

    return {
        "priority": round(min(score, 100), 2),
        "metric_type": "store_realtime_dashboard",
        "revenue": round(revenue, 2),
        "orders": int(orders),
        "ad_spend": round(ad_spend, 2),
        "roas": round(roas, 4) if roas is not None else None,
        "refund_rate": round(refund_rate, 4),
        "requires_review": refund_rate >= 0.08 or (roas is not None and roas < 1.2),
    }, notes


def score_pod_admin_snapshot(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    score = 72
    notes = ["POD 管理员端快照应进入 Supply Chain Director、OMS Director 和 Product Intelligence。"]
    if fields.get("base_url"):
        score += 5
        notes.append("已检测到 POD 管理员端可访问入口。")
    if fields.get("db_status") == "ok":
        score += 5
        notes.append("已读取 POD 本地数据库统计，可用于库存、底板、订单和履约判断。")
    pending = _number(fields.get("pending_print_job_count")) or 0
    exceptions = _number(fields.get("exception_job_count")) or 0
    low_stock = _number(fields.get("low_stock_sku_count")) or 0
    designs = _number(fields.get("design_count")) or 0
    blanks = _number(fields.get("blank_count")) or 0
    pending_listings = _number(fields.get("channel_pending_listing_count")) or 0
    pending_shipments = _number(fields.get("channel_pending_shipment_count")) or 0
    below_target = _number(fields.get("platform_ops_below_target_count")) or 0
    if pending > 0:
        score += min(10, pending)
        notes.append(f"存在待生产/待确认工单：{int(pending)}。")
    if exceptions > 0:
        score += min(14, exceptions * 2)
        notes.append(f"存在异常工单：{int(exceptions)}，需要先处理履约风险。")
    if low_stock > 0:
        score += min(10, low_stock)
        notes.append(f"存在低库存 SKU：{int(low_stock)}，选品承接前需要确认补货。")
    if designs > 0 or blanks > 0:
        notes.append(f"POD 可用资产：作品 {int(designs)}，底板 {int(blanks)}。")
    if fields.get("channel_analytics_status") == "ok":
        score += 5
        notes.append("已读取 POD 全平台渠道分析，可用于多渠道上架、广告和达人打法判断。")
    elif fields.get("channel_analytics_status") == "requires_admin_session":
        notes.append("POD 渠道分析接口需要管理员登录态，当前只保留接口结构和授权提示。")
    if pending_listings > 0:
        score += min(8, pending_listings)
        notes.append(f"存在渠道待上架/待同步 Listing：{int(pending_listings)}。")
    if pending_shipments > 0:
        score += min(8, pending_shipments)
        notes.append(f"存在渠道发货同步待处理：{int(pending_shipments)}。")
    if below_target > 0:
        score += min(10, below_target * 2)
        notes.append(f"存在平台代运营未达标商品：{int(below_target)}，需要复盘下架、换素材或换渠道。")
    return {
        "priority": round(min(score, 100), 2),
        "training_weight": "high",
        "pod_watch_type": "admin_read_only_snapshot",
        "requires_confirmation_for_write": True,
    }, notes


def score_money_case(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    roi = _number(fields.get("roi"))
    profit = _number(fields.get("total_profit"))
    failure_reason = str(fields.get("failure_reason", ""))
    score = 50
    notes: list[str] = []

    if roi is not None:
        score += min(35, roi * 10)
        notes.append(f"ROI 已记录：{roi}，可直接影响后续产品和达人判断。")
    if profit is not None and profit > 0:
        score += 10
        notes.append("这是正利润案例，应拆成可复用的产品、素材和达人规则。")
    if "亏" in failure_reason or (profit is not None and profit < 0):
        score += 20
        notes.append("这是亏损/风险案例，需要转成规避规则。")
    if fields.get("content_angle") or fields.get("main_visual_action"):
        score += 8
        notes.append("素材动作已记录，可复用到 Content Direction。")
    if fields.get("influencer_type") or fields.get("influencer_handle"):
        score += 8
        notes.append("达人线索已记录，可反哺 Influencer Hunter。")

    case_type = "win"
    if "亏" in failure_reason or (profit is not None and profit < 0):
        case_type = "loss"
    elif roi is None and profit is None:
        case_type = "unknown"

    return {
        "priority": round(min(score, 100), 2),
        "case_type": case_type,
        "training_weight": "highest",
    }, notes or ["真实案例已记录，后续应补 ROI、利润、达人和素材字段。"]


def score_influencer(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    roi = _number(fields.get("roi"))
    orders = _number(fields.get("orders"))
    avg_views = _number(fields.get("avg_views"))
    video_posted = fields.get("video_posted")
    score = 40
    notes: list[str] = []

    if avg_views is not None:
        score += min(20, avg_views / 5000)
    if roi is not None:
        score += min(35, roi * 10)
        notes.append(f"达人 ROI：{roi}。")
    if orders is not None:
        score += min(25, orders)
        notes.append(f"出单数：{orders}。")
    if video_posted is False:
        score -= 35
        notes.append("达人未出视频，后续合作需谨慎或拉黑。")

    if roi is not None and roi >= 2 or orders is not None and orders >= 30:
        grade = "A"
        action = "优先复投 / 继续合作"
    elif video_posted is False or orders == 0:
        grade = "C"
        action = "停止合作 / 进入黑名单观察"
    else:
        grade = "B"
        action = "低成本复测 / 继续观察"

    return {
        "priority": round(max(0, min(score, 100)), 2),
        "grade": grade,
        "recommended_action": action,
        "training_weight": "highest",
    }, notes or ["达人合作记录已保存，建议补充报价、是否出视频、订单和 ROI。"]


def score_supply_chain(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    inventory = _number(fields.get("inventory_qty"))
    unit_cost = _number(fields.get("unit_cost") or fields.get("landed_cost"))
    production_days = _number(fields.get("production_days"))
    shipping_days = _number(fields.get("shipping_days"))
    score = 45
    notes: list[str] = []

    if inventory is not None and inventory > 0:
        score += 25
        notes.append("有库存，选品执行优先级提高。")
    if unit_cost is not None:
        score += 10
        notes.append(f"成本已记录：{unit_cost}，可用于利润判断。")
    if production_days is not None and production_days <= 3:
        score += 10
        notes.append("生产周期短，适合快速测试。")
    if shipping_days is not None and shipping_days <= 3:
        score += 10
        notes.append("发货周期短，适合跟爆款节奏。")

    return {
        "priority": round(min(score, 100), 2),
        "available_for_fast_launch": score >= 70,
        "training_weight": "high",
    }, notes or ["供应链记录已保存，建议补库存、成本、周期和尺码颜色。"]


def score_selection_playbook(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    filled_keys = [
        key
        for key in [
            "selection_process",
            "selection_tools",
            "selection_direction",
            "selection_metrics",
            "amazon_validation_rules",
            "scoring_framework",
            "avoid_rules",
            "detail_checklist",
        ]
        if fields.get(key)
    ]
    score = 62 + len(filled_keys) * 4
    notes = [
        "选品SOP属于方法论训练资料，应影响 Product Intelligence、Competitor Intelligence、Keyword Hunter 和 Listing Builder。",
    ]
    if fields.get("selection_metrics"):
        notes.append("已记录选品维度指标，可用于后续给产品打分。")
    if fields.get("amazon_validation_rules"):
        notes.append("已记录亚马逊反推规则，可与 Amazon BSR/New Releases/Movers & Shakers 榜单联动。")
    if fields.get("avoid_rules"):
        notes.append("已记录避坑规则，后续选品时应作为淘汰条件。")
    return {
        "priority": round(min(score, 100), 2),
        "training_weight": "high",
        "playbook_stage": "product_selection",
    }, notes


def score_hot_link(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    score = 55
    notes = ["爆款链接先进入样本库，不要求人工立即拆解。"]
    if fields.get("url"):
        score += 15
    if fields.get("screenshot_path"):
        score += 10
    if fields.get("visible_growth_signal"):
        score += 20
        notes.append("已有增长信号，建议进入竞品拆解队列。")
    return {
        "priority": round(min(score, 100), 2),
        "analysis_status": "new",
        "training_weight": "highest",
    }, notes


def score_platform_ranking(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    marketplace = str(fields.get("marketplace") or fields.get("source_platform") or "").lower()
    ranking_type = str(fields.get("ranking_type") or fields.get("ranking_page") or "").lower()
    rank_position = _number(fields.get("rank_position"))
    sales_count = _number(fields.get("sales_count"))
    gmv = _number(fields.get("gmv") or fields.get("total_revenue"))
    score = 68
    notes = ["平台原生榜单信号优先级高于普通选品平台链接，应进入 Product Intelligence 和 Competitor Intelligence。"]

    if any(word in marketplace for word in ["amazon", "tiktok", "tk", "etsy", "walmart", "shein"]):
        score += 8
        notes.append("来源是目标销售平台本身，代表平台内部需求或平台推荐信号。")
    if any(word in ranking_type for word in ["bsr", "bs.new", "bs/new", "best sellers", "movers", "new releases", "榜单", "ranking"]):
        score += 10
        notes.append("已记录榜单类型，可用于区分老爆品、新品爆发、短期异动和类目长期需求。")
    if rank_position is not None:
        if rank_position <= 10:
            score += 12
            notes.append(f"排名进入 Top {int(rank_position)}，优先拆解关键词、价格、评论和素材方向。")
        elif rank_position <= 100:
            score += 7
            notes.append(f"排名进入 Top {int(rank_position)}，适合进入观察池。")
    if sales_count is not None and sales_count > 0:
        score += min(10, sales_count / 100)
        notes.append(f"榜单销量已记录：{sales_count}。")
    if gmv is not None and gmv > 0:
        score += min(10, gmv / 10_000)
        notes.append(f"榜单 GMV 已记录：{gmv}。")
    if fields.get("table_snapshot") or fields.get("metric_lines"):
        score += 6
        notes.append("已采集页面表格/指标，可用于对照排名和页面真实展示。")

    return {
        "priority": round(min(score, 100), 2),
        "platform_watch_type": "native_marketplace_ranking",
        "training_weight": "highest",
    }, notes


def score_tk_rule(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    risk_level = str(fields.get("risk_level", "")).lower()
    risk_score = {
        "低": 40,
        "low": 40,
        "中": 60,
        "medium": 60,
        "高": 80,
        "high": 80,
        "致命": 100,
        "critical": 100,
    }.get(risk_level, 70)
    notes = ["TK 规则变化应进入风控和 SOP 更新队列。"]
    if risk_score >= 80:
        notes.append("高风险规则，需要当天检查选品、Listing、广告和达人动作。")
    return {
        "priority": risk_score,
        "risk_score": risk_score,
        "training_weight": "high",
    }, notes


def score_store_health(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    account_status = str(fields.get("account_status") or "").lower()
    health_status = str(fields.get("health_status") or "").lower()
    combined_status = f"{account_status} {health_status}"
    pending_rectification = _number(fields.get("pending_rectification_count")) or 0
    appealable = _number(fields.get("appealable_violation_count")) or 0
    rejected_products = _number(fields.get("rejected_product_count")) or 0
    low_inventory = _number(fields.get("low_inventory_count")) or 0
    pending_shipments = _number(fields.get("pending_shipment_count")) or 0
    pending_after_sales = _number(fields.get("pending_after_sales_count")) or 0

    score = 65
    notes: list[str] = ["店铺健康事件应排在每日运营动作最前面，先判断店铺是否还能正常经营。"]
    store_operable = True
    recommended_action = "继续日常经营检查，并跟进待办项。"

    if any(word in combined_status for word in ["停用", "封", "disabled", "suspended", "deactivated"]):
        score = 100
        store_operable = False
        recommended_action = "暂停增长动作，优先进入店铺健康页查看违规原因、申诉窗口和可恢复路径。"
        notes.append("当前店铺疑似被封/停用，选品、达人、广告、Listing 动作全部降级，先处理账号健康。")
    elif pending_rectification > 0:
        score = max(score, 92)
        recommended_action = "先处理待整改违规，再恢复增长动作。"
        notes.append(f"待整改违规：{int(pending_rectification)}。")
    elif appealable > 0:
        score = max(score, 88)
        recommended_action = "检查可申诉违规的证据和截止时间。"
        notes.append(f"可申诉违规：{int(appealable)}。")

    if rejected_products > 0:
        score = max(score, 76)
        notes.append(f"被拒商品：{int(rejected_products)}，需要回看 Listing、类目和素材合规。")
    if low_inventory > 0:
        score = max(score, 62)
        notes.append(f"低库存商品：{int(low_inventory)}，供应链模块应同步检查库存。")
    if pending_shipments > 0:
        score = max(score, 70)
        notes.append(f"待发货订单：{int(pending_shipments)}，履约风险需要当天处理。")
    if pending_after_sales > 0:
        score = max(score, 70)
        notes.append(f"售后待处理：{int(pending_after_sales)}，避免影响店铺健康评分。")

    return {
        "priority": round(min(score, 100), 2),
        "store_operable": store_operable,
        "recommended_action": recommended_action,
        "training_weight": "highest",
    }, notes


def score_store_profile(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    required = {
        "store_id": "店铺编号",
        "marketplace": "平台",
        "country_code": "国家代码",
        "currency": "币种",
        "timezone": "时区",
        "language": "语言",
        "bit_profile_id": "Bit窗口",
        "ip_region": "IP区域",
        "fulfillment_model": "履约模式",
    }
    missing = [label for key, label in required.items() if not fields.get(key)]
    score = 45 + (len(required) - len(missing)) * 6
    notes: list[str] = ["店铺档案用于多国家、多平台、多Bit窗口分类，是后续自动运营和风险隔离的基础。"]

    if not missing:
        score += 15
        notes.append("核心适配字段已完整，可以进入按国家/平台分组的运营监控。")
    else:
        notes.append("还缺适配字段：" + "、".join(missing) + "。")

    if fields.get("credential_ref") or fields.get("legal_entity_ref"):
        notes.append("敏感信息应只保存引用，不要在备注或原始文本里保存明文密码、法人证件或邮箱密码。")
    if fields.get("ip_region") and fields.get("country_code"):
        notes.append("已记录 IP 区域和国家，可用于检查 Bit 浏览器窗口与店铺地区是否一致。")

    return {
        "priority": round(min(score, 100), 2),
        "adaptation_ready": not missing,
        "missing_fields": missing,
        "training_weight": "highest",
    }, notes


def score_store_operation(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    operation_type = str(fields.get("operation_type") or "").lower()
    path = str(fields.get("operation_path") or fields.get("observed_path") or "")
    blocked_by = str(fields.get("blocked_by") or "")
    score = 62
    notes: list[str] = ["店铺后台执行路径已记录，可转成运营 SOP 和自动化导航步骤。"]

    if any(word in operation_type + path for word in ["添加商品", "上架", "listing", "商品图片", "标题", "描述"]):
        score = max(score, 86)
        notes.append("这是 Listing 执行入口，会影响商品上架、主图、标题、描述、价格和库存。")
    if any(word in operation_type + path for word in ["折扣", "促销", "活动", "campaign", "promotion"]):
        score = max(score, 84)
        notes.append("这是促销/活动入口，需要和利润、库存、活动叠加规则一起判断。")
    if any(word in operation_type + path for word in ["达人", "联盟", "affiliate", "creator"]):
        score = max(score, 80)
        notes.append("这是达人联盟执行入口，可连接 Influencer Hunter 和 Influencer CRM。")
    if any(word in blocked_by for word in ["封", "停用", "disabled", "suspended"]):
        score = 94
        notes.append("该路径被封店/停用状态阻塞，自动化执行前必须先检查店铺健康。")

    required_inputs = fields.get("required_inputs")
    if required_inputs:
        notes.append(f"执行前所需输入：{required_inputs}")

    return {
        "priority": round(min(score, 100), 2),
        "operation_status": fields.get("operation_status") or ("blocked" if blocked_by else "observed"),
        "training_weight": "high",
    }, notes


def score_viral_content(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    previous_views = _number(fields.get("previous_views"))
    current_views = _number(fields.get("current_views"))
    growth_multiplier = _number(fields.get("growth_multiplier"))
    notes: list[str] = ["爆款内容信号应优先进入内容拆解队列，它可能比产品本身更能解释销量差距。"]
    score = 70

    if growth_multiplier is None and previous_views and current_views:
        growth_multiplier = current_views / max(previous_views, 1)

    if current_views is not None:
        if current_views >= 1_000_000:
            score += 15
            notes.append("播放量已进入百万级，优先拆钩子、场景和评论区购买动机。")
        elif current_views >= 100_000:
            score += 8
            notes.append("播放量达到可观察爆款级别，适合进入 watchlist。")
    if growth_multiplier is not None:
        if growth_multiplier >= 50:
            score += 15
            notes.append(f"播放增长倍数约 {growth_multiplier:.1f}，疑似短期爆发素材。")
        elif growth_multiplier >= 10:
            score += 8
            notes.append(f"播放增长倍数约 {growth_multiplier:.1f}，需要监控后续 24-72 小时。")
    if fields.get("comment_insights") or fields.get("purchase_intent_comments"):
        score += 8
        notes.append("评论区已有购买意向或需求信号，应优先提取购买原因。")
    if fields.get("product_theme") or fields.get("content_theme"):
        score += 5
        notes.append("内容主题已记录，可连接关键词、达人和 Listing 方向。")

    return {
        "priority": round(min(score, 100), 2),
        "analysis_status": "needs_video_breakdown",
        "training_weight": "highest",
    }, notes


def score_creator_spike(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    baseline = _number(fields.get("baseline_avg_views"))
    latest = _number(fields.get("latest_video_views"))
    spike_multiplier = _number(fields.get("spike_multiplier"))
    notes: list[str] = ["达人异动要连接 Influencer Hunter：不是只看粉丝数，而是看近期内容是否突然打穿人群。"]
    score = 68

    if spike_multiplier is None and baseline and latest:
        spike_multiplier = latest / max(baseline, 1)

    if spike_multiplier is not None:
        if spike_multiplier >= 30:
            score += 20
            notes.append(f"达人最新视频约为历史均播 {spike_multiplier:.1f} 倍，标记为疑似爆款达人。")
        elif spike_multiplier >= 10:
            score += 12
            notes.append(f"达人最新视频约为历史均播 {spike_multiplier:.1f} 倍，进入优先观察名单。")
    if latest is not None and latest >= 100_000:
        score += 8
        notes.append("最新视频播放较高，适合回看评论区和同类历史内容。")
    if fields.get("recommended_creator_type") or fields.get("audience_profile"):
        score += 5
        notes.append("达人画像已记录，可反哺寄样优先级和内容方向。")

    grade = "A-watch" if score >= 85 else "B-watch" if score >= 72 else "C-observe"
    return {
        "priority": round(min(score, 100), 2),
        "creator_watch_grade": grade,
        "training_weight": "highest",
    }, notes


def score_video_breakdown(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    score = 62
    notes: list[str] = ["视频拆解是 Content Director 的核心训练样本，优先提取结构、钩子、人群、场景、情绪和评论区。"]

    if fields.get("timeline_structure"):
        score += 10
        notes.append("已记录分秒结构，可直接生成复刻脚本骨架。")
    if fields.get("hook_text") or fields.get("hook"):
        score += 10
        notes.append("已记录开头钩子，应分类为情绪、反转、身份认同或争议。")
    if fields.get("audience_profile") or fields.get("audience_identity"):
        score += 8
        notes.append("已记录人群画像，可连接文化标签和关键词库。")
    if fields.get("scene"):
        score += 6
        notes.append("已记录场景，可复用到拍摄清单。")
    if fields.get("emotion"):
        score += 6
        notes.append("已记录情绪价值，可判断产品卖的是身份、陪伴、信仰还是归属感。")
    if fields.get("comment_insights") or fields.get("purchase_intent_comments"):
        score += 8
        notes.append("评论区洞察已记录，可提取购买原因和转化词。")
    if fields.get("replicate_plan") or fields.get("recommended_variations"):
        score += 10
        notes.append("已有复刻方案，应输出 Dog Dad / Fishing / Mechanic 等变体。")

    return {
        "priority": round(min(score, 100), 2),
        "replication_ready": score >= 82,
        "training_weight": "highest",
    }, notes


def score_video_script(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    script_type = str(fields.get("script_type") or "").lower()
    score = 58
    notes: list[str] = ["视频脚本是 Content Director 的可执行资产，需要同时沉淀店铺自播脚本和达人合作脚本。"]

    if any(word in script_type for word in ["store", "owned", "店铺", "自播"]):
        score += 8
        notes.append("这是店铺自播/自有素材脚本，应绑定目标店铺、产品展示点、主图/详情页承接和可复拍镜头。")
    if any(word in script_type for word in ["influencer", "creator", "达人"]):
        score += 8
        notes.append("这是达人脚本/达人 brief，应明确达人类型、自由发挥边界、寄样重点和不可说内容。")
    if fields.get("hook_text") or fields.get("hook"):
        score += 10
        notes.append("已记录开头 Hook，适合直接进入拍摄清单。")
    if fields.get("shot_list") or fields.get("timeline_structure"):
        score += 10
        notes.append("已记录镜头清单，可交给店铺拍摄或达人执行。")
    if fields.get("voiceover") or fields.get("spoken_text") or fields.get("script_lines"):
        score += 8
        notes.append("已记录口播/话术，可用于字幕和达人 brief。")
    if fields.get("on_screen_text") or fields.get("caption_text"):
        score += 6
        notes.append("已记录屏幕字幕，适合短视频前 2 秒钩子强化。")
    if fields.get("cta"):
        score += 6
        notes.append("已记录 CTA，可以连接店铺购买路径或达人挂车动作。")
    if fields.get("product_showcase_points"):
        score += 6
        notes.append("已记录产品展示点，能减少脚本好看但不转化的问题。")
    if fields.get("creator_brief") or fields.get("target_creator_type"):
        score += 6
        notes.append("已记录达人执行要求，可用于 Influencer Hunter/CRM 派单。")
    if fields.get("usage_guardrails"):
        score += 4
        notes.append("已记录禁区/注意事项，有助于规避平台和宣传风险。")

    script_channel = "store_owned"
    if any(word in script_type for word in ["influencer", "creator", "达人"]):
        script_channel = "influencer_brief"

    return {
        "priority": round(min(score, 100), 2),
        "script_channel": script_channel,
        "production_ready": score >= 82,
        "training_weight": "highest",
    }, notes


def score_social_account_profile(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    role = str(fields.get("account_role") or "").lower()
    bind_status = str(fields.get("aip_bind_status") or "").lower()
    can_publish = _truthy(fields.get("can_publish_video"))
    score = 56
    notes: list[str] = [
        "已保存视频账号资料。每个店铺建议先配 1 个官方号和 4 个渠道号，再放大内容发布。",
    ]

    if fields.get("store_id") or fields.get("target_store_id"):
        score += 8
    if fields.get("account_handle") or fields.get("official_account_handle") or fields.get("channel_account_handles"):
        score += 10
    if "official" in role or "官方" in role:
        score += 8
        notes.append("官方号：用于品牌信任、主推品教育、售后信任和稳定商品卡承接。")
    if "channel" in role or "渠道" in role:
        score += 7
        notes.append("渠道号：用于角度测试、细分人群、种草内容和小规模实验。")
    if fields.get("aip_provider"):
        score += 10
        notes.append("已记录 AIP 发视频软件。登录、授权和真实发布仍然必须人工确认。")
    if "bound" in bind_status or "绑定" in bind_status or can_publish:
        score += 10
        notes.append("看起来具备发布能力，但视频发布仍然进入确认队列。")
    else:
        notes.append("AIP 绑定或发视频权限还没有确认。")
    if fields.get("music_guardrails"):
        score += 4

    return {
        "priority": round(min(score, 100), 2),
        "account_matrix_type": "tk_video_account",
        "video_account_role": role or "unknown",
        "requires_aip_binding": not (fields.get("aip_provider") and ("bound" in bind_status or "绑定" in bind_status or can_publish)),
        "can_publish_video": bool(can_publish),
        "music_policy_required": True,
        "requires_confirmation_for_publish": True,
        "training_weight": "high",
    }, notes


def score_video_publish_plan(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    score = 46
    notes: list[str] = ["已保存视频发布计划。系统只准备素材包，真实 TikTok/AIP 发布必须进入确认队列。"]
    missing: list[str] = []
    for key, label, points in [
        ("store_id", "目标店铺", 6),
        ("target_account_handle", "目标账号", 8),
        ("aip_provider", "AIP 发视频软件", 8),
        ("video_file_ref", "视频/图片素材", 10),
        ("publish_title", "发布标题", 8),
        ("publish_tags", "标签", 6),
    ]:
        if fields.get(key) or (key == "store_id" and fields.get("target_store_id")):
            score += points
        else:
            missing.append(label)

    music_status = str(fields.get("music_license_status") or "").lower()
    music_volume = _number(fields.get("music_volume"))
    original_volume = _number(fields.get("original_audio_volume") or fields.get("voiceover_volume"))
    unsafe_music = any(word in music_status for word in ["unauthorized", "unlicensed", "unknown", "copyright_risk", "risk", "unapproved", "待确认", "未授权"])
    safe_music = any(word in music_status for word in ["royalty_free", "commercial", "licensed", "tiktok_library", "safe", "approved", "商用", "曲库", "已授权"])
    music_too_loud = music_volume is not None and music_volume > 0.35
    voice_too_low = original_volume is not None and original_volume < 0.65

    if safe_music:
        score += 8
        notes.append("音乐已标记为商用安全或已授权。")
    elif unsafe_music or fields.get("music_name"):
        notes.append("音乐发布前需要复核，不能使用版权不清或未授权音乐。")
    else:
        notes.append("还没有记录音乐选择，优先使用 TikTok 商用曲库、已授权或原创音频。")
    if music_volume is not None:
        if music_too_loud:
            notes.append("BGM 音量偏高，建议控制在 15%-30%，不要盖过口播和产品声音。")
        else:
            score += 4
            notes.append("BGM 音量可控。")
    if original_volume is not None:
        if voice_too_low:
            notes.append("原声/口播音量偏低，建议保持在 65%-70% 以上，保证产品解释和钩子清楚。")
        else:
            score += 4

    blocks_auto_publish = bool(missing or unsafe_music or music_too_loud or voice_too_low)
    publish_ready = not blocks_auto_publish and score >= 78
    return {
        "priority": round(min(score, 100), 2),
        "publish_ready": publish_ready,
        "missing_publish_fields": missing,
        "music_license_safe": safe_music and not unsafe_music,
        "music_too_loud": music_too_loud,
        "voice_too_low": voice_too_low,
        "blocks_auto_publish": blocks_auto_publish,
        "requires_confirmation_for_publish": True,
        "training_weight": "high",
    }, notes

    score = 46
    notes: list[str] = [
        "Video publish plan saved. The system can prepare the package, but real TikTok/AIP posting must stay in the confirmation queue.",
    ]
    missing: list[str] = []
    for key, label, points in [
        ("store_id", "target store", 6),
        ("target_account_handle", "target account", 8),
        ("aip_provider", "AIP publisher/provider", 8),
        ("video_file_ref", "video asset", 10),
        ("publish_title", "publish title", 8),
        ("publish_tags", "hashtags/tags", 6),
    ]:
        if fields.get(key) or (key == "store_id" and fields.get("target_store_id")):
            score += points
        else:
            missing.append(label)

    music_status = str(fields.get("music_license_status") or "").lower()
    music_volume = _number(fields.get("music_volume"))
    original_volume = _number(fields.get("original_audio_volume") or fields.get("voiceover_volume"))
    unsafe_music = any(word in music_status for word in ["unauthorized", "unlicensed", "unknown", "copyright_risk", "风险", "未知", "未授权"])
    safe_music = any(word in music_status for word in ["royalty_free", "commercial", "licensed", "tiktok_library", "safe", "已授权", "商用"])
    music_too_loud = music_volume is not None and music_volume > 0.35
    voice_too_low = original_volume is not None and original_volume < 0.65

    if safe_music:
        score += 8
        notes.append("Music is marked as commercially safe/licensed.")
    elif unsafe_music or fields.get("music_name"):
        notes.append("Music needs review before posting. Avoid copyrighted tracks and unclear commercial-use music.")
    else:
        notes.append("No music choice recorded yet. Prefer TikTok commercial library or clearly licensed audio.")
    if music_volume is not None:
        if music_too_loud:
            notes.append("BGM volume is too high. Keep music around 15%-30% so it does not cover voice/product sound.")
        else:
            score += 4
            notes.append("BGM volume looks controlled.")
    if original_volume is not None:
        if voice_too_low:
            notes.append("Original/voice audio is too low. Keep it above 65%-70% for product explanation and hooks.")
        else:
            score += 4

    blocks_auto_publish = bool(missing or unsafe_music or music_too_loud or voice_too_low)
    publish_ready = not blocks_auto_publish and score >= 78
    return {
        "priority": round(min(score, 100), 2),
        "publish_ready": publish_ready,
        "missing_publish_fields": missing,
        "music_license_safe": safe_music and not unsafe_music,
        "music_too_loud": music_too_loud,
        "voice_too_low": voice_too_low,
        "blocks_auto_publish": blocks_auto_publish,
        "requires_confirmation_for_publish": True,
        "training_weight": "high",
    }, notes


def score_creative_inspiration(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    score = 54
    notes: list[str] = [
        "Creative inspiration saved. It should combine historical hooks, titles, tags, scripts, comments, and performance data without copying competitor assets.",
    ]
    if fields.get("product_name") or fields.get("product_theme"):
        score += 8
    if fields.get("creative_angle") or fields.get("content_angle"):
        score += 10
        notes.append("Creative angle is defined.")
    if fields.get("source_hooks") or fields.get("source_titles") or fields.get("source_tags") or fields.get("derived_from_memory"):
        score += 12
        notes.append("Historical creative memory is referenced.")
    if fields.get("original_shot_plan") or fields.get("shot_list"):
        score += 10
        notes.append("Original shot plan is available for shooting or AI video generation.")
    if fields.get("creative_prompt"):
        score += 8
        notes.append("Generation prompt is ready for images/video/material production.")
    if fields.get("reuse_boundaries") or fields.get("usage_guardrails"):
        score += 8
        notes.append("Reuse boundary is recorded, reducing IP/copycat risk.")
    originality = str(fields.get("originality_type") or "").lower()
    if any(word in originality for word in ["original", "原创", "new"]):
        score += 6
    return {
        "priority": round(min(score, 100), 2),
        "creative_memory_ready": score >= 78,
        "requires_ip_check": True,
        "requires_confirmation_for_upload": True,
        "training_weight": "high",
    }, notes


def score_knowledge_asset(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    filled = sum(1 for value in fields.values() if value not in {"", None})
    return {
        "priority": min(100, 45 + filled * 6),
        "training_weight": "high",
    }, ["文化/节日资产已记录，会影响关键词、标题、素材和达人搜索。"]


def score_industry_research_asset(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    asset_type = str(fields.get("research_asset_type") or "").lower()
    score = 58
    notes: list[str] = [
        "跨境行业研究资产用于训练 AI Ecommerce Director 的行业脑：先拆解、分析、归档，再进入选品、内容、达人、Listing 或 POD 执行。"
    ]

    if asset_type:
        score += 8
        notes.append(f"已标记研究资产类型：{asset_type}。")
    if fields.get("industry_scope") or fields.get("marketplace"):
        score += 6
        notes.append("已绑定行业/平台范围，后续可以按 TikTok、Amazon、Shopify、POD 等场景筛选。")
    if fields.get("brand_name") or fields.get("product_name"):
        score += 6
        notes.append("已记录品牌或产品对象，可进入品牌库/产品库。")
    if fields.get("user_pain_point"):
        score += 8
        notes.append("已提取用户痛点，可反推产品机会、详情页卖点和内容钩子。")
    if fields.get("keyword_cluster"):
        score += 8
        notes.append("已提取关键词簇，可进入 Keyword Hunter 和 Listing Builder。")
    if fields.get("content_account") or fields.get("account_type"):
        score += 6
        notes.append("已记录内容账号或内容类型，可进入内容账号库和达人/素材监控。")
    if fields.get("competitor_site_url") or fields.get("navigation_pattern") or fields.get("collection_logic"):
        score += 8
        notes.append("已记录竞品网站结构，可用于 Product Analyst 拆页面、流程和转化路径。")
    if fields.get("knowledge_node") or fields.get("process_stage"):
        score += 6
        notes.append("已沉淀知识地图节点，可连接选品、供应链、物流、平台运营、合规等流程。")
    if fields.get("opportunity"):
        score += 8
        notes.append("已形成机会点，下一步要转成可验证任务。")
    if fields.get("validation_task"):
        score += 8
        notes.append("已写入验证任务，适合进入周度研究和小样本测试队列。")
    if fields.get("update_frequency"):
        score += 4
        notes.append("已设置更新频率，可纳入持续生长的行业研究节奏。")

    if not fields.get("validation_task"):
        notes.append("建议补充下一步验证任务，例如查榜单、看评论、抓近 90 天内容或拆 3 个竞品页面。")

    return {
        "priority": round(min(score, 100), 2),
        "training_weight": "high",
        "research_status": "ready_for_validation" if fields.get("validation_task") else "needs_validation_task",
        "research_asset_type": fields.get("research_asset_type") or "general_research",
    }, notes


def score_compliance_term(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    severity = str(fields.get("severity") or fields.get("risk_level") or "").lower()
    risk_category = str(fields.get("risk_category") or "").lower()
    score = 72
    notes: list[str] = ["违禁词/侵权风险词应进入 Risk Director，在生成标题、卖点、标签、素材脚本和达人 brief 前先扫描。"]

    if fields.get("term"):
        score += 8
        notes.append("已记录风险词，可用于 Listing、标题、标签和脚本扫描。")
    if any(word in severity for word in ["high", "critical", "高", "严重", "致命"]):
        score += 16
        notes.append("高风险词，命中后应阻止自动发布并进入人工复核。")
    elif any(word in severity for word in ["medium", "中"]):
        score += 8
        notes.append("中风险词，命中后应提示替换表达并复核上下文。")
    if any(word in risk_category for word in ["trademark", "copyright", "patent", "商标", "版权", "专利", "侵权"]):
        score += 10
        notes.append("属于知识产权风险，优先检查商标、版权、专利和平台政策。")
    if fields.get("applies_to_platform"):
        score += 5
        notes.append("已绑定适用平台，可按 TikTok Shop、Amazon、Etsy、Walmart、SHEIN 等分别扫描。")
    if fields.get("safe_replacement"):
        score += 5
        notes.append("已提供安全替代表达，后续可自动生成替换建议。")
    if fields.get("detection_rule"):
        score += 4
        notes.append("已提供检测规则，可用于批量扫描标题、五点、标签、图片文案和脚本。")

    return {
        "priority": round(min(score, 100), 2),
        "training_weight": "highest",
        "risk_scan_required": True,
        "blocks_auto_publish": score >= 88,
    }, notes


def score_ip_image_risk(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    severity = str(fields.get("severity") or fields.get("risk_level") or fields.get("delist_priority") or "").lower()
    tro_status = str(fields.get("tro_status") or "").lower()
    category = str(fields.get("element_category") or fields.get("risk_category") or "").lower()
    authorization_status = str(
        fields.get("authorization_status")
        or fields.get("license_status")
        or fields.get("brand_authorization_status")
        or fields.get("ip_authorization_status")
        or ""
    ).lower()
    has_authorization = bool(
        fields.get("authorization_proof")
        or fields.get("license_agreement_url")
        or fields.get("brand_authorization_file")
        or any(word in authorization_status for word in ["authorized", "licensed", "approved", "allowed", "permitted", "已授权", "允许", "许可", "可上架"])
    )
    has_tro_or_notice = bool(fields.get("case_number") or "tro" in tro_status or fields.get("platform_notice_url") or fields.get("complaint_url"))
    score = 78
    notes: list[str] = ["All-platform IP risk should enter Risk Director. This includes product images, listing text, videos, ads, scripts, POD artwork, brand marks, copyrighted artwork, celebrity likeness, TROs, and platform complaints."]

    if fields.get("risk_element") or fields.get("visual_signature"):
        score += 8
        notes.append("已记录具体图片/图案风险元素，可用于扫描主图、设计图、Listing和素材。")
    if fields.get("rights_owner") or fields.get("plaintiff") or fields.get("trademark_owner"):
        score += 8
        notes.append("已记录权利人/原告信息，适合建立TRO与品牌/IP风险库。")
    if fields.get("case_number") or "tro" in tro_status:
        score += 12
        notes.append("已出现TRO或案号线索，相关链接应进入优先下架复核队列。")
    if fields.get("image_url") or fields.get("evidence_url") or fields.get("screenshot_path"):
        score += 6
        notes.append("已保存图片或证据链接，可作为人工复核依据。")
    if fields.get("infringing_listing_url"):
        score += 10
        notes.append("已绑定疑似侵权商品链接，后续可生成待确认下架动作。")
    if any(word in severity for word in ["critical", "high", "urgent", "tro", "严重", "高", "立即"]):
        score += 10
        notes.append("高优先级图片/IP风险，建议当天复核并处理相关链接。")
    if any(word in category for word in ["brand", "logo", "character", "celebrity", "team", "movie", "cartoon", "trademark", "copyright", "品牌", "商标", "人物", "球队", "影视", "版权"]):
        score += 6
        notes.append("该元素属于POD常见高风险图案类型，发布前必须拦截。")
    if fields.get("safe_design_rule"):
        score += 4
        notes.append("已记录安全设计规则，可用于后续改图或替代设计。")

    if has_authorization:
        score -= 18
        notes.append("Authorization/license proof is recorded. Do not auto-delist this item; keep authorization evidence, scope, channels, and expiration date on file.")
    elif fields.get("infringing_listing_url"):
        notes.append("No authorization proof found for this listing. Block auto-publish and send it to manual authorization review.")

    final_score = round(min(score, 100), 2)
    requires_authorization_review = bool(not has_authorization and (fields.get("infringing_listing_url") or final_score >= 88 or has_tro_or_notice))
    return {
        "priority": final_score,
        "training_weight": "highest",
        "risk_scan_required": True,
        "blocks_auto_publish": bool(not has_authorization),
        "requires_delist_review": bool(not has_authorization and has_tro_or_notice),
        "requires_authorization_review": requires_authorization_review,
        "authorized_for_listing": has_authorization,
        "risk_watch_type": "all_platform_ip_tro",
    }, notes


def score_review_insight(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    score = 62
    notes: list[str] = ["评论/差评/投诉洞察应进入 Product Intelligence、Listing Builder、Content Director 和 Risk Director。"]
    evidence_count = _number(fields.get("evidence_count")) or 0
    review_type = str(fields.get("review_type") or "").lower()
    sentiment = str(fields.get("sentiment") or "").lower()

    if fields.get("review_source"):
        score += 5
        notes.append("已记录评论来源，可区分同行竞品评论和自己店铺客诉。")
    if any(word in review_type + sentiment for word in ["bad", "negative", "1-star", "one star", "差评", "负面", "一星"]):
        score += 10
        notes.append("负面评论优先级较高，应反推产品缺陷和详情页预期管理。")
    if fields.get("pain_point") or fields.get("defect_area"):
        score += 12
        notes.append("已提取痛点/问题部位，可用于选品避坑、供应链改良和素材解释。")
    if fields.get("refund_reason"):
        score += 8
        notes.append("已记录退款/退货原因，应连接售后、品控和页面描述。")
    if evidence_count:
        score += min(12, evidence_count)
        notes.append(f"已记录证据数量：{int(evidence_count)}。")
    if fields.get("suggested_fix"):
        score += 6
        notes.append("已有修复建议，可进入待确认的产品/Listing/素材优化草稿。")
    if fields.get("listing_implication"):
        score += 5
        notes.append("已标记 Listing 影响，可反推标题、卖点、FAQ、尺码/材质说明。")
    if fields.get("content_implication"):
        score += 5
        notes.append("已标记素材影响，可用于视频脚本和达人 brief。")

    return {
        "priority": round(min(score, 100), 2),
        "training_weight": "highest",
        "review_watch_type": "negative_review_or_complaint",
        "requires_fix_draft": bool(fields.get("pain_point") or fields.get("suggested_fix")),
    }, notes


def score_feedback_ticket(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    feedback_type = str(fields.get("feedback_type") or fields.get("review_type") or "").lower()
    severity = str(fields.get("severity") or "").lower()
    text = " ".join(
        str(fields.get(key) or "")
        for key in ["feedback_text", "actual_behavior", "expected_behavior", "suggestion", "annotation_notes"]
    ).lower()
    score = 50
    notes: list[str] = ["User feedback ticket saved for AI analysis, product improvement, and fix planning."]
    if fields.get("module_area") or fields.get("page_url"):
        score += 8
        notes.append("Module/page is identified, so the issue can be routed to the right area.")
    if fields.get("screenshot_path") or fields.get("annotated_image_path"):
        score += 12
        notes.append("Screenshot or annotated evidence is attached.")
    if fields.get("feedback_text"):
        score += 8
    if fields.get("expected_behavior") and fields.get("actual_behavior"):
        score += 10
        notes.append("Expected vs actual behavior is clear.")
    if any(word in severity for word in ["critical", "high", "严重", "紧急"]) or any(word in text for word in ["can't use", "cannot use", "打不开", "不能用", "崩", "错", "bug"]):
        score += 18
    elif any(word in severity for word in ["medium", "中"]):
        score += 8
    category = "suggestion"
    if any(word in feedback_type + text for word in ["bug", "error", "broken", "崩", "报错", "打不开", "不能用"]):
        category = "bug"
    elif any(word in feedback_type + text for word in ["data", "wrong", "偏差", "不准", "数据"]):
        category = "data_accuracy"
    elif any(word in feedback_type + text for word in ["ui", "ugly", "不好看", "看不懂", "界面", "体验"]):
        category = "ux_ui"
    elif any(word in feedback_type + text for word in ["feature", "新增", "希望", "建议", "功能"]):
        category = "feature_request"
    elif any(word in feedback_type + text for word in ["strategy", "运营", "选品", "投流", "素材", "策略"]):
        category = "operation_strategy"
    return {
        "priority": round(min(score, 100), 2),
        "feedback_category": category,
        "requires_triage": True,
        "requires_fix_draft": category in {"bug", "data_accuracy", "ux_ui", "feature_request"},
        "has_visual_evidence": bool(fields.get("screenshot_path") or fields.get("annotated_image_path")),
        "training_weight": "high",
    }, notes


def score_collection_job(fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    score = 66
    notes: list[str] = ["平台采集任务用于让 AI Director 选择 API、平台巡检、插件或人工投喂路径，把历史和当前数据收入数据库。"]

    if fields.get("platform_list") or fields.get("marketplace"):
        score += 8
        notes.append("已指定平台范围，可按平台选择 API 或浏览器采集路径。")
    if fields.get("data_window"):
        score += 8
        notes.append("已指定历史/当前数据窗口，可区分历史复盘和今日监控。")
    if fields.get("collection_target"):
        score += 10
        notes.append("已指定采集目标，例如榜单、爆款视频、评论、差评、达人、关键词或店铺数据。")
    if fields.get("analysis_task"):
        score += 8
        notes.append("已指定 AI 分析任务，可路由到行业研究、竞品、视频、评论或风控模块。")
    if fields.get("source_type"):
        score += 4
        notes.append("已指定数据源类型，可优先 API，其次插件/只读页面巡检。")

    return {
        "priority": round(min(score, 100), 2),
        "training_weight": "high",
        "collection_status": "ready",
        "read_only": True,
    }, notes


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("$", "")
        if text.endswith("%"):
            try:
                return float(text[:-1]) / 100
            except ValueError:
                return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y", "ok", "enabled", "available", "bound", "绑定", "是", "可发", "已绑定"}
