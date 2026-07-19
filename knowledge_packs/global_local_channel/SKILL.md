---
name: global-local-channel
description: Use when researching, admitting, planning, or reviewing a country-specific or regional advertising or commerce channel that is not already covered by a verified T One platform expert, including LinkedIn Ads, Yandex Direct, Rakuten advertising, and other local channels. Requires current first-party evidence, exact country/account routing, explicit unknowns, and owner approval before any live connection, spend, publishing, tracking change, purchase, message, or form submission.
---

# Global and Local Channel Expert

Use this Skill to evaluate one exact channel and country. Do not turn a list of regional platforms into a universal advertising runtime.

## Required project sources

Read these before producing channel facts:

- `config/platform_expert_training/global_local_channel.json`
- `config/advertising_agent.json`
- `config/platform_expert_training/advertising_media_buyer/evidence_index.json`
- `config/platform_expert_training/advertising_media_buyer/rules.json`
- `config/github_capability_registry.json`

## Resolve one executable route

Require tenant, project, store binding, platform, exact country site, commerce mode, ownership, ad/account binding, and execution identity. Treat GLOBAL, EU, Southeast Asia, LATAM, and MENA as research groups only.

## Build evidence before advice

1. Capture a current first-party page or an authorized read-only account receipt.
2. Record owner, URL, version/date, capture time, country sites, account scope, permission, inputs, outputs, measurement definition, price/spend boundary, validity, and content fingerprint.
3. Keep LinkedIn, Yandex, Rakuten, or any other candidate `unknown` until its first-party evidence exists.
4. Keep account availability `blocked_owner_input` until one tenant-scoped read-only receipt exists.
5. Use community cases only as dated hypotheses; never promote a search snippet to evidence.
6. Produce a local draft, evidence gaps, handoff, and approval checklist.

## Reuse the existing runtime

Route verified advertising work through `config/advertising_agent.json`. Reuse the existing LLMClient, measurement, profit, draft, human-review, and stop-loss contracts. Do not create another model gateway, universal ad agent, connector, or scheduler.

## Hard stops

Do not log in, authorize, buy a tool, install an unknown repository, change tracking, upload creative, publish, spend, message, submit a form, or bypass verification without owner approval. Never reuse authorization across countries, accounts, stores, tenants, or execution identities.
