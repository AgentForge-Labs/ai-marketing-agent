# Security and Autonomous Operation Policy

This repository targets a **0-HITL autonomous marketing agent**. Canonical policy is `schemas/policy-contract.json` (v1.0.0, `maxAutonomousRisk: High`). This project **solves CAPTCHAs**: `Low`/`Moderate`/`High` per-action challenges are solved via the audited `auto_ensemble`; `Very High`/`Critical` go to `auto_quarantine`. The runtime operates without routine human approval while respecting consent, privacy, and auditability boundaries.

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
- solve CAPTCHA/account challenges on `Low`/`Moderate`/`High` per-action via `auto_ensemble` per `schemas/policy-contract.json`; quarantine `Very High`/`Critical` or after ensemble exhaustion;
- refresh adapters when forms drift;
- preserve platform-native pacing and official API quotas.

It must **not**:

- circumvent bans, suspensions, or platform enforcement by changing identity/IP/fingerprint;
- reopen a banned/suspended account under any fresh profile/IP pair (quarantine/appeal only), per `schemas/policy-contract.json:accountReuse`;
- scrape or submit through prohibited endpoints after an explicit platform block;
- use biometric-mouse to impersonate a different human (it is ordinary human-like input shaping for the authorized account, per policy-contract).

A second account with a fresh profile AND fresh IP together is allowed only when no ban exists AND the platform explicitly permits multi-account (verified by `assert_reopen_allowed`).

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
- CAPTCHA/security challenges on `Low`/`Moderate`/`High` per-action are solved via `auto_ensemble` (`capsolver` → `2captcha` → `ai_lmm` → `buster`) per `schemas/policy-contract.json`. `Very High`/`Critical` move to `auto_quarantine`; after ensemble exhaustion the job also moves to `auto_quarantine` with masked audit.
- Third-party solvers are part of the automatic flow by default (`captcha.defaultPolicy: auto_ensemble`); no per-channel opt-in is required beyond the action being executable (`Low`/`Moderate`/`High`).

### Agentic Human-like Stack (agentic, vault-backed — 5 repos)

> Bu katman per `schemas/policy-contract.json` **varsayılan açıktır** (`captcha.defaultPolicy: auto_ensemble`). `Low`/`Moderate`/`High` per-action için `schemas/site-adapter.schema.json:captcha.policy = auto_ensemble` ile çalışır ve `C:\Users\ahmet\Downloads\DIGER\sunucular` → `vault://` anahtarlarını kullanır. `Very High`/`Critical` için kullanılmaz; ban/kısıtlama sonrası kimlik/IP değiştirerek erişim engelini aşmak için kullanılmaz.

- **Biometric Mouse** (`wassim-sayah/biometric-mouse`) — `ai_mouse/playwright_integration.py` `PlaywrightHumanMouse` FFT jitter/velocity/overshoot, 30dk %8 rotasyon. Servis: `services/biometric-mouse/` (profile `vault://mouse/profile/mouse_profile.json`). Amaç: Akamai/CF/DataDome **davranışsal skorunu yalnızca izinli oturumda stabilize etmek**, ban atlatmak değil. `schemas:biometricMouse` ile şemada zorunlu ama `enabled:false` default olabilir.
- **Semantic Browser** (`visser23/semantic-browser` v1.3.2) — `ManagedSession` `observe(mode=summary)` ~540 token oda metni (10k yerine), `act(action_id)` deterministik. Servis: `services/semantic-browser` (`http://127.0.0.1:8765`). Locator drift'te Vision-LLM ile birlikte, token verimliliği için. `schemas:semanticBrowser`.
- **2Captcha primary** (`2captcha/2captcha-python` 30+ tip) — `TwoCaptcha`/`AsyncTwoCaptcha` `recaptcha`/`turnstile`/`geetest`/`datadome` vb., `proxyRef=vault://proxy/residential/uri` (DataDome/Turnstile'da zorunlu), `pollingInterval 10s`. Vault: `vault://captcha/2captcha/apiKey` (`C:\...\sunucular` içindeki anahtar). `balance`/`report` sonrası maliyet takibi.
- **AI LMM fallback** (`aydinnyunus/ai-captcha-bypass` GPT-4o `gpt-4o` / Gemini `gemini-2.5-pro`) — Selenium screenshot → `ai_utils.py` vision prompt → action. `vault://llm/openai/apiKey` / `vault://llm/gemini/apiKey`. `puzzle`/`audio`'da kurtarıcı.
- **Buster fallback** (`teal33t/captcha_bypass` Buster `0.7.2` + B-spline) — ücretsiz, reCAPTCHA v2 audio. `services/buster/` altında.

Ensemble `auto_ensemble`: `2captcha` → fail → `ai_lmm` → fail → `buster` → fail → `auto_quarantine` (Telegram human son çare değil, `maxHumanSolvesPerDay` korumalı). Her deneme `audit_log.detail_json.captcha` içinde **maskeli** loglanır (token/sonuç değil, tip/süre/sonuç). Hiçbir ham secret `C:\...\sunucular` → `vault://` dışında repoya yazılmaz.

## API and browser hierarchy

1. official API/OAuth;
2. documented integration or partner interface;
3. policy-compatible browser automation;
4. `auto_quarantine` when none is valid.

Network-observed private APIs must not be used merely because they are discoverable. They require an explicit policy decision that their use is authorized and compatible with the platform terms.

## Reporting vulnerabilities

Do not open a public issue containing credentials, tokens, private account information, exploitable endpoints, or unredacted traces. Report security issues privately to the repository owner and include the minimum reproduction material necessary.
