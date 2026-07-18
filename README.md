# T One

**A local-first, multi-project foundation for AI-assisted commerce operations.**

[Chinese](README.zh-CN.md) | [Roadmap](ROADMAP.md) | [Contributing](CONTRIBUTING.md) | [Security](SECURITY.md) | [Apache-2.0 License](LICENSE)

T One is a sanitized, community-focused foundation for AI-assisted commerce operations. It provides reusable contracts for AI providers, encrypted local credentials, model data boundaries, commerce records, connector primitives, workspace hierarchy, and atomic local storage.

The public core is designed for teams that operate many projects, channels, stores, and tasks without mixing their identities or data. It is not a storefront, a generic ERP clone, or a dump of the private production workspace.

## What is included

- Multi-provider AI configuration with explicit model selection.
- Local credential references and Windows DPAPI-backed secret storage.
- Data classification, redaction, and provider policy checks before model calls.
- Commerce schemas for products, inventory, listings, orders, fulfillment, settlement, and feedback.
- A hierarchy of workspace -> project -> channel -> store -> task.
- Read-only connector primitives and normalized intake records.
- Atomic JSON storage, cache controls, and focused unit tests.
- Safe example configurations with no real store or customer data.

## What is intentionally private

- Real stores, accounts, customers, suppliers, leads, warehouses, and contacts.
- Recovered conversations, operating evidence, screenshots, browser profiles, and cookies.
- Product campaigns, marketplace execution scripts, private desktop shells, and browser extensions.
- API keys, OAuth tokens, MFA material, bank information, identity documents, and passwords.
- Private Feishu pages and raw course or brand-operating material.

## Architecture

```text
Workspace
  Project
    Channel (platform + country/site + store mode + ownership)
      Store (isolated authorization and execution identity)
        Task (model + skills + tools + policy + audit context)
```

Every executable store identity must remain isolated by tenant, workspace, project, platform, country/site, store mode, ownership, and store ID. A channel without a real authorized store is represented as `needs_platform_store`; it must not pretend that listing, order, shipment, settlement, activity, or advertising actions are available.

See [Architecture](docs/ARCHITECTURE.md) and the sanitized [Feishu Brand Operating System](docs/FEISHU_BRAND_OPERATING_SYSTEM.md).

## Quick start

The current community core is a Python library and test suite. Private desktop applications are not included.

```powershell
git clone https://github.com/alisanmtd-oss/T-one.git
cd T-one
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install .
.\.venv\Scripts\python -m compileall -q ai_ecommerce_director
.\.venv\Scripts\python -m unittest discover -s tests -v
```

Start from the safe examples in `config/`. Never put live credentials or customer data in committed JSON files.

## Community

- Use [Discussions](https://github.com/alisanmtd-oss/T-one/discussions) for design proposals, integrations, and implementation questions.
- Use Issues for reproducible bugs and scoped feature requests.
- Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.
- Report vulnerabilities through GitHub private vulnerability reporting, never through a public issue.

Good first contribution areas include connector schemas, platform/site taxonomy corrections, data-boundary tests, documentation, and small local-first skills. Store writes, advertising spend, payment, fulfillment, and account-security actions require stronger approval and audit controls and are not accepted as unguarded automations.

## Release status

This is a `0.x` community preview built from an exact-file allowlist. The generated package includes `PUBLIC_RELEASE_AUDIT.json` and `SHA256SUMS.json`. The public core is licensed under Apache-2.0; a release is published only when the audit has no findings and the generated tree passes its tests and privacy verifier.

## Brand boundary

The public-facing name is **T One**. See [BRAND_PUBLIC_BOUNDARY.md](docs/BRAND_PUBLIC_BOUNDARY.md). No private logo, customer mark, product photography, or third-party asset is included.
