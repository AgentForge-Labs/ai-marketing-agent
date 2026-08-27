#!/usr/bin/env python3
import csv
from pathlib import Path

CSV_PATH = Path('data/saas_marketing_1000_channels_ranked - 1000 Channels.csv')
RISK_ORDER = {'Low': 1, 'Moderate': 2, 'High': 3, 'Very High': 4, 'Critical': 5}
MEDIA = ['public_http', 'official_api', 'cli_sdk', 'webhook_bot', 'unified_api', 'local_browser_agent', 'browser_extension']
BEST_ORDER = ['official_api', 'cli_sdk', 'webhook_bot', 'unified_api', 'public_http', 'local_browser_agent', 'browser_extension']
ACTION_COLUMNS = [
    'Public Browse Action Risk',
    'Authenticated Browse Action Risk',
    'Data Collection Action Risk',
    'Own Content Submit/Post Action Risk',
    'Comment/Reply Action Risk',
    'DM/Outreach Action Risk',
    'Vote/Like/Follow Action Risk',
    'Review/Rating Action Risk',
    'Recommended Execution Method',
    'Action Risk Model',
]


def m(**kwargs):
    out = {k: 'N/A' for k in MEDIA}
    out.update(kwargs)
    return out


def cell(media, note=''):
    supported = [(k, v) for k, v in media.items() if v in RISK_ORDER]
    if supported:
        floor = min(RISK_ORDER[v] for _, v in supported)
        main = next(name for name, score in RISK_ORDER.items() if score == floor)
        best = next((k for k in BEST_ORDER if media.get(k) in RISK_ORDER and RISK_ORDER[media[k]] == floor), supported[0][0])
    else:
        main, best = 'N/A', 'none'
    details = '; '.join(f'{k}={media[k]}' for k in MEDIA)
    suffix = f' | note={note}' if note else ''
    return f'{main} | {details} | best={best}{suffix}'


def profile(kind):
    # Each action reports its minimum supported-medium risk first, then every medium.
    if kind == 'directory':
        return {
            'public': (m(public_http='Low', local_browser_agent='Low', browser_extension='Low'), 'Normal public discovery/read.'),
            'auth': (m(local_browser_agent='Moderate', browser_extension='Moderate'), 'Authenticated account navigation.'),
            'data': (m(public_http='Low', local_browser_agent='Low', browser_extension='Low'), 'Public listing metadata collection; keep request rate bounded.'),
            'submit': (m(local_browser_agent='Low', browser_extension='Low'), 'Create/update one owned listing; use API instead if a documented API is discovered.'),
            'comment': (m(), 'No generic comment surface assumed.'),
            'dm': (m(local_browser_agent='Moderate', browser_extension='Moderate'), 'Use only relevant contact/partner forms; avoid repetitive unsolicited outreach.'),
            'vote': (m(), 'No generic engagement surface assumed.'),
            'review': (m(), 'Not a review channel by default.'),
            'route': 'PUBLIC_HTTP for read/data -> OFFICIAL_API/CLI_SDK when documented -> LOCAL_PERSISTENT_BROWSER or EXTENSION for owned listing forms',
        }
    if kind == 'community':
        return {
            'public': (m(public_http='Low', local_browser_agent='Low', browser_extension='Low'), 'Normal public browsing/discovery.'),
            'auth': (m(local_browser_agent='Moderate', browser_extension='Moderate'), 'Authenticated browsing is account-stateful.'),
            'data': (m(public_http='Low', local_browser_agent='Low', browser_extension='Low'), 'Public product/topic/member-page research at bounded volume.'),
            'submit': (m(local_browser_agent='Moderate', browser_extension='Moderate'), 'Submit one owned launch/post/listing; write risk is separate from read risk.'),
            'comment': (m(local_browser_agent='Moderate', browser_extension='Moderate'), 'Contextual replies only; repetitive promotional commenting raises risk.'),
            'dm': (m(local_browser_agent='High', browser_extension='High'), 'Unsolicited/repetitive outreach is materially riskier than browsing.'),
            'vote': (m(local_browser_agent='Very High', browser_extension='Very High'), 'Automated amplification is a distinct high-risk action.'),
            'review': (m(), 'Not a review channel by default.'),
            'route': 'PUBLIC_HTTP for research -> documented API if available -> LOCAL_PERSISTENT_BROWSER/EXTENSION for one owned write; quarantine amplification',
        }
    if kind == 'review':
        return {
            'public': (m(public_http='Low', local_browser_agent='Low', browser_extension='Low'), 'Read public vendor/review pages.'),
            'auth': (m(local_browser_agent='Moderate', browser_extension='Moderate'), 'Vendor-account navigation.'),
            'data': (m(public_http='Low', local_browser_agent='Low', browser_extension='Low'), 'Collect public reviews, scores and listing facts.'),
            'submit': (m(local_browser_agent='Low', browser_extension='Low'), 'Create/update the company-owned vendor/listing profile only.'),
            'comment': (m(local_browser_agent='Low', browser_extension='Low'), 'Respond to existing reviews as the verified vendor/account.'),
            'dm': (m(local_browser_agent='Moderate', browser_extension='Moderate'), 'Legitimate customer review-request/vendor workflows only.'),
            'vote': (m(local_browser_agent='High', browser_extension='High'), 'Do not automate reputation amplification.'),
            'review': (m(local_browser_agent='Critical', browser_extension='Critical'), 'Do not generate or submit customer reviews/ratings for the vendor.'),
            'route': 'PUBLIC_HTTP for monitoring -> VENDOR_API/PORTAL if documented -> LOCAL_PERSISTENT_BROWSER for owned listing/response; quarantine review/rating creation',
        }
    if kind == 'developer':
        return {
            'public': (m(public_http='Low', local_browser_agent='Low', browser_extension='Low'), 'Read public technical content/questions.'),
            'auth': (m(local_browser_agent='Moderate', browser_extension='Moderate'), 'Authenticated research/session navigation.'),
            'data': (m(public_http='Low', local_browser_agent='Low', browser_extension='Low'), 'Public topic/question/content research.'),
            'submit': (m(local_browser_agent='Moderate', browser_extension='Moderate'), 'One relevant owned article/post is lower risk than repetitive promotion.'),
            'comment': (m(local_browser_agent='High', browser_extension='High'), 'Generated promotional replies can create account/reputation risk.'),
            'dm': (m(local_browser_agent='High', browser_extension='High'), 'Avoid repetitive unsolicited outreach.'),
            'vote': (m(local_browser_agent='Very High', browser_extension='Very High'), 'No automated reputation/vote amplification.'),
            'review': (m(), 'Not a review channel.'),
            'route': 'PUBLIC_HTTP/OFFICIAL_API for read -> content API when explicitly supported -> LOCAL_PERSISTENT_BROWSER for one owned contribution; quarantine reputation actions',
        }
    if kind == 'social':
        return {
            'public': (m(public_http='Low', official_api='Low', cli_sdk='Low', local_browser_agent='Low', browser_extension='Low'), 'CLI/SDK is low only when it wraps the official API.'),
            'auth': (m(official_api='Low', cli_sdk='Low', local_browser_agent='Moderate', browser_extension='Moderate'), 'Prefer OAuth/API over DOM automation.'),
            'data': (m(official_api='Low', cli_sdk='Low', public_http='Low', local_browser_agent='Moderate', browser_extension='Moderate'), 'Prefer official/public read surfaces; high-volume DOM collection can raise risk.'),
            'submit': (m(official_api='Low', cli_sdk='Low', unified_api='Low', local_browser_agent='High', browser_extension='Moderate'), 'Main risk is Low because an official/API-backed route exists; browser write remains separately higher risk.'),
            'comment': (m(official_api='Moderate', cli_sdk='Moderate', unified_api='Moderate', local_browser_agent='High', browser_extension='High'), 'Use supported API reply surfaces where available.'),
            'dm': (m(official_api='Moderate', cli_sdk='Moderate', local_browser_agent='Very High', browser_extension='Very High'), 'Official business messaging lowers transport risk; unsolicited repetitive outreach remains high-risk behavior.'),
            'vote': (m(official_api='Moderate', cli_sdk='Moderate', local_browser_agent='Very High', browser_extension='Very High'), 'Only supported first-party engagement actions; no artificial amplification.'),
            'review': (m(), 'Not a review channel.'),
            'route': 'OFFICIAL_API/OAUTH -> CLI_SDK(API-backed) -> SUPPORTED_UNIFIED_API -> LOCAL_PERSISTENT_BROWSER/EXTENSION only for gaps',
        }
    if kind == 'messaging':
        return {
            'public': (m(public_http='Low', official_api='Low', cli_sdk='Low'), 'Public channel/community discovery where exposed.'),
            'auth': (m(official_api='Low', cli_sdk='Low', webhook_bot='Low', local_browser_agent='Moderate', browser_extension='Moderate'), 'Prefer bot/business APIs.'),
            'data': (m(official_api='Low', cli_sdk='Low', webhook_bot='Low', local_browser_agent='Moderate'), 'Use authorized bot/business data surfaces.'),
            'submit': (m(official_api='Low', cli_sdk='Low', webhook_bot='Low', local_browser_agent='High', browser_extension='High'), 'Owned/community messages via bot/business APIs.'),
            'comment': (m(official_api='Low', cli_sdk='Low', webhook_bot='Low', local_browser_agent='High', browser_extension='High'), 'Replies via bot/business APIs.'),
            'dm': (m(official_api='Moderate', cli_sdk='Moderate', webhook_bot='Moderate', local_browser_agent='High', browser_extension='High'), 'Use opt-in/owned conversations; do not mass-message strangers.'),
            'vote': (m(), 'Not a primary action.'),
            'review': (m(), 'Not a review channel.'),
            'route': 'OFFICIAL_BOT/BUSINESS_API -> CLI_SDK(API-backed) -> WEBHOOK -> browser only for unsupported owned-account gaps',
        }
    if kind == 'marketplace':
        return {
            'public': (m(public_http='Low', local_browser_agent='Low', browser_extension='Low'), 'Public marketplace/catalog browsing.'),
            'auth': (m(official_api='Low', cli_sdk='Low', local_browser_agent='Moderate', browser_extension='Moderate'), 'Prefer partner/vendor API when available.'),
            'data': (m(public_http='Low', official_api='Low', cli_sdk='Low', local_browser_agent='Low'), 'Catalog/listing research.'),
            'submit': (m(official_api='Low', cli_sdk='Low', local_browser_agent='Low', browser_extension='Low'), 'Owned integration/app/listing submission; use partner API if available.'),
            'comment': (m(), 'No generic comment surface assumed.'),
            'dm': (m(local_browser_agent='Moderate', browser_extension='Moderate'), 'Partner/contact workflow only.'),
            'vote': (m(), 'No generic engagement surface assumed.'),
            'review': (m(local_browser_agent='High', browser_extension='High'), 'Do not manufacture marketplace ratings/reviews.'),
            'route': 'PARTNER/OFFICIAL_API -> CLI_SDK(API-backed) -> LOCAL_PERSISTENT_BROWSER/EXTENSION for owned vendor forms',
        }
    if kind == 'editorial':
        return {
            'public': (m(public_http='Low', local_browser_agent='Low'), 'Public article/newsletter research.'),
            'auth': (m(local_browser_agent='Moderate', browser_extension='Moderate'), 'Authenticated contributor/subscriber navigation.'),
            'data': (m(public_http='Low', local_browser_agent='Low'), 'Public editorial/contact research.'),
            'submit': (m(local_browser_agent='Moderate', browser_extension='Moderate'), 'One tailored owned pitch/submission; no repetitive mass submission.'),
            'comment': (m(), 'No generic comment surface assumed.'),
            'dm': (m(local_browser_agent='Moderate', browser_extension='Moderate'), 'One relevant editorial/partner contact; avoid bulk outreach.'),
            'vote': (m(), 'Not a primary action.'),
            'review': (m(), 'Not a review channel.'),
            'route': 'PUBLIC_HTTP for research -> documented submission/email/API -> LOCAL_PERSISTENT_BROWSER/EXTENSION for one tailored submission',
        }
    return profile('directory')


def choose_kind(channel_type):
    t = channel_type.lower()
    if 'review / comparison' in t:
        return 'review'
    if any(x in t for x in ['social', 'video', 'live streaming', 'federated']):
        return 'social'
    if any(x in t for x in ['messaging', 'community / owned']):
        return 'messaging'
    if any(x in t for x in ['developer community', 'q&a', 'seo / growth forum', 'marketing community']):
        return 'developer'
    if any(x in t for x in ['community / launch', 'deal marketplace / launch']):
        return 'community'
    if any(x in t for x in ['marketplace', 'integration', 'affiliate', 'partner', 'freelance', 'creator / membership', 'template / ecosystem']):
        return 'marketplace'
    if any(x in t for x in ['newsletter', 'publishing', 'pr / media', 'events']):
        return 'editorial'
    return 'directory'


def override(domain, base):
    d = domain.lower().strip()
    p = base

    if d == 'linkedin.com':
        p = {
            'public': (m(public_http='Low', official_api='Low', cli_sdk='Low', local_browser_agent='Low', browser_extension='Low'), 'Single/bounded public browsing is low risk; profile crawling at scale is a different action.'),
            'auth': (m(official_api='Low', cli_sdk='Low', local_browser_agent='Moderate', browser_extension='Moderate'), 'Use OAuth/API for supported account/page data; keep browser session local.'),
            'data': (m(public_http='Low', official_api='Low', cli_sdk='Low', local_browser_agent='High', browser_extension='Moderate'), 'Main risk is Low via approved/public API/read routes; high-volume DOM profile research is materially riskier.'),
            'submit': (m(official_api='Low', cli_sdk='Low', unified_api='Low', local_browser_agent='High', browser_extension='Moderate'), 'Official Posts API/supported scheduler is the preferred write medium; CLI/SDK inherits API risk when API-backed.'),
            'comment': (m(official_api='Low', cli_sdk='Low', unified_api='Moderate', local_browser_agent='High', browser_extension='High'), 'Comments API provides a lower-risk official route for supported identities.'),
            'dm': (m(local_browser_agent='Critical', browser_extension='Critical'), 'No general low-risk API route assumed for automated cold DMs/connection outreach.'),
            'vote': (m(official_api='Low', cli_sdk='Low', local_browser_agent='Very High', browser_extension='Very High'), 'Reactions API is lower-risk for supported/authorized use; DOM-based engagement loops are much riskier.'),
            'review': (m(), 'Not a review channel.'),
            'route': 'LINKEDIN_POSTS/COMMENTS/REACTIONS API -> CLI_SDK(API-backed) -> supported scheduler -> browser only for unsupported owned-account gaps; no automated cold outreach',
        }
    elif d == 'reddit.com':
        p = {
            'public': (m(public_http='Low', official_api='Low', cli_sdk='Low', local_browser_agent='Low', browser_extension='Low'), 'Public subreddit/post/comment browsing.'),
            'auth': (m(official_api='Low', cli_sdk='Low', local_browser_agent='Moderate', browser_extension='Moderate'), 'Prefer Reddit API/Devvit for account-aware actions.'),
            'data': (m(public_http='Low', official_api='Low', cli_sdk='Low', local_browser_agent='Low', browser_extension='Low'), 'Brand/topic/post/comment monitoring is a normal low-risk read workload at bounded volume.'),
            'submit': (m(official_api='Low', cli_sdk='Low', local_browser_agent='Moderate', browser_extension='Moderate'), 'API/Devvit can submit posts; user-attributed actions may have additional interaction requirements.'),
            'comment': (m(official_api='Low', cli_sdk='Low', local_browser_agent='Moderate', browser_extension='Moderate'), 'API/Devvit supports comments; relevance/context still matters.'),
            'dm': (m(official_api='Moderate', cli_sdk='Moderate', local_browser_agent='High', browser_extension='High'), 'Keep outreach contextual and non-repetitive.'),
            'vote': (m(local_browser_agent='Very High', browser_extension='Very High'), 'Do not automate voting/brigading; current Devvit user actions do not expose up/down voting.'),
            'review': (m(), 'Not a review channel.'),
            'route': 'REDDIT API/DEVVIT -> CLI_SDK(API-backed) -> PUBLIC_HTTP for monitoring -> browser only for unsupported owned flows',
        }
    elif d == 'producthunt.com':
        p = {
            'public': (m(public_http='Low', official_api='Low', cli_sdk='Low', local_browser_agent='Low', browser_extension='Low'), 'Browsing products, makers and public launch pages is low risk.'),
            'auth': (m(official_api='Low', cli_sdk='Low', local_browser_agent='Low', browser_extension='Low'), 'Normal authenticated navigation in the user-owned session.'),
            'data': (m(public_http='Low', official_api='Low', cli_sdk='Low', local_browser_agent='Low', browser_extension='Low'), 'Product/profile/launch research and monitoring; Product Hunt API exposes public data.'),
            'submit': (m(official_api='Moderate', cli_sdk='Moderate', local_browser_agent='Moderate', browser_extension='Moderate'), 'Own-product submission/update is distinct from vote automation; API write is partial/use-case dependent, so persistent browser remains valid fallback.'),
            'comment': (m(local_browser_agent='Moderate', browser_extension='Moderate'), 'Genuine replies on an owned launch; avoid repetitive promotional commenting.'),
            'dm': (m(), 'No generic Product Hunt DM route assumed.'),
            'vote': (m(local_browser_agent='Critical', browser_extension='Critical'), 'Do not automate upvotes, vote exchange or multi-account amplification.'),
            'review': (m(), 'Not a review/rating channel in this model.'),
            'route': 'PRODUCT_HUNT_API/CLI for public data -> LOCAL_PERSISTENT_BROWSER/EXTENSION for one owned product submission/update -> quarantine vote amplification',
        }
    elif d == 'ycombinator.com':
        p = {
            'public': (m(public_http='Low', local_browser_agent='Low', browser_extension='Low'), 'Public HN browsing.'),
            'auth': (m(local_browser_agent='Low', browser_extension='Low'), 'Normal user-owned session navigation.'),
            'data': (m(public_http='Low', local_browser_agent='Low', browser_extension='Low'), 'Read/search/monitor public stories and comments.'),
            'submit': (m(local_browser_agent='Moderate', browser_extension='Moderate'), 'One relevant owned submission/Show HN is separate from engagement automation.'),
            'comment': (m(local_browser_agent='High', browser_extension='High'), 'Automated promotional/generated comment loops create materially higher reputation/account risk.'),
            'dm': (m(), 'No native DM route assumed.'),
            'vote': (m(local_browser_agent='Critical', browser_extension='Critical'), 'Do not automate voting/reputation manipulation.'),
            'review': (m(), 'Not a review channel.'),
            'route': 'PUBLIC_HTTP for browse/data -> LOCAL_PERSISTENT_BROWSER/EXTENSION for one owned submission -> quarantine automated comments/votes',
        }
    elif d == 'quora.com':
        p = {
            'public': (m(public_http='Low', local_browser_agent='Low', browser_extension='Low'), 'Public question/answer/topic browsing is low risk.'),
            'auth': (m(local_browser_agent='Moderate', browser_extension='Moderate'), 'Authenticated navigation is stateful but not equivalent to posting.'),
            'data': (m(public_http='Low', local_browser_agent='Low', browser_extension='Low'), 'Question/topic/brand research is low risk at bounded volume.'),
            'submit': (m(local_browser_agent='High', browser_extension='High'), 'Autonomous answer/post loops are substantially riskier than research.'),
            'comment': (m(local_browser_agent='High', browser_extension='High'), 'Generated repetitive engagement is high risk.'),
            'dm': (m(local_browser_agent='High', browser_extension='High'), 'Avoid automated unsolicited messaging.'),
            'vote': (m(local_browser_agent='Very High', browser_extension='Very High'), 'No automated reputation amplification.'),
            'review': (m(), 'Not a review channel.'),
            'route': 'PUBLIC_HTTP/browser for research -> quarantine autonomous posting/outreach/reputation actions',
        }
    elif d == 'stackoverflow.com':
        p = {
            'public': (m(public_http='Low', official_api='Low', cli_sdk='Low', local_browser_agent='Low'), 'Public Q&A browsing.'),
            'auth': (m(local_browser_agent='Moderate', browser_extension='Moderate'), 'Authenticated account navigation.'),
            'data': (m(public_http='Low', official_api='Low', cli_sdk='Low', local_browser_agent='Low'), 'Stack Exchange read/search APIs are preferred for structured research.'),
            'submit': (m(local_browser_agent='High', browser_extension='High'), 'Marketing-oriented autonomous Q&A posting is high risk; genuine human-quality technical contribution is a different workflow.'),
            'comment': (m(local_browser_agent='High', browser_extension='High'), 'Automated promotional/generated comments are high risk.'),
            'dm': (m(), 'No general DM route assumed.'),
            'vote': (m(local_browser_agent='Critical', browser_extension='Critical'), 'Do not automate voting/reputation actions.'),
            'review': (m(), 'Not a review channel.'),
            'route': 'STACK_EXCHANGE_API/PUBLIC_HTTP for research -> quarantine autonomous marketing writes and votes',
        }
    elif d == 'x.com':
        p = profile('social')
        p['dm'] = (m(official_api='Moderate', cli_sdk='Moderate', local_browser_agent='High', browser_extension='High'), 'Use official DM API only when entitlement/use case supports it; otherwise do not substitute DOM mass outreach.')
        p['route'] = 'X API/OAUTH -> CLI_SDK(API-backed) -> supported unified scheduler -> browser only for unsupported owned-account gaps'
    elif d == 'youtube.com':
        p = profile('social')
        p['submit'] = (m(official_api='Low', cli_sdk='Low', unified_api='Low', local_browser_agent='Moderate', browser_extension='Moderate'), 'Use YouTube Data API/upload or supported publishing integration for owned videos.')
        p['comment'] = (m(official_api='Low', cli_sdk='Low', local_browser_agent='Moderate', browser_extension='Moderate'), 'YouTube API supports comment operations for authorized use.')
        p['dm'] = (m(), 'No general YouTube DM automation route assumed.')
    elif d in {'facebook.com', 'instagram.com', 'threads.net', 'tiktok.com', 'pinterest.com', 'bsky.app', 'joinmastodon.org'}:
        p = profile('social')
    elif d in {'discord.com', 'telegram.org', 'whatsapp.com'}:
        p = profile('messaging')
    return p


def main():
    with CSV_PATH.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f))
    if len(rows) < 4:
        raise SystemExit('unexpected CSV structure')
    header = rows[3]
    for col in ACTION_COLUMNS:
        if col not in header:
            header.append(col)
    width = len(header)
    for row in rows[:3]:
        row.extend([''] * (width - len(row)))
    index = {c: i for i, c in enumerate(header)}
    rows[1][0] = ('Rank #1 = start first. Ordered for general B2B/developer/AI SaaS using buyer intent, reach, trust, '
                  'repeatability, ecosystem fit and current actionability. P0/P1/P2/P3 now follow the strict rank. '
                  'Human Review and coarse platform-level risk fields are contextual metadata only; runtime routing uses '
                  'the action-specific risk columns, where each action main risk is the minimum risk among supported execution media.')

    for row in rows[4:]:
        row.extend([''] * (width - len(row)))
        kind = choose_kind(row[index['Channel Type']])
        p = override(row[index['Domain']], profile(kind))
        mapping = {
            'Public Browse Action Risk': 'public',
            'Authenticated Browse Action Risk': 'auth',
            'Data Collection Action Risk': 'data',
            'Own Content Submit/Post Action Risk': 'submit',
            'Comment/Reply Action Risk': 'comment',
            'DM/Outreach Action Risk': 'dm',
            'Vote/Like/Follow Action Risk': 'vote',
            'Review/Rating Action Risk': 'review',
        }
        for col, key in mapping.items():
            media, note = p[key]
            row[index[col]] = cell(media, note)
        row[index['Recommended Execution Method']] = p['route']
        row[index['Action Risk Model']] = 'action-medium-v1:min-supported-medium-risk; CLI/SDK inherits underlying API risk; N/A means no supported/assumed route'

    with CSV_PATH.open('w', encoding='utf-8', newline='') as f:
        csv.writer(f, lineterminator='\n').writerows(rows)


if __name__ == '__main__':
    main()
