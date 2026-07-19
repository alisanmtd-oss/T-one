# Evidence, tools, and approvals

## Evidence labels

- `verified_live_fact`: directly observed in an authorized live system or supported by a current responsible-person execution receipt.
- `time_sensitive_evidence`: dated official rule, product page, customer statement, rate, list result, or other evidence that must be rechecked.
- `historical_operator_trace`: prior operation, output, or seller experience that can inform an experiment but cannot override current authority.
- `draft`: prepared, inferred, hypothesized, or approved but not sent, published, signed, booked, paid, or shipped.
- `failed_attempt`: attempted page, software, connector, validation, or action that did not produce the required result.
- `unknown`: required information is absent, expired, conflicting, or not yet supported.
- `blocked_owner_input`: progress requires an owner-supplied fact, permission, credential scope, bank/identity input, or accountable decision.

Seller experience and community reports can only be `historical_operator_trace` or `draft`. Record sample, date, country, channel, hypothesis, metric, stop rule, and official-rule conflict check. Never promote it to a policy rule by counting anecdotes.

## Source order

1. Applicable law, regulator, customs, sanctions, or official government source.
2. ICC or another competent rule owner for its own standard.
3. Authorized connector or responsible-person document for transaction facts.
4. First-party product/company source for company claims.
5. Reputable secondary source for context.
6. Seller experience only as an experiment hypothesis.

Every time-sensitive record must include `url`, `verified_on`, `country_site`, `store_model`, `applies_to`, `limitations`, and `recheck_trigger`.

## Tool states

- `research_only`: public, lawful read-only use.
- `available_unconnected`: the tool/capability is named, but no verified credentials or health check exists.
- `connected_read_only`: authorization and read health are evidenced; writes are impossible or disabled.
- `connected_write_gated`: exact account scope, permission, health check, approval gate, idempotency, and audit trail are evidenced.
- `blocked`: prohibited, unsafe, unsupported, or outside scope.

A model candidate in the expert registry is not a live model connection. A tool name in the registry is not a connector. Never upgrade state from a UI label or configuration key alone.

## Approval record

Each side effect requires: `approval_id`, `action_type`, `tenant_id`, `project_id`, `account_id`, recipient/counterparty, exact payload or document hash, monetary and legal impact, connector and execution identity, approver, approval time, expiry, idempotency key, and result receipt. Any changed recipient, price, bank detail, destination, term, attachment, or payload invalidates the approval.

## Always blocked

- bulk unsolicited messaging or form submission;
- scraping private contact data or gated groups;
- bypassing robots, rate limits, anti-bot controls, CAPTCHA, MFA, or platform restrictions;
- anti-association or account-linkage evasion;
- reusing credentials across tenants, projects, stores, accounts, or execution identities;
- copying customer photos, reviews, competitor videos, trademarks, people, music, or other protected assets without permission;
- fabricated product, contact, company, certification, customs, payment, delivery, or performance facts;
- automatic bank-detail changes, payment confirmations, shipment commitments, or advertising spend.

## Architecture reference

The public `cjboy007/super-sales-agent` repository is an architecture reference only. Its useful patterns are a canonical customer timeline, draft-only quote rows with missing-field lists, human approval for customer-visible actions, explicit runtime switches, workspace authorization, and execution/failure logs. Do not install it, create a second universal agent runtime, or treat its adapters as connected T One capabilities.
