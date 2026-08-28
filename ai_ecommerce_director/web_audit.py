from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# SEO / AEO / GEO auditor. Pure HTML analysis (audit_html) + best-effort site
# scan (audit_site). No network, no scraping — reads the operator's own site.
# SEO = traditional search (title/meta/headings/structured data/sitemap/robots).
# AEO = answer engines (FAQ/HowTo schema, question-style content).
# GEO = generative engines / LLMs (clear entity schema, llms.txt, not blocked).


def _search(pattern: str, text: str) -> "re.Match[str] | None":
    return re.search(pattern, text, re.IGNORECASE | re.DOTALL)


def audit_html(html_text: str, url: str = "") -> dict[str, Any]:
    text = html_text or ""
    checks: list[dict[str, Any]] = []

    def add(area: str, item: str, ok: bool, detail: str = "", fix: str = "") -> None:
        checks.append({"area": area, "item": item, "ok": bool(ok), "detail": detail, "fix": fix})

    json_ld_blocks = re.findall(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", text, re.IGNORECASE | re.DOTALL)
    ld_types = " ".join(json_ld_blocks).lower()

    # --- SEO ---
    title_match = _search(r"<title[^>]*>(.*?)</title>", text)
    title = title_match.group(1).strip() if title_match else ""
    add("SEO", "标题 title", bool(title) and 10 <= len(title) <= 60, f"“{title[:60]}”（{len(title)}字）", "加 <title>，10-60字、含主关键词")
    desc_match = _search(r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"']([^\"']*)", text)
    desc = desc_match.group(1).strip() if desc_match else ""
    add("SEO", "meta description", bool(desc) and 50 <= len(desc) <= 160, f"{len(desc)}字", "加 description，50-160字")
    h1_count = len(re.findall(r"<h1[\s>]", text, re.IGNORECASE))
    add("SEO", "唯一 H1", h1_count == 1, f"{h1_count} 个", "每页有且仅一个 H1")
    add("SEO", "viewport", bool(_search(r"name=[\"']viewport[\"']", text)), "", "加 <meta name=viewport>")
    add("SEO", "canonical", bool(_search(r"rel=[\"']canonical[\"']", text)), "", "加 <link rel=canonical>")
    add("SEO", "html lang", bool(_search(r"<html[^>]+lang=", text)), "", "设 <html lang=…>")
    add("SEO", "Open Graph", bool(_search(r"property=[\"']og:title[\"']", text)) and bool(_search(r"property=[\"']og:image[\"']", text)), "", "加 og:title/og:description/og:image")
    imgs = re.findall(r"<img\b[^>]*>", text, re.IGNORECASE)
    no_alt = [i for i in imgs if not re.search(r"\balt=", i, re.IGNORECASE)]
    add("SEO", "图片 alt", not imgs or not no_alt, f"{len(no_alt)}/{len(imgs)} 缺 alt", "给所有图片加 alt")
    add("SEO", "结构化数据 JSON-LD", bool(json_ld_blocks), f"{len(json_ld_blocks)} 块", "加 JSON-LD(Organization/Product/Breadcrumb)")

    # --- AEO ---
    add("AEO", "FAQ schema", "faqpage" in ld_types, "", "加 FAQPage JSON-LD + 真实问答内容")
    add("AEO", "HowTo/Article schema", ("howto" in ld_types or "article" in ld_types), "", "适用则加 HowTo/Article schema")
    add("AEO", "问答式内容", bool(_search(r"how |what |why |怎么|如何|是什么|多少", text)), "", "用问题式小标题 + 一句话简明回答")

    # --- GEO ---
    add("GEO", "实体 schema(Organization/Product)", ("organization" in ld_types or "product" in ld_types), "", "加 Organization/Product JSON-LD，让 AI 识别你是谁/卖什么")
    robots_match = _search(r"name=[\"']robots[\"'][^>]+content=[\"']([^\"']*)", text)
    robots_val = robots_match.group(1).lower() if robots_match else ""
    add("GEO", "未对抓取设 noindex", "noindex" not in robots_val, robots_val, "勿对搜索/AI 抓取设 noindex")
    add("GEO", "正文有可被引用的事实", len(re.sub(r"<[^>]+>", " ", text).split()) >= 100, "", "正文给清晰、权威、可引用的事实陈述")
    # 段落可引用性：核心答案写成 134-167 词的独立段落，便于 AI 整段引用（思路参考 MIT 项目 claude-seo）。
    paragraphs = re.findall(r"<p\b[^>]*>(.*?)</p>", text, re.IGNORECASE | re.DOTALL)
    para_words = [len(re.sub(r"<[^>]+>", " ", para).split()) for para in paragraphs]
    citable = any(100 <= words <= 200 for words in para_words)
    add("GEO", "可引用段落(~134-167词)", citable, f"最长段落 {max(para_words) if para_words else 0} 词", "把核心答案写成 134-167 词的独立段落，方便 AI 整段引用")

    passed = sum(1 for c in checks if c["ok"])
    return {
        "url": url,
        "passed": passed,
        "total": len(checks),
        "score": int(round(100 * passed / len(checks))) if checks else 0,
        "checks": checks,
    }


def audit_site(path: str | Path) -> dict[str, Any]:
    base = Path(path)
    html_text = ""
    candidates = list(base.glob("index.html")) + list(base.glob("public/index.html")) + list(base.glob("*/index.html"))
    if candidates:
        try:
            html_text = candidates[0].read_text(encoding="utf-8", errors="replace")
        except OSError:
            html_text = ""
        report = audit_html(html_text, url=str(candidates[0])) if html_text else {}
    else:
        report = {}
    if not report:
        report = {"url": str(base), "passed": 0, "total": 0, "score": 0, "checks": [], "note": "未找到静态 index.html（动态/构建型站点，建议提供线上 URL，或在源码模板里加 meta/结构化数据）"}

    def has(*names: str) -> bool:
        return any((base / name).exists() for name in names)

    report["site_files"] = {
        "sitemap.xml": has("sitemap.xml", "public/sitemap.xml"),
        "robots.txt": has("robots.txt", "public/robots.txt"),
        "llms.txt": has("llms.txt", "public/llms.txt"),
    }
    return report
