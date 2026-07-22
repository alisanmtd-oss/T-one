---
name: b2b-export-expert
description: Compatibility route for the product-agnostic B2B export workflow. Use it to preserve legacy expert routing while delegating live work to the canonical b2b-foreign-trade-sales Skill, with tenant, category, product, task-evidence, connector, and approval isolation.
---

# B2B Export Expert Compatibility Route

## Compatibility Status

This entry is `merge_duplicate`, not a second B2B agent. The canonical execution and training source is `skills/b2b-foreign-trade-sales/SKILL.md`, and the canonical runtime is `ai_ecommerce_director/b2b_sales_runtime.py`. Do not create another model gateway, CRM, account timeline, agent runtime, or universal sales workflow here.

`config/platform_expert_training/b2b_export.json` remains a compatibility and regression contract only. The assets below this directory are dated training evidence; they do not override the canonical Skill or prove that a named connector is live.

## Income-Mainline Acceptance Gate

At least 70% of each learning round must directly improve the product-independent B2B revenue path: buyer and purchase-signal discovery, deduplication, qualification, contact/decision chain, industry language, discovery, sample/quote, negotiation, PI/contract, production/logistics, delivery, collection, repeat, representatives/upstream/downstream partners, or evidence-gated cross-sell. Trade finance is auxiliary only when a scoped buyer's payment terms, LC, D/P, D/A, credit, sanctions or collection issue requires it. Macro finance, investing, stocks, crypto assets and general banking research are `irrelevant_skip`.

A webpage is `opened_not_reviewed` until the actual page is scrolled through its relevant sections to the footer or a recorded access boundary and at least one directly relevant second-level page is inspected. Structured text may support facts but does not satisfy the visible-scroll gate by itself. A video at 0:00, a cover, title or description is `opened_not_reviewed`; for a video no longer than ten minutes, require at least 95% playback or at least 95% public transcript coverage plus key-frame checks. When comments exist, inspect pinned/high-signal, questions, objections and failure cases, with at least ten visible comments or all available when fewer; record sorts, overlap, omissions and noise. Never infer unseen content.

Every round must output four truth lists: `deviation_check`, `opened_not_reviewed`, `completed_review`, and the incremental runner's actual `updated` or `no_delta` result. Do not promote knowledge from a page or video that fails its media gate, and do not use auxiliary research to pad the mainline percentage.

## Required Scope Layers

Keep these layers separate on every read and write:

1. `platform_public`: platform rules, country/site, store mode, generic listing, order, advertising, and after-sales behavior. Never place a tenant's product facts here.
2. `category_capability`: plug-in category schema and compliance for apparel, home, beauty, electronics, food/restricted goods, digital goods, machinery, and other lawful categories. Read the current official platform schema when the category is unknown; do not invent fields.
3. `tenant_project_product`: the user's own product, variants, cost, price, images, inventory, capacity, lead time, brand, warehouse, and compliance evidence. Load it only for the matching `tenant_id/project_id/product_id/store_binding`.
4. `task_evidence`: a listing, advertisement, order, asset, customer, message, quote, failure, payment, or shipment event belongs only to its task and account timeline. It must not become a global product default.

## Delegate Before Acting

1. Read the project authority files required by `AGENTS.md`.
2. Load `skills/b2b-foreign-trade-sales/SKILL.md` as the one canonical B2B workflow.
3. Require `tenant_id`, `project_id`, `product_id`, `store_binding`, `platform`, `country_site`, `mode`, `ownership`, `execution_identity`, `account_id`, and `task_id` before any state write.
4. Resolve the current category and platform schema. If the schema, product facts, ownership, or connector state is not evidenced, keep it `unknown` or `blocked_owner_input`.
5. Use the generic lifecycle `lead -> qualified -> discovery -> sample_or_quote -> negotiation -> pi_contract -> delivery -> collection -> repeat` for any lawful product. A draft, button, report, test, approval, or public page does not advance a business stage.

## Scope Leakage Guard

Private tenant product, variation, price, media, inventory, capacity, warehouse, and customer fixtures are excluded from this public pack and must never become defaults.

Private tenant routes and facts are not included; public users must supply their own fully scoped project evidence.

## Evidence and Side-Effect Boundary

Use exactly one material evidence label: `verified_live_fact`, `time_sensitive_evidence`, `historical_operator_trace`, `draft`, `failed_attempt`, `unknown`, or `blocked_owner_input`. Tool names, buttons, public help pages, and passing tests do not prove a live connector or business outcome.

Without item-level human confirmation and a verified correctly scoped connector, do not publish, change price, spend on ads, create promotions, contact a lead, send a quotation/PI/contract, request or confirm payment, book or confirm shipment, refund, or write to an external CRM. Never bypass CAPTCHA/MFA/anti-bot controls, evade account controls, reuse cross-account authorization, or reuse unlicensed assets.

## Knowledge-Package Admission and Reuse

Before opening broad platform introductions, inventory the existing T One Skill, rules, curriculum, templates, evaluations, failure traces, connectors and GitHub admission registry, then search for already distilled B2B playbooks, schemas, checklists, SDK samples or maintained sales packages that address the specific gap. Audit each candidate's upstream owner, version or recent commit/release, citations, license, issues/PRs/security, executable code, credentials or telemetry risk, dependencies, deployment cost, overlap and `platform/country_site/store_mode/ownership` scope. Use only `keep_reuse`, `merge_into_existing`, `extract_rules_only`, `research_only`, `rejected_stale`, `rejected_license` or `rejected_unsafe`; an unknown license blocks copying, installation and commercial integration.

Sample one core workflow, one boundary or failure and three material rules before adopting a package. Verify only the time-sensitive differences against current official deep pages. Merge the delta into this existing route and the canonical B2B Skill; never install a second CRM or Agent merely because a repository contains a timeline, pipeline or approval UI. Use the recorded English query matrix and its `repo/topic/awesome/skill/playbook/SOP/checklist/template/evaluation/SDK/MCP/ERP/OMS/PIM/WMS` variants for scoped gaps, retaining both result and no-result queries as the search receipt.

Current disposition is: keep the already admitted Super Sales Agent timeline/approval/idempotency patterns as reference only; use Frappe CRM only as a schema-comparison source because its LICENSE and package metadata conflict between AGPL/GPL labels and deployment duplicates the existing runtime; reject Twenty code integration pending explicit commercial-license review because its upstream license mixes AGPL with Enterprise-marked files. Keep `qpood/b2b-buyer-qualification` as `research_only`: its explainable evidence map and explicit `no public evidence` boundary are compatible with existing truth rules, but its fixed 100-point weights are a new, uncited single-author rubric and must not become a universal score. Reject `Tomsonx232/smb-sales-boost-skill` and `baryhuang/mcp-hubspot` as `rejected_unsafe` for integration: the former exposes paid lead queries/exports, PII, external email scheduling and purchase/auto-top-up surfaces; the latter requests CRM read/write scopes and has unresolved upstream tenant-isolation, timeout, prompt-injection and dry-run concerns. Do not provide credentials, export people, purchase credits, schedule messages, authorize CRM scopes, install or execute either candidate. None of the reviewed repositories is newly installed or connected.

## Buyer-Finding and Qualification Gate

Find prospects through a scoped combination of current country/industry research, lawful public company and association sources, trade shows or missions, tenders/RFQs, platform-native inquiries, direct channels, and qualified representatives or distributors. Record the canonical source, date, country, product/category fit and public business signal. A public company page, directory row, show attendee, customs record, map result, AI suggestion or partner-search report is a `lead_candidate`, not consent, a verified decision maker, outreach, qualification or a deal.

Before promoting a candidate, establish the legal entity and role, source reliability, market/territory, product and standards fit, buying use case, authority and decision process, indicative volume, schedule, destination, delivery and service needs, payment expectations, trade/bank references, sanctions/export-control scope and unresolved fraud signals. For a representative or distributor, also test sales force, territory, product conflicts, facilities, inventory/service capability, customer profile, marketing plan and realistic projections. Preserve `unknown` instead of filling gaps with private_tenant facts or generic assumptions.

## Professional Terms and Industry Talk Tracks

Maintain a sourced terminology ledger rather than a static sales glossary. Each term must retain language, authoritative definition or current industry meaning, version/date, parties, named place or event, product/category and country applicability, ambiguity and approved translation. For example, an Incoterms® rule allocates tasks, costs and risk; it does not by itself define the goods, price, payment method/timing, title transfer, document set, non-conformity liability or dispute resolution. Always write the chosen rule, precise named place/port and version.

Draft talk tracks from evidence: `sourced relevance -> bounded value hypothesis -> one discovery question -> next step`. Discovery should ask how the buyer uses or resells the product, required specifications/certifications, target volume and forecast basis, current supplier/process pain, approval roles, timeline, destination and logistics, installation/training/after-sales needs, acceptance criteria, payment method and risk constraints. Separate industry facts from hypotheses, mirror the buyer's verified vocabulary, explain acronyms once, and localize meaning rather than word-for-word translating. A fluent draft is not permission to send and never proves buyer interest.

## Buying-Signal and Decision-Chain Ledger

Keep an evidence ladder instead of one generic `interested` flag: `source_context -> account_fit_hypothesis -> observed_account_signal -> verified_contact_role -> discovery_confirmed_need -> commercial_action_receipt`. A trade-show page saying that attendees are actively sourcing, placing orders or looking for private-label, small-batch, fast-turn or capacity solutions is an event-level source signal. It does not prove that a named company attended, that a person is a decision maker, or that either wants the tenant's offer.

For each candidate, preserve `signal_subject`, `signal_type`, `source_url_or_receipt`, `observed_at`, `country_site`, `category`, `role`, `decision_stage`, `verification_state`, `valid_until`, `counter_signal`, and `next_verification_question`. Map the likely chain without inventing names: user or technical evaluator, sourcing/procurement, operations or production, finance, compliance, and final approver. Tailor terminology and discovery to the evidenced role; do not send the same pitch to an operator, buyer and owner.

Private customer records, pipeline state, and company identities are excluded from this public pack. Reuse only the generic deduplication, consent, evidence, and approval rules.

## Signal-to-Discovery and Mutual-Next-Step Gate

Convert research through this truth sequence only: `public_or_first_party_signal -> evidence_backed_hypothesis -> role_specific_open_question -> customer_confirmed_need -> next_step_draft -> bilateral_or_authorized_receipt`. Hiring, funding, technology, visit, event, CRM, transcript, AI-summary or package-generated signals do not prove pain, intent, role, authority, consent or qualification. State the sourced fact and uncertainty, then ask one open question suited to the role; validate research rather than presenting inference as fact.

The discovery packet should preserve known fact/source, hypothesis, role to verify, current workflow, measurable success criterion, problem source and consequence, timeline reason, constraints, decision roles/process, counter-signal and next question. Do not interrogate with a complete checklist or force one framework onto every buyer. A mutual-action plan, recap, calendar proposal or AI-generated next step remains a draft until both sides confirm owners, deliverable, target date, success criteria, dependencies and risks through an authorized receipt. ROI remains a sourced range or scenario; missing inputs generate questions, not promises.

The public packages `Prospeda/claude-gtm-skills` and `rossgrieb/technical-discovery-playbook` have no root license file and remain `research_only`; copy no code, prose or templates. `imnotcarlosboozer/gtm-agent-repo` is `rejected_unsafe` because its tenant-specific scoring, sensitive data dependencies, CRM writes, sequence activation and autonomous updates cannot enter T One. Never install these packages, enroll a sequence, write CRM, activate outreach or create a second runtime from research evidence.

## Public Tender and RFQ Gate

Treat an official public notice with a canonical URL, issuing organization, unique reference, beneficiary country, opportunity type, publication date and deadline/time zone as an `official_notice_identity` and issuer-level purchase signal. It is not yet a qualified buyer, a verified contact or decision maker, a product match, permission to contact, an approved quotation, a submitted bid or revenue. Preserve the notice version, amendment state, registration level, official Links/Documents and Contacts tabs, goods/service codes, exact submission channel and every missing annex or eligibility fact.

Do not quote from a broad title such as “procurement of equipment” when specifications, quantities, acceptance criteria, destination, commercial form or eligibility remain in an unseen annex. UNGM states that its e-procurement systems are not integrated into the marketplace and that the grey `Express Interest` control does not submit an offer; follow the actual notice instructions. For UNDP notices, Quantum is the described digital procurement platform, but public documentation does not prove a tenant account, entitlement or T One connector. Only a receipt from the notice-authorized submission system can advance to `submitted_receipt`, and any registration, clarification, document upload or submission remains an external action requiring item-level approval.

For anti-fraud review, compare any invitation against the canonical notice URL and reference, issuer, country, publication/deadline including time zone, official Links/Documents, official contact, submission method and current amendments. An alternate email, private messaging path, urgent registration/legal/bank fee, third-party processor or beneficiary, or request to ignore the official portal is contradictory evidence: pause contact, payment, quotation commitment, travel and shipment, preserve the packet and route it to the responsible owner. Do not accuse the sender or report externally without authority.

## Counterparty Fraud-Risk Gate

Do not declare someone a scammer from one anomaly. Classify the scoped counterparty as `unverified`, `inconsistent_evidence`, `high_risk_pending_review`, `verified_with_residual_risk`, or `officially_confirmed_fraud`. Preserve the evidence and missing checks. High-risk signals include impersonating a government or known company through an inconsistent/personal address, cloned sites or forged-looking documents, unsolicited outsized procurement claims, secrecy or urgency, pressure for executive travel, upfront taxes/registration/legal/bank fees, wire/crypto demands, last-minute third-party processors or beneficiary changes, mismatched billing/shipping/country data, refusal to provide a valid business license/chamber listing/trade or bank references, and evasive end-use or service answers.

Pause communication, quote commitment, payment and travel when risk is high. Independently verify the legal entity and license, official domain/contact, authorized person, address/site, trade and bank references, beneficial owners/controllers, end user/use, sanctions/export-control results and beneficiary consistency through official or independently sourced channels. Official-looking documents, a reference supplied only by the prospect, a CSL no-match, a video call or an AI score is not clearance. Only an authorized regulator, law-enforcement outcome or responsible owner may set `officially_confirmed_fraud`; T One may prepare a verification packet but must not accuse, contact, pay, report or expose personal data autonomously.

## Sanctions and Export-Control Gate

Before a commercial commitment where U.S. sanctions or export-control rules may apply, screen the scoped buyer, aliases, owners, controllers, signers, end user, intermediaries, banks and route. A name-search score is only a candidate: preserve query inputs, original source list, version or capture time, result and human disposition. Apply OFAC aggregate direct/indirect ownership analysis separately from control, and review a blocked person acting for an otherwise nonblocked entity. Never treat a no-match, fuzzy score or tool response as legal clearance.

BIS red flags—such as an implausible end use, abnormal route, refusal of ordinary installation/training or evasive answers—trigger bounded inquiry and re-evaluation, not an automatic accusation. If unresolved, refrain from commitment and route to the responsible compliance owner. The ITA CSL API and `moov-io/watchman` are not connected: Watchman remains `research_only_candidate`; do not install its experimental MCP or use it to decide sanctions, ownership, end-use or transaction approval.

## Payment-Change and BEC Gate

Freeze every bank-account, beneficiary or payment-procedure change until it is independently verified through a pre-existing known-good channel. Never use the telephone number, link or reply path contained in the change request, and do not treat the same email thread, urgency, an invoice PDF, a screenshot or a buyer promise as verification. Preserve the baseline instruction, requested change, invoice/account scope, callback evidence and a separate authorized reviewer disposition.

If funds may already have been diverted, route immediate contact with the financial institution through its official independently found channel, prepare a recall and evidence packet, and assign jurisdiction-specific reporting to the responsible owner. A bank contact, recall request, IC3/NCSC report, investigation or annual recovery statistic is not recovered money. T One must not change a beneficiary, make a payment, submit a complaint, promise recovery or mark collection without the correctly scoped authority and receipt.

## Trade-Finance Instrument Gate

Select cash-in-advance or licensed escrow, letter of credit, documentary collection, open account and any insurance/finance instrument from the actual buyer relationship, credit and country/bank risk, shipment mode, document control, cash-flow and FX facts. Never impose a universal hierarchy, fixed transaction threshold, fixed advance percentage or first-shipment count from a forum comment.

For a documentary credit, preserve issuing/advising/confirming/nominated bank roles, authenticity, terms/amendments, presentation deadline, required documents, discrepancies, bank disposition and receipt. Banks examine documents rather than goods, and the credit is separate from the sales contract. An issued LC, prepared document set or presentation is not payment. In a collection, banks do not guarantee payment or verify documents: D/P releases controlling documents against payment, while D/A releases them against a signed promise whose maturity payment is not assured. Open-account shipment precedes the due date and remains exporter exposure unless a separately verified mitigation applies. A buyer promise, signed acceptance, insurance option, recall request or provider status never replaces an external funds receipt.
