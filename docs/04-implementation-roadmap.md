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

**Current status (2026-08-27):** the strict canonical CSV importer, action×medium `PlatformRiskRouter`, SQLite prototype `site_registry` persistence, append-only risk audit, and bounded URL preflight foundation are implemented and regression-tested. Production PostgreSQL persistence and the versioned Policy Registry/policy crawler remain pending.

- Implement the canonical CSV Channel Importer, including the metadata rows before the real CSV header. Treat XLSX only as a convenience/export snapshot. **Implemented.**
- Normalize all 1,000 channel records into `site_registry`. **Implemented in the SQLite prototype with idempotent source-hash upserts.**
- Implement URL/domain normalization and validation. **Implemented for canonical HTTP(S) URLs and preflight targets.**
- Implement runtime preflight for current register/login/submit URLs. **Bounded public-network reachability foundation implemented; policy/API capability discovery remains pending.**
- Implement Policy Registry and versioned policy records.
- Add policy crawler for API/OAuth availability, allowed actions, disclosure, account rules, and quotas.
- Implement `api_auto`, `browser_auto`, `auto_full`, and `auto_quarantine` decision primitives. **Risk-router decision mapping implemented; external adapter execution remains pending.**

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

## Phase 5B — Agentic Browsing & CAPTCHA Ensemble (vault-backed, policy-gated)

- `services/biometric-mouse`: `wassim-sayah/biometric-mouse` `ai_mouse/` projeye `services/biometric-mouse/ai_mouse/` olarak kopyalanır; `scripts/record_mouse.py` + `mouse_dojo/index.html` ile 1 personel gerçek el kaydı, `train_mouse_model.py` ile `profile/mouse_profile.json` (`vault://mouse/profile/mouse_profile.json`), `visualize.py` 3×3 grey=gerçek vs colored=AI doğrulama. 30dk %8 varyans.
- `services/captcha-ensemble`: `2captcha-python` `twocaptcha` (`pip install 2captcha-python`) + `aydinnyunus/ai-captcha-bypass` `ai_utils.py`/`puzzle_solver.py` (`services/captcha-lmm/`) + `teal33t/captcha_bypass` Buster `0.7.2` xpi (`services/buster/`). `C:\Users\ahmet\Downloads\DIGER\sunucular` içindeki `openai_platform.txt` ve `2captcha` anahtarı `vault://llm/openai/apiKey` ve `vault://captcha/2captcha/apiKey` olarak taşınır; ham secret repoda yok.
- `services/semantic-browser`: `visser23/semantic-browser` `pip install semantic-browser[managed]` + `semantic-browser install-browser` + `serve --host 127.0.0.1 --port 8765` (`vault://semantic/browser/token`). `schemas:semanticBrowser.enabled=true` ile drift repair'de Vision-LLM ile birlikte.
- Her adapter `captcha.policy=auto_ensemble` ile test edilir: önce 2captcha, fail → LMM, fail → Buster. Başarı `successful_solves/*.gif` benzeri kanıtla audit'e maskeli loglanır (token değil, tip/süre/sonuç). `schemas/site-adapter.schema.json:captcha` + `biometricMouse` + `semanticBrowser` ile şemada zorunlu.
- **Politika:** Bu ensemble per `schemas/policy-contract.json` (v1.0.0, `maxAutonomousRisk: High`) `Low`/`Moderate`/`High` per-action için otomatik akışın parçasıdır; `Very High`/`Critical` doğrudan `auto_quarantine`. Ban/kısıtlama sonrası kimlik/IP değiştirerek erişim engelini aşmak için kullanılmaz. `SECURITY.md` “Agentic Human-like Stack” bölümüne bak.

**Exit criteria:** `turnstile` + `recaptcha_v2` + `datadome` 3 tipte agentic çözüm kanıt üretir ve `dead-pool` tetiklenmeden 10 ardışık submit başarılıdır; `management` review'de `audit_log.detail_json.captcha` maskeli ve `vault://` referanslı.

## Phase 6 — Automatic submit and verification

- Enable automatic submit for policy-valid pilot adapters.
- Run pre-submit idempotency checks.
- Implement multi-signal success assertion.
- Implement remote object lookup before retrying ambiguous outcomes.
- Implement automatic email verification for authorized accounts.
- Implement automatic TOTP where authorized.
- Solve CAPTCHA/security challenges on `Low`/`Moderate`/`High` per-action via `auto_ensemble` per `schemas/policy-contract.json`; `Very High`/`Critical` or ensemble exhaustion go to `auto_quarantine`.
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

Implement CAPTCHA solving (`auto_ensemble`) and biometric-human input shaping per `schemas/policy-contract.json` for `Low`/`Moderate`/`High` per-action. Explicitly do **not** implement ban/suspension evasion via identity/IP rotation or submit through explicitly blocked endpoints after a platform block.

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
- audited CAPTCHA solving only (`Low`/`Moderate`/`High` via `auto_ensemble`); no ban evasion or blocked-endpoint submission;
- measurable business outcome is captured where possible.

Roll out progressively from verified P0/P1 channels, then P2/P3 based on actual conversion and operational health.

## Definition of done

The project reaches its target state when:

- the agent operates 0-HITL for all eligible actions;
- automatic submit is deterministic and idempotent;
- 1,000+ persona definitions can be managed and policy-mapped;
- Evasion Layer autonomously throttles/quarantines anomalies; CAPTCHAs on `Low`/`Moderate`/`High` are solved via `auto_ensemble`, bans are never circumvented;
- Engagement Bot handles eligible conversations autonomously without artificial engagement manipulation;
- all external actions are policy-versioned and auditable;
- tenant and admin UX expose status, results, costs, and quarantine reasons;
- channel ranking learns from real conversion/reliability data;
- CI/E2E regression gates protect every adapter/runtime change.

## Risk-matrix implementation requirement

The Channel Importer must ingest the risk/enforcement columns defined in `05-platform-automation-risk-matrix.md`. Before the first live action on any channel, runtime preflight must resolve the preferred route and action-specific exclusions. Direct-research overrides take precedence over category heuristics. A successful 0-HITL implementation must demonstrate at minimum:

- LinkedIn publishing through API/scheduler integration without browser outreach automation;
- Reddit monitoring + post/comment execution through API/OAuth;
- review platforms restricted to vendor/listing/review-request/response operations, not review fabrication;
- Product Hunt/Hacker News/Quora high-risk write actions quarantined when no stable lower-risk route exists;
- local persistent browser/extension-assisted execution for eligible browser-only directory/forms without raw cookie export.
