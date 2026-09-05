# Agentic CAPTCHA Ensemble — `capsolver` + `2captcha` + `ai-captcha-bypass` + `buster` — per-action High dahil

Bu klasör 1 servis + 3 repo için **tek ensemble katmanıdır — per-action Low/Moderate/High (High riskli grupta olsa bile, Very High/Critical değilse site riskli olsa bile) CAPTCHA çıkarsa her zaman denenir**. Sıra: `capsolver` → `2captcha` → `ai_lmm` → `buster` → `auto_quarantine`.

**Neden CapSolver primary (2026 karşılaştırması):** reCAPTCHA v2/v3 ve Turnstile'da **$0.80/1k, 2-8sn AI** — en iyi fiyat/performans. 2Captcha $2.99/1k, 15-30sn ama en geniş kapsama + Turnstile %97 insan yedeği → coverage fallback. CapMonster Cloud reCAPTCHA v2'de $0.60 ile daha ucuz ama Turnstile'da $1.30 (CapSolver'ın %60 pahalı), hCaptcha/DataDome yok → ensemble dışında tutuldu.

**Güncel Politika:** Risk site çapında değil eylem bazlı. Eylem `Very High`/`Critical` değilse, vault:// ile `auto_ensemble` her zaman kullanılabilir (site High olsa bile per-action High → ensemble). Biometric mouse her zaman. Very High/Critical → doğrudan quarantine, ensemble yok.

## Kaynaklar
- **CapSolver REST API** (`https://api.capsolver.com`, `createTask`/`getTaskResult`) — primary, 30+ tip, AI 2-8sn, $0.80/1k recaptcha+turnstile. Kod: `src/ai_marketing_agent/captcha_ensemble.py:_solve_with_capsolver` (ek paket yok, `requests` yeterli)
- `https://github.com/2captcha/2captcha-python` (794★) — 30+ tip, API `twocaptcha.TwoCaptcha` / `AsyncTwoCaptcha`, sync/async, proxy, balance/report → coverage fallback
- `https://github.com/aydinnyunus/ai-captcha-bypass` (1.2k★) — GPT-4o/Gemini multimodal, Selenium, 5 tip (text/complicated_text/recaptcha_v2/puzzle/audio), `ai_utils.py`/`puzzle_solver.py`
- `https://github.com/teal33t/captcha_bypass` (330★) — Selenium + GeckoDriver + `buster_captcha_solver_for_humans-0.7.2` + B-spline

## Vault Mapping (C:\Users\ahmet\Downloads\DIGER\sunucular → vault://)

| Dosya | vault:// ref | Kullanım |
|---|---|---|
| `openai_platform.txt` | `vault://llm/openai/apiKey` | `ai-captcha-bypass` GPT-4o (`gpt-4o`) |
| `capsolver*.txt` | `vault://captcha/capsolver/apiKey` | CapSolver `createTask` (`CAPSOLVER_API_KEY`) — primary |
| `2captcha*.txt` | `vault://captcha/2captcha/apiKey` | `TwoCaptcha(apiKey)` — coverage fallback |
| `proxy` / `hetzner.txt` / `cloudflare.txt` | `vault://proxy/residential/uri` → `login:password@IP:PORT` | DataDome/Turnstile için zorunlu `proxy={'type':'HTTPS','uri':...}` (2captcha) / `"proxy"` (CapSolver) |
| `telegram` (varsa) | `vault://notify/telegram` | `notifyChannelRef` son çare |

Ham anahtar asla repoya yazılmaz; `SECURITY.md` gereği Vault/credential store'da.

## Kurulum

```bash
pip install 2captcha-python
pip install -r services/captcha-ensemble/requirements.txt  # openai, google-generativeai, selenium, pillow

# .env (örnek)
cp services/captcha-ensemble/.env.example .env
# OPENAI_API_KEY=sk-...
# GOOGLE_API_KEY=...
# CAPSOLVER_API_KEY=...
# CAPTCHA_2CAPTCHA_KEY=...
```

## Kullanım (ensemble)

```python
# services/captcha-ensemble/ensemble.py
from twocaptcha import AsyncTwoCaptcha
from ai_utils import solve_with_gpt4o  # ai-captcha-bypass
import subprocess

async def solve_agentic(captcha_type, sitekey, url, image_path=None, proxy=None):
    # 1) CapSolver primary ($0.80/1k, 2-8sn — en ucuz/hızlı)
    try:
        r = capsolver_createTask(sitekey, url, proxy)  # bkz. src/ai_marketing_agent/captcha_ensemble.py:_solve_with_capsolver
        return {"solver": "capsolver", "token": r}
    except Exception: pass

    # 2) 2captcha (insan yedeği, en geniş kapsama)
    try:
        solver = AsyncTwoCaptcha('vault://captcha/2captcha/apiKey', defaultTimeout=120, recaptchaTimeout=600, pollingInterval=10)
        if captcha_type == "recaptcha_v2":
            r = await solver.recaptcha(sitekey=sitekey, url=url, **({} if not proxy else {"proxy": proxy, "userAgent": "Mozilla/5.0..."}))
            return {"solver": "2captcha", "token": r['code']}
        if captcha_type == "turnstile":
            r = await solver.turnstile(sitekey=sitekey, url=url, **({"proxy": proxy} if proxy else {}))
            return r
        # geetest, datadome vb. — 2captcha-python README'deki 30+ method
    except Exception: pass

    # 3) LMM fallback (novel puzzle)
    try:
        # screenshot → GPT-4o/Gemini vision prompt (ai-captcha-bypass/ai_utils.py)
        r = solve_with_gpt4o(image_path, provider="openai", model="gpt-4o")
        return {"solver": "ai_lmm", "text": r}
    except Exception: pass

    # 4) Buster (ücretsiz, reCAPTCHA v2 audio)
    try:
        subprocess.run(["python", "services/buster/recaptcha_buster_bypass.py"], check=True)
        return {"solver": "buster"}
    except Exception: pass

    # 5) human Telegram (rate-limited)
    raise Exception("captcha_ensemble_failed -> notifyChannelRef")
```

**Önemli:**
- `callback` tanımlıysa `TwoCaptcha` sadece `captcha ID` döner, polling yok — `get_result` ile manuel alınır.
- `balance()` ve `report(id, True/False)` her solve sonrası çağrılmalı (maliyet takibi).
- Başarı `successful_solves/*.gif` gibi kanıtla audit'e yazılır; token/sonuç log'a yazılmaz, sadece `type/duration/result=success`.

## Site Adapter Şeması

`schemas/site-adapter.schema.json:captcha` (`auto_ensemble` default):

```json
"captcha": {
  "policy": "auto_ensemble",
  "strategy": "auto_ensemble",
  "solvers": ["capsolver","2captcha","ai_lmm","buster"],
  "capSolver": {"apiKeyRef":"vault://captcha/capsolver/apiKey","server":"https://api.capsolver.com"},
  "twoCaptcha": {"apiKeyRef":"vault://captcha/2captcha/apiKey","server":"2captcha.com"},
  "aiLmm": {"provider":"openai","model":"gpt-4o","apiKeyRef":"vault://llm/openai/apiKey"},
  "buster": {"enabled":true,"useBsplineMouse":true},
  "proxyRef": "vault://proxy/residential/uri",
  "notifyChannelRef": "telegram://marketing-agent/alerts",
  "maxHumanSolvesPerDay": 5
}
```

`security`/`stealth` testleri: her captcha tipi için `benchmark.py` benzeri success rate ölçümü.

## Maliyet Notu (2026 karşılaştırması)

| Tip (/1k) | CapSolver (primary) | 2Captcha (fallback) | CapMonster (dahil değil) |
|---|---|---|---|
| reCAPTCHA v2 | **$0.80** | $2.99 | $0.60 |
| Turnstile | **$0.80** | $1.45 | $1.30 |
| hCaptcha | $0.80 | $2.00 | — |
| Hız | 2-8sn AI | 15-30sn | <2sn iddia |

- CapSolver: primary — en iyi fiyat/performans, hacim indirimi $100+ harcamada.
- 2Captcha: coverage fallback — Turnstile %97, insan yedeği.
- CapMonster dahil değil: recaptcha v2'de $0.60 ile ucuz ama Turnstile $1.30 + hCaptcha/DataDome yok.
- LMM: token maliyeti yüksek, novel puzzle'da kurtarıcı.
- Buster: ücretsiz ama success düşük, son fallback.

