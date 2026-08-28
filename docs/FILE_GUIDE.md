# 文件说明

- `ai_ecommerce_director/`：正式 Python 服务、桌面渲染、业务运行时、工具与连接器。
- `desktop_app/`：Electron 主进程、预加载桥、Python 桌面桥和安装配置。
- `config/`：公开安全的默认注册表与空白初始配置；不含真实账号或凭据。
- `knowledge_packs/`：Agent/Skill 可复用规则、参考资料和机器合同。
- `scripts/start_local_server_port.py`：源码开发时启动本地服务。
- `scripts/prepare_windows_installer.py`：从已审查公开树构建内置运行时。
- `scripts/verify_public_tree.py`：检查私人路径、密钥和禁止进入公开包的运行数据。
- `tests/`：公开行为、权限、工作区和发行回归测试。
- `PUBLIC_RELEASE_AUDIT.json` 与 `SHA256SUMS.json`：生成公开暂存树时产生的审查与哈希清单。

公开包中不会出现 `data/`、真实 `outputs/`、浏览器配置、账号、店铺、客户、付款、私有对话或凭据文件。`desktop_app/build/` 和 `desktop_app/dist/` 是本机构建产物，不属于源码提交内容。
