# T One

**面向全球电商与外贸 B2B 的开源、本地优先 AI 运营核心。**

[![CI](https://github.com/alisanmtd-oss/T-one/actions/workflows/ci.yml/badge.svg)](https://github.com/alisanmtd-oss/T-one/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-3776AB.svg)](pyproject.toml)

[English](README.md) | [公共知识包](docs/PUBLIC_KNOWLEDGE_PACKS.md) | [路线图](ROADMAP.md) | [架构](docs/ARCHITECTURE.md) | [参与贡献](CONTRIBUTING.md) | [安全策略](SECURITY.md)

T One 面向个人创业者、电商团队、开发者、工厂和服务商，目标是让 AI 智能体协助处理跨境电商与外贸工作，同时避免不同店铺、客户、凭据和证据互相串用。

它为商品、SKU、Listing、库存、订单、履约、结算、供应商、工厂、仓库、B2B 客户、报价、付款、内容实验与人工审批提供统一的本地数据边界。当前公开版不会假装已经接通 Amazon、TikTok Shop、SHEIN、Shopee 等平台的真实写入权限。

## 0.3：直接聊天选择平台智能体

不需要先创建复杂项目或进入扩展配置。普通聊天里写出平台名，公共路由会选择对应的脱敏知识包；多平台问题保持为对比，不会把一个平台的规则串到另一个平台。

本版公开 AliExpress、B2B 外贸、eBay、Etsy、全球/本土渠道规划、Google Ads、独立站、Lazada、Meta、SHEIN、Shopee、TikTok Ads 和 Walmart 共 13 个知识包。TikTok Shop 知识包明确不在公开范围内。

```python
from ai_ecommerce_director.platform_agents import route_public_chat

result = route_public_chat("这个商品适合速卖通哪些市场？")
assert result["agent_id"] == "aliexpress"
assert result["external_execution_allowed"] is False
```

这些知识包只提供公开规划规则，不代表真实店铺、OAuth、广告账户或平台写入已经连接。详见 [公共知识包说明](docs/PUBLIC_KNOWLEDGE_PACKS.md)。

0.3.1 同步更新了无依赖浏览器演示：用户只需说目标，由 T One 自动选择智能体；文件从聊天框“＋”进入，模型、账号和管理统一收进设置。邮箱与通信账号页面仅演示 7 类账号的设置路径，不接收凭据、不连接外部服务。

## 0.2 版本重点

- 提供一个完全使用合成数据、无需依赖的聊天优先界面参考。
- 日常入口只保留智能体对话；模型、账号连接、诊断和自动任务归入一个设置后台。
- 脚本、分镜、提示词和剪辑建议归入一个内容创作智能体，不再拆成多个项目。
- 广告智能体采用“读取证据 → 解释原因 → 给出建议 → 负责人确认”的流程，不会在演示中花费、停投或发布。
- 商品表、图片和说明从对话输入框旁的加号进入，不再占用顶部导航。

直接在浏览器打开 [`demo/chat-first-workspace.html`](demo/chat-first-workspace.html) 即可体验交互参考。该页面不发送网络请求、不保存密钥，也不连接真实店铺。

## 当前公共核心

| 能力 | 公开状态 |
|---|---|
| AI 服务商 | 服务商目录、显式模型选择、任务路由元数据和脱敏错误反馈 |
| 本地凭据 | Windows DPAPI 加密存储与凭据引用；不把明文密钥写进项目 JSON |
| AI 数据边界 | 数据分级、输入输出脱敏、服务商策略检查和敏感字段阻断 |
| 电商数据契约 | 商品、SKU、Listing、店铺、订单、库存、履约、结算、反馈、证据与风险记录 |
| 外贸数据契约 | 企业、企业用户、供应商、工厂、共享目录、报价、发票、付款与同意记录 |
| 工作区隔离 | `工作区 → 项目 → 渠道 → 店铺 → 任务`，隔离平台、站点、模式、归属和授权 |
| 连接器基础 | 只读连接器原语、标准化导入记录和能力元数据；真实写入仍受门禁控制 |
| 聊天优先参考 | 智能体切换、快捷提示、资料入口、消息演示和统一设置抽屉 |
| 公共平台智能体 | 普通聊天自动选择 13 个脱敏知识包；无需先进入项目或扩展配置 |

当前 `0.x` 是 Python 库、测试和浏览器交互参考，是构建真实智能体与运营应用的基础，不是可以绕过确认自动花钱、发布商品、群发客户或发货的成品机器人。

## 基础架构

```text
工作区
  项目
    渠道（平台 + 国家/站点 + 店铺模式 + 归属）
      店铺（独立授权与执行身份）
        任务（模型 + Skill + 工具 + 策略 + 证据 + 审计）
    项目工作流（B2B、研究、创意、财务或供应链）
```

如果只是计划进入某个平台或站点、还没有真实授权店铺，状态必须是 `needs_platform_store`。T One 不能假装已经可以上架、拉单、发货回传、结算、参加活动或投放广告。

## 本地安装与验证

```powershell
git clone https://github.com/alisanmtd-oss/T-one.git
cd T-one
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install .
.\.venv\Scripts\python -m compileall -q ai_ecommerce_director
.\.venv\Scripts\python -m unittest discover -s tests -v
```

请从 `config/` 中的合成示例开始。不要把真实密钥、客户资料、供应商联系人、店铺 ID 或运营证据提交到 Git。

## 公开与私有边界

本仓库由精确文件白名单生成。它不包含真实店铺、客户、线索、联系人、仓库、具体商品活动、恢复会话、截图、浏览器配置、Cookie、在线凭据、私有桌面运行时、浏览器插件或未授权第三方资产。

公开的 `demo/chat-first-workspace.html` 只是合成交互参考，不是私有桌面的源代码，也不包含连接器与执行身份。

## 社区、许可与发布完整性

- 在 [Discussions](https://github.com/alisanmtd-oss/T-one/discussions) 讨论架构、平台知识、外贸流程与实现问题。
- 通过 [Issues](https://github.com/alisanmtd-oss/T-one/issues) 提交可复现 Bug 或范围清晰的功能建议。
- 提交代码前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。
- 安全与隐私问题请使用 GitHub 私密漏洞报告。

T One 采用 [Apache-2.0](LICENSE)。每次公开 staging 都包含 `PUBLIC_RELEASE_AUDIT.json` 和 `SHA256SUMS.json`；只有隐私检查、哈希、安装、测试和 CI 全部通过才接受发布。
