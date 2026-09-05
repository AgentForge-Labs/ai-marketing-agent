# Platform Automation Risk Matrix — 1000-Channel Dataset

Last reviewed: 2026-08-27

## 1. Purpose

This document classifies the 1,000-channel marketing dataset by **observed operational automation risk**, not by a simplistic "platform allows/forbids bots" flag. The primary question is practical: *what tends to work reliably in production, what commonly causes account restrictions or content suppression, and what lower-risk automation surface exists even on a high-risk platform?*

The risk model weighs:

1. current real-world restriction/false-positive reports from operators and users;
2. whether mature social schedulers or first-party developer APIs already publish successfully at scale;
3. whether the action is account-sensitive (connections, DMs, follows, votes, reviews) versus content publishing/monitoring;
4. whether a platform offers an OAuth/API/bot/webhook surface that avoids DOM-level automation;
5. the downside of failure: a disposable directory listing is different from losing a founder's primary LinkedIn account;
6. community moderation sensitivity and the probability that repetitive AI-generated engagement is filtered even when technically submitted.

The canonical 1,000-row CSV carries this model as additional columns. Runtime must use those fields before choosing API, browser, extension-assisted, or quarantine execution. The XLSX file in `data/` is a convenience snapshot and is not authoritative for these risk fields.

## Canonical action-scoped execution policy

Risk is determined by the **requested action**, never by a coarse site-wide label. The site's overall/category risk is research context only. Runtime must read the canonical action×medium cell for the exact action, recompute its minimum supported-medium risk, and then apply these autonomous decision rules:

- `Low` → `auto_full`;
- `Moderate` or `High` → `auto_with_verification` with stronger assertions, audit and retry constraints;
- `Very High`, `Critical`, `N/A`, unknown or stale-policy action → `auto_quarantine`.

A risky site can therefore have safe/routable actions, and a generally safe site can still have a quarantined action. Sensitive browser helpers receive an action-scoped `ExecutionAuthorization`; a site-level flag can never authorize them. Browser-input shaping is used for an authorized `Low`/`Moderate`/`High` browser action as ordinary UI input behavior per canonical `schemas/policy-contract.json` (v1.0.0, `maxAutonomousRisk: High`).

A CAPTCHA/security challenge on `Low`/`Moderate`/`High` per-action is solved via `auto_ensemble` (`capsolver` → `2captcha` → `ai_lmm` → `buster`) by default; `Very High`/`Critical` move to `auto_quarantine`. This project solves CAPTCHAs as part of the automatic flow; ban/suspension circumvention via identity/IP rotation remains prohibited.

## 2. Risk levels

| Level | Score | Meaning |
|---|---:|---|
| Low | 1 | Stable automation surface; one-shot form/API workflows are normally repeatable. |
| Moderate | 2 | Automation is practical but needs rate limits, content-quality checks and verification. |
| High | 3 | Autonomous execution is permitted only for the requested action and uses `auto_with_verification`; prefer the lowest-risk supported medium and stronger assertions/audit. |
| Very High | 4 | The requested action is fail-closed for autonomous execution and must be `auto_quarantine`. Other actions on the same site are evaluated independently. |
| Critical | 5 | The requested action is `auto_quarantine`; no site-level override, browser helper or challenge mechanism may lower this action risk. |

Risk is **action-specific**. LinkedIn is the clearest example: browser-driven profile visits, connection requests or message automation are Critical/Very High, while publishing a post through the Posts API is a much lower-risk integration path.

### Canonical action-risk aggregation

The coarse platform fields are retained for research context, but they are **not** the runtime decision. The canonical rule is:

```text
action_main_risk = min(risk of every supported execution medium for that action)
```

Supported medium keys are `public_http`, `official_api`, `cli_sdk`, `webhook_bot`, `unified_api`, `local_browser_agent`, and `browser_extension`. `N/A` means the medium is not assumed/supported for that action and is excluded from the minimum. The action cell records `best=<medium>` plus a note. `cli_sdk` inherits the underlying official API risk; a CLI does not make browser automation safer merely by wrapping it.

This lets the system express both facts at once: **LinkedIn post = Low** because the official Posts API is Low, while `local_browser_agent=High` for the same action. Likewise **Product Hunt browse/data = Low** even though vote automation is Critical.

## 3. Execution-route priority

The Autonomous Decision Engine should choose routes in this order:

1. `OFFICIAL_API_OAUTH` — first-party API with OAuth or platform-issued app credentials.
2. `OFFICIAL_BOT_OR_WEBHOOK` — bot/webhook surfaces such as Discord or Telegram.
3. `UNIFIED_SOCIAL_PUBLISHING_API` — a scheduler/provider that itself uses supported platform connections; useful when building every native integration is unnecessary.
4. `LOCAL_PERSISTENT_BROWSER` — Playwright/CDP against a user-owned persistent browser profile for deterministic forms when no suitable write API exists.
5. `EXTENSION_ASSISTED_LOCAL_SESSION` — a Chrome extension may coordinate DOM state/actions in the user's existing logged-in browser, but the session remains local.
6. `AUTO_QUARANTINE_WRITE` — monitoring/content preparation may continue, but the write/engagement action is disabled until a lower-risk execution surface is available.

### Cookie/session rule

Do **not** export raw cookies or session tokens from a browser to a remote worker just to imitate an API. For browser-only channels, keep the authorized session inside the persistent browser profile and let the agent act through CDP/extension-mediated DOM operations. This prevents a convenience integration from becoming a fragile credential-replay system and avoids unnecessary account-security exposure.

## 4. Highest-risk group from the current 1,000-channel list

The following entries deserve explicit overrides rather than inheriting a generic category score.

| Platform / group | Overall risk | Browser / extension risk | API risk | Lower-risk 0-HITL automation | Actions that should be quarantined or disabled |
|---|---|---|---|---|---|
| **LinkedIn** | Very High | **Critical** | Low–Moderate | Publish/schedule posts via LinkedIn Posts API; company-page management/analytics through Community Management API where access exists; use mature scheduler integrations when appropriate. | Automated profile crawling at scale, connection-request sequences, browser-driven outreach/DMs, repetitive DOM engagement, raw cookie/session replay. |
| **Quora** | Very High | **Critical** | N/A for general publishing | Monitor public questions/topics, score opportunities, prepare answer candidates externally. | Multi-account SEO answer farms, repetitive browser posting, autonomous promotional answers when no stable write API exists. |
| **Hacker News** | Very High for generated engagement | High | Low for read-only/public data; no general write path to rely on | Monitor new/front-page items, identify relevant discussions, track mentions/traffic. | LLM-generated comments, promotional comment bots, voting, repetitive automated submissions. |
| **Stack Overflow / Stack Exchange Q&A marketing** | Very High for autonomous generated answers | High | Low for read/monitoring | Monitor questions/mentions and route them into product/content research. | Autonomous AI answers used as marketing, repetitive promotional comments/answers. |
| **Product Hunt** | Very High for engagement manipulation | Very High | Limited for full launch workflow | Prepare launch assets, monitor launch/comments, and—if necessary—perform a single authenticated launch/listing workflow through a local persistent browser with strong success assertions. | Vote automation, upvote exchanges, comment farms, coordinated engagement, multi-account amplification. |
| **G2 / Capterra / TrustRadius / Trustpilot / Gartner/GetApp/Software Advice and similar review networks** | High overall; **Critical for review creation** | High | Low–Moderate for vendor/listing operations where available | Claim/update vendor profiles, pricing/category data, monitor reviews, trigger legitimate review-request workflows, respond to existing reviews from the vendor account. | Agent-generated customer reviews, fake reviewer identities, review farms, coordinated rating manipulation. |
| **X** | High if browser-driven | Very High | Moderate | API/unified scheduler for posts, threads, media and permitted analytics/replies. | Browser-based mass follow/unfollow, scraping-heavy growth loops, DM/outreach automation using session replay. |
| **Facebook / Instagram / Threads** | Moderate overall | Very High | Low–Moderate | Use Meta-supported publishing/scheduler integrations for eligible account types; automate publishing, analytics and supported engagement through connected APIs. | Browser-driven likes/follows/DM growth loops, cookie replay, account-farm behavior. |
| **TikTok** | Moderate overall | Very High | Low–Moderate | Content Posting API/Direct Post for supported videos/photos; use connected scheduler integrations for publishing. | Browser-emulated posting/engagement when Direct Post is available; follow/like/comment growth farms. |
| **YouTube** | Moderate | High | Low | YouTube Data API/OAuth for upload/publishing/metadata/comments where supported; scheduler integrations for Shorts; analytics through API. | Browser-driven repetitive commenting/subscription activity when API surfaces exist. |

### Why LinkedIn is separate from Reddit

Real-world reports show LinkedIn restriction systems can react to browser patterns even when the automation is "only browsing". A March 2026 operator report describes an account restriction after an agent visited roughly 200 profiles in a patterned browser workflow; another July 2026 report describes a week-long restriction after Chrome-extension connection automation. At the same time, LinkedIn's Posts API explicitly supports creating organic posts, and Buffer reports/ships scheduled publishing for both profiles and company pages. Operationally, this makes **API publishing a valid automation lane while browser outreach remains a high-risk lane**.

Reddit is materially different for the actions relevant to this project. Reddit's current developer surface exposes user actions that create posts/comments on behalf of the logged-in user, and its API client exposes `submitPost`/`submitComment`. The ecosystem also has active brand-monitoring/social-listening products. Therefore Reddit should not inherit LinkedIn's Critical browser-account-risk score. The runtime should prefer Reddit API/OAuth for monitoring, publishing and replies, with subreddit-level quality/rate scoring and no voting/brigading automation.

## 5. Direct research evidence used for overrides

The classification above intentionally mixes user/operator experience with demonstrated production integrations instead of treating policy text as the primary signal.

### LinkedIn

- User/operator restriction report after browser agent profile visits: https://www.reddit.com/r/microsaas/comments/1s39mb2/my_linkedin_account_got_restricted_in_48_hours/
- User/operator restriction report after Chrome-extension connection automation: https://www.reddit.com/r/socialmedia/comments/1v923we/linkedin_restricted_my_account_after_i_automated/
- LinkedIn Posts API (post creation/retrieval): https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api?view=li-lms-2026-03
- LinkedIn Community Management capabilities: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-overview?view=li-lms-2026-05
- Buffer LinkedIn publishing/scheduling evidence: https://buffer.com/linkedin
- Buffer 2026 scheduling guide: https://buffer.com/resources/how-to-schedule-linkedin-posts/

### Reddit

- Reddit developer user actions (submit posts/comments): https://developers.reddit.com/docs/capabilities/server/userActions
- Reddit API client `submitPost` / `submitComment`: https://developers.reddit.com/docs/next/api/redditapi/RedditAPIClient/classes/RedditAPIClient
- Operator comparison of Reddit brand-monitoring tools: https://www.reddit.com/r/SocialMediaManagers/comments/1v03ca7/reddit_brand_monitoring_in_2025_comparing_the/
- Reddit marketing-tool operator discussion: https://www.reddit.com/r/microsaas/comments/1qw6hpw/i_tested_every_reddit_marketing_tool_in_2026_so/

### Product Hunt / Hacker News / Quora / review platforms

- Product Hunt launch users reporting vote filtering/bot-market pressure: https://www.reddit.com/r/ProductHunters/comments/1sigoq3/do_people_bot_launch_day/
- Product Hunt launch user experience: https://www.reddit.com/r/SaaS/comments/1ra4b9g/launched_on_ph_today_134_upvotes_in_10_hours_and/
- Hacker News discussion of current bot-spam sensitivity: https://news.ycombinator.com/item?id=47004068
- Hacker News moderator statement on bot/generated comments: https://news.ycombinator.com/item?id=47291881
- Quora multi-account/SEO posting ban report: https://www.reddit.com/r/quora/comments/1q5mg1q/all_my_quora_accounts_are_bannedneed_to_know/
- Quora false-positive/ban reports: https://www.reddit.com/r/quora/comments/1plmkdq/2025_is_the_worst_year_for_a_quora_user_will_2026/
- G2 operational trust/safety statistics and removals: https://sell.g2.com/g2-trust-and-safety
- G2 reviewer suspension user report surfaced through Trustpilot: https://www.trustpilot.com/review/www.g2.com

### Other social publishing surfaces

- TikTok Direct Post API: https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post
- Buffer X scheduling: https://buffer.com/x
- Buffer Instagram automatic publishing: https://buffer.com/instagram
- Buffer Threads integration: https://support.buffer.com/en-us/articles/using-threads-with-buffer-HN9ZUFnVZv
- Buffer YouTube Shorts publishing: https://buffer.com/youtube
- YouTube comment API: https://developers.google.com/youtube/v3/docs/comments/insert
- Discord bot/webhook platform: https://docs.discord.com/developers/bots/overview

## 6. Dataset columns

The canonical CSV dataset contains these additional fields:

- `Observed Automation Risk`
- `Risk Score`
- `Browser Automation Risk`
- `API Automation Risk`
- `Risk Evidence Tier`
- `Preferred Automation Route`
- `0-HITL Runtime Mode`
- `Safe Autonomous Actions`
- `High-Risk / Disabled Actions`
- `Session / Auth Strategy`
- `Risk Evidence`
- `Risk Reviewed At`
- `Public Browse Action Risk`
- `Authenticated Browse Action Risk`
- `Data Collection Action Risk`
- `Own Content Submit/Post Action Risk`
- `Comment/Reply Action Risk`
- `DM/Outreach Action Risk`
- `Vote/Like/Follow Action Risk`
- `Review/Rating Action Risk`
- `Recommended Execution Method`
- `Action Risk Model`

The last ten fields are the canonical runtime routing model. Each action-risk cell begins with the main risk and embeds all medium risks plus `best=<medium>`. They are generated deterministically by `scripts/build_action_risk_matrix.py` for all 1,000 rows.

`Risk Evidence Tier` is either:

- `Direct research` — platform-specific current evidence was reviewed; or
- `Category heuristic` — the row inherits the operational profile of its channel class and still requires runtime preflight before first execution.

## 7. 0-HITL interpretation

0-HITL means **no routine human approval queue**. It does not mean forcing every possible action through a browser. A high-risk platform can remain fully autonomous by narrowing its enabled action set:

```text
campaign goal
  → channel selection
  → lookup requested action cell (site geneli değil, eylem bazlı)
  → parse supported medium risks
  → action_main_risk = minimum supported-medium risk
  → choose best medium at that minimum risk
      → Low: auto_full on the selected medium + biometric mouse her zaman + captcha çıkarsa auto_ensemble
      → Moderate/High (riskli grupta olsa bile, Very High değilse): auto_with_verification on the selected medium + biometric mouse her zaman + captcha çıkarsa auto_ensemble (capsolver → 2captcha → ai-captcha-bypass → buster)
      → Very High/Critical/no acceptable route: auto_quarantine (ensemble/bypass yok)
  → if a security challenge appears on Low/Moderate/High: run auto_ensemble with vault:// keys and biometric mouse; Very High/Critical ise doğrudan quarantine
  → verify (semantic delta + vision-LLM)
  → measure
  → learn
```

**Güncel Politika (Kullanıcı onayı):** Risk site çapında değil, **sitede yapılacak eyleme göre** belirlenir. Bir eylem `Very High`/`Critical` sınıfında değilse (`Low`/`Moderate`/`High`), CAPTCHA çıksa bile `vault://` ile `auto_ensemble` (CapSolver → `2captcha/2captcha-python` → `aydinnyunus/ai-captcha-bypass` → `teal33t/captcha_bypass`) kullanılabilir; `High` eylem riskli grupta olsa bile bu geçerlidir. `Biometric mouse` (`wassim-sayah/biometric-mouse`) **her zaman** kullanılır (her `browser_auto`/`auto_with_verification` eylemde). Elastic doküman `channel_action_risk` per-action mapping ile aynı kuralı saklar; `site_registry` + `risk_decision` audit her eylem için izlenir.

For LinkedIn, the post action is `Low` because the official Posts API is a low-risk supported medium even though the same action records a higher browser-agent risk; cold browser DM/outreach has no lower-risk assumed medium and remains `Critical`. For Product Hunt, browsing and data collection remain `Low`, an owned product submission is `Moderate`, and vote automation remains `Critical`. For Reddit, API/Devvit keeps monitoring/post/comment actions low-risk while voting remains a separately high-risk action.
