# Meta Ads official-evidence routing

Use the canonical evidence records in `config/platform_expert_training/advertising_media_buyer/evidence_index.json`; do not copy claims here as timeless truth.

## Current public surfaces observed on 2026-07-18

- `META-001`: the Meta Business Advantage+ URL redirected the unauthenticated browser to login. Account controls remain blocked.
- `META-002`: the public Meta Developer home exposed a current Marketing API v25.0 banner.
- `META-003`: the canonical Marketing API page exposed campaign/ad set/creative management, optimization, Conversions API, Catalog API, Business Management API, and Ads Manager links.
- `META-004`: the official CAPI help page recommends pairing Pixel and CAPI for website measurement and does not permit privacy circumvention.
- `META-005`: live account fields, feature eligibility, event state, budget, and publishing remain owner-blocked.

## Current Parameter Builder evidence observed on 2026-07-19


- `META-006`: Meta's current Parameter Builder pages were updated June 30, 2026. Client-side calls may write first-party cookies and require cookie consent before use; server-side SDKs return recommended cookies but do not set browser cookies themselves.
- `META-007`: Meta's official Get Started page directly identifies `facebook/capi-param-builder`. The repository was pinned at `5d024d077dd8ef61185c6d2cfe8e698f4941c88a`; it has tags but no GitHub Releases and uses the Facebook Platform-specific license.
- `META-008`: `capi-param-builder-nodejs` is currently `1.3.1`. Its standalone Node API has no Python-style `Preference`; `processRequestFromContext` extracts request context before callers choose getters. T One must enforce consent and route policy before invocation, trust proxy and canonical-domain boundaries, URL/query redaction, and an output-field allowlist.
- `META-009`: the Node npm package lacks `gitHead` and attestation metadata, while the corresponding publish workflow recently failed. It remains `research_only` and uninstalled; a registry package or passing CI is not a verified T One connector.

## Decision checklist

- Identify conversion destination and owner.
- Verify Meta business, ad account, app/token, catalog, pixel/event, and store/site binding separately.
- Do not infer Advantage+ account options from public marketing pages.
- Treat Ads Library as public creative research; hidden audience, profit, spend, and ROAS remain unknown.
- Preserve creative licensing and consent evidence.
- Keep Python Business SDK `Preference` rules separate from the standalone Node Parameter Builder. Never claim a library-level Node field allowlist that does not exist.
- Do not pass raw HTTP requests, headers, cookies, referrers, or URLs through the task payload. Build approved derived fields inside the tenant-scoped backend after trusted-proxy, canonical-domain, consent, and query-redaction checks.
- Treat repository commit, tag, registry version, integrity, provenance, license, CI, and security state as separate gates. Missing provenance or a failed publish chain keeps the package `research_only`.

> Private runtime paths, evidence, execution identities, and product records are intentionally excluded from this public pack.
