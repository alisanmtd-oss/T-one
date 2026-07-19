# TikTok surface and official-evidence routing

Use the canonical records in `config/platform_expert_training/advertising_media_buyer/evidence_index.json`.

## Surface boundary

| Surface | Verified purpose | Do not claim |
|---|---|---|
| TikTok Ads Manager | Media buying and account reporting | Connected access, launch, spend, or pause |
| TikTok One | Creators, partners, content supply, AI tools, dubbing, translation | A media objective, unrestricted creator usage, or workspace access |
| Product GMV Max / TTO | TikTok Shop Ads total-channel ROI optimization | Pure paid incrementality or external-site measurement |

## Current official evidence observed on 2026-07-18

- `TIKTOK-001` and `TIKTOK-002`: Product GMV Max page, updated July 2026, including total-channel ROI and organic/affiliate order attribution.
- `TIKTOK-003`: creator collaboration page, updated April 2026, requiring authorization before Ads Manager sync and limiting creator visibility by region.
- `TIKTOK-004`: TikTok One advertiser page, updated June 2026, advertising AI tools, AI dubbing, and translation; actual workspace fields remain unknown.
- `TIKTOK-005`: public product page was readable, but Get started reached a login boundary.
- `TIKTOK-006`: Web Conversions uses Pixel/Events API with deduplication guidance.

## Review requirements

- Record country site and shop mode; global help content does not prove local availability.
- Reconcile paid spend, paid conversions, total GMV, organic orders, and affiliate orders.
- Preserve creator authorization, commercial disclosure, and content ownership evidence.
