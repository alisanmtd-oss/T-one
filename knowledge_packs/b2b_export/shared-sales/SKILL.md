---
name: b2b-foreign-trade-sales
---

# B2B Foreign Trade Sales

## Start from authority

1. Read `tk智能体_当前权威记忆.md`, `tk智能体_当前任务队列.md`, and `config/current_task_queue.json`.
2. No private customer pool or operating file is included in this public pack.
3. Read the public files in `references/` before changing code, data, or the software workstreams. Private project-asset inventories are intentionally excluded from the public release.
4. Never load the 14GB raw conversation. Search the compact recovery files only when tracing a specific historical requirement.

## Choose the sales scope

- Use `generic_b2b` for any other lawful tenant product. Load tenant/project/product facts and the applicable country, channel and category schema; if facts are absent, keep them `unknown`. Never inherit private_tenant prices, variants, inventory, warehouse, customers, images or equipment assumptions.
- Use `equipment_cross_sell` only when the same customer record contains explicit capacity, DTG/DTF, outsourcing, labor, quality, lead-time, expansion, or dealer evidence. A keyword is a review signal, not a qualified machine opportunity.
- Do not create a second customer merely because the offer changes from T-shirts to equipment. Append events and opportunity records to the same canonical account timeline.

## Run the workflow

1. Establish the customer and source evidence; separate company facts, public contact paths, inferences, and unknowns.
2. Qualify ICP fit, business need, authority, quantity/capacity, destination, timing, and exclusion risks.
3. Draft the next message for the selected channel and language. Cite the customer signal used for personalization.
4. Put every real email, WhatsApp, social DM, form submission, call, quotation, sample order, contract, payment request, shipment promise, or CRM write into the matching approval gate.
5. Build sample or quotation drafts only after the required fields in [trade-and-quotation.md](references/trade-and-quotation.md) are evidenced.
6. Record send, reply, rejection, bounce, quote version, approval, order, payment, production, QC, shipment, delivery, complaint, and reorder as separate events. Never promote a stage from a draft or plan alone.
7. Review the outcome and update only reusable rules that have evidence. Keep dated market, contact, legal, logistics, price, and platform facts as time-sensitive evidence.

Before distilling a public source, record page coverage: title/owner/date/version/site/mode, relevant sections, expanded modules and direct links, list pagination/latest sort, public comments or replies when present, footer status, unavailable regions and confidence. Structured text coverage is not visible manual scrolling. Stop at login, CAPTCHA, paywall, 403, rate limit or access control; never describe an unobserved area as reviewed.

Treat social and forum comments as a separate evidence track. When a platform permits it, inspect pinned, top/high-signal, latest, author/official replies, nested replies, disputes and counterexamples; use at least two provided sorts and record the actual sample/thread count. Cluster only anonymous themes with language, observed sample frequency and minority counterexamples. Filter duplicate text, bots, affiliate/lead-generation spam, covert ads, review manipulation, suspected AI comments and off-topic content. Votes and frequency never prove a rule. Any policy, fee, API or feature-change claim must be checked against a current official source. If comments cannot be reached, sorted or counted, mark them `unknown`/`blocked` and derive no comment knowledge. Never retain usernames, avatars, contact details, private messages or identifiable profiles, and never contact commenters.

Read [workflow.md](references/workflow.md) for stage semantics and the T-shirt-to-equipment handoff. Read [evidence-and-approval.md](references/evidence-and-approval.md) before any action that can affect a person, customer, price, money, goods, contract, or external system.

## Enforce truth labels

Use one of these labels on material claims: `verified_current`, `verified_stale`, `customer_stated`, `internal_assumption`, `inferred`, `unknown`, `draft`, `approved_not_executed`, or `externally_confirmed`.

For training evidence, keep a separate evidence axis and use exactly one of `verified_live_fact`, `time_sensitive_evidence`, `historical_operator_trace`, `draft`, `failed_attempt`, `unknown`, or `blocked_owner_input`. The business-truth label above describes what a claim means; the training-evidence label describes how it was learned. Never silently convert one axis into the other.

- `draft` is never sent.
- `approved_not_executed` is never sent, paid, ordered, produced, or shipped.
- A public contact page is not a verified recipient.
- A quoted price is not an accepted order.
- A payment request is not a payment.
- A tracking number is not delivery.
- An equipment review signal is not a validated application, technical fit, certification, warranty, installation plan, or purchase intent.

## Keep platform assistance behind receipts

- Platform AI output, reply generation, translation, content enhancement, RFQ matching, inserted text, saved drafts, buttons, and approvals are intermediate states. Only the correctly scoped platform send or submission receipt can mark a message, quotation, order, contract change, or payment link as external.
- Platform buyer ranks, activity, company fields, spam counts, industry interests, and matching results are dated prioritization signals. They never automatically qualify, reject, blacklist, or create a customer/order.
- A buyer message, screenshot, payment link, bank claim, order email, or payment request is not collected payment. Confirm collection only from the correctly bound platform, bank, or finance receipt authorized for that task.
- Shipping fields, a tracking document, an upload, a platform status, or a tracking number do not prove carrier acceptance or delivery. Keep approval, platform submission, carrier receipt, delivery, and customer acceptance as separate events.
- `Frozen funds`, `Funds to withdraw`, a Payoneer transfer, and a bank receipt are different states. Never enter an authentication code, initiate a withdrawal, change bank details, or mark bank settlement for the owner.
- For complaints, refunds, chargebacks, and after-sales disputes, preserve the current platform notice and deadline, gather truthful complete lawful evidence, and prepare an owner/legal-reviewed draft only. Never decide liability, fabricate evidence, submit the response, or execute a refund autonomously.
- Country-site manuals and notices stay scoped to their seller country, site, store mode, ownership, and validity period. Preserve superseded versions and their replacement edge; never generalize a Japan-site cancellation, fee, order cap, or payment condition globally.

## Gate WhatsApp business messaging

- A public or CRM phone number is not consent. Before any WhatsApp business contact, preserve both the recipient-provided mobile number and an applicable opt-in; honor every block, stop, or opt-out request and keep `external_message_sent=false` until a scoped send receipt exists.
- Check the current official customer-service window against the timestamp of the last user message. Business-initiated conversations and messages outside the documented 24-hour window require an approved template; generated text, a test button, a template, or an API success response is not a delivery receipt.
- Any automated or native-AI conversation must offer a prompt, clear, direct human escalation path. Hand contractual, payment, compliance, complaint, sensitive-data, and opt-out issues to the responsible owner.
- Meta Business Agent and WhatsApp Business Platform remain `blocked_connector` until the tenant's country/eligibility, business account, phone number, role, permissions, content rights, webhook/error path, and scoped authorization are verified. A public feature page does not prove entitlement or activation.
- Require an explicit subscription receipt for the correctly scoped WABA before relying on live webhook events. A test callback proves only the test path; it does not prove the production subscription or any live message status.
- Keep API acceptance, `sent`, `delivered`, `read`, `failed`, `deleted`, reply, and opt-out as separate events. `sent` means the WhatsApp server received the message, not that the recipient did. Correlate status by message ID and event timestamp because notification arrival order may differ from event time.
- Preserve the official error payload for `failed`; do not infer a root cause from a 2xx response, missing callback, test button, or community report. Do not build a new On-Premises connector when the current official workspace marks it deprecated; extend the existing Cloud API connector path only after scoped authorization.
- Never scrape private numbers, reuse consent across tenants, share one customer's chat with another, or request full payment-card, bank-account, or identity numbers in WhatsApp.
- Public community cases may supply counterexamples. Only three independent sources can support a bounded experiment, and they still cannot override official rules or prove guaranteed platform protection.

## Gate LinkedIn research and Sales Navigator AI

- Treat a public LinkedIn profile or post as a scoped research signal, not consent, a verified recipient, qualification or permission to copy. LinkedIn's current public terms prohibit scraping, access-limit bypass and unauthorized bots that add/download contacts or send messages; do not automate these through extensions or unpublished endpoints.
- A live LinkedIn connector requires the correctly bound tenant/project/account/execution identity, developer application, OAuth receipts and approved product scopes. Sales Navigator API integration additionally requires LinkedIn SNAP partner approval. Without these receipts, keep it `blocked_connector`.
- Lead IQ's documented entry is a Sales Navigator lead page's Lead IQ tab (`Generate Lead IQ`) or Lead Panel. Its public-profile/activity/network/Account IQ summary and talking points are hypotheses only. Review sources and facts before any outreach; the output is not a send, reply or deal receipt.
- If entitlement, admin settings, English interface, a minimum of three public insights, profile language or desktop availability blocks Lead IQ, record `unknown`/`blocked` and use lawful manual research. Never fall back to scraping.
- Sales Navigator AI inputs/outputs may be associated with an enterprise seat, retained and in some cases manually reviewed. Do not enter another tenant's product, customer, CRM or confidential data. Admin AI switches apply account-wide and require owner approval; disabling one feature may not remove its derived insights from another enabled feature.
- Do not install or copy `linkedin-developers/linkedin-api-python-client`. Its current package metadata declares a proprietary license, the repository is beta and the observed mainline is stale with open defect reports. Use only the official OAuth/Rest.li concepts after a separately approved connector and license review.

## Preserve hard boundaries

- Do not bulk-message, scrape private contacts, bypass access controls, or infer consent.
- Do not state a price, margin, MOQ, inventory, capacity, lead time, freight, duty, tax, Incoterm, certification, warranty, installation, training, spare-parts commitment, bank detail, payment status, or shipping status without a named evidence source and timestamp.
- Do not make a sanctions, export-control, customs, tax, privacy, or contract determination from model memory. Use the current official source checklist in [trade-and-quotation.md](references/trade-and-quotation.md) and escalate uncertain cases.
- Do not install or run Super Sales Agent. Reuse only its approved reference patterns already registered in `config/github_capability_registry.json`.

## Evaluate before release

Run the project tests and apply every case in [evaluations.md](references/evaluations.md). A failure that invents a customer fact or upgrades a draft to a real-world outcome blocks release.

> Private runtime paths, evidence, execution identities, and product records are intentionally excluded from this public pack.
