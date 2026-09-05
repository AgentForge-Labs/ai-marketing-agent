# Identity and Persona Strategy — 0-HITL

## 1. Purpose

The identity layer supports a fully autonomous marketing agent operating across 1,000+ channels. Its purpose is to keep account/session state deterministic, route channel-specific content through stable brand/campaign personas, and provide enough isolation for reliability and auditability without relying on human approval steps.

The authoritative model is **0-HITL**: the system creates plans, chooses eligible personas, authenticates authorized accounts, submits allowed actions, verifies results, and quarantines unsupported flows automatically.

## 2. Core modules

| Module | Responsibility |
|---|---|
| Persona Engine | Creates and maintains 1,000+ brand/campaign persona records, voice profiles, locales, and channel eligibility. |
| Identity Registry | Maps tenant/brand/persona/channel to authorized account references and session state. |
| Content Core | Produces channel-native copy from product facts, brand voice, campaign goal, and persona voice. |
| Distribution Orchestrator | Selects persona, channel, schedule, adapter, and action mode. |
| Engagement Bot | Handles policy-allowed replies/follow-up autonomously. |
| Evasion Layer | Detects anomalies, duplicate patterns, rate-limit pressure, session drift, and challenge signals; slows, cools down, or quarantines automatically. |
| Audit Layer | Records policy decision, adapter version, content hash, submit result, and resulting URL/event. |

## 3. Persona model

A persona is a versioned campaign/brand identity used for voice, localization, experimentation, and routing. The platform may support 1,000+ persona definitions even when a specific channel permits only one account.

Minimum persona fields:

- `persona_id`
- `tenant_id`
- `brand_id`
- `display_name`
- `handle_strategy`
- `locale`
- `timezone`
- `voice_profile`
- `topics`
- `disclosure_profile`
- `allowed_channel_classes`
- `account_refs`
- `session_policy`
- `content_history_ref`
- `status`

### Identity constraints

- Never impersonate a real person without authorization.
- Never create fabricated customer identities, testimonials, or reviews.
- Required affiliation/sponsorship disclosure must be preserved.
- Multi-account behavior must follow channel policy. If a platform permits one account only, multiple personas remain content/voice variants behind that authorized account.
- Account reuse rule (canonical `schemas/policy-contract.json:accountReuse`): a second account on the same platform must never reuse the banned (or any active) account's IP or browser profile alone — same IP + different profile and same profile + different IP are both forbidden. A new account is allowed only with BOTH a fresh browser profile AND a fresh IP, registered as a new audited identity.
- A persona never grants permission to bypass a ban/suspension by rotating identity/IP. Per canonical `schemas/policy-contract.json` (v1.0.0, `maxAutonomousRisk: High`), CAPTCHA/security challenges on `Low`/`Moderate`/`High` per-action are solved via the audited `auto_ensemble`; `Very High`/`Critical` go to `auto_quarantine`.

## 4. Account and credential registry

Credentials do not live inside persona JSON documents. The identity registry stores references such as:

```json
{
  "persona_id": "persona-de-dev-001",
  "site_id": "example-directory",
  "account_ref": "vault://accounts/example-directory/acct-42",
  "session_ref": "vault://sessions/example-directory/acct-42",
  "status": "active",
  "last_verified_at": "2026-08-26T00:00:00Z"
}
```

Secrets must be held in Vault/KMS/managed secrets or an encrypted development store. Passwords, cookies, TOTP secrets, OAuth tokens, and Playwright `storageState` never enter Git.

## 5. Authentication hierarchy

The autonomous runner selects the strongest allowed path:

1. official OAuth/API;
2. documented partner/integration authentication;
3. policy-compatible browser login;
4. `auto_quarantine` if authentication cannot be completed legitimately.

Email verification may be performed automatically for an authorized account. TOTP may be generated automatically from an authorized vault secret. CAPTCHA/security challenges on `Low`/`Moderate`/`High` per-action are solved via `auto_ensemble` per `schemas/policy-contract.json`; `Very High`/`Critical` or ensemble exhaustion cause autonomous quarantine and policy/session re-evaluation.

## 6. 1,000+ persona scheduling

The Persona Engine must support large-scale scheduling without creating correlated bursts or duplicate output. Scheduling inputs include:

- campaign priority;
- channel timezone;
- API quota/rate limit;
- account/session health;
- content freshness;
- previous channel outcome;
- policy freshness;
- cooldown state.

Pacing exists for reliability and policy compliance, not to conceal prohibited automation. When a platform signals throttling or challenge state, the agent decreases concurrency or pauses the affected account/channel.

## 7. Content identity

Each persona has a stable `voice_profile`, but all claims originate from the tenant's verified product profile. The LLM must not invent customer stories, credentials, benchmark results, reviews, or product capabilities.

Content generation pipeline:

```text
Product Profile + Campaign Goal + Channel Rules
        ↓
Persona Voice + Locale + Disclosure Profile
        ↓
Content Core
        ↓
Claim verification + similarity check + policy check
        ↓
Versioned content artifact
```

Content diversity is used to avoid repetitive spam and improve relevance. It must not be used to hide coordinated manipulation or evade moderation.

## 8. Engagement Bot

The Engagement Bot operates without routine human approval. Eligible operations include:

- replies to comments on the brand's own posts/listings;
- answers to inbound product questions;
- follow-up in an existing relevant thread;
- responses to opted-in inbound messages;
- support/sales routing;
- publishing clarification/update replies when the channel allows them.

It must not create fake consensus through controlled-account cross-engagement, artificial likes/upvotes, fabricated reviews, mass unsolicited DMs, or unrelated mass comments.

Every generated reply receives:

- thread/context input;
- brand/persona voice;
- disclosure rules;
- safety/policy classification;
- duplicate/similarity check;
- rate-limit check;
- audit record.

## 9. Evasion Layer / anomaly management

The project retains the component name `Evasion Layer`, but the production definition is an adaptive reliability layer. It observes:

- unusual failure rate;
- duplicate/repetitive output;
- form drift;
- session expiry;
- API throttling;
- CAPTCHA/security challenge;
- account restriction;
- policy drift;
- unexpected redirect/login loops.

Allowed responses:

- reduce concurrency;
- apply cooldown;
- refresh policy/discovery information;
- rebuild a stale adapter;
- rotate to another already-authorized account only when the channel policy permits it;
- quarantine the action.

It does not rotate IP/account identity to evade bans/suspensions. Biometric mouse is ordinary human-like input shaping for the authorized account on `Low`/`Moderate`/`High` per-action per `schemas/policy-contract.json`, not impersonation of a different human.

## 10. Autonomous lifecycle

```text
[Persona Engine]
    ↓
[Identity Registry]
    ↓
[Policy Registry]
    ↓
[Content Core]
    ↓
[Autonomous Decision Engine]
    ↓
[API / Browser Runner]
    ↓
[Automatic Submit]
    ↓
[Assertion + Audit]
    ↓
[Engagement Bot]
    ↓
[Analytics / Score Feedback]
    ↓
[Next autonomous action]
```

No approval queue is part of this lifecycle. A non-executable action becomes `auto_quarantine`, not “waiting for human approval.”
