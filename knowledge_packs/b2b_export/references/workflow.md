# B2B Export workflow

## Canonical account model

Use one account record and one chronological timeline. Opportunities may be `apparel_supply` or `equipment_cross_sell`, but both point to the same `account_id`. A status transition must carry `event_id`, `event_time`, `actor`, `source`, `evidence_ref`, and `previous_status`.

## Stage gates

| Stage | Minimum entry evidence | Primary artifact | Exit evidence |
|---|---|---|---|
| Lead | Public company identity, URL/source, target country, ICP hypothesis | Research card | Deduped account and allowed contact path |
| Qualified | Business fit, use case, geography, reachability, disqualifiers | Qualification scorecard | Human-reviewed fit and next contact hypothesis |
| Discovery | Customer-stated need or approved discovery plan | Discovery notes/questions | Quantity/use/decision/timing constraints captured |
| Sample or quote | Product/spec, quantity, currency, destination and commercial unknowns listed | Sample plan or quotation draft | Customer acceptance/revision request evidenced |
| Negotiation | Objections and requested changes are recorded | Concession ledger | Approved price/term position and open items |
| PI/contract | Legal entities, goods, quantity, price, currency, Incoterms named place, payment and delivery inputs | PI/contract draft | Authorized signatures or formal acceptance evidence |
| Delivery | Approved order, collection condition, packing/label/document requirements | Delivery checklist | Carrier/warehouse evidence and shipment status |
| Collection | Invoice/payment terms and due dates | Receivables plan | Bank/payment-provider confirmation, not a promise |
| Repeat | Delivered/accepted order plus follow-up signal | Reorder and account-growth plan | New accepted order or verified referral |

Never infer a later stage from an earlier artifact. A quotation draft is not a sent quotation; a customer promise is not payment; a booking draft is not shipment; a tracking number is not delivery.

## Qualification and discovery

Record: company role, business model, locations, current blank/apparel or print workflow, purchasing frequency, approximate volume range, decision role, target delivery country, urgency, constraints, compliance flags, and evidence confidence. Public personal data is not automatically lawful for outreach; route by the recipient country and subscriber type.

## Sample and quotation

Do not fabricate SKU, specifications, stock, production capacity, lead time, unit cost, price, freight, duty, tax, warranty, certification, or bank details. A quotation draft should list missing fields and separate product price, tooling/setup, sample fee, freight, taxes/duties, validity, and assumptions. Incoterms require the three-letter rule, the exact named place/port, and the `Incoterms® 2020` version; they do not decide title transfer or payment terms.

## Negotiation

Use a concession ledger: customer request, evidence, cost/risk effect, offered concession, required exchange, approval owner, expiry, and result. Never trade away an unknown margin, compliance requirement, service obligation, or payment safeguard.

## PI, contract, delivery, and collection

Before formal commitment, verify legal entity names, addresses, product description, quantity, currency, price, Incoterms named place, delivery window, payment method, inspection/acceptance, warranty/service, governing law/dispute venue as applicable, sanctions/export-control result, and document list. Country-specific customs and tax requirements remain unknown until origin, destination, HS classification, product, and importer-of-record are verified.

Payment status is externally confirmed only from an authorized bank or payment-provider record. Shipment status is externally confirmed only from an authorized carrier, warehouse, ERP, or responsible-person document. Apply segregation of duties to bank-detail changes and callback verification using a known channel.

## Evidence-based equipment branch

The following may open discovery but cannot qualify a machine opportunity alone: website mentions of printing, equipment, DTG, DTF, capacity, custom apparel, or fast turnaround. Require a dated customer statement or responsible-person validation plus operational details.

Equipment discovery fields:

- application and substrate;
- print process and ink;
- print area, color/white requirements, and quality target;
- actual and peak daily volume, shifts, utilization, rejects/rework;
- bottleneck, labor, lead-time, or outsourcing cost evidence;
- utilities, ventilation, floor space, environmental limits, and operator skills;
- destination, installation, training, consumables, spares, service SLA, warranty, certifications;
- budget, financing, decision team, approval path, and timeline.

ROI is a scenario, not a fact. Show every input, source, range, sensitivity, excluded cost, and confidence. If the data is incomplete, output an information request rather than a recommendation.
