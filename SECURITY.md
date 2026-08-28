# Security Policy

## Supported Deployment

T One is currently a local Python library for a trusted Windows workstation. It is not a public SaaS server, a hosted control plane, or a write-capable marketplace agent.

Private desktop applications, browser assistants, browser profiles, store automations, and live connector credentials are not included in this repository.

## Secrets and Private Data

Do not commit passwords, cookies, MFA codes, API keys, OAuth tokens, bank data, identity documents, full warehouse addresses, customer or supplier private data, or browser profiles. Use operating-system credential storage or an external vault and store only a credential reference in project data.

All examples, tests, issues, and pull requests must use synthetic or fully redacted records.

## Connector Boundaries

- Treat browser connectivity as different from an authorized platform API.
- Isolate every executable identity by tenant, workspace, project, task, platform, country/site, store mode, ownership, and store ID.
- Unknown integrations, dependencies, permissions, and data classes fail closed.
- A future write adapter must require scoped authorization, idempotency, limits, approval policy, audit correlation, and verifiable before/after evidence.
- Webhooks must verify timestamp, nonce, event ID, and signature before accepting an event.

## Known Limitations

- External OAuth client registration, signed webhook reception, MCP serving, and store write scopes are not implemented in this public core.
- The included credential backend is intended for a trusted local Windows user. Shared, server, or multi-user deployment requires a workspace-scoped external vault, access policy, and rotation process.

## Reporting

Use [GitHub private vulnerability reporting](https://github.com/alisanmtd-oss/T-one/security/advisories/new) for security or privacy concerns. Do not open a public issue containing secrets, account identifiers, store or customer data, screenshots with private data, or operating evidence.

If private reporting is unavailable, open a minimal public issue asking a maintainer to enable a private channel without including the sensitive details.
