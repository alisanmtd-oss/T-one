# Public knowledge packs

T One 0.4 ships 17 complete sanitized public knowledge-pack bundles. They are selected through ordinary chat; users do not need to open an extension registry or configure a project before asking a platform question.

The public catalog covers Amazon, AliExpress, B2B export, B2B outbound customer development, B2B marketplace sales, commerce video, eBay, Etsy, global/local channel planning, Google Ads, independent commerce, Lazada, Meta, SHEIN, Shopee, TikTok Ads, and Walmart. The TikTok Shop agent, Skill, training contract, tests and references are intentionally excluded from this public release.

Each directory under `knowledge_packs/` contains the applicable subset of:

- aliases used by the local chat router;
- the scope that must be known before platform-specific advice can become executable;
- public planning capabilities;
- safety boundaries for identity, country/site, evidence, approval, privacy, retries, and effect verification;
- research dispositions where a reviewed open-source candidate was not safe or complete enough to become a connector.
- Skill instructions and agent metadata;
- curated workflows, official-source notes, evidence rules and failure reviews;
- machine contracts, curricula, evaluations, rules, source indexes or capability schemas;
- `PUBLIC_PACK.json`, which lists the public files and the private asset classes deliberately excluded.

`knowledge_packs/MANIFEST.json` is the exact public inventory for all 17 bundles. Two private source Skills are folded into their canonical public packs: the foreign-trade sales foundation is included under `b2b_export/shared-sales`, and the legacy Etsy operator is included under the canonical `etsy` pack. This avoids publishing duplicate routers while preserving their reusable knowledge.

The catalog does not include credentials, cookies, browser profiles, store IDs, customer or order data, recovered conversations, screenshots, private product facts, or executable write connectors. `live_connection_claimed` is always `false`, and the public router always returns `external_execution_allowed: false`.

## Example

```python
from ai_ecommerce_director.platform_agents import route_public_chat

result = route_public_chat("这个商品适合速卖通哪些市场？")
assert result["agent_id"] == "aliexpress"
assert result["external_execution_allowed"] is False
```

Multi-platform questions remain comparisons. Unknown country, store mode, ownership, authorization, product facts, and current platform eligibility remain unknown until the caller supplies evidence.
