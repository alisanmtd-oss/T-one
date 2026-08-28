"""Prepare truthful, task-local SHEIN manual-operation workspaces.

The module never logs in, uploads, publishes, or mutates a seller account.  It
only creates the local files that the desktop buttons open for a human-guided
workflow.  Ranking observations remain demand signals until a product-level
fact and rights review makes a term eligible.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .workspace_runtime import ensure_task_local_folder, load_workspace_config
from .workspace_schema import find_task_context


SUPPORTED_ACTIONS = {"collect", "keywords", "batch-listing"}
ACTION_DIRECTORIES = {
    "collect": Path("inputs") / "catalog-collector",
    "keywords": Path("inputs") / "keyword-library",
    "batch-listing": Path("inputs") / "batch-listing",
}
KEYWORD_FIELDS = [
    "marketplace",
    "site",
    "locale",
    "category_path",
    "ranking_type",
    "source_period",
    "captured_at",
    "rank",
    "term",
    "term_translation",
    "term_type",
    "metric_name",
    "metric_value",
    "growth_signal",
    "source_url",
    "product_evidence",
    "ip_status",
    "status",
    "notes",
    "updated_at",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _write_text_if_changed(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8-sig") == text:
        return
    path.write_text(text, encoding="utf-8", newline="\n")


def _keyword_source(root: Path) -> Path:
    distilled_source = (
        root.parent
        / "ChatGPT"
        / "SHEIN智能体"
        / "shein-market-keyword-library.csv"
    )
    if distilled_source.is_file():
        return distilled_source
    return root / "skills" / "platform-experts" / "shein" / "assets" / "keyword-library.csv"


def _number(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value or "").replace(",", "").replace("%", "").strip())
    except ValueError:
        return default


def _distill_keyword_library(source: Path, target: Path) -> dict[str, int]:
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="") as handle:
            csv.DictWriter(handle, fieldnames=KEYWORD_FIELDS).writeheader()
        return {"observations": 0, "terms": 0, "eligible": 0, "blocked": 0}

    if "keyword" not in rows[0]:
        normalized = []
        for row in rows:
            updated_at = str(row.get("updated_at") or _now_iso()[:10]).strip()
            item = {
                "marketplace": str(row.get("marketplace") or "shein").strip(),
                "site": str(row.get("site") or "shein-us").strip(),
                "locale": str(row.get("locale") or "en-US").strip(),
                "category_path": str(row.get("category_path") or "Unclassified").strip(),
                "ranking_type": str(row.get("ranking_type") or row.get("source_kind") or "legacy-observation").strip(),
                "source_period": str(row.get("source_period") or updated_at[:10]).strip(),
                "captured_at": str(row.get("captured_at") or updated_at).strip(),
                "rank": str(row.get("rank") or "").strip(),
                "term": str(row.get("term") or "").strip(),
                "term_translation": str(row.get("term_translation") or "").strip(),
                "term_type": str(row.get("term_type") or "candidate").strip(),
                "metric_name": str(row.get("metric_name") or "legacy_demand_signal").strip(),
                "metric_value": str(row.get("metric_value") or row.get("demand_signal") or "").strip(),
                "growth_signal": str(row.get("growth_signal") or "").strip(),
                "source_url": str(row.get("source_url") or source.resolve().as_uri()).strip(),
                "product_evidence": str(
                    row.get("product_evidence")
                    or "Legacy keyword observation only; exact product fact match is required before use."
                ).strip(),
                "ip_status": str(row.get("ip_status") or "review").strip(),
                "status": str(row.get("status") or "reserve").strip(),
                "notes": str(row.get("notes") or "").strip(),
                "updated_at": updated_at,
            }
            if item["ip_status"] not in {"clear", "review", "blocked", "not_applicable"}:
                item["ip_status"] = "review"
            if item["status"] not in {"eligible", "reserve", "rejected", "blocked"}:
                item["status"] = "reserve"
            if item["status"] == "eligible" and item["ip_status"] != "clear":
                item["status"] = "reserve"
            normalized.append(item)
    else:
        groups: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            term = " ".join(str(row.get("keyword") or "").split()).strip()
            if term:
                groups[term.casefold()].append(row)
        normalized = []
        for grouped in groups.values():
            first = grouped[0]
            term = " ".join(str(first.get("keyword") or "").split()).strip()
            boards = sorted({str(row.get("board") or "").strip() for row in grouped if str(row.get("board") or "").strip()})
            windows = sorted({str(row.get("window") or "").strip() for row in grouped if str(row.get("window") or "").strip()})
            blocked = any(str(row.get("status") or "").strip().lower() == "blocked" for row in grouped)
            ranks = [_number(row.get("rank"), 1_000_000) for row in grouped]
            indexes = [_number(row.get("index")) for row in grouped]
            growths = [_number(row.get("growth")) for row in grouped if str(row.get("growth") or "").strip()]
            periods = sorted({str(row.get("period") or "").strip() for row in grouped if str(row.get("period") or "").strip()})
            word_count = len(term.replace("-", " ").split())
            normalized.append(
                {
                    "marketplace": "shein",
                    "site": str(first.get("site") or "shein-us"),
                    "locale": "en-US",
                    "category_path": str(
                        first.get("category")
                        or "Men/Standard Clothing/Men Tops/Men T-Shirts"
                    ),
                    "ranking_type": "+".join(boards) or "ranking-observation",
                    "source_period": "/".join(periods[-2:]) or _now_iso()[:10],
                    "captured_at": periods[-1] if periods else _now_iso(),
                    "rank": str(int(min(ranks))) if ranks and min(ranks) < 1_000_000 else "",
                    "term": term,
                    "term_translation": str(first.get("translation") or "").strip(),
                    "term_type": "long-tail-candidate" if word_count >= 2 else "head",
                    "metric_name": "search_index",
                    "metric_value": str(int(max(indexes or [0]))),
                    "growth_signal": f"peak={max(growths):g}%" if growths else "",
                    "source_url": source.resolve().as_uri(),
                    "product_evidence": "Ranking signal only; exact product fact match is required before use.",
                    "ip_status": "blocked" if blocked else "clear",
                    "status": "blocked" if blocked else "reserve",
                    "notes": f"Distilled from {len(grouped)} observations; windows={'+'.join(windows)}.",
                    "updated_at": periods[-1] if periods else _now_iso()[:10],
                }
            )
        normalized.sort(key=lambda row: (row["status"] == "blocked", row["term"].casefold()))

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=KEYWORD_FIELDS)
        writer.writeheader()
        writer.writerows(normalized)
    return {
        "observations": len(rows),
        "terms": len(normalized),
        "eligible": sum(str(row.get("status") or "") == "eligible" for row in normalized),
        "blocked": sum(str(row.get("status") or "") == "blocked" for row in normalized),
    }


def _store_record(root: Path, task_id: str, store_id: str) -> dict[str, Any]:
    path = root / "projects" / "product-10001-growth" / "connections" / "shein_us_stores.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    candidates = payload.get("stores") if isinstance(payload, dict) else []
    if not isinstance(candidates, list):
        return {}
    return next(
        (
            dict(item)
            for item in candidates
            if isinstance(item, dict)
            and (
                str(item.get("task_id") or "").casefold() == task_id.casefold()
                or str(item.get("store_id") or item.get("external_id") or "").casefold()
                == store_id.casefold()
            )
        ),
        {},
    )


def prepare_shein_manual_workspace(root: Path, payload: dict[str, object]) -> dict[str, object]:
    task_id = str(payload.get("task_id") or "").strip().lower()
    action = str(payload.get("action") or "").strip().lower()
    if action not in SUPPORTED_ACTIONS:
        raise ValueError("SHEIN 人工工作台动作无效。")
    found = find_task_context(load_workspace_config(root), task_id)
    if found is None:
        raise ValueError("所选任务不存在。")
    project, _channel, _store, task = found
    if str(task.get("platform") or "").strip().lower() != "shein":
        raise ValueError("所选任务不是 SHEIN 店铺任务。")
    task_folder, relative_task_folder = ensure_task_local_folder(root, task)
    action_folder = task_folder / ACTION_DIRECTORIES[action]
    action_folder.mkdir(parents=True, exist_ok=True)

    store_id = str(task.get("store_id") or "").strip()
    store = _store_record(root, task_id, store_id)
    keyword_stats = {"observations": 0, "terms": 0, "eligible": 0, "blocked": 0}
    if action == "collect":
        _write_text_if_changed(
            action_folder / "README.md",
            "# 商品来源采集\n\n"
            "把负责人自有、供应商授权或明确可再利用的商品来源放在这里。公开可访问不等于可复制上架。\n\n"
            "必填：source_url、product_name、rights_basis、media_rights、price、inventory、measurements。\n",
        )
        _write_text_if_changed(
            action_folder / "product-source-intake.csv",
            "source_url,product_name,rights_basis,media_rights,price,currency,inventory,warehouse,measurements,status,notes\n",
        )
    elif action == "keywords":
        source = _keyword_source(root)
        keyword_stats = _distill_keyword_library(source, action_folder / "keyword-library.csv")
        _write_text_if_changed(
            action_folder / "README.md",
            "# SHEIN 词库与长尾词\n\n"
            "词库已按词去重。reserve 只是需求信号；必须与具体商品事实逐词匹配并通过 IP 审查后，才可改为 eligible。\n",
        )
    else:
        preflight = {
            "schema_version": 1,
            "task_id": task_id,
            "project_id": str(project.get("id") or task.get("project_id") or ""),
            "platform": "shein",
            "site": "shein-us",
            "store_id": store_id,
            "connection_state": str(store.get("connection_state") or store.get("status") or "unknown"),
            "write_authorized": store.get("write_authorized") is True,
            "exact_workbook": "",
            "exact_leaf_category": "Men/Standard Clothing/Men Tops/Men T-Shirts",
            "status": "needs_owner_product_inputs",
            "blockers": [
                "exact_owner_authorized_product_source_missing",
                "product_level_media_and_ip_rights_missing",
                "live_price_inventory_warehouse_missing",
                "required_measurements_missing",
                "exact_workbook_and_store_publish_confirmation_missing",
            ],
            "external_store_write_actions": 0,
            "updated_at": _now_iso(),
        }
        _write_text_if_changed(
            action_folder / "batch-preflight.json",
            json.dumps(preflight, ensure_ascii=False, indent=2) + "\n",
        )
        _write_text_if_changed(
            action_folder / "README.md",
            "# SHEIN 批量上架人工工作台\n\n"
            "这里先做当前模板预检。只有精确文件、店铺、商品权利、图片、价格、实时库存、仓库和尺寸全部确认后，才进入上传与发布。\n",
        )

    state = {
        "schema_version": 1,
        "task_id": task_id,
        "action": action,
        "platform": "shein",
        "store_id": store_id,
        "local_folder": action_folder.relative_to(root).as_posix(),
        "keyword_stats": keyword_stats,
        "write_authorized": store.get("write_authorized") is True,
        "external_store_write_actions": 0,
        "updated_at": _now_iso(),
    }
    _write_text_if_changed(
        task_folder / "memory" / "shein-manual-operator-state.json",
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
    )
    return {
        "ok": True,
        **state,
        "task_folder": relative_task_folder,
        "absolute_folder": str(action_folder),
        "message": "SHEIN 本地人工工作台已准备；店铺写入 0。",
    }
