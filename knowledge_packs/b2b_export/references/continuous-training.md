# Continuous evidence-first training

## Fixed order

1. Resolve the execution identity first: tenant, project, store binding, platform, country/site, mode, ownership and executable identity.
3. Otherwise inspect an official public Seller, Developer, Ads, Help, product-demo or legal page. Do not borrow another account or bypass login, CAPTCHA, MFA, paywalls or access controls.
4. Record the app/page, version or URL, capture time, country/site, store mode, ownership, permissions, clicks, scrolling, actual input, actual output, errors and limitations.
5. Only after a new external-visible evidence record is accepted may the run update this Skill, curriculum, rules, evaluations or tool mapping.
6. If no new evidence is obtained, output `no_delta` and make no learning-asset changes.

## Evidence promotion

- Use exactly: `verified_live_fact`, `time_sensitive_evidence`, `historical_operator_trace`, `draft`, `failed_attempt`, `unknown`, `blocked_owner_input`.
- Official rules and product pages are time-sensitive until rechecked.
- A real authorized UI observation can verify an entry, field or boundary, but a visible button alone does not prove the downstream business action completed.
- Seller experience, forums and GitHub repositories remain hypotheses or technical references unless the relevant official rule or live authorized behavior corroborates them.
- Expired evidence is not eligible for rule promotion.

## Incremental loop

Run:

```powershell
python skills/platform-experts/b2b_export/b2b-export-expert/scripts/run_incremental_training.py --write
```


Every automation run must first collect external evidence with a supported browser/software tool. The script is the distillation gate, not a substitute for evidence collection.

## No-delta behavior

When no new page or software evidence is available:

- do not add inferred facts;
- do not manufacture curriculum modules or evaluations;
- do not advance connector states;
- write only a no-delta report with the attempted source, error and next retry condition.

## Human approval boundary

Real publishing, price changes, advertising spend, discounts, payments, shipments, refunds, outreach, MFA, banking and identity actions stop before execution. Follow Amazon Ads Agent's verified public pattern: summarize proposed changes first; the user reviews, selects and approves changes before any executable connector can act.

> Private runtime paths, evidence, execution identities, and product records are intentionally excluded from this public pack.
