# T One

**面向多项目、多平台、多店铺运营的本地优先电商智能体公共核心。**

[English](README.md) | [路线图](ROADMAP.md) | [参与贡献](CONTRIBUTING.md) | [安全策略](SECURITY.md) | [Apache-2.0 许可证](LICENSE)

T One 是面向 AI 辅助电商运营、经过脱敏的社区基础层。它提供 AI 模型配置、本地凭据引用、模型数据边界、电商数据契约、连接器基础能力、项目层级和原子化本地存储。

它不是把私有生产系统整包公开，也不是一个只有页面的 ERP 外壳。公共版本首先解决可以复用、可以测试、可以安全扩展的基础问题。

## 已包含

- 多 AI 服务商与模型选择配置。
- Windows DPAPI 本地加密凭据存储。
- 模型调用前的数据分级、脱敏和服务商策略检查。
- 商品、库存、Listing、订单、履约、结算和反馈数据结构。
- `工作区 -> 项目 -> 渠道 -> 店铺 -> 任务` 层级。
- 只读连接器基础能力和标准化数据记录。
- 原子 JSON 存储、缓存控制和单元测试。
- 不含真实店铺或客户信息的安全示例配置。

## 明确不公开

- 真实店铺、账号、客户、供应商、线索、仓库、地址和联系人。
- 恢复聊天、运营证据、截图、浏览器配置、Cookie 和会话。
- 具体商品活动、平台实操脚本、私有桌面端和浏览器插件。
- API Key、OAuth Token、验证码、银行资料、身份文件和密码。
- 私有飞书页面、原始课程和品牌运营资料。

## 基础结构

```text
工作区
  项目
    渠道（平台 + 国家站点 + 店铺模式 + 归属）
      店铺（独立授权与执行身份）
        任务（模型 + Skill + 工具 + 策略 + 审计上下文）
```

每个可执行店铺必须按租户、工作区、项目、平台、国家站点、店铺模式、归属和店铺 ID 隔离。只有渠道意向、没有真实授权店铺时，状态必须是 `needs_platform_store`，不能假装已经可以上架、拉单、发货回传、结算、活动或广告投放。

## 本地验证

```powershell
git clone https://github.com/alisanmtd-oss/T-one.git
cd T-one
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install .
.\.venv\Scripts\python -m compileall -q ai_ecommerce_director
.\.venv\Scripts\python -m unittest discover -s tests -v
```

配置请从 `config/` 下的示例文件开始。不要把真实密钥、客户数据或店铺信息写进 Git 仓库。

## 社区方向

优先欢迎：连接器数据结构、平台与国家站点分类修正、数据边界测试、文档和小型本地 Skill。涉及店铺写入、广告花费、付款、发货和账号安全的自动化，必须先具备审批、幂等、限额和审计能力。

当前为 `0.x` 社区预览版，采用 Apache-2.0 许可证。只有脱敏审计无发现，且公开树通过测试、隐私检查和最终复核后，才会正式发布。
