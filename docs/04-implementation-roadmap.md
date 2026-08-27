# Uygulama yol haritası

## Faz 0 — Ürün ve politika hazırlığı

- Ürün profil şemasını doldur.
- Logo, screenshot ve onaylı metin varyantlarını hazırla.
- Suppression/opt-out veri modelini tanımla.
- Her pilot site için güncel ToS ve otomasyon iznini kontrol et.


## Faz 1 — Recorder ve dry-run

- Playwright codegen'i keşif başlangıcı olarak kullan.
- Semantik locator'ları recorder formatına dönüştür.
- Sanitized form şemasını (`schemas/form.schema.json` sözleşmesine uygun `form.json`) ve fingerprint'i üret.
- `before` ve `filled-redacted` screenshot'larını üret.
- Submit varsayılan olarak kapalı olsun.

Çıkış kriteri: Pilot adapter'lar üç ardışık dry-run'da doğru formu ve tekil locator'ları bulur.

## Faz 2 — İlk 10 site

- 5 yüksek uyumlu dizin
- 2 içerik platformu
- 3 manual/draft-only sosyal veya topluluk kanalı

Çıkış kriterleri:

- kopya submission yok
- yanlış hesap/persona kullanımı yok
- onaysız submit/comment/DM yok
- her başarı için listing/post URL'si veya güçlü başarı kanıtı var
- form değişikliğinde fail-closed davranışı var
- secret veya kişisel veri log/screenshot içinde görünmüyor

## Faz 3 — Adapter family'leri

- Tekrarlayan form alanlarını family tabanına taşı.
- Site-specific override yapısını uygula.
- Canary site ile family sürümünü doğrula.
- Aynı anda tüm siteleri çalıştırma; family başına kademeli rollout kullan.

Çıkış kriteri: Bir family değişikliği başka site adapter'larında sessiz davranış değişikliği yaratmaz.

## Faz 4 — API entegrasyonları

- Resmî API/OAuth desteği bulunan platformları browser adapter'ından ayır.
- API scope'larını minimum yetkiyle tanımla.
- Rate limit, consent ve opt-out kurallarını merkezi policy registry'den uygula.
- API ve browser audit formatlarını ortaklaştır.

## Faz 5 — Operasyon ve bakım

- Adapter health check
- policy review tarihi alarmı
- expiring auth state alarmı
- başarısız/ambiguous submission kuyruğu
- listing güncelleme ve doğrulama takvimi
- UTM ve conversion raporlaması

## Faz 5B — Agentic Browsing & CAPTCHA (mimari entegrasyon)

- `services/biometric-mouse`: `wassim-sayah/biometric-mouse` `ai_mouse/` klasörü projeye `services/biometric-mouse/ai_mouse/` olarak kopyalanır; `scripts/record_mouse.py` + `mouse_dojo/index.html` ile 1 personel gerçek el kaydı alır, `train_mouse_model.py` ile `profile/mouse_profile.json` üretilir, `visualize.py` 3×3 rapor (grey=gerçek, colored=AI) doğrulanır. `vault://mouse/profile/mouse_profile.json` referansı `schemas/site-adapter.schema.json:biometricMouse` ile zorunlu.
- `services/captcha-ensemble`: `2captcha-python` `twocaptcha` paketi `requirements.txt`'ye eklenir; `aydinnyunus/ai-captcha-bypass` `ai_utils.py`/`puzzle_solver.py` `services/captcha-lmm/` altında mikro-servis; `teal33t/captcha_bypass` Buster xpi `services/buster/` altında. `C:\Users\ahmet\Downloads\DIGER\sunucular` içindeki `openai_platform.txt` ve `2captcha` anahtarları `vault://llm/openai/apiKey` ve `vault://captcha/2captcha/apiKey` olarak taşınır.
- `services/semantic-browser`: `visser23/semantic-browser` `pip install semantic-browser[managed]` + `semantic-browser install-browser` + `serve --host 127.0.0.1 --port 8765`. `docs/03` içindeki `semanticBrowser.enabled=true` ile drift repair'de kullanılır.
- Her adapter `captcha` alanı `auto_ensemble` ile test edilir: önce 2captcha, fail → LMM, fail → Buster. Başarısızlık `audit_log.detail_json.captcha` içinde maskeli loglanır (token değil, tip/süre/sonuç).
- E2E kanıt: `examples/site-adapter.example.json` captcha alanı `auto_ensemble` demo, `biometricMouse` ve `semanticBrowser` örnekleri eklendi.

Çıkış kriteri: `turnstile` + `recaptcha_v2` + `datadome` 3 tipte de agentic çözüm `successful_solves/*.gif` benzeri kanıt üretir ve `dead-pool` tetiklenmeden 10 ardışık submit başarılıdır.

## Ölçekleme kuralı

Yeni site sayısı hedef değildir. Aşağıdakiler ölçülmeden P2/P3 long-tail kanallara geçilmez:

- başarılı yayın oranı
- kabul/indexlenme oranı
- referral trafik
- signup/demo dönüşümü
- kanal başına insan zamanı
- politika ve hesap riski
- **agentic captcha başarı oranı (>95% 2captcha, >80% LMM/Buster)** ve **biometric mouse false-positive oranı (<2% Akamai/DataDome)**

