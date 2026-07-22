---
name: b2b-outbound-customer-development
description: Operate T One's independent outbound foreign-trade specialist for lawful public buyer research, account deduplication, decision-role and purchase-signal hypotheses, qualification, one-to-one email/LinkedIn/WhatsApp/social/form drafts, follow-up planning, and handoff to the shared quotation and export workflow. Use when work begins from independent prospecting rather than a B2B marketplace inquiry or seller account.
---

# B2B Outbound Customer Development

## Load the shared foundation

1. Read the authority files required by `AGENTS.md`.
2. Read `skills/b2b-foreign-trade-sales/SKILL.md`; it remains the canonical account timeline, qualification, commercial, delivery, collection, and approval source.
3. Read [source-and-boundaries.md](references/source-and-boundaries.md) before using the user training document, country generalizations, send thresholds, scoring cutoffs, or fixed sequences.
4. Reuse `ai_ecommerce_director/b2b_lead_playbook.py`, `ai_ecommerce_director/b2b_sales_runtime.py`, `ai_ecommerce_director/b2b_outbound_evidence.py`, and the single-use approval ledger in `ai_ecommerce_director/b2b_document_approval.py`. Do not create another customer pool, CRM, sequencer, email sender, or chat connector.

## Resolve one outbound task

Require `tenant_id`, `project_id`, `task_id`, `product_id`, `country_site`, `channel_mode`, `ownership`, `execution_identity_id`, `account_id`, and `owner_id` before a state write. Resolve `channel_mode` as one of: lawful customs/trade data, public business directory, map/business listing, company website, public social/company page, LinkedIn research, trade show/event, referral/representative, public email path, WhatsApp opt-in, or another explicitly approved source.

A URL, company name, public profile, phone, email pattern, data-vendor record, customs event, post, comment, job title, or AI summary is a candidate signal. It is not consent, a verified recipient, a decision maker, purchase intent, qualification, an order, or permission to contact.

## Run the outbound workflow

1. Inventory the existing customer pool, source fingerprints, account timeline, suppression list, connector state, evidence, Skill, evaluations, and GitHub admission registry. Reuse and deduplicate before searching.
2. Define the tenant product, evidence-backed ICP, target country, allowed source types, exclusion criteria, privacy basis, and research budget. Unknown facts remain `unknown`.
3. Collect only lawful, relevant public company evidence within source terms. Preserve source URL, owner, date, exact observed text or field, access boundary, and confidence. Separate company facts, contact path, purchase signal, inference, and unknown.
4. Resolve a canonical company key and merge platform, website, map, trade, social, event, and prior CRM traces into one account. Never create another customer because the offer or channel changes.
5. Map possible roles and decision chain as hypotheses. Validate product fit, destination, demand/quantity signal, timing, supply-chain problem, current relationship, sanctions/export-control escalation, fraud signal, and reason to stop. Do not score or reject from one keyword or stereotype.
6. Draft one channel-appropriate first touch using a cited, recent customer signal and truthful tenant value proposition. Do not invent familiarity, a pain point, price, stock, capacity, certification, customer name, case study, local presence, or compliance result.
7. Check recipient evidence, consent/legitimate-interest policy, suppression/opt-out, local time and channel rules, domain authentication/deliverability state, message risk, attachments/links, and owner approval. Thresholds from a course are hypotheses unless the current connector policy proves them.
8. Stop before email send, LinkedIn connection/message, WhatsApp send, form submit, call, CRM external write, sequence activation, paid data purchase, or calendar booking. Mark external contact only from the correctly scoped send/delivery receipt.
9. On a real reply, create a separate event and hand the account to the shared discovery, quotation, sample, negotiation, contract, delivery, collection, and repeat workflow.

## Bind evidence and the exact draft

- Every supported claim must point to one or more `source_evidence_refs`; a public address or profile remains a candidate contact path, not consent or buyer intent.
- Before owner review, create one immutable outbound packet containing the exact sender binding, recipient, channel, subject, body, attachment manifest and their SHA256 values. Any recipient/body/attachment change invalidates the approval.
- Attachments start as `quarantined_untrusted`. Only a clean malware scan plus content review and scan evidence may release them for owner review; release still does not permit sending.
- Screening results are evidence cases, never automated legal conclusions. A potential match requires an authorized reviewer; “no candidate match” is not legal clearance.
- `outbound_message_send` approval expires, can be revoked, and is consumed once. Consuming the local gate does not itself send a message; a separately authorized connector and scoped execution receipt are still required.

## Prefer mature knowledge packages

Before broad web collection, search existing T One assets and the approved GitHub registry for maintained lead-research playbooks, enrichment schemas, public-source checklists, CRM/sequence connectors, deliverability diagnostics, evaluation sets, and failure traces. Audit owner, license, version, maintenance, core files, tests, issues/security, credentials, telemetry, external writes, dependencies, cost, overlap, and data-source terms.

Classify only as `keep_reuse`, `merge_into_existing`, `extract_rules_only`, `research_only`, `rejected_stale`, `rejected_license`, or `rejected_unsafe`. Unknown license or data provenance blocks copy, install, and commercial integration. Use current official documentation only to verify channel terms, permissions, API scopes, deliverability, privacy, and availability differences.

## Share cross-cutting capabilities

Reuse shared legal/IP, privacy, communication, CRM, product truth, pricing/profit, compliance, fraud, video, documents, payment, security, and approval modules. Do not duplicate them inside this specialist. Coordinate with the B2B platform specialist through the same canonical `account_id`, owner, suppression state, last-contact event, opportunity, and next action.

## Hard stops

- Do not scrape private contacts, comments, followers or logged-in data; bypass CAPTCHA/rate limits; buy or export lead PII without approval; infer email addresses and call them verified; or evade platform account controls.
- Do not bulk-message, auto-connect, auto-follow, auto-submit forms, activate sequences, rotate accounts/domains/IPs to evade limits, or simulate normal-user behavior.
- Do not treat SPF/DKIM/DMARC, a validation result, a public address, an opt-in elsewhere, an approved draft, API acceptance, `sent`, or a screenshot as consent, delivery, reply, qualification, or deal proof.
- Do not hardcode universal send volumes, warm-up periods, bounce cutoffs, country schedules, contact counts, personality stereotypes, or response sequences from the user course.
