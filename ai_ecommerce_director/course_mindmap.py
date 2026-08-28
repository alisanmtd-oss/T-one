from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


COURSE_MINDMAP_PREFIX = "course_mindmap"


@dataclass(slots=True)
class CourseMindMapResult:
    run_date: str
    title: str
    lesson: str
    report: str
    report_path: Path
    json_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "title": self.title,
            "lesson": self.lesson,
            "report": self.report,
            "report_path": str(self.report_path),
            "json_path": str(self.json_path),
        }


def run_course_mindmap(
    root: Path,
    *,
    title: str,
    source_text: str,
    lesson: str = "lesson-01",
    run_date: str | None = None,
) -> CourseMindMapResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    outline = build_course_outline(title=title, source_text=source_text, lesson=lesson)
    report = build_course_mindmap_report(report_date, outline)
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_lesson = re.sub(r"[^0-9A-Za-z_-]+", "_", lesson.strip() or "lesson")
    report_path = output_dir / f"{COURSE_MINDMAP_PREFIX}_{safe_lesson}_{report_date}.md"
    json_path = output_dir / f"{COURSE_MINDMAP_PREFIX}_{safe_lesson}_{report_date}.json"
    report_path.write_text(report, encoding="utf-8")
    json_path.write_text(json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8")
    return CourseMindMapResult(report_date, title, lesson, report, report_path, json_path)


def build_course_outline(*, title: str, source_text: str, lesson: str) -> dict[str, Any]:
    cleaned = clean_course_text(source_text)
    bullets = extract_bullets(cleaned)
    headings = extract_headings(cleaned)
    branches = build_reference_branches(cleaned, bullets, headings)
    return {
        "title": title.strip() or "未命名课程",
        "lesson": lesson.strip() or "lesson-01",
        "source_length": len(cleaned),
        "core_summary": build_core_summary(cleaned, bullets, headings),
        "branches": branches,
        "keywords": extract_keywords(cleaned),
    }


def clean_course_text(text: str) -> str:
    text = text.replace("\ufeff", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_line_prefix(line: str) -> str:
    return re.sub(r"^\s*\d+\s*[:：]\s*", "", line).strip()


def normalize_transcript_noise(text: str) -> str:
    replacements = {
        "Tiktok": "TikTok",
        "tiktok": "TikTok",
        "tk": "TK",
        "Tk": "TK",
        "fastmoss": "FastMoss",
        "kalodata": "Kalodata",
        "glodastory": "GlodaStory",
        "roi": "ROI",
        "roas": "ROAS",
        "gmv": "GMV",
        "psa": "PSA",
        "vsa": "VSA",
    }
    result = text
    for wrong, right in replacements.items():
        result = re.sub(rf"\b{re.escape(wrong)}\b", right, result, flags=re.IGNORECASE)
    return result.strip()


def extract_bullets(text: str) -> list[str]:
    bullets: list[str] = []
    for raw_line in text.splitlines():
        line = normalize_transcript_noise(strip_line_prefix(raw_line))
        line = line.strip(" -•·*✅🔥")
        if len(line) < 4:
            continue
        if line in {"特征：", "执行方案：", "案例参考：", "适用场景："}:
            continue
        parts = re.split(r"[。；;]\s*", line)
        for part in parts:
            part = normalize_transcript_noise(part.strip(" -•·*✅🔥"))
            if len(part) < 4:
                continue
            if len(part) > 86:
                part = part[:84] + "..."
            if part not in bullets:
                bullets.append(part)
    return bullets[:120]


def extract_headings(text: str) -> list[str]:
    headings: list[str] = []
    for raw_line in text.splitlines():
        line = normalize_transcript_noise(strip_line_prefix(raw_line))
        if not line or len(line) > 70:
            continue
        looks_like_heading = bool(
            re.search(r"^(第[一二三四五六七八九十0-9]+[章节]|[一二三四五六七八九十]+、|\d+[\.、]\s*)", line)
        )
        has_course_word = any(word in line for word in ["阶段", "选品", "素材", "达人", "广告", "Listing", "商品卡", "运营", "钩子"])
        if looks_like_heading or has_course_word:
            line = re.sub(r"^\d+[\.、]\s*", "", line)
            if line not in headings:
                headings.append(line)
    return headings[:24]


def extract_keywords(text: str) -> list[str]:
    candidates = [
        "TikTok Shop",
        "TikTok",
        "TK",
        "FastMoss",
        "Kalodata",
        "Amazon",
        "BSR",
        "New Release",
        "Movers & Shakers",
        "商品卡",
        "达人",
        "视频",
        "脚本",
        "钩子",
        "评论",
        "GMV",
        "ROI",
        "ROAS",
        "广告",
        "投流",
        "选品",
        "关键词",
        "差评",
        "侵权",
        "利润",
        "生命周期",
    ]
    lowered = text.lower()
    return [item for item in candidates if item.lower() in lowered][:18]


def build_core_summary(text: str, bullets: list[str], headings: list[str]) -> list[str]:
    summary: list[str] = []
    for item in bullets:
        if any(word in item for word in ["核心", "必须", "重点", "风险", "红利", "商品卡", "达人", "视频", "选品", "投流"]):
            summary.append(item)
        if len(summary) >= 5:
            break
    if summary:
        return summary
    if headings:
        return [f"本节重点：{item}" for item in headings[:5]]
    if bullets:
        return bullets[:5]
    if text:
        return [text[:90]]
    return ["暂无课程文字稿，需要先补录屏逐字稿或课堂纪要。"]


def build_reference_branches(text: str, bullets: list[str], headings: list[str]) -> list[dict[str, Any]]:
    return [
        branch("课程定位", course_position_nodes(bullets, headings)),
        branch("1 选品基础流程", workflow_nodes(bullets)),
        branch("2 选品平台工具", platform_nodes(bullets)),
        branch("3 选品方向", direction_nodes(bullets)),
        branch("4 选品维度指标", dimension_nodes(bullets)),
        branch("5 打品与起盘", launch_nodes(bullets)),
        branch("6 视频素材脚本", video_script_nodes(bullets)),
        branch("7 达人和店铺运营", influencer_store_nodes(bullets)),
        branch("8 风控和侵权", risk_nodes(bullets)),
        branch("9 需对照视频核对", needs_video_review_nodes(text)),
    ]


def branch(name: str, nodes: list[dict[str, Any]]) -> dict[str, Any]:
    return {"name": name, "nodes": dedupe_nodes(nodes)}


def node(text: str, children: list[str] | None = None) -> dict[str, Any]:
    return {"text": text, "children": children or []}


def course_position_nodes(bullets: list[str], headings: list[str]) -> list[dict[str, Any]]:
    nodes = [node(item, ["本节主线", "课堂重点", "对应实操演示"]) for item in headings[:4]]
    nodes.extend(
        [
            node("课程要解决的问题", ["怎么找品", "怎么判断平台机会", "怎么拆素材", "怎么形成执行动作"]),
            node("课程最终要会判断", ["这个品做不做", "为什么做", "缺什么证据", "下一步怎么执行"]),
            node("不能只写概念", ["要有链接", "要有截图", "要有数据", "要有视频脚本", "要有达人名单"]),
            node("内容来源", ["以下分支均出自课程逐字稿", "标准结构对照 TK体系2.0", "未展开处标注需对照视频"]),
        ]
    )
    return nodes[:8]


def workflow_nodes(bullets: list[str]) -> list[dict[str, Any]]:
    nodes = source_nodes(bullets, ["流程", "步骤", "打开", "搜索", "筛选", "记录", "复盘"], "先看证据", "再记指标", limit=5)
    nodes.extend(
        [
            node("1 确定目标", ["商品名", "国家站点", "平台", "价格带", "目标人群"]),
            node("2 找同品竞品", ["TikTok Shop商品页", "FastMoss榜单", "Kalodata榜单", "Amazon BSR补充"]),
            node("3 拆内容打法", ["热视频", "达人视频", "店铺自播", "评论区购买信号"]),
            node("4 出运营结论", ["做/不做", "小测/放量", "补证据/暂停", "进入实验队列"]),
            node("5 写入记忆", ["成功模式", "失败原因", "关键词", "违禁词", "素材模板"]),
        ]
    )
    return nodes[:10]


def platform_nodes(bullets: list[str]) -> list[dict[str, Any]]:
    nodes = source_nodes(bullets, ["FastMoss", "Kalodata", "TikTok", "Amazon", "BSR", "New Release"], "榜单", "商品卡", limit=5)
    nodes.extend(
        [
            node("FastMoss", ["TikTok商品排名", "热视频素材", "达人和店铺", "优先用已登录页面"]),
            node("Kalodata", ["热卖榜单", "短视频/直播", "市场趋势", "和FastMoss交叉验证"]),
            node("TikTok Shop买家端", ["同类竞品", "商品卡", "真实评论", "内容是否带动转化"]),
            node("Amazon", ["BSR", "New Release", "Movers & Shakers", "评论/价格/图片补充验证"]),
            node("其他平台", ["Etsy看设计", "Walmart看价格带", "SHEIN看款式", "eBay看长尾需求"]),
        ]
    )
    return nodes[:10]


def direction_nodes(bullets: list[str]) -> list[dict[str, Any]]:
    nodes = source_nodes(bullets, ["方向", "爆品", "新手", "类目", "蓝海", "趋势", "红利"], "避开假热度", "看增长曲线", limit=5)
    nodes.extend(
        [
            node("不只看大类目", ["必须下钻二级", "必须下钻三级", "看小类目增速", "看新品榜"]),
            node("找突然增长的品", ["24小时增长", "7天增长", "30天增长", "达人新爆点"]),
            node("找内容能讲清楚的品", ["痛点明显", "前后对比强", "3秒内能展示结果", "评论区会追问"]),
            node("找供应链能承接的品", ["有库存", "成本稳定", "发货快", "售后风险可控"]),
            node("全品类轮训", ["美妆个护", "保健品", "服饰鞋包", "珠宝配饰", "手机配件", "家居宠物", "工具小家电"]),
        ]
    )
    return nodes[:10]


def dimension_nodes(bullets: list[str]) -> list[dict[str, Any]]:
    nodes = source_nodes(bullets, ["维度", "销量", "播放", "评论", "利润", "物流", "退货", "评分"], "当前值", "7日变化", limit=5)
    nodes.extend(
        [
            node("市场大小", ["GMV", "榜单位置", "同品数量", "搜索热度"]),
            node("增长速度", ["新增视频", "新增达人", "排名上升", "评论增长"]),
            node("内容爆发力", ["播放量", "完播/互动", "购买意图评论", "可复制脚本"]),
            node("利润空间", ["售价", "成本", "寄样成本", "平台佣金", "广告保本ROI"]),
            node("风险成本", ["侵权", "禁限售", "退货率", "差评痛点", "物流难度"]),
        ]
    )
    return nodes[:10]


def launch_nodes(bullets: list[str]) -> list[dict[str, Any]]:
    nodes = source_nodes(bullets, ["打品", "测品", "起盘", "投流", "预算", "收割", "生命周期"], "测试预算", "止损线", limit=5)
    nodes.extend(
        [
            node("A 测品期", ["小预算", "多素材", "多达人", "看点击和评论信号"]),
            node("B 增长期", ["加达人", "加短视频", "上折扣", "小额投流验证"]),
            node("C 成熟期", ["控ROI", "扩国家/店铺", "优化库存", "拉长生命周期"]),
            node("D 衰退期", ["清库存", "降广告", "换素材角度", "找下一代品"]),
            node("起盘节奏", ["先种草", "再集中收割", "TK是配量机制", "Amazon是买量机制"]),
        ]
    )
    return nodes[:10]


def video_script_nodes(bullets: list[str]) -> list[dict[str, Any]]:
    nodes = source_nodes(bullets, ["视频", "素材", "脚本", "钩子", "运镜", "剪辑", "评论", "达人"], "Hook钩子", "镜头", limit=5)
    nodes.extend(
        [
            node("0-2秒钩子", ["身份认同", "痛点刺激", "反差结果", "价格/优惠", "争议点"]),
            node("2-5秒商品出现", ["让用户知道卖什么", "近景细节", "使用前状态", "不要拖太久"]),
            node("5-10秒证明", ["前后对比", "真人使用", "场景化", "评论/口碑背书"]),
            node("10-15秒转化", ["商品卡", "优惠", "礼物场景", "限时CTA"]),
            node("达人脚本", ["给方向不写死", "保留达人口吻", "避免广告感太重", "要求真实使用镜头"]),
            node("官方号脚本", ["标准化开场", "价格解释", "痛点答疑", "上链接节奏"]),
        ]
    )
    return nodes[:12]


def influencer_store_nodes(bullets: list[str]) -> list[dict[str, Any]]:
    nodes = source_nodes(bullets, ["达人", "红人", "店铺", "联盟", "合作", "BD", "账号"], "粉丝", "均播", limit=5)
    nodes.extend(
        [
            node("达人筛选", ["粉丝量", "均播", "互动率", "内容质量", "粉丝质量"]),
            node("达人分级", ["A级优先寄样", "B级观察", "C级淘汰", "ROI复盘"]),
            node("联系方式", ["邮箱", "主页外链", "TikTok私信", "Instagram", "YouTube", "商务联系方式"]),
            node("店铺运营", ["商品卡", "折扣", "活动报名", "评价维护", "客服响应"]),
            node("内容矩阵", ["1个官方号", "4个渠道号", "达人视频", "直播中控", "AI视频混剪"]),
        ]
    )
    return nodes[:10]


def risk_nodes(bullets: list[str]) -> list[dict[str, Any]]:
    nodes = source_nodes(bullets, ["风险", "侵权", "禁忌", "差评", "审核", "投诉", "专利", "商标"], "证据", "处理动作", limit=5)
    nodes.extend(
        [
            node("侵权词库", ["品牌词", "角色/IP", "明星/球队", "专利外观", "平台禁词"]),
            node("四档审核", ["clear可公开", "borderline观察", "confirmed_ip仅私用", "prohibited驳回"]),
            node("老店保护", ["不自动改价", "不自动投广告", "不自动下架爆品", "不自动发布公开视频"]),
            node("投诉建议中心", ["截图", "视频", "鼠标标注", "AI归类", "进入修复任务"]),
            node("证据不足处理", ["不硬判", "列缺口", "安排补采", "低置信度不能进执行队列"]),
        ]
    )
    return nodes[:10]


def needs_video_review_nodes(text: str) -> list[dict[str, Any]]:
    """逐字稿没覆盖到的课程主题，提示老师对照录屏/截图补充，而不是凭空编。"""
    lowered = text.lower()
    checks = [
        ("逐字稿未展开 TikTok 商品/视频画面", ["tiktok", "tk", "视频"]),
        ("逐字稿未展开 销量/GMV/排名变化", ["销量", "gmv", "rank", "排名"]),
        ("逐字稿未展开 达人名单与合作数据", ["达人", "creator", "influencer", "红人"]),
        ("逐字稿未展开 评论区购买信号与差评痛点", ["评论", "review", "差评"]),
        ("逐字稿未展开 广告/投流/ROAS 数据", ["广告", "roas", "投流"]),
        ("逐字稿未展开 侵权/违禁词检查", ["侵权", "trademark", "copyright", "违禁"]),
    ]
    missing = [label for label, words in checks if not any(word in lowered for word in words)]
    if not missing:
        return [node("本节逐字稿信息较完整", ["可直接成图", "仍建议对照视频核对画面细节"])]
    return [node(label, ["对照视频/截图", "标注时间点", "确认后再补进导图"]) for label in missing]


def source_nodes(bullets: list[str], keywords: list[str], child_a: str, child_b: str, *, limit: int) -> list[dict[str, Any]]:
    picked = []
    for item in bullets:
        if any(keyword.lower() in item.lower() for keyword in keywords):
            picked.append(node(item, [child_a, child_b, "来源于课程文字稿"]))
        if len(picked) >= limit:
            break
    return picked


def dedupe_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in nodes:
        key = str(item.get("text") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def build_course_mindmap_report(run_date: str, outline: dict[str, Any]) -> str:
    title = str(outline.get("title") or "未命名课程")
    lesson = str(outline.get("lesson") or "lesson")
    source_length = int(outline.get("source_length") or 0)
    lines = [
        f"# {title} - 细节思维导图",
        "",
        f"日期：{run_date}",
        f"课程：{lesson}",
        f"来源：课程逐字稿（{lesson}），字数 {source_length}；本图仅基于该逐字稿生成。",
        "",
        "## 老板先看",
        "",
    ]
    for item in outline.get("core_summary", []):
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## 细节思维导图",
            "",
            "```mermaid",
            "mindmap",
            f"  root(({mermaid_label(title)}))",
        ]
    )
    for item_branch in outline.get("branches", []):
        branch_name = mermaid_label(str(item_branch.get("name") or "未命名分支"))
        lines.append(f"    {branch_name}")
        for item_node in item_branch.get("nodes", [])[:12]:
            text = mermaid_label(str(item_node.get("text") or "未命名节点"))
            lines.append(f"      {text}")
            for child in item_node.get("children", [])[:5]:
                lines.append(f"        {mermaid_label(str(child))}")
    lines.extend(
        [
            "```",
            "",
            "## 制图说明（给老师）",
            "",
            "- 每节课单独一张图，不要把多节课混成一锅。",
            "- 逐字稿有口音或错别字时，先按课程常识纠正，再写进导图。",
            "- 选品内容拆到：平台、类目、商品、视频、达人、评论、风险、下一步。",
            "- 视频脚本拆到：钩子、运镜、场景、剪辑节奏、字幕、CTA、评论区购买信号。",
            "- 本图仅取自课程逐字稿；标注「需对照视频核对」的节点请看录屏后再补。",
            "",
            "<details>",
            "<summary>展开文字版细节</summary>",
            "",
        ]
    )
    for item_branch in outline.get("branches", []):
        lines.append(f"### {item_branch.get('name')}")
        for item_node in item_branch.get("nodes", []):
            lines.append(f"- {item_node.get('text')}")
            for child in item_node.get("children", []):
                lines.append(f"  - {child}")
        lines.append("")
    lines.extend(["</details>", ""])
    return "\n".join(lines).rstrip() + "\n"


def mermaid_label(text: str) -> str:
    text = re.sub(r"[\r\n\t]+", " ", text).strip()
    text = text.replace('"', "'")
    text = re.sub(r"\s+", " ", text)
    if len(text) > 46:
        text = text[:44] + "..."
    return f'"{text}"'
