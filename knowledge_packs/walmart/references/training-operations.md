# Incremental training operations

## Evidence classes

- `verified_live_fact`: observed in the current authorized T One software/store scope with capture time and evidence reference. A local config value can be live software fact without being live business fact.
- `time_sensitive_evidence`: current official policy, API documentation or dated Seller Center evidence. Recheck at expiry or before a write/commitment.
- `historical_operator_trace`: prior action or output retained for failure learning; never current platform authority.
- `draft`: unexecuted content, plan, schema or approval package.
- `failed_attempt`: attempted research, validation or integration that did not meet its acceptance condition.
- `unknown`: no adequate evidence. Do not infer from another country or platform.
- `blocked_owner_input`: the missing evidence or action belongs to the store/account owner, including identity, tax, bank, OAuth consent, MFA, advertiser billing and external approval.

Each evidence record must carry `captured_at`, `country_site`, `commerce_mode`, `ownership`, `permission_scope`, `source_url_or_local_ref`, `valid_until_or_recheck_trigger` and `evidence_class`. Store secrets only by `credential_ref`.

## One incremental run

1. Read the machine contract, curriculum, official evidence index and failure log.
2. Recheck the actual local connector/registry state; a name or button is not a connection.
3. Select at most three modules using the curriculum selection rule.
4. Collect only permitted official public pages or authorized store evidence. Do not bypass access controls or fetch protected competitor assets.
5. Split claims into facts, time-sensitive evidence, historical traces, drafts, failed attempts, unknowns and owner-blocked inputs.
6. Preserve conflicting evidence and block affected writes; do not silently overwrite history.
7. Update only changed source/rule/module/evaluation records and append a concise failure review when applicable.
8. Run `scripts/validate_training_assets.py` and `tests.test_walmart_expert_training`.
9. Report added/invalidated knowledge, country coverage, failures, test results and owner inputs. Research, a webpage, a button or a passing offline test is never business completion.

## Expiry policy

- API schema, endpoint availability, ads access, performance thresholds, promotions, fees, WFS limits and release notes: recheck every 30 days or before a related write.
- Onboarding, country eligibility, returns, payments and seller policies: recheck every 60 days or before a commitment.
- Authenticated store facts: expire when the store, account, authorization, item, order or task changes; capture again before execution.
- `unknown` and `failed_attempt` do not expire into truth. They require new evidence.

## Failure review format

Record: failure ID, time, module, attempted evidence/action, expected acceptance, observed result, evidence class, impact, safe fallback, retry trigger and whether owner input is required. Never retry CAPTCHA/MFA, identity, bank or authorization steps autonomously.
