# Channel and Content Strategy — 0-HITL

## 1. General principle

The system is a fully autonomous marketing agent that plans and executes distribution across a ranked catalogue of 1,000+ channels. There is no routine human approval step. Every action is resolved automatically as `auto_full`, `auto_with_verification`, or `auto_quarantine` by the Policy Registry and Autonomous Decision Engine.

The objective is not blind volume. The objective is to select the highest-value eligible channels for each product/campaign, publish useful channel-native content, measure outcomes, and continuously update the ranking.

## 2. Channel classes

The catalogue includes directories, review/comparison sites, social networks, communities, developer platforms, marketplaces, newsletters, PR/media, partner ecosystems, and other long-tail distribution channels.

Each channel record must be normalized to include at least:

- canonical site/domain;
- channel class;
- current homepage/register/login/submit URLs;
- URL confidence and last preflight time;
- official API/OAuth availability;
- allowed operations;
- disclosure rules;
- account/multi-account policy;
- rate limits and quotas;
- auth/verification requirements;
- adapter family;
- automation confidence;
- channel score;
- last policy review.

The source dataset's `Human Review` field is research metadata. It does not create a human approval workflow. If runtime policy cannot justify autonomous execution, the action becomes `auto_quarantine`.

## 3. Channel selection

The orchestrator ranks channels per campaign rather than simply processing rank 1 through 1000. Suggested score inputs:

```text
channel_score =
  buyer_intent
  × product_fit
  × audience_fit
  × policy_confidence
  × automation_reliability
  × historical_conversion
  × freshness
  ÷ expected_cost
```

P0/P1/P2/P3 remain useful bootstrap priors, but real performance data must override static assumptions over time.

## 4. Automatic execution hierarchy

For every eligible action:

1. official API/OAuth;
2. documented partner/integration path;
3. policy-compatible browser automation;
4. autonomous quarantine.

Automatic submit occurs only after:

- policy pass;
- adapter/schema validation;
- identity/session validation;
- content claim validation;
- duplicate/idempotency check;
- rate-limit check;
- required disclosure injection;
- pre-submit assertion.

## 5. Persona and content model

The platform supports 1,000+ brand/campaign persona definitions. Personas vary voice, localization, technical depth, format, and topic emphasis while remaining anchored to verified product facts.

A persona is not a fabricated customer. Content must not invent personal experiences, testimonials, benchmark results, reviews, or credentials.

Where a platform permits only one authorized account, multiple personas are content variants behind that account rather than covert extra accounts.

## 6. Content Core

The Content Core receives:

- product profile;
- campaign objective;
- channel rules;
- persona voice;
- locale/timezone;
- previous content corpus;
- disclosure requirements;
- CTA/link policy;
- current campaign experiments.

It outputs a versioned content artifact with:

- body/title/summary fields;
- optional media/assets;
- source facts;
- disclosure markers;
- semantic fingerprint;
- UTM/tracking metadata;
- policy classification;
- content confidence.

### Content diversity

Similarity checking prevents repetitive spam and stale copy. Diversity is used to improve relevance and avoid duplicate content, not to hide coordinated manipulation.

The system should compare new output with recent tenant/channel/persona content and rewrite when similarity exceeds the configured threshold.

## 7. 0-HITL engagement bot

The Engagement Bot is part of the autonomous execution loop.

Allowed operations, subject to channel policy:

- respond to comments on owned/brand content;
- answer inbound product questions;
- continue an existing relevant conversation;
- respond to opted-in inbound DMs;
- post clarification/update replies;
- route commercial/support intent into the relevant workflow.

The bot must not perform artificial amplification such as fake likes/upvotes, coordinated votes between controlled accounts, fabricated reviews, mass unsolicited DMs, or unrelated mass commenting.

Each engagement action runs:

```text
thread context
  → intent classification
  → policy/consent check
  → persona/brand response generation
  → claim + disclosure + similarity check
  → rate-limit check
  → automatic execution
  → result assertion + audit
```

## 8. Anti-detection / Evasion Layer

`Evasion Layer` is the retained architecture name for anomaly-aware execution. Its purpose is to keep the autonomous system reliable and non-spammy, not to defeat platform controls.

Signals include:

- HTTP/API throttling;
- repeated form failures;
- session expiry;
- CAPTCHA/security challenge;
- account restriction;
- form/DOM drift;
- duplicate-content risk;
- policy drift;
- abnormal failure burst;
- unexpected auth loops.

Autonomous responses include:

- lower concurrency;
- cooldown;
- stop affected adapter family;
- refresh policy/preflight;
- re-discover form structure;
- rebuild adapter;
- quarantine blocked operations.

The layer must not circumvent bans/suspensions through identity/IP rotation. CAPTCHAs/security challenges on `Low`/`Moderate`/`High` per-action are solved via `auto_ensemble` per canonical `schemas/policy-contract.json`; `Very High`/`Critical` go to `auto_quarantine`.

## 9. Scheduling

Scheduling is outcome- and policy-driven. Inputs include:

- channel timezone and posting windows;
- API quota;
- explicit platform rate limits;
- tenant campaign budget;
- persona/account health;
- content freshness;
- recent outcome/conversion data;
- cooldown state.

The scheduler should avoid bursty duplicate behavior and must stop when a channel signals throttling or challenge state.

## 10. Directories and listings

Directories are strong candidates for `auto_full` when:

- submission is allowed;
- listing ownership is valid;
- the form contract is current;
- required fields map deterministically;
- duplicate listing search succeeds;
- post-submit outcome can be asserted.

Typical flow:

```text
PREFLIGHT → SEARCH EXISTING LISTING → GENERATE CHANNEL COPY → FILL → SUBMIT → VERIFY → TRACK
```

## 11. Social and community channels

Social/community automation remains 0-HITL, but only actions allowed by current platform policy are eligible for automatic execution. The runner does not replace an old approval queue with forced execution. Unsupported actions move to `auto_quarantine`.

Typical eligible operations may include scheduled brand publishing through official APIs, replies on owned content, or other documented automation surfaces.

## 12. Review platforms

The agent may claim/update a legitimate vendor profile and invite real customers through permitted workflows. It must never create fabricated reviews, incentivize misleading reviews, or use controlled personas as customers.

## 13. Outreach and DM

Outbound messaging requires an explicit allowed channel policy and applicable consent/legal basis. Mass unsolicited DM behavior is prohibited. Inbound and opted-in conversations may be handled autonomously by the Engagement Bot.

## 14. UTM and attribution

Every trackable destination should use deterministic campaign metadata:

- `utm_source`
- `utm_medium`
- `utm_campaign`
- `utm_content`
- `channel_id`
- `persona_id`
- `content_id`
- `execution_id`

The analytics layer should track:

- submitted/published/verified state;
- listing/post URL;
- impressions/clicks where available;
- referral sessions;
- signup/demo/trial events;
- paid conversion;
- channel-level CAC/ROI;
- time-to-conversion;
- execution reliability.

## 15. Feedback loop

```text
[Dataset + Product Profile]
        ↓
[Policy + Preflight]
        ↓
[Channel Scoring]
        ↓
[Persona Engine + Content Core]
        ↓
[Autonomous Decision Engine]
        ↓
[Automatic API/Browser Submit]
        ↓
[Assertion + Audit]
        ↓
[Engagement Bot]
        ↓
[Analytics + Conversion]
        ↓
[Channel Score Update / Next Best Action]
```

This loop runs continuously without a human approval queue. `auto_quarantine` is the autonomous safety valve for anything that is not currently executable.

## Platform-specific operational risk matrix

The 1,000-channel catalogue is classified by **action and execution medium**, not by one platform-wide automation label. Runtime reads the requested action cell and selects the lowest-risk supported medium. See [`05-platform-automation-risk-matrix.md`](05-platform-automation-risk-matrix.md).

The deterministic rule is `action_main_risk = min(risk(supported_media))`. Unsupported media are `N/A` and do not lower the score. `cli_sdk` inherits the risk of the official API it wraps; a CLI is not a separate loophole. A local real browser agent and a browser extension remain separate media because their operational risk may differ from API execution.

Examples: LinkedIn `Own Content Submit/Post` is `Low` because the official Posts API is `Low`, while the same cell records `local_browser_agent=High`. Product Hunt `Public Browse` and `Data Collection` are `Low`, an owned product submit/update is `Moderate`, and vote automation is `Critical`. Quora public research is `Low` even though autonomous posting remains `High`. Reddit post/comment actions remain lower-risk through API/Devvit than through repetitive browser workflows.
