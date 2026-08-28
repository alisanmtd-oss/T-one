# T One 中文版

T One 是本地优先的跨境经营桌面工作台。这个仓库发布的是正式 T One 的 Python 服务、Electron 桌面程序、能力市场、项目/任务工作区和连接器运行层，不再使用过去的简化网页壳。

[English](README.md) · [功能状态](docs/CAPABILITY_STATUS.md) · [文件说明](docs/FILE_GUIDE.md) · [路线图](ROADMAP.md)

## 普通用户：直接安装

1. 在 GitHub Releases 下载最新的 `T-One-Setup-0.5.9.exe`。
2. 双击安装包。
3. 选择安装位置，按提示完成安装。
4. 从桌面或开始菜单打开 `T One`。

安装包已经带有本地运行时。普通用户不需要先安装 Python、Git、Node.js，也不需要打开源码文件夹找入口。首次打开会在当前 Windows 用户目录建立独立工作区，不会把开发者电脑路径写进你的安装。

## CLI 版本

安装后可从开始菜单打开 `T One CLI`，或在 PowerShell 中运行安装目录 `resources` 下的 `T-One-CLI.cmd`。常用入口：

```powershell
tone status
tone workspace list
tone workspace show --project 项目编号
tone workspace show --task 任务编号
tone fs list C:\
tone process list
tone window list
tone harness status
tone harness prepare --project 项目编号 --yes
tone harness web --task 任务编号 --yes
```

文件修改、程序执行、鼠标、键盘、窗口聚焦和浏览器打开等动作必须带 `--yes`。CLI 使用启动它的 Windows 访问令牌：普通打开是当前用户权限；确实需要管理员权限时运行 `tone elevate ...`，由 Windows 显示 UAC 后再提升。它不会绕过 UAC，也不会把未获得的管理员权限显示成已获得。

## 这次公开的正式功能

- 正式中文 Electron 桌面界面，而不是浏览器演示页。
- 项目、平台、国家/站点、店铺模式、店铺账号、任务和执行身份分开管理。
- 每个项目和任务有稳定本地文件夹，供 AI、Skill、CLI 和 MCP 快速找到资料、记忆、运行结果与回执。
- 新建任务后按“明确目标 → 选择能力 → 开始执行 → 查看结果”继续；选择能力会返回原任务并把状态从“待配置”推进到“待执行”。
- 对话/任务树、历史上下文、实时大盘、全模块大屏和卖家模式。
- 能力市场按 `Agent / Skill / MCP / CLI` 分类，可搜索、筛选、安装或配置，并可按项目搭配。
- 开放工具注册，可增加本地程序、CLI、MCP、浏览器工具和外部 Agent；未验证的连接不会显示成“已连接”。
- Codex CLI、Gemini、WorkBuddy/CodeBuddy 等本地或外部 AI 的项目级协作入口。
- Windows 鼠标、键盘、默认浏览器和受控浏览器能力入口。
- DeepSeek 官方开源 Harness 可作为本机底座；在能力市场选择项目或任务即可启用，共用一套运行时，不把 6 GB 源码复制进每个项目。
- 商品、内容、广告、财务、B2B、数据采集、店铺运营和知识包能力框架。

仓库不附带任何真实账号、Token、Cookie、店铺数据、浏览器配置、客户资料、历史对话或付款资料。安装后看到“待配置/未验证”是正常状态，不代表功能被删掉；用户可在自己的项目范围内连接所需工具。

## 能力状态怎么看

| 状态 | 含义 |
| --- | --- |
| `已实测` | 正式桌面程序或本地运行时已走通对应路径。 |
| `已实现，待配置` | 源码与界面已存在，需要用户自己的工具、账号或凭据。 |
| `候选，未验证` | 可以添加或研究，但尚未在当前 T One 安装中验证。 |
| `不可自动调用` | 软件已检测到，但没有可用的 CLI/API 自动回传通道。 |

页面、按钮、测试或工具名称本身不等于已经连接。T One 会把平台、站点、店铺、账号和执行身份分别记录，不按“中国 AI / 美国 AI”之类的地域标签拆分工具。

## 开发者运行

普通用户请使用安装包。只有需要修改源码时才执行：

```powershell
git clone https://github.com/alisanmtd-oss/T-one.git
cd T-one
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e .
python scripts/start_local_server_port.py 8767
```

桌面开发：

```powershell
cd desktop_app
npm install
npm start
```

生成 Windows 安装包前必须先生成并审查脱敏公开树；`scripts/prepare_windows_installer.py` 会拒绝从含私人运行数据的工作区直接打包。

## 目录

| 路径 | 用途 |
| --- | --- |
| `ai_ecommerce_director/` | 正式 Python 服务、业务能力、桌面渲染和连接器运行层 |
| `desktop_app/` | Electron 桌面壳、桥接和 Windows 安装配置 |
| `config/` | 可公开的默认注册表与空白初始配置 |
| `knowledge_packs/` | 可复用的 Skill、规则、参考资料和机器合同 |
| `scripts/` | 本地启动、安装构建和公开树验证工具 |
| `tests/` | 行为、权限、工作区与发行回归测试 |

## 当前源码说明

正式界面运行层已经以可读 Python 源码发布。公开构建会拒绝任何 `.pyc` 字节码进入源码包，并通过精确文件清单排除本机账号、凭据、浏览器配置、运行数据库、店铺资料、输出和历史对话。

## 数据和执行边界

- 用户数据默认保存在本机工作区。
- 凭据只保存引用或进入本机凭据存储，不写入公开仓库。
- 店铺写入、投放、付款、发货、退款、OAuth、MFA 和外联由具体项目/店铺授权控制。
- 新安装不会自动连接、发布、付款或操作任何外部平台。

许可证：[Apache License 2.0](LICENSE)。
