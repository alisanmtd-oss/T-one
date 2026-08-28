from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


PRIVATE_PROJECT_FACTS_PATH = Path("config/private_project_facts.json")


def _default_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_private_project_facts(root: Path | None = None) -> dict[str, Any]:
    """Load project-only facts that must never be embedded in generic runtime code."""

    base = (root or _default_root()).resolve()
    path = base / PRIVATE_PROJECT_FACTS_PATH
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return deepcopy(payload) if isinstance(payload, dict) else {}


def private_project_section(name: str, root: Path | None = None) -> dict[str, Any]:
    payload = load_private_project_facts(root)
    section = payload.get(str(name or "").strip())
    return deepcopy(section) if isinstance(section, dict) else {}


def private_amazon_products(root: Path | None = None) -> list[dict[str, Any]]:
    """Return private Amazon product facts without embedding them in runtime code."""

    section = private_project_section("amazon_operations", root)
    products = section.get("products")
    if not isinstance(products, list):
        return []
    return [deepcopy(item) for item in products if isinstance(item, dict)]


def private_amazon_product(index: int, root: Path | None = None) -> dict[str, Any]:
    products = private_amazon_products(root)
    try:
        item = products[int(index)]
    except (IndexError, TypeError, ValueError):
        return {}
    return deepcopy(item)


def private_amazon_browser_profile(root: Path | None = None) -> str:
    section = private_project_section("amazon_seller_reply", root)
    labels = section.get("browser_labels")
    if isinstance(labels, list):
        for item in labels:
            value = str(item or "").strip()
            if value:
                return value
    return str(section.get("browser_display_name") or "").strip()


def private_amazon_offer(index: int, root: Path | None = None) -> dict[str, Any]:
    section = private_project_section("amazon_finance", root)
    offers = section.get("offer_defaults")
    if not isinstance(offers, list):
        return {}
    try:
        item = offers[int(index)]
    except (IndexError, TypeError, ValueError):
        return {}
    return deepcopy(item) if isinstance(item, dict) else {}
