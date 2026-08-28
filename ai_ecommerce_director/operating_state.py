from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .project_facts import private_amazon_product, private_amazon_products, private_project_section


AMAZON_10001_OPERATING_STATE_FILE = "amazon_10001_operating_state_latest.json"
AMAZON_10001_CURRENT_GATE_ACTION_ID = "amazon-10001-account-offer-revenue-gate"
AMAZON_10001_REVENUE_REVIEW_ACTION_ID = "amazon-10001-revenue-launch-review"


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "on", "active", "verified", "buyable"}


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _status_display(value: Any, labels: dict[str, str]) -> str:
    clean = _text(value)
    if not clean:
        return "未知"
    return labels.get(clean.lower(), clean)


def load_amazon_10001_operating_state(root: Path) -> dict[str, Any] | None:
    path = root / "outputs" / AMAZON_10001_OPERATING_STATE_FILE
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or _text(payload.get("product_id")) != "10001":
        return None
    route = _mapping(payload.get("route"))
    if _text(route.get("channel_id")).lower() != "amazon" or _text(route.get("country_code")).upper() != "US":
        return None
    return payload


def amazon_10001_listing_work_complete(state: dict[str, Any] | None) -> bool:
    if not state:
        return False
    listing = _mapping(state.get("listing"))
    return bool(
        _flag(listing.get("single_variation_complete"))
        and _integer(listing.get("single_child_count")) >= 88
        and _integer(listing.get("single_color_count")) >= 11
        and _integer(listing.get("single_size_count")) >= 8
    )


def _offer_primary_buyable(offer: dict[str, Any]) -> bool:
    if "has_primary_add_to_cart" in offer or "has_primary_buy_now" in offer:
        return _flag(offer.get("has_primary_add_to_cart")) or _flag(offer.get("has_primary_buy_now"))
    return _flag(offer.get("has_add_to_cart")) or _flag(offer.get("has_buy_now"))


def _offer_buyable_via_options(offer: dict[str, Any]) -> bool:
    return _flag(offer.get("buyable_via_buying_options")) or _flag(offer.get("buying_options_add_to_cart"))


def amazon_10001_spend_gate_open(state: dict[str, Any] | None) -> bool:
    if not state or not amazon_10001_listing_work_complete(state):
        return False
    account = _mapping(state.get("account"))
    fulfillment = _mapping(state.get("fulfillment"))
    offers = _mapping(state.get("offers"))
    us_active = _text(account.get("us_store_status")).lower() in {"active", "in_sale", "selling", "在售"}
    access_open = _text(account.get("selling_services_access")).lower() in {
        "active",
        "open",
        "unrestricted",
        "available",
    }
    bank_verified = _text(account.get("bank_verification")).lower() in {"verified", "complete", "completed"}
    us_warehouse_ready = _flag(fulfillment.get("us_warehouse_location_configured"))
    delivery_ready = _flag(fulfillment.get("competitive_delivery_promise_verified"))
    single = _mapping(offers.get("single"))
    four_pack = _mapping(offers.get("four_pack"))
    return bool(
        us_active
        and access_open
        and bank_verified
        and us_warehouse_ready
        and delivery_ready
        and _offer_primary_buyable(single)
        and _offer_primary_buyable(four_pack)
    )


def build_amazon_10001_authoritative_status(root: Path) -> dict[str, Any] | None:
    state = load_amazon_10001_operating_state(root)
    if not state:
        return None

    listing = _mapping(state.get("listing"))
    account = _mapping(state.get("account"))
    fulfillment = _mapping(state.get("fulfillment"))
    offers = _mapping(state.get("offers"))
    orders = _mapping(state.get("orders"))
    evidence = _mapping(state.get("evidence"))
    single = _mapping(offers.get("single"))
    four_pack = _mapping(offers.get("four_pack"))
    listing_complete = amazon_10001_listing_work_complete(state)
    spend_gate_open = amazon_10001_spend_gate_open(state)
    single_primary_buyable = _offer_primary_buyable(single)
    four_pack_primary_buyable = _offer_primary_buyable(four_pack)
    single_options_buyable = _offer_buyable_via_options(single)
    four_pack_options_buyable = _offer_buyable_via_options(four_pack)
    us_warehouse_ready = _flag(fulfillment.get("us_warehouse_location_configured"))
    delivery_ready = _flag(fulfillment.get("competitive_delivery_promise_verified"))

    blockers: list[str] = []
    gate_ids: list[str] = []
    if _text(account.get("bank_verification")).lower() not in {"verified", "complete", "completed"}:
        blockers.append("银行验证仍未完成；这是账号持有人动作，后台 AI 不代填密码、银行或身份资料。")
        gate_ids.append("amazon_bank_verification_incomplete")
    if _text(account.get("selling_services_access")).lower() not in {"active", "open", "unrestricted", "available"}:
        blockers.append("Amazon 账户概览仍显示销售服务访问受限；Store Status 在售不等于账号已具备完整可售权限。")
        gate_ids.append("amazon_selling_services_access_restricted")
    if _text(account.get("inform_status")).lower() not in {"clear", "verified", "complete", "completed"}:
        blockers.append("INFORM / 账户风险操作项仍需处理，或等待 Amazon 完成复核。")
        gate_ids.append("amazon_inform_or_account_risk_pending")
    if _text(account.get("seller_central_session_status")).lower() == "mfa_required":
        blockers.append("Seller Central 当前等待发送到尾号 358 手机的 MFA 验证码；后台 AI 不绕过或代猜验证码。")
        gate_ids.append("amazon_seller_central_mfa_required")
    if not us_warehouse_ready:
        blockers.append("美国站 FBM 仍未配置获批准的美国仓发货地址；当前唯一发货地点在中国，不能把库存口径当成配送已接通。")
        gate_ids.append("amazon_us_warehouse_location_missing")
    if not delivery_ready:
        blockers.append("代表 SKU 的美国配送承诺仍为数周；在配送时效达到可竞争范围前，禁止开启广告、优惠和外部导流。")
        gate_ids.append("amazon_competitive_delivery_promise_missing")
    if not single_primary_buyable:
        if single_options_buyable:
            blockers.append("单件可在 Buying Options 以 $20 加入购物车，但主购买区仍无 Featured Offer；当前配送承诺约 3–7 周。")
        else:
            blockers.append("单件父体已有 11 色、8 码和 $20 报价，但买家页仍无 Add to Cart / Buy Now。")
        gate_ids.append("amazon_single_featured_offer_missing")
    if not four_pack_primary_buyable:
        if four_pack_options_buyable:
            blockers.append("4 件套可在 Buying Options 以 $50 加入购物车，但主购买区仍无 Featured Offer；当前配送承诺约 5–7 周。")
        else:
            blockers.append("4 件套已有 8 个尺码和 $50 报价，但买家页仍无 Add to Cart / Buy Now。")
        gate_ids.append("amazon_four_pack_featured_offer_missing")

    ready: list[str] = []
    if listing_complete:
        ready.append(
            "单件变体合并已完成：批次 {batch}，父体 {sku} / {asin}，{children} 个子体、{colors} 色、{sizes} 码。".format(
                batch=_text(listing.get("variation_batch_id")) or "已完成",
                sku=_text(listing.get("single_parent_sku")) or "68-DDNH-IM56",
                asin=_text(listing.get("single_parent_asin")) or "B0EXAMPLE1",
                children=_integer(listing.get("single_child_count")),
                colors=_integer(listing.get("single_color_count")),
                sizes=_integer(listing.get("single_size_count")),
            )
        )
    if _flag(listing.get("legacy_duplicates_removed")):
        ready.append("旧重复父体和旧 4PK 子体已隔离；禁止再次上传旧 1/89 文件或创建重复父体。")
    if _text(account.get("us_store_status")).lower() in {"active", "in_sale", "selling", "在售"}:
        ready.append("美国 Store Status 已显示在售；现在只判断账号权限和前台主报价，不再重复铺货。")
    if single_options_buyable and four_pack_options_buyable:
        ready.append("单件和 4 件套均已在 See All Buying Options 内出现 BI ZHENG 的 Add to Cart；这是二级报价可买，不等于已获得 Featured Offer。")
    order_check_prefix = "订单上次确认" if _text(orders.get("current_recheck_status")) == "blocked_by_mfa" else "订单监控已接通"
    ready.append(
        order_check_prefix + "：等待中 {pending}、未发货 {unshipped}、匹配订单 {total}。".format(
            pending=_integer(orders.get("pending")),
            unshipped=_integer(orders.get("unshipped")),
            total=_integer(orders.get("total")),
        )
    )

    if spend_gate_open:
        phase = "美国站已可售，进入出单放量复核"
        headline = "10001 已通过可售闸门，下一步准备优惠、广告和订单履约"
        next_steps = [
            "读取两个 ASIN 的实时价格、库存、Featured Offer 和配送承诺，再生成精确优惠与广告草稿。",
            "负责人确认优惠、预算、出价、否词和止损线后，才允许进入真实提交。",
            "持续监控订单；出现首单后按 SKU、颜色、尺码和仓库库存生成 FBM 发货任务。",
        ]
    else:
        if single_options_buyable and four_pack_options_buyable:
            phase = "二级报价已可下单，MFA、Featured Offer 与配送闸门未解除"
            headline = "10001 不需要再铺货；链接可在购买选项下单，当前只解决主报价和配送"
        else:
            phase = "变体已完成，账号与 Featured Offer 闸门未解除" if listing_complete else "变体/上架修复进行中"
            headline = "10001 不需要再铺货；当前只解决账号可售和主报价"
        next_steps = []
        if _text(account.get("seller_central_session_status")).lower() == "mfa_required":
            next_steps.append("账号持有人提供本次发送到尾号 358 手机的 MFA 验证码，完成当前 Seller Central 登录。")
        next_steps.extend(
            [
                "登录后复核 Bank Verification、INFORM / 销售服务限制和订单。",
                f"限制未解除时继续跟进 Seller Support 工单 {_text(account.get('support_case_id')) or '00000000000'}。",
                "检查美国 FBM shipping template、handling time 和仓库配送承诺；主购买框与配送时效均达标后才打开优惠、广告和外部流量。",
                "订单仍为 0 时保持监控，不创建发货、退款或买标任务。",
            ]
        )

    return {
        "source": "authoritative_operating_state",
        "state_updated_at": _text(state.get("updated_at")),
        "stage": _text(state.get("stage")),
        "route_label": "Amazon 美国站 / 平台卖家店 / 设计师自运营 / FBM",
        "product_label": "10001 230g 复古水洗 100% 棉 T 恤",
        "phase": phase,
        "headline": headline,
        "draft_id": "",
        "evidence_count": _integer(evidence.get("evidence_count")),
        "report_path": _text(evidence.get("report_path")),
        "latest_priority_checker": {},
        "gtin_evidence": {},
        "blockers": blockers,
        "gate_ids": list(dict.fromkeys(gate_ids)),
        "ready": ready,
        "next_steps": next_steps,
        "listing_work_complete": listing_complete,
        "spend_gate_open": spend_gate_open,
        "us_warehouse_location_configured": us_warehouse_ready,
        "competitive_delivery_promise_verified": delivery_ready,
        "single_buyable": single_primary_buyable or single_options_buyable,
        "four_pack_buyable": four_pack_primary_buyable or four_pack_options_buyable,
        "single_primary_buyable": single_primary_buyable,
        "four_pack_primary_buyable": four_pack_primary_buyable,
        "single_buyable_via_options": single_options_buyable,
        "four_pack_buyable_via_options": four_pack_options_buyable,
        "orders_total": _integer(orders.get("total")),
        "support_case_id": _text(account.get("support_case_id")),
        "locked_actions": [
            _text(item)
            for item in _list(_mapping(state.get("gates")).get("locked_actions"))
            if _text(item)
        ],
        "facts": [
            {"label": "单件变体", "value": f"{_integer(listing.get('single_color_count'))} 色 × {_integer(listing.get('single_size_count'))} 码"},
            {
                "label": "美国站",
                "value": _status_display(
                    account.get("us_store_status"),
                    {"active": "在售", "inactive": "未启用", "restricted": "受限", "under_review": "复核中"},
                ),
            },
            {
                "label": "银行验证",
                "value": _status_display(
                    account.get("bank_verification"),
                    {"in_progress": "复核中", "verified": "已完成", "complete": "已完成", "failed": "未通过"},
                ),
            },
            {
                "label": "二级购买选项",
                "value": "单件/四件套可加入购物车" if single_options_buyable and four_pack_options_buyable else "未确认",
            },
            {"label": "前台主报价", "value": "可买" if single_primary_buyable and four_pack_primary_buyable else "未解锁"},
            {"label": "订单", "value": str(_integer(orders.get("total")))},
        ],
    }


def amazon_10001_authoritative_context_lines(root: Path) -> list[str]:
    status = build_amazon_10001_authoritative_status(root)
    if not status:
        return []
    return [
        f"Amazon 10001 当前阶段：{status['phase']}。",
        f"当前结论：{status['headline']}。",
        "已完成：" + " ".join(status["ready"][:3]),
        "当前硬阻塞：" + " ".join(status["blockers"][:4]),
        "下一步：" + " ".join(status["next_steps"][:3]),
        f"Spend gate={'OPEN' if status['spend_gate_open'] else 'CLOSED'}；未打开时禁止优惠、广告、外部流量和发货。",
    ]


def amazon_10001_action_is_obsolete(action: dict[str, Any], state: dict[str, Any] | None) -> bool:
    if not amazon_10001_listing_work_complete(state):
        return False
    action_id = _text(action.get("action_id"))
    action_type = _text(action.get("action_type"))
    source_package = _text(action.get("source_package"))
    if action_id in {AMAZON_10001_CURRENT_GATE_ACTION_ID, AMAZON_10001_REVENUE_REVIEW_ACTION_ID}:
        return False
    obsolete_id_prefixes = (
        "amazon-10001-submit-ready",
        "amazon-10001-product-details-submit-ready",
        "amazon-10001-ready-draft",
        "amazon-10001-current-listing-preflight",
        "amazon-10001-gtin-evidence-review",
        "amazon-10001-seller-central-template-download",
        "amazon-us-store-operations",
        "amazon-us-ads-page-capture",
        "amazon-10001-account-verification-buyability-gate",
        "amazon-10001-fbm-offer-price-inventory-confirmation",
        "amazon-10001-full-chain",
        "amazon-10001-owner-review",
        "amazon-10001-final-gate",
    )
    obsolete_types = {
        "submit_amazon_listing_draft",
        "amazon_listing_preflight",
        "amazon_product_identity_preflight",
        "amazon_seller_central_template_download",
        "amazon_store_operations_capture",
        "amazon_ads_page_capture",
        "amazon_store_operations_repair_plan",
        "amazon_account_verification_buyability_gate",
        "amazon_fbm_offer_price_inventory_confirmation",
        "listing_draft",
        "ads_test_plan_draft",
        "pricing_promotion_draft",
        "amazon_settlement_module_draft",
    }
    return bool(
        action_id.startswith(obsolete_id_prefixes)
        or action_type in obsolete_types
        or source_package.startswith(("amazon_10001_owner_review", "amazon_10001_final_gate_blocker"))
    )
