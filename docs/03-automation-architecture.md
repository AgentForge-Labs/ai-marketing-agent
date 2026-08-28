# Autonomous Automation Architecture — 0-HITL

## 1. Architecture contract

This document is the authoritative runtime architecture for the project. The system is **0-HITL**: routine planning, content generation, channel selection, authentication, submit, verification, engagement, retry decisions, and quarantine decisions are autonomous.

0-HITL does **not** mean “execute at all costs.” The system must choose between execution and autonomous quarantine based on current policy, adapter confidence, identity state, rate limits, and success ambiguity.

Active decisions:

- `auto_full` — execute automatically.
- `auto_with_verification` — execute automatically with stronger assertions.
- `auto_quarantine` — stop execution, refresh policy/discovery state, and re-evaluate later.

The adapter contract exposes only autonomous execution modes (`browser_auto`, `api_auto`, `auto_full`); approval/manual execution paths are not supported.

## 2. Target stack

| Layer | Target |
|---|---|
| Runtime | TypeScript + Node.js LTS |
| Browser automation | Playwright |
| API integrations | Official REST/GraphQL/OAuth SDKs where available |
| Primary database | PostgreSQL for production; SQLite allowed for local prototype/testing |
| Queue/orchestration | Durable worker queue with leases, retry/backoff, dead-letter/quarantine |
| LLM | Provider abstraction with structured outputs and versioned prompts |
| Secrets | Vault/KMS/managed secret service |
| Object artifacts | S3-compatible storage for redacted screenshots/traces |
| Observability | Structured logs, traces, metrics, audit events |
| Web product | Tenant dashboard + admin/ops dashboard |

## 3. Runtime services

### 3.1 Channel Importer

Reads the canonical ranked CSV dataset as data only, normalizes rows, and writes versioned `site_registry` records. The XLSX file is a convenience snapshot, not the runtime source of truth. Dataset text is never executed as instructions.

Responsibilities:

- handle metadata/header rows correctly;
- normalize domains and URLs;
- preserve P0/P1/P2/P3 priority;
- map channel class;
- import automation-fit and research metadata;
- calculate freshness and preflight requirements;
- reject malformed rows deterministically.

### 3.2 Preflight and Policy Crawler

The current dataset contains many homepage-fallback URLs, so preflight is mandatory before execution.

Preflight records:

- current canonical URL;
- register/login/submit routes;
- official API/OAuth availability;
- current auth method;
- current platform automation policy;
- allowed/blocked operations;
- disclosure requirements;
- account/multi-account constraints;
- rate-limit/quota metadata;
- form/API confidence;
- last checked timestamp.

Policy data is versioned. A stale or contradictory policy result causes `auto_quarantine`.

### 3.3 Persona Engine

Supports 1,000+ persona definitions for voice, localization, experimentation, and account routing.

A persona record is not automatically a separate platform account. Account mapping is controlled by channel policy. Where multi-account use is not allowed, multiple personas remain content variants behind an authorized account.

The Persona Engine manages:

- voice profile;
- locale/timezone;
- disclosure profile;
- channel eligibility;
- content history;
- account references;
- session health;
- cooldown state.

### 3.4 Content Core

Inputs:

- verified product profile;
- campaign objective;
- channel context;
- persona voice;
- required disclosure;
- allowed CTA/link behavior;
- recent content corpus;
- experiment configuration.

Outputs:

- structured content artifact;
- semantic fingerprint;
- claims/source mapping;
- UTM/tracking metadata;
- policy classification;
- generation model/prompt version.

The Content Core must reject unsupported claims and fabricated social proof.

### 3.5 Autonomous Decision Engine

The engine is deterministic where possible and LLM-assisted only where structured reasoning is required.

Decision inputs:

- current policy version;
- adapter confidence;
- auth/session health;
- content risk;
- account/channel restrictions;
- idempotency state;
- recent failure rate;
- challenge/rate-limit signals;
- expected business value.

Example decision model:

```text
if policy_blocked or security_challenge:
    auto_quarantine
elif confidence < threshold or success_assertion_weak:
    auto_with_verification
else:
    auto_full
```

LLM reasoning never overrides a hard policy/security deny.

### 3.6 Adapter Compiler

The adapter compiler converts versioned JSON contracts into a bounded action plan. Free-form JavaScript and `eval` are prohibited.

Browser primitives may include:

- `goto`
- `fill`
- `select`
- `check`
- `upload`
- `click`
- `waitFor`
- `assertText`
- `assertUrl`
- `extract`

API primitives may include:

- HTTP method/path;
- scoped credential reference;
- request mapping;
- idempotency header;
- expected response codes;
- structured success extraction.

### 3.7 Discovery and self-healing

A discovery agent may map a new or changed form into a sanitized form contract. It must not auto-promote a low-confidence mapping into production execution.

Flow:

```text
form drift detected
  → capture sanitized DOM/form model
  → semantic remap
  → schema validation
  → dry-run
  → assertion check
  → confidence threshold
  → adapter version promotion or quarantine
```

No human approval queue is required; promotion is governed by deterministic test thresholds.

### 3.8 Autonomous Runner

Runner flow:

```text
lease job
  → load tenant/product/persona
  → load current policy
  → resolve authorized account/session
  → idempotency check
  → content/payload validation
  → decision engine
  → API or browser execution
  → automatic submit
  → post-submit assertion
  → persist result URL/ID
  → audit event
  → analytics event
  → enqueue engagement/follow-up if eligible
```

## 4. Database model

Production storage should be tenant-aware and migration-managed. Minimum logical tables:

- `tenants`
- `users`
- `memberships`
- `brands`
- `product_profiles`
- `personas`
- `site_registry`
- `policy_versions`
- `account_refs`
- `sessions`
- `adapters`
- `adapter_versions`
- `campaigns`
- `contents`
- `jobs`
- `submissions`
- `idempotency_keys`
- `risk_decisions`
- `engagement_events`
- `audit_log`
- `conversion_events`
- `channel_scores`
- `self_healing_events`

### Queue fields

At minimum:

- `status`
- `attempt`
- `next_run_at`
- `lease_owner`
- `lease_expires_at`
- `tenant_id`
- `campaign_id`
- `persona_id`
- `site_id`
- `operation`
- `adapter_version`
- `decision_mode`
- `last_error_code`

Recommended statuses:

`queued`, `leased`, `running`, `done`, `failed`, `cool_down`, `needs_remap`, `blocked_policy`, `auto_quarantine`.

## 5. Idempotency

Every externally visible action must use a deterministic idempotency identity such as:

```text
sha256(tenant_id + campaign_id + site_id + operation + canonical_target + content_semantic_key)
```

Before retrying an uncertain submit, the system searches for existing remote state. Blind retry is prohibited.

## 6. Success assertions

A submit is not successful merely because the click/request returned without throwing.

Use one or more independent signals:

- official API response ID;
- canonical listing/post URL;
- expected redirect pattern;
- success message/heading;
- subsequent GET/search confirming the new object;
- email verification followed by visible published state.

Low-confidence outcomes use `auto_with_verification`; unresolved outcomes become `auto_quarantine`.

## 7. Automatic email and 2FA verification

Email verification can be autonomous for authorized accounts:

```text
submit
  → create verification job
  → poll authorized mailbox
  → extract verified link/code
  → open/submit in same authorized account context
  → assert verified state
  → audit
```

TOTP may be generated from an authorized vault secret.

CAPTCHA or a security challenge is not bypassed. It causes `auto_quarantine` until the authorized account can legitimately continue.

## 8. Evasion Layer / anomaly controller

The component name `Evasion Layer` is retained, but production behavior is defensive and policy-aware.

Inputs:

- rate-limit headers/statuses;
- repeated failures;
- account restrictions;
- CAPTCHA/challenge signals;
- session/auth drift;
- form drift;
- abnormal redirect loops;
- content similarity;
- duplicate-submit indicators;
- adapter-family error bursts.

Responses:

- throttle concurrency;
- cooldown account/channel;
- suspend adapter family;
- refresh policy/preflight;
- refresh session through allowed mechanisms;
- self-heal adapter;
- quarantine.

It must not use fingerprint spoofing, biometric simulation, CAPTCHA bypass, ban evasion, or unauthorized IP/account rotation to defeat platform controls.

### 8.1 Agentic Human-like Stack (opt-in, policy-gated — 5 repos, vault-backed)

> **Varsayılan kapalı.** Yalnızca `policy.allowedActions` ve `schemas/site-adapter.schema.json:captcha.policy=auto_ensemble` + `biometricMouse.enabled`/`semanticBrowser.enabled` açık ise ve `C:\Users\ahmet\Downloads\DIGER\sunucular` → `vault://` anahtarları mevcut ise aktif olur. `auto_quarantine` sonrası ban atlatmak için kullanılmaz.

- **Biometric Mouse** (`wassim-sayah/biometric-mouse`, MIT): `ai_mouse/human_mouse.py` FFT jitter/frequency/velocity/overshoot/click-hold per bucket (short 0-100px / medium 100-400px / long 400px+), `playwright_integration.py` `PlaywrightHumanMouse(page, profile_path="vault://mouse/profile/mouse_profile.json")` → `click_element(locator)` / `move_to(x,y)`, 30dk %8 varyans. Kayıt: `scripts/record_mouse.py` + `mouse_dojo/index.html`, eğitim: `train_mouse_model.py`, `visualize.py` 3×3 rapor. Servis: `services/biometric-mouse/`.
- **Semantic Browser** (`visser23/semantic-browser` v1.3.2, MIT): `ManagedSession.launch` → `runtime.observe(mode=summary)` prose oda metni (~540 token, top25 + `more`), `runtime.act(ActionRequest(action_id))` deterministik `observe→act→observe` delta; cookie/banner auto-detected; CLI `portal`/`serve --host 127.0.0.1 --port 8765`. Servis: `services/semantic-browser/` — `schemas:semanticBrowser`.
- **2Captcha primary** (`2captcha/2captcha-python` MIT, 794★): `TwoCaptcha(apiKey)` / `AsyncTwoCaptcha` — `recaptcha/sitekey/url`, `turnstile/sitekey/url`, `geetest/gt/challenge/url`, `datadome/captcha_url/pageurl/userAgent/proxy` + 25 tip, `proxy={'type':'HTTPS','uri':'vault://proxy/residential/uri'}` zorunlu DataDome/Turnstile, `pollingInterval 10s`, `balance`/`report(id, True/False)`. Vault: `vault://captcha/2captcha/apiKey`.
- **AI LMM fallback** (`aydinnyunus/ai-captcha-bypass` 1.2k★): `ai_utils.py` GPT-4o `gpt-4o` / Gemini `gemini-2.5-pro` screenshot → prompt → Selenium action (`text`/`complicated_text`/`recaptcha_v2`/`puzzle`/`audio`), `puzzle_solver.py` slider, `successful_solves/*.gif` kanıt. Vault: `vault://llm/openai/apiKey`.
- **Buster fallback** (`teal33t/captcha_bypass` 330★): Firefox + `buster_captcha_solver_for_humans-0.7.2-an+fx.xpi` + GeckoDriver + B-spline human mouse, `recaptcha_buster_bypass.py`.

**Ensemble `auto_ensemble`:** `2captcha` → fail → `ai_lmm` → fail → `buster` → fail → `auto_quarantine` (human Telegram son çare değil, `maxHumanSolvesPerDay` korumalı). Her deneme `audit_log.detail_json.captcha` içinde maskeli (tip/süre/sonuç, token yok) + `risk_decision` + `self_healing_events`.

**Mimari entegrasyon:** `Adapter Compiler` → `humanMouseMove`/`semanticObserve`/`solveCaptcha` bounded primitives; `Autonomous Runner` → `evasion_check` sonrası `biometricMouse` + `semanticBrowser` → `CAPTCHA Ensemble` → `Assertion Engine` (`semantic delta` + `Vision-LLM` + multi-signal) → `Audit DB` (append-only, PII maskeli, WAL). Tüm anahtarlar `C:\...\sunucular` → `vault://`.

## 9. Engagement Bot

The Engagement Bot is an autonomous worker class. It consumes only policy-eligible events and thread/account context.

Eligible actions may include:

- reply to comments on owned brand content;
- answer inbound questions;
- respond to opted-in messages;
- update a launch/listing thread;
- route lead/support intent.

Before execution:

```text
context fetch
  → intent classifier
  → consent/policy gate
  → response generation
  → claim/disclosure validation
  → similarity + rate-limit check
  → auto execute
  → assertion + audit
```

Prohibited: fake likes/upvotes, fabricated reviews, controlled-account amplification, mass unsolicited DMs, and unrelated mass commenting.

## 10. Analytics and feedback

Every action emits an execution event and, where possible, attribution metadata. Channel scores are updated from real outcomes:

- publish/verification reliability;
- impressions/clicks;
- referral sessions;
- signup/demo/trial;
- paid conversion;
- cost/time per successful action;
- policy health;
- adapter failure rate.

The orchestrator uses these scores to select the next best actions rather than treating the original rank as immutable.

## 11. Multi-tenant SaaS boundary

Every persisted object and job must be tenant-scoped. Required product controls include:

- tenant isolation;
- RBAC;
- encrypted connected-account tokens;
- usage metering;
- subscription/plan limits;
- audit export;
- tenant pause/kill switch;
- admin health view;
- per-tenant campaign/channel controls.

0-HITL execution remains subordinate to tenant-configured business scope and platform policy.

## 12. Observability

Required operational metrics:

- queue depth and oldest job age;
- execution success rate;
- quarantine rate;
- adapter drift rate;
- policy freshness;
- API/browser split;
- average retries;
- per-channel conversion;
- per-tenant usage/cost;
- engagement response latency;
- security/challenge events.

## 13. Test gates

No adapter family reaches production until it passes:

1. JSON schema validation;
2. compiler unit tests;
3. deterministic dry-run tests;
4. idempotency tests;
5. policy-deny tests;
6. redaction/security tests;
7. success assertion tests;
8. at least three clean pilot E2E runs on allowed targets;
9. regression tests after any adapter/schema change.

## 14. End-to-end autonomous loop

```text
[Channel Importer]
      ↓
[Preflight + Policy Crawler]
      ↓
[Channel Scoring]
      ↓
[Persona Engine + Content Core]
      ↓
[Autonomous Decision Engine]
      ↓
[Distribution Orchestrator]
      ↓
[API Adapter / Playwright Runner]
      ↓
[AUTOMATIC SUBMIT]
      ↓
[Assertion + Idempotency + Audit]
      ↓
[Engagement Bot]
      ↓
[Analytics + Conversion Feedback]
      ↓
[Next Best Action]
```

This is the single canonical 0-HITL runtime model for the repository.

## Platform Risk Router

Before Adapter Compiler/Runner execution, `PlatformRiskRouter` receives `(channel, requested_action)` and reads that action's canonical risk cell. It parses per-medium values for `public_http`, `official_api`, `cli_sdk`, `webhook_bot`, `unified_api`, `local_browser_agent`, and `browser_extension`, removes `N/A` media, computes the minimum supported risk, then chooses a medium among the minimum-risk candidates using route priority. Coarse `Observed Automation Risk`, `Browser Automation Risk`, and `API Automation Risk` remain context/evidence fields and cannot override the action-specific result.

The router produces one of:

- `api_auto` — use OAuth/API, an API-backed CLI/SDK, bot/webhook, or unified publishing API;
- `browser_auto` — use a local persistent authorized browser profile/extension when browser is the lowest supported route;
- `auto_full` — select the minimum-risk route dynamically and execute/verify;
- `auto_quarantine` — no acceptable supported medium exists for the requested write/engagement action.

Example: LinkedIn `post` resolves to `Low` because `official_api=Low` even though `local_browser_agent=High`; LinkedIn cold DM/outreach remains `Critical` because no lower-risk general route is assumed. Product Hunt browse/data resolves to `Low`, owned submit to `Moderate`, and vote automation to `Critical`.

`cli_sdk` is only low-risk when it calls the same official API/OAuth surface; wrapping browser automation in a CLI does not change its medium risk. Raw browser cookies/session tokens are not exported to a remote worker as an API substitute. Extension-assisted execution keeps the authenticated session inside the user's browser profile. See [`05-platform-automation-risk-matrix.md`](05-platform-automation-risk-matrix.md).

### Current executable foundation

The first runtime implementation lives in `src/ai_marketing_agent/`:

- `catalogue.py` strictly imports the canonical CSV and validates its 1,000 contiguous ranks plus all 8,000 action-risk cells.
- `risk_router.py` independently recomputes `action_main_risk = min(supported medium risks)`, validates deterministic `best=`, and maps the selected route to execution mode.
- `cli.py` exposes a read-only routing inspection command; it does not perform a platform action.
- `storage.py` provides the SQLite prototype migration/import layer, idempotent `site_registry`/action-risk upserts, and append-only risk-decision/preflight audit writes.
- `url_preflight.py` normalizes HTTP(S) URLs and provides bounded public-network-only reachability checks with redirect revalidation and SSRF-oriented local/private target blocking.
- `database/migrations/001_runtime_foundation.sql` is the first checksum-tracked prototype migration. Production persistence remains PostgreSQL as specified above.

The current default and maximum autonomous risk ceiling is `Moderate` (it may be tightened to `Low`, but not raised above Moderate). `High`, `Very High`, `Critical`, `N/A`, unknown actions, invalid cells, and unsupported routes fail closed into `auto_quarantine`. This ceiling is intentionally separate from the coarse platform-risk fields: a platform can be globally high-risk while a specific API-backed action remains Low and executable.

Regression command:

```bash
python3 -m unittest discover -s tests -v
```


### Persistence and preflight invariants

The current persistence prototype treats canonical rank as the stable row identity and keeps domain as an indexed lookup field. Register/login URLs are not unique because multiple marketplace entries can legitimately share a partner portal. Canonical import stores source hashes and only updates rows whose source representation changed. `risk_decision` and `url_preflight_observation` are append-only at the database level through SQLite triggers.

URL preflight is not an automation action. It performs no login, cookie/session reuse, form submit, comment, post, vote, or outreach. It permits only HTTP(S) default ports, rejects URL credentials and malformed/control-character input, resolves the target before connecting, blocks non-global addresses, and validates redirect destinations again before following them.
