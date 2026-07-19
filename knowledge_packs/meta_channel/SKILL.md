---
name: meta-channel
description: Use when planning, reviewing, researching, or evaluating Meta Ads for Facebook or Instagram, including Marketing API, Advantage+, Pixel/CAPI, catalogs, audiences, creatives, budgets, bidding, attribution, experiments, risk controls, and performance review. Requires external visible evidence before knowledge updates and never executes live spend or publishing without owner confirmation.
---

# Meta Ads Channel Expert

Use this Skill for Meta Ads only. Do not import TikTok or Google product rules into Meta merely because measurement or profit fields look similar.

## Required project sources

Read these before producing platform facts or updating this Skill:

- `config/platform_expert_training/advertising_media_buyer/evidence_index.json`
- `config/platform_expert_training/advertising_media_buyer/rules.json`
- `config/platform_expert_training/advertising_media_buyer/tool_registry.json`
- `config/platform_expert_training/advertising_media_buyer/training_state.json`
- [references/official-evidence.md](references/official-evidence.md)

## Evidence-first workflow

1. Inspect a real authorized Meta surface read-only, or an official public Meta Business/Developer/Help page when no authorization exists.
2. Record URL/version, capture time, country site, store mode, ownership, permission, clicks/scrolls, actual input/output, errors, and validity.
3. Classify each claim with the project knowledge-state taxonomy. If no new external evidence exists, report `no_increment` and do not rewrite training assets.
4. Confirm the route has tenant, project, store binding, platform, country site, mode, ownership, and execution identity.
5. Review account hierarchy, Pixel/CAPI/events, catalog, audience, creative rights, budget, bid, attribution, experiments, risk, and profit separately.
6. Produce a draft and explicit unknown/blocked fields. Research or a passing test is not business completion.

## Execution boundary

Meta Marketing API and Ads Manager are unconnected in the current T One baseline. You may research official schemas, prepare request examples, design experiments, and run local safety preflights. Do not claim account reads, API execution, connected OAuth, Advantage+ eligibility, publishing, pausing, deletion, or spend.

Before any live budget, launch, pause, creative publish, or account change, stop for owner confirmation at action time.

## T One integration

Reuse the existing LLMClient, `config/multi_ai.json`, advertising measurement/profit/draft/human-review/stop-loss base, and expert registry. Do not create another model gateway or universal advertising Agent. Shared-core changes are recommendations only.
