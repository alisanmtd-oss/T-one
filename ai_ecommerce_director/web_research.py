"""联网搜索（自建，免费）：用 DuckDuckGo HTML 端点检索，不需要任何 key。

只做轻量检索，返回 标题 + 链接。失败优雅降级（返回空 + error），
必要时可改用你模型自带的 web_search。解析函数 parse_ddg_html 与网络分离，便于测试。
"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
from typing import Any, Callable

_UA = {"User-Agent": "Mozilla/5.0 (compatible; tk-agent/1.0)"}
_DDG = "https://html.duckduckgo.com/html/?"


def _default_fetch(url: str, timeout: float) -> str:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def parse_ddg_html(html: str, limit: int = 8) -> list[dict[str, str]]:
    """从 DuckDuckGo HTML 结果页提取 标题+真实链接（纯函数，便于测试）。"""
    out: list[dict[str, str]] = []
    for m in re.finditer(r'result__a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html or "", re.DOTALL):
        href = m.group(1)
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        mm = re.search(r"uddg=([^&]+)", href)
        link = urllib.parse.unquote(mm.group(1)) if mm else href
        if title and link.startswith("http"):
            out.append({"title": title, "url": link})
        if len(out) >= limit:
            break
    return out


def web_search(query: str, *, limit: int = 8, timeout: float = 8.0,
               fetch: Callable[[str, float], str] | None = None) -> dict[str, Any]:
    q = str(query or "").strip()
    if not q:
        return {"query": "", "results": [], "count": 0, "note": "空查询"}
    url = _DDG + urllib.parse.urlencode({"q": q})
    try:
        html = (fetch or _default_fetch)(url, timeout)
    except Exception as exc:  # noqa: BLE001 - 联网失败优雅降级
        return {"query": q, "results": [], "count": 0, "error": str(exc),
                "note": "联网失败，已降级；可改用你模型自带的 web_search。"}
    results = parse_ddg_html(html, limit)
    return {"query": q, "results": results, "count": len(results),
            "note": "免费 DuckDuckGo 检索；可能被限流，必要时换成你模型自带的 web_search。"}


def run_web_research(payload: dict[str, Any]) -> dict[str, Any]:
    payload = payload or {}
    return web_search(str(payload.get("query") or ""), limit=int(payload.get("limit") or 8))
