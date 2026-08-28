from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from .product_targets import load_product_targets, normalize_list
from .scoring import score_record
from .storage import append_record, read_records
from .types import IntakeRecord


PATENT_SEARCH_CONFIG = Path("config") / "patent_search.json"
PATENT_SEARCH_REPORT_PREFIX = "patent_search"


DEFAULT_PROVIDERS = [
    {
        "id": "google-patents",
        "name": "Google Patents",
        "category": "patent",
        "url_template": "https://patents.google.com/?q={query}",
        "official": False,
        "notes": "Broad patent and design-patent discovery entry. Use it for first-pass matching.",
    },
    {
        "id": "uspto-patent-public-search",
        "name": "USPTO Patent Public Search",
        "category": "patent",
        "url_template": "https://ppubs.uspto.gov/pubwebapp/",
        "official": True,
        "notes": "Official US patent search. Paste the saved query into the official search box for legal review.",
    },
    {
        "id": "uspto-trademark-search",
        "name": "USPTO Trademark Search",
        "category": "trademark",
        "url_template": "https://tmsearch.uspto.gov/",
        "official": True,
        "notes": "Official US trademark search. Use for brand names, logos, slogans, product names, and phrases.",
    },
    {
        "id": "wipo-patentscope",
        "name": "WIPO Patentscope",
        "category": "patent",
        "url_template": "https://patentscope.wipo.int/search/en/search.jsf",
        "official": True,
        "notes": "International patent search entry for non-US markets.",
    },
]


@dataclass(slots=True)
class PatentSearchResult:
    run_date: str
    statuses: list[dict[str, Any]]
    records: list[IntakeRecord]
    report: str
    report_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "statuses": self.statuses,
            "records": [record.to_dict() for record in self.records],
            "report": self.report,
            "report_path": str(self.report_path),
        }


def run_patent_search_agent(root: Path, run_date: str | None = None) -> PatentSearchResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    config = load_patent_search_config(root)
    providers = enabled_providers(config)
    targets = build_patent_targets(root, config)
    statuses: list[dict[str, Any]] = []
    saved_records: list[IntakeRecord] = []

    if not config.get("enabled", True):
        statuses.append({"step": "patent_search", "status": "disabled"})
    elif not targets:
        statuses.append({"step": "patent_search", "status": "no_targets", "reason": "No product or IP search targets configured."})
    else:
        for target in targets[: int(config.get("max_targets_per_run", 20) or 20)]:
            target_records: list[IntakeRecord] = []
            for provider in providers:
                record = build_patent_record(target, provider, report_date)
                if already_saved_patent_record(root, record, report_date):
                    continue
                score, notes = score_record(record.record_type, record.fields)
                record.score = score
                record.director_notes = notes + [
                    "This is an IP discovery lead, not a legal conclusion. Confirm with official databases, authorization files, or counsel before publishing/delisting."
                ]
                append_record(root, record)
                target_records.append(record)
            saved_records.extend(target_records)
            statuses.append(
                {
                    "step": "patent_search",
                    "status": "collected" if target_records else "duplicate",
                    "target": target.get("name"),
                    "query": target.get("query"),
                    "providers_checked": len(providers),
                    "saved_records": len(target_records),
                }
            )

    report = build_patent_report(report_date, statuses, saved_records, config)
    report_path = write_patent_report(root, report_date, report)
    return PatentSearchResult(report_date, statuses, saved_records, report, report_path)


def load_patent_search_config(root: Path) -> dict[str, Any]:
    path = root / PATENT_SEARCH_CONFIG
    if not path.exists():
        return default_patent_search_config()
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        return default_patent_search_config()
    payload.setdefault("providers", DEFAULT_PROVIDERS)
    payload.setdefault("targets", [])
    return payload


def default_patent_search_config() -> dict[str, Any]:
    return {
        "enabled": True,
        "max_targets_per_run": 20,
        "use_product_targets": True,
        "use_recent_hot_records": False,
        "providers": DEFAULT_PROVIDERS,
        "targets": [
            {
                "enabled": True,
                "name": "Melatonin supplement",
                "query": "melatonin gummies bottle label sleep supplement",
                "platforms": ["Amazon", "TikTok Shop", "Walmart"],
                "risk_scope": "product packaging formula name listing image",
            },
            {
                "enabled": True,
                "name": "Graphic tee phrases and artwork",
                "query": "blue collar dad shirt slogan graphic tee",
                "platforms": ["TikTok Shop", "Amazon", "Etsy", "POD"],
                "risk_scope": "trademark slogan copyrighted artwork design patent",
            },
        ],
    }


def enabled_providers(config: dict[str, Any]) -> list[dict[str, Any]]:
    raw = config.get("providers")
    providers = raw if isinstance(raw, list) else DEFAULT_PROVIDERS
    enabled = [item for item in providers if isinstance(item, dict) and item.get("enabled", True)]
    return enabled or DEFAULT_PROVIDERS


def build_patent_targets(root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for item in config.get("targets", []):
        if isinstance(item, dict) and item.get("enabled", True):
            query = str(item.get("query") or item.get("name") or "").strip()
            if query:
                targets.append({**item, "query": query})
    if config.get("use_product_targets", True):
        for target in load_product_targets(root).get("targets", []):
            if not isinstance(target, dict) or not target.get("enabled", True):
                continue
            keywords = normalize_list(target.get("keywords")) or [str(target.get("name") or "")]
            for keyword in keywords[:3]:
                query = " ".join(part for part in [keyword, target.get("product_family"), "patent trademark design"] if part)
                targets.append(
                    {
                        "enabled": True,
                        "name": str(target.get("name") or keyword),
                        "query": query,
                        "platforms": target.get("platforms") or [],
                        "product_target_id": target.get("id"),
                        "reference_image": target.get("reference_image"),
                        "risk_scope": "product target patent trademark copyright scan",
                    }
                )
    if config.get("use_recent_hot_records", True):
        targets.extend(recent_record_targets(root))
    return dedupe_targets(targets)


def recent_record_targets(root: Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for record_type in ["platform_ranking_signal", "viral_content_signal", "hot_link", "video_breakdown"]:
        for record in sorted(read_records(root, record_type), key=lambda item: item.created_at, reverse=True)[:12]:
            fields = record.fields or {}
            name = first_nonempty(fields, ["product_name", "title", "video_title", "ranking_title", "keyword", "target_keyword"])
            if not name or is_bad_ip_target(name):
                continue
            candidates.append(
                {
                    "enabled": True,
                    "name": name,
                    "query": f"{name} patent trademark copyright design",
                    "platforms": [fields.get("marketplace") or fields.get("source_platform") or "Unknown"],
                    "source_record_id": record.record_id,
                    "suspected_listing_url": first_nonempty(fields, ["product_url", "listing_url", "url", "page_url", "ranking_page"]),
                    "risk_scope": "recent hot product or viral content IP scan",
                }
            )
    return candidates


def is_bad_ip_target(name: str) -> bool:
    clean = name.strip().lower()
    if not clean:
        return True
    blocked_exact = {
        "security check",
        "access denied",
        "verify to continue",
        "captcha",
        "login",
        "sign in",
    }
    if clean in blocked_exact:
        return True
    blocked_fragments = ["security check", "verify you are human", "please login", "page not found"]
    if any(fragment in clean for fragment in blocked_fragments):
        return True
    return len(clean) < 4


def dedupe_targets(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    clean: list[dict[str, Any]] = []
    for target in targets:
        query = str(target.get("query") or "").strip()
        if not query:
            continue
        key = query.lower()
        if key in seen:
            continue
        seen.add(key)
        clean.append(target)
    return clean


def build_patent_record(target: dict[str, Any], provider: dict[str, Any], run_date: str) -> IntakeRecord:
    query = str(target.get("query") or target.get("name") or "").strip()
    provider_name = str(provider.get("name") or provider.get("id") or "IP search")
    provider_id = str(provider.get("id") or provider_name).strip()
    category = str(provider.get("category") or "ip_search")
    search_url = provider_search_url(provider, query)
    fields = {
        "risk_element": str(target.get("name") or query),
        "element_category": f"{category}_search",
        "risk_category": "patent_trademark_copyright_design_search",
        "product_name": str(target.get("name") or query),
        "search_query": query,
        "source_platform": provider_name,
        "provider_id": provider_id,
        "platform": ", ".join(normalize_list(target.get("platforms"))),
        "marketplace": ", ".join(normalize_list(target.get("platforms"))),
        "evidence_url": search_url,
        "search_url": search_url,
        "official_database": bool(provider.get("official", False)),
        "provider_notes": str(provider.get("notes") or ""),
        "risk_scope": str(target.get("risk_scope") or "all-platform IP scan"),
        "authorization_status": str(target.get("authorization_status") or "unknown"),
        "authorization_proof": str(target.get("authorization_proof") or ""),
        "suspected_listing_url": str(target.get("suspected_listing_url") or ""),
        "infringing_listing_url": str(target.get("infringing_listing_url") or ""),
        "reference_image": str(target.get("reference_image") or ""),
        "data_category": "patent_ip_search",
        "scan_date": run_date,
        "manual_review_required": True,
    }
    raw_text = (
        f"IP search lead: {provider_name}\n"
        f"Query: {query}\n"
        f"URL: {search_url}\n"
        f"Scope: {fields['risk_scope']}\n"
        "Use this to check patent, design patent, trademark, copyright, logo, phrase, and packaging risk."
    )
    return IntakeRecord(
        record_type="ip_image_risk",
        fields=fields,
        raw_text=raw_text,
        source="patent_search_agent",
        review_status="needs_review",
        confidence=0.72,
        metadata={
            "automation_run_date": run_date,
            "automation_source_id": f"patent-search:{provider_id}",
            "source_record_id": str(target.get("source_record_id") or ""),
        },
    )


def provider_search_url(provider: dict[str, Any], query: str) -> str:
    template = str(provider.get("url_template") or "")
    if "{query}" in template:
        return template.replace("{query}", quote_plus(query))
    return template


def already_saved_patent_record(root: Path, record: IntakeRecord, run_date: str) -> bool:
    fields = record.fields
    key = (
        str(fields.get("provider_id") or "").lower(),
        str(fields.get("search_query") or "").lower(),
        str(fields.get("scan_date") or run_date),
    )
    for existing in read_records(root, "ip_image_risk"):
        existing_fields = existing.fields or {}
        existing_key = (
            str(existing_fields.get("provider_id") or "").lower(),
            str(existing_fields.get("search_query") or "").lower(),
            str(existing_fields.get("scan_date") or existing.created_at[:10]),
        )
        if existing_key == key:
            return True
    return False


def build_patent_report(run_date: str, statuses: list[dict[str, Any]], records: list[IntakeRecord], config: dict[str, Any]) -> str:
    lines = [
        f"# Patent / Trademark / IP Search Agent - {run_date}",
        "",
        "Purpose: collect all-platform IP risk leads into the unified IP/TRO database before listing, image generation, POD publishing, or influencer content reuse.",
        "",
        "Important: these are discovery leads, not legal conclusions. Authorized items should keep proof and allowed channel scope; unauthorized high-risk items go to manual review.",
        "",
        "## Run Status",
    ]
    if not statuses:
        lines.append("- No patent search steps ran.")
    for status in statuses:
        lines.append(
            f"- {status.get('status')}: {status.get('target') or status.get('step')} | query={status.get('query', '')} | saved={status.get('saved_records', 0)}"
        )
    lines.extend(["", "## Saved Leads"])
    if not records:
        lines.append("- No new patent/IP leads were saved today.")
    for record in records[:30]:
        fields = record.fields
        lines.append(f"- {fields.get('product_name')}: {fields.get('source_platform')} | {fields.get('search_query')} | {fields.get('evidence_url')}")
    lines.extend(["", "## Config"])
    lines.append(f"- providers_enabled: {len(enabled_providers(config))}")
    lines.append(f"- use_product_targets: {bool(config.get('use_product_targets', True))}")
    lines.append(f"- use_recent_hot_records: {bool(config.get('use_recent_hot_records', True))}")
    return "\n".join(lines) + "\n"


def write_patent_report(root: Path, run_date: str, content: str) -> Path:
    path = root / "outputs" / f"{PATENT_SEARCH_REPORT_PREFIX}_{run_date}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def first_nonempty(fields: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = str(fields.get(key) or "").strip()
        if value:
            return value
    return ""
