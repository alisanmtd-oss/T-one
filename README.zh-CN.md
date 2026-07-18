# T One

**面向全球电商与外贸 B2B 的开源、本地优先 AI 运营核心。**

[![CI](https://github.com/alisanmtd-oss/T-one/actions/workflows/ci.yml/badge.svg)](https://github.com/alisanmtd-oss/T-one/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-3776AB.svg)](pyproject.toml)
[![Discussions](https://img.shields.io/badge/community-Discussions-7A41C6.svg)](https://github.com/alisanmtd-oss/T-one/discussions)

[English](README.md) | [路线图](ROADMAP.md) | [架构](docs/ARCHITECTURE.md) | [参与贡献](CONTRIBUTING.md) | [安全策略](SECURITY.md)

T One 面向个人创业者、电商团队、开发者、工厂和服务商，目标是让 AI 智能体协助处理跨境电商与外贸业务，同时避免不同店铺、客户、凭据和证据互相串用。

项目覆盖完整运营链条：商品与 SKU、平台 Listing、价格、库存、订单、履约、退货、结算、供应商、工厂、仓库、B2B 企业客户、目录、报价、发票、付款、内容实验和人工审批。它可以作为 Amazon、TikTok Shop、SHEIN、Shopee、Lazada、Walmart、eBay、Etsy、独立站及外贸 B2B 工作流的公共基础，但当前公开版**不会假称这些平台的真实写入授权已经全部接通**。

## T One 可以服务什么业务

### 全球电商运营

- 统一商品、变体、SKU、Listing、价格、库存、订单、履约、退货退款、结算和账号健康证据。
- 按平台、国家站点、店铺模式、店铺归属和授权身份严格隔离。
- 支持构建 AI 选品研究、商品导入、Listing 草稿、运营检查、风险检查和带人工确认的连接器工作流。
- 为事实记录来源和时间，防止 AI 草稿在没有证据时被当成真实运营结果。

### 外贸 B2B

- 建模企业买家、供应商、工厂、企业联系人、共享目录、报价明细、价格表、发票、付款请求、结算和交付假设。
- 联系人隐私信息只保存引用，并配套同意或合法处理依据，避免把隐私数据散落在提示词和项目文件里。
- 为线索筛选、客户时间线、样品与报价交接、订单跟进、付款、发货和售后流程提供结构基础。
- 外联消息、报价发送、付款和其他不可逆商业动作必须经过明确人工确认。

### 供应链、POD 与履约

- 表达供应商、工厂、生产方式、产能、质量、SLA、仓库、库存、入库出库和履约成本假设。
- 把商品与订单记录关联到来源文件、合规材料、反馈和学习事件。
- 支持多项目、多平台、多店铺扩展，同时避免凭据或执行状态意外共享。

### 内容与增长智能

- 记录竞品、Listing、价格、关键词、创意、视频场景、平台规则、实验和效果快照。
- 把观察转成可验证的假设和实验，同时保留版权、证据、可信度和风险边界。
- 为后续图片、视频、本地化、广告、达人和内容到交易归因 Skill 提供安全基础。

## 当前公共核心已经实现

| 能力 | 公开状态 |
|---|---|
| AI 服务商 | 服务商目录、显式模型选择、任务路由元数据和脱敏错误反馈 |
| 本地凭据 | Windows DPAPI 加密存储与凭据引用；不把明文密钥写进项目 JSON |
| AI 数据边界 | 数据分级、输入输出脱敏、服务商策略检查和敏感字段阻断 |
| 电商数据契约 | 商品、SKU、Listing、店铺、订单、库存、履约、结算、反馈、治理、证据和风险记录 |
| 外贸数据契约 | 企业、企业用户、供应商、工厂、共享目录、报价明细、价格表、发票、付款和同意记录 |
| 工作区隔离 | `工作区 -> 项目 -> 渠道 -> 店铺 -> 任务`，隔离平台、国家站点、模式、归属和授权 |
| 连接器基础 | 只读连接器原语、标准化导入记录和能力元数据；真实店铺写入仍受门禁控制 |
| 本地运行 | 原子 JSON 存储、缓存失效、安全示例、测试、发布审计和 SHA256 清单 |

当前 `0.x` 是 Python 库和测试套件，是构建真实智能体和运营应用的基础，不是已经能绕过确认自动花钱、发布商品、群发客户或发货的成品机器人。

## 基础架构

```text
工作区
  项目
    渠道（平台 + 国家站点 + 店铺模式 + 归属）
      店铺（独立授权与执行身份）
        任务（模型 + Skill + 工具 + 策略 + 证据 + 审计）
    项目工作流（B2B、研究、创意、财务或供应链）
```

如果只是计划进入某个渠道、还没有真实授权店铺，状态必须是 `needs_platform_store`。T One 不能假装已经可以上架、拉单、发货回传、结算、参加活动或投放广告。

更多说明见[架构文档](docs/ARCHITECTURE.md)和脱敏后的[品牌运营系统](docs/FEISHU_BRAND_OPERATING_SYSTEM.md)。

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

请从 `config/` 下的合成示例开始。不要把真实密钥、客户资料、供应商联系人、店铺 ID 或运营证据提交到 Git。

## 社区交流

- 在 [Discussions](https://github.com/alisanmtd-oss/T-one/discussions) 自我介绍、讨论架构、平台知识、外贸流程和实现问题。
- 通过 [Issues](https://github.com/alisanmtd-oss/T-one/issues) 提交可复现 Bug 和范围明确的功能建议。
- 提交代码前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。
- 安全和隐私问题使用 GitHub 私密漏洞报告，不要公开真实敏感资料。

欢迎优先贡献：平台与国家站点分类、外贸数据契约、连接器 schema、本地安全 Skill、数据边界测试、文档和合成示例。任何贡献都不得包含真实客户、店铺、供应商、仓库、账号或凭据信息。

## 公开与私有边界

本仓库由精确文件白名单生成，不包含真实店铺、客户、线索、联系人、仓库、具体商品活动、恢复会话、截图、浏览器配置、Cookie、在线凭据、私有桌面端、浏览器插件、飞书原始页面或未授权第三方资产。

公开名称为 **T One**。在视觉资产完成独立权利审核前，仓库只使用文字标识。详见 [BRAND_PUBLIC_BOUNDARY.md](docs/BRAND_PUBLIC_BOUNDARY.md)。

## 许可证与发布完整性

T One 采用 [Apache-2.0](LICENSE)。每次公开 staging 都包含 `PUBLIC_RELEASE_AUDIT.json` 和 `SHA256SUMS.json`；只有隐私检查、哈希、安装、测试和 CI 全部通过才接受发布。
