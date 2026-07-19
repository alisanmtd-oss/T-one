# SHEIN evidence status and rule lifecycle

Use exactly one primary status per claim or training record.

| Status | Meaning | Permitted use |
|---|---|---|
| `verified_live_fact` | Observed in an authorized, store-scoped response or an owner-provided authoritative store document with matching site/mode/ownership | May support a decision inside the same authorization scope until its validity or permission expires |
| `time_sensitive_evidence` | Current official public documentation, announcement or policy captured with a date and applicability boundary | Research, draft validation and connector design; recheck before volatile commitments |
| `historical_operator_trace` | Prior store action, result, rejection, error or metric with traceable origin | Diagnosis and experiment design; not a current platform rule by itself |
| `draft` | Proposed rule, mapping, workflow or seller-experience hypothesis awaiting proof | Simulation or review only |
| `failed_attempt` | A research, connector, validation or action attempt that did not establish the claimed result | Failure learning; never positive capability evidence |
| `unknown` | Evidence is absent, ambiguous, stale or scope-mismatched | Must remain unknown; request the smallest missing input |
| `blocked_owner_input` | Progress needs a store owner action or sensitive/externally consequential authorization | Stop at a checklist or gated draft and name the required owner input |

## Required evidence envelope

```json
{
  "record_id": "stable-id",
  "claim": "one atomic claim",
  "status": "verified_live_fact|time_sensitive_evidence|historical_operator_trace|draft|failed_attempt|unknown|blocked_owner_input",
  "source_url_or_trace": "official URL or safe internal trace reference",
  "captured_at": "RFC3339 with timezone",
  "country_site": "site code or unknown",
  "commerce_mode": "platform_self_operated|semi_managed|recognition_only|unknown",
  "ownership": "self_owned|private_tenant_owned|platform_co_ops|partner_owned|unknown",
  "store_binding_id": "required for store facts, otherwise null",
  "execution_identity_id": "required for authenticated proof, otherwise null",
  "permission_scope": "public_read or exact authenticated scope",
  "valid_until_or_review_at": "RFC3339 or event trigger",
  "boundary": "what this evidence does not prove",
  "supersedes": []
}
```

Never store tokens, cookies, MFA material, bank data, customer PII or unredacted secrets in the envelope.

## Precedence and downgrade rules

1. A current authorized store response outranks a planning registry or public announcement for that exact store.
2. Official public evidence outranks seller experience for platform rules, but cannot prove store access or eligibility.
3. Seller experience starts as `draft`; repeated results can become `historical_operator_trace`, not an official universal rule.
4. Scope mismatch, expired authorization, stale review date, permission error or contradictory live evidence downgrades a claim to `unknown` or `failed_attempt`.
5. A screenshot, button, route name, connector name or passing unit test cannot promote capability state without an authenticated read/write proof.

## Rule lifecycle

`draft -> time_sensitive_evidence -> verified_live_fact` is not automatic. Each transition needs new evidence and preserved boundaries. Store rules may move from `verified_live_fact` to `unknown` when the store, site, mode, ownership, category, permission or validity changes.

Every executable rule records:

- `rule_id`, version and superseded IDs;
- source and capture time;
- site, mode, ownership, store and permission scope;
- review date or invalidation event;
- capability state and external-effect gate;
- regression cases that must pass.

Suggested review windows are only scheduler defaults: 7 days for campaign/SLA/payment/onboarding summaries, 30 days for API fields and Seller Hub feature descriptions, and 90 days for low-volatility corporate history. Recheck immediately on an API error, Seller Hub mismatch, policy announcement, permission change or owner report.

## Evidence-before-training gate

Every cycle runs in this order:

1. Identify the real execution identity, browser/software version and store authorization state.
2. If authorized, inspect the exact store-scoped surface read-only; otherwise use an official public Seller/Developer/Ads/Help page or lawful sandbox.
3. Record opened page/software, URL/version, capture time, site, mode, clicks/scrolls, actual input/output, errors and permission boundary.
4. Only then update a rule, workflow, evaluation or capability mapping.

If no new external page/software evidence is obtained, record `no_increment_recorded`. Do not manufacture a training result. A screenshot or page alone is insufficient when the claim requires live input/output, account eligibility or a business action result.
