from __future__ import annotations

from typing import Any

from .types import IntakeRecord


TIKTOK_VIDEO_HINTS = (
    "tiktok",
    "tik tok",
    "tk shop",
    "tk_shop",
    "tiktok shop",
    "fastmoss",
    "kalodata",
)

NON_TIKTOK_VIDEO_HINTS = (
    "amazon",
    "youtube",
    "instagram",
    "reels",
    "shorts",
    "walmart",
    "etsy",
    "shein",
    "shopify",
    "temu",
    "ebay",
)


def has_tiktok_video_hint(value: Any) -> bool:
    text = normalize_source_text(value)
    return any(hint in text for hint in TIKTOK_VIDEO_HINTS)


def has_non_tiktok_video_hint(value: Any) -> bool:
    text = normalize_source_text(value)
    return any(hint in text for hint in NON_TIKTOK_VIDEO_HINTS)


def allows_tiktok_video_strategy(record: IntakeRecord) -> bool:
    """Only TikTok-side signals should create video analysis or scripts.

    Amazon and other marketplaces can still feed product, listing, image, price,
    review, and ranking decisions. They should not create viral-video actions.
    """

    source_text = record_source_text(record)
    if has_tiktok_video_hint(source_text):
        return True
    if has_non_tiktok_video_hint(source_text):
        return False
    return record.record_type in {"video_script", "video_publish_plan"}


def record_source_text(record: IntakeRecord) -> str:
    fields = record.fields
    values = [
        record.record_type,
        record.source,
        fields.get("source_platform"),
        fields.get("marketplace"),
        fields.get("platform"),
        fields.get("platform_name"),
        fields.get("platform_list"),
        fields.get("data_category"),
        fields.get("collection_target"),
        fields.get("collection_goal"),
        fields.get("analysis_route"),
        fields.get("ranking_type"),
        fields.get("url"),
        fields.get("page_url"),
        fields.get("product_url"),
        fields.get("video_url"),
        fields.get("notes"),
    ]
    return normalize_source_text(values)


def normalize_source_text(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return " ".join(normalize_source_text(item) for item in value).lower()
    if isinstance(value, dict):
        return " ".join(f"{key} {normalize_source_text(item)}" for key, item in value.items()).lower()
    return str(value or "").lower()
