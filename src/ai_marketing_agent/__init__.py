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
from .analytics import AnalyticsStore, ChannelScore, compute_score
from .adapter_compiler import (
    BROWSER_OPS,
    CompileError,
    PromotionGates,
    compile_api_flow,
    compile_flow,
    detect_drift,
    fingerprint_form,
    gate_promotion,
)
from .content_core import ContentArtifact, ContentRequest, fingerprint, generate_content, jaccard_similarity, verify_claims
from .engagement import EngagementEvent, EngagementOutcome, RateLimiter, draft_reply, gate_event, handle_event
from .orchestrator import Campaign, ChannelCandidate, OrchestratorState, next_best_action, release, score_channel
from .discovery import extract_page_model
from .perf import SLO, TTLCache, ConcurrencyGate, BenchmarkResult, benchmark
from .rollout import GATE_ITEMS, GateEvidence, GateVerdict, evaluate_gate, rollout_order
from .saas import SaaSStore, Tenant
from .evasion import AnomalySignals, DeadPool, EvasionDecision, check_dead_pool, evaluate as evaluate_anomalies
from .persona import Persona, PersonaRegistry, refresh_oauth_token, totp_now
from .policy_crawler import CrawlSignals, crawl_policy
from .submit import (
    AmbiguousOutcome,
    SubmitPlan,
    ensure_submit_tables,
    pilot_checklist,
    pre_submit_check,
    record_submission,
    resolve_ambiguous,
)
from .policy_registry import PolicyRecord, PolicyRegistry, evaluate_policy_gate
from .queue import complete_job, enqueue, fail_job, idempotency_key, lease_next_job, quarantine_job, recover_stalled
from .vault import EnvVault, require_vault_ref, resolve_secret
from .execution_policy import ExecutionAuthorization, authorize_execution
from .human_mouse import HumanMouse, get_human_mouse
from .captcha_ensemble import CaptchaResult, CaptchaTask, inject_token, solve_captcha
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
    "AmbiguousOutcome",
    "SubmitPlan",
    "ensure_submit_tables",
    "pilot_checklist",
    "pre_submit_check",
    "record_submission",
    "resolve_ambiguous",
    "BROWSER_OPS",
    "CompileError",
    "PromotionGates",
    "compile_api_flow",
    "compile_flow",
    "detect_drift",
    "fingerprint_form",
    "gate_promotion",
    "AnomalySignals",
    "DeadPool",
    "EvasionDecision",
    "check_dead_pool",
    "evaluate_anomalies",
    "AnalyticsStore",
    "ChannelScore",
    "compute_score",
    "GATE_ITEMS",
    "GateEvidence",
    "GateVerdict",
    "evaluate_gate",
    "rollout_order",
    "SLO",
    "TTLCache",
    "ConcurrencyGate",
    "BenchmarkResult",
    "benchmark",
    "extract_page_model",
    "SaaSStore",
    "Tenant",
    "Campaign",
    "ChannelCandidate",
    "OrchestratorState",
    "next_best_action",
    "release",
    "score_channel",
    "EngagementEvent",
    "EngagementOutcome",
    "RateLimiter",
    "draft_reply",
    "gate_event",
    "handle_event",
    "ContentArtifact",
    "ContentRequest",
    "fingerprint",
    "generate_content",
    "jaccard_similarity",
    "verify_claims",
    "Persona",
    "PersonaRegistry",
    "refresh_oauth_token",
    "totp_now",
    "EnvVault",
    "resolve_secret",
    "require_vault_ref",
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
    "inject_token",
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
