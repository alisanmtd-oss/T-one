# T One

**A local-first operating brain for multi-project, multi-store commerce teams.**

[简体中文](README.zh-CN.md) | [Capability status](docs/CAPABILITY_STATUS.md) | [File guide](docs/FILE_GUIDE.md) | [Roadmap](ROADMAP.md)

T One organizes work across marketplace operations, independent commerce, B2B sales,
outbound development, content and advertising, finance, risk, and approvals. It is
designed around durable business context:

`workspace -> project -> platform -> real store or business container -> primary conversation -> workflows`

T One is **not** a claim that every marketplace, ERP, payment provider, or messaging
service is already connected. The public repository is a sanitized community core.
Private store credentials, customer data, live connectors, browser profiles, and
execution evidence are not published.

![T One chat-first workspace](assets/screenshots/t-one-chat-workspace.png)

## Product direction

- One project can contain many platforms and real stores.
- One store or business container keeps one durable primary conversation.
- Listing, inventory, orders, ads, content, finance, and support are workflows inside
  that conversation, not duplicate sidebar agents.
- Unbound stores do not appear as live operating data.
- Shared legal, copyright, finance, approval, evidence, and connector controls are
  built once and reused across business units.
- External writes, ad spend, payments, fulfillment, refunds, outreach, identity,
  banking, and MFA stay behind explicit human approval.

## What is usable today

Status labels in this repository have strict meanings:

| State | Meaning |
| --- | --- |
| **Verified** | Implemented and exercised in the public test suite or public demo. |
| **Requires setup** | Implemented contract or local integration that still needs the operator's lawful credentials or environment. |
| **Partial** | Useful foundation exists, but the end-to-end workflow is not complete. |
| **Not connected / planned** | Documentation, schema, or design only. Do not treat it as a working integration. |

| Capability | State | Public evidence |
| --- | --- | --- |
| Local Python community core | **Verified** | Package, tests, synthetic fixtures |
| Project / platform / store / task isolation | **Verified** | Domain models and regression tests |
| Chat-first browser reference | **Verified** | Synthetic demo; no live stores |
| Knowledge-pack registry | **Verified** | Sanitized non-private packs |
| Approval and evidence contracts | **Verified** | Local contracts and tests |
| Local model/provider configuration contracts | **Partial** | No provider credentials are shipped |
| Marketplace and ERP reads | **Requires setup** | Contracts exist; no public live account |
| Marketplace writes and advertising | **Not connected / planned** | Intentionally approval-gated |
| Email, WhatsApp, WeChat, Telegram, Feishu | **Not connected / planned** | No public OAuth or live connector |
| Payment and settlement providers | **Not connected / planned** | Financial schemas only |
| Windows community installer | **Verified** | Offline synthetic demo only; no live connectors or computer control |
| Full Windows operating runtime | **Private product, not in this repo** | Public installer does not claim these capabilities |

See [docs/CAPABILITY_STATUS.md](docs/CAPABILITY_STATUS.md) before evaluating or
integrating any feature.

## Public core versus private product

This repository publishes:

- a dependency-light Python community core;
- synthetic configuration and fixtures;
- sanitized platform knowledge packs;
- an installable offline Windows shell for the browser reference experience;
- approval, evidence, routing, and isolation contracts;
- tests, contribution guidance, and release integrity manifests.

It does not publish:

- live store, customer, supplier, employee, or financial data;
- credentials, tokens, cookies, browser profiles, or identity documents;
- private Windows desktop runtime and commercial connectors;
- unrestricted store writes, outreach, advertising, payments, or fulfillment;
- private prompts, internal evidence archives, or raw conversation history.

## Architecture

```text
Owner / Investor
  -> Group operating brain / PMO
    -> Business unit lead
      -> Supervisor
        -> Role agents and reusable skills

Business units
  - Marketplace operations
  - Independent commerce
  - B2B platform acquisition
  - Outbound customer development
  - Content and advertising
  - Shared finance, legal, evidence, approvals, and connectors
```

Every provider authorization and external execution identity must remain isolated by
project, platform, site, store mode, and store binding.

## Quick start

### Normal Windows installation

Download `T-One-Community-Setup-*.exe` from the Release assets, open it, choose an
installation directory, and continue through the setup wizard. It creates Start menu
and optional desktop shortcuts and includes an uninstaller. No Python or command line
is required. This public installer contains only the synthetic offline demo; it does
not control the computer, connect a store, or call an external service.

The installer source is under `desktop_public/`. The fixed dependency versions and
GitHub workflow make the installer reproducible from public source.

### Developer installation

```powershell
git clone https://github.com/alisanmtd-oss/T-one.git
cd T-one
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install .
.\.venv\Scripts\python -m compileall -q ai_ecommerce_director
.\.venv\Scripts\python -m unittest discover -s tests -v
```

Open `demo/chat-first-workspace.html` to inspect the synthetic browser reference.
It does not connect to a real store or execute external actions.

## Repository map

| Path | Purpose |
| --- | --- |
| `ai_ecommerce_director/` | Public Python domain models, routing, evidence, approval, and knowledge-pack APIs |
| `knowledge_packs/` | Sanitized platform and business knowledge assets |
| `config/` | Synthetic examples and public-safe registries |
| `demo/` | Browser-only reference UI with synthetic data |
| `desktop_public/` | Public Electron shell and assisted NSIS installer definition |
| `docs/` | Architecture, file guide, status truth, and public knowledge-pack notes |
| `scripts/` | Public validation and release-integrity helpers |
| `tests/` | Regression tests for public behavior and safety boundaries |
| `.github/` | Issue, pull request, and community workflows |

Read [docs/FILE_GUIDE.md](docs/FILE_GUIDE.md) for a detailed guide.

## Screenshots

The screenshots show the interaction direction, not proof of a live marketplace or
ERP connection.

![T One settings reference](assets/screenshots/t-one-settings.png)

## Next release direction

The next public milestone focuses on:

1. a stable skill/plugin/connector manifest;
2. scoped local MCP/API access with revocable tokens;
3. provider connection tests with understandable errors;
4. read-only commerce and ERP adapters before any write adapter;
5. settlement and operating-cost schemas separated by platform, site, store mode,
   legal entity, fulfillment model, and rule version;
6. durable jobs, evidence, approvals, and recovery;
7. clearer installation and compatibility verification.

The full sequence and non-goals are in [ROADMAP.md](ROADMAP.md).

## Codex integration

The companion project
**[Codex × T One Operator Skill](https://github.com/alisanmtd-oss/codex-t-one-skill)**
teaches Codex how to inspect,
configure, operate, and verify a T One workspace without confusing drafts, plans, and
live integrations. It is published separately so the T One runtime and the Codex
operating instructions can evolve independently.

## Safety and contribution

- Never commit live credentials or personal, store, customer, supplier, or financial data.
- A button, schema, research note, or unit test is not proof of a live integration.
- Unknown repositories and connectors are blocked until license and security review.
- External side effects require explicit human confirmation.

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md),
[GOVERNANCE.md](GOVERNANCE.md), and [SUPPORT.md](SUPPORT.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).
