# 跨境母体需求到 Lazada/T One 的融合矩阵

来源：用户提供的 `pasted-text.txt`。本文件把它当作候选需求清单，不当作官方规则或已实现能力。

完整逐项机器矩阵见 [mother-requirements-matrix.json](mother-requirements-matrix.json)。每一行均包含：母体需求、T One 现有能力、真实缺口、最小融合路径、课程映射和下列唯一状态之一：

- `reuse_existing`：共享底座已经存在，只引用，不重复开发。
- `extend_existing`：在 Lazada 独立资产上增加证据、课程、规则或评测。
- `research_only`：只能做公开/授权研究或实验假设，不能成为执行事实。
- `blocked_connector`：缺少真实账号、OAuth、许可证、成功调用或数据权利。
- `rejected_unsafe`：涉及绕过、串权、无授权素材、批量私有抓取、虚假永久保证或巨型万能 Agent。

## 当前融合结论

| 需求域 | 现有能力 | 缺口 | 最小融合路径 | 主状态 |
|---|---|---|---|---|
| C1/正式 App/项目-平台-多店层级 | 已完成 | 无 Lazada 真实店铺绑定 | 复用 C1，接店后增加逐国 binding | `reuse_existing` |
| 唯一模型网关 | `LLMClient + multi_ai.json`、模型与凭据链已完成 | 不提供 Lazada OAuth | 只使用现有模型槽 | `reuse_existing` |
| 专家/Skill/连接器底座 | 注册表、适配器、活动门禁已存在 | Lazada 独立课程/证据/复盘需持续补齐 | 扩展本目录和训练契约 | `extend_existing` |
| SG/MY/TH/VN/PH/ID 与六合一 | 六站路由和逐国 identity 规则已有 | 无真实 seller_id/short_code | 官方授权证据 + 逐国绑定 | `extend_existing` / `blocked_connector` |
| Marketplace Ease 半托管 | 本轮取得官方公开页面证据 | 共享路由未注册，国家/资格未知 | 作为不可执行候选，提交共享评审建议 | `extend_existing` |
| Choice/JIT/VMI | 有独立授权/库存页面证据 | 店铺模式与 full-managed 映射未证实 | 保持项目/库存模型，不进入可执行模式 | `research_only` |
| Listing/订单/仓配/售后/结算 | 通用适配与审批门已有，官方 API 目录可见 | 无 OAuth、订单、仓库、逆向订单、财务样本 | 先读连接，后逐对象验证；写操作人审 | `blocked_connector` |
| Sponsored Solutions 与平台 AI | 统一广告测量/止损底座已有；官方 AI Diagnosis/NPL 可见 | 无逐国广告身份、钱包；Open Platform AI 登录受限 | 复用广告底座，新增逐国资格/AI 证据 | `extend_existing` / `blocked_connector` |
| 第三方 Lazada 工具 | 仅有候选名称 | 许可证、授权、成功读取均未知 | 准入审查 + owner 授权 + 只读探针后再接 | `blocked_connector` |
| 自动持续训练 | Codex 自动化与目标模式可用 | 需防重复、只处理增量 | 单一每日 Lazada 任务 + 证据门 + 无增量游标 | `extend_existing` |
| 自动反爬/关联规避/素材复用 | 无，也不允许 | 与安全/权利边界冲突 | 不实现 | `rejected_unsafe` |
| 巨型母提示词/第二万能 Agent | 模块化 Skill 与统一运行时已足够 | 会混入过时和串权知识 | 保持 Skill + 契约 + references | `rejected_unsafe` |

## 需要共享核心的建议（未修改共享文件）

1. 在平台模式证据注册表评审 `marketplace_ease_semi_managed`：官方定义已见，但要补国家可用性、准入、授权响应与 ownership 后再决定 route 轴。
2. 正式 App 的专家详情页以后读取本专家的课程覆盖、连接状态、证据过期和失败复盘；不要增加新的运行时或模型网关。
3. 连接器接入顺序固定为：一个具体国家店铺/跨境账户 → OAuth/逐国 seller identity → 只读类目/商品/订单 → webhook → 仓配/售后/财务 → Sponsored Solutions 独立身份。
