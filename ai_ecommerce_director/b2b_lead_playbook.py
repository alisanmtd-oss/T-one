from __future__ import annotations

import html
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


B2B_MAIN_ROUTE = {
    "business_line": "wholesale_tshirts_and_machines",
    "ownership": "teelab_b2b_sales",
    "route_key": "b2b:GLOBAL:teelab_sales",
    "visible_label": "外贸 B2B / 批发 T 恤 / 后续机器设备 / TeeLab 自营销售",
}


@dataclass(frozen=True, slots=True)
class B2BLeadSource:
    source_id: str
    title: str
    customer_fit: tuple[str, ...]
    search_examples: tuple[str, ...]
    lead_signals: tuple[str, ...]
    private_domain_path: tuple[str, ...]
    automation_boundary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "customer_fit": list(self.customer_fit),
            "search_examples": list(self.search_examples),
            "lead_signals": list(self.lead_signals),
            "private_domain_path": list(self.private_domain_path),
            "automation_boundary": self.automation_boundary,
        }


@dataclass(frozen=True, slots=True)
class B2BTargetSegment:
    segment_id: str
    title: str
    first_offer: str
    later_machine_offer: str
    qualify_questions: tuple[str, ...]
    score_boosters: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "title": self.title,
            "first_offer": self.first_offer,
            "later_machine_offer": self.later_machine_offer,
            "qualify_questions": list(self.qualify_questions),
            "score_boosters": list(self.score_boosters),
        }


B2B_LEAD_SOURCES: tuple[B2BLeadSource, ...] = (
    B2BLeadSource(
        "customs_import_data",
        "海关 / 进出口数据",
        ("服装进口商", "批发商", "品牌采购", "区域分销商", "有固定补货节奏的企业买家"),
        (
            "HS code + cotton t-shirt importer + US",
            "blank t-shirt importer Mexico",
            "apparel wholesaler import records",
        ),
        ("重复进口", "采购国家稳定", "收货公司真实", "货量增长", "同类供应商切换"),
        ("Email", "LinkedIn", "官网表单", "WhatsApp after opt-in"),
        "可做公开/授权数据研究和线索评分；购买名单、批量外联、导出第三方数据库必须负责人确认。",
    ),
    B2BLeadSource(
        "maps_local_business",
        "地图 / 本地商家目录",
        ("T 恤印花店", "DTF/DTG 店", "刺绣店", "校服工服供应商", "促销礼品公司"),
        (
            "screen printing near me Dallas",
            "custom t shirts Miami",
            "DTF printing Los Angeles",
            "uniform supplier Toronto",
        ),
        ("公开官网", "评分和评论量", "营业状态", "报价/批发页面", "WhatsApp 或 Email 可见"),
        ("官网表单", "Email", "WhatsApp opt-in", "电话人工确认"),
        "不批量抓取或缓存 Google Maps 内容；只保存合规来源、官网线索、Place ID 和人工确认字段。",
    ),
    B2BLeadSource(
        "social_followers_and_content",
        "社交媒体主页 / 内容 / 粉丝 / 评论",
        ("品牌粉丝", "同行粉丝", "评论区采购意向", "代理商账号", "批发商账号", "小 B 店主"),
        (
            "#customtshirts buyer comments",
            "followers of screen printing suppliers",
            "Instagram DTF shop followers",
            "TikTok comments: where can I buy bulk",
        ),
        ("询价评论", "粉丝身份像店主/代理", "主页写 wholesale/agent/distributor", "频繁发布生产/采购内容"),
        ("社媒人工私信", "Lead form", "WhatsApp opt-in", "Email", "CRM"),
        "可识别公开互动和生成草稿；不自动爬 LinkedIn/Instagram，不群发私信，不刷赞或假互动。",
    ),
    B2BLeadSource(
        "independent_store",
        "独立站 / Shopify / WooCommerce / DTC",
        ("服装品牌", "电商卖家", "POD 卖家", "有复购的独立站店铺"),
        (
            'inurl:/collections/t-shirts "wholesale"',
            '"Powered by Shopify" "custom t-shirts"',
            '"bulk order" "t-shirts" "add to quote"',
        ),
        ("T 恤 SKU 多", "上新频繁", "有批发/RFQ 页", "有定制入口", "站点技术栈可判断"),
        ("Email", "联系表单", "Instagram", "WhatsApp after opt-in"),
        "只采公开业务信息和联系入口；提交表单、发邮件、发 DM 前进入确认队列。",
    ),
    B2BLeadSource(
        "marketplace_seller",
        "电商平台卖家 / 店铺主页",
        ("Amazon/Etsy/eBay/Walmart 卖家", "TikTok Shop/Shopee/Lazada 卖家", "有 T 恤或周边需求的店铺"),
        (
            "Amazon custom t shirt seller brand website",
            "Etsy bulk custom shirt shop",
            "TikTok Shop apparel seller contact",
        ),
        ("店铺销量/评价", "产品线匹配", "差评暴露面料/交期问题", "独立站或社媒可联系"),
        ("平台外公开官网", "Email", "Instagram", "LinkedIn", "CRM"),
        "不绕平台站内规则导流成交；只用公开官网/社媒做 B2B 合作触达，真实外联需确认。",
    ),
    B2BLeadSource(
        "pod_factory_and_print_shop",
        "POD 工厂 / 印花服务商 / 机器代理",
        ("POD 工厂", "DTF/DTG 服务商", "区域机器代理", "耗材商", "白牌履约商"),
        (
            "white label print on demand supplier",
            "DTF gang sheet provider",
            "apparel decorator directory",
            "DTF printer distributor",
        ),
        ("产能扩张", "招聘操作员", "机器视频", "交期压力", "接短单/多 SKU", "主动找代理"),
        ("Email", "LinkedIn", "WhatsApp", "会议", "样品/测试文件"),
        "机器作为第二阶段机会；先用 T 恤、样品包、耗材或履约合作建立关系。",
    ),
    B2BLeadSource(
        "trade_show_and_b2b_platform",
        "展会 / B2B 平台 / RFQ",
        ("品牌采购", "批发商", "区域代理", "设备买家", "POD 工厂老板"),
        (
            "apparel trade show exhibitors",
            "promotional products distributors",
            "Alibaba RFQ custom t shirt",
            "DTF printer distributor wanted",
        ),
        ("展商身份", "RFQ 数量", "采购时间", "预算", "目的国", "是否要样品"),
        ("平台询盘", "Email", "WhatsApp opt-in", "视频会议", "CRM"),
        "平台内询盘按平台规则回复；外部成交、付款、合同和代理授权必须负责人确认。",
    ),
    B2BLeadSource(
        "ads_and_content_leads",
        "广告表单 / 内容引流",
        ("主动留资客户", "样品包需求", "批发价表需求", "机器 ROI 需求", "代理合作需求"),
        (
            "TikTok Lead Gen: sample pack",
            "Meta Lead Ads: bulk t-shirt price list",
            "YouTube: DTF printer ROI calculator",
        ),
        ("主动填写表单", "选择数量/MOQ", "留下 WhatsApp/Email", "下载价表/ROI 表"),
        ("CRM", "Email automation", "WhatsApp opt-in", "销售跟进"),
        "广告、表单和预算变更需确认；线索进入 CRM 后可自动评分和提醒跟进。",
    ),
)


B2B_TARGET_SEGMENTS: tuple[B2BTargetSegment, ...] = (
    B2BTargetSegment(
        "print_shop",
        "本地 T 恤印花店 / DTF / DTG 店",
        "230g 重磅水洗 T 恤样品包、批发价表、短交期补货",
        "DTF/DTG/热压机、耗材、第二台设备、维护培训",
        ("现在月用多少件空白 T 恤？", "主要做丝印、DTF、DTG 还是刺绣？", "目的国和交期？"),
        ("官网有 bulk/custom quote", "近期生产视频活跃", "评论里有人问价格/交期", "公开 WhatsApp/Email"),
    ),
    B2BTargetSegment(
        "brand_and_dtc",
        "服装品牌 / Shopify / WooCommerce / DTC 店",
        "小批量私标 T 恤、POD 履约、吊牌包装、热卖坯衫",
        "销量稳定后再推自建生产线或合作工厂方案",
        ("现在卖哪些 T 恤款？", "日单量和主要国家？", "是否需要私标包装？"),
        ("T 恤 SKU 多", "上新频繁", "有 wholesale/RFQ", "社媒粉丝真实互动"),
    ),
    B2BTargetSegment(
        "promo_uniform",
        "活动周边 / 校服工服 / 促销礼品公司",
        "大货 T 恤、POLO、帽衫、工服、团体服快速报价",
        "内部打样设备、热压线、绣花/标牌设备",
        ("项目数量多少？", "是否有 logo 文件？", "交期和收货城市？"),
        ("网站写 corporate/uniform/promo", "常接团体订单", "有 rush order 入口"),
    ),
    B2BTargetSegment(
        "marketplace_seller",
        "电商平台卖家 / 独立站卖家",
        "爆款 T 恤补货、套装、低 MOQ 测款、跨境发货",
        "稳定订单后提供机器、仓库或供应链升级方案",
        ("卖哪个平台和国家站点？", "现在月销量多少？", "是否需要一件代发或批量补货？"),
        ("评价多", "差评提到面料/尺码/物流", "有站外官网或社媒"),
    ),
    B2BTargetSegment(
        "agent_distributor",
        "代理商 / 批发商 / 区域分销商",
        "区域批发价表、样品箱、代理政策、长期供货价",
        "区域机器代理、耗材代理、展厅样机",
        ("覆盖哪个国家/城市？", "有多少下游客户？", "想代理 T 恤、机器还是耗材？"),
        ("主页写 distributor/agent/wholesale", "关注同行供应商", "有展会/仓库/团队信息"),
    ),
)


B2B_PIPELINE_STAGES = [
    {"stage": "lead_discovered", "label": "发现线索", "owner": "AI B2B Researcher", "goal": "从公开来源发现公司/主页/粉丝/评论/代理商线索并去重。"},
    {"stage": "enriched", "label": "补全资料", "owner": "AI Data Enricher", "goal": "补国家、城市、官网、社媒、邮箱、WhatsApp、买家类型和证据链接。"},
    {"stage": "qualified", "label": "需求评分", "owner": "AI B2B BD", "goal": "按数量、匹配度、联系方式、预算、活跃度和机器机会评分。"},
    {"stage": "first_touch_drafted", "label": "首触草稿", "owner": "AI Sales Copywriter", "goal": "生成个性化私信/邮件/表单草稿，等待负责人确认后发送。"},
    {"stage": "private_channel_connected", "label": "进入私域", "owner": "AI CRM Operator", "goal": "沉淀 WhatsApp、Email、Instagram、LinkedIn 或表单，记录 opt-in/退订状态。"},
    {"stage": "quote_sent", "label": "报价", "owner": "AI Quote Operator", "goal": "按 100/300/1000 件、样品费、运费、交期、付款方式生成报价。"},
    {"stage": "sample_or_proof", "label": "样品/打样", "owner": "AI Sample Coordinator", "goal": "确认颜色、尺码、图案、包装，机器客户可用测试文件出样。"},
    {"stage": "negotiation", "label": "谈判", "owner": "AI Sales Follow-up", "goal": "跟进价格、交期、付款、包装、质保、代理条款。"},
    {"stage": "won_or_reorder", "label": "成交/复购", "owner": "AI Account Manager", "goal": "PI/定金/生产/QC/发货/售后/补货提醒全链路留档。"},
]


B2B_CRM_FIELDS = [
    "lead_id",
    "source_platform",
    "source_url",
    "source_keyword",
    "country",
    "city",
    "language",
    "company_name",
    "buyer_type",
    "contact_name",
    "role",
    "website",
    "email",
    "whatsapp",
    "instagram",
    "facebook",
    "tiktok",
    "linkedin",
    "youtube",
    "product_line",
    "quantity_hint",
    "budget_hint",
    "destination_country",
    "timeline",
    "demand_summary",
    "evidence",
    "lead_score",
    "stage",
    "owner",
    "next_follow_up_at",
    "last_contact_at",
    "opt_in_status",
    "unsubscribe_status",
    "risk_tags",
]


def build_b2b_lead_playbook_payload() -> dict[str, Any]:
    return {
        "route": dict(B2B_MAIN_ROUTE),
        "sources": [source.to_dict() for source in B2B_LEAD_SOURCES],
        "target_segments": [segment.to_dict() for segment in B2B_TARGET_SEGMENTS],
        "pipeline_stages": list(B2B_PIPELINE_STAGES),
        "crm_fields": list(B2B_CRM_FIELDS),
        "boss_summary": [
            "外贸 B2B 不只找海关数据；地图、本地商家、社媒粉丝/评论/同行粉丝、代理商、独立站、电商卖家、POD 工厂、展会/RFQ 都是线索池。",
            "第一阶段优先卖批发 T 恤、样品包、POD 履约和转印/耗材；机器设备放到第二阶段，在客户有产能、短单、外包或扩产信号后再推。",
            "AI 可以自动发现、去重、评分、补字段、写首触草稿和跟进提醒；真实发邮件、私信、WhatsApp、提交表单、报价、收款和代理授权必须确认。",
            "私域承接以 WhatsApp + Email + CRM 为主，社媒负责内容信任、评论互动、粉丝线索和广告表单。",
        ],
    }


def b2b_lead_context_lines(limit: int = 14) -> list[str]:
    payload = build_b2b_lead_playbook_payload()
    lines = [
        "外贸 B2B 获客任务包：批发 T 恤先跑通，后续再承接机器/设备；路线 b2b:GLOBAL:teelab_sales。",
        "线索池包含海关/进出口数据、地图/本地商家、社媒主页/内容/粉丝/评论、同行粉丝、代理商、独立站、电商平台卖家、POD 工厂、展会/RFQ 和广告表单。",
        "私域路径：公开识别和评分 -> 个性化首触草稿 -> WhatsApp/Email/Instagram/LinkedIn/表单 -> CRM 跟单 -> 报价/样品/PI/生产/发货/复购。",
    ]
    for source in payload["sources"]:
        lines.append(
            f"B2B 来源：{source['title']}；客户：{' / '.join(source['customer_fit'][:3])}；"
            f"信号：{' / '.join(source['lead_signals'][:3])}；边界：{source['automation_boundary']}"
        )
    return lines[:limit]


def render_b2b_lead_playbook_panel(*, compact: bool = False) -> str:
    payload = build_b2b_lead_playbook_payload()
    source_cards = "".join(
        "<div class='b2b-lead-card'>"
        f"<span>{html.escape(source['source_id'])}</span>"
        f"<strong>{html.escape(source['title'])}</strong>"
        f"<p>{html.escape(' / '.join(source['customer_fit'][:3]))}</p>"
        f"<small>信号：{html.escape(' / '.join(source['lead_signals'][:3]))}</small>"
        "</div>"
        for source in payload["sources"][: (4 if compact else len(payload["sources"]))]
    )
    segment_cards = "".join(
        "<div class='b2b-segment-card'>"
        f"<strong>{html.escape(segment['title'])}</strong>"
        f"<p>{html.escape(segment['first_offer'])}</p>"
        f"<small>机器机会：{html.escape(segment['later_machine_offer'])}</small>"
        "</div>"
        for segment in payload["target_segments"][: (3 if compact else len(payload["target_segments"]))]
    )
    stage_cards = "".join(
        "<div class='b2b-stage-pill'>"
        f"<strong>{html.escape(stage['label'])}</strong>"
        f"<span>{html.escape(stage['owner'])}</span>"
        "</div>"
        for stage in payload["pipeline_stages"]
    )
    extra_class = " compact" if compact else ""
    return f"""
    <section class="panel b2b-lead-playbook{extra_class}" aria-label="外贸 B2B 获客和私域跟单任务包">
      <div class="b2b-lead-head">
        <div>
          <span>外贸 B2B 获客任务包</span>
          <h2>从线索发现到私域跟单成交</h2>
          <p>把海关、地图、社媒粉丝、同行粉丝、代理商、独立站、电商卖家和 POD 工厂统一进 CRM；先卖批发 T 恤，机器设备放到第二阶段。</p>
        </div>
        <b>{len(payload["sources"])} 类来源</b>
      </div>
      <div class="b2b-lead-grid">{source_cards}</div>
      <div class="b2b-segment-grid">{segment_cards}</div>
      <div class="b2b-stage-row">{stage_cards}</div>
    </section>
"""


def write_b2b_lead_playbook_report(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    payload = build_b2b_lead_playbook_payload()
    lines = [
        "# B2B Lead Playbook",
        "",
        f"Date: {actual_date}",
        f"Route: {payload['route']['visible_label']}",
        "",
        "## Boss Summary",
        "",
        *[f"- {item}" for item in payload["boss_summary"]],
        "",
        "## Lead Sources",
        "",
    ]
    for source in payload["sources"]:
        lines.append(f"- {source['title']}: {', '.join(source['customer_fit'])}")
        lines.append(f"  - Signals: {'; '.join(source['lead_signals'])}")
        lines.append(f"  - Boundary: {source['automation_boundary']}")
    lines.extend(["", "## Target Segments", ""])
    for segment in payload["target_segments"]:
        lines.append(f"- {segment['title']}: {segment['first_offer']}")
        lines.append(f"  - Machine opportunity: {segment['later_machine_offer']}")
    lines.extend(["", "## CRM Fields", "", "```json", json.dumps(payload["crm_fields"], ensure_ascii=False, indent=2), "```"])
    path = root / "outputs" / f"b2b_lead_playbook_{actual_date}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
