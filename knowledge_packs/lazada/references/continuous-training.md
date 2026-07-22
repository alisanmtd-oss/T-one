# Lazada 持续增量训练机制

## 已建立的自动化

- 名称：`Lazada专家持续增量训练`
- 自动化 ID：`lazada`
- 状态：`ACTIVE`
- 频率：每 24 小时一次
- 通知：仅失败运行通知


## 每轮固定顺序

1. 读取权威记忆、机器队列、平台专家注册表和本专家的 training state。
2. 检查 Lazada 专属真实执行身份：逐国 `store_binding_id`、seller ID、OAuth、浏览器、广告、ERP、仓配与财务授权。
3. 有身份则只读进入对应身份；无身份则打开官方公开 Seller/Open Platform/Sponsored/Help 页面或合法沙箱。
4. 至少记录一个新页面/版本/授权响应/真实错误/业务结果；否则本轮写 `no_delta`，不得制造课程或规则。
5. 仅处理 source cursor 之后的新证据或已到期证据；计算 claim/content fingerprint，保留站点、模式、ownership、权限和有效期。
6. 官方 URL 在打开前比对 canonical URL、标题、发布日期/Last-Modified 和内容指纹；未变化则进入重复跳过清单。来源轮换至少包含一个官方一手来源，并从社区、公开视频或 GitHub 中选择至少一类；单一案例只保留为 dated anecdote。视频只使用平台允许的公开播放、描述和字幕/转写入口；字幕加载失败就记录失败，不下载或绕过。社区遇到登录、challenge、403 或地区限制立即停止并换合法来源。
7. 更新 Lazada 课程、规则、证据账本、失败复盘、评测和增量报告；平台公共、类目能力、租户商品和任务证据四层分离，通用能力补匿名非优先项目样例。
8. 每周合并同义知识、冲突和反例；每月复核过期规则、失效工具、连接器状态和评测覆盖。旧证据标 `superseded`/`expired` 并保留版本链，不直接删除。
9. 运行 `python -m unittest tests.test_lazada_expert_training`。
10. 固定汇报：已查软件/网页、重复跳过、新增事实、失效知识、冲突、蒸馏内容、复用/扩展、授权阻塞、下一轮来源。

## 状态提升条件

- `available_unconnected -> connected_read_only`：必须同时有具体 `store_binding_id + country_site + seller_id/short_code + credential_ref + successful authenticated read + captured result`。
- `connected_read_only -> connected_write_gated`：还需对象级 scope、幂等键、写锁、当前状态证据和人工确认队列。
- 页面、按钮、公开文档、schema、测试或演示均不能独自触发状态提升。
- 项目样品、价格、库存、媒体、仓库、客户或历史任务不能触发平台公共默认值；缺少当前租户事实时必须返回 `unknown`。

## 允许的写入范围

- `skills/platform-experts/lazada/**`
- `config/platform_expert_training/lazada.json`
- `tests/test_lazada_expert_training.py`

不修改共享 C1/C4 核心、权威记忆、机器队列、平台专家注册表或其他专家资产。需要共享改动时只写建议。

## 固定学习轨道（increment-07）

- `industry_intelligence`：政策、算法/广告、API、站点/店铺模式、支付税务合规、物流售后、财报/大会和服务商变化；新闻只作带日期事件。
- `ai_commerce`：平台原生 Listing/图片/客服/广告/分析 AI 与通用模型、MCP、插件、浏览器/桌面自动化的真实输入输出、权限、隔离、费用、数据去向、门禁和效果回写。
- `social_comment_intelligence`：评论区为独立来源轨道，不再是可选补充；只保存匿名主题、时间、语言、站点、证据等级和公开链接。
- `official_open_source`：先用官方网站/开发文档/已验证官方社媒反向验证 GitHub 组织，再按 `owner/repo + release_or_commit` 去重；不自动 clone/install/run。

## 深度页面与评论完整性

1. 纳入蒸馏前记录身份、标题、作者、日期/版本、国家站点、店铺模式、目录/标签、最终滚动位置、展开模块、相关链接、分页和不可访问范围。
2. 列表至少检查首页、下一页和最新排序（若界面存在）；GitHub检查 README、docs、releases/changelog、license、issues、PR、discussions、security 和最近 commits，缺失模块明确记录。
3. 社媒/视频/论坛在界面允许时检查置顶、高赞、最新、作者/官方回复、楼中楼和争议；懒加载只记录实际覆盖量，不写“全部评论”。
4. 评论按用户问题、场景、站点/模式、异议、功能诉求、失败步骤、投诉/退货、竞品和规则变化线索聚类；重复、引流、广告、机器人和疑似 AI 噪声标记并排除。
5. 评论和作者案例保持 `community_signal` / `dated_operator_case`；政策、费用、API 与功能变更必须回查官方。不得保存用户名、头像、联系方式或大段原文。
6. 连续两层无新增、偏题、重复、登录、验证码、付费或访问限制即停止。登录态只通过所有者授权的当前 Chrome 支持接口只读复用；接口失败时不得导出 Cookie、令牌或配置。

本轮覆盖记录：LISA 课程已检查 29/29 页、公开视频已播放至 01:25/01:25，两页均无可见评论模块；知乎文章/评论因登录要求未读取；GitHub issue 134 与 PR 148 的时间线被检查并匿名化。Chrome 浏览器客户端在列出标签页前初始化失败，未访问任何登录态内容。

## 第 09 轮起的硬验收

- 候选来源分为 `candidate_screened`、`opened_not_reviewed`、`fully_reviewed`、`blocked`。网页必须有至少 90% 的分段滚动覆盖、页尾、导航/目录、适用分页/关联页和必要二级页；二级页被登录、403 或通用错误阻断时，记录 URL、错误和零覆盖，不重试不变阻断。无限滚动至少观察三次新加载并记录停止原因。
- 10 分钟内视频必须达到至少 95% 实际播放或字幕覆盖并核对关键画面；停在 `0:00`、只看封面或覆盖不足的来源标 `opened_not_reviewed`，不得蒸馏。
- 有评论时检查置顶/高赞/最新/作者或官方回复/追问/反对/失败，至少采样 10 条或全部；没有评论模块或明确 0 条时记录零，不能制造共识。
- 每轮至少 70% 证据工作直接服务 Lazada 六站点的店铺、商品、流量/广告、达人内容、活动、订单仓配、售后结算或 Open Platform；工具/通用 AI 证据不超过 20%，带明确迁移假设的跨平台参考不超过 10%；无关页面标 `irrelevant_skip`。
- 固定交付新增：`mainline_ratio`、`deviation_check`、`opened_not_reviewed`、`fully_reviewed` 和 `no_delta`。只有通过硬验收的新证据才允许改 Skill、规则、评测或连接状态。

## 第 10 轮起：英文检索与现成知识包优先

- 每轮先从现有唯一 Skill、规则、课程、模板、评测、失败复盘、连接器、GitHub 准入记录和 source cursor 找真实缺口，不从首页或 About 重新学习。
- 至少 50% 时间用于英文知识包发现、源码/许可证/安全/维护审计、去重与最小复用；泛官方介绍页不超过 10%，官方深页只核验候选包中有争议的当前字段、权限、签名、站点或店铺模式。
- 固定英文组合包括 `Lazada seller agent skills`、`Lazada operations playbook`、`Lazada sponsored solutions automation`、`Lazada Open Platform SDK`、`Lazada ERP integration`，并与 `repo/topic/awesome/skill/playbook/SOP/checklist/template/evaluation/SDK/MCP/ERP/OMS/PIM/WMS` 交叉。
- 每个主题比较 2–3 个候选，检查作者/身份链、owner/repo+commit/tag、License、release/commit、README/docs/changelog、issues/PR/security/CI、凭据/遥测/执行风险、依赖/部署、逐国 seller identity 和 T One 重叠度；不按 stars 或 feature count 采用。
- 候选结论只能是 `keep_reuse / merge_into_existing / extract_rules_only / research_only / rejected_stale / rejected_license / rejected_unsafe`。未知许可、自动镜像文档、默认关闭 TLS、日志暴露令牌、静默国家回退或测试入口未真实执行时阻断，不 clone/install/run。
- README、release、CI 或单测通过不等于真实连接；必须验证 exact endpoint method/path/body/signature/response、country_user_info seller identity 和一次所有者授权的 scoped read，才可推进 connector state。

> Private runtime paths, evidence, execution identities, and product records are intentionally excluded from this public pack.
