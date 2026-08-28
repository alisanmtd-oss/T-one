from __future__ import annotations

import html
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .project_facts import private_project_section

@dataclass(frozen=True, slots=True)
class AmazonOpsRole:
    role_id: str
    agent: str
    title: str
    job: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    current_10001_tasks: tuple[str, ...]
    automation_level: str
    external_actions: tuple[str, ...]
    guardrails: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_id": self.role_id,
            "agent": self.agent,
            "title": self.title,
            "job": self.job,
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "current_10001_tasks": list(self.current_10001_tasks),
            "automation_level": self.automation_level,
            "external_actions": list(self.external_actions),
            "guardrails": list(self.guardrails),
        }


AMAZON_US_OPERATION_ROLES: tuple[AmazonOpsRole, ...] = (
    AmazonOpsRole(
        "listing",
        "AI Listing Operator",
        "Listing 优化 / 上架",
        "把产品资料变成可提交的 Amazon 父子变体、字段、SKU、标题、五点、描述和合规属性。",
        ("产品规格", "价格", "尺码表", "颜色图", "类目路径", "品牌/GTIN 状态"),
        ("单件链接草稿", "4 件套链接草稿", "变体 SKU 表", "发布前错误清单"),
        (
            "保留单件规范父体 68-DDNH-IM56 / B0EXAMPLE1：11 色 x 8 码 = 88 个子体，价格 $20。",
            "保留 4 件套规范父体 TL10001-MIX4-PARENT / B0H7JKJBRF：8 个尺码子体，价格 $50。",
            "禁止复用旧 1/89 文件、再建父体或把单件和套装混入同一个三维变体家族。",
        ),
        "L2 draft / L3 after confirmation",
        ("publish_listing", "update_listing", "price_change"),
        ("不复制同行文案", "Brand/GTIN 未通过不提交", "Ready 不等于可直接发布"),
    ),
    AmazonOpsRole(
        "image",
        "AI Image Operator",
        "产品图 / A+ 素材",
        "生成并检查主图、颜色图、面料图、尺码图、套装图和移动端可读素材。",
        ("供应商原图", "平铺图", "尺码表", "颜色清单", "Amazon 图片规则"),
        ("白底主图", "颜色变体图", "面料细节图", "尺码图", "4 件套价值图"),
        (
            "单件当前代表子体仅 2 个媒体位，补齐白底主图、背面、洗水/面料、版型尺码和场景图。",
            "4 件套当前仅 1 个媒体位；主图必须真实展示包内 4 件，辅图解释固定配色、尺码和价值。",
            "11 个颜色逐一映射真实颜色素材；缺图先进入资产队列，不用生成图冒充实物颜色。",
        ),
        "L2 draft / L3 upload after confirmation",
        ("upload_asset", "replace_listing_image"),
        ("主图不放促销文字", "不使用侵权图案", "上传失败必须保留截图和原因"),
    ),
    AmazonOpsRole(
        "ads",
        "AI Ads Operator",
        "广告设置 / 投放优化",
        "在链接可售后准备 Sponsored Products 自动广告、手动精准词和否词规则。",
        ("可售 ASIN/SKU", "广告账号", "关键词", "毛利", "库存", "预算上限"),
        ("冷启动广告草稿", "关键词表", "ACOS 止损线", "放量/暂停规则"),
        (
            "Amazon 预设草稿已可读取：单件与 4 件套均为 $10/日、动态竞价上下调、手动 40 词。",
            "主购买区仍无 Featured Offer，配送承诺长达数周，因此保留草稿、不点 Launch campaign。",
            "闸门打开后单件与 4 件套分开投放，先小预算测试并按查询词、转化、ACOS 和利润止损。",
        ),
        "L2 draft / L3 after confirmation",
        ("launch_ad", "update_ad_budget", "pause_ad"),
        ("Amazon Ads 授权和 Seller Central 分开", "预算先小额", "没有库存不投放"),
    ),
    AmazonOpsRole(
        "promotion",
        "AI Promotion Operator",
        "活动 / 优惠 / 叠加",
        "研究 Coupons、Promotions、Deals 和价格折扣，计算亏本测试、止损和叠加影响。",
        ("售价", "成本", "Amazon 费用", "运费", "库存", "活动规则", "广告预算"),
        ("优惠草稿", "亏损上限", "叠加校验", "活动日历", "回滚条件"),
        (
            "Seller Central Coupons 当前显示 Acesso necessário，缺少 Publicidade -> Cupons 权限。",
            "权限、Featured Offer、配送和利润闸门都通过后，再为单件 $20 与 4 件套 $50 分别建活动草稿。",
            "活动必须校验参考价、叠加、每单成本、库存、开始/结束时间和止损，不做虚假折扣。",
        ),
        "L2 draft / L3 after confirmation",
        ("set_discount", "coupon_create", "deal_submit", "price_change"),
        ("不虚假折扣", "优惠叠加后先算净利润", "活动提交前保留截图"),
    ),
    AmazonOpsRole(
        "inventory",
        "AI Inventory Planner",
        "库存 / 备货",
        "按颜色尺码深度、断码风险、补货周期和广告节奏决定备货。",
        ("现货数量", "尺码销量", "颜色转化", "补货周期", "退货原因"),
        ("首批库存表", "补货建议", "断码预警", "滞销处理"),
        (
            "禁止写入 10 件/5 套等测试数量；库存以 Seller Central 与美国仓真实可用量为准。",
            "单件按 88 个颜色尺码子体监控，4 件套按 8 个尺码子体监控，并校验套装占用的单件库存。",
            "广告和活动前检查可售、预留、断码、重复报价和库存更新时间。",
        ),
        "L1-L2",
        ("update_inventory", "reserve_stock"),
        ("没有真实库存不改数量", "投广告前检查可售库存", "补货不靠感觉"),
    ),
    AmazonOpsRole(
        "fulfillment",
        "AI Fulfillment Operator",
        "发货 / 履约",
        "自仓 FBM 订单读取、拣货校验、物流追踪号、迟发风险和异常处理。",
        ("订单", "SKU", "仓库库存", "物流服务", "承诺发货时间", "追踪号"),
        ("发货任务单", "异常清单", "迟发预警", "物流回传记录"),
        (
            "当前 10001 先走 FBM 自仓，不走 FBA。",
            "当前仅配置中国厦门发货地，买家页配送承诺数周；先取得获批美国仓地址与履约说明。",
            "订单出现后先匹配 SKU、尺码、颜色和库存，再生成仓库交接与物流回传待确认动作。",
            "迟发、地址异常、缺货订单必须先进入确认。",
        ),
        "L1-L2 / L3 after confirmation",
        ("ship_order", "cancel_order", "upload_tracking"),
        ("不绕过平台履约规则", "不发错尺码颜色", "发货前留订单和库存证据"),
    ),
    AmazonOpsRole(
        "customer_service",
        "AI Customer Service Agent",
        "客服 / 售后",
        "处理尺码、面料、物流、退货、差评和退款原因，反哺 listing 与产品。",
        ("买家消息", "退货原因", "差评", "订单", "尺码表", "物流状态"),
        ("回复草稿", "退货原因归因", "listing 修改建议", "质量改进单"),
        (
            "预先准备尺码、面料、洗护和物流回复模板。",
            "退货原因按尺码偏大/偏小、色差、面料、物流拆分。",
            "不承诺平台政策外赔偿，退款前先查订单。",
        ),
        "L2 draft / L3 after confirmation",
        ("send_message", "refund_customer", "replacement_order"),
        ("不泄露内部数据", "不越权承诺赔偿", "高风险纠纷升级负责人"),
    ),
    AmazonOpsRole(
        "finance",
        "AI Finance & Settlement Officer",
        "利润 / 回款 / 费用",
        "计算 SKU 级利润、广告 ACOS、平台费用、退款损耗、现金回款和补货现金流。",
        ("售价", "成本", "运费", "Amazon 费用", "广告费", "优惠", "退款", "回款报告"),
        ("SKU 利润表", "保本 ROAS", "现金流表", "回款差异", "止损建议"),
        (
            "单件按 $20、4 件套按 $50 分开算利润，不混合看 GMV。",
            "前期亏本测试要写清楚日亏损上限和几单后复盘。",
            "回款以平台结算报告为准，广告费、退款和 reserve 单独列。",
        ),
        "L1-L2",
        ("pay_invoice", "move_money"),
        ("不移动资金", "不提交税务", "利润口径必须含广告和退款"),
    ),
    AmazonOpsRole(
        "risk",
        "AI Compliance Officer",
        "账号健康 / 合规",
        "检查品牌、GTIN、图片、类目、违禁词、账号健康、迟发率、取消率和授权风险。",
        ("Account Health", "类目路径", "品牌状态", "GTIN/豁免", "图片提示", "订单指标"),
        ("发布闸门", "合规阻塞", "申诉草稿", "风险复盘"),
        (
            "美国站当前 Account Health 200、0 个可见政策问题，但销售服务访问和银行状态仍需复核。",
            "验证码、账号安全、付款和授权变更立即停下。",
            "广告和优惠不等于店铺授权，必须分开核对。",
        ),
        "L0-L2",
        ("authorize_app", "submit_appeal", "account_security_change"),
        ("不绕过验证码", "不保存明文密码", "不混用多个店铺执行身份"),
    ),
    AmazonOpsRole(
        "operations_memory",
        "AI Operations Memory",
        "操作记忆 / 快速续接",
        "把每次打开页面、读取、判断、草稿、提交、验证、失败和下一步写入追加式账本，下一轮直接续接。",
        ("权威状态 JSON", "操作账本", "浏览器连接", "页面证据", "审批状态"),
        ("最新动作游标", "追加式 JSONL 账本", "快速恢复包", "卡点与下一步"),
        (
            "固定使用 BitBrowser profile 和 Amazon US 路由，禁止临时新建环境。",
            "每个动作落盘到 amazon_10001_operation_log.jsonl，并更新最新动作游标。",
            "不在日志中保存密码、Cookie、验证码/MFA、银行信息或身份材料。",
        ),
        "L4 reversible internal logging",
        (),
        ("日志只追加不覆盖历史", "外部动作单独标记", "状态冲突以实时店铺证据为准"),
    ),
)


def build_amazon_10001_operations_payload(root: Path | None = None) -> dict[str, Any]:
    facts = private_project_section("amazon_operations", root)
    route = facts.get("route") if isinstance(facts.get("route"), dict) else {}
    products = facts.get("products") if isinstance(facts.get("products"), list) else []
    boss_summary = facts.get("boss_summary") if isinstance(facts.get("boss_summary"), list) else []
    fast_resume = facts.get("fast_resume") if isinstance(facts.get("fast_resume"), dict) else {}
    return {
        "project_label": str(facts.get("project_label") or "Amazon 项目"),
        "panel_title": str(facts.get("panel_title") or "Amazon 运营任务包"),
        "headline": str(facts.get("headline") or "读取私有项目配置后显示运营计划"),
        "route": dict(route),
        "products": [dict(item) for item in products if isinstance(item, dict)],
        "roles": [role.to_dict() for role in AMAZON_US_OPERATION_ROLES],
        "boss_summary": [str(item) for item in boss_summary],
        "fast_resume": dict(fast_resume),
    }


def amazon_10001_operations_context_lines(limit: int = 12) -> list[str]:
    payload = build_amazon_10001_operations_payload()
    products = payload["products"]
    route_label = str(payload["route"].get("visible_label") or "私有路由未配置")
    summary = "；".join(payload["boss_summary"][:3]) or "私有商品事实未配置。"
    lines = [f"{payload['project_label']} 运营任务包：{route_label}；{summary}"]
    for product in products:
        lines.append(
            f"Amazon 商品计划：{product['label']}；售价 ${product['price_usd']:.2f}；"
            f"{product['fulfillment']}；子体 {product['child_count']}；"
            f"上架结构 {product['listing_type']}。"
        )
    for role in AMAZON_US_OPERATION_ROLES[: max(0, limit - len(lines))]:
        lines.append(
            f"Amazon 岗位：{role.title}；负责人 {role.agent}；工作 {role.job}；"
            f"当前项目任务 {' / '.join(role.current_10001_tasks[:2])}；"
            f"真实动作 {' / '.join(role.external_actions[:3]) or '无'} 需确认。"
        )
    return lines[:limit]


def render_amazon_10001_operations_panel(*, compact: bool = False) -> str:
    payload = build_amazon_10001_operations_payload()
    product_cards = "".join(
        "<div class='amazon-ops-card'>"
        f"<span>{html.escape(product['listing_type'])}</span>"
        f"<strong>{html.escape(product['label'])}</strong>"
        f"<p>售价 ${product['price_usd']:.2f} · {html.escape(product['fulfillment'])} · {html.escape(product['fba_policy'])}</p>"
        f"<small>规范父体：{html.escape(product['canonical_parent_sku'])} / {html.escape(product['canonical_parent_asin'])}；子体：{product['child_count']}；库存：只读真实店铺/仓库</small>"
        "</div>"
        for product in payload["products"]
    )
    role_cards = "".join(
        "<div class='amazon-ops-role'>"
        f"<strong>{html.escape(role.title)}</strong>"
        f"<span>{html.escape(role.agent)}</span>"
        f"<p>{html.escape('；'.join(role.current_10001_tasks[:2]))}</p>"
        "</div>"
        for role in AMAZON_US_OPERATION_ROLES[: (4 if compact else 10)]
    )
    extra_class = " compact" if compact else ""
    panel_title = html.escape(payload["panel_title"])
    headline = html.escape(payload["headline"])
    return f"""
    <section class="panel amazon-ops-playbook{extra_class}" aria-label="{panel_title}">
      <div class="amazon-status-head">
        <div>
          <span>{panel_title}</span>
          <h2>{headline}</h2>
          <p>把 Listing、图片、广告、活动、库存、发货、客服、利润和回款拆成 AI 岗位任务，客户不用自己研究后台。</p>
        </div>
        <b>10 个 AI 岗位</b>
      </div>
      <div class="amazon-ops-products">{product_cards}</div>
      <div class="amazon-ops-roles">{role_cards}</div>
    </section>
"""


def write_amazon_10001_operations_report(root: Path, run_date: str | None = None) -> Path:
    actual_date = run_date or date.today().isoformat()
    payload = build_amazon_10001_operations_payload()
    lines = [
        f"# {payload['project_label']} Operations Playbook",
        "",
        f"Date: {actual_date}",
        f"Route: {payload['route'].get('visible_label', 'private route not configured')}",
        "",
        "## Products",
        "",
    ]
    for product in payload["products"]:
        lines.append(
            f"- {product['label']}: ${product['price_usd']:.2f}, {product['fulfillment']}, {product['listing_type']}."
        )
    lines.extend(["", "## AI Roles", ""])
    for role in AMAZON_US_OPERATION_ROLES:
        lines.append(f"- {role.title} ({role.agent}): {role.job}")
        lines.append(f"  - Current tasks: {'; '.join(role.current_10001_tasks)}")
        lines.append(f"  - Guardrails: {'; '.join(role.guardrails)}")
    path = root / "outputs" / f"amazon_10001_operations_playbook_{actual_date}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
