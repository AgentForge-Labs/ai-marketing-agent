"""Executable runtime primitives for the AI Marketing Agent."""

from .catalogue import Channel, ChannelCatalogue, CatalogueValidationError
from .storage import ImportSummary, MigrationError, RuntimeStore, apply_migrations, connect_sqlite
from .url_preflight import PreflightResult, URLValidationError, normalize_http_url, preflight_url
from .risk_router import (
    ACTION_COLUMNS,
    MEDIA_PRIORITY,
    RISK_ORDER,
    ActionRisk,
    PlatformRiskRouter,
    RouteDecision,
    RiskCellError,
    parse_action_risk,
)
from .browser import BrowserProvider, BrowserLaunchResult, get_browser_for_tenant, get_tenant_proxy
from .email_verification import fetch_code, fetch_link, handle_verification
from .account_reuse import BanState, PlatformPolicy, assert_reopen_allowed, audit_record as account_reuse_audit_record
from .policy_crawler import CrawlSignals, crawl_policy
from .policy_registry import PolicyRecord, PolicyRegistry, evaluate_policy_gate
from .queue import complete_job, enqueue, fail_job, idempotency_key, lease_next_job, quarantine_job, recover_stalled
from .execution_policy import ExecutionAuthorization, authorize_execution
from .human_mouse import HumanMouse, get_human_mouse
from .captcha_ensemble import CaptchaResult, CaptchaTask, solve_captcha
from .semantic_browser import SemanticBrowser, get_semantic_browser
from .runner import AutonomousRunner, RunnerConfig, RunnerResult

__all__ = [
    "ACTION_COLUMNS",
    "MEDIA_PRIORITY",
    "RISK_ORDER",
    "ActionRisk",
    "CatalogueValidationError",
    "ImportSummary",
    "MigrationError",
    "RuntimeStore",
    "PreflightResult",
    "URLValidationError",
    "Channel",
    "ChannelCatalogue",
    "PlatformRiskRouter",
    "RouteDecision",
    "RiskCellError",
    "parse_action_risk",
    "apply_migrations",
    "connect_sqlite",
    "normalize_http_url",
    "preflight_url",
    "BanState",
    "PlatformPolicy",
    "assert_reopen_allowed",
    "account_reuse_audit_record",
    "CrawlSignals",
    "crawl_policy",
    "complete_job",
    "enqueue",
    "fail_job",
    "idempotency_key",
    "lease_next_job",
    "quarantine_job",
    "recover_stalled",
    "PolicyRecord",
    "PolicyRegistry",
    "evaluate_policy_gate",
    "ExecutionAuthorization",
    "authorize_execution",
    "HumanMouse",
    "get_human_mouse",
    "CaptchaTask",
    "CaptchaResult",
    "solve_captcha",
    "SemanticBrowser",
    "get_semantic_browser",
    "RunnerConfig",
    "RunnerResult",
    "AutonomousRunner",
    "BrowserProvider",
    "BrowserLaunchResult",
    "get_browser_for_tenant",
    "get_tenant_proxy",
    "fetch_code",
    "fetch_link",
    "handle_verification",
]
