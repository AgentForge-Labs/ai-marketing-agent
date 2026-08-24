# Otomasyon mimarisi

## Teknoloji kararı

Tarayıcı adapter'ları için Playwright önerilir. Temel nedenler:

- kullanıcıya görünen `role`, `label`, `placeholder` tabanlı locator'lar
- locator seviyesinde auto-wait ve retry
- codegen ile keşif başlangıcı
- trace, screenshot ve video ile hata analizi
- bağımsız BrowserContext'ler
- kontrollü `storageState` kullanımı

Uzun CSS zincirleri ve absolute XPath kullanılmamalıdır. Locator önceliği:

1. `role + accessible name`
2. `label`
3. `placeholder`
4. stabil `name`/`id`
5. kısa ve bağlama alınmış CSS fallback

Kaynaklar:

- https://playwright.dev/docs/locators
- https://playwright.dev/docs/codegen
- https://playwright.dev/docs/auth

## Bileşenler

### Channel importer

Excel'i yalnızca veri olarak okur ve normalize edilmiş `site-registry` üretir. Excel hücrelerindeki metinler çalıştırılmaz.

### Policy registry

Her site için:

- resmî politika URL'si
- son doğrulama tarihi
- API/browser/manual çalışma modu
- izinli ve yasaklı eylemler
- submit/comment/DM için onay seviyesi
- siteye özel oran ve concurrency sınırı

tutar.

### Human recorder

Yetkili kişi siteyi bir kez gezer; login/register/listing/post/comment/DM akışlarını işaretler. Recorder şu artefaktları üretir:

```text
sites/<site-id>/<flow>/<version>/
  adapter.json
  form.json
  before.png
  filled-redacted.png
  success.png
  sanitized.html
  metadata.json
```

Ekran görüntüsü tek başına otomasyon kaynağı değildir. `form.json`, erişilebilir isimler, alan tipi, zorunluluk, seçenekler ve validation bilgilerini taşır.

### Adapter compiler

JSON DSL'i sınırlı Playwright eylemlerine çevirir:

- `goto`
- `fill`
- `select`
- `check`
- `upload`
- `click`
- `waitForURL`
- `assertVisible`
- `captureScreenshot`

JSON içinde serbest JavaScript veya `eval` çalıştırılmaz.

### Runner

Runner akışı:

```text
preflight
  → policy check
  → auth state load
  → entry URL allowlist check
  → form fingerprint check
  → locator uniqueness check
  → dry-run fill
  → redacted screenshot
  → approval boundary
  → submit
  → success/failure assertion
  → audit + idempotency record
```

Her site/hesap için concurrency varsayılan olarak `1` olmalıdır. Rastgele insan taklidi gecikmeleri yerine açık kuyruk ve politika tabanlı hız sınırı kullanılmalıdır.

### Approval queue

Eylem modları:

- `manual_only`: Runner platformda eylem gerçekleştirmez.
- `draft_only`: İçerik/form taslağı üretir, submit etmez.
- `browser_with_submit_approval`: Formu doldurur, submit öncesi durur.
- `api_with_approval`: API isteği insan onayı sonrası gönderilir.
- `api_auto`: Yalnızca açıkça izinli, düşük riskli ve idempotent işlemler.

Comment, reply, review, DM, PR pitch ve marketplace yayınları varsayılan olarak otomatik modda olamaz.

## Form fingerprint ve drift

Fingerprint şu normalize edilmiş bilgilerin hash'idir:

- form action/method
- alanların name/type/accessible label bilgisi
- zorunlu alanlar
- select seçeneklerinin temel kimlikleri
- submit düğmesinin role/name bilgisi

Hash değişirse runner submit etmez. Adapter `needs_remap` olur ve recorder kuyruğuna geri döner.

## Başarı doğrulaması ve idempotency

Başarı tek bir toast mesajına bağlanmamalıdır. İki veya daha fazla sinyal tercih edilir:

- beklenen URL deseni
- başarı heading/alert metni
- listing/post URL'sinin oluşması
- resmî API response ID'si
- e-posta doğrulama durumunun görünmesi

İşlem sonucu belirsizse otomatik retry yapılmaz. Önce mevcut listing/post aranır. İdempotency anahtarı örneği:

```text
<product-id>:<site-id>:<operation>:<content-version>
```

## Oturum ve secret yönetimi

- Şifreler adapter veya log içine yazılmaz.
- `storageState` cookie ve token içerebildiği için şifreli secret store'da tutulur.
- Site/hesap başına ayrı state kullanılır.
- State süresi dolduğunda kullanıcı yeniden manuel login olur.
- 2FA, CAPTCHA ve e-posta doğrulaması insan tarafından tamamlanır.
- Screenshot ve HTML kaydından password, token, hidden CSRF value, cookie, e-posta ve kişisel veriler maskelenir.
- Trace dosyaları kısa süreli tutulur ve hassas artefakt kabul edilir.

## Comment ve DM güvenlik sınırları

DM job'ı şu alanlar olmadan çalışmaz:

- `recipientId`
- `reason`
- `consentSource`
- `recipientOptInAt`
- `approvedBy`
- `approvedAt`
- `contentVersion`

Comment/reply; anahtar kelime taramasıyla toplu kullanıcı hedefleyemez. İçerik ilgili thread'e özel olmalı ve insan onayı taşımalıdır.

## Adapter family yaklaşımı

1.000 ayrı monolitik script yerine ortak family'ler kullanılır:

- `generic-directory`
- `ai-directory`
- `review-vendor-profile`
- `discourse-community`
- `content-publisher`
- `integration-marketplace`
- `cloud-marketplace`
- `manual-social`
- `manual-pr-outreach`

Family ortak alan ve doğrulamaları sağlar; site adapter'ı sadece URL, locator, politika ve siteye özgü validation farklarını içerir.

