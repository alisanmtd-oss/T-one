# File guide

## Runtime and domain code

- `ai_ecommerce_director/`: public Python core. It contains domain models, isolation
  rules, evidence and approval contracts, and safe knowledge-pack access.
- `knowledge_packs/`: sanitized public knowledge. A pack is not a live connector and
  does not grant permission to act on a platform.
- `config/`: synthetic examples and public-safe registries. Values in this directory
  are examples unless a file explicitly states otherwise.

## User experience

- `demo/chat-first-workspace.html`: dependency-free browser reference. It uses only
  synthetic data and cannot operate a real store.
- `assets/screenshots/`: sanitized images used by the public README. Screenshots show
  product direction, not live integration evidence.

## Quality and release integrity

- `tests/`: public regression tests for behavior and boundaries.
- `scripts/`: validation and release-integrity helpers.
- `SHA256SUMS.json`: generated artifact hashes in a staged release.
- `PUBLIC_RELEASE_AUDIT.json`: generated audit describing the staged release.

## Project documentation

- `README.md` and `README.zh-CN.md`: aligned English and Chinese entrypoints.
- `docs/CAPABILITY_STATUS.md`: source of truth for usable, partial, and planned areas.
- `ROADMAP.md`: next milestones and explicit non-goals.
- `CHANGELOG.md`: released and unreleased changes.
- `SECURITY.md`: vulnerability reporting and security boundaries.
- `desktop_public/`: public offline Electron shell and Windows installer definition.
- `CONTRIBUTING.md`: contribution workflow.
- `GOVERNANCE.md`: community decision process.
- `BRAND_PUBLIC_BOUNDARY.md`: brand and data publication boundary.
- `FEISHU_BRAND_OPERATING_SYSTEM.md`: sanitized brand operating reference, not a live
  Feishu connector.

## What is intentionally absent

The public repository must not contain private operating-runtime code, credentials,
store/customer/supplier data, browser profiles, identity documents, internal prompts,
raw conversations, or unrestricted external execution connectors.
