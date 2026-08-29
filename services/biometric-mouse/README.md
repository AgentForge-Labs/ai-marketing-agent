# Biometric Mouse Service — `wassim-sayah/biometric-mouse` — HER ZAMAN

Bu klasör `https://github.com/wassim-sayah/biometric-mouse` reposunun **agentic entegrasyon katmanıdır — HER ZAMAN her browser eylemde kullanılır** (Low/Moderate/High per-action, site riskli grupta olsa bile Very High/Critical değilse). Orijinal `ai_mouse/` kodu değiştirilmeden kopyalanır ve TypeScript runner tarafından `playwright_integration` üzerinden çağrılır.

**Güncel Politika:** `Siteler ve riskler` dokümanı per-action risk — biometric mouse her `browser_auto`/`auto_with_verification` eylemde her zaman (fallback Playwright B-spline). Site geneli High olsa bile per-action High → her zaman.

## Kaynak
- Orijinal repo: https://github.com/wassim-sayah/biometric-mouse (MIT, 3 yıldız)
- Lisans: MIT — `ai_mouse/` klasörü orijinal lisansıyla korunur
- Amaç: Davranışsal anti-bot (Akamai, Cloudflare, DataDome) atlatma — sentetik Bezier yerine **gerçek el klonu**

## Kurulum (bir kez, insan)

```bash
# 1) Kodu kopyala (bu repo zaten docs/03'e göre services altına alınır)
git clone https://github.com/wassim-sayah/biometric-mouse temp && cp -r temp/ai_mouse services/biometric-mouse/ai_mouse

# 2) Kayıt
pip install -r services/biometric-mouse/requirements.txt
playwright install chromium
python services/biometric-mouse/scripts/record_mouse.py
# mouse_dojo/index.html aç, hedeflere doğal tıkla, ESC ile bitir

# 3) Eğitim
python services/biometric-mouse/scripts/train_mouse_model.py
# → profile/mouse_profile.json (FFT: jitter amplitude/frequency, velocity shape, overshoot rate/ratio, click hold, inter-event delay; bucket: short 0-100px / medium 100-400px / long 400px+)

# 4) Doğrulama
python services/biometric-mouse/scripts/visualize.py
# → docs/sample_report.png 3×3 grid: grey=gerçek, colored=AI — lens şekli ve hız tepesi örtüşmeli
```

Çıktı `profile/mouse_profile.json` → `vault://mouse/profile/mouse_profile.json` olarak Vault'a konur (asla repoya yazılmaz). Her site/hesap aynı profil, 30dk %8 varyans rotasyonu.

## Runner Entegrasyonu (TypeScript)

`docs/03-automation-architecture.md` ve `schemas/site-adapter.schema.json:biometricMouse` ile zorunlu:

```ts
import { PlaywrightHumanMouse } from "./services/biometric-mouse/ai_mouse/playwright_integration";
// Python tarafı: PlaywrightHumanMouse(page, profile_path="vault://mouse/profile/mouse_profile.json")
await mouse.click_element(page.locator('button.submit')); // jitter + velocity early peak + overshoot + hold
await mouse.move_to(800, 300);
```

`site-adapter.json`:
```json
"biometricMouse": { "enabled": true, "profileRef": "vault://mouse/profile/mouse_profile.json", "rotationMinutes": 30, "variancePercent": 8 }
```

`rotationMinutes` her 30dk'da matematiksel varyans — yorgunluk/postür simülasyonu.

## Güvenlik Notu
Tek başına yeterli değil. **MultiLogin statik fingerprint + residential proxy + gerçekçi header + cookie** ile birlikte etkili. Farklı mouse/DPI'da yeniden kayıt gerekir. `ai_mouse/` dışındaki `scripts/` ve `mouse_dojo/` lokal kalır.
