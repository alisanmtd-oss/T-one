from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .storage import read_records
from .types import IntakeRecord


CREATOR_RECORD_TYPES = {
    "influencer_cooperation",
    "creator_spike_event",
    "viral_content_signal",
    "video_breakdown",
    "video_script",
}


@dataclass(slots=True)
class InfluencerProfile:
    key: str
    handle: str
    platform: str = ""
    country: str = ""
    profile_url: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    whatsapp: str = ""
    dm_url: str = ""
    business_contact: str = ""
    contact_method: str = ""
    follower_count: float = 0
    avg_views: float = 0
    engagement_rate: float = 0
    quote_amount: float = 0
    sample_cost: float = 0
    orders: float = 0
    roi: float = 0
    cooperation_score_input: float | None = None
    content_quality_input: float | None = None
    response_status: str = ""
    cooperation_status: str = ""
    video_posted: bool | None = None
    products: set[str] = field(default_factory=set)
    niches: set[str] = field(default_factory=set)
    record_ids: list[str] = field(default_factory=list)
    source_types: set[str] = field(default_factory=set)
    latest_signal: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        score = score_influencer_profile(self)
        return {
            "key": self.key,
            "handle": self.handle,
            "platform": self.platform or "Unknown",
            "country": self.country or "",
            "profile_url": self.profile_url,
            "contact": {
                "email": self.contact_email,
                "phone": self.contact_phone,
                "whatsapp": self.whatsapp,
                "dm_url": self.dm_url,
                "business_contact": self.business_contact,
                "method": self.contact_method,
                "has_contact": any([self.contact_email, self.contact_phone, self.whatsapp, self.dm_url, self.business_contact]),
            },
            "follower_count": int(self.follower_count) if self.follower_count else 0,
            "follower_segment": follower_segment(self.follower_count),
            "avg_views": int(self.avg_views) if self.avg_views else 0,
            "view_to_follower_ratio": round(self.avg_views / self.follower_count, 4) if self.follower_count else 0,
            "engagement_rate": round(self.engagement_rate, 4),
            "quote_amount": round(self.quote_amount, 2),
            "sample_cost": round(self.sample_cost, 2),
            "orders": int(self.orders) if self.orders else 0,
            "roi": round(self.roi, 2),
            "response_status": self.response_status,
            "cooperation_status": self.cooperation_status,
            "video_posted": self.video_posted,
            "products": sorted(self.products),
            "niches": sorted(self.niches),
            "record_ids": self.record_ids,
            "source_types": sorted(self.source_types),
            "latest_signal": self.latest_signal,
            "notes": self.notes[:6],
            **score,
        }


def build_influencer_library(root: Path, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized_filters = normalize_filters(filters or {})
    records = [record for record in read_records(root) if record.record_type in CREATOR_RECORD_TYPES]
    profiles = aggregate_influencer_profiles(records)
    rows = [profile.to_dict() for profile in profiles.values()]
    rows = apply_filters(rows, normalized_filters)
    rows.sort(
        key=lambda item: (
            float(item.get("score", 0)),
            float(item.get("roi", 0)),
            float(item.get("avg_views", 0)),
        ),
        reverse=True,
    )
    return {
        "summary": summarize_profiles(rows),
        "filters": normalized_filters,
        "profiles": rows,
        "top_a": [item for item in rows if item.get("grade") == "A"][:20],
        "watchlist": [item for item in rows if item.get("grade") == "B"][:20],
        "blocked_or_avoid": [item for item in rows if item.get("grade") == "C"][:20],
        "segments": summarize_segments(rows),
    }


def aggregate_influencer_profiles(records: list[IntakeRecord]) -> dict[str, InfluencerProfile]:
    profiles: dict[str, InfluencerProfile] = {}
    for record in records:
        handle = creator_handle(record.fields)
        profile_url = clean(record.fields.get("profile_url") or record.fields.get("creator_profile_url"))
        if not handle and not profile_url:
            continue
        key = normalized_key(handle or profile_url)
        profile = profiles.setdefault(key, InfluencerProfile(key=key, handle=handle or profile_url))
        merge_record(profile, record)
    return profiles


def merge_record(profile: InfluencerProfile, record: IntakeRecord) -> None:
    fields = record.fields
    profile.source_types.add(record.record_type)
    profile.record_ids.append(record.record_id)
    profile.handle = creator_handle(fields) or profile.handle
    profile.platform = first(profile.platform, fields.get("source_platform"), fields.get("platform"), fields.get("marketplace"))
    profile.country = first(profile.country, fields.get("country"), fields.get("country_code"), fields.get("shop_region"))
    profile.profile_url = first(profile.profile_url, fields.get("profile_url"), fields.get("creator_profile_url"), fields.get("url"))
    profile.contact_email = first(
        profile.contact_email,
        fields.get("contact_email"),
        fields.get("creator_email"),
        fields.get("business_email"),
        fields.get("email"),
    )
    profile.contact_phone = first(
        profile.contact_phone,
        fields.get("contact_phone"),
        fields.get("creator_phone"),
        fields.get("business_phone"),
        fields.get("phone"),
        fields.get("phone_number"),
    )
    profile.whatsapp = first(profile.whatsapp, fields.get("whatsapp"), fields.get("whatsapp_number"), fields.get("whatsapp_url"))
    profile.dm_url = first(
        profile.dm_url,
        fields.get("dm_url"),
        fields.get("contact_url"),
        fields.get("tiktok_dm_url"),
        fields.get("instagram_dm_url"),
        fields.get("youtube_contact_url"),
    )
    profile.business_contact = first(
        profile.business_contact,
        fields.get("business_contact"),
        fields.get("agent_contact"),
        fields.get("contact_person"),
        fields.get("agency"),
    )
    profile.contact_method = first(
        profile.contact_method,
        fields.get("contact_method"),
        fields.get("preferred_contact_method"),
        fields.get("contact_channel"),
    )
    profile.follower_count = max(profile.follower_count, number(fields.get("follower_count") or fields.get("followers") or fields.get("fans")))
    profile.avg_views = max(
        profile.avg_views,
        number(fields.get("avg_views") or fields.get("average_views") or fields.get("baseline_avg_views")),
        number(fields.get("latest_video_views") or fields.get("current_views")) * 0.6,
    )
    profile.engagement_rate = max(profile.engagement_rate, percent_number(fields.get("engagement_rate") or fields.get("interaction_rate")))
    profile.quote_amount = max(
        profile.quote_amount,
        number(fields.get("quote_amount") or fields.get("creator_price") or fields.get("influencer_cost") or fields.get("fee")),
    )
    profile.sample_cost = max(profile.sample_cost, number(fields.get("sample_cost") or fields.get("shipping_cost")))
    profile.orders += number(fields.get("orders") or fields.get("order_count") or fields.get("sales_count"))
    profile.roi = max(profile.roi, number(fields.get("roi") or fields.get("roas")))
    profile.cooperation_score_input = max_optional(
        profile.cooperation_score_input,
        number_or_none(fields.get("cooperation_score") or fields.get("communication_score")),
    )
    profile.content_quality_input = max_optional(
        profile.content_quality_input,
        number_or_none(fields.get("content_quality_score") or fields.get("content_score")),
    )
    profile.response_status = first(profile.response_status, fields.get("response_status"), fields.get("reply_status"), fields.get("contact_status"))
    profile.cooperation_status = first(
        profile.cooperation_status,
        fields.get("cooperation_status"),
        fields.get("collaboration_status"),
        fields.get("status"),
    )
    posted = bool_field(fields.get("video_posted") or fields.get("posted_video") or fields.get("has_video"))
    if posted is not None:
        profile.video_posted = posted if profile.video_posted is None else profile.video_posted or posted
    for key in ["product_name", "product_theme", "product_family"]:
        value = clean(fields.get(key))
        if value:
            profile.products.add(value)
    for key in ["niche", "creator_type", "influencer_type", "target_creator_type", "recommended_creator_type", "audience_profile"]:
        value = clean(fields.get(key))
        if value:
            profile.niches.add(value)
    signal = first(
        "",
        fields.get("latest_signal"),
        fields.get("comment_insights"),
        fields.get("visible_growth_signal"),
        fields.get("hook"),
        fields.get("script_type"),
    )
    if signal:
        profile.latest_signal = signal
    for note in record.director_notes[:2]:
        if note and note not in profile.notes:
            profile.notes.append(note)


def score_influencer_profile(profile: InfluencerProfile) -> dict[str, Any]:
    score = 35.0
    reasons: list[str] = []
    risks: list[str] = []

    if profile.roi >= 3:
        score += 28
        reasons.append("ROI >= 3")
    elif profile.roi >= 1.5:
        score += 16
        reasons.append("ROI positive")
    elif profile.roi > 0:
        score += 7

    if profile.orders >= 50:
        score += 18
        reasons.append("50+ orders")
    elif profile.orders >= 10:
        score += 10
        reasons.append("10+ orders")
    elif profile.orders == 0 and profile.quote_amount > 0:
        score -= 12
        risks.append("paid but no orders yet")

    if profile.avg_views >= 100_000:
        score += 14
        reasons.append("high average views")
    elif profile.avg_views >= 20_000:
        score += 9
    elif profile.avg_views >= 5_000:
        score += 5

    if profile.follower_count:
        ratio = profile.avg_views / profile.follower_count
        if 0.2 <= ratio <= 2.5:
            score += 8
            reasons.append("views match follower size")
        elif ratio < 0.03:
            score -= 8
            risks.append("low view-to-follower ratio")

    if profile.engagement_rate >= 0.05:
        score += 10
        reasons.append("engagement >= 5%")
    elif profile.engagement_rate >= 0.02:
        score += 5

    if profile.cooperation_score_input is not None:
        score += min(12, max(0, profile.cooperation_score_input))
    if profile.content_quality_input is not None:
        score += min(8, max(0, profile.content_quality_input))

    status = f"{profile.response_status} {profile.cooperation_status}".lower()
    if any(word in status for word in ["replied", "reply", "signed", "posted", "cooperative", "good", "responsive"]):
        score += 8
        reasons.append("good cooperation signal")
    if any(word in status for word in ["black", "blacklist", "refuse", "rejected", "no reply", "unresponsive", "bad"]):
        score -= 25
        risks.append("poor cooperation signal")

    if profile.video_posted is True:
        score += 8
        reasons.append("video posted")
    elif profile.video_posted is False:
        score -= 30
        risks.append("did not post video")

    if profile.niches:
        score += 4
    if profile.products:
        score += 3

    score = round(max(0, min(score, 100)), 2)
    if score >= 80 and "did not post video" not in risks:
        grade = "A"
        recommended_action = "Priority sample / repeat cooperation"
    elif score >= 60 and "poor cooperation signal" not in risks:
        grade = "B"
        recommended_action = "Observe / low-cost test"
    else:
        grade = "C"
        recommended_action = "Avoid or blacklist until new evidence"

    return {
        "score": score,
        "grade": grade,
        "recommended_action": recommended_action,
        "fit_reason": reasons[:5],
        "risk_flags": risks[:5],
    }


def apply_filters(rows: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        if filters["platform"] != "all" and filters["platform"].lower() not in str(row.get("platform", "")).lower():
            continue
        if filters["grade"] != "all" and str(row.get("grade")) != filters["grade"]:
            continue
        if filters["segment"] != "all" and str(row.get("follower_segment")) != filters["segment"]:
            continue
        if filters["min_followers"] and float(row.get("follower_count") or 0) < filters["min_followers"]:
            continue
        if filters["max_followers"] and float(row.get("follower_count") or 0) > filters["max_followers"]:
            continue
        query = filters["q"].lower()
        if query:
            text = " ".join(
                [
                    str(row.get("handle", "")),
                    str(row.get("platform", "")),
                    str(row.get("contact", {}).get("email", "")),
                    str(row.get("contact", {}).get("phone", "")),
                    str(row.get("contact", {}).get("whatsapp", "")),
                    str(row.get("contact", {}).get("business_contact", "")),
                    " ".join(row.get("products", [])),
                    " ".join(row.get("niches", [])),
                ]
            ).lower()
            if query not in text:
                continue
        result.append(row)
    return result


def summarize_profiles(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total": len(rows),
        "grade_a": len([item for item in rows if item.get("grade") == "A"]),
        "grade_b": len([item for item in rows if item.get("grade") == "B"]),
        "grade_c": len([item for item in rows if item.get("grade") == "C"]),
        "with_roi": len([item for item in rows if float(item.get("roi") or 0) > 0]),
        "with_video": len([item for item in rows if item.get("video_posted") is True]),
        "with_contact": len([item for item in rows if dict(item.get("contact") or {}).get("has_contact")]),
    }


def summarize_segments(rows: list[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for row in rows:
        segment = str(row.get("follower_segment") or "unknown")
        summary[segment] = summary.get(segment, 0) + 1
    return summary


def normalize_filters(filters: dict[str, Any]) -> dict[str, Any]:
    return {
        "platform": clean(single_value(filters.get("platform"))) or "all",
        "grade": clean(single_value(filters.get("grade"))) or "all",
        "segment": clean(single_value(filters.get("segment"))) or "all",
        "q": clean(single_value(filters.get("q"))),
        "min_followers": number(single_value(filters.get("min_followers"))),
        "max_followers": number(single_value(filters.get("max_followers"))),
    }


def creator_handle(fields: dict[str, Any]) -> str:
    return clean(
        fields.get("creator_handle")
        or fields.get("influencer_handle")
        or fields.get("account_handle")
        or fields.get("author_handle")
        or fields.get("nickname")
        or fields.get("creator_name")
    )


def follower_segment(followers: float) -> str:
    if followers >= 1_000_000:
        return "mega"
    if followers >= 500_000:
        return "macro"
    if followers >= 100_000:
        return "mid"
    if followers >= 10_000:
        return "micro"
    if followers > 0:
        return "nano"
    return "unknown"


def first(*values: Any) -> str:
    for value in values:
        cleaned = clean(value)
        if cleaned:
            return cleaned
    return ""


def clean(value: Any) -> str:
    return str(value or "").strip()


def normalized_key(value: Any) -> str:
    return clean(value).lower().strip("/")


def single_value(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else ""
    return value


def max_optional(existing: float | None, incoming: float | None) -> float | None:
    if incoming is None:
        return existing
    if existing is None:
        return incoming
    return max(existing, incoming)


def number_or_none(value: Any) -> float | None:
    raw = clean(value)
    if not raw:
        return None
    return number(raw)


def number(value: Any) -> float:
    raw = (
        clean(value)
        .lower()
        .replace(",", "")
        .replace("$", "")
        .replace("usd", "")
        .replace("rmb", "")
        .replace("cny", "")
        .replace("¥", "")
    )
    if not raw:
        return 0.0
    multiplier = 1.0
    if raw.endswith("k"):
        multiplier = 1_000
        raw = raw[:-1]
    elif raw.endswith("m"):
        multiplier = 1_000_000
        raw = raw[:-1]
    elif raw.endswith("w"):
        multiplier = 10_000
        raw = raw[:-1]
    try:
        return float(raw) * multiplier
    except ValueError:
        return 0.0


def percent_number(value: Any) -> float:
    raw = clean(value)
    if not raw:
        return 0.0
    if raw.endswith("%"):
        return number(raw[:-1]) / 100
    numeric = number(raw)
    return numeric / 100 if numeric > 1 else numeric


def bool_field(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    raw = clean(value).lower()
    if not raw:
        return None
    if raw in {"1", "true", "yes", "y", "posted", "done", "sent"}:
        return True
    if raw in {"0", "false", "no", "n", "not posted", "none", "missing"}:
        return False
    return None
