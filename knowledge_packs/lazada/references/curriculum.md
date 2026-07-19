# Lazada 专家增量课程

版本：2026-07-19 increment-10
范围：SG / MY / TH / VN / PH / ID；`local`、`cross_border`，以及尚未进入共享执行路由的官方项目候选。

## 训练准入门

每轮必须先取得外部可见证据，再允许修改课程、规则、Skill 或评测：

1. 优先读取已授权的真实 Lazada 店铺、浏览器或 API；当前未发现此类身份。
2. 无真实授权时，只读打开 Lazada 官方 Seller、Open Platform、Sponsored Solutions、Help 或合法沙箱。
3. 记录实际页面、URL、捕获时间、站点、店铺模式、点击/滚动动作、可见输入输出、错误与权限边界。
4. 页面或软件没有新增证据时，本轮只更新“无增量”游标，不制造新规则。
5. 真实发布、改价、库存、优惠、广告、付款、发货、退款、外联、MFA、银行与身份动作停在确认前。
6. 官方页面先比对 canonical URL、标题、发布日期/Last-Modified 与内容指纹；未变化则跳过。每轮至少保留一个官方一手来源，并从社区、公开视频或 GitHub 中轮换至少一类补充来源。
7. 单一卖家或博主案例只保留为带日期的实验假设；至少三个彼此独立来源且不与官方冲突，才允许提出可验证的通用假设。

## 课程模块

### C00 证据状态与母体材料清洗

- 目标：只使用 `verified_live_fact`、`time_sensitive_evidence`、`historical_operator_trace`、`draft`、`failed_attempt`、`unknown`、`blocked_owner_input`。
- 证据强度：与生命周期状态分轴标记 `official_current`、`verified_software_observation`、`multi_source_practice`、`single_case`、`historical_trace`、`unknown`；`multi_source_practice` 至少三个独立来源且不得覆盖冲突的官方规则。
- 实操：先读 `evidence-ledger.json` 和 `mother-requirements-matrix.json`；识别官方事实、用户愿望、历史轨迹和不安全要求。
- 通过：不能把母体文档、卖家经验、网页按钮或工具名称写成已连接能力。
- 评测：LZ-E017、LZ-E018、LZ-E023、LZ-E024、LZ-E028。

### C01 T One 架构与能力真值

- 目标：复用唯一 `LLMClient + config/multi_ai.json`、专家注册表、动态 schema、审批队列与隔离执行底座。
- 实操：核验 `integration_hub.json`、适配器、开发能力和活动规则；查找真实 `store_binding_id`、OAuth、广告和 ERP 成功证据。SDK 只从授权应用的 App Console 获取并核对版本、校验和、依赖和成功作用域读取，公开仓库不得替代。
- 通过：当前 Lazada 维持 `available_unconnected`；不得另建万能 Agent 或模型网关。平台公共层、类目能力层、租户/项目/商品层和任务证据层不得互相串台。
- 评测：LZ-E002、LZ-E018、LZ-E024、LZ-E026、LZ-E039、LZ-E045、LZ-E053、LZ-E054。

### C02 六站卖家授权与身份隔离

- 目标：掌握 SG/MY/TH/VN/PH/ID、ABA/ALA/ASA、local/cross-border 授权、`country_user_info`、`seller_id`、`short_code` 与 token 生命周期。
- 实操：在官方授权页核对站点选项、授权策略、token 字段和当前更新时间；不进入真实授权。
- 通过：六合一/Crossborder 只能扩大授权或发布范围，仍按国家店铺保存身份、权限和写锁。
- 评测：LZ-E001、LZ-E003、LZ-E004、LZ-E005、LZ-E025。

### C03 店铺模式、平台项目与履约概念消歧

- 目标：区分 `local`、`cross_border`、Marketplace Ease、Choice、JIT、VMI、FBL、多仓与 ownership。
- 实操：读取 Marketplace Ease 和 Choice 官方页面；本轮又把 MY Seller Center 公共注册页分段滚动到页尾，核对 Marketplace、LazMall、LazGlobal、CN/cross-border URL 参数、表单与入驻步骤；未输入 OTP、身份、银行或接受条款。
- 通过：Marketplace Ease 是已见官方“MP 商家半托管”项目，但共享路由未注册且无真实授权，保持不可执行；JIT/VMI 是 Choice 库存模型，不是普通店铺模式。Marketplace/LazMall/LazGlobal 是注册或项目标签，不扩充执行 `store_model`；LazGlobal 的区域文案不创建 SEA 店铺或共享 seller ID。
- 评测：LZ-E019、LZ-E026、LZ-E027、LZ-E093 至 LZ-E095。

### C04 类目、Listing、媒体与 IP

- 目标：按站点/类目动态读取叶子类目、必填/key/SKU 属性、品牌、图片/视频、合规与变体规则；服装、家居、美妆、电子、食品/受限品、数字商品资格和机械设备不得共用静态字段表。
- 实操：在官方文档核对叶子类目与属性类型，并用匿名非优先项目样例验证；Marketplace Ease 的普通价格字段不可自动套到 `supply_price` 流程。
- 通过：每个 Listing 保留事实、未知、类目证据、素材权利和站点结果；没有用户商品事实时明确 `unknown`，不继承其他项目价格、尺码、图片、库存、仓库或客户资料。
- 评测：LZ-E006、LZ-E007、LZ-E008、LZ-E029、LZ-E039 至 LZ-E045。

### C05 价格、库存、仓库与可售量

- 目标：区分普通库存、多仓、FBL 仓库存、sellable/withhold/occupy/total 与 Choice JIT/VMI。
- 实操：核对目标项目允许的库存 API；先读后写、逐 SKU 幂等、写入需确认。
- 通过：Lazada 仓库存不得被普通价格库存 API 假设为可编辑；无仓库映射不生成可执行库存写入。
- 评测：LZ-E004、LZ-E011、LZ-E027、LZ-E030。

### C06 Seller Voucher、Free Shipping、Flexicombo 与平台活动

- 目标：把活动对象、报名、优惠、成本承担、叠加、库存和国家日历分开。
- 实操：每次决策读取具体国家 Seller Center/官方条款；无登录时标记 unknown。本轮实际打开并滚动 Promotion webhook，核对授权、重试、三种活动类型、到期和库存预算字段。
- 通过：webhook 只触发带 seller/country-store/promotion scope 的定向当前读取，不证明活动状态或叠加；计算优惠后毛利与广告成本，外部激活、延期、停用或报名必须进入审批。
- 评测：LZ-E012、LZ-E013、LZ-E031、LZ-E055、LZ-E056。

### C07 Sponsored Solutions 与平台原生 AI

- 目标：区分 Sponsored Max、Discovery、Display、Open Platform AI Assistant、AI Smart Listing、AI Smart Product Optimisation、AI-powered translations、Business Advisor、Lazzie Seller 与 LISA；逐国学习入口、资格、输入、输出、可编辑/保存/提交/发送边界、指标与失败恢复。
- 实操：已滚动 AI Diagnosis、点击 NPL 并核对六站入口；Open Platform `AI Assistant` 实际跳转登录页。第 06 轮从 Lazada Group 官方索引打开并渲染 2025 AI Playbook/公告，核对工具描述；再实际打开 Business Advisor 六国选择器，确认未选择时 Continue 禁用，选择 SG 后进入 SG Seller Center 登录。未输入账号、密码或 MFA，未观察授权后的仪表盘或 AI 输出。
- 通过：所有原生 AI 先解析到具体国家、账户、店铺、功能权限和当前 UI。AI Listing/优化/翻译只生成待核字段或素材，按实时叶类目 schema、产品事实、素材权利和目标语言复核；Lazzie Seller/Business Advisor 只作建议或分析；LISA 自动回复属于外部消息，需配置审计、恢复路径和人工确认。公开手册、新闻稿或六国入口不证明功能已连接或六合一店铺存在。
- 评测：LZ-E014、LZ-E015、LZ-E016、LZ-E020、LZ-E032、LZ-E033、LZ-E034、LZ-E071 至 LZ-E078。
- 第 07 轮实操：完整检查 LISA 课程 29/29 页和客服视频 00:00-01:25；把 size chart、knowledge base、keyword、report、human service 与 reminder 分别建模，公开课程不触发可用性提升。
- 第 07 轮通过：配置写、自动答复、人转人工、已发送、已解决和报表读数保持独立状态；新增 LZ-E079 至 LZ-E083、LZ-E090。

### C08 订单、包裹与履约

- 目标：店铺范围订单 ID、订单项状态、push、Pack、Repack、AWB、ReadyToShip、服务商和交接证据。
- 实操：以 webhook + 目标读取为主；没有真实订单只训练状态机和前置条件。本轮从 MY Seller Center 官方页脚反向验证官方 YouTube 频道，检查 Latest/Most popular 两种频道排序，并完整播放 145.741 秒 MCL 仓库视频、展开描述和转写、检查 Most popular/Newest 两种评论排序。
- 通过：发货、取消、实物交接与状态写入均需新鲜对象状态和确认。MCL 必须先有逐国店铺资格、仓库/SKU/库存映射；enrollment、inbound、receipt、putaway、sellable、allocation、pick、pack、dispatch、carrier handoff、delivery 分开，公开视频不完成任一真实对象状态，也不证明费用、SLA 或退货路径。
- 评测：LZ-E009、LZ-E010、LZ-E011、LZ-E096 至 LZ-E100。

### C09 逆向订单、评价、IM 与售后

- 目标：区分取消校验、退货到商家/仓库、退款、拒绝、理由、历史、评价回复与 IM；把 `site_id/session_id/message_id`、push、风控拦截、撤回、会话有效期和 refund card 分开。
- 实操：本轮实际打开并滚动 IM Open API，查看 GetMessages/SendMessage、`process_msg`、recall status、session validity 和 push best practices；公开视频只读取公开描述和平台 transcript UI，不下载。买家 PII 只在授权最小范围使用。
- 通过：push 优先且不得连续轮询；撤回按 session+message 去重；拦截消息不能报已送达；refund card 不是完整逆向状态；退款/拒绝/消息/评价回复不因 API 存在而自动执行。2021 视频的 85% 门槛保持 dated hypothesis。
- 评测：LZ-E021、LZ-E022、LZ-E035、LZ-E059 至 LZ-E064。

### C10 财务、物流费、结算与利润

- 目标：使用 payout status、transaction details、account transactions、物流费、银行回单和 ERP 证据做逐国逐店对账，同时保留原始字段和差异链路。
- 实操：第 05 轮实际打开并滚动官方 `GetTransactionDetails` 详情页，核对六国 endpoint、授权要求、时间窗口、最大 500 行和 offset 分页、交易/费用/税/付款引用字段；再只读打开并滚动 BigSeller 公开 Lazada 对账帮助页，观察第三方多店汇总、导出、店铺/币种筛选和手工 `Collected` 状态。没有登录、API 调用、店铺同步、导出或状态写入。
- 通过：请求绑定一个国家 endpoint、店铺和 seller finance identity；完整分页后才推进逐国 watermark。Lazada transaction、Lazada payout、银行到账和 ERP/操作员对账是四个独立状态。第三方手工 `Collected` 不等于银行回款；字段缺失或合计不平时保留 unknown，不造费用、不强行平账、不把单一 ERP 限制写成平台规则。
- 评测：LZ-E036、LZ-E037、LZ-E065 至 LZ-E070。

### C11 工具、竞品与素材权利

- 目标：只使用已授权、合规、可验证的官方接口、公开页面和项目准入工具。
- 实操：第三方插件/ERP/分析工具先核许可证、权限、连接与数据来源；公开同行信号只做观察。本轮检查 `lazop/iopsdk` 的组织、提交、文件、发布、包和 Apache-2.0 许可状态。
- 通过：许可证不等于维护、兼容、安全或授权；2018 年单提交且无 release/package 的公开仓库保持历史研究证据，不自动安装。不绕过反爬，不批量扒店，不复用评论/买家秀/广告素材，不以三名卖家意见替代官方规则。
- 评测：LZ-E017、LZ-E018、LZ-E023、LZ-E038、LZ-E057、LZ-E058。
- 第 07 轮实操：从 Alibaba 官方开源站反向验证 `github.com/alibaba`，检查组织仓库页 1-2；深读 `alibaba/skill-up` 的 README、docs、两页 releases/issues/PR、license、security、commits 和代表性线程；未 clone/install/run。
- 第 07 轮纠错：`github.com/lazop` 没有已捕获的 Lazada 官方反向链接，身份降为 `unknown`；官方 SDK 仍以授权 App Console 为准。新增 LZ-E084 至 LZ-E089。

### C12 增量训练、失败复盘与软件融合

- 目标：每轮只处理新页面、新版本、新授权响应、新失败或新业务结果。
- 实操：更新证据游标、内容指纹、版本关系、失败复盘、规则与评测；每周合并同义项/冲突/反例，每月复核过期规则、失效工具和评测覆盖；运行定向测试。
- 通过：无证据不改平台知识；已有 T One 能力标 `reuse_existing`，真实缺口给最小融合路径，不重建共享底座；通用能力必须有匿名非优先项目回归样例。
- 评测：全量回归包。
- 深度覆盖：记录目录/标签、日期/版本/站点、滚动终点、展开模块、相关链接、分页和评论范围；无法访问的区段必须明确列出。
- 评论轨道：在平台允许时检查置顶/高赞/最新/作者或官方回复/楼中楼/争议，匿名聚类并过滤重复、引流、广告和疑似自动化；政策和 API 线索必须回查官方。
- 固定轨道：行业情报、AI×电商、社媒评论、官方开源；每轮仍以单一现有 Skill/规则/评测和去重游标为落点。
- 第 08 轮评论轨道：MCL 视频实际只有 2 条公开评论，Most popular 与 Newest 两种排序均查看；两条均为泛化赞扬，0 条作者/官方回复、0 条楼中楼、0 个物流/规则/失败主题，作为 filtered noise 记录而不制造“社区共识”。

## 当前优先级

1. C02：真实 Lazada 开发者 app 与一个具体国家店铺授权仍缺失。
2. C07：原生 AI 公共工具矩阵与 Business Advisor 六国登录边界已核验；Open Platform AI Assistant、AI Smart Listing/优化/翻译、Lazzie Seller、LISA、Business Advisor 仪表盘和 Sponsored Max 仍需逐国卖家/开发者/广告身份做只读验收。
3. C06：已核实促销 webhook 事件边界，但六国 Seller Center 的活动叠加和真实对象状态仍需逐店授权读取。
4. C03：Marketplace Ease 的国家可用性、准入和共享路由映射需官方/负责人共同确认。
5. C10：已核验 transaction-detail 字段、分页和第三方对账边界，但仍无真实逐国授权响应、payout、银行回单或 T One ERP 对账样本。
6. C09：公共 IM 状态机已有证据，但无逐国 IM app、seller authorization、push、真实会话、送达或响应率读取。

## 第 09 轮：MCL 逐国覆盖冲突与硬验收

- 主线占比：本轮证据工作全部落在 Lazada 的 MY/PH 订单仓配与六站点执行隔离；`mainline_ratio=100%`，无旁支成果凑数。
- 页面验收：MCL 主页面、MY 国家页、PH 国家页、Sponsored 行业文章及其作者二级页均完成分段滚动与页尾核对；Instagram MCL 帖子检查 5/5 轮播、正文、时间、评论区与页尾，二级 profile 失败如实记录。
- 视频验收：本轮没有新视频进入课程；因此无 `0:00`、封面或低于 95% 覆盖的视频被蒸馏。第 08 轮 MCL 视频仍保留 145.741/145.741 秒的完整播放证据。
- 评论验收：Sponsored 文章无评论模块；Instagram 帖子明确显示 0 条评论；Reddit PH 物流线程在正文前返回 HTTP 403，标为 `opened_not_reviewed`，0 条评论，不使用搜索摘要代替。
- 新知识：MCL 官方项目页当前列 SG/MY/TH/VN/ID；PH 国家页存在并描述 FBL/端到端履约，但正文 0 个 MCL 提及；2026-06-30 Lazada 署名 Sponsored 文章则声称六国覆盖。三者构成未解决的时效冲突，不能选择性合并。
- 课程通过条件：逐国 MCL 资格只能来自当前官方项目条款、合同或授权卖家资格读取；PH FBL 不等于 PH MCL。`one consolidated stock` 不等于 SEA 库存，必须保留国家、seller、store binding、program enrollment、warehouse、channel、SKU 和 ownership。
- 类目边界：PH 页面中的空调区与高价值 fenced zone 只是类目敏感的设施信号。匿名美妆、食品或电子商品仍需动态叶类目、合规、仓库和 SKU 资格，不继承 private_tenant 或其他项目数据。
- 评测增量：LZ-E101 至 LZ-E112 覆盖五国/六国冲突、PH FBL≠MCL、区域库存隔离、Sponsored 指标、联系人门禁、匿名非优先类目样例、零评论和 blocked community source。

## 第 10 轮：知识包优先的 Open Platform SDK 准入

- 英文检索先比较 EcomPHP、appolous、xKeNcHii 和 easycb 四条实现路径，再用官方 Signature algorithm 与 Requests and responses 深页核验传输差异；没有从 Lazada 首页或导航目录重复学习。
- `EcomPHP/lazada-php` 只提取负面与准入规则：region 不能替代逐国 seller identity，缺省 VN 必须改为 fail-closed，mock method mapping 不证明 body/signature/transport；不安装其 PHP/MCP 运行时。
- `appolous/lazada-php-sdk` 与 `easycb/easycb-go` 因关闭 TLS 校验、潜在敏感 URL 日志或测试入口真实性缺陷标 `rejected_unsafe`；MIT 许可、近期 release 和 stars 不改变结论。
- `@lazada-sdk/sdk v0.1.0-alpha.0` 只标 `research_only`：其发布说明自限于两个 SG live probes，不能外推到 MY/TH/VN/PH/ID、token refresh、pagination、errors 或全部 managers。配套自动文档抓取/镜像/生成链因根许可和访问权限未知标 `rejected_unsafe`。
- 通过条件：第三方客户端必须安全默认、逐国 seller identity/store binding、端点级 method/path/body/signature/schema 合同与一项所有者授权 scoped read 全部可验证；否则不提升连接器状态。
- 评测增量：LZ-E113 至 LZ-E120 覆盖 release/CI 误判、VN 静默回退、TLS/日志、两端点外推、未授权 scraper、虚假测试覆盖、单测≠连接和匿名 TH 家居类目范围隔离。
