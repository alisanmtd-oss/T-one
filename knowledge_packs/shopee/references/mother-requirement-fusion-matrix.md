# Cross-border mother requirements → T One fusion matrix

Source: `pasted-text.txt`, fully read on 2026-07-18. It is a candidate requirements list, not an authority for platform facts or software connection state. Allowed decisions are exactly `reuse_existing`, `extend_existing`, `research_only`, `blocked_connector`, and `rejected_unsafe`.

## T One baseline that Shopee must inherit

| ID | Mother/baseline requirement | Existing capability | Gap | Decision | Minimum fusion path |
|---|---|---|---|---|---|
| B01 | T-One desktop, T1 mark, one-store long-running chat, project/platform/multi-store hierarchy, task isolation | C1 is completed and manually accepted in `T-One-0.1.0`. | Shopee expert is not yet in the shared registry/UI route. | `reuse_existing` | Add one shared registry/router recommendation under C4; do not rebuild desktop or conversations. |
| B02 | Unified AI foundation | One `LLMClient + config/multi_ai.json`, nine ready models, persisted selection, DPAPI credentials, real connection tests/errors/calls. | Shopee-specific prompts and evidence routing only. | `reuse_existing` | Invoke existing model slots through the same gateway; never create another gateway or万能 Agent. |
| B03 | Expert/extension foundation | Shared expert registry and Skill/plugin/model/connector entry points exist; Etsy proves the pattern. | Shopee registry entry and invocation/usability tests are pending. | `extend_existing` | Reuse the Etsy-style contract/Skill/router pattern and submit shared integration recommendations only. |
| B05 | Platform/ERP schema foundation | Dynamic product schema, adapter/evidence registries, approval and task routing exist. | Shopee OAuth/API/Ads/ERP/PTD/store mappings are absent. | `blocked_connector` | Extend existing adapters and schemas after real authorization; display blocked states meanwhile. |
| B07 | B2B customer pool and gates | private customer records and shared timeline; external results remain zero. | Outside Shopee marketplace execution. | `research_only` | Reuse only generic approval/audit patterns if a future Shopee B2B flow is explicitly scoped. |
| B08 | Unified advertising measurement | Profit, draft, review, stop-loss and channel separation exist; external Ads OAuth is absent; TikTok One is supply-side. | Shopee Ads identity/eligibility/balance and attribution are absent. | `extend_existing` | Reuse measurement/approval schema; add a separate Shopee on-platform Ads identity connector when authorized. |
| B09 | Visual/video foundation | `creative_video.py`, storyboard/prompt/variant rules, CapCut/FFmpeg detection exist. | Shopee-native AI and outcome writeback are not integrated. | `extend_existing` | Feed rights-cleared assets into drafts; use native-AI site evidence and require manual approval/writeback. |
| B10 | GitHub admission gate | `config/github_capability_registry.json` controls admission; named repos remain blocked or unverified. | No admitted Shopee connector was found. | `research_only` | Check registry and current scans before any repository evaluation; never install from the mother list. |

## Mother architecture and training requirements

| ID | Candidate requirement | Existing capability | Gap | Decision | Minimum fusion path |
|---|---|---|---|---|---|
| M01 | Modular platform/independent-site/channel experts | Shared registry, Skills, routing and platform adapters exist. | Mother combines Shopee+Lazada and uses regional execution labels. | `extend_existing` | Keep a Shopee-only Skill and eight site routes; use regions only for reporting and reuse shared services. |
| M02 | Separate platform-native Ads from external media Ads | Existing ad schema already separates platform and off-platform measurement. | Shopee Ads connector is absent. | `reuse_existing` | Preserve the split in every draft and route; add only Shopee-specific identity/fields. |
| M03 | Panel switching and compact expert entry | C1 panel and registry foundation exist. | Shopee entry and save/invoke/error/result loop are pending. | `extend_existing` | Register this existing Skill in C4; do not import a giant prompt or duplicate panel. |
| M04 | Every expert “masters every tool” automatically | No evidence that named third-party products are licensed, current, connected, or legally usable. | Product existence, terms, country coverage, APIs/exports, permissions, and data quality are unknown. | `research_only` | Evaluate one tool at a time from official product docs and a licensed account; keep `research_only` until verified. |
| M05 | Daily official/community/video/GitHub learning and durable memory | Authoritative memory, evidence registries, test/report pattern and automation facility exist. | Shopee incremental cursor, dedupe and expiry loop are new. | `extend_existing` | Run official-evidence-first automation; community experience remains hypotheses; update only changed evidence. |
| M06 | “Permanent/immutable” knowledge and rules | Versioned files and authority hierarchy exist. | Permanent lock conflicts with correction, expiry, and current official policy. | `rejected_unsafe` | Keep provenance, status, validity and supersession; allow authoritative corrections. |
| M07 | Do not disturb mature software | Shared core/queue/memory are occupied and read-only for this task. | Shopee integration still needs later shared changes. | `reuse_existing` | Limit this task to Shopee-owned assets/tests/report and provide integration recommendations. |

## Sources and collection

| ID | Candidate requirement | Existing capability | Gap | Decision | Minimum fusion path |
|---|---|---|---|---|---|
| S01 | Official Seller/Help/Developer/Ads sources first | Browser/web research and evidence schema are available. | Site-by-site capture remains incomplete. | `extend_existing` | Each round first opens public official or authorized pages, records interactions, then distills. |
| S02 | Domestic/overseas forums and communities | Public research can be performed case by case. | Provenance, consent, access, sample bias and currentness vary. | `research_only` | Convert experience to an experiment hypothesis; never override official/current store evidence. |
| S03 | “Automatically bypass anti-scraping” | None, by design. | Violates platform controls and user safety boundary. | `rejected_unsafe` | Respect robots/access controls, CAPTCHA, rate limits, paywalls and login boundaries; use official/public or authorized data. |
| S04 | Three sellers can make a rule “standard” | No trustworthy mechanism makes anecdotal consensus authoritative. | Sampling and site/store differences remain. | `research_only` | Use multiple reports only to prioritize a store-scoped experiment; official policy remains authoritative. |
| S05 | Timed GitHub learning, including automation/ERP/crawlers/anti-linkage | Admission registry exists. | Named repos/licenses/security/integration are unverified. | `research_only` | Read the capability registry first; reject linkage evasion and install nothing without approval. |
| S06 | Download/transcribe all videos | Visual/video detection and prompt pipeline exist, but rights and source access vary. | No Shopee-specific licensed ingestion/ASR loop is connected. | `research_only` | Process user-owned/licensed or officially accessible media only; store provenance and rights. |
| S07 | Payment, tax, customs and FX “real-time” automation | Generic profit fields exist. | No authoritative Shopee site tax/customs/FX feeds are connected. | `blocked_connector` | Use dated owner-provided/official inputs; require legal/financial review and connector approval. |

## Shopee tools and competitor research

| ID | Candidate requirement | Existing capability | Gap | Decision | Minimum fusion path |
|---|---|---|---|---|---|
| T01 | SellerSprite, Shopee Spy, Ecomhunt SEA and Lazada plug-ins | Names are recorded only as candidates. | License, current product, country coverage, API/export, privacy and Shopee terms are unknown. | `research_only` | Evaluate individually; do not claim mastery or connection from the name. |
| T02 | Full competitor-store extraction, cadence, prices and activity strategy | Public manual research and structured audit drafts are possible. | Bulk extraction authority and data completeness are absent. | `research_only` | Use permitted public facts/exports and sampling; label inference and never bypass controls. |
| T03 | Copy an entire competitor strategy/products | No legitimate right or reliable causal proof. | IP, data rights and misleading certainty risks. | `rejected_unsafe` | Extract patterns/hypotheses only; create original, rights-cleared listings and experiments. |
| T04 | Download reviews, buyer images/video and directly reuse them in ads | Explicitly prohibited by current safety and rights policy. | No licenses/permissions. | `rejected_unsafe` | Use owner-created, licensed or platform-authorized assets with provenance. |
| T05 | Advanced crawler used across all modules | No authorized crawler is connected. | Platform terms, privacy, rate limits and permissions are unknown. | `blocked_connector` | Prefer official APIs/exports; any crawler needs legal review, scoped authorization and rate/control compliance. |
| T06 | Cross-validate multiple tools | Evidence comparison schema exists. | Inputs are unavailable while tools are unconnected. | `extend_existing` | Preserve independent source IDs and conflicts; run only after permitted data is obtained. |

## Shopee operating coverage

| ID | Candidate requirement | Existing capability | Gap | Decision | Minimum fusion path |
|---|---|---|---|---|---|
| O01 | Shopee+Lazada “Southeast Asia expert” | Shared platform adapter pattern exists. | Combining platforms/region would erase authorization and rule boundaries. | `rejected_unsafe` | Keep independent Shopee expert and site routes; share only generic services and reporting groups. |
| O02 | Cross-border/local/brand stores across SEA and Latin America | Shopee route contract covers SG/MY/TH/VN/PH/ID/TW/BR and seller origin. | Real store model/program/ownership per site is unknown. | `extend_existing` | Read each authorization/onboarding result; record `marketplace_seller + seller_origin + account_program + ownership`. |
| O03 | “SLS logistics” as a general Shopee/Lazada capability | No current official site/store evidence in this round. | Label may be platform/program/site-specific and must not be generalized. | `research_only` | Verify exact official terminology and site/store availability before adding a fulfillment value. |
| O04 | Listing, ads, campaigns, orders, logistics, aftersales and settlement | Existing generic schemas and Shopee course/workflow cover these domains. | All Shopee execution/data connectors are absent. | `blocked_connector` | Produce evidence-grounded drafts now; unlock each domain with separate store/site permission and tested reads. |
| O05 | Platform-native AI | TW public seller education now documents AI product-image/try-on flows; AI terms exist for SG/MY/PH/TW. | Real-store feature visibility, credentials, outputs and performance are unavailable. | `extend_existing` | Add site-scoped native-AI catalog and evals; keep live use `blocked_owner_input` until a store is authorized. |

## Distillation, scheduling and panel commands

| ID | Candidate requirement | Existing capability | Gap | Decision | Minimum fusion path |
|---|---|---|---|---|---|
| D01 | Clean/distill/expire conflicting knowledge | Evidence states, official precedence and regression tests exist. | Shopee status taxonomy/cursor/failure review needed. | `extend_existing` | Use seven statuses, content hashes, validity/recheck triggers, conflict retention and tests. |
| D02 | Daily/weekly/monthly background learning and Self-Instruct at scale | Codex recurring automation exists. | Mass synthetic Q&A can amplify unsupported claims and duplicate runs. | `extend_existing` | One deduplicated Shopee automation, official external evidence first, capped incremental work; no synthetic fact promotion. |
| D03 | One-click global update | Shared scheduler is outside this expert and not authorized. | Cross-expert orchestration would modify others. | `research_only` | Keep one Shopee-only automation; propose global scheduling separately to the owner. |
| D04 | Switch expert / retrieve compact knowledge | Shared registry/Skill UI pattern exists. | Shopee shared registration pending. | `extend_existing` | Register the compact Skill and load references progressively; no giant mother prompt. |
| D05 | Parse a video link and learn | Generic visual/video foundation exists. | Rights, download permission, ASR and Shopee classifier are not closed-loop. | `research_only` | Only process authorized media and label claims as hypotheses until official/store verification. |
| D06 | Competitor research command autonomously picks tools | Routing can choose tools by declared state. | Most candidates are unconnected. | `extend_existing` | Choose only `connected_*` or permitted public research; otherwise return the blocked connector and owner input. |
| D07 | “Only internal distilled knowledge; no model common sense” | Evidence-backed answer contract exists. | Absolute ban is neither enforceable nor desirable; it can hide uncertainty. | `rejected_unsafe` | Require evidence for platform facts, label inference, and expose unknowns; use the LLM only through the existing gateway. |
| D08 | “Never chat; business only” | Expert can stay concise and task-focused. | Absolute conversational ban harms clarification and approvals. | `research_only` | Keep responses operational, but ask for the minimum owner input when execution scope or safety requires it. |

## Result

The minimum fusion path is one Shopee Skill and machine contract on top of the existing T One gateway/router/schema/approval foundations. It adds site-scoped evidence, native-AI/tool catalogs, evaluations, and one deduplicated training automation. It does not create a second model gateway, universal Agent, shared platform crawler, or cross-expert scheduler.

> Private runtime paths, evidence, execution identities, and product records are intentionally excluded from this public pack.
