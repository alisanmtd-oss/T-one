"""趋势分析（自建，跑我们自己数据湖的时间序列；免费、不依赖 Google Trends/外网）。

思路：把采集记录按关键词/类目分桶，比较"近一窗"与"前一窗"的出现次数，
得出上升/下降清单。数据越多越准；这是我们自己的趋势，不被任何外部源计费。
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any


def _parse(ts: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def compute_trends(records: list[dict[str, Any]], *, field: str = "keyword",
                   window_days: int = 7, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cur_start = now - timedelta(days=window_days)
    prev_start = now - timedelta(days=2 * window_days)
    cur: Counter[str] = Counter()
    prev: Counter[str] = Counter()
    for r in records or []:
        key = str((r or {}).get(field) or "").strip()
        if not key:
            continue
        dt = _parse((r or {}).get("created_at") or (r or {}).get("captured_at"))
        if not dt:
            continue
        if dt >= cur_start:
            cur[key] += 1
        elif dt >= prev_start:
            prev[key] += 1
    rows = []
    for key in set(cur) | set(prev):
        c, p = cur[key], prev[key]
        delta = c - p
        growth = (delta / p) if p else (1.0 if c else 0.0)
        rows.append({"key": key, "current": c, "previous": p, "delta": delta, "growth": round(growth, 3)})
    rising = sorted([r for r in rows if r["delta"] > 0], key=lambda x: (-x["delta"], -x["growth"]))[:10]
    falling = sorted([r for r in rows if r["delta"] < 0], key=lambda x: (x["delta"], x["growth"]))[:10]
    return {
        "field": field,
        "window_days": window_days,
        "rising": rising,
        "falling": falling,
        "note": "基于我们自己数据湖的采集时间序列，免费、不依赖外网；数据越多越准。",
    }


def run_trend_insight(payload: dict[str, Any]) -> dict[str, Any]:
    payload = payload or {}
    return compute_trends(
        payload.get("records") or [],
        field=str(payload.get("field") or "keyword"),
        window_days=int(payload.get("window_days") or 7),
    )
