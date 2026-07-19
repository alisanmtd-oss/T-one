# Evidence and learning protocol

## Non-negotiable evidence gate

Each cycle must first capture a newly visible external page or software state. The evidence record must include the actual URL/product version, capture time, site, store mode, ownership, execution identity, operations performed, visible input/output, errors and permissions. A cycle with no new evidence may update a blocked-status note, but it may not promote rules, curriculum, Skill guidance or eval expectations.

Use these state labels consistently: `verified_live_fact`, `time_sensitive_evidence`, `historical_operator_trace`, `draft`, `failed_attempt`, `unknown`, `blocked_owner_input`.

Current authentication must be proven in the same live round. Historical authenticated state expires at the next login, cookie or MFA surface. Do not automate authentication challenges.

## Required source fields

Every source must record `source_id`, `source_type`, `modality`, `authority_tier`, `location`, `captured_at`, `rights_status`, `raw_reuse_allowed`, `commercial_use_allowed`, `marketplace`, `country_site`, `store_scope`, and `update_frequency`.

Every derived claim must record:

- claim text and claim type: fact, observation, inference, rule, recommendation or draft;
- source and exact evidence span, frame timestamp or screenshot region;
- capture time and, for policies, effective time;
- store/site/product identity;
- confidence, contradiction status and expiry/recheck rule;
- allowed use and actions requiring confirmation.

## Recipes

### Text and documents

Extract headings and evidence spans before summarizing. Split policy requirements from educational suggestions and seller anecdotes. Hash the captured body. Keep large originals outside model context and retrieve only relevant chunks.

### Images and screenshots

Keep the original hash. OCR visible text, identify page/site/store, and attach bounding boxes or a concise region description. Label icons, colors and layout as observations. Do not infer a saved value, hidden selector state or publication state from one frame.

### Video

Confirm that viewing or processing is permitted. Capture metadata and transcript, then sample frames at scene changes and referenced timestamps. Distinguish what the presenter says, what the interface visibly demonstrates, and what later store data verifies. A revenue claim without independent evidence remains an anecdote.

### Software traces

Use the phases `resume`, `navigate`, `observe`, `analyze`, `draft`, `submit`, `verify`, `block`. A successful click or HTTP response is not final proof. Reload or re-query the authoritative surface and record the persisted result.

## Promotion rules

- Official current rule or verified live store fact may become an active rule/fact.
- Historical store facts remain time-bounded evidence.
- Repeated third-party observations may become a hypothesis, not a platform rule.
- Drafts and presets may become templates, not current state.
- Contradictory evidence is quarantined until the newer authoritative source is verified.
- Generate eval cases before promoting high-impact knowledge to long-term memory or a reusable Skill.

## Privacy and rights

Never store passwords, cookies, tokens, MFA values, bank data, identity documents, customer PII or full licensed course/video copies in training records. Store only authorized originals and compliant derived facts, patterns, checks and citations.
