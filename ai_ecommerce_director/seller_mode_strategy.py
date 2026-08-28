from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .seller_mode_skill_packs import seller_mode_skill_pack_snapshot
from .productization import current_context, stable_id, write_audit_log
from .storage import append_record, read_records
from .types import IntakeRecord


SELLER_MODES = {
    "testing_seller": "Testing Seller / 测品型卖家",
    "launch_seller": "Launch Seller / 打品型卖家",
    "factory_seller": "Factory Seller / 工厂型卖家",
    "brand_seller": "Brand Seller / 品牌型卖家",
    "multi_platform_team": "Multi-platform Team / 多平台团队",
}

COMPLIANCE_RED_LINES = [
    "Do not advise under-declared customs value.",
    "Do not advise fake country of origin.",
    "Do not advise wrong HS/HTS classification to reduce duty.",
    "Do not advise split shipments to evade supervision.",
    "Do not advise hiding related-party transactions.",
    "Do not advise fake contracts or black-money remittance paths.",
    "Tax/entity/trade-route scenarios are planning outputs and require professional tax/legal confirmation.",
]

COUNTRY_MARKET_RULES = [
    {
        "country": "US",
        "platforms": ["TikTok Shop", "Amazon", "Walmart", "Shopify"],
        "market_logic": "High content leverage, high AOV tolerance, mature creator and Amazon search ecosystem.",
        "risks": ["strict account health", "IP/TRO exposure", "review/return pressure", "warehouse depth"],
    },
    {
        "country": "MX",
        "platforms": ["TikTok Shop", "Mercado Libre", "Amazon"],
        "market_logic": "Good for lower-ticket goods, direct shipping tests and product-card driven discovery.",
        "risks": ["last-mile stability", "price sensitivity", "payment/localization"],
    },
    {
        "country": "EU",
        "platforms": ["Amazon", "TikTok Shop", "SHEIN", "Etsy"],
        "market_logic": "Better for quality, compliance, eco claims, certification and stable brand positioning.",
        "risks": ["VAT", "product compliance", "environmental claims", "returns"],
    },
    {
        "country": "Middle East",
        "platforms": ["TikTok Shop", "Noon", "Amazon", "Shopify"],
        "market_logic": "Gift, family, beauty, fashion and high-AOV categories can work when localization is strong.",
        "risks": ["cultural fit", "import rules", "payment", "local fulfillment"],
    },
    {
        "country": "SG",
        "platforms": ["TikTok Shop", "Shopee", "Lazada", "SHEIN"],
        "market_logic": "Singapore site: small but operationally clean social commerce tests; keep store, ads and campaign authorization isolated.",
        "risks": ["small volume ceiling", "high service expectation", "local fulfillment cost"],
    },
    {
        "country": "MY",
        "platforms": ["TikTok Shop", "Shopee", "Lazada", "SHEIN"],
        "market_logic": "Malaysia site: strong low-ticket social commerce and campaign cadence; content speed matters more than deep margin.",
        "risks": ["low price ceiling", "fast copycats", "local payment and COD rules"],
    },
    {
        "country": "TH",
        "platforms": ["TikTok Shop", "Shopee", "Lazada", "SHEIN"],
        "market_logic": "Thailand site: creator-led discovery and double-day campaigns can work when localization is strong.",
        "risks": ["language localization", "price sensitivity", "returns/logistics variance"],
    },
    {
        "country": "VN",
        "platforms": ["TikTok Shop", "Shopee", "Lazada", "SHEIN"],
        "market_logic": "Vietnam site: fast-moving content tests and value-led offers; keep campaign rules and local fulfillment separate.",
        "risks": ["local language content", "low price ceiling", "last-mile reliability"],
    },
    {
        "country": "PH",
        "platforms": ["TikTok Shop", "Shopee", "Lazada", "SHEIN"],
        "market_logic": "Philippines site: social commerce and creator content can drive impulse products with clear logistics promises.",
        "risks": ["island delivery variance", "COD/payment handling", "customer service load"],
    },
    {
        "country": "ID",
        "platforms": ["TikTok Shop", "Shopee", "Lazada", "SHEIN"],
        "market_logic": "Indonesia site: large audience potential, but marketplace, shop ownership and local compliance must be handled per route.",
        "risks": ["local compliance", "logistics variance", "high competition"],
    },
]


@dataclass(slots=True)
class SellerModeStrategyResult:
    run_date: str
    seller_profile: dict[str, Any]
    assessment: dict[str, Any]
    capability_scores: list[dict[str, Any]]
    strategy_package: dict[str, Any]
    records: list[dict[str, Any]]
    report: str
    report_path: Path
    json_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "seller_profile": self.seller_profile,
            "assessment": self.assessment,
            "capability_scores": self.capability_scores,
            "strategy_package": self.strategy_package,
            "records": self.records,
            "report": self.report,
            "report_path": str(self.report_path),
            "json_path": str(self.json_path),
        }


def diagnose_seller_mode(root: Path, questionnaire: dict[str, Any], run_date: str | None = None) -> SellerModeStrategyResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    context = current_context(root, payload=questionnaire)
    profile = build_seller_profile(questionnaire, context)
    scores = build_capability_scores(profile)
    assessment = assess_seller_mode(profile, scores)
    strategy = build_strategy_package(profile, assessment, scores)
    generated_records = persist_seller_strategy(root, profile, assessment, scores, strategy)
    write_audit_log(
        root,
        context,
        "seller_mode.diagnose",
        "seller_profile",
        str(profile["seller_profile_id"]),
        after_state={"seller_mode": assessment["seller_mode"], "confidence": assessment["confidence"]},
    )
    report = build_seller_strategy_report(profile, assessment, scores, strategy)
    report_path = write_report(root, report_date, profile["seller_profile_id"], report)
    json_path = write_json(root, report_date, profile["seller_profile_id"], {
        "seller_profile": profile,
        "assessment": assessment,
        "capability_scores": scores,
        "strategy_package": strategy,
        "records": generated_records,
    })
    return SellerModeStrategyResult(report_date, profile, assessment, scores, strategy, generated_records, report, report_path, json_path)


def build_seller_profile(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    seller_name = text(payload, "seller_name", "company_name", "brand_name", default="Unnamed Seller")
    platforms = normalize_list(payload.get("platforms") or payload.get("platform"))
    countries = normalize_list(payload.get("countries") or payload.get("country"))
    product_lines = normalize_product_lines(payload.get("product_lines") or payload.get("factory_skus") or payload.get("products"))
    profile_id = text(payload, "seller_profile_id", default="")
    if not profile_id:
        profile_id = stable_id("seller_profile", context.get("tenant_id"), context.get("workspace_id"), seller_name)
    return {
        "seller_profile_id": profile_id,
        "tenant_id": context.get("tenant_id"),
        "workspace_id": context.get("workspace_id"),
        "seller_name": seller_name,
        "platforms": platforms or ["TikTok Shop"],
        "countries": countries or ["US"],
        "monthly_gmv_usd": number(payload.get("monthly_gmv_usd") or payload.get("monthly_gmv")),
        "store_count": int(number(payload.get("store_count")) or 0),
        "has_factory": truthy(payload.get("has_factory")),
        "has_overseas_warehouse": truthy(payload.get("has_overseas_warehouse")),
        "has_creator_team": truthy(payload.get("has_creator_team")),
        "has_ad_team": truthy(payload.get("has_ad_team")),
        "has_pod_capability": truthy(payload.get("has_pod_capability")),
        "has_b2b_customers": truthy(payload.get("has_b2b_customers")),
        "can_develop_products": truthy(payload.get("can_develop_products") or payload.get("can_open_new_models")),
        "has_brand_assets": truthy(payload.get("has_brand_assets") or payload.get("has_brand")),
        "has_content_assets": truthy(payload.get("has_content_assets")),
        "repeat_purchase_goal": truthy(payload.get("repeat_purchase_goal")),
        "inventory_depth_days": int(number(payload.get("inventory_depth_days")) or 0),
        "cash_budget_usd": number(payload.get("cash_budget_usd") or payload.get("budget_usd") or payload.get("cashflow_budget")),
        "creator_budget_usd": number(payload.get("creator_budget_usd") or payload.get("influencer_budget_usd")),
        "ad_budget_usd": number(payload.get("ad_budget_usd")),
        "sku_count": int(number(payload.get("sku_count") or len(product_lines)) or 0),
        "daily_capacity_units": int(number(payload.get("daily_capacity_units") or payload.get("production_capacity")) or 0),
        "moq": int(number(payload.get("moq")) or 0),
        "lead_time_days": int(number(payload.get("lead_time_days")) or 0),
        "certifications": normalize_list(payload.get("certifications")),
        "manufacturing_origin_country": text(payload, "manufacturing_origin_country", "origin_country", default="China"),
        "entity_jurisdictions": normalize_list(payload.get("entity_jurisdictions")) or ["China", "Hong Kong", "Singapore", "United States"],
        "product_lines": product_lines,
        "notes": text(payload, "notes", default=""),
        "created_at_utc": now_iso(),
    }


def build_capability_scores(profile: dict[str, Any]) -> list[dict[str, Any]]:
    supply_chain = score_from(
        20 if profile["has_factory"] else 0,
        18 if profile["has_overseas_warehouse"] else 0,
        min(25, profile["inventory_depth_days"]),
        min(20, profile["daily_capacity_units"] / 50),
        10 if profile["can_develop_products"] else 0,
    )
    content = score_from(
        25 if profile["has_content_assets"] else 0,
        20 if profile["has_creator_team"] else 0,
        min(25, profile["creator_budget_usd"] / 400),
        15 if "TikTok Shop" in profile["platforms"] else 0,
    )
    creator = score_from(
        35 if profile["has_creator_team"] else 0,
        min(35, profile["creator_budget_usd"] / 300),
        10 if profile["has_content_assets"] else 0,
    )
    ads = score_from(
        35 if profile["has_ad_team"] else 0,
        min(45, profile["ad_budget_usd"] / 300),
        10 if profile["monthly_gmv_usd"] > 10000 else 0,
    )
    risk = score_from(
        25 if profile["certifications"] else 0,
        15 if profile["has_overseas_warehouse"] else 0,
        15 if profile["has_brand_assets"] else 0,
        10 if profile["store_count"] >= 2 else 0,
    )
    capital = score_from(
        min(55, profile["cash_budget_usd"] / 500),
        min(20, profile["monthly_gmv_usd"] / 5000),
        10 if profile["inventory_depth_days"] >= 30 else 0,
    )
    factory = score_from(
        35 if profile["has_factory"] else 0,
        20 if profile["can_develop_products"] else 0,
        min(20, profile["daily_capacity_units"] / 80),
        min(10, profile["sku_count"]),
        10 if profile["has_b2b_customers"] else 0,
    )
    brand = score_from(
        30 if profile["has_brand_assets"] else 0,
        20 if profile["has_content_assets"] else 0,
        20 if profile["repeat_purchase_goal"] else 0,
        10 if profile["monthly_gmv_usd"] > 20000 else 0,
    )
    dimensions = {
        "supply_chain": supply_chain,
        "content": content,
        "creator": creator,
        "ads": ads,
        "risk_control": risk,
        "capital": capital,
        "factory": factory,
        "brand": brand,
    }
    return [
        {
            "seller_capability_score_id": stable_id("seller_capability", profile["seller_profile_id"], key),
            "seller_profile_id": profile["seller_profile_id"],
            "score_dimension": key,
            "score": int(round(value)),
            "level": score_level(value),
        }
        for key, value in dimensions.items()
    ]


def assess_seller_mode(profile: dict[str, Any], scores: list[dict[str, Any]]) -> dict[str, Any]:
    score_map = {item["score_dimension"]: int(item["score"]) for item in scores}
    mode_scores = {
        "testing_seller": 35
        + (20 if not profile["has_factory"] else 0)
        + (15 if profile["cash_budget_usd"] < 10000 else 0)
        + (10 if profile["inventory_depth_days"] < 30 else 0)
        + (10 if score_map["supply_chain"] < 50 else 0)
        - (20 if profile["has_brand_assets"] else 0)
        - (15 if profile["repeat_purchase_goal"] else 0)
        - (10 if profile["monthly_gmv_usd"] > 20000 else 0),
        "launch_seller": score_map["capital"] * 0.25
        + score_map["content"] * 0.25
        + score_map["creator"] * 0.2
        + score_map["ads"] * 0.15
        + min(15, profile["inventory_depth_days"] / 3),
        "factory_seller": score_map["factory"] * 0.55 + score_map["supply_chain"] * 0.25 + (20 if profile["has_factory"] else 0),
        "brand_seller": score_map["brand"] * 0.55 + score_map["content"] * 0.15 + (25 if profile["repeat_purchase_goal"] else 0) + (10 if profile["monthly_gmv_usd"] > 20000 else 0),
        "multi_platform_team": min(100, len(profile["platforms"]) * 18 + profile["store_count"] * 8 + score_map["risk_control"] * 0.25),
    }
    seller_mode = max(mode_scores, key=lambda key: mode_scores[key])
    sorted_scores = sorted(mode_scores.items(), key=lambda item: item[1], reverse=True)
    confidence = min(0.95, max(0.45, (sorted_scores[0][1] - sorted_scores[1][1] + 45) / 100))
    return {
        "seller_mode_assessment_id": stable_id("seller_mode_assessment", profile["seller_profile_id"], now_iso()),
        "seller_profile_id": profile["seller_profile_id"],
        "seller_mode": seller_mode,
        "seller_mode_label": SELLER_MODES[seller_mode],
        "confidence": round(confidence, 2),
        "mode_scores": {key: int(round(value)) for key, value in mode_scores.items()},
        "capability_summary": capability_summary(score_map),
        "created_at_utc": now_iso(),
    }


def build_strategy_package(profile: dict[str, Any], assessment: dict[str, Any], scores: list[dict[str, Any]]) -> dict[str, Any]:
    mode = str(assessment["seller_mode"])
    package = {
        "seller_strategy_package_id": stable_id("seller_strategy_package", profile["seller_profile_id"], mode),
        "seller_profile_id": profile["seller_profile_id"],
        "seller_mode": mode,
        "seller_mode_label": assessment["seller_mode_label"],
        "capability_scores": scores,
        "recommended_strategy": recommended_strategy(mode, profile),
        "not_recommended_strategy": not_recommended_strategy(mode, profile),
        "risk_warnings": risk_warnings(mode, profile),
        "first_30_day_plan": first_30_day_plan(mode, profile),
        "first_90_day_plan": first_90_day_plan(mode, profile),
        "platform_fit": build_platform_fit(profile, mode),
        "country_market_fit": build_country_market_fit(profile, mode),
        "fit_flags": fit_flags(mode),
        "automation_guidance": automation_guidance(mode),
        "professional_review_required": mode == "factory_seller",
        "created_at_utc": now_iso(),
    }
    if mode == "factory_seller":
        package["factory_globalization"] = build_factory_globalization_plan(profile)
    return package


def persist_seller_strategy(
    root: Path,
    profile: dict[str, Any],
    assessment: dict[str, Any],
    scores: list[dict[str, Any]],
    strategy: dict[str, Any],
) -> list[dict[str, Any]]:
    records: list[IntakeRecord] = []
    records.append(make_record("seller_profile", profile["seller_profile_id"], profile))
    records.append(make_record("seller_mode_assessment", assessment["seller_mode_assessment_id"], assessment))
    for score in scores:
        records.append(make_record("seller_capability_score", score["seller_capability_score_id"], score))
    records.append(make_record("seller_strategy_package", strategy["seller_strategy_package_id"], strategy))
    mode_table = {
        "testing_seller": "testing_seller_playbook",
        "launch_seller": "launch_seller_playbook",
        "factory_seller": "factory_seller_playbook",
        "brand_seller": "brand_seller_playbook",
        "multi_platform_team": "brand_seller_playbook",
    }[strategy["seller_mode"]]
    playbook_id = stable_id(mode_table, profile["seller_profile_id"], strategy["seller_mode"])
    records.append(make_record(mode_table, playbook_id, {"seller_profile_id": profile["seller_profile_id"], **strategy}))
    if strategy["seller_mode"] == "factory_seller":
        records.extend(factory_records(profile, strategy["factory_globalization"]))
    for record in records:
        append_record(root, record)
    return [record.to_dict() for record in records]


def make_record(record_type: str, record_id: str, fields: dict[str, Any]) -> IntakeRecord:
    return IntakeRecord(
        record_id=record_id,
        record_type=record_type,
        fields=fields,
        raw_text=json.dumps(fields, ensure_ascii=False),
        source="seller_mode_strategy_system",
        score={"priority": 80},
        director_notes=["Seller Mode Strategy System generated this record."],
    )


def factory_records(profile: dict[str, Any], plan: dict[str, Any]) -> list[IntakeRecord]:
    records: list[IntakeRecord] = []
    for item in plan.get("product_line_diagnosis", []):
        record_id = stable_id("factory_product_line", profile["seller_profile_id"], item.get("product_line_name"))
        records.append(make_record("factory_product_line", record_id, {"factory_product_line_id": record_id, "seller_profile_id": profile["seller_profile_id"], **item}))
        tariff_id = stable_id("tariff_classification", profile["seller_profile_id"], item.get("product_line_name"))
        records.append(make_record("tariff_classification_record", tariff_id, {
            "tariff_classification_record_id": tariff_id,
            "seller_profile_id": profile["seller_profile_id"],
            "product_line_name": item.get("product_line_name"),
            "category": item.get("category"),
            "status": "requires_official_lookup",
            "allowed_output": "Scenario planning only. Use official HS/HTS resources and broker/legal review before import.",
            "red_lines": [
                "Do not choose wrong HS/HTS codes to reduce duty.",
                "Do not under-declare customs value.",
            ],
        }))
    capacity_id = stable_id("factory_capacity", profile["seller_profile_id"])
    records.append(make_record("factory_capacity_profile", capacity_id, {"factory_capacity_profile_id": capacity_id, "seller_profile_id": profile["seller_profile_id"], **plan["capacity_profile"]}))
    for fit in plan.get("country_market_fit", []):
        record_id = stable_id("country_market_fit", profile["seller_profile_id"], fit.get("country"), fit.get("primary_platform"))
        records.append(make_record("country_market_fit", record_id, {"country_market_fit_id": record_id, "seller_profile_id": profile["seller_profile_id"], **fit}))
    for fit in plan.get("platform_fit", []):
        record_id = stable_id("platform_fit", profile["seller_profile_id"], fit.get("platform"))
        records.append(make_record("platform_fit_score", record_id, {"platform_fit_score_id": record_id, "seller_profile_id": profile["seller_profile_id"], **fit}))
    for scenario in plan.get("landed_cost_scenarios", []):
        record_id = stable_id("landed_cost", profile["seller_profile_id"], scenario.get("scenario_name"))
        records.append(make_record("landed_cost_scenario", record_id, {"landed_cost_scenario_id": record_id, "seller_profile_id": profile["seller_profile_id"], **scenario}))
    for scenario in plan.get("tax_entity_scenarios", []):
        record_id = stable_id("tax_entity", profile["seller_profile_id"], scenario.get("scenario_name"))
        records.append(make_record("tax_entity_scenario", record_id, {"tax_entity_scenario_id": record_id, "seller_profile_id": profile["seller_profile_id"], **scenario}))
    for jurisdiction in profile.get("entity_jurisdictions", []):
        record_id = stable_id("company_structure", profile["seller_profile_id"], jurisdiction)
        records.append(make_record("company_structure_option", record_id, {
            "company_structure_option_id": record_id,
            "seller_profile_id": profile["seller_profile_id"],
            "jurisdiction": jurisdiction,
            "purpose": "Evaluate banking, marketplace access, tax registration, substance and reporting fit.",
            "requires_tax_legal_review": True,
            "allowed_output": "Comparison and checklist only; no tax evasion, fake contracts or hidden related-party transactions.",
        }))
    for route in plan.get("trade_route_scenarios", []):
        record_id = stable_id("trade_route", profile["seller_profile_id"], route.get("route_name"))
        records.append(make_record("trade_route_scenario", record_id, {"trade_route_scenario_id": record_id, "seller_profile_id": profile["seller_profile_id"], **route}))
    origin_id = stable_id("manufacturing_origin", profile["seller_profile_id"], profile.get("manufacturing_origin_country"))
    records.append(make_record("manufacturing_origin_option", origin_id, {
        "manufacturing_origin_option_id": origin_id,
        "seller_profile_id": profile["seller_profile_id"],
        "origin_country": profile.get("manufacturing_origin_country"),
        "allowed_output": "Declare origin only when real manufacturing or substantial transformation supports it.",
        "required_evidence": ["factory record", "BOM", "process flow", "commercial invoice", "logistics documents"],
        "red_lines": ["Do not advise fake country of origin.", "Do not use paper-only routing to pretend origin changed."],
    }))
    for item in plan.get("brand_product_development", []):
        record_id = stable_id("brand_product_dev", profile["seller_profile_id"], item.get("product_line_name"))
        records.append(make_record("brand_product_development_plan", record_id, {"brand_product_development_plan_id": record_id, "seller_profile_id": profile["seller_profile_id"], **item}))
    for item in plan.get("export_plan", []):
        record_id = stable_id("factory_export_plan", profile["seller_profile_id"], item.get("target_country"), item.get("platform"))
        records.append(make_record("factory_export_plan", record_id, {"factory_export_plan_id": record_id, "seller_profile_id": profile["seller_profile_id"], **item}))
    compliance_id = stable_id("compliance_review", profile["seller_profile_id"], "factory_globalization")
    records.append(make_record("compliance_advisor_review", compliance_id, {"compliance_advisor_review_id": compliance_id, "seller_profile_id": profile["seller_profile_id"], "review_topic": "factory_globalization", "required": True, "red_lines": COMPLIANCE_RED_LINES}))
    return records


def recommended_strategy(mode: str, profile: dict[str, Any]) -> list[str]:
    if mode == "testing_seller":
        return [
            "Monitor middle-rank rising products, not only top sellers.",
            "Use small-batch, direct shipping or light inventory tests.",
            "Separate traffic products from profit products.",
            "Keep winners only while margin and return signals stay healthy.",
            "Exit before competing with factory sellers on bottom price.",
        ]
    if mode == "launch_seller":
        return [
            "Build a material matrix before scaling: hooks, creators, scenes and CTAs.",
            "Use small-budget tests first, then push winners through creator matrix and GMV Max.",
            "Protect inventory days, score and refund rate before aggressive scaling.",
            "Use natural traffic as the harvest layer after paid/content tests prove demand.",
        ]
    if mode == "factory_seller":
        return [
            "Start with factory SKU and capacity diagnosis.",
            "Choose country-platform entry sequence from landed cost and demand fit.",
            "Use TikTok to test content and audience, Amazon to catch search, SHEIN/B2B for stable orders where fit exists.",
            "Convert market pain points into product development and packaging upgrades.",
            "Run tax/entity/trade-route scenarios only as planning output for tax/legal review.",
        ]
    if mode == "brand_seller":
        return [
            "Prioritize brand memory, repeat purchase and content asset reuse.",
            "Create product families and hero offers instead of only chasing short-cycle winners.",
            "Use creator content and reviews to strengthen trust and lifecycle extension.",
        ]
    return [
        "Create channel-specific playbooks rather than one platform plan.",
        "Centralize store data, creator data, risk and finance into one review cadence.",
        "Give each platform a role: discovery, search, stable order, B2B or retention.",
    ]


def not_recommended_strategy(mode: str, profile: dict[str, Any]) -> list[str]:
    common = ["Do not execute high-risk platform/store actions without approval."]
    if mode == "testing_seller":
        return common + [
            "Do not chase the final margin of a declining winner.",
            "Do not deep-stock before content and conversion signals are proven.",
            "Do not fight factory sellers in a price war.",
        ]
    if mode == "launch_seller":
        return common + [
            "Do not scale from one winning material only.",
            "Do not break score, fulfillment or stock for short-term GMV.",
            "Do not ignore creator fatigue and material decay.",
        ]
    if mode == "factory_seller":
        return common + COMPLIANCE_RED_LINES
    return common + ["Do not mix brand assets with unreviewed IP, celebrity or competitor materials."]


def risk_warnings(mode: str, profile: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if profile["inventory_depth_days"] < 14 and mode in {"launch_seller", "factory_seller"}:
        warnings.append("Inventory depth is thin for scaling. Scaling may create stockout and score risk.")
    if profile["creator_budget_usd"] <= 0 and "TikTok Shop" in profile["platforms"]:
        warnings.append("TikTok needs creator/content testing. Missing creator budget reduces launch confidence.")
    if mode == "factory_seller" and not profile["certifications"]:
        warnings.append("Factory export plan needs product certificates/compliance docs before EU/Walmart/Amazon scale.")
    if profile["cash_budget_usd"] < 3000 and mode == "launch_seller":
        warnings.append("Launch seller mode needs budget for material, creator, inventory and tests; current cash budget looks low.")
    if not warnings:
        warnings.append("No critical blocker detected, but real platform data and store metrics are still required before execution.")
    return warnings


def first_30_day_plan(mode: str, profile: dict[str, Any]) -> list[str]:
    if mode == "testing_seller":
        return [
            "Create 10-20 monitored product targets by category and country.",
            "Pick 3-5 mid-rank rising products for small tests.",
            "Prepare lightweight listing, product-card and 3 short-video angles per product.",
            "Define stop loss: no click, no add-to-cart, no order, high refund or logistics issue.",
        ]
    if mode == "launch_seller":
        return [
            "Choose 1-2 high-margin launch products with enough inventory.",
            "Prepare at least 20 content angles and creator briefs.",
            "Run small-budget content/creator tests and rank winners.",
            "Create scale rules and stop-loss rules before GMV Max or ad expansion.",
        ]
    if mode == "factory_seller":
        return [
            "Finish SKU/capacity/cost/certification diagnosis.",
            "Select 2 target countries and 2 platform routes for first validation.",
            "Build landed cost scenarios and professional review checklist.",
            "Use market reviews and creator feedback to define the next product-development batch.",
        ]
    if mode == "brand_seller":
        return [
            "Define hero product, hero audience and brand content pillars.",
            "Collect competitor reviews and creator scripts for brand differentiation.",
            "Build repeat-purchase and product-family plan.",
        ]
    return [
        "Map platforms by role: TikTok discovery, Amazon search, SHEIN stable orders, B2B large orders.",
        "Build unified data import and store dashboard.",
        "Run one controlled category pilot before expanding.",
    ]


def first_90_day_plan(mode: str, profile: dict[str, Any]) -> list[str]:
    if mode == "testing_seller":
        return [
            "Retain only products with positive margin and stable delivery.",
            "Build a failure database for bad suppliers, high returns and weak hooks.",
            "Move proven products from light test to controlled stock; exit decaying links early.",
        ]
    if mode == "launch_seller":
        return [
            "Scale winners with creator matrix, natural traffic and controlled paid budget.",
            "Extend lifecycle through new scenes, bundles, reviews and repeat-purchase offers.",
            "Build a weekly material decay and stock-risk review.",
        ]
    if mode == "factory_seller":
        return [
            "Turn first validation into country-platform entry sequence.",
            "Create product-development roadmap from reviews, returns and creator feedback.",
            "Prepare entity/trade/tax scenarios for professional review and banking/KYC readiness.",
            "Decide whether to add Amazon/SHEIN/B2B after TikTok audience validation.",
        ]
    if mode == "brand_seller":
        return [
            "Build brand matrix by audience, product family and content pillar.",
            "Develop creator community and review-driven product iterations.",
        ]
    return [
        "Expand by proven platform role and country fit.",
        "Create channel owners, unified approval queue and weekly AI review meeting.",
    ]


def build_platform_fit(profile: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    platforms = ["TikTok Shop", "Amazon", "SHEIN", "Walmart", "Etsy", "Mercado Libre", "B2B", "Shopify"]
    result: list[dict[str, Any]] = []
    for platform in platforms:
        score = 40
        if platform in profile["platforms"]:
            score += 15
        if platform == "TikTok Shop":
            score += 20 if profile["has_content_assets"] or profile["has_creator_team"] else 5
        if platform == "Amazon":
            score += 15 if profile["has_overseas_warehouse"] or profile["has_brand_assets"] else 5
        if platform == "SHEIN":
            score += 20 if profile["has_factory"] and profile["daily_capacity_units"] > 0 else 5
        if platform == "B2B":
            score += 25 if profile["has_factory"] or profile["has_b2b_customers"] else 0
        if platform == "Etsy":
            score += 15 if profile["has_pod_capability"] or profile["can_develop_products"] else 0
        if mode == "testing_seller" and platform in {"SHEIN", "Walmart", "B2B"}:
            score -= 15
        result.append({
            "platform": platform,
            "fit_score": max(0, min(100, int(score))),
            "role": platform_role(platform),
            "entry_advice": platform_entry_advice(platform, mode),
        })
    return sorted(result, key=lambda item: int(item["fit_score"]), reverse=True)


def build_country_market_fit(profile: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    fits: list[dict[str, Any]] = []
    for rule in COUNTRY_MARKET_RULES:
        base = 45
        if rule["country"] in profile["countries"]:
            base += 15
        if mode == "factory_seller" and rule["country"] in {"US", "EU", "Middle East"}:
            base += 12
        if mode == "testing_seller" and rule["country"] in {"MX", "SG", "MY", "TH", "VN", "PH", "ID"}:
            base += 12
        if mode == "launch_seller" and rule["country"] == "US":
            base += 15
        fits.append({
            "country": rule["country"],
            "primary_platform": rule["platforms"][0],
            "platforms": rule["platforms"],
            "fit_score": min(100, base),
            "market_logic": rule["market_logic"],
            "risk_points": rule["risks"],
        })
    return sorted(fits, key=lambda item: int(item["fit_score"]), reverse=True)


def build_factory_globalization_plan(profile: dict[str, Any]) -> dict[str, Any]:
    product_lines = profile["product_lines"] or [{"product_line_name": "Factory SKU line", "category": "unknown"}]
    product_diagnosis = [
        {
            "product_line_name": item.get("product_line_name") or item.get("name") or "Factory SKU line",
            "category": item.get("category") or "unknown",
            "cost": item.get("cost"),
            "moq": item.get("moq") or profile["moq"],
            "lead_time_days": item.get("lead_time_days") or profile["lead_time_days"],
            "recommended_channels": factory_product_channels(item, profile),
            "development_advice": "Use review pain points, creator feedback, material/color/packaging upgrades and seasonal/IP-safe variants.",
        }
        for item in product_lines[:20]
    ]
    platform_fit = build_platform_fit(profile, "factory_seller")
    country_fit = build_country_market_fit(profile, "factory_seller")
    return {
        "capacity_profile": {
            "daily_capacity_units": profile["daily_capacity_units"],
            "sku_count": profile["sku_count"],
            "moq": profile["moq"],
            "lead_time_days": profile["lead_time_days"],
            "certifications": profile["certifications"],
            "small_batch_fast_response": profile["moq"] <= 200 or profile["lead_time_days"] <= 10,
        },
        "product_line_diagnosis": product_diagnosis,
        "country_market_fit": country_fit,
        "platform_fit": platform_fit,
        "landed_cost_engine": {
            "formula": "Factory Cost + Export Cost + Freight + Import Duty + Additional Tariffs + Customs/Broker Fee + Warehouse Cost + Fulfillment Cost + Return Reserve + Platform Fee + Tax Compliance Cost",
            "official_tariff_note": "US tariff classification should be checked against official HTS/USITC resources; EU/other markets need local tariff and VAT confirmation.",
        },
        "landed_cost_scenarios": [
            {
                "scenario_name": "China factory + US warehouse + TikTok US",
                "cost_components": ["factory_cost", "export_cost", "freight", "import_duty", "warehouse", "fulfillment", "returns", "platform_fee", "creator_commission"],
                "recommended_use": "Content and audience validation for high-potential product lines.",
                "professional_review_required": True,
            },
            {
                "scenario_name": "China/HK entity + US warehouse + Amazon/Walmart",
                "cost_components": ["factory_cost", "freight", "import_duty", "FBA/WFS_or_3PL", "PPC", "returns", "tax_compliance"],
                "recommended_use": "Search demand capture after content validation.",
                "professional_review_required": True,
            },
        ],
        "tax_entity_scenarios": [
            {
                "scenario_name": "China company + direct export",
                "advantages": ["simple starting point", "factory control"],
                "watch_points": ["platform access", "banking/KYC", "VAT/sales tax", "related party pricing if other entities are used"],
                "requires_tax_legal_review": True,
            },
            {
                "scenario_name": "Hong Kong / Singapore holding or trading company",
                "advantages": ["cross-border banking option", "regional expansion flexibility"],
                "watch_points": ["substance", "transfer pricing", "profit attribution", "bank KYC"],
                "requires_tax_legal_review": True,
            },
            {
                "scenario_name": "US local entity + US warehouse",
                "advantages": ["platform trust", "local banking", "Amazon/Walmart readiness"],
                "watch_points": ["sales tax", "income tax", "state registration", "related-party transactions"],
                "requires_tax_legal_review": True,
            },
        ],
        "trade_route_scenarios": [
            {
                "route_name": "China -> US warehouse -> TikTok/Amazon customer",
                "best_for": "US content and search validation.",
                "risk_points": ["HTS classification", "duty", "returns", "warehouse SLA"],
            },
            {
                "route_name": "China -> regional hub -> local marketplace",
                "best_for": "SG / MY / TH / VN / PH / ID and MX low-ticket tests.",
                "risk_points": ["last-mile cost", "local compliance", "payment and returns"],
            },
        ],
        "brand_product_development": [
            {
                "product_line_name": item.get("product_line_name") or item.get("name") or "Factory SKU line",
                "inputs": ["market trend", "negative reviews", "creator feedback", "price band", "material upgrade", "color upgrade", "bundle upgrade", "safe seasonal design"],
                "output": "Next product-development batch with channel-specific positioning.",
            }
            for item in product_lines[:10]
        ],
        "export_plan": [
            {
                "target_country": fit["country"],
                "platform": fit["primary_platform"],
                "stage": "validate" if index == 0 else "observe",
                "required_docs": ["product certificate if applicable", "cost sheet", "SKU sheet", "logistics quote", "tax/legal review notes"],
            }
            for index, fit in enumerate(country_fit[:5])
        ],
        "compliance_red_lines": COMPLIANCE_RED_LINES,
    }


def build_seller_strategy_report(
    profile: dict[str, Any],
    assessment: dict[str, Any],
    scores: list[dict[str, Any]],
    strategy: dict[str, Any],
) -> str:
    score_lines = "\n".join(f"- {item['score_dimension']}: {item['score']} / {item['level']}" for item in scores)
    platform_lines = "\n".join(f"- {item['platform']}: {item['fit_score']} / {item['role']}" for item in strategy["platform_fit"][:5])
    country_lines = "\n".join(f"- {item['country']}: {item['fit_score']} / {item['primary_platform']} / {item['market_logic']}" for item in strategy["country_market_fit"][:5])
    factory_block = ""
    if strategy.get("factory_globalization"):
        plan = strategy["factory_globalization"]
        factory_block = f"""

## Factory Globalization Plan

Landed Cost Formula:

```text
{plan['landed_cost_engine']['formula']}
```

Compliance Red Lines:

{chr(10).join(f"- {item}" for item in COMPLIANCE_RED_LINES)}
"""
    return f"""# Seller Mode Strategy Package

Seller: {profile['seller_name']}
Mode: {assessment['seller_mode_label']}
Confidence: {assessment['confidence']}

## Capability Score

{score_lines}

## Recommended Strategy

{chr(10).join(f"- {item}" for item in strategy['recommended_strategy'])}

## Not Recommended

{chr(10).join(f"- {item}" for item in strategy['not_recommended_strategy'])}

## Risk Warnings

{chr(10).join(f"- {item}" for item in strategy['risk_warnings'])}

## First 30 Days

{chr(10).join(f"- {item}" for item in strategy['first_30_day_plan'])}

## First 90 Days

{chr(10).join(f"- {item}" for item in strategy['first_90_day_plan'])}

## Platform Fit

{platform_lines}

## Country Fit

{country_lines}
{factory_block}
"""


def latest_seller_mode_report(root: Path) -> tuple[str, Path | None]:
    output_dir = root / "outputs"
    reports = sorted(output_dir.glob("seller_mode_strategy_*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not reports:
        return "", None
    return reports[0].read_text(encoding="utf-8"), reports[0]


def build_seller_mode_payload(root: Path) -> dict[str, Any]:
    profiles = [record.to_dict() for record in read_records(root, "seller_profile")[-50:]]
    packages = [record.to_dict() for record in read_records(root, "seller_strategy_package")[-50:]]
    report, path = latest_seller_mode_report(root)
    skill_pack_snapshot = seller_mode_skill_pack_snapshot(root)
    return {
        "profiles": profiles,
        "strategy_packages": packages,
        "latest_report": report,
        "report_path": str(path) if path else "",
        "modes": SELLER_MODES,
        "red_lines": COMPLIANCE_RED_LINES,
        "seller_mode_skill_packs": skill_pack_snapshot,
    }


def write_report(root: Path, run_date: str, profile_id: str, content: str) -> Path:
    path = root / "outputs" / f"seller_mode_strategy_{run_date}_{profile_id[-8:]}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_json(root: Path, run_date: str, profile_id: str, payload: dict[str, Any]) -> Path:
    path = root / "outputs" / f"seller_mode_strategy_{run_date}_{profile_id[-8:]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def automation_guidance(mode: str) -> dict[str, Any]:
    return {
        "default_external_customer_max_level": 2,
        "recommended_level": 2 if mode in {"testing_seller", "brand_seller"} else 3,
        "high_risk_actions": ["publish_listing", "change_price", "launch_ad", "refund_order", "ship_order", "authorize_app"],
        "rule": "Generate recommendations and drafts first. Sensitive execution must enter approval queue.",
    }


def fit_flags(mode: str) -> dict[str, bool]:
    return {
        "suitable_for_testing": mode in {"testing_seller", "launch_seller", "factory_seller"},
        "suitable_for_launch_scaling": mode in {"launch_seller", "factory_seller", "brand_seller"},
        "suitable_for_factory_globalization": mode == "factory_seller",
        "suitable_for_brand_matrix": mode in {"factory_seller", "brand_seller", "multi_platform_team"},
    }


def capability_summary(score_map: dict[str, int]) -> list[str]:
    return [
        f"{key}: {value}" for key, value in sorted(score_map.items(), key=lambda item: item[1], reverse=True)
    ]


def score_from(*values: float) -> int:
    return int(max(0, min(100, sum(float(value or 0) for value in values))))


def score_level(value: float) -> str:
    if value >= 80:
        return "strong"
    if value >= 55:
        return "medium"
    if value >= 30:
        return "weak"
    return "missing"


def normalize_product_lines(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        result = []
        for item in value:
            if isinstance(item, dict):
                result.append(dict(item))
            elif str(item).strip():
                result.append({"product_line_name": str(item).strip()})
        return result
    if isinstance(value, str):
        return [{"product_line_name": item.strip()} for item in value.replace("，", ",").split(",") if item.strip()]
    return []


def normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.replace("，", ",").replace("/", ",").split(",") if item.strip()]
    return []


def text(payload: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "有", "是", "可以", "能"}


def number(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except ValueError:
        return 0.0


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def platform_role(platform: str) -> str:
    return {
        "TikTok Shop": "content discovery and horse-race allocation",
        "Amazon": "search demand capture and PPC",
        "SHEIN": "stable supply/order channel",
        "Walmart": "local compliance and stable price channel",
        "Etsy": "design and long-tail personalization",
        "Mercado Libre": "local-market price and logistics",
        "B2B": "sample, quote, contract and bulk order",
        "Shopify": "brand-owned retention and CRM",
    }.get(platform, "channel observation")


def platform_entry_advice(platform: str, mode: str) -> str:
    if platform == "TikTok Shop":
        return "Use content, creators and product-card testing first."
    if platform == "Amazon":
        return "Use after listing/search/review readiness is stronger."
    if platform == "SHEIN":
        return "Best when factory supply and price stability are clear."
    if platform == "B2B":
        return "Use for factories with samples, certificates, MOQ and delivery terms."
    if mode == "testing_seller":
        return "Observe first; do not over-expand before product signal is proven."
    return "Evaluate channel role and data readiness before entry."


def factory_product_channels(item: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    channels = ["TikTok Shop"]
    if profile["has_overseas_warehouse"] or profile["has_brand_assets"]:
        channels.append("Amazon")
    if profile["daily_capacity_units"] > 0:
        channels.append("SHEIN")
    if profile["has_b2b_customers"]:
        channels.append("B2B")
    if profile["has_pod_capability"]:
        channels.append("Etsy")
    return channels
