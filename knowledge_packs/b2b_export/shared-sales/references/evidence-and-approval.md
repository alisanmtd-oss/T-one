# Evidence and approval policy

## Minimum evidence record

For each material claim, store:

- `claim`
- `truth_label`
- `source_type`
- `source_uri_or_local_path`
- `observed_at`
- `subject_scope` (tenant, project, account, opportunity, task)
- `owner`
- `confidence` only for inference
- `expires_at_or_recheck_trigger`

Keep credentials as `credential_ref`; never place secrets in task payloads, prompts, CSVs, screenshots, or skill files.

## Approval gates

- `outreach_gate`: exact recipient, lawful/allowed channel basis, suppression check, message version, sender identity, opt-out handling.
- `price_and_sample_gate`: product/specification, quantity, destination, currency, cost, freight, margin, validity, sample charges, approval owner.
- `legal_and_money_gate`: entity, contract version, governing terms, bank/payment route, fraud check, sanctions/export-control review where applicable.
- `production_gate`: approved order, BOM/specification, capacity, due date, QC and exception owner.
- `shipping_and_document_gate`: Incoterm plus named place, mode, packaging, documents, broker/carrier, duties/taxes responsibility, consignee, shipment approval.
- `refund_or_credit_gate`: amount, reason, evidence, accounting owner, and recovery path.

## Always block

- Bulk unsolicited outreach or evasion of platform/message limits.
- Private-contact scraping, credential sharing, CAPTCHA/MFA bypass, or hidden browser identity mixing.
- Invented company, person, consent, reply, quote, order, payment, shipment, certification, warranty, service, or ROI facts.
- Changing prices, sending formal documents, requesting payment, booking freight, or committing delivery without the matching approval record.

## Failure recording

Record attempted action, inputs, exact failure, external side effect (if any), retry eligibility, next owner action, and evidence path. Retrying must not change recipient, price, scope, or permissions.
