from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


STOPWORDS = {
    "the",
    "and",
    "or",
    "for",
    "with",
    "shirt",
    "tee",
    "tshirt",
    "t-shirt",
    "hat",
    "cap",
    "men",
    "women",
    "unisex",
    "gift",
    "new",
    "best",
    "seller",
    "amazon",
    "etsy",
}


@dataclass(slots=True)
class ProductMatch:
    status: str
    score: float
    shared_terms: list[str]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "score": self.score,
            "shared_terms": self.shared_terms,
            "reason": self.reason,
        }


def compare_product_text(target: dict[str, Any], candidate: dict[str, Any]) -> ProductMatch:
    target_terms = product_terms(target)
    candidate_terms = product_terms(candidate)
    if not target_terms or not candidate_terms:
        return ProductMatch("needs_review", 0.0, [], "Not enough text to compare product identity.")
    shared = sorted(target_terms & candidate_terms)
    union = target_terms | candidate_terms
    score = len(shared) / len(union) if union else 0.0
    family = normalize_text(str(target.get("product_family") or ""))
    if family:
        family_terms = tokenize(family)
        if family_terms and family_terms <= candidate_terms:
            score += 0.15
    focus_terms = important_target_terms(target)
    focus_hits = sorted(focus_terms & candidate_terms)
    if len(focus_hits) >= 3:
        score += 0.28
    elif len(focus_hits) >= 2:
        score += 0.18
    score = min(score, 1.0)
    if score >= 0.62 and (len(shared) >= 3 or len(focus_hits) >= 3):
        status = "same_product"
        reason = "Title/category terms strongly overlap with the monitored product."
    elif score >= 0.34 and (len(shared) >= 2 or len(focus_hits) >= 2):
        status = "similar_product"
        reason = "Product appears related but still needs image/detail verification."
    elif shared or focus_hits:
        status = "different_product"
        reason = "Only weak keyword overlap was found."
    else:
        status = "different_product"
        reason = "No meaningful product terms overlap."
    merged_shared = sorted(set(shared) | set(focus_hits))
    return ProductMatch(status, round(score, 3), merged_shared[:12], reason)


def product_terms(fields: dict[str, Any]) -> set[str]:
    values = [
        fields.get("product_name"),
        fields.get("page_title"),
        fields.get("product_family"),
        fields.get("content_theme"),
        fields.get("visible_growth_signal"),
    ]
    for key in ["keywords", "expected_keywords"]:
        value = fields.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif value:
            values.append(value)
    text = " ".join(str(value or "") for value in values)
    return tokenize(text)


def important_target_terms(fields: dict[str, Any]) -> set[str]:
    raw_terms: list[str] = []
    for key in ["product_name", "product_family", "keywords", "expected_keywords"]:
        value = fields.get(key)
        if isinstance(value, list):
            raw_terms.extend(str(item) for item in value)
        elif value:
            raw_terms.append(str(value))
    terms = tokenize(" ".join(raw_terms))
    generic = {"product", "products", "daily", "sensitive", "skin", "care", "market", "search"}
    return {term for term in terms if term not in generic}


def tokenize(text: str) -> set[str]:
    normalized = normalize_text(text)
    terms = set(re.findall(r"[a-z0-9][a-z0-9'-]{1,}", normalized))
    return {term for term in terms if term not in STOPWORDS and len(term) > 2}


def normalize_text(text: str) -> str:
    return text.lower().replace("&", " and ")
