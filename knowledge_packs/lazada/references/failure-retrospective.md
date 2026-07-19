# Lazada 专家失败复盘

更新时间：2026-07-18 22:16 +08:00

## F001 Skill 快速校验器缺少 PyYAML

- 状态：`failed_attempt`
- 发生：`skill-creator/scripts/quick_validate.py` 启动时出现 `ModuleNotFoundError: yaml`。
- 影响：官方快速校验脚本未完成；不影响 JSON/Skill 专属测试执行。
- 处理：未擅自安装新依赖；使用 `tests/test_lazada_expert_training.py` 验证 frontmatter、路径、契约、安全边界和回归集。
- 后续：若负责人批准依赖变更，再在共享依赖治理中处理，不能为单一 Skill 私装一套环境。

## F002 Open Platform URL 的 `&nodeId` 被命令行拆分

- 状态：`failed_attempt`
- 发生：Playwright CLI 导航完整 URL 时，Windows `npx.cmd` 把 `&nodeId=10777` 解释为额外命令；浏览器仍成功进入 `docId=108260` 页面。
- 影响：命令返回非零，但公开授权文档内容完整可见。
- 处理：后续公开文档导航使用仅含 `docId` 的 URL；证据账本仍保存正式完整 URL。
- 防复发：浏览器页面 URL 与命令退出码分别记录，不能把本地命令解析问题写成 Lazada 平台故障。

## F003 Playwright 会话关闭命令超时

- 状态：`failed_attempt`
- 发生：`playwright-cli -s=lazada_public close` 超时。
- 影响：无法仅凭该命令判断浏览器是否关闭。
- 处理：运行 `playwright-cli list`，确认 `lazada_public` 已不在打开会话中。
- 防复发：关闭超时后先做只读 session list，不直接 kill 所有会话，避免影响其他任务。

## F004 Open Platform AI Assistant 登录阻断

- 状态：`blocked_owner_input`
- 发生：公开开发文档中点击 `AI Assistant` 后跳转 `/apps/user/login`。
- 影响：无法核验真实输入字段、输出、编辑/提交边界、指标和失败恢复。
- 处理：停在登录页，不填写账号/密码，不借用其他平台身份。
- 解锁：负责人提供经批准的 Lazada 开发者账号/执行身份；MFA 和身份资料仍由负责人完成。

## F005 旧训练资产遗漏官方 Marketplace Ease 模式

- 状态：`failed_attempt`
- 发生：首轮契约只列 `local/cross_border`，把“可能的半托管”留在未知项，没有实际打开 `Marketplace Ease Mode（MP商家半托管）` 官方页面。
- 影响：模式课程覆盖不完整。
- 修复：本轮真实浏览器打开官方页面，确认其官方项目定义和受限 API 范围；新增为 `marketplace_ease_semi_managed_candidate`。
- 边界：共享注册表仍未包含该 route，国家可用性和真实资格未知，因此不得直接变为可执行模式。

## F006 工具名称曾容易与连接能力混淆

- 状态：`historical_operator_trace`
- 发生：注册表和代码包含 `lazada-open-platform`、Seller Center、Sponsored Solutions、ERP 等工具/表面名称。
- 风险：把注册名、按钮或测试当成 OAuth/成功调用，会制造虚假完成。
- 修复：证据账本增加 `verified_live_fact` 的本地软件审计；没有 `store_binding_id + authorization + successful read` 时保持 `available_unconnected`。

## F007 系统 `python` 指向 Windows Store 占位程序

- 状态：`failed_attempt`
- 发生：首次运行 `python -m unittest tests.test_lazada_expert_training` 时没有进入测试框架；只读检查确认 `python.exe` 来自 `WindowsApps`。
- 处理：读取工作区依赖清单，改用 Codex 工作区捆绑 Python 运行同一测试；未安装依赖、未更改 PATH 或系统配置。
- 边界：这是本地命令解析问题，不是 Lazada 平台故障，也不影响训练契约内容。

## F008 页面证据计数断言过严

- 状态：`failed_attempt`
- 发生：捆绑 Python 的首次回归运行执行 23 项测试，其中 1 项失败；测试把 6 个官方内容页捕获和 1 个独立登录边界捕获错误地要求成“至少 7 个官方内容页”。
- 处理：断言改为至少 6 个官方内容页，并继续单独检查 `LZ-LEDGER-008` 的 AI 登录阻断证据。
- 边界：没有为了让测试通过而虚构第 7 个官方内容页，证据分类保持真实。

## F009 正式 T One 客户端启动链不稳定

- 状态：`failed_attempt`
- 发生：从正式路径两次启动 `desktop_app/dist/T-One-0.1.0.exe`，均显示“Python 后端提前退出（exit=9009）”。运行日志显示捆绑 Python 候选先启动但 18 秒内未通过健康检查，随后 `py` 不存在，WindowsApps `python.exe` 回退以 9009 退出；稍后 8768 后端又恢复健康。
- 影响：不能证明正式 App 的 Lazada 专家页面、模型保存、Skill 读取、连接器错误链和店铺上下文已可用。
- 处理：未停止共享 Python 进程、未覆盖 `desktop_app/main.js`；把最小修复建议交给共享核心负责人：保留首个候选的 stderr/超时原因，可靠回收迟到进程，并在健康后端出现时重新附着而不是用最后一个回退错误覆盖根因。
- 边界：这是当前正式 App 启动链问题，不是 Lazada 平台或 LLM 网关故障。

## F010 Windows 浏览器只读验收被安全停止

- 状态：`failed_attempt`
- 发生：本机存在 T One “新建对话/出单”页面，但 Windows 控制无法可靠确认当前浏览器 URL，安全策略停止了继续点击。
- 影响：没有获得新的 Lazada 专家页面可用性证据。
- 处理：停止 UI 输入，不使用坐标猜测，不把已有页面标题写成闭环完成。

## F011 产品范围串台审计

- 状态：`failed_attempt`
- 发生：Lazada Skill 曾把 POD 作为默认 Listing 分支，LZ-E007 只用 POD shirt 做版权样例；共享旧桌面入口和 B2B Skill 也存在当前优先项目耦合。
- 修复：Lazada Skill 改为任意第三方/个性化/用户素材的权利审查，评测改为匿名家居商品并新增跨类目、跨租户、跨任务回归。
- 共享移交：`desktop_app/private_tenant_desktop.py` 和 `skills/b2b-foreign-trade-sales/**` 由其所有者评估通用化；本专家不并发修改共享资产。
- 边界：项目样本仍可在其 tenant/project/product/task 内做真实回归，但不得成为平台公共默认值或进入开源包。

## F012 证据账本 v2 URL 字段兼容

- 状态：`failed_attempt`
- 发生：增量 02 首次定向回归执行 31 项，其中 1 项因测试只读取旧 `source_url`，而新证据使用 `canonical_url`，触发 `KeyError`。
- 修复：测试明确兼容 `canonical_url` 或旧 `source_url`，并继续验证 HTTPS、捕获时间、站点、模式、权限和证据文件；没有回退 v2 指纹结构。
- 结果：修复后 31/31 通过；加入六级证据强度测试后最终 32/32 通过。

## F013 组合回归模块名使用旧名称

- 状态：`failed_attempt`
- 发生：首次组合命令引用不存在的 `tests.test_dynamic_product_requirements` 与 `tests.test_platform_activity_execution`，产生 2 个 import error；实际文件为 `test_platform_product_requirements.py` 与 `test_platform_activity_execution_plan.py`。
- 修复：先用 `rg --files tests` 读取真实文件名，再运行同一范围的正确模块。
- 结果：Lazada、平台专家路由、动态商品要求和活动执行计划共 78/78 通过。
- 边界：模块导入失败是本地测试命令错误，不是产品功能回归失败。

## F014 把同名组织的历史 SDK 仓库误判为当前可安装组件

- 状态：`historical_operator_trace`
- 风险：`lazop/iopsdk` 位于同名公开组织且采用 Apache-2.0；若只看组织名和许可证，容易误写成 Lazada 官方身份或当前 SDK 已可连接。
- 实际核验：浏览器查看仓库、文件、提交、release/package 和许可证；只见 2018 年单次提交、README/LICENSE，无 release 或 package。
- 处理：把自动安装列为 `rejected_unsafe`，仓库只保留身份未知的历史来源；第 07 轮未找到 Lazada 官方反向链接，已用 LZ-LEDGER-049 和官方 GitHub 索引纠正旧措辞。当前应用专属 SDK 仍须由注册开发者在 App Console 下载并完成依赖、安全和真实作用域读取验证。
- 边界：拒绝自动安装不代表 Apache-2.0 不可用，也不代表 Open Platform API 不可用；它只说明这个公开仓库不能证明当前生产兼容性。

## F015 增量 04 浏览器命令恢复

- 状态：`failed_attempt`
- 发生：第一次打开 IM 文档时，完整 URL 的 `&nodeId` 被本地命令解释为第二段；随后旧式 `scroll` 命令不被当前 CLI 支持。
- 处理：使用 canonical `docId` URL 正常打开页面，再用 `mousewheel` 完成真实滚动和快照。
- 边界：这是本地命令参数/版本问题，不是 Lazada 页面或 API 故障；没有修改平台状态。

## F016 公开社区 403/challenge

- 状态：`failed_attempt`
- 发生：真实浏览器打开一条公开 Reddit Lazada 退货讨论时返回 HTTP 403 和 JavaScript challenge。
- 处理：立即停止，不处理 challenge、不登录、不绕过反爬；该页面内容没有进入 Skill 或规则，改用合法公开视频来源满足来源轮换。
- 边界：搜索摘要不能替代本轮页面证据，失败访问也不能证明任何退货政策。

## F017 SG Seller Help 文章内容缺失

- 状态：`failed_attempt`
- 发生：请求 Chat Best Practices URL 后重定向到 generic Help Center，文章正文未显示；只看到 ADA、Live Chat、Raise Concern 等公共支持入口。
- 处理：未点击 Chat Now/Raise Concern，也没有把支持时段写成买家 IM 或响应率规则。
- 边界：公开帮助壳存在不等于卖家账号、客服会话、文章政策或提交链已可用。

## F018 视频转写加载未完成

- 状态：`failed_attempt`
- 发生：YouTube 公开视频可播放，描述、发布日期和章节可见；点击平台“内容转文字”后面板停在 loading。
- 处理：没有下载视频、调用外部字幕抓取或绕过平台限制；只保留描述中 85% 门槛为 2021 单一案例。
- 边界：作者自述培训资历和视频描述均不等于 Lazada 当前官方政策。

## F019 新来源日期断言固定为旧日

- 状态：`failed_attempt`
- 发生：第 05 轮首次定向回归执行 41 项，其中 1 项把所有官方来源的 `checked_at` 固定要求为 2026-07-18，因本轮新页面在 2026-07-19 实际核验而失败。
- 处理：断言改为接受账本中真实存在的 2026-07-18 或 2026-07-19 核验日；没有回写旧来源日期，也没有把新页面伪装成前一日证据。
- 结果：定向回归 41/41、组合回归 88/88 通过。
- 边界：这是测试时效断言问题，不是 Lazada 页面、API、店铺或财务数据故障。

## F020 组合回归中的共享 Amazon 字符串断言误命中

- 状态：`failed_attempt`
- 发生：第 05 轮最终组合回归执行 89 项，其中共享 `tests/test_platform_product_requirements.py` 的 Amazon 匿名家电测试用 `assertNotIn("US", json.dumps(submission))` 检查站点串台，但合法事件名 `LISTINGS_ITEM_STATUS_CHANGE` 中的 `STATUS` 自身包含连续大写字符 `US`，导致 1 项与 Lazada 无关的失败。
- 处理：本专家没有修改共享测试或 Amazon 契约；保留定向 Lazada 41/41 结果，并把组合结果如实记为 88/89，交由共享文件负责人把断言收窄到结构化站点字段。
- 边界：该失败不证明 Lazada 训练资产回归，也不能被本专家越权修成绿色。

## F021 浏览器 PDF 视图未生成可读快照

- 状态：`failed_attempt`
- 发生：第 06 轮从 Lazada Group 官方索引点击两份官方 PDF 后，浏览器 PDF viewer 的页面快照为空，其中一次控制台显示错误；没有得到可审计正文节点。
- 处理：保留由官方索引打开的直接 PDF URL，改用允许的 PDF 文本提取和逐页渲染查看第 0、1、3、34、35、37 页，再只蒸馏可见内容、页码和版权边界。
- 边界：PDF viewer 空快照是本地可见性限制，不是 Lazada 文件失效；未看见的入口、资格、模型版本、编辑/保存/提交行为仍为 `unknown`。

## F022 Business Advisor 点击等待超时但已到登录边界

- 状态：`failed_attempt`
- 发生：Business Advisor 选择 Singapore 并点击 Continue 后，浏览器命令等待 5 秒超时，但当前 URL 与标题已经变为 SG Seller Center 登录页。
- 处理：把失败归为本地导航等待超时，同时记录已观察的六国选择器、选择前后按钮状态和 SG 登录 URL；随后停止，没有输入凭据或处理 MFA。
- 边界：到达登录页只证明公开入口与国家登录边界，不证明账号、六店绑定、Business Advisor 指标、原生 AI 输出或业务完成。

## F023 原生 AI capability 边界断言过度依赖单一措辞

- 状态：`failed_attempt`
- 发生：第 06 轮首次定向回归运行 45 项，其中 1 项要求五个 `available_unconnected` capability 的 boundary 都包含字面量 `unverified`；AI Smart Product Optimisation 已用等价但更具体的 `no authorized ... exists` 表述，因此测试失败。
- 处理：断言改为接受三种明确未连接语义：`unverified`、`no authorized` 或 `no authenticated`；没有放宽 capability 状态，也没有把公开资料提升为真实连接。
- 结果：修复后重新运行定向回归。
- 边界：这是本地测试措辞问题，不是 Lazada 功能、页面或授权故障。

## F024 Alibaba 官方项目目录固定头部拦截点击

- 状态：`failed_attempt`
- 发生：检查 Alibaba 官方开源项目目录时，固定页面头部一度拦截搜索控件点击；页面筛选状态随后仍显示目标词和 0 个结果。
- 处理：把它记为本地交互失败，只保留实际可见的筛选状态和目录范围；没有把一次点击动作写成成功，也没有把目录内 0 结果外推为全网不存在。
- 边界：这不影响 `opensource.alibaba.com` 对 `github.com/alibaba/*` 的反向身份链，但限制了负向搜索结论的范围。

## F025 Lazada University 视频播放控件定位恢复

- 状态：`failed_attempt`
- 发生：首次使用元素定位播放公开视频时，控件位于当时视口外，点击未执行。
- 处理：重新截图确认可见播放器后使用当前画面内控件，实际播放并验证到 `01:25 / 01:25`；未下载视频或调用绕过式字幕工具。
- 边界：恢复只证明公开播放覆盖，不证明国家店铺功能、指标或转化结果。

## F026 知乎组织内容登录阻断

- 状态：`failed_attempt`
- 发生：从 Lazada University 官方页进入 Lazada 知乎组织后，只看到组织元信息；文章正文和评论要求登录。
- 处理：停止在登录边界，没有输入账号、验证码或手机号，也没有以搜索摘要代替正文/评论。
- 边界：本轮该来源的正文、评论、作者回复和规则事实覆盖均为 0。

## F027 已授权 Chrome 会话接口初始化失败

- 状态：`failed_attempt`
- 发生：按 Chrome Skill 的支持路径加载浏览器客户端并调用 `setupBrowserRuntime`，在干净 JS 内核重试后仍报 `Cannot redefine property: process`。
- 处理：在列出或 claim 任一标签页前停止；没有复制 Cookie、令牌、密码、配置或个人资料，也没有改用未授权脚本接管会话。
- 边界：只能写“本轮浏览器接口未初始化”，不能写 Chrome 未安装、账号未登录或登录内容不存在。

## F028 深度浏览证据产物目录回收

- 状态：`failed_attempt`
- 发生：本轮 Playwright 深度浏览的部分新快照最初落在工作区根 `.playwright-cli`，超出 Lazada 专家独立写入目录。
- 处理：先解析并核对绝对源/目标路径，再只移动本轮可识别的 39 个产物到 `skills/platform-experts/lazada/.playwright-cli/`；未碰其他任务文件。
- 边界：这是本地证据目录所有权修复，不改变网页事实或业务状态。

## F029 increment-07 规则测试措辞不匹配

- 状态：`failed_attempt`
- 发生：首次定向回归运行 51 项，其中 1 项测试要求规则文本包含 `identity as unknown`，而实际更精确的规则写的是 `official ownership as unknown`。
- 处理：只把测试期望收窄到规则中的完整语义，没有改变规则、身份门槛或 capability 状态。
- 边界：这是本地断言措辞问题，不是 Lazada、GitHub 身份链、LISA 或连接器故障。

## F030 组合回归中的共享 Amazon 匿名商品站点串台

- 状态：`failed_attempt`
- 发生：increment-07 组合回归执行 101 项，其中共享 `test_platform_product_requirements.py` 的匿名 Amazon 家电测试发现 submission 内含 `effective_dated_content_rules.us_title_and_item_highlights.country_site=US`，因此 1 项失败；Lazada 定向 51 项和 Lazada+router+activity 91 项均通过。
- 处理：本专家没有修改共享 Amazon 契约或测试，只记录 100/101 和单模块 9/10 的真实结果，并把共享修复所有权交回主任务。
- 边界：该失败不属于 Lazada 资产，也不能用删掉共享断言或隐瞒 US 规则块来伪造绿色；共享负责人应决定匿名商品输出是否应排除所有站点专属规则块。

## F031 Lazada University 查询参数被本地命令拆分

- 状态：`failed_attempt`
- 发生：第 08 轮首次打开 `全效宝2.0` 搜索 URL 时，未安全包裹的 `&tabType=all` 被 Windows 命令解释为第二段并报 `tabType is not recognized`。
- 处理：重新以安全参数打开查询；页面 canonical URL 随后包含完整 `tabType=all`，并实际看到 21 条结果。
- 边界：这是本地命令参数失败，不是 Lazada 搜索或课程失败；首次失败不计页面覆盖，恢复后的目录和登录边界才进入证据。

## F032 视频状态检查的 JavaScript 选择器引号丢失

- 状态：`failed_attempt`
- 发生：第一次读取 YouTube 播放状态时，本地 shell 丢失 `document.querySelector("video")` 的选择器引号，返回 `ReferenceError`。
- 处理：改用安全的外层/内层引号组合重新读取，随后取得真实 `currentTime`、`duration`、`paused`、`ended` 和 `readyState`。
- 边界：这是本地命令转义错误，不是视频、字幕或 Lazada 内容故障；失败输出没有被当作页面事实。

## F033 YouTube 广告与自动播放中断目标视频

- 状态：`failed_attempt`
- 发生：MCL 视频首次播放后自动导航到无关内容；重新打开 canonical URL 后，中途广告又使正片暂停并临时回到未就绪状态。
- 处理：关闭自动播放，只跳过平台公开的广告控件，重新打开目标 canonical URL，安全恢复播放，并最终验证 `145.741 / 145.741`、`ended=true`。没有下载视频、抓取私有字幕、点击广告或执行账号交互。
- 边界：一次播放开始或描述展开不等于完整视频覆盖；只有最终 ended 状态、描述、转写和两种评论排序共同构成本轮覆盖证据，也仍不证明 MCL 资格或业务结果。

## F034 Reddit 公开线程在正文前返回 403

- 状态：`failed_attempt` / `opened_not_reviewed`
- 发生：第 09 轮打开一个当前 PH Lazada Logistics 延迟主题的 Reddit 公开 URL 时，在正文、排序器和评论出现前返回 HTTP 403 网络安全阻断页。
- 处理：立即停止，没有处理 challenge、提交 support ticket、登录、复制 Cookie 或使用其他身份；该页记 0 条评论，并改读合法公开的 Instagram MCL 帖子。
- 边界：搜索摘要不是页面证据。此失败只证明本轮接口无法访问该 URL，不证明帖子内容、评论共识、PH 物流故障或平台政策。

## F035 Instagram 二级 profile 页面加载失败

- 状态：`failed_attempt`
- 发生：公开 MCL 帖子正文、5/5 轮播和 0 评论状态可读，但随后打开关联 public profile 作为二级页时返回通用加载错误。
- 处理：没有重新登录、反复刷新、关注或切换账号；保留帖子本身的完整公开覆盖，并把账号 ownership 降为 `platform_branded_social_account_official_reverse_link_not_captured`。
- 边界：帖子可读不等于 profile 身份链完整；不能把账号或帖子提升为当前官方政策，更不能由此推导 MCL 资格或运行结果。

## F036 PowerShell 选择器转义生成误文件

- 状态：`failed_attempt`
- 发生：一次只读 Instagram DOM 命令中的 `>` 被 PowerShell 解释，意外在 Lazada 专属目录生成一个 99 字节、仅含 CSS 选择器解析错误的文件。
- 处理：读取确认内容后用补丁删除该误文件，并改用不含歧义重定向的选择器命令；没有删除任何用户资产或共享文件。
- 边界：本地转义错误不计页面覆盖或平台事实；修复只清理本轮误生成物，不扩大可写范围。

## 复盘写入规则

- 只记录真实发生的失败、阻断、误判或恢复动作，不编造“模拟失败”。
- 平台错误、本地工具错误、权限缺失和业务结果必须分开。
- 失败修复不能自动提升业务状态；通过测试也不等于已接店、已发布、已投放或已结算。

## F037 第三方 PHP SDK 关闭 TLS 并泄露签名 URL 风险

- 状态：`failed_attempt` / `rejected_unsafe`
- 发生：静态审计 `appolous/lazada-php-sdk` 发现 GET/POST 都关闭 TLS peer/host verification，且错误日志可接收含 app_key、access_token 和 sign 的完整请求 URL。
- 处理：未 clone/install/run；近期 Laravel 兼容 release 与 MIT 许可不抵消传输和凭据风险，只保留负面规则与回归题。
- 边界：这是候选包安全拒绝，不是 T One 已连接失败或 Lazada API 故障。

## F038 Alpha SDK 的两项 SG 探针被误外推风险

- 状态：`failed_attempt` / `research_only`
- 发生：`xKeNcHii/lazada-sdk` 发布说明只声称验证 SG 的两个端点，却明确把另外五国、refresh round trip、wire errors、Unicode、pagination 和 31/33 managers 留为未验证。
- 处理：运行时保留为研究线索；文档 scraper/spec 管线因根许可证和自动抓取权限未知标 `rejected_unsafe`，未运行或复制。
- 边界：仓库作者的 live claim 未被独立复现，不能提升任一国家连接状态。

## F039 Go SDK 测试入口与安全默认不成立

- 状态：`failed_attempt` / `rejected_unsafe`
- 发生：`easycb/easycb-go` 将 TLS verification 默认关闭；测试 fixture 又显式关闭 TLS、使用空凭据，并可能在 `m.Run()` 前返回，代表测试只打印错误而无成功断言。
- 处理：未 clone/install/run；README 的“每个功能都有测试”、release 数和 stars 不作为准入证据，转成测试入口真实性与 fail-closed 回归。
- 边界：这不是运行 T One connector 的失败；T One 仍没有 Lazada OAuth、seller identity 或 scoped live read。
