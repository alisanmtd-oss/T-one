# Capability status

This file is the public truth table for T One Community Core.

## Status definitions

- `verified`: implemented and exercised by public tests or the synthetic public demo.
- `requires_setup`: implementation exists but needs operator-owned credentials, an
  approved account, or a compatible local environment.
- `partial`: a useful foundation exists, but the end-to-end workflow is incomplete.
- `planned`: schema, research, or design only.
- `private_product`: exists outside the public repository and is not a public claim.

## Current public status

| Area | Status | Notes |
| --- | --- | --- |
| Python domain core | `verified` | Dependency-light package and public tests |
| Project/store/task isolation | `verified` | Synthetic fixtures only |
| Knowledge-pack catalog | `verified` | Sanitized packs; no private TikTok Shop pack |
| Approval/evidence contracts | `verified` | Local contracts, no automatic external writes |
| Browser reference UI | `verified` | Synthetic data; demo-only |
| Windows community installer | `verified` | Installable shell for the same offline synthetic demo |
| Chinese capability market | `verified` | Agent/Skill local demo assignment; MCP/CLI visibly unconfigured or undetected |
| Model/provider configuration | `partial` | Credentials are never shipped |
| Local MCP/API surface | `partial` | Scoped read/draft surface, not a universal runtime |
| Marketplace/ERP reads | `requires_setup` | No public live account |
| Marketplace/ERP writes | `planned` | Human approval remains mandatory |
| Advertising execution | `planned` | No public ad account or budget authorization |
| Messaging/email/social connectors | `planned` | No public OAuth sessions |
| Payments/settlement/banking | `planned` | Financial contracts only |
| Full Windows operating runtime | `private_product` | Computer control and commercial connectors are not distributed here |

## Verification rule

A capability is not `verified` merely because a page, button, schema, test fixture,
research report, or connector name exists. Verification requires an implementation,
the appropriate automated tests, understandable failure feedback, and the correct
runtime or synthetic demo evidence.

中文说明：公开能力市场中的“已包含”只代表代码和离线示例随安装包提供；
“未配置”与“未检测”不能理解为已经安装、登录或连接第三方服务。
