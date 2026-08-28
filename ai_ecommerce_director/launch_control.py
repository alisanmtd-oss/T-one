from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .product_lifecycle import build_product_lifecycle_plans
from .storage import read_records
from .store_metrics import extract_metric_values
from .types import IntakeRecord


REPORT_PREFIX = "launch_control"


@dataclass(slots=True)
class LaunchControlResult:
    run_date: str
    plans: list[dict[str, Any]]
    report: str
    report_path: Path
    json_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "plans": self.plans,
            "report": self.report,
            "report_path": str(self.report_path),
            "json_path": str(self.json_path),
        }


def run_launch_control_analysis(root: Path, run_date: str | None = None) -> LaunchControlResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    plans = build_launch_control_plans(root, report_date)
    report = build_launch_control_report(report_date, plans)
    report_path = write_report(root, report_date, report)
    json_path = write_json(root, report_date, plans)
    return LaunchControlResult(report_date, plans, report, report_path, json_path)


def build_launch_control_plans(
    root: Path,
    run_date: str | None = None,
    lifecycle_plans: list[dict[str, Any]] | None = None,
    records: list[IntakeRecord] | None = None,
) -> list[dict[str, Any]]:
    records = records if records is not None else read_records(root)
    lifecycle_plans = lifecycle_plans if lifecycle_plans is not None else build_product_lifecycle_plans(root, run_date, records=records)
    ranking_records = [record for record in records if record.record_type == "platform_ranking_signal"]
    scripts = [record for record in records if record.record_type == "video_script"]
    creator_records = [record for record in records if record.record_type in {"influencer_cooperation", "creator_spike_event"}]
    store_metrics = [record for record in records if record.record_type == "store_metric_snapshot"]
    results = [
        build_product_launch_control(plan, scripts, creator_records, store_metrics, ranking_records)
        for plan in lifecycle_plans
    ]
    return sorted(
        results,
        key=lambda item: (
            0 if item.get("is_monitored_target") else 1,
            -int(item.get("control_priority") or 0),
            str(item.get("product_name") or ""),
        ),
    )[:100]


def build_product_launch_control(
    lifecycle_plan: dict[str, Any],
    scripts: list[IntakeRecord],
    creators: list[IntakeRecord],
    store_metrics: list[IntakeRecord],
    ranking_records: list[IntakeRecord],
) -> dict[str, Any]:
    product_name = str(lifecycle_plan.get("product_name") or "")
    related_scripts = related_records(product_name, scripts)
    related_creators = related_records(product_name, creators)
    related_metrics = related_records(product_name, store_metrics)
    related_rankings = related_records(product_name, ranking_records)
    stage = str(lifecycle_plan.get("lifecycle_stage") or "A")
    roas = aggregate_roas(related_metrics)
    refund_rate = float(lifecycle_plan.get("return_rate") or 0)
    recent_units = int(lifecycle_plan.get("recent_units_7d") or 0)
    inventory_qty = lifecycle_plan.get("inventory_qty")
    stock_plan = lifecycle_plan.get("stock_plan") if isinstance(lifecycle_plan.get("stock_plan"), dict) else {}
    launch_stage = choose_launch_stage(stage, recent_units, roas, refund_rate)
    platform_mechanisms = infer_platform_mechanisms(product_name, related_rankings, related_metrics, related_scripts, related_creators)
    pressure = plate_pressure(lifecycle_plan, roas, len(related_scripts), len(related_creators))
    control_priority = min(100, int(lifecycle_plan.get("opportunity_score") or 0) + pressure["score"] // 2)
    is_monitored_target = str(lifecycle_plan.get("source") or "") == "product_target"
    if is_monitored_target and control_priority < 35:
        control_priority = 35
    return {
        "product_name": product_name,
        "is_monitored_target": is_monitored_target,
        "lifecycle_stage": stage,
        "lifecycle_label": lifecycle_plan.get("stage_label") or stage,
        "launch_stage": launch_stage,
        "launch_label": launch_stage_label(launch_stage),
        "control_priority": control_priority,
        "roas": roas,
        "refund_rate": refund_rate,
        "recent_units_7d": recent_units,
        "inventory_qty": inventory_qty,
        "script_count": len(related_scripts),
        "creator_signal_count": len(related_creators),
        "platform_mechanisms": platform_mechanisms,
        "platform_playbook": platform_playbook(platform_mechanisms, launch_stage),
        "plate_pressure": pressure,
        "launch_plan": build_launch_plan(launch_stage, lifecycle_plan, len(related_scripts), len(related_creators)),
        "plate_control_plan": build_plate_control_plan(launch_stage, lifecycle_plan, roas, refund_rate, inventory_qty),
        "budget_control": budget_control_plan(launch_stage, roas, refund_rate),
        "live_room_control": live_room_control_plan(launch_stage, lifecycle_plan),
        "stop_loss_rules": stop_loss_rules(launch_stage, roas, refund_rate, stock_plan),
        "learning_tasks": learning_tasks(launch_stage, product_name),
    }


def choose_launch_stage(stage: str, recent_units: int, roas: float | None, refund_rate: float) -> str:
    if stage == "D" or refund_rate >= 0.12 or (roas is not None and roas < 1.0 and recent_units > 0):
        return "cooldown_reset"
    if stage == "B":
        return "scale_control"
    if stage == "C":
        return "harvest_stabilize"
    if stage == "A" and recent_units > 0:
        return "micro_test_control"
    return "seed_launch"


def infer_platform_mechanisms(
    product_name: str,
    rankings: list[IntakeRecord],
    metrics: list[IntakeRecord],
    scripts: list[IntakeRecord],
    creators: list[IntakeRecord],
) -> list[dict[str, Any]]:
    platform_text = " ".join(
        json.dumps(record.fields, ensure_ascii=False).lower()
        for record in [*rankings, *metrics, *scripts, *creators]
    )
    mechanisms: list[dict[str, Any]] = []
    if any(term in platform_text for term in ["tiktok", "tk shop", "tk-us", "buyer video", "product card", "creator", "affiliate"]):
        mechanisms.append(
            {
                "platform": "TikTok Shop",
                "traffic_model": "allocation_horse_race",
                "label": "TK配量/赛马",
                "core_logic": "TikTok Shop不是单纯买量，核心是平台给素材、达人、账号和商品卡分配初始流量，再按互动和成交继续配量。",
                "launch_rule": "先准备多匹马：多脚本、多达人、多账号、多场景，小流量赛马，赢的素材/达人再加热视频和挂车。",
                "control_metrics": ["3秒留存", "完播", "评论购买意图", "商品卡点击", "订单", "退款率", "库存天数"],
            }
        )
    if any(term in platform_text for term in ["amazon", "asin", "bsr", "best sellers", "new releases", "keyword search", "ppc"]):
        mechanisms.append(
            {
                "platform": "Amazon",
                "traffic_model": "paid_search_buying",
                "label": "Amazon买词/买量",
                "core_logic": "Amazon更像买搜索流量和排名承接，核心是关键词、PPC、Listing、评价、价格和库存共同决定转化。",
                "launch_rule": "先确认关键词和Listing承接，再用小预算PPC买词测转化，赢的词进入放量和自然排名防守。",
                "control_metrics": ["CTR", "CVR", "ACOS/ROAS", "关键词排名", "BSR", "评价", "库存天数"],
            }
        )
    if not mechanisms:
        mechanisms.append(
            {
                "platform": "Unknown",
                "traffic_model": "unknown",
                "label": "待识别平台机制",
                "core_logic": "缺少平台信号，先不要套用TK或Amazon打法。",
                "launch_rule": f"继续采集 {product_name} 的平台、榜单、广告、内容和店铺销售数据。",
                "control_metrics": ["平台", "流量来源", "转化", "库存", "退款"],
            }
        )
    return mechanisms


def platform_playbook(mechanisms: list[dict[str, Any]], launch_stage: str) -> list[str]:
    labels = {str(item.get("traffic_model") or "") for item in mechanisms}
    playbook: list[str] = []
    if "allocation_horse_race" in labels:
        playbook.extend(
            [
                "TK打法：不要只盯买量，先造马池。至少准备自有号素材、达人素材、直播片段和商品卡承接一起赛马。",
                "TK控盘：平台给了小配量后，看留存、完播、评论购买意图、商品卡点击和订单，再决定是否继续加热视频/达人/挂车。",
                "TK禁忌：不要一条素材死磕，不要没有库存就强收割，不要用深折扣掩盖内容不行。",
            ]
        )
    if "paid_search_buying" in labels:
        playbook.extend(
            [
                "Amazon打法：先买关键词和承接，不是先拼视频。关键词、主图、标题、价格、评价和PPC要一起看。",
                "Amazon控盘：按保本ACOS/ROAS、关键词排名、CVR和库存天数阶梯加预算，失败词及时否定或降价测试。",
                "Amazon禁忌：Listing没承接、评价不足、库存不稳时，不要硬买大流量。",
            ]
        )
    if launch_stage == "scale_control" and "allocation_horse_race" in labels:
        playbook.append("当前是TK起量期：把赢家素材复制给相近达人和渠道号，但每24小时检查素材衰减和退款。")
    if launch_stage == "scale_control" and "paid_search_buying" in labels:
        playbook.append("当前是Amazon起量期：赢家关键词进入Exact/ Phrase防守，预算按保本线阶梯加。")
    return playbook or ["先识别平台机制，再决定是赛马配量、买词买量，还是内容种草。"]


def build_launch_plan(launch_stage: str, lifecycle_plan: dict[str, Any], script_count: int, creator_count: int) -> list[str]:
    product = str(lifecycle_plan.get("product_name") or "target product")
    base = {
        "seed_launch": [
            f"{product} 先做起盘蓄水：3 条自有号种草视频 + 3 条达人 brief，不急着硬收割。",
            "先拆同行爆款：0-2秒钩子、场景、运镜、字幕、评论购买理由和商品卡承接。",
            "主图/标题/价格/库存只做草稿，等内容和评论信号出来再确认上架或改价。",
        ],
        "micro_test_control": [
            "进入小盘测试：同一商品至少跑 3 个 Hook、2 个场景、2 个 CTA。",
            "每条素材独立记录播放、评论购买意图、商品卡点击、订单和退款。",
            "只在新店/测试店创建小额折扣或低预算广告草稿，执行前进确认中心。",
        ],
        "scale_control": [
            "进入起量控盘：放大 A 级素材和达人，同时保持安全库存，避免爆了断货。",
            "预算和达人不要一次性全推，每 24 小时按 ROAS、退款率、库存天数阶梯放量。",
            "同步准备直播间挂车节奏、优惠券节奏和复投达人名单。",
        ],
        "harvest_stabilize": [
            "进入稳盘收割：稳定复投高转化素材，做套装、二代、礼品版和人群变体。",
            "控折扣深度，优先保利润；用评论痛点更新详情页、FAQ 和视频解释。",
            "不要用单一素材长期硬推，按 3-5 天轮换脚本和达人类型。",
        ],
        "cooldown_reset": [
            "进入降温/重开：停止大额补货和大预算投放，先查素材疲劳、差评、价格战、库存和侵权风险。",
            "保留低成本验证：重做主图、脚本或二代卖点，再决定是否重新起盘。",
            "如果退货/差评无法修复，进入淘汰池或清库存策略。",
        ],
    }[launch_stage]
    if script_count == 0:
        base.append("当前缺少可执行脚本：先生成店铺自有脚本和达人脚本。")
    if creator_count == 0 and launch_stage in {"scale_control", "harvest_stabilize"}:
        base.append("当前缺少达人信号：补 A/B/C 达人池，否则放量会缺外部种草。")
    return base


def build_plate_control_plan(
    launch_stage: str,
    lifecycle_plan: dict[str, Any],
    roas: float | None,
    refund_rate: float,
    inventory_qty: Any,
) -> list[str]:
    stock = lifecycle_plan.get("stock_plan") if isinstance(lifecycle_plan.get("stock_plan"), dict) else {}
    stock_days = stock.get("safety_stock_days") or 0
    lines = {
        "seed_launch": [
            "控盘重点：控节奏，不控销量。先让内容教育用户，避免一上来靠深折扣冲单。",
            "每天只看三个信号：评论购买意图、商品卡点击、同类竞品排名变化。",
        ],
        "micro_test_control": [
            "控盘重点：小预算、小库存、小达人批量验证，避免单点误判。",
            "同一时间只改一个变量：Hook、价格、主图、折扣或达人类型。",
        ],
        "scale_control": [
            f"控盘重点：防断货、防退款、防素材衰减。建议安全库存约 {stock.get('recommended_available_stock', 0)} 件。",
            "每次加预算/加达人前先确认库存天数、发货时效和客服投诉。",
        ],
        "harvest_stabilize": [
            "控盘重点：利润和稳定性。用变体和二代延长周期，不靠持续降价。",
            "固定复盘排名、评分、退货、广告成本和素材疲劳，异常就降预算换脚本。",
        ],
        "cooldown_reset": [
            "控盘重点：止损。暂停大动作，把剩余库存、广告、达人和折扣收回到可控范围。",
            "只做低成本重测，不再追加大货和深度投流。",
        ],
    }[launch_stage]
    if roas is not None:
        lines.append(f"当前 ROAS 约 {roas:.2f}，放量前必须和保本 ROI 对比。")
    if refund_rate >= 0.08:
        lines.append(f"退款/退货率 {refund_rate:.1%} 偏高，先查产品质量、履约和详情页预期。")
    if inventory_qty is not None and int(inventory_qty or 0) < int(stock.get("recommended_available_stock", 0) or 0):
        lines.append(f"库存低于建议安全库存，放量前先补货或降低推广节奏。")
    if stock_days:
        lines.append(f"库存复盘触发：安全库存低于 {stock_days} 天时停止加速。")
    return lines


def budget_control_plan(launch_stage: str, roas: float | None, refund_rate: float) -> dict[str, Any]:
    if launch_stage == "seed_launch":
        mode = "no_or_tiny_budget"
        rule = "先不追 GMV，用自有号和低成本达人拿内容信号。"
    elif launch_stage == "micro_test_control":
        mode = "small_budget_test"
        rule = "每组素材小预算冷启动，跑出点击/加购/订单再放大。"
    elif launch_stage == "scale_control":
        mode = "step_up_budget"
        rule = "每次只阶梯加预算，ROAS、退款率、库存任一异常就停止加速。"
    elif launch_stage == "harvest_stabilize":
        mode = "defend_and_harvest"
        rule = "稳定复投赢家素材，保护利润和排名，避免无效抢量。"
    else:
        mode = "pause_or_minimum"
        rule = "停止大预算，只保留必要防守或重测。"
    allowed = launch_stage in {"micro_test_control", "scale_control", "harvest_stabilize"} and refund_rate < 0.08
    if roas is not None and roas < 1.2:
        allowed = False
    return {"mode": mode, "scale_allowed": allowed, "rule": rule}


def live_room_control_plan(launch_stage: str, lifecycle_plan: dict[str, Any]) -> list[str]:
    product = str(lifecycle_plan.get("product_name") or "target product")
    if launch_stage in {"seed_launch", "micro_test_control"}:
        return [
            f"{product} 直播间先做预热位或测试挂车，不做深折扣主推。",
            "观察评论提问、商品卡点击和下单峰值，再决定是否推到主商品位。",
        ]
    if launch_stage == "scale_control":
        return [
            "直播间节奏：预热品 -> 主推品 -> 套装/加购 -> 限时券。",
            "下单峰值后 5-10 分钟看转化和库存，再决定是否加券或换讲解点。",
        ]
    if launch_stage == "harvest_stabilize":
        return [
            "直播间做稳定收割：固定讲解卖点、对比竞品痛点、插入评论证明。",
            "折扣只做阶段性，不长期破坏价格体系。",
        ]
    return [
        "直播间降温：不再主推，只做清库存或新版测试挂车。",
        "如果投诉/退货高，暂停直播间强推。"
    ]


def stop_loss_rules(launch_stage: str, roas: float | None, refund_rate: float, stock_plan: dict[str, Any]) -> list[str]:
    rules = [
        "任何真实改价、折扣、广告、挂车、上传、发布都进入确认中心。",
        "老店/稳定店/正在跑广告的店默认只读和草稿，不能自动扰动。",
    ]
    if roas is not None:
        rules.append("ROAS 连续低于保本线或 24 小时无改善，停止加预算并换素材。")
    if refund_rate >= 0.08:
        rules.append("退款/退货率超过 8%，暂停放量，先查差评、履约和产品缺陷。")
    if launch_stage in {"scale_control", "harvest_stabilize"}:
        rules.append(f"可用库存低于建议安全库存 {stock_plan.get('recommended_available_stock', 0)} 件时，不再加达人/广告/直播强度。")
    if launch_stage == "cooldown_reset":
        rules.append("除清库存和低成本重测外，不新增大货、不深投广告。")
    return rules


def learning_tasks(launch_stage: str, product_name: str) -> list[str]:
    return [
        f"收集 {product_name} 同品同行起盘路径：第一条爆款视频、第一批达人、首次折扣、首次直播挂车。",
        "记录每次控盘动作前后：GMV、订单、ROAS、退款、库存、评论、排名。",
        f"把 {launch_stage_label(launch_stage)} 的有效动作沉淀为 strategy_memory，失败动作写入 what_not_to_do。",
    ]


def plate_pressure(lifecycle_plan: dict[str, Any], roas: float | None, script_count: int, creator_count: int) -> dict[str, Any]:
    score = 0
    warnings: list[str] = []
    if lifecycle_plan.get("lifecycle_stage") == "B":
        score += 25
    if int(lifecycle_plan.get("recent_units_7d") or 0) > 20:
        score += 15
    if lifecycle_plan.get("inventory_qty") is None:
        warnings.append("缺少库存数据")
    elif int(lifecycle_plan.get("inventory_qty") or 0) < int((lifecycle_plan.get("stock_plan") or {}).get("recommended_available_stock") or 0):
        score += 15
        warnings.append("库存可能跟不上")
    if roas is None:
        warnings.append("缺少广告/ROAS数据")
    elif roas < 1.2:
        score += 15
        warnings.append("ROAS偏低")
    if script_count < 3:
        warnings.append("脚本储备不足")
    if creator_count == 0 and lifecycle_plan.get("lifecycle_stage") in {"B", "C"}:
        warnings.append("达人池不足")
    return {"score": min(score, 100), "warnings": warnings}


def related_records(product_name: str, records: list[IntakeRecord]) -> list[IntakeRecord]:
    key = product_name.strip().lower()
    if not key:
        return []
    return [record for record in records if key in record_search_text(record)]


def record_search_text(record: IntakeRecord) -> str:
    cached = record.metadata.get("_launch_search_text")
    if isinstance(cached, str):
        return cached
    text = json.dumps(record.fields, ensure_ascii=False).lower()
    record.metadata["_launch_search_text"] = text
    return text


def aggregate_roas(records: list[IntakeRecord]) -> float | None:
    revenue = 0.0
    ad_spend = 0.0
    for record in records[-20:]:
        values = extract_metric_values(record.fields)
        revenue += float(values.get("revenue") or 0)
        ad_spend += float(values.get("ad_spend") or 0)
    return round(revenue / ad_spend, 4) if ad_spend > 0 else None


def launch_stage_label(stage: str) -> str:
    return {
        "seed_launch": "起盘蓄水",
        "micro_test_control": "小盘测试",
        "scale_control": "起量控盘",
        "harvest_stabilize": "收割稳盘",
        "cooldown_reset": "降温/重开",
    }.get(stage, stage)


def build_launch_control_report(run_date: str, plans: list[dict[str, Any]]) -> str:
    lines = [
        f"# Launch & Plate Control Report - {run_date}",
        "",
        "## 口径",
        "- 起盘：用内容、达人、Listing、价格、库存和评论信号把产品从冷启动拉到可测、可卖、可放量。",
        "- 控盘：用预算、折扣、库存、达人节奏、直播挂车、退款和素材衰减控制风险，不让盘失控。",
        "",
        "## 今日重点",
    ]
    if not plans:
        lines.append("- 暂无可分析商品。先设置监控商品并采集同行视频、榜单、销量、库存和店铺数据。")
        return "\n".join(lines)
    for plan in plans[:30]:
        lines.append(
            f"- {plan['product_name']}｜{plan['launch_label']}｜优先级 {plan['control_priority']}｜"
            f"机制 {', '.join(item.get('label', '') for item in plan.get('platform_mechanisms', []) if item.get('label')) or '待识别'}｜"
            f"ROAS {plan['roas'] if plan['roas'] is not None else '缺失'}｜"
            f"库存 {plan['inventory_qty'] if plan['inventory_qty'] is not None else '未知'}｜"
            f"{'; '.join(plan['plate_pressure']['warnings']) or '暂无明显盘面压力'}"
        )
    lines.extend(["", "## 平台机制口径", "- TikTok Shop：赛马机制，平台配量。AI要准备多素材、多达人、多账号、多商品卡承接，让平台给初始流量后筛赢家。", "- Amazon：买量机制，搜索/PPC/关键词/Listing承接。AI要先算保本ACOS/ROAS，再买词、守排名、控库存。"])
    return "\n".join(lines)


def write_report(root: Path, run_date: str, content: str) -> Path:
    path = root / "outputs" / f"{REPORT_PREFIX}_{run_date}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_json(root: Path, run_date: str, plans: list[dict[str, Any]]) -> Path:
    path = root / "outputs" / f"{REPORT_PREFIX}_{run_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"run_date": run_date, "plans": plans}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def latest_launch_control_report(root: Path) -> tuple[str, Path | None]:
    output_dir = root / "outputs"
    if not output_dir.exists():
        return "No launch control report yet.", None
    paths = sorted(output_dir.glob(f"{REPORT_PREFIX}_*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not paths:
        return "No launch control report yet.", None
    return paths[0].read_text(encoding="utf-8"), paths[0]
