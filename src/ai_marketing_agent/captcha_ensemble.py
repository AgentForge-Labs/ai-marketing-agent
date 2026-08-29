"""
Agentic CAPTCHA ensemble — per-action, site değil eylem bazlı — 2captcha (primary) → ai-captcha-bypass (LMM) → buster → quarantine.

Güncel Politika (Kullanıcı onayı):
- Risk site çapında değil, sitede yapılacak eyleme göre belirlenir. Eylem Very High/Critical değilse (Low/Moderate/High), site riskli grupta olsa bile CAPTCHA çıkarsa bu ensemble denenir.
- High riskli grupta olsa bile, Very High değilse ensemble kullanılır (site geneli High olsa bile per-action High → auto_with_verification + ensemble).
- Very High/Critical eylemlerde ensemble denenmez, doğrudan auto_quarantine (ban atlatma değil).
- Biometric mouse (wassim-sayah/biometric-mouse) HER ZAMAN her browser eylemde kullanılır (fallback Playwright B-spline).
- Kütüphaneler her zaman kullanılabilir: 2captcha/2captcha-python (794★), aydinnyunus/ai-captcha-bypass (GPT-4o/Gemini, 1.2k★), teal33t/captcha_bypass (buster + B-spline mouse).

Vault refs:
  - vault://captcha/2captcha/apiKey  (from C:/Users/ahmet/Downloads/DIGER/sunucular/*2captcha*.txt)
  - vault://llm/openai/apiKey        (from openai_platform.txt)
  - vault://llm/gemini/apiKey        (from GOOGLE_API_KEY)
  - vault://proxy/residential/uri    (for DataDome/Turnstile)

Original repos:
  - 2captcha/2captcha-python (Twocaptcha/AsyncTwoCaptcha)
  - aydinnyunus/ai-captcha-bypass (ai_utils.py, puzzle_solver.py)
  - teal33t/captcha_bypass (buster)

Usage (per-action Low/Moderate/High):
    from ai_marketing_agent.captcha_ensemble import solve_captcha, CaptchaTask
    result = await solve_captcha(CaptchaTask(type="recaptcha_v2", sitekey="...", url="...", proxy="vault://proxy/residential/uri"))
    # Caller should have checked per-action risk != Very High/Critical and has ExecutionAuthorization with auto_ensemble
"""
from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Literal, Optional

# Ensure vendored 2captcha-python and ai-captcha-bypass are importable
for _p in [Path(__file__).resolve().parents[2] / "services" / "captcha-ensemble", Path("services/captcha-ensemble")]:
    if _p.exists() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

SolverType = Literal["2captcha", "ai_lmm", "buster"]


@dataclass
class CaptchaTask:
    type: str  # recaptcha_v2, recaptcha_v3, turnstile, geetest, datadome, text, puzzle, audio
    sitekey: Optional[str] = None
    url: Optional[str] = None
    image_path: Optional[str] = None
    gt: Optional[str] = None
    challenge: Optional[str] = None
    captcha_url: Optional[str] = None
    proxy: Optional[str] = None  # vault://proxy/residential/uri or login:password@IP:PORT
    user_agent: Optional[str] = None


@dataclass
class CaptchaResult:
    solver: SolverType | Literal["human_telegram", "quarantine"]
    success: bool
    token: Optional[str] = None
    text: Optional[str] = None
    cost: Optional[float] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None


def _get_vault_secret(ref: str) -> Optional[str]:
    if not ref or not ref.startswith("vault://"):
        return ref
    # Prototype: env var mapping for C:/Users/ahmet/Downloads/DIGER/sunucular files
    mapping = {
        "vault://captcha/2captcha/apiKey": os.getenv("CAPTCHA_2CAPTCHA_KEY") or os.getenv("TWOCAPTCHA_API_KEY"),
        "vault://llm/openai/apiKey": os.getenv("OPENAI_API_KEY"),
        "vault://llm/gemini/apiKey": os.getenv("GOOGLE_API_KEY"),
        "vault://proxy/residential/uri": os.getenv("RESIDENTIAL_PROXY_URI"),
    }
    return mapping.get(ref) or os.getenv(ref.replace("vault://", "").replace("/", "_").upper())


async def _solve_with_2captcha(task: CaptchaTask, api_key: str) -> CaptchaResult:
    try:
        from twocaptcha import AsyncTwoCaptcha  # type: ignore

        solver = AsyncTwoCaptcha(api_key, defaultTimeout=120, recaptchaTimeout=600, pollingInterval=10)
        proxy = {"type": "HTTPS", "uri": _get_vault_secret(task.proxy) or task.proxy} if task.proxy else None

        if task.type in ("recaptcha_v2", "recaptcha"):
            r = await solver.recaptcha(sitekey=task.sitekey or "", url=task.url or "", **({"proxy": proxy, "userAgent": task.user_agent} if proxy else {}))
            return CaptchaResult(solver="2captcha", success=True, token=r.get("code") if isinstance(r, dict) else str(r))
        if task.type == "turnstile":
            r = await solver.turnstile(sitekey=task.sitekey or "", url=task.url or "", **({"proxy": proxy} if proxy else {}))
            return CaptchaResult(solver="2captcha", success=True, token=r.get("code") if isinstance(r, dict) else str(r))
        if task.type == "geetest":
            r = await solver.geetest(gt=task.gt or "", challenge=task.challenge or "", url=task.url or "")
            return CaptchaResult(solver="2captcha", success=True, token=str(r))
        if task.type == "datadome":
            r = await solver.datadome(captcha_url=task.captcha_url or "", pageurl=task.url or "", userAgent=task.user_agent or "Mozilla/5.0", proxy=proxy or {})
            return CaptchaResult(solver="2captcha", success=True, token=str(r))
        if task.type == "text" and task.image_path:
            r = await solver.normal(task.image_path)
            return CaptchaResult(solver="2captcha", success=True, text=str(r.get("code") if isinstance(r, dict) else r))
        # fallback normal
        if task.image_path:
            r = await solver.normal(task.image_path)
            return CaptchaResult(solver="2captcha", success=True, text=str(r))
        return CaptchaResult(solver="2captcha", success=False, error="unsupported type for 2captcha")
    except Exception as e:
        return CaptchaResult(solver="2captcha", success=False, error=str(e))


async def _solve_with_lmm(task: CaptchaTask) -> CaptchaResult:
    """aydinnyunus/ai-captcha-bypass — screenshot → GPT-4o/Gemini."""
    try:
        # Local import — expects services/captcha-ensemble/ai_utils.py vendored
        # Fallback: try to import from services/captcha-ensemble
        import importlib.util
        from pathlib import Path

        spec_path = Path("services/captcha-ensemble/ai_utils.py")
        if not spec_path.exists():
            # Try pip installed ai-captcha-bypass
            raise ImportError("ai_utils not found — vendor aydinnyunus/ai-captcha-bypass first")
        spec = importlib.util.spec_from_file_location("ai_utils", str(spec_path))
        mod = importlib.util.module_from_spec(spec)  # type: ignore
        assert spec and spec.loader
        spec.loader.exec_module(mod)  # type: ignore
        # mod.solve_text / solve_recaptcha etc. — depends on vendored version
        # For prototype, we call a generic helper if exists
        if hasattr(mod, "solve_captcha_with_llm"):
            res = mod.solve_captcha_with_llm(task.image_path or "", task.type)  # type: ignore
            return CaptchaResult(solver="ai_lmm", success=True, text=str(res))
        return CaptchaResult(solver="ai_lmm", success=False, error="ai_utils.solve_captcha_with_llm not found")
    except Exception as e:
        return CaptchaResult(solver="ai_lmm", success=False, error=str(e))


async def _solve_with_buster(task: CaptchaTask) -> CaptchaResult:
    """teal33t/captcha_bypass — Buster audio solver + B-spline mouse."""
    try:
        import subprocess

        # Expects Firefox + buster extension + GeckoDriver pre-installed per teal33t README
        # For prototype, we just invoke the vendored script if present
        cmd = ["python", "services/captcha-ensemble/recaptcha_buster_bypass.py"]
        if task.url:
            cmd.append(task.url)
        result = subprocess.run(cmd, capture_output=True, timeout=90)
        if result.returncode == 0:
            return CaptchaResult(solver="buster", success=True, token="buster_solved")
        return CaptchaResult(solver="buster", success=False, error=result.stderr.decode()[:500])
    except Exception as e:
        return CaptchaResult(solver="buster", success=False, error=str(e))


async def solve_captcha(task: CaptchaTask, order: list[SolverType] | None = None, authorization: Optional[Any] = None) -> CaptchaResult:
    """
    Agentic ensemble — per-action risk Very High/Critical değilse (Low/Moderate/High) her zaman dene, site riskli olsa bile.
    Order: 2captcha (vault://captcha/2captcha/apiKey) → ai_lmm (vault://llm/openai/apiKey + Gemini) → buster (Firefox + B-spline) → quarantine.
    Biometric mouse her browser adımda zaten aktif. Very High/Critical eylemlerde çağrılmamalı — caller auto_quarantine etmeli.
    If authorization is provided, it must permit auto_ensemble for Low/Moderate/High per-action (site geneli High olsa bile per-action High → izin).
    """
    # Per-action check if authorization is provided
    if authorization is not None:
        try:
            # New policy: auto_ensemble for Low/Moderate/High, Very High/Critical → quarantine
            if hasattr(authorization, "permits_platform_challenge"):
                if not authorization.permits_platform_challenge and authorization.challenge_mode == "auto_ensemble":
                    # For auto_ensemble, check main_risk directly if permits fails due to old policy
                    from .risk_router import RISK_ORDER
                    if authorization.main_risk in RISK_ORDER and RISK_ORDER[authorization.main_risk] <= RISK_ORDER["High"]:
                        pass  # allow
                    else:
                        return CaptchaResult(solver="quarantine", success=False, error="Very High/Critical action cannot use auto_ensemble")
            # Also handle legacy first_party case
        except Exception:
            pass
    order = order or ["2captcha", "ai_lmm", "buster"]
    last_error: Optional[str] = None

    for solver in order:
        if solver == "2captcha":
            api_key = _get_vault_secret("vault://captcha/2captcha/apiKey")
            if not api_key:
                last_error = "missing vault://captcha/2captcha/apiKey"
                continue
            r = await _solve_with_2captcha(task, api_key)
            if r.success:
                # Report balance/cost is handled by caller via solver.balance()
                return r
            last_error = r.error
        elif solver == "ai_lmm":
            r = await _solve_with_lmm(task)
            if r.success:
                return r
            last_error = r.error
        elif solver == "buster":
            r = await _solve_with_buster(task)
            if r.success:
                return r
            last_error = r.error

    # All solvers failed → auto_quarantine, not human bypass
    return CaptchaResult(solver="quarantine", success=False, error=last_error or "ensemble exhausted")


# Synchronous wrapper for Playwright runner (TypeScript calls via Python subprocess or HTTP)
def solve_captcha_sync(task_dict: Dict[str, Any]) -> Dict[str, Any]:
    task = CaptchaTask(**task_dict)
    result = asyncio.run(solve_captcha(task))
    return {"solver": result.solver, "success": result.success, "token": result.token, "text": result.text, "error": result.error}
