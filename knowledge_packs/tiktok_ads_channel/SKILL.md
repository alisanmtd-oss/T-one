---
name: tiktok-ads-channel
description: Use when planning, reviewing, researching, or evaluating TikTok Ads, TikTok One, TTO, or GMV Max, including Ads Manager, Business Center, Pixel/Events API, Shop Ads, creative authorization, creators, native AI, audiences, budgets, bidding, attribution, experiments, risk, and performance review. Keeps media buying, creative supply, and TikTok Shop Ads separate and requires owner confirmation for live actions.
---

# TikTok Ads, TikTok One, TTO, and GMV Max Expert

Keep three surfaces distinct:

- TikTok Ads Manager: media buying.
- TikTok One: creator, partner, content, and AI-assisted creative supply.
- GMV Max/TTO: TikTok Shop Ads optimization and shop-channel measurement.

## Required project sources

Read these before producing platform facts or updating this Skill:

- `config/platform_expert_training/advertising_media_buyer/evidence_index.json`
- `config/platform_expert_training/advertising_media_buyer/rules.json`
- `config/platform_expert_training/advertising_media_buyer/tool_registry.json`
- `config/platform_expert_training/advertising_media_buyer/training_state.json`
- [references/surface-and-evidence.md](references/surface-and-evidence.md)

## Evidence-first workflow

1. Inspect a real authorized TikTok surface read-only, or official public TikTok Business Help/TikTok One pages when authorization is absent.
2. Record URL/version, capture time, region/country site, shop mode, ownership, permission, clicks/scrolls, actual input/output, errors, and validity.
3. If no new external evidence exists, report `no_increment`; do not manufacture a course or rule update.
4. Bind tenant/project/store, Business Center, ad account, seller shop, primary ad account, pixel/events, creator authorization, and execution identity.
5. Classify the task as media buying, creative supply, or shop ads before planning.
6. Separate paid spend/conversions from GMV Max total-channel ROI and organic/affiliate attribution.
7. Produce a draft, measurement reconciliation, approval checklist, and failure-recovery path.

## Execution boundary

TikTok Business API, Ads Manager, TikTok One workspace, and GMV Max account surfaces are unconnected. Public pages verify product concepts, not account eligibility or live inputs. Do not invite creators, pay creators, sync content, publish Spark Ads, change budget/ROI targets, pause campaigns, or spend without explicit owner confirmation.

Never use creator or competitor content without authorization. Do not bypass login, business verification, region restrictions, CAPTCHA, MFA, or platform controls.

## T One integration

Reuse the existing LLMClient, model gateway, TikTok Shop expert evidence, creative_video.py, and advertising measurement/profit/draft/human-review/stop-loss base. Do not duplicate TikTok Shop ownership or create another universal Agent.
