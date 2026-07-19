# Public knowledge packs

T One 0.3 ships a sanitized catalog of 13 public knowledge packs. They are selected through ordinary chat; users do not need to open an extension registry or configure a project before asking a platform question.

The public catalog covers AliExpress, B2B export, eBay, Etsy, global/local channel planning, Google Ads, independent commerce, Lazada, Meta, SHEIN, Shopee, TikTok Ads, and Walmart. The TikTok Shop pack is intentionally excluded from this public release.

Each pack contains:

- aliases used by the local chat router;
- the scope that must be known before platform-specific advice can become executable;
- public planning capabilities;
- safety boundaries for identity, country/site, evidence, approval, privacy, retries, and effect verification;
- research dispositions where a reviewed open-source candidate was not safe or complete enough to become a connector.

The catalog does not include credentials, cookies, browser profiles, store IDs, customer or order data, recovered conversations, screenshots, private product facts, or executable write connectors. `live_connection_claimed` is always `false`, and the public router always returns `external_execution_allowed: false`.

## Example

```python
from ai_ecommerce_director.platform_agents import route_public_chat

result = route_public_chat("这个商品适合速卖通哪些市场？")
assert result["agent_id"] == "aliexpress"
assert result["external_execution_allowed"] is False
```

Multi-platform questions remain comparisons. Unknown country, store mode, ownership, authorization, product facts, and current platform eligibility remain unknown until the caller supplies evidence.
