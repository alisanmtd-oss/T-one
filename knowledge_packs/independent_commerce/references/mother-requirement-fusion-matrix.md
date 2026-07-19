# 母体需求 → T One 能力 → 缺口 → 最小融合路径

来源：`pasted-text.txt`，已于 2026-07-18 完整读取。它是跨境母体需求清单，不是官方权威或可直接部署证明。

状态只允许：`reuse_existing / extend_existing / research_only / blocked_connector / rejected_unsafe`。完整机器矩阵见 `../state/mother_requirement_matrix.json`。

| 范围 | 母体需求 | T One 现有能力 | 真实缺口 | 状态 | 最小融合路径 |
|---|---|---|---|---|---|
| 架构 | 独立站统一大类，含 DTC/POD/代发/数字服务/OTA | 已有共享工作流和六类垂直扩展 | 不同履约、税务、退款、容量不能只做“微调” | `extend_existing` | 单一专家入口 + 按订单行选择垂直扩展 |
| 广告 | 站内广告与独立站站外广告分离 | 统一广告 Agent 已有测量、利润、草稿、人审和止损 | Meta/TikTok/Google 无真实 OAuth；TikTok One 非投放目标 | `reuse_existing` | 仅做带广告账户身份的渠道 handoff |
| 专家 | 面板模块化切换 | C1 App 与专家注册底座存在 | Adobe/Salla/Zid 未进共享注册表 | `extend_existing` | 先在专家契约补 adapter，主任务再集成共享注册表 |
| 模型 | 全工具/全模型直接部署 | 唯一 LLMClient + multi_ai.json 与 9 个模型已验证 | 工具名称、模型名称不代表业务连接 | `reuse_existing` | 复用网关，逐连接器 capability probe |
| 学习 | 每日/每周/月度自训练 | 证据与自动化底座存在 | 独立站无水位线、失败日志和同名自动化 | `extend_existing` | 单一增量任务，只处理水位线之后的证据 |
| 公开研究 | 论坛、社群、媒体、视频 | 可做合法公开研究 | 无全站 API/订阅/转写授权 | `research_only` | 卖家经验只做带日期实验假设 |
| 采集 | 自动绕过反爬/验证码/MFA | 受控浏览器可做合法访问 | 绕过平台限制被禁止 | `rejected_unsafe` | 官方 API、允许页面、授权会话；遇限制停止 |
| 官方资料 | 平台、广告、支付、税务、海关优先 | 已有 Shopify/Woo/BigCommerce/广告证据 | Adobe/Salla/Zid 和国家规则未全覆盖 | `extend_existing` | 每条保存 URL、日期、国家、模式、ownership、有效期 |
| 卖家经验 | 多人共识升级为标准 | 已有实验假设分类 | 人数不能替代官方或实店证据 | `research_only` | 只提高实验优先级，不升级为 live fact |
| GitHub | 自动学习并集成仓库 | github_capability_registry 已准入控制 | 未知/许可证/安全未审查即阻断 | `reuse_existing` | 只按 registry decision 引用，不自动安装 |
| 视频 | 下载、降噪、转写、入库 | creative_video.py、CapCut/FFmpeg 探测存在 | 下载权利、转写、语种、效果回写未闭环 | `blocked_connector` | 先处理有权使用的本地文件，隔离试点转写 |
| 技术侦测 | BuiltWith 等技术识别 | 候选工具已登记 | 无订阅/API/精度验证 | `research_only` | 逐工具探测；估算不当实店事实 |
| 选品 | Ecomhunt/PPSpy 等爆品数据 | 研究报告底座存在 | 工具未连接，“实时全网”不可证 | `research_only` | 有界样本、时间窗、偏差和交叉验证 |
| SEO | Similarweb/Semrush/Ahrefs | SEO/GEO/AEO 模型槽位存在 | 付费数据源未连接 | `research_only` | 公开/官方数据先行，第三方只报估算 |
| 广告侦察 | 恢复竞品受众/预算/转化 | 广告 Agent 可接收研究 brief | 公开资料库不提供完整真实投放数据 | `research_only` | 只分析可见素材/落地页，未知项明确标记 |
| POD | Printful/Printify 自动连接 | POD 数据合同已定义 | 无供应商账户、App/API、实时价/库存/产能 | `blocked_connector` | 先做店铺+供应商双授权、读探针和 SKU 映射 |
| OTA | 自动识别库存、价格和 booking | OTA 履约扩展已定义 | 无 provider connector、合同、许可、支付 | `blocked_connector` | 无读探针时禁止确认库存或预订 |
| 竞品 | 全赛道全店批量抓取 | 公开研究可做有界采样 | “全部”不可验证，易越权 | `rejected_unsafe` | 合法样本、速率限制、缺失范围和停止条件 |
| 素材 | 竞品评论/图片/视频直接复用 | 权利审核边界存在 | 无授权复用违法/违规 | `rejected_unsafe` | 只提炼结构，成品必须自有或授权 |
| 财税 | 自动固定离岸架构、实时关税 | 可记录实体/币种/税务字段 | 无实时连接，且需要专业责任人 | `blocked_connector` | 官方数据+时间戳；实体/税务由负责人确认 |
| 平台 | Shopify/Woo/BigCommerce/Magento/Salla/Zid 等 | 前三者有基线，本轮扩展后三者 | 其他平台仍无 adapter/auth/schema/webhook | `extend_existing` | 平台 profile 分层接入，未验证保持 research_only |
| 运营 | PIM/CMS/SEO/结账/支付/税/库存/订单/物流/客服/邮件/分析 | 共享经营工作流已有骨架 | 多数插件和 API 未连接 | `extend_existing` | 课程共用，连接器按店铺/站点/模式逐项验证 |
| 社媒 | Meta/TikTok 内容与广告协同 | 广告与内容专家底座存在 | Page/Business/ad account 权限未验证 | `extend_existing` | 共享 brief，不共享执行授权 |
| Google | SEO+Ads+YouTube | Google 模型槽位和测量底座存在 | Ads/Merchant/GA4/GSC 未真实授权 | `blocked_connector` | 先只读，属性和账户逐一绑定 |
| 本土渠道 | LinkedIn/乐天/Yandex 等 | 有候选接口边界 | 国家、账户、规则和授权未知 | `research_only` | 一国一渠道一证据/adapter |
| 蒸馏 | 通用逻辑迁移与冲突淘汰 | 事实/假设/未知和垂直扩展已存在 | 缺统一七态和 superseded 记录 | `extend_existing` | 七态证据分类 + 冲突/失效链 |
| Self-Instruct | 海量问答内化 | 已有 50 条 evidence-bound 回归 | 合成内容会放大错误 | `research_only` | 小批量 evidence-bound eval + oracle + 反例 |
| 面板 | 一键更新、切换专家 | C1 已验收 | 本任务不改共享 UI | `reuse_existing` | Skill/contract 先接底座，主任务统一集成 |
| 知识库 | 全文/精简版永久调用 | Skill 可渐进加载 references | 母体文档不是权威母提示词 | `extend_existing` | 按需检索课程、规则和证据，不塞巨型提示词 |
| 推理 | 禁止模型常识、永久不可改写 | 证据检索和唯一模型网关存在 | 永久锁定会阻止纠错 | `rejected_unsafe` | 模型推理需标记；事实绑定证据，规则可 supersede |
| C1 | 正式包、长期主对话、层级隔离 | 已完成人工验收 | 无独立站 UI 专项验收 | `reuse_existing` | 在现有对话/层级路由，不建第二 App |
| 执行 | route 全字段、API 优先 | 独立站契约已有完整 route | Adobe/Salla/Zid 原生身份未补 | `extend_existing` | 增加 store/site/view identity 和 scope |
| ERP/API | 动态 schema 与适配底座 | Shopify/Woo planned；其余未验证 | 无实店读探针和业务闭环 | `blocked_connector` | 只读授权→字段映射→webhook→审批写入 |
| Amazon/B2B | 复用历史资产 | 各自状态/时间线存在 | 不是独立站实时事实 | `reuse_existing` | 只复用字段和审批模式，事实按专家隔离 |
| 视觉 | 分镜/提示词/CapCut/FFmpeg | 基础探测已实现 | Seedance/Google 路由与效果回写未闭环 | `extend_existing` | 增加独立站 brief 和权利门禁，不虚构连接 |
| 开源 | 仅按准入表使用 | 注册表已阻断未知和自动安装 | 候选研究不等于集成 | `reuse_existing` | 只引用获准模式，不复制/安装/换运行时 |
| 外部用户 | 新项目、多店绑定、导入/识图、AI补字段 | 导入按钮、route、字段提示可见 | 当前只有 private_tenant 项目，冷启动未验收 | `extend_existing` | 共享 owner 修唯一现有闭环；缺事实 unknown，不复制私有 fixture |

融合结论：复用现有桌面、路由、模型、广告、视觉、研究和审批底座；新增内容只限独立站 adapter、课程、证据、评测和增量训练状态。所有 `planned`、工具名称和官方 API 存在性都不得写成 `implemented` 或 `connected`。

> Private runtime paths, evidence, execution identities, and product records are intentionally excluded from this public pack.
