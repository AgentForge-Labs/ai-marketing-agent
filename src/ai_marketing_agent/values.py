"""Values resolver (#30) — valueFrom -> real value, fail-closed.

The runner executes `values[valueFrom]`; this module is the only sanctioned
builder: product/persona/content dotted paths, vault:// refs via a loader
callback, and auth credentials from adapter auth *Ref fields. Plaintext
secrets are never accepted: *Ref fields must be vault:// (require_vault_ref),
and a missing/unresolvable required value raises instead of filling garbage.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .vault import require_vault_ref, resolve_secret

Loader = Callable[[str], Optional[str]]


class ValuesError(ValueError):
    pass


def _dotted(source: Dict[str, Any], path: str, *, what: str) -> Any:
    cur: Any = source
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise ValuesError(f"unknown {what} path: {path!r}")
        cur = cur[part]
    return cur


def _flow_fields(flow: Dict[str, Any]) -> List[Dict[str, Any]]:
    fields: List[Dict[str, Any]] = list(flow.get("fields", []) or [])
    for step in flow.get("steps", []) or []:
        fields.extend(step.get("fields", []) or [])
    return fields


def _require_ref(ref: str, field: str) -> str:
    try:
        return require_vault_ref(ref, field=field)
    except ValueError as e:
        raise ValuesError(str(e))


def default_loader(ref: str) -> Optional[str]:
    """Vault/env-backed loader (no plaintext passthrough for secrets)."""
    _require_ref(ref, "secret ref")
    return resolve_secret(ref)


def resolve_values(
    adapter: Dict[str, Any],
    operation: str,
    *,
    loader: Loader = default_loader,
    content: Optional[Dict[str, Any]] = None,
    persona: Optional[Dict[str, Any]] = None,
    product: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Resolve every valueFrom used by the operation's flow. Raises ValuesError."""
    flow = (adapter.get("flows") or {}).get(operation)
    if not isinstance(flow, dict):
        raise ValuesError(f"no flow: {operation}")
    auth = adapter.get("auth") or {}
    out: Dict[str, Any] = {}
    for field in _flow_fields(flow):
        vf = field.get("valueFrom")
        if not vf:
            continue
        if vf in out:
            continue
        out[vf] = _resolve_one(vf, adapter, auth, loader=loader,
                               content=content, persona=persona, product=product)
    return out


def _resolve_one(
    vf: str,
    adapter: Dict[str, Any],
    auth: Dict[str, Any],
    *,
    loader: Loader,
    content: Optional[Dict[str, Any]],
    persona: Optional[Dict[str, Any]],
    product: Optional[Dict[str, Any]],
) -> Any:
    if vf.startswith("vault://"):
        val = loader(vf)
        if val is None:
            raise ValuesError(f"unresolvable secret ref: {vf}")
        return val
    if vf.startswith("content."):
        if content is None:
            raise ValuesError(f"no content provided for {vf!r}")
        return _dotted(content, vf[len("content."):], what="content")
    if vf.startswith("persona."):
        if persona is None:
            raise ValuesError(f"no persona provided for {vf!r}")
        return _dotted(persona, vf[len("persona."):], what="persona")
    if vf.startswith("product.") or vf.startswith("productProfile."):
        if product is None:
            raise ValuesError(f"no product profile provided for {vf!r}")
        prefix = "product." if vf.startswith("product.") else "productProfile."
        return _dotted(product, vf[len(prefix):], what="product")
    if vf in ("auth.username", "auth.password", "auth.apiKey"):
        ref_key = {"auth.username": "usernameRef", "auth.password": "passwordRef",
                   "auth.apiKey": "credentialRef"}[vf]
        ref = auth.get(ref_key)
        if ref is None:
            raise ValuesError(f"adapter auth.{ref_key} missing for {vf!r}")
        _require_ref(ref, f"auth.{ref_key}")
        val = loader(ref)
        if val is None:
            raise ValuesError(f"unresolvable secret ref: {ref}")
        return val
    raise ValuesError(f"unknown valueFrom: {vf!r}")


def default_values_fn(adapter: Dict[str, Any], job: Any) -> Dict[str, Any]:
    """Worker default: vault-backed, no content/persona (their refs fail closed)."""
    return resolve_values(adapter, job.operation)
