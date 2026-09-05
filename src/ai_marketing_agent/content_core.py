"""Content Core (Phase 4, #7) — verified product facts -> policy-valid content.

Pipeline: product profile ingestion -> brand/persona voice layers ->
platform-native templates -> claim verification -> disclosure injection ->
similarity/fingerprint gate -> UTM/tracking metadata + provenance.
Deterministic, stdlib only, LLM-free (LLM prompts carry provenance in Phase 4+).

Fail-closed: unsupported claims and fabricated social proof are rejected,
never rewritten silently.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "product-profile.schema.json"

# Claim patterns that MUST be grounded in the product profile (case-insensitive).
GROUNDED_CLAIM_RES = [
    re.compile(r"(\b\d+\s?%|%\s?\d+)"),                 # percentages (EN + TR order)
    re.compile(r"\b\d[\d.,]*\s?(k|m|b|bn|million)\b", re.I),  # scale numbers
    re.compile(r"#\s?1\b|best\b|first\b|only\b", re.I),       # superlatives
    re.compile(r"\$\s?\d|€\s?\d|£\s?\d|\d\s?(usd|eur|tl)\b", re.I),  # prices
    re.compile(r"\b(customer|client|user)s?\b.{0,20}\b(said|says|review|★|stars?)\b", re.I),  # testimonials
]

BANNED_PHRASES = [
    "guaranteed results", "get rich", "no risk", "100% free money",
    "click here now!!!",
]

TEMPLATE_FIELDS = ("title", "body", "summary")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_product_profile(path: str | Path) -> Dict[str, Any]:
    """Load + minimal-validate a product-profile.json against required keys."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        schema = json.loads(PRODUCT_SCHEMA_PATH.read_text(encoding="utf-8"))
        required = schema.get("required", [])
    except OSError:
        required = ["id", "name", "website", "taglines", "descriptions", "categories", "assets", "founder"]
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"product profile missing required keys: {missing}")
    return data


def _profile_text_blob(profile: Dict[str, Any]) -> str:
    parts: List[str] = [str(profile.get("name", "")), str(profile.get("pricingSummary", ""))]
    for section in ("taglines", "descriptions"):
        node = profile.get(section, {})
        if isinstance(node, dict):
            parts.extend(str(v) for v in node.values())
    parts.extend(str(c) for c in profile.get("categories", []))
    parts.extend(str(u) for u in profile.get("useCases", []))
    founder = profile.get("founder", {})
    if isinstance(founder, dict):
        parts.append(str(founder.get("bio", "")))
    return "\n".join(parts)


def verify_claims(text: str, profile: Dict[str, Any]) -> List[str]:
    """Return list of violation reasons; empty means all claims grounded.

    A grounded-claim pattern matches only if a numeric/keyword anchor from the
    match also appears in the verified profile blob (conservative overlap).
    """
    blob = _profile_text_blob(profile).lower()
    violations: List[str] = []
    lowered = text.lower()
    for phrase in BANNED_PHRASES:
        if phrase in lowered:
            violations.append(f"banned_phrase:{phrase}")
    for rx in GROUNDED_CLAIM_RES:
        for m in rx.finditer(text):
            anchor = re.sub(r"\W+", " ", m.group(0)).strip().lower()
            tokens = [t for t in anchor.split() if len(t) > 2 and not t.isdigit()]
            numbers = re.findall(r"\d[\d.,]*", m.group(0))
            grounded = any(t in blob for t in tokens) or any(n in blob for n in numbers)
            if not grounded:
                violations.append(f"ungrounded_claim:{m.group(0)[:60]}")
    return violations


def _tokens(text: str) -> set:
    return set(re.findall(r"[a-z0-9ğüşöçı]{3,}", text.lower()))


def jaccard_similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class ContentRequest:
    operation: str  # post | comment | listing | dm
    channel_class: str = ""
    persona_voice: Dict[str, Any] = field(default_factory=dict)
    brand_voice: Dict[str, Any] = field(default_factory=dict)
    locale: str = ""
    max_similarity: float = 0.20
    campaign_id: str = ""
    template: str = "problem_solution"


@dataclass(frozen=True)
class ContentArtifact:
    body: str
    title: str = ""
    summary: str = ""
    fingerprint: str = ""
    disclosure_markers: List[str] = field(default_factory=list)
    utm: Dict[str, str] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
    policy_class: str = "needs_review"


DISCLOSURE_BY_OPERATION = {
    "post": ["#ad"],
    "comment": [],
    "listing": ["sponsored"],
    "dm": ["opt-in"],
}

VOICE_PREFIX = {
    "technical": "Teknik not: ",
    "storyteller": "Deneyimim: ",
    "skeptic": "Şüpheyle yaklaştım ama ",
}


def generate_content(
    profile: Dict[str, Any],
    request: ContentRequest,
    *,
    corpus: Optional[List[str]] = None,
    disclosure_override: Optional[List[str]] = None,
) -> ContentArtifact:
    """Deterministic assembly from verified facts. Raises ValueError on violation.

    Steps: template fill from profile facts -> voice layering -> disclosure ->
    similarity gate vs corpus -> UTM + provenance.
    """
    name = str(profile.get("name", "")).strip()
    if not name:
        raise ValueError("profile name required")
    use_case = (profile.get("useCases") or [""])[0]
    tagline = ((profile.get("taglines") or {}).get("medium120") or (profile.get("taglines") or {}).get("short60") or "")
    voice = str(request.persona_voice.get("tone", "") or request.brand_voice.get("tone", "")).lower()
    prefix = VOICE_PREFIX.get(voice, "")

    if request.template == "problem_solution":
        body = f"{prefix}{use_case} için {name} kullanıyorum. {tagline}".strip()
        title = f"{name} deneyimim"
    elif request.template == "comparison":
        body = f"{prefix}{name} ile önceki çözümümü karşılaştırdım: {tagline}".strip()
        title = f"{name} karşılaştırma"
    elif request.template == "question":
        body = f"{prefix}{name} kullanan var mı? {tagline}".strip()
        title = f"{name} hakkında soru"
    else:
        raise ValueError(f"unknown template: {request.template}")

    violations = verify_claims(f"{title}\n{body}", profile)
    if violations:
        raise ValueError(f"claim violations: {violations}")

    markers = list(disclosure_override if disclosure_override is not None else DISCLOSURE_BY_OPERATION.get(request.operation, []))
    if markers:
        body = f"{body} {' '.join(markers)}"

    corpus = corpus or []
    for existing in corpus:
        if jaccard_similarity(body, existing) > request.max_similarity:
            raise ValueError(f"similarity above threshold {request.max_similarity}")

    utm = {
        "utm_source": request.channel_class or "direct",
        "utm_medium": request.operation,
        "utm_campaign": request.campaign_id or profile.get("id", ""),
        "utm_content": fingerprint(body)[:12],
    }
    return ContentArtifact(
        body=body, title=title, summary=body[:160],
        fingerprint=fingerprint(body), disclosure_markers=markers, utm=utm,
        provenance={"template": request.template, "profile_id": profile.get("id", ""),
                    "locale": request.locale, "generator": "content_core/1.0",
                    "generated_at": _utc_now()},
        policy_class="auto_valid",
    )
