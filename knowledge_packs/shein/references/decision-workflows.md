# SHEIN decision workflows

## Preflight record

Create one record per task:

```json
{
  "tenant_id": "required",
  "project_id": "required",
  "store_binding_id": "required_for_authenticated_work",
  "platform": "shein",
  "country_site": "authorized_value_or_unknown",
  "commerce_mode": "platform_self_operated|semi_managed|recognition_only|unknown",
  "ownership": "required",
  "execution_identity_id": "required_for_authenticated_work",
  "developer_account_id": "required_for_open_platform_work",
  "application_id": "required_for_open_platform_work",
  "application_type": "exactly_one_official_business_type_per_application",
  "credential_ref": "reference_only",
  "capability": "listing|activity|ads|orders|inventory|fulfillment|customer_service|finance|competitor|learning",
  "capability_state": "research_only|available_unconnected|connected_read_only|connected_write_gated|blocked",
  "evidence": [],
  "unknowns": [],
  "approval_items": []
}
```

Reject or downgrade the record when a required dimension is absent, the store identity differs from the credential scope, the authorized mode/site is not confirmed, or the evidence is stale.

For Open Platform work, never collapse developer account, application, store authorization and execution identity into one identifier. A separate application is required for each official application type. POP, full-managed and SHEIN self-run observations do not authorize T One execution.

## Developer sandbox and authorization decision

1. Prefer the official fixed test application/store environment for connector validation before any production store call.
2. Require an owner-approved developer account identity and the exact application type. Account type and application type are durable choices; do not guess them.
3. Treat test merchant authorization, test API calls and product-publish debugging as `available_unconnected` until a developer login proves access.
4. Store only `credential_ref`/key references. The store main account performs authorization; never request or retain raw OTP, password, temporary token, open key or secret in a task record.
5. Exchange the short-lived authorization result only inside a secret-aware connector. Enforce the documented timestamp/signature requirements in runtime code.
6. Record test application/store, application type, endpoint, request schema, redacted response, error and trace. A test tool page alone is not a passed connector test.
7. Run read-only test calls first. Any test publish or production write remains owner-gated and must use a clearly non-production sandbox object.

Failure fallback: on login redirect, expired temporary authorization, signature/timestamp error, application-type mismatch or store-scope mismatch, record the exact stage and stop. Never reuse another application/store key or retry across modes.

## Listing decision

1. Read store status, mode, enabled sites/currencies and publish quota.
2. Read available category, attributes, brands, IP and category-specific publish-field standard.
3. Validate product facts, product safety, restricted-product and IP evidence.
4. Build SPU/SKC/SKU/media payload as a draft.
5. Run completeness and policy validation.
6. Return `draft_ready`, `needs_store_fact`, `needs_category_authorization`, `needs_owner_approval` or `blocked`.
7. Publish/edit only through a proven store-scoped write connector after owner confirmation and with an idempotency key.

Failure fallback: preserve the draft, exact API/Seller Hub error, trace ID when safe, rejected fields, source snapshot and next smallest corrective action. Never retry blindly across stores or sites.

## Activity and ads decision

1. Read the authenticated Seller Hub eligibility, site, SKU scope, campaign window, price requirement, inventory commitment and stacking display.
2. Separate platform campaigns, seller promotions, flash sales and coupons.
3. Calculate margin using known mode-specific fields; mark missing commission, fulfillment, tax or refund costs unknown.
4. For “ads,” first prove the store-specific surface, billing identity, permissions, spend unit and reporting source.
5. Without that proof, output a research note or promotion draft, never a paid campaign package.
6. Require approval for enrollment, campaign price, coupon activation, inventory commitment or any spend.

## Order, fulfillment and returns decision

1. Treat an order/return Webhook as a trigger containing scoped identifiers and change time, not complete order/return truth or approval.
2. Validate application/store scope and signature, deduplicate, durably hand off and return 2xx within the documented 1.5-second threshold; then process asynchronously. Preserve the public body/content-type inconsistency until a redacted official test event resolves it.
3. For return recovery or polling, call the authorized `/open-api/return-order/list` with one declared time dimension, an overlap around the store-scoped high-water mark, 30-row pagination and deduplication by return number plus update time.
4. Read `/open-api/return-order/details` in batches of at most 30. Bind mode/site/currency and compare return/per-goods status, no-return-goods marker, platform/member waybills, receive type, seller-sign/update times, `goodsId`, return media/reasons and mode-specific cost fields.
5. Apply the current endpoint developer ceilings together with the solution's store-level ceiling; use the tightest known applicable limit and retain each scope instead of flattening them into one universal QPS.
6. Treat carrier delivery, platform warehouse transition, seller receipt and completion as separate states. A community report about delivered-but-not-received is a case hypothesis, not a policy or automatic refund/rejection signal.
7. Distinguish seller-fulfilled, SHEIN-integrated logistics and authorized SFS, then validate stock and label/tracking requirements against current store policy.
8. Prepare shipment, return sign, refund or response as a gated item. Confirm externally only after owner approval and write the result to the same `store_binding_id` and order/return case.

Failure fallback: deduplicate repeated events and use the overlapped list plus scoped detail query. Do not rely on platform retries as a complete queue: current public guidance says non-order events retry once and order events twice, with the first retry around 30–60 minutes. If carrier and warehouse receipt disagree, preserve both, request only the missing scoped evidence and send the case to human review. Record signature, callback, durable-queue, list, detail, evidence and decision stages separately; never turn an event/list/carrier result into shipment, sign or refund execution.

## Knowledge-package and third-party fulfillment decision

1. Search the current T One Skill, rules, evaluations, failure ledger, connector state and GitHub admission registry before opening a candidate. Use English SHEIN-specific combinations first, then bounded generic combinations such as `SHEIN marketplace integration`, `SHEIN API SDK`, `multichannel ecommerce ERP`, `order inventory fulfillment automation`, `playbook`, `SOP`, `schema`, `evaluation`, `SDK`, `ERP`, `OMS`, `PIM` and `WMS`.
2. Record candidate owner, source, version/commit/release, license, maintenance, issues/security, credential/telemetry/logging risks, dependencies, deployment cost, test evidence, overlap and exact site/mode/ownership scope. The result must be one of `keep_reuse`, `merge_into_existing`, `extract_rules_only`, `research_only`, `rejected_stale`, `rejected_license` or `rejected_unsafe`.
3. Compare two or three candidates when available. Sample one core workflow, one failure boundary and at least three rules, then use only the directly relevant current official deep page to validate platform facts. Unknown-license, unverified-owner, stale or unsafe code is never installed, copied or given credentials.
4. For every ERP/OMS/WMS/MCF path, assign exactly one execution owner for each order, SKU and warehouse. Do not let two integrations acknowledge, fulfill, write tracking or update the same inventory scope.
5. Preserve SHEIN `goodsId` as the per-unit line identity even when seller SKUs repeat. Surface an unmapped item as `unknown_product`; do not merge units, invent a mapping or inherit product facts from another tenant.
6. When a dedicated fulfillment warehouse is configured, persist both `warehouseId` and `warehouseName`, exclude that warehouse from other ERP/OMS tracking writers and verify that only available inventory is offered. A guide or form proves neither app authorization nor a live connection.

Failure fallback: on duplicate-executor risk, unknown SKU mapping, missing warehouse identity, package-version drift, unsafe request/response logging or absent owner authorization, stop before connection or external write. Preserve the candidate fingerprint and redacted error, keep the connector `blocked`, and return the single missing owner input or safe registry-review action.

## Inventory mutation decision

1. Read the authorized current inventory and protected preoccupied/occupied quantities for the matching store, SHEIN SKU, site, warehouse and inventory type.
2. Use `/open-api/stock/change-inventory/v2`; keep old v1 in a superseded migration chain and recheck its documented 2026-12-31 retirement before cutover.
3. Permit only documented `VI` or `JI` change proposals. SHEIN physical warehouse inventory stays platform-workflow controlled.
4. Bind a stable item idempotency key to store, SKU, inventory type, change type and intended quantity. SUB cannot exceed current saleable inventory; OVERWRITE cannot reduce below preoccupied/occupied inventory.
5. Keep the proposal `connected_write_gated` and require owner confirmation. After a redacted authorized call, inspect every `failedList` item even when top-level code is zero; never blindly replay the full batch.

Failure fallback: on partial failure, uncertain timeout, original-inventory-changed error, scope mismatch or permission error, query current authorized state and the prior idempotency result before proposing a targeted retry. Do not create new idempotency keys for the same intended mutation merely to bypass duplicate protection.

## Finance decision

1. Reconcile order facts with check-order and remittance records.
2. Keep seller sales price, semi-managed cost price, promotion/coupon amounts, commission, fulfillment fees, tax, refund, currency and site as separate fields.
3. Do not apply a self-operated formula to semi-managed orders or vice versa.
4. Flag missing statements, mismatched currency/site, unresolved refunds and unverified tax treatment.
5. Never change bank, tax, payment or settlement settings without owner confirmation.

## Learning write-back

Write public official rules, tenant facts, project decisions, store facts and task results to separate scopes. Every rule stores source URL, checked date, applicable site/mode, confidence, expiry/review trigger and superseded rule ID. Seller experience remains an experiment hypothesis until store results or official evidence validate it.
