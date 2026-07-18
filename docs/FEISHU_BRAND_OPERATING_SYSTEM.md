# T One Brand Operating System

This document is a sanitized, compliance-first distillation of owner-supplied operating material originally organized in Feishu. It is not a copy of the private course, internal chat, account record, or marketplace evidence.

## 1. Source and truth policy

Every fact used by an agent has one of three sources:

1. **Owner-confirmed facts**: product identity, SKU and variants, cost source or cost rule, intended price or pricing rule, approved product media, and rights constraints.
2. **Connector facts**: store identity, site, currency, orders, inventory, settlement, advertising account, delivery promise, and platform status read from an authorized system.
3. **AI drafts**: positioning, copy, keywords, visual concepts, storyboards, prompts, outreach drafts, and forecasts. Drafts must never be presented as operating facts.

The initial product intake should stay short. It should accept a product table, ERP reference, DAM folder, or image bundle instead of asking the operator to retype every field. Company, currency, payment, advertising, and marketplace identity should be read from the relevant authorized account when possible.

## 2. Brand decision record

Before public content or a campaign is launched, the project keeps one versioned decision record:

- audience and buying situation;
- customer problem and desired outcome;
- product proof and permitted claims;
- value proposition and differentiation;
- price architecture and bundle logic;
- voice, visual direction, and prohibited expressions;
- channel, country/site, store model, and ownership;
- asset rights, music rights, talent consent, and marketplace restrictions.

AI may propose missing strategy fields, but the system labels them as drafts and records the evidence used.

## 3. Operating layers

The public architecture uses this hierarchy:

```text
workspace
  -> project
    -> channel (platform + country/site)
      -> store (store model + ownership + isolated authorization)
        -> store task
    -> project workstream (B2B, creative, research, finance, or supply chain)
```

One platform can contain many stores. Stores never share an executable authorization implicitly. A regional label may group reporting, but execution always resolves to a concrete country/site and store identity.

## 4. Commerce and content loop

The operating loop connects brand work to measurable commerce work:

1. Observe market, search demand, competitor listings, reviews, and public creative patterns.
2. Select a product hypothesis and record the expected customer, site, price band, proof, and risk.
3. Build or improve the listing: title, variant structure, product images, offer, delivery promise, and compliance.
4. Produce creative variants from explicit hooks, scenes, proof, CTA, aspect ratio, duration, and rights metadata.
5. Test with controlled budgets or organic distribution according to platform rules.
6. Read real impressions, clicks, conversion, contribution margin, returns, comments, and fulfillment outcomes.
7. Keep, revise, pause, or stop based on evidence. Preserve the decision and its source for later agent learning.

## 5. Visual and video intelligence

Competitor analysis describes structure without copying protected expression. A reusable analysis record contains:

- first-three-second hook;
- audience tension or desire;
- shot list, framing, motion, pacing, text, sound, and CTA;
- product proof and trust device;
- platform-native interaction pattern;
- observed performance evidence and collection time;
- elements that may be reused as an abstract pattern;
- elements blocked by copyright, trademark, likeness, music, or platform policy.

The generation pipeline produces a storyboard, image/video prompts, continuity constraints, edit plan, caption, thumbnail direction, and several testable variants. Results feed the next iteration; a visually similar output is not treated as a valid result unless rights and performance are both acceptable.

## 6. Roles, permissions, and scale

- Owners control projects, credential policy, budget ceilings, publication rights, and member administration.
- Project administrators can create scoped stores, tasks, and subaccounts only within assigned projects.
- Store operators see only assigned store identities and tasks.
- Creative, B2B, finance, customer service, and supply-chain roles receive only the data and actions required for their work.
- High-impact actions such as publishing, advertising spend, payment, refunds, shipment confirmation, external messaging, identity verification, and credential changes require explicit policy, audit, and approval boundaries.

At scale, queues, rate limits, idempotency keys, per-store credentials, retries, evidence timestamps, and failure isolation are mandatory. A failed store task must not block or contaminate another store.

## 7. Public boundary

The open-source package does not include private Feishu pages, recovered conversations, addresses, contacts, store identifiers, product campaigns, customer leads, browser profiles, credentials, or raw operating evidence. Numeric benchmarks from private courses are not promoted as universal rules; they require current platform evidence before use.
