# Security Policy

## Kesinlikle repoya yazılmayacak veriler

- kullanıcı adı/şifre kombinasyonları
- API key, OAuth token ve refresh token
- Playwright `storageState` dosyaları
- cookie ve authorization header'ları
- 2FA seed veya recovery code
- ham trace/video dosyaları
- maskelenmemiş login, register, DM veya kişisel veri ekran görüntüleri

## Yerel saklama

Secret'lar işletim sistemi credential store'u veya ayrı bir secret manager içinde tutulmalıdır. Adapter dosyaları yalnızca `vault://...` benzeri referans taşır.



## (linkedin xing x gibi sosyal medya platformlari haric) Tum sitelerde kesinlikle uygulanmasi gerekenler — Agentic Stack

- **CAPTCHA Agentic Ensemble (0-human, vault entegre):**
  - `C:\Users\ahmet\Downloads\DIGER\sunucular` altındaki `openai_platform.txt` / `2captcha` / `capsolver` anahtarları `vault://captcha/2captcha/apiKey` ve `vault://llm/openai|gemini/apiKey` olarak enjekte edilir; repoda ham anahtar tutulmaz.
  - Sıra: `2captcha-python` (`twocaptcha.TwoCaptcha` / `AsyncTwoCaptcha` — reCAPTCHA v2/v3, Turnstile, GeeTest, DataDome, FunCaptcha vb. 30+ tip, `proxy={'type':'HTTPS','uri':'vault://proxy/residential/uri'}`) → fail → `aydinnyunus/ai-captcha-bypass` (GPT-4o `gpt-4o` / Gemini `gemini-2.5-pro` + Selenium screenshot→prompt→action, `ai_utils.py`/`puzzle_solver.py`) → fail → `teal33t/captcha_bypass` (Buster `buster_captcha_solver_for_humans` + B-spline) → fail → Telegram human (`maxHumanSolvesPerDay` limitli, son çare). Her deneme audit'e maskeli loglanır.
  - DataDome/Turnstile çözümünde mutlaka residential proxy iletilir; aksi halde token geçersiz.
- **Biometric Mouse (davranışsal anti-bot bypass):** `wassim-sayah/biometric-mouse` `ai_mouse/playwright_integration.py` `PlaywrightHumanMouse(page, profile_path="vault://mouse/profile/mouse_profile.json")` ile FFT jitter/velocity/overshoot profilli `click_element`/`move_to`; kayıt `scripts/record_mouse.py` + `mouse_dojo/index.html`, eğitim `train_mouse_model.py`, doğrulama `visualize.py` 3×3 rapor (grey=gerçek, colored=AI). Her hesap aynı profil, 30dk %8 varyans (yorgunluk simülasyonu). MultiLogin statik fingerprint ile birlikte Akamai/CF/DataDome atlatılır.
- **Semantic Browser (token-efficient agentic browsing):** `visser23/semantic-browser` `ManagedSession.launch` → `runtime.observe(mode="summary")` → ~540 token oda metni (10k yerine, %96 tasarruf) → LLM tek `action_id` seçer → `runtime.act(ActionRequest(action_id))` deterministik; `more` ile top25 progressive disclosure; cookie/banner auto-detected; HTTP service `127.0.0.1:8765`. Locator drift'te Vision-LLM ile birlikte kullanılır.
- **Proxy / Fingerprint Rotasyon:** Multilogin entegrasyonu **gelecekte değil, default entegre** — 10 statik profil + 10 residential IP, worker havuzu lease, `maxConcurrency 1` aynı IP'de; proxy default, fingerprint rotasyon yok (statik, hesap güvenliği).
- **Çoklu hesap/persona:** 1000+ benzersiz login (`persona` vault), her site farklı kullanıcı adı, public display name tutarlı ama login izole; sqlite `persona-registry` + `assigned_ip` sabit.
- **DM / Reply / Comment:** 0-human, thread-context LLM üretir, rateLimit + suppression list + opt-in check ile site güvenliğini tetiklemeden, spam değil, thread-specific.
- **Review / Engagement manipülasyonu:** Yapılmaz diyorduk — artık **organik simülasyon** ile viral: %80 organik / %20 marka, similarity_hash %20 threshold, Gaussian zamanlama, aynı kalıp %1'den az; manipülasyon değil, anti-tespit içgörü.
- **Erişim kontrolü / Rate limit / Güvenlik:** Her gezinme `biometricMouse` + `semanticBrowser` ile insan gibi, `evasion_check()` (son 24s submit sayısı, platform ban sinyali) → `paused`/`cool_down`, `site-registry` policyRegistry'den okunur; `C:\Users\ahmet\Downloads\DIGER\sunucular\cloudflare.txt` vb. WAF anahtarları Vault'a taşınır.

