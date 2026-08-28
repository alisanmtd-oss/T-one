from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .storage import read_records
from .types import IntakeRecord

# Six-dimension product selection scoring + profit model, aligned to the operator's
# own "TikTok Shop 品牌化教程 2.0" (TK体系2.0), lesson 2「商品卡选品与案例判断」.
# Standards applied here: 轻量化(≤500g) + 客单甜区($15-35) 或低价截流模型; 风控红线
# (侵权 / 文化·宗教禁忌 / 医疗宣称 / 禁用词·虚假承诺 / 退货率); 趋势/节日机会窗口.
# See docs/TK_SELECTION_STANDARD_V2.md for the distilled standard.
#
# Credit: the six-dimension methodology + profit-breakdown idea are inspired by the
# open-source project xiaolu7586/ecommerce-product-scout-agent. The CODE is our own
# clean Python reimplementation — we do not reuse its scraping / anti-scraping
# (Firecrawl) collection. This module only scores data already in our local Data Lake.

DIMENSIONS = ["demand", "competition", "margin", "operational", "risk", "opportunity"]
WEIGHTS = {
    "demand": 0.28,
    "competition": 0.16,
    "margin": 0.22,
    "operational": 0.10,
    "risk": 0.12,
    "opportunity": 0.12,
}


def _num(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(str(value).replace(",", "").replace("$", "").replace("%", "").strip())
    except ValueError:
        return 0.0


def estimate_profit(
    price: float,
    *,
    cost_ratio: float = 0.30,
    platform_fee_ratio: float = 0.08,
    ad_ratio: float = 0.15,
    return_ratio: float = 0.05,
    ship_cost: float = 2.0,
) -> dict[str, float]:
    """Rough unit profit model. All ratios are of price unless noted. Returns the
    components and the net margin percentage (estimate, for screening only)."""
    price = max(0.0, price)
    cost = price * cost_ratio
    platform_fee = price * platform_fee_ratio
    ad = price * ad_ratio
    returns = price * return_ratio
    net = price - cost - platform_fee - ad - returns - ship_cost
    margin_pct = round((net / price * 100) if price else 0.0, 1)
    return {
        "price": round(price, 2),
        "cost": round(cost, 2),
        "platform_fee": round(platform_fee, 2),
        "ad": round(ad, 2),
        "returns": round(returns, 2),
        "ship_cost": round(ship_cost, 2),
        "net_unit_profit": round(net, 2),
        "margin_pct": margin_pct,
    }


def _clamp(value: float) -> int:
    return int(max(0, min(100, round(value))))


def score_product(signals: dict[str, Any]) -> dict[str, Any]:
    """Score one product on six dimensions (0-100) and give a verdict. `signals`
    is a normalized dict; missing values score conservatively and are flagged."""
    rationale: list[str] = []
    missing: list[str] = []

    views = _num(signals.get("views"))
    sales = _num(signals.get("sales"))
    gmv = _num(signals.get("gmv"))
    if not (views or sales or gmv):
        missing.append("需求证据(销量/GMV/播放量)")
    demand = _clamp(
        min(45, views / 20000 * 45) + min(35, sales / 200 * 35) + min(20, gmv / 5000 * 20)
    )

    competitors = _num(signals.get("competitor_count"))
    saturation = str(signals.get("saturation") or "").lower()
    competition = 60
    if competitors:
        competition = _clamp(90 - min(70, competitors * 3))
    if saturation in {"high", "高", "red_ocean"}:
        competition = min(competition, 30)
    elif saturation in {"low", "低", "blue_ocean"}:
        competition = max(competition, 75)

    price = _num(signals.get("price"))
    if price <= 0:
        missing.append("价格")
    profit = estimate_profit(
        price,
        cost_ratio=_num(signals.get("cost_ratio")) or 0.30,
        ad_ratio=_num(signals.get("ad_ratio")) or 0.15,
        return_ratio=_num(signals.get("return_ratio")) or 0.05,
    )
    margin = _clamp(profit["margin_pct"] * 2.5)  # 40% margin -> 100
    # TK体系2.0: 客单 $15-35 甜区更易跑通物流与转化；过低需走低价截流模型，过高需内容/达人。
    weight_g = _num(signals.get("weight_grams"))
    if 15 <= price <= 35:
        margin = _clamp(margin + 8)
        rationale.append("客单 $15-35 甜区，符合 TK体系2.0 轻量化打法")
    elif 0 < price < 8:
        rationale.append("低客单：须按低价截流模型设计运费/赠品/套装，否则毛利不足")
    elif price > 60:
        rationale.append("高客单：须先用短视频+达人建立信任，再由商品卡转化")

    fragile = signals.get("fragile") or signals.get("oversized") or signals.get("heavy")
    variants = _num(signals.get("variant_count"))
    operational = _clamp(85 - (20 if fragile else 0) - min(25, variants * 2))
    if weight_g > 500:
        operational = _clamp(operational - 20)
        rationale.append("重量 >500g：物流成本与退货风险偏高（TK体系2.0 偏好 ≤500g）")
    elif 0 < weight_g <= 500:
        operational = _clamp(operational + 5)

    ip_risk = str(signals.get("ip_risk") or "").lower()
    refund_rate = _num(signals.get("refund_rate"))
    risk = 80
    if ip_risk in {"high", "高"}:
        risk = 25
        rationale.append("侵权/IP 风险偏高，需先过合规筛查")
    elif ip_risk in {"medium", "中"}:
        risk = 55
    if refund_rate:
        risk = _clamp(risk - min(40, refund_rate))
    # TK体系2.0 风控红线：文化/宗教禁忌、禁用词/虚假承诺/医疗宣称。
    cultural = str(signals.get("cultural_risk") or signals.get("religious_risk") or "").lower()
    if cultural in {"high", "高"} or signals.get("religious_taboo"):
        risk = min(risk, 25)
        rationale.append("目标市场存在文化/宗教禁忌风险，先排查再上（TK体系2.0 红线）")
    if signals.get("forbidden_words") or signals.get("false_claim") or signals.get("medical_claim"):
        risk = _clamp(risk - 25)
        rationale.append("标题/主图疑似禁用词/虚假承诺/医疗宣称，须改写")

    trend = str(signals.get("trend") or "").lower()
    opportunity = 55
    if trend in {"rising", "up", "上升", "viral"}:
        opportunity = 85
        rationale.append("处于上升/爆发趋势，存在窗口期")
    elif trend in {"declining", "down", "下降"}:
        opportunity = 30
        rationale.append("趋势下行，窗口可能已过")
    if signals.get("seasonal_now"):
        opportunity = min(100, opportunity + 10)

    scores = {
        "demand": demand,
        "competition": competition,
        "margin": margin,
        "operational": operational,
        "risk": risk,
        "opportunity": opportunity,
    }
    total = _clamp(sum(scores[dim] * WEIGHTS[dim] for dim in DIMENSIONS))

    if risk <= 30:
        verdict = "not_recommend"
        verdict_label = "不推荐（风险过高）"
    elif total >= 70 and not missing:
        verdict = "strongly_recommend"
        verdict_label = "强烈推荐"
    elif total >= 50:
        verdict = "caution"
        verdict_label = "谨慎尝试 / 先补证据"
    else:
        verdict = "not_recommend"
        verdict_label = "不推荐"

    if missing:
        rationale.append("缺少：" + "、".join(missing) + "（先采真实数据再定）")
    return {
        "scores": scores,
        "total": total,
        "verdict": verdict,
        "verdict_label": verdict_label,
        "profit": profit,
        "rationale": rationale,
    }


def signals_from_record(record: IntakeRecord) -> dict[str, Any]:
    f = record.fields or {}
    return {
        "product_name": f.get("product_name") or f.get("title") or "",
        "product_url": f.get("product_url") or f.get("url") or "",
        "views": f.get("views") or f.get("view_count") or f.get("current_views"),
        "sales": f.get("sales") or f.get("sales_count") or f.get("sales_7d_visible"),
        "gmv": f.get("gmv") or f.get("gmv_7d_visible") or f.get("total_gmv_visible"),
        "price": f.get("price") or f.get("price_visible"),
        "refund_rate": f.get("refund_rate") or f.get("return_rate"),
        "ip_risk": f.get("ip_risk") or f.get("infringement_risk"),
        "trend": f.get("trend") or f.get("growth_signal") or f.get("visible_growth_signal"),
        "competitor_count": f.get("competitor_count"),
        "saturation": f.get("saturation"),
        "weight_grams": f.get("weight_grams") or f.get("weight"),
        "cultural_risk": f.get("cultural_risk") or f.get("religious_risk"),
        "forbidden_words": f.get("forbidden_words"),
        "false_claim": f.get("false_claim"),
        "variant_count": f.get("variant_count"),
    }


def build_scout_report(root: Path, *, limit: int = 30) -> list[dict[str, Any]]:
    """Score recent product/content records and rank them with verdicts."""
    records = [
        r for r in read_records(root)
        if r.record_type in {"platform_ranking_signal", "hot_link", "viral_content_signal"}
    ]
    records.sort(key=lambda r: r.created_at, reverse=True)
    results: list[dict[str, Any]] = []
    for record in records[:limit]:
        signals = signals_from_record(record)
        if not (signals.get("product_name") or signals.get("product_url")):
            continue
        scored = score_product(signals)
        results.append({
            "product_name": signals["product_name"],
            "product_url": signals["product_url"],
            **scored,
        })
    results.sort(key=lambda item: item["total"], reverse=True)
    return results


def save_scout_report(root: Path, report: list[dict[str, Any]], run_date: str | None = None) -> Path:
    run_date = run_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = root / "outputs" / f"product_scout_{run_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
