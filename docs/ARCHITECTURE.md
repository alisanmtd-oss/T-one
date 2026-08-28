# T One architecture

## Runtime

```text
Electron desktop
  -> localhost authenticated session
  -> bundled Python server + desktop bridge
  -> local workspace
       config/
       projects/<project>/
       tasks/<task>/
       logs/
       outputs/
```

The release installer carries the Electron shell and a bundled Python runtime. A first launch copies only public-safe initial configuration into the current user's workspace. Existing workspace files are not overwritten during later launches.

## Project and task model

```text
project
  platform + country/site
  store bindings
  project AI/Agent/Skill/MCP/CLI selection
  tasks
    inputs + attachments
    memory + history
    runs + results + receipts
```

Platform, country/site, store mode, ownership, account and execution identity are separate fields. A marketplace tool can be general, project-scoped, or store-scoped; it does not gain access to unrelated projects merely because it is installed.

## Capability marketplace

The marketplace is one surface with four first-class types: Agent, Skill, MCP and CLI. Items are organized by purpose, not by the country of an AI provider. Connection status is explicit: installed, configured, verified, unavailable, or candidate.

## Local and external execution

Model or tool requests flow through the selected project/task context. Credentials remain in local credential storage or user-controlled environment references. External writes are separate from read, analysis and draft operations and require the relevant project/store authorization.

## Public boundary

The public tree includes the formal desktop and backend source selected by an exact-file manifest. It excludes compiled Python bytecode, runtime databases, credentials, accounts, store/customer records, browser profiles, outputs and private histories.
