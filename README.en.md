# T One Community

T One is a local-first operating workspace for multi-project and multi-store commerce teams.

[Download the Windows installer](https://github.com/alisanmtd-oss/T-one/releases/latest) · [简体中文](README.md) · [Capability status](docs/CAPABILITY_STATUS.md)

The public repository contains a sanitized Python community core, public knowledge packs, and an installable local-first desktop workspace. The Chinese desktop app persists project/task folders and history, and includes a truthful capability market organized by Agent, Skill, MCP, and CLI.

The public build does not ship live store credentials, customer data, browser profiles, private connectors, computer-control runtime, or unrestricted external actions. MCP and CLI entries remain visibly unconfigured or undetected until a user supplies and verifies their own environment.

## Developer setup

```powershell
git clone https://github.com/alisanmtd-oss/T-one.git
cd T-one
python -m venv .venv
.\.venv\Scripts\python -m pip install .
.\.venv\Scripts\python -m unittest discover -s tests -v
```

Apache-2.0. See [LICENSE](LICENSE), [CONTRIBUTING.md](CONTRIBUTING.md), and [SECURITY.md](SECURITY.md).
