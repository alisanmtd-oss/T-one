"""评论痛点分析（自建，跑我们自己采集的评论数据；不依赖任何付费源）。

输入：评论/评论区文本列表（来自数据湖的 review / comment / viral_content 记录）。
输出：差评痛点 Top + 频次/占比 + 对应改良建议 + 好评信号。
关键词信号是确定性兜底；传入 LLMClient 可做更细的语义聚类（可选增强）。
数量为信号统计，非精确情感分。
"""
from __future__ import annotations

from collections import Counter
from typing import Any

# 痛点主题 → 触发关键词（中英都覆盖）
PAIN_SIGNALS: dict[str, list[str]] = {
    "质量/做工": ["质量", "做工", "劣质", "不结实", "松散", "掉线", "开线", "脱落", "断了", "坏了",
                "quality", "cheap", "flimsy", "broke", "broken", "fell apart", "poorly made"],
    "尺码/版型": ["尺码", "偏大", "偏小", "版型", "太大", "太小", "不合身",
                "size", "too small", "too big", "runs small", "runs large", "doesn't fit"],
    "色差/外观": ["色差", "掉色", "褪色", "和图片不符", "和描述颜色",
                "faded", "not as pictured", "different color", "color off"],
    "物流/包装": ["物流", "太慢", "破损", "包装", "压坏", "延迟", "迟到",
                "slow shipping", "damaged", "packaging", "arrived broken", "late delivery"],
    "异味/材质": ["异味", "味道", "刺鼻", "材质", "劣质料", "smell", "odor", "chemical smell"],
    "与描述不符": ["与描述不符", "货不对板", "虚假", "夸大", "not as described", "misleading", "false advertising"],
    "功能/效果": ["不好用", "没效果", "失灵", "不灵", "doesn't work", "useless", "stopped working", "no effect"],
    "客服/售后": ["客服", "售后", "退款", "退货", "没人理", "no response", "bad service", "refund", "return"],
}
IMPROVE: dict[str, str] = {
    "质量/做工": "升级用料/加固工艺，附质检视频；主图标注材质与承重。",
    "尺码/版型": "出真人尺码表+实测对照；详情页提示'偏大/偏小，建议拍大/小一号'。",
    "色差/外观": "用实拍图替换渲染图，标注'屏幕色差'，附多光线实拍。",
    "物流/包装": "换更稳包装+本地仓提速；时效写清楚、管理预期。",
    "异味/材质": "换环保料/出厂晾置除味；详情页说明材质与安全认证。",
    "与描述不符": "标题/主图/详情与实物一致，去夸大词，降退货。",
    "功能/效果": "出真实使用演示+前后对比，写清适用场景与限制。",
    "客服/售后": "明确售后 SOP 与响应时效；常见问题前置到详情页。",
}
POSITIVE = ["好评", "喜欢", "值得", "质量好", "好用", "超值", "回购", "推荐", "满意",
            "love", "great", "perfect", "excellent", "amazing", "worth it", "recommend"]


def summarize_reviews(reviews: list[str]) -> dict[str, Any]:
    texts = [str(r or "") for r in (reviews or []) if str(r or "").strip()]
    n = len(texts)
    pain: Counter[str] = Counter()
    positive = 0
    for t in texts:
        low = t.lower()
        for theme, kws in PAIN_SIGNALS.items():
            if any(k.lower() in low for k in kws):
                pain[theme] += 1
        if any(k.lower() in low for k in POSITIVE):
            positive += 1
    top = [
        {"theme": theme, "count": c, "share": round(c / n, 3) if n else 0.0, "improve": IMPROVE.get(theme, "")}
        for theme, c in pain.most_common()
    ]
    return {
        "reviews_analyzed": n,
        "positive_signal": positive,
        "positive_share": round(positive / n, 3) if n else 0.0,
        "pain_points": top,
        "top_pain": top[0]["theme"] if top else "",
        "note": "自建评论痛点分析（关键词信号+频次）；接 LLM 可做语义聚类。数量为信号统计，非精确情感分。",
    }


def run_review_insight(payload: dict[str, Any]) -> dict[str, Any]:
    """skill_agents 风格的可执行处理器：payload={'reviews':[...]} → 结构化痛点。"""
    return summarize_reviews((payload or {}).get("reviews") or [])
