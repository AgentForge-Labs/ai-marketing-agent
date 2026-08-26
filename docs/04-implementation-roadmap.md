# Implementation Roadmap — 0-HITL

This roadmap implements the architecture in `03-automation-architecture.md`. Every phase assumes the same target model: **0-HITL, automatic submit, 1,000+ persona support, anomaly-aware Evasion Layer, and autonomous Engagement Bot**. No routine human approval queue is part of the target runtime.

## Phase 0 — Repository and contracts

- Create TypeScript/Node.js workspace and package boundaries.
- Add package manager lockfile and `tsconfig`.
- Define runtime configuration and environment validation.
- Add database migration framework.
- Add CI: lint, typecheck, schema tests, unit tests, integration tests, security scans.
- Make `docs/03-automation-architecture.md` the canonical architecture contract.
- Remove approval/manual execution modes from active schemas; keep only autonomous execution contracts.
- Add schema/fixtures tests for all JSON examples.

**Exit criteria:** a clean checkout can install, validate all contracts, run tests, and build deterministically.

## Phase 1 — Data and policy foundation

- Implement the CSV/XLSX Channel Importer, including the metadata rows before the real CSV header.
- Normalize all 1,000 channel records into `site_registry`.
- Implement URL/domain normalization and validation.
- Implement runtime preflight for current register/login/submit URLs.
- Implement Policy Registry and versioned policy records.
- Add policy crawler for API/OAuth availability, allowed actions, disclosure, account rules, and quotas.
- Implement `auto_full`, `auto_with_verification`, `auto_quarantine` decision primitives.

**Exit criteria:** every channel has a normalized registry record, policy freshness state, and deterministic autonomous execution classification.

## Phase 2 — Persistence, queue, audit and idempotency

- Implement PostgreSQL production schema and migrations.
- Add tenant-aware records for sites, policies, personas, campaigns, contents, adapters, jobs, submissions, risk decisions, engagement events, conversions, and audit events.
- Implement durable queue leases and worker recovery.
- Implement retry/backoff and dead-letter/quarantine behavior.
- Implement deterministic idempotency keys.
- Implement append-only audit trail.
- Add redaction for logs, screenshots, traces, and error payloads.

**Exit criteria:** duplicate external actions are prevented and every action/decision is fully attributable.

## Phase 3 — Persona Engine and identity registry

- Implement 1,000+ persona definitions with voice, locale, timezone, channel eligibility, disclosure profile, and content history.
- Implement account/session references without storing secrets in Git or plaintext DB columns.
- Integrate Vault/KMS/managed secret provider abstraction.
- Implement OAuth token refresh and authorized TOTP generation.
- Enforce channel account/multi-account policy during persona-to-account mapping.
- Implement automatic session health checks and quarantine on access challenges.

**Exit criteria:** the orchestrator can select an eligible persona/account/session autonomously while respecting channel identity policy.

## Phase 4 — Content Core

- Implement verified Product Profile ingestion.
- Implement brand voice and persona voice layers.
- Add platform-native content templates/structured outputs.
- Add claim verification against product facts.
- Add required disclosure injection.
- Add semantic similarity/fingerprint checks.
- Add UTM/tracking metadata generation.
- Persist prompt/model/version provenance.

**Exit criteria:** the system can generate policy-valid, non-duplicate, fact-grounded channel content without human review.

## Phase 5 — Adapter compiler and dry-run runtime

- Implement bounded adapter DSL compiler; no free-form JavaScript or `eval`.
- Implement Playwright primitives for navigation, fields, uploads, actions, waits, and assertions.
- Implement official API adapter runner.
- Implement dry-run mode that fills without submit.
- Capture redacted before/filled screenshots and sanitized form contracts.
- Implement form fingerprinting and drift detection.
- Implement autonomous discovery/self-healing candidate generation.
- Promote adapter changes only after schema validation, dry-run, confidence threshold, and regression gates.

**Exit criteria:** pilot adapters can discover/fill/assert deterministically and drift moves to autonomous remap/quarantine rather than uncontrolled execution.

## Phase 6 — Automatic submit and verification

- Enable automatic submit for policy-valid pilot adapters.
- Run pre-submit idempotency checks.
- Implement multi-signal success assertion.
- Implement remote object lookup before retrying ambiguous outcomes.
- Implement automatic email verification for authorized accounts.
- Implement automatic TOTP where authorized.
- Treat CAPTCHA/security challenges as `auto_quarantine`, not bypass opportunities.
- Store resulting listing/post IDs and URLs.

**Exit criteria:** at least five allowed pilot channels complete three consecutive autonomous submit-and-verify E2E runs without duplicate actions.

## Phase 7 — Evasion Layer / anomaly controller

Implement the production-safe Evasion Layer:

- rate-limit/throttling detection;
- failure burst detection;
- duplicate-content detection;
- form drift detection;
- session expiry/auth-loop detection;
- CAPTCHA/security challenge detection;
- policy drift detection;
- automatic concurrency reduction;
- account/channel cooldown;
- adapter-family pause;
- policy/preflight refresh;
- autonomous quarantine.

Explicitly do **not** implement CAPTCHA bypass, biometric-human simulation, ban evasion, stealth/fingerprint spoofing, or unauthorized identity/IP rotation to defeat platform controls.

**Exit criteria:** anomalies reduce or stop execution automatically before they become repeated failures or policy violations.

## Phase 8 — Engagement Bot

- Implement event ingestion for comments, replies, inbound messages, listing questions, and launch-thread updates where supported.
- Fetch thread/account context.
- Run consent/policy gate.
- Generate persona/brand-consistent response.
- Validate claims/disclosure/similarity/rate limits.
- Execute eligible replies automatically.
- Persist response linkage and engagement outcome.
- Quarantine unsupported or ambiguous interactions.

Do not implement artificial likes/upvotes, fabricated reviews, controlled-account amplification, mass unsolicited DMs, or unrelated mass commenting.

**Exit criteria:** supported inbound/owned-content engagement flows run autonomously end-to-end with audit and policy enforcement.

## Phase 9 — Distribution Orchestrator

- Implement campaign objectives and constraints.
- Implement channel-product fit scoring.
- Implement expected-value/ROI-aware next-best-action selection.
- Implement scheduling from timezone, quota, cooldown, session health, and content freshness.
- Add campaign pause/resume/cancel and tenant kill switch.
- Support parallel workers with per-channel/account concurrency rules.

**Exit criteria:** the agent selects what to do next instead of blindly iterating over the 1,000-row ranking.

## Phase 10 — Analytics and learning loop

- Capture submission/publish/verification state.
- Capture referral/click/impression signals where APIs permit.
- Integrate conversion events from product analytics/GA4/PostHog/webhooks as applicable.
- Calculate channel conversion, reliability, cost, and ROI.
- Update `channel_scores` from real outcomes.
- Feed results into next-best-action selection.

**Exit criteria:** static channel rank becomes a prior; real campaign outcomes continuously change execution priority.

## Phase 11 — SaaS product layer

Implement end-user application surfaces:

- onboarding and product profile;
- campaign wizard;
- channel catalogue and eligibility state;
- connected accounts;
- persona management;
- generated content;
- execution/calendar view;
- published URLs/results;
- quarantine/health view;
- analytics and ROI;
- audit history;
- settings/integrations.

Implement SaaS foundation:

- tenants/organizations;
- users and memberships;
- RBAC;
- tenant isolation;
- invites;
- API keys;
- usage metering;
- subscription/plan limits;
- admin dashboard.

**Exit criteria:** a tenant can configure a product/campaign and observe autonomous execution and outcomes without operating the underlying workers manually.

## Phase 12 — Scale to the full catalogue

Expansion gate for each new adapter family/channel:

- policy is current;
- preflight URL/auth state is current;
- adapter schema validates;
- dry-run passes;
- idempotency works;
- success assertion is deterministic;
- security/redaction tests pass;
- three clean pilot E2E runs pass;
- no duplicate submission;
- no access-control bypass;
- measurable business outcome is captured where possible.

Roll out progressively from verified P0/P1 channels, then P2/P3 based on actual conversion and operational health.

## Definition of done

The project reaches its target state when:

- the agent operates 0-HITL for all eligible actions;
- automatic submit is deterministic and idempotent;
- 1,000+ persona definitions can be managed and policy-mapped;
- Evasion Layer autonomously throttles/quarantines anomalies without defeating platform controls;
- Engagement Bot handles eligible conversations autonomously without artificial engagement manipulation;
- all external actions are policy-versioned and auditable;
- tenant and admin UX expose status, results, costs, and quarantine reasons;
- channel ranking learns from real conversion/reliability data;
- CI/E2E regression gates protect every adapter/runtime change.
