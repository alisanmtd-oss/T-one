# T One

**An open-source, local-first AI operating core for global e-commerce and B2B foreign trade.**

[![CI](https://github.com/alisanmtd-oss/T-one/actions/workflows/ci.yml/badge.svg)](https://github.com/alisanmtd-oss/T-one/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-3776AB.svg)](pyproject.toml)
[![Discussions](https://img.shields.io/badge/community-Discussions-7A41C6.svg)](https://github.com/alisanmtd-oss/T-one/discussions)

[中文介绍](README.zh-CN.md) | [Public knowledge packs](docs/PUBLIC_KNOWLEDGE_PACKS.md) | [Roadmap](ROADMAP.md) | [Architecture](docs/ARCHITECTURE.md) | [Contributing](CONTRIBUTING.md) | [Security](SECURITY.md)

T One is built for solo operators, commerce teams, developers, factories, and service partners who want AI agents to help manage cross-border e-commerce and foreign-trade work without mixing stores, customers, credentials, or evidence.

The project models the complete operating chain: product and SKU intake, marketplace listings, pricing, inventory, orders, fulfillment, returns, settlement, suppliers, factories, warehouses, B2B companies, catalogs, quotes, invoices, payments, content experiments, and human approvals. It is designed for workflows around marketplaces and channels such as Amazon, TikTok Shop, SHEIN, Shopee, Lazada, Walmart, eBay, Etsy, independent stores, and B2B export—but this public release does **not** claim that live write access to those platforms is already connected.

## What T One is for

### Global e-commerce operations

- Normalize products, variants, SKUs, listings, prices, inventory, orders, fulfillment, returns, refunds, settlement, and account-health evidence.
- Separate every platform, country/site, store model, ownership type, and authorization identity.
- Prepare AI-assisted research, product intake, listing drafts, operating checklists, risk checks, and approval-gated connector work.
- Preserve the source and timestamp behind facts so an AI draft cannot silently become an operating fact.

### B2B foreign trade

- Model enterprise buyers, suppliers, factories, company contacts, shared catalogs, quote lines, price lists, invoices, payment requests, settlement, and delivery assumptions.
- Keep contact PII behind references and consent/lawful-basis records instead of spreading it through prompts and project files.
- Support the structure needed for lead qualification, customer timelines, sample and quotation handoffs, order follow-up, payment, shipment, and after-sales workflows.
- Keep external messages and irreversible commercial actions behind explicit human confirmation.

### Supply chain, POD, and fulfillment

- Represent suppliers, factories, production methods, capacity, quality, SLA, warehouses, stock, inbound/outbound movement, and fulfillment cost assumptions.
- Connect commerce records to evidence, source documents, compliance artifacts, feedback, and learning events.
- Make multi-project and multi-store growth possible without sharing credentials or execution state by accident.

### Content and growth intelligence

- Store competitor, listing, price, keyword, creative, video-scene, policy, experiment, and performance snapshots as traceable records.
- Turn observations into hypotheses and experiments while preserving rights, evidence, confidence, and risk boundaries.
- Provide a safe foundation for future image, video, localization, advertising, creator, and content-to-commerce skills.

## What is implemented in the public core

| Area | Public status |
|---|---|
| AI providers | Provider catalog, explicit model selection, task routing metadata, and redacted connection errors |
| Credentials | Windows DPAPI-backed local secret storage and credential references; plaintext secrets are not written to project JSON |
| AI data boundary | Data classification, prompt/output redaction, provider policy checks, and sensitive-field blocking |
| Commerce contracts | Products, SKUs, listings, stores, orders, inventory, fulfillment, settlement, feedback, governance, evidence, and risk records |
| Foreign-trade contracts | Companies, company users, suppliers, factories, shared catalogs, quote lines, price lists, invoices, payouts, and consent records |
| Workspace isolation | `workspace -> project -> channel -> store -> task`, with platform, country/site, mode, ownership, and authorization boundaries |
| Connector foundation | Read-only connector primitives, normalized intake records, and capability metadata; live store write adapters remain gated |
| Local runtime | Atomic JSON storage, cache invalidation, safe example configuration, tests, release audit, and SHA256 manifest |
| Chat-first UX reference | Dependency-free synthetic workspace with agent conversations, quick prompts, file-intake affordance, and one settings drawer |
| Public platform agents | Ordinary-chat routing to 17 complete sanitized knowledge-pack bundles; no project setup or extension registry is required |

The current `0.x` release is a Python library, tests, and a browser-only UX reference. It is a foundation for building real agents and operator applications, not a finished hosted ERP or an unguarded bot that can spend money, publish listings, message customers, or ship orders by itself.

## Chat-first platform agents

Version 0.4 publishes all reusable non-TikTok-Shop packs as browsable bundles under [`knowledge_packs/`](knowledge_packs/). The 17 packs cover Amazon, AliExpress, B2B export, B2B outbound customer development, B2B marketplace sales, commerce video, eBay, Etsy, global/local channel planning, Google Ads, independent commerce, Lazada, Meta, SHEIN, Shopee, TikTok Ads, and Walmart. Each bundle contains the applicable Skill instructions, curated references and machine contracts. The TikTok Shop agent, Skill, training contract, tests and references are intentionally excluded.

The dependency-free browser demo keeps the chat-first interaction: users state a goal, T One selects the agent, files enter through the composer, and model/account controls stay in Settings. Its account walkthrough is illustrative only and does not accept credentials or connect to external services.

```python
from ai_ecommerce_director.platform_agents import route_public_chat

route = route_public_chat("比较 Etsy 和 eBay 的上架边界")
assert route["status"] == "multi_platform_comparison"
assert route["external_execution_allowed"] is False
```

The router is deterministic and local. It does not read credentials, connect a store, queue work, or execute a platform action. See [Public knowledge packs](docs/PUBLIC_KNOWLEDGE_PACKS.md).

## Architecture

```text
Workspace
  Project
    Channel (platform + country/site + store mode + ownership)
      Store (isolated authorization and execution identity)
        Task (model + skills + tools + policy + evidence + audit)
    Workstream (B2B, research, creative, finance, or supply chain)
```

If a channel is planned but no authorized platform store exists, its status must be `needs_platform_store`. T One must not pretend that listing, order, shipment, settlement, promotion, or advertising execution is available.

Read the [Architecture](docs/ARCHITECTURE.md) and the sanitized [Brand Operating System](docs/FEISHU_BRAND_OPERATING_SYSTEM.md) for the evidence and operating model.

## Quick start

```powershell
git clone https://github.com/alisanmtd-oss/T-one.git
cd T-one
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install .
.\.venv\Scripts\python -m compileall -q ai_ecommerce_director
.\.venv\Scripts\python -m unittest discover -s tests -v
```

Start with the synthetic examples in `config/`. Never commit live credentials, customer data, supplier contacts, store IDs, or operating evidence.

To inspect the chat-first interaction model without installing anything, open [`demo/chat-first-workspace.html`](demo/chat-first-workspace.html) in a browser. It uses synthetic data, makes no network request, and never claims a live store or advertising connection.

## Community

- Join [Discussions](https://github.com/alisanmtd-oss/T-one/discussions) for introductions, architecture proposals, platform knowledge, foreign-trade workflows, and implementation questions.
- Open an [Issue](https://github.com/alisanmtd-oss/T-one/issues) for reproducible bugs or scoped feature requests.
- Read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request.
- Use GitHub private vulnerability reporting for security or privacy concerns.

Good first contributions include platform/country taxonomies, B2B contracts, connector schemas, safe local skills, data-boundary tests, documentation, and synthetic examples. Contributions must not contain real customer, store, supplier, warehouse, account, or credential data.

## Public/private boundary

This repository is built from an exact-file allowlist. It excludes private stores, customers, leads, contacts, warehouses, product campaigns, recovered conversations, screenshots, browser profiles, cookies, live connector credentials, private desktop shells, browser extensions, raw Feishu pages, and unlicensed third-party assets.

The public-facing name is **T One**. The repository uses a text-only identity until separately reviewed visual assets have clear ownership and redistribution rights. See [BRAND_PUBLIC_BOUNDARY.md](docs/BRAND_PUBLIC_BOUNDARY.md).

## License and release integrity

T One is licensed under [Apache-2.0](LICENSE). Every generated public package includes `PUBLIC_RELEASE_AUDIT.json` and `SHA256SUMS.json`; publication is accepted only when privacy checks, hashes, installation, tests, and CI pass.
