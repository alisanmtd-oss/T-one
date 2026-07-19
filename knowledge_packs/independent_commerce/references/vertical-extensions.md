# Vertical extensions

Select exactly one primary vertical for each sellable item or booking. Mixed stores may use multiple extensions, but every order line must retain its own delivery and tax semantics.

## Shared fields

Require product/service identity, truthful description and media rights, price, cost basis, currency, selling market, tax category, payment path, refund/cancellation policy, customer-support owner, delivery evidence, and connector state.

## DTC physical goods

Require:

- variant/SKU, weight and dimensions, inventory location, available quantity and reservation rule;
- ship-from, carrier/service, handling time, delivery promise, duties/incoterm treatment, return address and restocking rule;
- product compliance, origin/HS code when relevant, packaging and damage/loss process;
- landed contribution margin after product, pick/pack, freight, duties/tax handling, payment fees, discounts, returns and acquisition cost.

Never infer stock, ship-from, delivery date, duties, or return eligibility from a product page alone.

## POD

Inherit DTC physical requirements and add:

- design/IP ownership and commercial-use evidence;
- blank/product variant mapping to the production partner;
- print method, printable area, color/size mapping, mockup truthfulness and personalization validation;
- production SLA, routing location, reprint/refund responsibility, tracking callback and supplier outage fallback;
- production cost and shipping quote freshness by destination.

Treat a POD provider name as `available_unconnected` until its store-specific API/app authorization and webhook/read probe pass. Do not promise inventory or production capacity without supplier evidence.

## Dropshipping

Inherit DTC physical requirements and add:

- supplier identity, authorization, live stock/price freshness, order-routing boundary and idempotency;
- actual ship-from, delivery range, split shipment, branded packing constraints, customs/duties and return destination;
- substitution/backorder policy, supplier cancellation, tracking quality and chargeback ownership;
- margin sensitivity to supplier price, FX, long delivery, refunds and reshipments.

Do not advertise a domestic ship-from, guaranteed delivery, branded packaging, return address, or stock level without current supplier evidence.

## Digital products

Require:

- delivery artifact/app, entitlement identity, download/access limits, version/update policy and support duration;
- license and content rights, refund conditions, fraud/chargeback handling and delivery evidence;
- customer location, tax category and market-specific digital VAT/sales-tax review;
- personal-data classification and retention/deletion behavior.

Do not apply physical inventory, shipping, or return-location logic. A successful payment is not proof of successful entitlement delivery.

## Service booking

Require:

- service location or remote-delivery method, provider identity, capacity/calendar source and timezone;
- lead time, reschedule/cancellation/no-show/refund policy, service completion evidence and dispute owner;
- taxes, payment capture timing, deposits, tips/gratuities and provider payout rules by market;
- customer communication and accessibility/language needs.

Do not convert product quantity into service capacity without a verified booking/calendar connector.

## OTA or experience booking

Inherit service-booking requirements and add:

- supplier/operator contract and inventory source, date/time slot, participant rules, blackout dates and timezone;
- booking confirmation/voucher, amendment/cancellation deadline, no-show, weather/force-majeure and supplier failure process;
- destination taxes/fees, currency, settlement timing, commissions, payout and refund ownership;
- traveler data minimization, emergency/support contact, local regulatory and insurance evidence where applicable.

Use the shared Independent Commerce core only for catalog, checkout, conversion, customer and finance structure. Keep inventory, ticketing/voucher, cancellation, local tax, safety and supplier settlement provider-specific. If no official booking/provider connector is registered, remain `research_only` and do not accept or confirm live bookings.
