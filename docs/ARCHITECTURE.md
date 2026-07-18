# Architecture

## Design principles

1. **Local first:** operating data and credentials stay on the operator's machine unless a connector is explicitly authorized.
2. **Fail closed:** unknown dependencies, stores, permissions, or data classes do not become executable capabilities.
3. **Identity isolation:** authorization is scoped to one concrete store identity and route.
4. **Evidence before action:** external facts and current platform state must be observed before a write is proposed.
5. **Approval by consequence:** higher-impact actions require stronger limits, confirmation, idempotency, and audit evidence.

## Workspace model

```text
workspace
  projects[]
    channels[]
      stores[]
        tasks[]
    workstreams[]
```

A channel expresses an intended operating route. A store represents a real executable authorization. A task combines a store or workstream context with a model, skills, tools, policy, and audit trail.

## Route identity

The minimum commerce route is:

```text
platform:country-or-site:store-mode:ownership:store-id
```

Regional groupings are useful for reporting but cannot replace a country/site in store binding, activity rules, advertising accounts, or authorization checks.

## AI boundary

Model requests flow through:

```text
task context -> data classification -> redaction -> provider policy -> model request -> usage/audit record
```

The provider never receives a credential value from project JSON. Configuration stores only a credential reference; the secret remains in the local credential backend.

## Connector boundary

Read-only adapters normalize external data into stable records. A future write adapter must add:

- scoped authorization;
- idempotency key;
- correlation and audit IDs;
- before/after state hashes;
- rate, spend, and quantity limits;
- approval policy;
- verifiable result or rollback evidence.

## Public boundary

This repository contains contracts and local-first primitives. Private production UI, browser automation, marketplace execution, live operating records, and recovered context are intentionally outside the first public release.

