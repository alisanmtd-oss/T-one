from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# AI usage + cost metering. Each LLM call records one event with token counts and
# an estimated USD cost. Events are kept in monthly files (data/usage/<YYYY-MM>.jsonl)
# so monthly summaries stay cheap. Prices are USD per 1,000,000 tokens and are
# editable per model; they are estimates for budgeting, not an exact bill.

USAGE_DIR = "usage"

# Rough default prices (USD per 1M tokens) keyed by substring of the provider name.
# Free tiers are 0. Users can override per model via the add-model form.
DEFAULT_PRICING: list[tuple[str, float, float]] = [
    ("free", 0.0, 0.0),
    ("gpt-main", 5.0, 15.0),
    ("gpt-mini", 0.15, 0.6),
    ("openai-gpt", 2.5, 10.0),
    ("claude", 3.0, 15.0),
    ("gemini", 0.3, 2.5),
    ("deepseek-pro", 0.55, 2.2),
    ("deepseek", 0.27, 1.1),
    ("zhipu-glm-plus", 0.7, 0.7),
    ("zhipu-glm-vision", 0.7, 0.7),
    ("zhipu", 0.1, 0.1),
    ("siliconflow", 0.1, 0.1),
    ("longcat", 0.0, 0.0),
    ("agnes", 0.0, 0.0),
    ("kiro", 0.0, 0.0),
    ("ollama", 0.0, 0.0),
]


def _usage_dir(root: Path) -> Path:
    path = root / "data" / USAGE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _month_key(when: datetime | None = None) -> str:
    return (when or datetime.now(timezone.utc)).strftime("%Y-%m")


def provider_pricing(root: Path, provider: str) -> tuple[float, float]:
    """(input_per_1m, output_per_1m) USD for a provider name."""
    try:
        data = json.loads((root / "config" / "multi_ai.json").read_text(encoding="utf-8-sig"))
        for item in data.get("providers", []) if isinstance(data, dict) else []:
            if isinstance(item, dict) and str(item.get("name") or item.get("id")) == provider:
                if item.get("price_in_per_m") is not None or item.get("price_out_per_m") is not None:
                    return float(item.get("price_in_per_m") or 0.0), float(item.get("price_out_per_m") or 0.0)
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    low = provider.lower()
    for token, price_in, price_out in DEFAULT_PRICING:
        if token in low:
            return price_in, price_out
    return 0.0, 0.0


def estimate_cost(root: Path, provider: str, prompt_tokens: int, completion_tokens: int) -> float:
    price_in, price_out = provider_pricing(root, provider)
    return round(prompt_tokens / 1_000_000 * price_in + completion_tokens / 1_000_000 * price_out, 6)


def record_usage(root: Path, provider: str, model: str, prompt_tokens: int, completion_tokens: int, task: str = "") -> None:
    """Append one usage event. Best-effort: never raise into the LLM call path."""
    try:
        now = datetime.now(timezone.utc)
        prompt_tokens = max(0, int(prompt_tokens or 0))
        completion_tokens = max(0, int(completion_tokens or 0))
        event = {
            "ts": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "provider": provider,
            "model": model or "",
            "task": task or "",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cost_usd": estimate_cost(root, provider, prompt_tokens, completion_tokens),
        }
        path = _usage_dir(root) / f"{_month_key(now)}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 - metering must never break the AI call.
        pass


def _read_month(root: Path, month: str) -> list[dict[str, Any]]:
    path = root / "data" / USAGE_DIR / f"{month}.jsonl"
    events: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return events


def _aggregate(events: list[dict[str, Any]]) -> dict[str, Any]:
    total_cost = 0.0
    total_tokens = 0
    by_model: dict[str, dict[str, Any]] = {}
    for e in events:
        cost = float(e.get("cost_usd") or 0.0)
        tokens = int(e.get("total_tokens") or 0)
        total_cost += cost
        total_tokens += tokens
        key = str(e.get("provider") or "") + " / " + str(e.get("model") or "")
        slot = by_model.setdefault(key, {"calls": 0, "tokens": 0, "cost_usd": 0.0})
        slot["calls"] += 1
        slot["tokens"] += tokens
        slot["cost_usd"] += cost
    models = [
        {"model": key, **{k: (round(v, 4) if k == "cost_usd" else v) for k, v in slot.items()}}
        for key, slot in by_model.items()
    ]
    models.sort(key=lambda item: item["cost_usd"], reverse=True)
    return {
        "calls": len(events),
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 4),
        "by_model": models,
    }


def month_summary(root: Path, month: str | None = None) -> dict[str, Any]:
    month = month or _month_key()
    summary = _aggregate(_read_month(root, month))
    summary["month"] = month
    return summary


def today_summary(root: Path) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    events = [e for e in _read_month(root, _month_key(now)) if str(e.get("date")) == today]
    summary = _aggregate(events)
    summary["date"] = today
    return summary


def available_months(root: Path) -> list[str]:
    path = root / "data" / USAGE_DIR
    if not path.exists():
        return [_month_key()]
    months = sorted((p.stem for p in path.glob("*.jsonl")), reverse=True)
    return months or [_month_key()]
