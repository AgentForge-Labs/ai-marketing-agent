# Security and Autonomous Operation Policy

This repository targets a **0-HITL autonomous marketing agent**. Autonomy does not mean bypassing security controls. The runtime must be able to operate without routine human approval while still respecting platform policy, access controls, consent, privacy, and anti-abuse boundaries.

## Core security invariants

- Secrets, passwords, cookies, OAuth tokens, TOTP seeds, proxy credentials, and Playwright `storageState` must never be committed to Git.
- Use a dedicated secret store (Vault/KMS/managed secret service or encrypted local development store) and reference secrets by ID.
- Logs, screenshots, traces, and audit events must redact secrets and unnecessary personal data.
- Every external action must be attributable to a tenant, campaign, persona, channel, adapter version, policy version, and idempotency key.
- Every submit/comment/reply/DM action must pass the Policy Registry before execution.
- Automatic submit is allowed only after policy, identity/session, rate-limit, idempotency, disclosure, and pre-submit assertion checks pass.
- Uncertain success must be verified before any retry.
- Jobs fail closed and move to autonomous quarantine when policy, identity, or access requirements are not satisfied.

## 0-HITL model

There is no routine human approval queue. The Autonomous Decision Engine selects one of three outcomes:

1. `auto_full` — execute automatically.
2. `auto_with_verification` — execute automatically with additional assertions.
3. `auto_quarantine` — do not execute; schedule policy/discovery refresh and re-evaluate later.

A blocked job is not silently forced through. 0-HITL means the system makes the stop/continue decision itself, not that it ignores controls.

## Persona security

The system may maintain 1,000+ content/brand personas for channel-specific voice, localization, experiments, and campaign routing. Persona isolation includes separate account references, session state, content history, and rate-limit history where the platform permits multiple accounts.

Persona rules:

- never impersonate a real person without authorization;
- never fabricate customer identities, testimonials, or reviews;
- respect platform limits on duplicate or coordinated accounts;
- preserve required sponsorship/affiliation disclosures;
- where a platform allows only one account, multiple personas are content variants behind that authorized account rather than covert additional accounts.

## Anti-detection / evasion layer

The project uses the historical name **Evasion Layer**, but its production meaning is defensive and reliability-oriented:

- detect rate-limit, challenge, session, or policy anomalies;
- reduce concurrency and apply cooldowns;
- avoid duplicate submissions and repetitive content;
- keep a stable authorized session rather than rapidly rotating identities;
- stop or quarantine on CAPTCHA, account challenge, ban, or access-control failure;
- refresh adapters when forms drift;
- preserve platform-native pacing and official API quotas.

It must **not**:

- bypass or solve CAPTCHAs to defeat access controls;
- circumvent bans, suspensions, or platform enforcement by changing identity/IP/fingerprint;
- defeat authentication, authorization, or bot-detection controls;
- scrape or submit through prohibited endpoints after an explicit platform block;
- use biometric-mouse, stealth/fingerprint spoofing, or similar techniques to impersonate human interaction for the purpose of defeating security systems.

## Engagement Bot boundaries

The Engagement Bot is autonomous but bounded:

Allowed examples:

- reply to comments on the brand's own content when policy permits;
- answer inbound questions and opted-in conversations;
- follow up on a published listing or launch thread;
- route support/sales questions to the appropriate autonomous workflow;
- generate context-specific responses with disclosure rules applied.

Prohibited examples:

- fake likes/upvotes/votes;
- coordinated engagement between controlled accounts to create artificial popularity;
- fabricated reviews or testimonials;
- mass unsolicited DMs;
- keyword-based mass commenting;
- deceptive astroturfing or undisclosed impersonation.

## CAPTCHA, 2FA and verification

- Email verification may be automated when it is a normal verification step for an authorized account.
- TOTP may be generated automatically from an authorized secret stored in the vault.
- CAPTCHA or an account-security challenge is treated as a security boundary. The job moves to `auto_quarantine`; the system may retry only after the challenge is legitimately resolved through an allowed account/platform mechanism.
- The system must not route CAPTCHA challenges to third-party bypass services.

## API and browser hierarchy

1. official API/OAuth;
2. documented integration or partner interface;
3. policy-compatible browser automation;
4. `auto_quarantine` when none is valid.

Network-observed private APIs must not be used merely because they are discoverable. They require an explicit policy decision that their use is authorized and compatible with the platform terms.

## Reporting vulnerabilities

Do not open a public issue containing credentials, tokens, private account information, exploitable endpoints, or unredacted traces. Report security issues privately to the repository owner and include the minimum reproduction material necessary.
