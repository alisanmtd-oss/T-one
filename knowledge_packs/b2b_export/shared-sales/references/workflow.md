# Sales workflow and state semantics

## Shared customer timeline

Keep one canonical account and append immutable events:

1. `lead_discovered`: public company evidence exists.
2. `enriched`: contact path and source timestamp exist; this is not consent or delivery validity.
3. `qualified_for_review`: ICP and exclusion checks are documented.
4. `outreach_drafted`: message exists locally.
5. `outreach_approved`: a human approved the exact recipient, channel, and message version.
6. `outreach_sent`: execution receipt or manual evidence exists.
7. `reply_received`: customer-authored content and receipt time exist.
8. `discovery_complete`: material need, quantity/capacity, destination, timing, and decision path are evidenced.
9. `sample_or_quote_drafted`: versioned internal draft exists.
10. `sample_or_quote_approved`: human approved the exact commercial terms.
11. `sample_or_quote_sent`: customer-visible send evidence exists.
12. `negotiation`: customer response to terms exists.
13. `order_confirmed`: signed contract, accepted PI/PO, or other approved order evidence exists.
14. `payment_confirmed`: bank/payment-platform evidence is reconciled; a screenshot or customer claim alone is insufficient.
15. `production_or_fulfillment`: authorized order and operational evidence exist.
16. `shipped`: carrier receipt and tracking evidence exist.
17. `delivered`: carrier or customer delivery evidence exists.
18. `aftersales_or_reorder`: feedback, issue, reorder, or referral evidence exists.

Never skip state evidence. Keep `lost`, `disqualified`, `unsubscribed`, `bounced`, and `do_not_contact` as explicit terminal or suppression states with reasons.

## Apparel wholesale


## Equipment cross-sell

Create an equipment review signal only when customer evidence indicates at least one of:

- current DTG/DTF/printing process and capacity constraint;
- outsourcing cost, quality, labor, or lead-time pain;
- repeat order volume that could justify in-house production;
- expansion, second-machine, replacement, dealer, or distributor intent;
- explicit request for machine, print test, ROI, installation, service, or consumables.

Then discover application, substrate, ink/process, print size, color/white-ink needs, throughput by shift, current equipment, facility power/space/ventilation, operator skill, destination, local service expectations, budget, buying authority, decision date, and sample-test acceptance criteria.

Do not recommend a model or promise ROI until verified product specifications, total landed cost, utilization assumptions, maintenance, consumables, yield/waste, training, warranty, installation, taxes/duties, and service coverage are present.

## Learning loop

Promote only repeatable, evidence-backed patterns:

- Stable: stage semantics, evidence fields, approval gates, calculation formulas, failure categories, regression cases.
- Time-sensitive: contacts, company status, prices, stock, capacity, freight, duty, laws, sanctions lists, certifications, delivery times, model availability, platform policies.

Record outcomes and rejection reasons. Never let learning relax an approval gate or convert an inference into a fact.

> Private runtime paths, evidence, execution identities, and product records are intentionally excluded from this public pack.
