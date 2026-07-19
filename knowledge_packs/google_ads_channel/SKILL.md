---
name: google-ads-channel
description: Use when planning, reviewing, researching, or evaluating Google Ads, including Search, Performance Max, Demand Gen, Display, YouTube, Shopping/feed campaigns, Google Ads API, OAuth, conversion tracking, native AI, assets, audiences, budgets, bidding, attribution, experiments, risk, and performance review. Requires official external evidence and owner approval before any account mutation or spend.
---

# Google Ads Channel Expert

Use this Skill for Google Ads only. Keep Google product structure, API identity, conversion ownership, and experiment rules separate from Meta and TikTok.

## Required project sources

Read these before producing platform facts or updating this Skill:

- `config/platform_expert_training/advertising_media_buyer/evidence_index.json`
- `config/platform_expert_training/advertising_media_buyer/rules.json`
- `config/platform_expert_training/advertising_media_buyer/tool_registry.json`
- `config/platform_expert_training/advertising_media_buyer/training_state.json`
- [references/official-evidence.md](references/official-evidence.md)

## Evidence-first workflow

1. Inspect a real authorized Google Ads surface read-only, or official Google Ads Help/Developer pages when authorization is absent.
2. Record URL/version, capture time, country site, business/store mode, ownership, permission, clicks/scrolls, actual input/output, errors, and validity.
3. If no new external evidence exists, report `no_increment`; do not update rules, curriculum, Skill, or evaluations.
4. Confirm tenant/project/store binding, customer ID, optional manager customer ID, OAuth owner, developer token, conversion customer, feed/merchant owner, country, and execution identity.
5. Verify conversion tracking before PMax. Review campaign type, asset/feed ownership, audience/signals, budget, bidding, attribution, experiments, risk, and profit separately.
6. Treat recommendations and AI outputs as proposals. Record what is editable and what requires a live account; do not auto-apply.
7. Produce a draft and explicit blocked/unknown list. No research result is a live campaign.

## Execution boundary

Google Ads API and UI are unconnected. You may research official docs, draft GAQL or mutate requests, build experiments, and run local preflights. Do not claim customer reads, beta eligibility, conversion status, publishing, pausing, budget changes, or spend.

OAuth, 2SV/MFA, developer token, customer IDs, billing, and any live account change belong to the owner. Stop for confirmation at action time.

## T One integration

Reuse the existing LLMClient, `config/multi_ai.json`, Google/independent-commerce expert inputs, and advertising measurement/profit/draft/human-review/stop-loss base. Do not create a second Google gateway or universal advertising Agent.
