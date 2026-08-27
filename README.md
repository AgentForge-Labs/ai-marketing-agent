# AI Marketing Agent

Compliance-first, **0-HITL (Zero Human In The Loop)** SaaS marketing automation system for planning, executing, verifying, and optimizing distribution across a ranked catalogue of 1,000+ channels.

The repository currently contains the product strategy, channel dataset, JSON contracts, and reference adapter specifications. The target runtime is a fully autonomous system: it selects channels, generates platform-native content, executes allowed submissions, verifies outcomes, reacts to engagement, and continuously updates channel scores without requiring an approval queue.

## Authoritative operating model

All project documents use the same operating model:

- **0-HITL by default:** no routine human approval step exists in the execution loop.
- **Automatic submit:** when a channel policy and adapter permit the action, the runner submits automatically.
- **Autonomous quarantine:** uncertainty, policy conflict, unsupported access controls, or low confidence does not create a human-approval task; the job is blocked/quarantined and re-evaluated by discovery/policy services.
- **1,000+ personas:** the Persona Engine supports large-scale brand/campaign personas, but account creation and use must respect each platform's account, identity, disclosure, and multi-account rules. A persona is not permission to impersonate a real person.
- **Anti-detection/evasion layer:** this means anomaly-aware pacing, duplicate suppression, content diversity, session stability, rate-limit compliance, and automatic cooldown. It must not bypass CAPTCHAs, access controls, bans, or platform security mechanisms.
- **Engagement Bot:** autonomous replies and follow-up are allowed where platform policy permits and where the interaction is relevant to the brand/account context. Artificial likes, votes, reviews, coordinated amplification, or deceptive engagement are prohibited.
- **API-first:** official API/OAuth is preferred whenever available; browser automation is used only when allowed and appropriate.
- **Fail closed:** uncertain outcomes are never blindly retried. Idempotency and success assertions run before any retry.
- **Secrets stay out of Git:** passwords, cookies, OAuth tokens, TOTP secrets, proxy credentials, and Playwright `storageState` are stored in an approved secret store, never in the repository.

## Dataset

`data/saas_marketing_1000_channels_ranked - 1000 Channels.csv` is the canonical machine-readable 1,000-channel catalogue. The tracked XLSX is a convenience snapshot and must not be treated as the runtime source of truth; risk/enforcement decisions are read from the CSV.


The canonical CSV also contains action-specific automation-risk fields (`Observed Automation Risk`, browser/API risk, preferred route, runtime mode, safe actions, disabled actions, session strategy and evidence). See [`docs/05-platform-automation-risk-matrix.md`](docs/05-platform-automation-risk-matrix.md).

Observed automation-risk distribution (reviewed 2026-08-27): **748 Low / 172 Moderate / 68 High / 12 Very High**.

Current distribution:

- P0: 50 channels
- P1: 150 channels
- P2: 300 channels
- P3: 500 channels
- High automation fit: 720 channels
- Human-review metadata in the source dataset: 280 channels
- Runtime-preflight URL confidence: 774 channels

The `Human Review` column is **source/research metadata**, not an execution-mode switch. Runtime behavior is determined by the Policy Registry and Autonomous Decision Engine. A channel that cannot be executed safely and policy-compliantly is automatically quarantined rather than sent to an approval queue.

Spreadsheet strategy text is research input, not executable instruction. Runtime executes only versioned and validated adapter contracts.

## Target architecture

```text
Channel Dataset / Product Profile
        ↓
Channel Importer + Site Registry
        ↓
Policy Registry + Policy Crawler
        ↓
Persona Engine + Content Core
        ↓
Autonomous Decision Engine
        ↓
Distribution Orchestrator
        ↓
API Adapter or Playwright Adapter
        ↓
Automatic Submit
        ↓
Assertion + Idempotency + Audit
        ↓
Engagement Bot + Analytics
        ↓
Score Feedback / Next Best Action
```

## Execution modes

The active runtime modes are:

- `auto_full`: policy-valid, deterministic, idempotent action; execute and verify automatically.
- `auto_with_verification`: execute automatically with stronger pre/post assertions.
- `auto_quarantine`: do not execute; refresh policy/discovery data and retry only when the blocking condition is resolved.

The schema exposes only autonomous execution modes: `browser_auto`, `api_auto`, and `auto_full`. Approval/manual execution modes are not part of the current contract.

## Repository structure

```text
data/       Ranked 1,000-channel research dataset

docs/       Identity, channel, automation, and implementation specifications
schemas/    JSON Schema contracts
examples/   Example product, identity, and adapter documents
```

## Documents

- [Identity strategy](docs/01-identity-strategy.md)
- [Channel and content strategy](docs/02-channel-strategy.md)
- [Automation architecture](docs/03-automation-architecture.md)
- [Implementation roadmap](docs/04-implementation-roadmap.md)
- [Security policy](SECURITY.md)

## First implementation milestone

The first production milestone is not “run all 1,000 channels.” It is a deterministic autonomous pilot:

1. import and normalize the channel catalogue;
2. preflight current policy/auth/URLs;
3. implement the DB, policy engine, idempotency and audit layers;
4. implement dry-run and assertion-capable adapters;
5. enable automatic submit only for verified, policy-compatible pilot channels;
6. validate at least three clean end-to-end runs per adapter family;
7. expand by measured conversion, reliability, and policy-health scores.
