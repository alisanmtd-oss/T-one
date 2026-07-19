# Open Source Readiness

## Current Decision

The private product codebase must not be published as a whole. A fail-closed, exact-file allowlist now builds a sanitized `T One` staging package. Version 0.3 adds ordinary-chat routing and 13 sanitized non-TikTok-Shop knowledge packs. Version 0.3.1 refreshes only the generic browser demo with the accepted chat-first composer and progressively disclosed account settings. TikTok Shop knowledge, the real desktop runtime, accounts, stores, business records, credentials and execution connectors remain private. The owner selected Apache-2.0 for the public core; publication still requires a clean generated audit, tests, privacy verification, and final human review.

## P0 Before Public Release

- Include the owner-selected Apache-2.0 `LICENSE` only in the generated public core; the private product workspace remains private.
- Add a production multi-user credential-vault adapter before supporting shared/server deployment; the current Windows desktop build uses a local DPAPI-encrypted credential store.
- Remove or exclude all recovered conversations, business evidence, customer pipelines, screenshots, outputs, account profiles, warehouse references, browser profiles, and build artifacts.
- Publish only original code or reviewed third-party dependencies. Do not publish local copies of DeepSeek-GUI or other studied repositories as T One source.
- Keep private desktop and connected browser surfaces out of the community-core release. Both PyWebView and the Electron runtime are intentionally absent from the exact-file public allowlist; only a standalone synthetic HTML reference is public.
- Replace local-only absolute paths and generated PyInstaller spec paths with portable build configuration.
- Complete dependency review and a clean-room installation test before the first repository is published. Unit-test CI, public-tree privacy checks, and Dependabot configuration are included in the staging package.

## Already Improved

- Real operating files and recovery archives are excluded in `.gitignore`.
- Machine-specific configs have safe `.example.json` templates.
- Desktop source no longer defaults to a user-specific absolute project path.
- Read-only API payloads omit store IDs and owner profile values.
- Product intake files and per-project operating profiles stay in ignored local runtime paths; the public API returns readiness counts rather than raw product costs or file paths.
- Private desktop, browser-assistant, and browser-extension implementations are excluded from the public allowlist rather than documented as public interfaces.
- `config/public_source_manifest.json` is an exact-file allowlist; anything not named is private by default.
- `scripts/build_public_release.py` copies only allowlisted regular files, rejects path traversal and symlinks, scans the result for private markers and live-secret patterns, and writes SHA-256 plus an audit record.
- The public staging package contains the Python community core plus a dependency-free, synthetic chat-first UX reference. Product-specific marketplace and private-catalog flows, recovered conversations, business evidence, browser extension code and desktop shells remain private.
- Community files now include bilingual repository introductions, architecture, roadmap, governance, contribution rules, support guidance, Issue forms, a pull-request template, Windows test CI, and a public-tree privacy verifier.
- Version 0.3 publishes a package-data catalog for AliExpress, B2B export, eBay, Etsy, global/local channel planning, Google Ads, independent commerce, Lazada, Meta, SHEIN, Shopee, TikTok Ads, and Walmart. The TikTok Shop knowledge pack is explicitly excluded.

## Sanitized Public Source Set

```text
selected ai_ecommerce_director core modules (exact files only)
sanitized ai_ecommerce_director platform agent router and 13 public knowledge packs
selected config/*.example.json files
selected independent tests
public_release_template/README.md
public_release_template/BRAND_PUBLIC_BOUNDARY.md
public_release_template/FEISHU_BRAND_OPERATING_SYSTEM.md
public_release_template/demo/chat-first-workspace.html
public_release_template/community and GitHub templates
public_release_template/LICENSE and Python package metadata
SECURITY.md
requirements*.txt
```

Build a private staging directory with:

```powershell
python scripts/build_public_release.py --output D:\TOnePublicRelease\T-one --strict-license
```

The audit must say `ready_for_final_review`. Never use `git add .` in the private project; publish only the generated staging directory after reviewing its complete file list.
