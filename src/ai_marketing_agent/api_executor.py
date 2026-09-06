"""Official-API executor (#32) — runs compile_api_flow plans over HTTP.

Covers the 77 Low `official_api` submit routes the browser runner cannot reach.
Auth headers resolve from vault:// at run time (never from the adapter file);
payloads bind valueFrom via the resolved `values` dict. Evidence is redacted:
no raw bodies, tokens or keys in logs/details. Retries honor the adapter retry
policy (timeout/networkError/rateLimited only); anything else fails closed.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urljoin

import requests

from .adapter_compiler import compile_api_flow
from .queue import idempotency_key

Loader = Callable[[str], Optional[str]]

RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
_SECRET_PATTERN = re.compile(r"(api[_-]?key|token|secret|password|authorization)(\"?\s*[:=]\s*\"?)[^\"&\s,}]+", re.I)


def _redact(text: str, limit: int = 300) -> str:
    text = (text or "")[:limit]
    return _SECRET_PATTERN.sub(r"\1\2[redacted]", text)


@dataclass
class ApiResult:
    status: str  # done | failed
    detail: Dict[str, Any] = field(default_factory=dict)


def _resolve_headers(headers_from: Dict[str, str], loader: Loader) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    for name, ref in (headers_from or {}).items():
        if not str(ref).startswith("vault://"):
            raise ValueError(f"header {name!r} must use vault:// ref")
        val = loader(ref)
        if val is None:
            raise ValueError(f"unresolvable header ref: {ref}")
        headers[name] = val
    return headers


def _resolve_payload(payload_from: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for key, vf in (payload_from or {}).items():
        if isinstance(vf, str) and vf in values:
            payload[key] = values[vf]
        elif isinstance(vf, str) and "." in vf:
            raise ValueError(f"unresolvable payload ref: {vf!r}")
        else:
            payload[key] = vf  # literal constant
    return payload


def _extract(data: Any, spec: Dict[str, str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name, path in (spec or {}).items():
        cur: Any = data
        try:
            for part in str(path).split("."):
                cur = cur[part] if isinstance(cur, dict) else cur[int(part)]
            out[name] = cur
        except (KeyError, IndexError, ValueError, TypeError):
            out[name] = None
    return out


def execute_api_flow(
    adapter: Dict[str, Any],
    flow: Dict[str, Any],
    values: Dict[str, Any],
    *,
    loader: Optional[Loader] = None,
    timeout_s: float = 15.0,
    sleep: Callable[[float], None] = time.sleep,
) -> ApiResult:
    """Execute one compiled API flow. Raises ValueError on contract violations."""
    from .values import default_loader

    load = loader or default_loader
    plan = compile_api_flow(flow)
    base = flow.get("baseUrl", "")
    if not (base.startswith("http://") or base.startswith("https://")):
        raise ValueError(f"baseUrl must be http(s): {base!r}")
    retry = adapter.get("retry") or {}
    max_attempts = max(1, int(retry.get("maxAttempts", 1)))
    backoffs: List[float] = list(retry.get("backoffSeconds", [60])) or [60]
    retry_on = set(retry.get("retryOn", ["timeout", "networkError", "rateLimited"]))

    step_results: List[Dict[str, Any]] = []
    for step in plan:
        url = urljoin(base.rstrip("/") + "/", step["path"].lstrip("/"))
        headers = _resolve_headers(step["headersFrom"], load)
        if step.get("idempotencyHeader"):
            headers[step["idempotencyHeader"]] = idempotency_key(url, json_dumps(values))
        payload = _resolve_payload(step["payloadFrom"], values)
        expect = int(step.get("expectStatus", 200))
        last_err: Optional[str] = None
        for attempt in range(1, max_attempts + 1):
            try:
                resp = requests.request(step["method"], url, json=payload or None,
                                        headers=headers, timeout=timeout_s)
                if resp.status_code == expect:
                    try:
                        data = resp.json()
                    except ValueError:
                        data = {"_text": resp.text[:300]}
                    step_results.append({"path": step["path"], "status": resp.status_code,
                                         "extracted": _extract(data, step.get("successExtract", {}))})
                    last_err = None
                    break
                kind = "rateLimited" if resp.status_code == 429 else (
                    "networkError" if resp.status_code in RETRYABLE_STATUS else "unexpected_status")
                last_err = f"{kind}:{resp.status_code}:{_redact(resp.text)}"
            except (requests.Timeout,) as e:
                kind, last_err = "timeout", f"timeout:{str(e)[:120]}"
            except (requests.ConnectionError,) as e:
                kind, last_err = "networkError", f"networkError:{str(e)[:120]}"
            except requests.RequestException as e:
                return ApiResult(status="failed", detail={"reason": f"request_error:{str(e)[:150]}",
                                                           "steps": step_results})
            if kind not in retry_on or attempt >= max_attempts:
                break
            sleep(float(backoffs[min(attempt - 1, len(backoffs) - 1)]))
        if last_err is not None:
            return ApiResult(status="failed",
                             detail={"reason": last_err[:200], "steps": step_results})
    return ApiResult(status="done", detail={"steps": step_results})


def json_dumps(values: Dict[str, Any]) -> str:
    import json as _json
    return _json.dumps(values, sort_keys=True, default=str)


def default_api_fn(adapter: Dict[str, Any], decision: Any, flow: Dict[str, Any],
                   values: Dict[str, Any]) -> ApiResult:
    """Worker api_auto branch default (#29 wiring)."""
    return execute_api_flow(adapter, flow, values)
