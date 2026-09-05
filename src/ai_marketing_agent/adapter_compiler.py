"""Adapter compiler (Phase 5, #8) — bounded JSON DSL -> executable action plan.

Allowed browser ops: goto, fill, select, check, upload, click, waitFor,
assertText, assertUrl, extract, captureScreenshot.
Free-form JavaScript / eval is prohibited at compile time (deep scan).
API flows compile to request plans with vault:// header refs (no secrets).

Also: form fingerprinting (sha256 of normalized structure), drift detection,
and promotion gating (schema + dry-run + confidence + regression gates).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

BROWSER_OPS = frozenset({
    "goto", "fill", "select", "check", "upload", "click",
    "waitFor", "assertText", "assertUrl", "extract", "captureScreenshot",
})

BANNED_TOKENS = ("eval", "javascript:", "Function(", "new Function", "<script")


class CompileError(ValueError):
    """Raised when an adapter contract violates compiler bounds."""


def _deep_scan_forbidden(node: Any, path: str = "$") -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            lowered = str(key).lower()
            if any(tok.lower() in lowered for tok in ("eval", "javascript", "__proto__")):
                raise CompileError(f"forbidden key at {path}.{key}")
            _deep_scan_forbidden(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            _deep_scan_forbidden(value, f"{path}[{i}]")
    elif isinstance(node, str):
        lowered = node.lower()
        if ("javascript:" in lowered or "<script" in lowered or "new function" in lowered
                or re.search(r"\beval\s*\(", lowered)):
            raise CompileError(f"forbidden inline script at {path}")


def _require_locator(loc: Any, path: str) -> Dict[str, Any]:
    if not isinstance(loc, dict) or "kind" not in loc:
        raise CompileError(f"locator without kind at {path}")
    if loc["kind"] not in ("role", "label", "placeholder", "name", "id", "testId", "text", "css"):
        raise CompileError(f"unknown locator kind at {path}: {loc['kind']!r}")
    return loc


def compile_flow(flow: Dict[str, Any], *, dry_run: bool = False) -> List[Dict[str, Any]]:
    """Compile one flow (web kind) into a bounded action plan.

    dry_run=True converts submit clicks into no-op assertions (fill without submit).
    """
    if not isinstance(flow, dict):
        raise CompileError("flow must be an object")
    _deep_scan_forbidden(flow)
    plan: List[Dict[str, Any]] = []

    def _compile_step(step: Dict[str, Any], prefix: str) -> None:
        if "entryUrl" in step and prefix == "flow":
            plan.append({"op": "goto", "url": step["entryUrl"]})
        for f in step.get("fields", []) or []:
            loc = _require_locator((f.get("locators") or [None])[0], f"{prefix}.fields")
            ftype = f.get("fieldType", "text")
            value_from = f.get("valueFrom")
            if not value_from:
                raise CompileError(f"field without valueFrom at {prefix}")
            if ftype in ("select", "multiselect"):
                plan.append({"op": "select", "locator": loc, "valueFrom": value_from,
                             "optionsValueFrom": f.get("optionsValueFrom")})
            elif ftype == "checkbox":
                plan.append({"op": "check", "locator": loc, "valueFrom": value_from})
            elif ftype == "file":
                plan.append({"op": "upload", "locator": loc, "uploadRef": f.get("uploadRef")})
            else:
                plan.append({"op": "fill", "locator": loc, "valueFrom": value_from})
        submit = step.get("submit")
        if submit:
            loc = _require_locator(submit.get("locator"), f"{prefix}.submit")
            if dry_run:
                plan.append({"op": "assertText", "note": f"dry-run: submit skipped at {prefix}"})
            else:
                plan.append({"op": "click", "locator": loc})
        wait = step.get("wait")
        if wait:
            plan.append({"op": "waitFor", "kind": wait.get("kind"), "matches": wait.get("matches")})

    if "steps" in flow:
        steps = flow["steps"]
        if not isinstance(steps, list) or len(steps) < 2:
            raise CompileError("multi-step flow needs >= 2 steps")
        for i, step in enumerate(steps):
            _compile_step(step, f"steps[{i}]")
    else:
        _compile_step(flow, "flow")

    for sig in flow.get("success", []) or []:
        if sig.get("kind") == "url":
            plan.append({"op": "assertUrl", "matches": sig.get("matches", "")})
        elif sig.get("kind") == "text":
            plan.append({"op": "assertText", "matches": sig.get("matches", "")})
    plan.append({"op": "captureScreenshot", "redacted": True})
    for step in plan:
        if step["op"] not in BROWSER_OPS:
            raise CompileError(f"op out of bounds: {step['op']!r}")
    return plan


def compile_api_flow(flow: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Compile kind=api flow: requests with vault:// header refs, idempotency, expectations."""
    _deep_scan_forbidden(flow)
    if not flow.get("baseUrl") or not flow.get("requests"):
        raise CompileError("api flow needs baseUrl + requests")
    plan = []
    for req in flow["requests"]:
        if req.get("method") not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            raise CompileError(f"bad method: {req.get('method')!r}")
        for header, ref in (req.get("headersFrom") or {}).items():
            if not str(ref).startswith("vault://"):
                raise CompileError(f"header {header!r} must use vault:// ref")
        plan.append({
            "op": "api_request",
            "method": req["method"],
            "path": req.get("path", ""),
            "payloadFrom": req.get("payloadFrom", {}),
            "headersFrom": req.get("headersFrom", {}),
            "idempotencyHeader": req.get("idempotencyHeader"),
            "expectStatus": req.get("expectStatus", 200),
            "successExtract": req.get("successExtract", {}),
        })
    return plan


def fingerprint_form(form: Dict[str, Any]) -> str:
    """sha256 over normalized structure: action/method, fields(name/type/label/required/options), submit locator."""
    norm = {
        "action": (form.get("form") or {}).get("action", ""),
        "method": (form.get("form") or {}).get("method", ""),
        "fields": sorted(
            [{
                "name": f.get("name", ""),
                "type": f.get("type", ""),
                "label": f.get("accessName", "") or f.get("placeholder", ""),
                "required": bool(f.get("required", False)),
                "options": sorted(o.get("value", "") for o in (f.get("options") or [])),
            } for f in (form.get("fields") or [])],
            key=lambda d: d["name"],
        ),
        "submit": str(((form.get("submit") or {}).get("locator") or {}).get("kind", "")),
    }
    blob = json.dumps(norm, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def detect_drift(old_fingerprint: str, new_fingerprint: str) -> bool:
    """True when the form changed -> runner must not submit (needs_remap)."""
    return old_fingerprint != new_fingerprint


@dataclass
class PromotionGates:
    schema_valid: bool = False
    dry_run_pass: bool = False
    confidence: float = 0.0
    confidence_threshold: float = 0.85
    regression_pass: bool = False

    def promotable(self) -> bool:
        return (self.schema_valid and self.dry_run_pass and self.regression_pass
                and self.confidence >= self.confidence_threshold)


def gate_promotion(gates: PromotionGates) -> Dict[str, Any]:
    """Promotion only after ALL gates; otherwise quarantine (never silent execution)."""
    ok = gates.promotable()
    return {"promote": ok, "next": "production" if ok else "quarantine",
            "confidence": gates.confidence, "threshold": gates.confidence_threshold}
