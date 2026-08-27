# AI Marketing Agent

Compliance-first, **0-HITL (Zero Human In The Loop)** SaaS marketing automation system for planning, executing, verifying, and optimizing distribution across a ranked catalogue of 1,000+ channels.

The repository contains the product strategy, channel dataset, JSON contracts, reference adapter specifications, and the first executable channel-risk routing runtime. The target runtime is a fully autonomous system: it selects channels, generates platform-native content, executes allowed submissions, verifies outcomes, reacts to engagement, and continuously updates channel scores without requiring an approval queue.

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


The canonical CSV contains both coarse platform-context fields and the canonical **action × execution-medium** risk fields. Runtime routing uses action-specific columns for public browse, authenticated browse, data collection, own content submit/post, comment/reply, DM/outreach, vote/like/follow, and review/rating. Each action cell starts with the action's main risk and then preserves per-medium risk for `public_http`, `official_api`, `cli_sdk`, `webhook_bot`, `unified_api`, `local_browser_agent`, and `browser_extension`. The main risk is the **minimum risk among actually supported media**. See [`docs/05-platform-automation-risk-matrix.md`](docs/05-platform-automation-risk-matrix.md).

The older observed platform-risk distribution (reviewed 2026-08-27) remains contextual metadata: **748 Low / 172 Moderate / 68 High / 12 Very High**. It must not override a lower-risk action route; for example, LinkedIn post publishing is `Low` through the official Posts API even though browser outreach is Critical.

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
scripts/    Deterministic dataset risk-matrix generator
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

## Executable risk-router runtime

The repository now includes a zero-dependency Python runtime foundation under `src/ai_marketing_agent/`. It strictly imports the canonical CSV, validates all 8 action-risk cells for every channel, recomputes the minimum supported-medium risk, verifies the declared `best=` route, and fails closed on malformed or unknown data.

The default and maximum production autonomous threshold is **Moderate**; it may only be tightened to `Low`, not raised above Moderate. A requested action whose best supported route is `High`, `Very High`, or `Critical` is returned as `auto_quarantine`; this is independent of the old coarse platform-level risk. Thus LinkedIn `post` executes as `Low` through `official_api`, while LinkedIn `dm` is quarantined as `Critical`. Product Hunt browse/data is Low, owned submit is Moderate, and vote automation is Critical/quarantined.

Run the full runtime tests:

```bash
python3 -m unittest discover -s tests -v
```

Inspect one route without executing any external action:

```bash
python3 scripts/route_channel_action.py linkedin.com post
python3 scripts/route_channel_action.py producthunt.com vote
```

The router emits `api_auto`, `browser_auto`, `auto_full`, or `auto_quarantine`. Unknown actions, missing routes, malformed risk cells, unknown risk values, inconsistent aggregate risk, or an unsupported risk-model version fail closed.

## Prototype persistence and URL preflight

The executable foundation now includes a **SQLite prototype/test persistence layer**. Production architecture still targets PostgreSQL; SQLite is intentionally limited to local development, deterministic tests, and the first runtime prototype.

`database/migrations/001_runtime_foundation.sql` creates:

- `site_registry` — normalized canonical channel records keyed by rank, with domain lookup index;
- `channel_action_risk` — the 8 normalized action-risk records per channel;
- `risk_decision` — append-only audit records for every routed action;
- `url_preflight_observation` — append-only observations for homepage/register/login reachability;
- `schema_migrations` — checksum-tracked migration history.

The importer is idempotent: a second import of the same 1,000-channel CSV changes **zero** channel/action-risk rows. Changed source rows are updated by source hash while historical risk decisions remain immutable.

Initialize/import a prototype database and inspect an audited decision:

```bash
python3 scripts/runtime_db.py --db /tmp/ai-marketing-agent.sqlite3 import
python3 scripts/runtime_db.py --db /tmp/ai-marketing-agent.sqlite3 route linkedin.com post
```

Run a selected URL preflight:

```bash
python3 scripts/runtime_db.py --db /tmp/ai-marketing-agent.sqlite3 preflight producthunt.com homepage --timeout 5
```

Preflight is deliberately read-only and bounded: only HTTP(S) is accepted, credentials and non-default ports are rejected, private/loopback/link-local/reserved network targets are blocked, every redirect is revalidated, no account session/cookie is attached, no form is submitted, and the response body is not consumed. The request uses a small ranged GET so sites that do not support `HEAD` can still be classified as reachable, redirected, HTTP error, network error, or blocked.
