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
]
