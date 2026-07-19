# 跨境母体需求到 SHEIN 专家的最小融合矩阵

母体来源：`pasted-text.txt`，2026-07-18 复核，SHA-256 `f564a2e8341a6f3370e1efac9b249df65af67ef44957ecb7c907f789381acf3b`。该附件是候选需求清单，不是平台事实、授权证明或实现证明。

分类只允许：

- `reuse_existing`：T One 已有能力可直接作为底座使用，不重复开发。
- `extend_existing`：在已有底座上增加 SHEIN 专属规则、证据、评测或适配器。
- `research_only`：仅做候选研究或官方核验，不能称为已接入或业务完成。
- `blocked_connector`：方向允许，但缺真实 OAuth/API/店铺/ERP/浏览器/仓库等连接或负责人授权。
- `rejected_unsafe`：规避平台限制、无授权素材复用、虚假能力或破坏隔离的要求，拒绝吸收。

## 现有 T One 基线

| ID | 母体/补充需求 | 分类 | 现有能力 | 缺口 | 最小融合路径 |
|---|---|---|---|---|---|
| `B01` | Windows 正式包、T1 标、一店一长期主对话与层级隔离 | `reuse_existing` | C1 已完成人工验收 | SHEIN 尚无真实店铺 | 沿用现有 workspace/project/store/task 层级，不新建壳层 |
| `B02` | 唯一模型网关、模型选择、DPAPI、真实连接测试 | `reuse_existing` | `LLMClient + multi_ai.json`，9 个就绪模型 | 无 SHEIN 平台权限 | 只调用现有网关做研究/草稿，绝不另建模型网关 |
| `B03` | 专家注册、Skill/插件/模型/连接器入口 | `extend_existing` | 平台专家底座与 Etsy 范例已存在 | SHEIN Skill 尚待主任务注册集成 | 交付独立 Skill/契约/测试；共享注册由主任务集成 |
| `B05` | 动态商品 schema、适配器、证据注册表 | `extend_existing` | 通用底座存在 | SHEIN 动态类目/字段及真实连接器未接 | 将官方动态 schema 映射到现有适配器，不复制一套商品系统 |
| `B06` | Amazon 88 子体与禁止重复父体历史 | `research_only` | Amazon 专属操作资产存在 | 与 SHEIN 店铺无可迁移执行授权 | 仅复用“幂等/禁止重复发布”控制模式，不迁移 ASIN 数据 |
| `B08` | Meta/TikTok/Google/Amazon 广告统一测量与止损 | `reuse_existing` | 统一草稿、人审、利润和止损底座存在 | SHEIN 付费广告面/API/账单身份未核实 | 复用测量契约；SHEIN 付费广告保持 `research_only` |
| `B09` | 视频创意与 CapCut/FFmpeg 探测 | `reuse_existing` | `creative_video.py` 和分镜/提示词基础存在 | 平台/项目安装和效果回写未闭环 | 只生成有授权素材草稿；不为 SHEIN 再造视频流水线 |
| `B10` | GitHub 能力只能按准入注册表 | `reuse_existing` | `github_capability_registry.json` 已复核 | SHEIN 无获准的新仓库/连接器 | 未知仓库默认阻断；Kun 仅研究，其他项目按各自准入结论 |

## 母体架构与全局规则

| ID | 母体需求 | 分类 | 现有能力 | 缺口 | 最小融合路径 |
|---|---|---|---|---|---|
| `A01` | 建立跨境总母体和大量可切换专家 | `extend_existing` | 已有平台专家注册与独立 Skill 底座 | 不需要第二套万能 Agent | SHEIN 作为现有注册表中的独立专家资产融合 |
| `A02` | 平台店与独立站两大板块 | `reuse_existing` | 平台/站点/模式路由已存在 | 母体分类不能替代店铺授权 | SHEIN 只用平台店路线，独立站不纳入本 Skill |
| `A03` | 平台站内广告与站外广告严格分开 | `reuse_existing` | 统一广告底座已区分渠道与目标 | SHEIN 站内付费广告尚未证实 | 活动/优惠与付费广告分别建证据状态 |
| `A04` | 每个专家内置全部行业工具并自动使用 | `rejected_unsafe` | 有配置入口但多数工具未连接 | “工具名=已接入/精通”是虚假能力 | 只登记经验证 capability state 和最小连接缺口 |
| `A05` | 每日全网、社群、视频、GitHub 自动抓取并永久学习 | `research_only` | 有公开研究、视频基础和本次增量自动化 | 无全源授权、稳定连接、版权/隐私与质量闭环 | 先只巡检官方一手资料；其他来源作为实验候选 |
| `A06` | 永久锁定、无法改写的规则 | `rejected_unsafe` | 有权威记忆、版本和过期复核机制 | 平台规则会变更 | 使用带来源、有效期、supersedes 的可撤销规则 |
| `A07` | 兼容现有程序，只扩知识库 | `reuse_existing` | 本次限制在 SHEIN 独立目录 | 共享路由注册仍需主任务集成 | 不修改共享核心，只提交融合建议 |

## 采集源与学习机制

| ID | 母体需求 | 分类 | 现有能力 | 缺口 | 最小融合路径 |
|---|---|---|---|---|---|
| `S01` | 国内论坛、社区、媒体作为来源 | `research_only` | 可做公开研究 | 非官方、时效和转载来源不稳定 | 只生成带来源的假设，不进入平台规则 |
| `S02` | B站/抖音自动解析全部视频 | `blocked_connector` | 视频解析基础存在 | 无合法抓取连接、下载授权和全量转写闭环 | 仅处理用户提供或明确授权的视频 |
| `S03` | YouTube/TikTok 与海外社群自动采集 | `blocked_connector` | 公开网页研究能力存在 | 登录、API、内容授权和隐私边界未建立 | 官方优先；公开内容只做最小研究，不自动入规则 |
| `S04` | 自动绕过反爬 | `rejected_unsafe` | 无此能力且不应建立 | 违反平台边界 | 使用官方 API、允许的公开访问或人工提供资料 |
| `S05` | 各平台官方大学、公告、政策每日巡检 | `extend_existing` | 官方证据索引和定时任务底座存在 | 需增量水位、站点/模式边界和失效检测 | SHEIN 自动化只处理新增/变更/过期官方证据 |
| `S06` | 广告、支付、税务、海关实时规则 | `research_only` | 广告/利润/人审底座存在 | 高风险规则需要国家与专业责任人核验 | SHEIN 只记录官方链接和适用边界，不给跨站通用结论 |
| `S07` | 卖家经验经多人验证后变成标准规则 | `research_only` | 已有证据状态和实验框架 | 多人一致仍不是官方事实 | 先标 `draft`，结果只升为历史操作轨迹 |
| `S08` | GitHub 定时搜索 ERP、广告、爬虫、防关联 | `research_only` | GitHub 准入注册表存在 | 未核仓库默认禁用；防关联规避不可采纳 | 只研究注册表允许面；不得自动安装或接店 |
| `S09` | 防关联程序学习 | `rejected_unsafe` | 店铺身份隔离是合规底座 | 规避平台关联风控不允许 | 仅做授权、身份、店铺边界隔离，不做规避 |
| `S10` | 下载→降噪→转写→蒸馏视频流水线 | `blocked_connector` | CapCut/FFmpeg 探测和创意结构存在 | 下载授权、ASR/模型和来源许可未闭环 | 仅对有权素材执行本地最小流水线 |

## 工具与竞品研究

| ID | 母体需求 | 分类 | 现有能力 | 缺口 | 最小融合路径 |
|---|---|---|---|---|---|
| `T01` | Amazon 工具与全盘竞品扒取 | `research_only` | Amazon 专属资产另有任务 | 非 SHEIN 范围且多数工具未接 | 不在 SHEIN 专家重复建设 |
| `T02` | TikTok Shop 数据/达人/直播工具 | `research_only` | TikTok 另有平台路线 | 非 SHEIN 范围且无连接证明 | 保持专家隔离，不共享执行身份 |
| `T03` | Shopee/Lazada 数据和爬虫 | `research_only` | 平台注册底座可扩 | 非 SHEIN 范围 | 不在本专家接入 |
| `T04` | 速卖通/Etsy/eBay 工具 | `research_only` | Etsy Skill/路由测试存在但无 OAuth | 非 SHEIN 范围 | 仅借鉴独立 Skill 结构，不借用连接状态 |
| `T05` | BuiltWith/Wappalyzer 等技术侦测 | `research_only` | 公共网页研究基础存在 | 不是 SHEIN Seller Hub 权限 | 只用于合法公开网站技术研究，不进入店铺执行 |
| `T06` | Ecomhunt/PPSpy 等爆品监测 | `research_only` | 无已验证连接 | 数据许可、账号与准确性未知 | 候选研究；不得声称实时全网覆盖 |
| `T07` | SimilarWeb/Semrush/Ahrefs/Trends | `research_only` | 无 SHEIN 专属连接证明 | 订阅、API、数据范围未知 | 需要时逐工具核验并保存数据时间窗 |
| `T08` | 广告资料库和竞品广告分析 | `reuse_existing` | 统一广告研究与草稿底座存在 | SHEIN 站内广告边界和部分工具 OAuth 未通 | 只复用公开、授权分析模式；不复用素材 |
| `T09` | 完整还原竞品投放策略 | `research_only` | 可分析公开信号 | 公开信号不足以证明预算、受众或效果 | 明确事实/推断/未知，不输出“完整还原”假结论 |
| `T10` | POD、供应链、尺码与物流测算 | `reuse_existing` | Creator POD/商品和利润底座存在 | SHEIN 类目、仓库、费率未授权 | 用真实商品与店铺字段接入现有模型 |
| `T11` | OTA 侦测和动态定价 | `research_only` | 另属独立站/地球支线 | 与 SHEIN 专家无关 | 不在本专家融合 |
| `T12` | Meta/TikTok Ads/Google 渠道工具 | `reuse_existing` | 统一测量/草稿/人审底座存在 | 真实 OAuth 多数未通 | 仅作为站外渠道候选，不冒充 SHEIN 站内能力 |
| `T13` | TikTok One 作为投放目标 | `rejected_unsafe` | 真实基线定义其为创意达人供应层 | 母体分类错误 | 保持供应层语义，不进入广告投放目标 |
| `T14` | 全球本土渠道工具 | `research_only` | 渠道扩展底座存在 | 国家、账号、合规与连接未知 | 按国家逐项核验，不进入 SHEIN 店铺写操作 |
| `T15` | 全网批量爬取竞品店铺 | `research_only` | 有受控公开研究基础 | 授权、robots/条款、频率和隐私边界未建立 | 只用允许的公开数据和限速白名单研究 |
| `T16` | 自动扒取买家秀、评论图片和视频直接投广告 | `rejected_unsafe` | 有素材权利门禁 | 未授权复用侵权并可能暴露个人信息 | 只分析公开结构；素材需原创或有明确许可 |
| `T17` | 实时汇率、关税、离岸架构自动测算 | `research_only` | 利润测算底座存在 | 实时源、税务责任和国家适用性未核 | 标注数据时间与假设，付款/税务由负责人确认 |
| `T18` | 每个工具高级功能必须全部精通 | `rejected_unsafe` | 能力状态注册机制存在 | 不可能从工具清单证明精通 | 以逐工具任务证据和评测通过为准 |
| `T19` | 自动更新工具版本、淘汰旧方法 | `extend_existing` | 证据过期和增量水位已建立 | 无全工具版本源 | 只跟踪已准入且与 SHEIN 直接相关的来源 |
| `T20` | 多工具交叉验证 | `extend_existing` | 证据 envelope 可承载多来源 | 当前多数工具未连接 | 官方源优先；候选工具只补充推断，不替代官方/店铺事实 |

## 专家模块与 SHEIN 专项

| ID | 母体需求 | 分类 | 现有能力 | 缺口 | 最小融合路径 |
|---|---|---|---|---|---|
| `E01` | Amazon 专家完整运营/广告/风控 | `research_only` | Amazon 另有真实资产与任务 | 不属于 SHEIN | 保持店铺/平台身份隔离 |
| `E02` | TikTok Shop 专家 | `research_only` | 平台底座可承载 | 不属于 SHEIN | 不在本 Skill 实现 |
| `E03` | SHEIN 全托管识别 | `research_only` | 模式标签可识别 | T One 不接官方全托管或供货/OBM 全托管执行 | 返回 `blocked_mode`，不作为 private_tenant 可选身份 |
| `E04` | SHEIN 半托管 | `extend_existing` | 路由和契约已支持 `semi_managed` | 无真实店铺模式响应 | 授权后读取站点、字段、仓库、结算，不从规划表执行 |
| `E05` | SHEIN 自运营/Marketplace | `extend_existing` | 路由和契约已支持 `platform_self_operated` | 无 seller/store ID 与权限 | 授权后接动态 schema；外部写入逐项确认 |
| `E06` | SHEIN 供应商模式 | `research_only` | Open Platform 文档可识别多种标签 | “供应商”含义、ownership 与商业模式未由店铺证明 | 先解析实体/模式；官方全托供货只识别不执行 |
| `E07` | SHEIN 入驻与国家站点 | `extend_existing` | 官方来源索引和规划站点提示存在 | 当前站点/实体/资格会变且无授权 | 公共信息做 `time_sensitive_evidence`，执行读授权店铺 |
| `E08` | SHEIN 品控与类目规则 | `extend_existing` | 合规工作流、动态类目字段契约已建立 | 服装/家居/定制/全类目授权未知 | 逐店读类目/属性/证书，不把候选标签当店型 |
| `E09` | SHEIN 上新 | `blocked_connector` | Listing 草稿和幂等门禁可复用 | 产品 API、Seller Hub、类目、品牌、仓库均未接 | 只产草稿/连接清单；发布需连接证明和确认 |
| `E10` | SHEIN 活动和优惠 | `blocked_connector` | 活动工作流与利润门禁存在 | authenticated eligibility/stacking 未接 | 读到店铺证据后生成 gated draft，激活需确认 |
| `E11` | SHEIN 付费广告 | `research_only` | 统一广告底座可复用 | 未找到可执行公开 Ads API/账单身份/权限 | 继续研究，禁止把营销标签或优惠当付费广告 |
| `E12` | SHEIN 订单、仓配、售后 | `blocked_connector` | 订单/履约/退货决策契约已建立 | API、Seller Hub、仓库和真实订单未接 | 先做只读接入；发货/退款/消息逐项确认 |
| `E13` | SHEIN 结算 | `blocked_connector` | 自营/半托管字段分离和对账契约已建立 | Finance API/报表/币种/税费映射未接 | 先只读对账；银行/税务/付款设置禁止自动改 |
| `E14` | SHEIN 平台原生 AI | `extend_existing` | 已核实 Listing Optimizer 自动建议/A-B 描述及内部 AI 风控边界 | 无账号访问/API/结果回写；Listing Optimizer 未被官方页明确称为 AI | 保存 native automation/internal AI/third-party 分层矩阵 |
| `E15` | Shopee/Lazada、速卖通、Etsy/eBay 专家 | `research_only` | 各平台共享底座或候选 Skill | 非 SHEIN | 不在本任务扩展 |
| `E16` | 独立站统一专家 | `research_only` | 另有 Creator POD/独立站/地球支线能力 | 非 SHEIN | 不合并进 SHEIN Skill |
| `E17` | Meta/TikTok/Google/本土渠道专家 | `research_only` | 渠道底座存在 | 非 SHEIN 店铺执行面 | 通过目标/渠道字段关联，不共享店铺授权 |

## 蒸馏、自动化、面板和永久约束

| ID | 母体需求 | 分类 | 现有能力 | 缺口 | 最小融合路径 |
|---|---|---|---|---|---|
| `L01` | 清洗广告、水文和个案 | `extend_existing` | 证据状态、来源优先级和失败复盘已建立 | 仍需每轮执行 | 自动化仅处理官方增量，经验保留为假设 |
| `L02` | 蒸馏通用底层逻辑并跨业务套用 | `research_only` | 可抽取工作流模式 | 跨平台/模式套用可能错误 | 只复用审批、幂等、证据结构，不复用站点规则或结算公式 |
| `L03` | 每日更新、自动淘汰旧规则 | `extend_existing` | 增量水位和过期机制已建立 | 持续任务尚需创建并观测 | 建唯一 SHEIN 自动化；保留 superseded 记录不物理抹除 |
| `L04` | 每周全网/视频/GitHub蒸馏 | `research_only` | 部分研究/视频/GitHub准入底座存在 | 全源连接、授权和质量控制未闭环 | 当前只扩官方增量；其他输入逐项授权和准入 |
| `L05` | 每月海量 Self-Instruct 问答内化 | `research_only` | 20+ 离线回归场景已存在 | 海量合成可能放大幻觉 | 只从已核证规则生成离线评测，不写成业务事实 |
| `P01` | 一键全域更新 | `extend_existing` | 自动化与专家入口底座存在 | 共享面板按钮未集成 | 先以 SHEIN 独立定时任务运行；面板改动交主任务 |
| `P02` | 一键切换专家 | `reuse_existing` | `platform_expert_registry.json` 已存在 | SHEIN 独立 Skill 尚待共享集成 | 由主任务登记，不在本任务改注册表 |
| `P03` | 调取完整/精简母体知识库 | `research_only` | Skill 渐进加载可替代 | 巨型母提示词会污染上下文 | 入口 Skill 精简，细节按 references 按需读取 |
| `P04` | 解析任意视频链接并自动入库 | `blocked_connector` | 本地视频工具基础存在 | 下载/版权/连接/转写未闭环 | 只处理用户提供或授权素材，先产草稿再审核 |
| `P05` | 竞品调研自动选择全部工具 | `research_only` | 受控公开研究与证据记录存在 | 工具连接与数据许可不足 | 只选择已验证/已授权工具，事实与推断分开 |
| `H01` | 禁止模型常识，只能用永久母库 | `rejected_unsafe` | 有证据优先和权威记忆 | “永久母库”会过期且不完整 | 可用模型推理，但可变结论必须有当前证据 |
| `H02` | 永远不混淆站内/站外广告 | `reuse_existing` | 已有目标/渠道分层 | SHEIN 站内 Ads 仍未知 | 继续用显式广告 surface、billing、reporting 字段 |
| `H03` | 独立站/OTA和社媒广告合并 | `research_only` | 属其他专家设计 | 与 SHEIN 无关且不能覆盖实际业务差异 | 保持现有项目/专家边界 |
| `H04` | 熟练全部工具并自动扒取 | `rejected_unsafe` | 能力注册和真实测试机制存在 | 虚构成熟度、可能越权 | 逐工具按 evidence/capability 状态开放 |
| `H05` | 稳定外网自动反爬、永久保存 | `rejected_unsafe` | 合规公开研究和版本化存储存在 | 反爬规避被禁止；永久事实会过期 | 不绕过限制；存版本、来源、有效期和删除/更新能力 |
| `H06` | 不改已成型功能 | `reuse_existing` | 本次独立写入边界明确 | 共享注册/调度仍需集成 | 只提交 SHEIN 资产和明确的共享改动建议 |
| `H07` | 不闲聊、只围绕业务 | `reuse_existing` | 专家 Skill 有明确触发范围 | 不能以此覆盖安全/澄清/审批 | 输出保持任务相关，同时保留必要的安全说明和确认 |

## 最小融合结论

1. 不创建第二套母体 Agent、模型网关、商品系统、广告测量、视频流水线或店铺身份层。
2. SHEIN 增量只落在独立 Skill、机器契约、证据索引、课程、失败复盘、评测和学习水位。
3. 真实 SHEIN 能力当前停在 `available_unconnected`、`research_only` 或 `blocked`；规划项不能写成 implemented。
4. 共享注册、App 面板和连接器运行时由主任务在占用边界解除后集成；本专家只给出接口与差距建议。
5. 所有外部动作继续逐项确认，所有规避和无授权素材复用要求永久拒绝。

> Private runtime paths, evidence, execution identities, and product records are intentionally excluded from this public pack.
