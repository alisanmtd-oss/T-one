# Contributing to T One

Thank you for helping build a safer, more useful commerce-agent foundation.

## Before you start

1. Search existing Issues and Discussions.
2. Keep one pull request focused on one capability or correction.
3. Do not include real store data, customer data, credentials, screenshots, recovered conversations, or private operating evidence.
4. For a new dependency or copied code, document its source, license, maintenance status, and why it is needed.

## Contribution areas

- `core`: schemas, storage, data boundaries, provider configuration.
- `connector`: read-only platform, ERP, or service adapters.
- `skill`: narrowly scoped, installable operating knowledge or workflows.
- `docs`: architecture, platform taxonomy, examples, and translations.
- `test`: regressions, security boundaries, and compatibility coverage.

## Commerce taxonomy requirement

Platform work must identify all four dimensions:

```text
platform + country/site + store mode + ownership
```

Do not use a broad region such as Southeast Asia as an executable store. TikTok Shop, Shopee, and Lazada routes must resolve to a concrete country/site. T One-operated or co-operated stores must not be described as a marketplace's official full-managed program.

## Development workflow

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install .
.\.venv\Scripts\python -m compileall -q ai_ecommerce_director
.\.venv\Scripts\python -m unittest discover -s tests -v
```

- Add or update focused tests for behavior changes.
- Keep configuration examples synthetic.
- Preserve backward compatibility unless the pull request documents a migration.
- Do not introduce network writes, account actions, payment, ad spend, fulfillment, or message sending without an explicit approval and audit design.

## Pull requests

Describe the problem, the behavior change, the data or authorization boundary, and the tests used. Small pull requests are easier to review and safer to release.

By contributing, you certify that you have the right to submit the work under the Apache License 2.0.
