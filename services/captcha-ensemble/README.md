# Agentic CAPTCHA Ensemble — `2captcha` + `ai-captcha-bypass` + `buster` — per-action High dahil

Bu klasör 3 repo + 1 servis için **tek ensemble katmanıdır — per-action Low/Moderate/High (High riskli grupta olsa bile, Very High/Critical değilse site riskli olsa bile) CAPTCHA çıkarsa her zaman denenir**. Sıra: `2captcha` → `ai_lmm` → `buster` → `auto_quarantine`.

**Güncel Politika:** Risk site çapında değil eylem bazlı. Eylem `Very High`/`Critical` değilse, vault:// ile `auto_ensemble` her zaman kullanılabilir (site High olsa bile per-action High → ensemble). Biometric mouse her zaman. Very High/Critical → doğrudan quarantine, ensemble yok.

## Kaynaklar
- `https://github.com/2captcha/2captcha-python` (794★) — 30+ tip, API `twocaptcha.TwoCaptcha` / `AsyncTwoCaptcha`, sync/async, proxy, balance/report
- `https://github.com/aydinnyunus/ai-captcha-bypass` (1.2k★) — GPT-4o/Gemini multimodal, Selenium, 5 tip (text/complicated_text/recaptcha_v2/puzzle/audio), `ai_utils.py`/`puzzle_solver.py`
- `https://github.com/teal33t/captcha_bypass` (330★) — Selenium + GeckoDriver + `buster_captcha_solver_for_humans-0.7.2` + B-spline

## Vault Mapping (C:\Users\ahmet\Downloads\DIGER\sunucular → vault://)

| Dosya | vault:// ref | Kullanım |
|---|---|---|
| `openai_platform.txt` | `vault://llm/openai/apiKey` | `ai-captcha-bypass` GPT-4o (`gpt-4o`) |
| `2captcha` / `capsolver` anahtar dosyası (varsa) | `vault://captcha/2captcha/apiKey` | `TwoCaptcha(apiKey)` |
| `proxy` / `hetzner.txt` / `cloudflare.txt` | `vault://proxy/residential/uri` → `login:password@IP:PORT` | DataDome/Turnstile için zorunlu `proxy={'type':'HTTPS','uri':...}` |
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
# CAPTCHA_2CAPTCHA_KEY=...
```

## Kullanım (ensemble)

```python
# services/captcha-ensemble/ensemble.py
from twocaptcha import AsyncTwoCaptcha
from ai_utils import solve_with_gpt4o  # ai-captcha-bypass
import subprocess

async def solve_agentic(captcha_type, sitekey, url, image_path=None, proxy=None):
    # 1) 2captcha (99%, pay-per-1k, en ucuz)
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

    # 2) LMM fallback (novel puzzle)
    try:
        # screenshot → GPT-4o/Gemini vision prompt (ai-captcha-bypass/ai_utils.py)
        r = solve_with_gpt4o(image_path, provider="openai", model="gpt-4o")
        return {"solver": "ai_lmm", "text": r}
    except Exception: pass

    # 3) Buster (ücretsiz, reCAPTCHA v2 audio)
    try:
        subprocess.run(["python", "services/buster/recaptcha_buster_bypass.py"], check=True)
        return {"solver": "buster"}
    except Exception: pass

    # 4) human Telegram (rate-limited)
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
  "solvers": ["2captcha","ai_lmm","buster"],
  "twoCaptcha": {"apiKeyRef":"vault://captcha/2captcha/apiKey","server":"2captcha.com"},
  "aiLmm": {"provider":"openai","model":"gpt-4o","apiKeyRef":"vault://llm/openai/apiKey"},
  "buster": {"enabled":true,"useBsplineMouse":true},
  "proxyRef": "vault://proxy/residential/uri",
  "notifyChannelRef": "telegram://marketing-agent/alerts",
  "maxHumanSolvesPerDay": 5
}
```

`security`/`stealth` testleri: her captcha tipi için `benchmark.py` benzeri success rate ölçümü.

## Maliyet Notu (docs/03'e göre)
- 2Captcha: pay-per-1k, en ucuz ve en yüksek başarı → primary.
- LMM: token maliyeti yüksek, novel puzzle'da kurtarıcı.
- Buster: ücretsiz ama success düşük, son fallback.

