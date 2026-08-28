# T One

**[中文说明](README.zh-CN.md)**

T One is a local-first desktop workspace for multi-project commerce operations. This repository now ships the same formal Python/Electron runtime used by T One, including its project/task workspaces, capability marketplace, connector layer, history context, and seller-mode surfaces. It no longer substitutes a synthetic browser demo for the product.

## Install on Windows

Download the latest `T-One-Setup-0.5.9.exe` from GitHub Releases, double-click it, choose an installation folder, and finish the guided setup. The installer contains the local runtime; ordinary users do not need Python, Git, or Node.js.

On first launch, T One creates an isolated workspace under the current Windows user profile. No developer-specific absolute path is embedded in the package.

## CLI edition

After installation, open `T One CLI` from the Start menu or run `T-One-CLI.cmd` from the installed `resources` directory. `tone status`, `tone workspace list`, `tone workspace show`, `tone fs`, `tone process`, `tone shell`, `tone mouse`, `tone keyboard`, `tone window`, and `tone browser` expose the local workspace and the computer surfaces allowed by the current Windows access token. Mutating or execution commands require `--yes`. Administrator access is available only after an explicit Windows UAC confirmation through `tone elevate`; the CLI does not bypass UAC or claim permissions it has not received.

## Included product surfaces

- Formal Chinese Electron desktop application.
- Project, task, platform, country/site, store mode, store account, and execution-identity isolation.
- Stable project/task folders for inputs, attachments, knowledge, memory, runs, results, and receipts.
- Conversation/task history, dashboards, seller modes, and scoped operating context.
- A categorized Agent / Skill / MCP / CLI marketplace with project-level assignment.
- Open registration for local tools, CLIs, MCP servers, browser tools, and external agents.
- Local AI collaboration routes including Codex CLI, Gemini, and WorkBuddy/CodeBuddy candidates.
- Windows mouse, keyboard, default-browser, and controlled-browser entry points.

The repository contains no live credentials, accounts, stores, browser profiles, customer records, private conversations, or payment data. An item marked unverified or requiring setup has not been removed; it needs configuration in the user's own workspace. Unverified candidates are never presented as connected.

## Developer setup

```powershell
git clone https://github.com/alisanmtd-oss/T-one.git
cd T-one
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e .
python scripts/start_local_server_port.py 8767
```

For Electron development:

```powershell
cd desktop_app
npm install
npm start
```

The Windows installer must be built from a generated, audited public staging tree. `scripts/prepare_windows_installer.py` intentionally refuses to package an unaudited private workspace.

## Source completeness

The formal desktop workspace runtime is distributed as readable Python source. Public builds reject `.pyc` bytecode and use an exact-file allowlist to exclude local accounts, credentials, browser profiles, runtime databases, store records, outputs, and private conversations.

See [capability status](docs/CAPABILITY_STATUS.md), [architecture](docs/ARCHITECTURE.md), and the [file guide](docs/FILE_GUIDE.md).

License: [Apache License 2.0](LICENSE).
