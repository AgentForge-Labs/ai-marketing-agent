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

Ekran görüntüsü tek başına otomasyon kaynağı değildir. `form.json`, erişilebilir isimler, alan tipi, zorunluluk, seçenekler ve validation bilgilerini taşır; şeması [`schemas/form.schema.json`](../schemas/form.schema.json) dosyasındaki sözleşmedir. Recorder çıktısı bu şemaya uymayan hiçbir adapter devreye alınmaz.

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

### E-posta doğrulama akışı

Dizinlerin çoğu submission sonrası e-posta onayı ister. Bu adım tamamlanmadan işlem `published` sayılmaz; `submitted` durumunda bekler. Adapter'da flows altında `emailVerification` akışı tanımlanır:

```json
"emailVerification": {
  "kind": "email",
  "execution": "manual_only",
  "mailboxRef": "vault://sites/<site-id>/<persona>/inbox"
}
```

- Runner gelen kutusunu okumaz; görev kuyruğunda insana hatırlatma üretir.
- Doğrulama bağlantısına tıklama her zaman insan tarafından yapılır.
- Başarı, listing URL'sinin görünmesiyle iki sinyal kuralına göre doğrulanır ve audit kaydına yazılır.
- E-posta doğrulaması tamamlanmamış listing'ler raporlamada ayrı tutulur.

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

## Audit ve idempotency deposu

Audit, idempotency ve politika kayıtları tek dosyalık SQLite veritabanında tutulur. Dosya repoya girmez; runner ile aynı makinede veya yedeklenen bir veri klasöründe durur.

Kurallar:

- Tablolar append-only'dir. `UPDATE` ve `DELETE` yapılmaz; düzeltme yeni bir event satırıdır.
- Şifre, token, cookie veya hassas form değeri yazılmaz.
- Runner her submit öncesi idempotency anahtarını `PRIMARY KEY` üzerinden kontrol eder; aynı anahtar için ikinci submit denemesi fail-closed durur.
- WAL modu açık olur; düzenli olarak okunabilir dışa aktarım (CSV/JSONL) üretilir.

Minimum tablo seti:

```sql
CREATE TABLE submissions (
  idempotency_key  TEXT PRIMARY KEY,   -- <product-id>:<site-id>:<operation>:<content-version>
  product_id       TEXT NOT NULL,
  site_id          TEXT NOT NULL,
  operation        TEXT NOT NULL,      -- register | login | submitListing | post | comment | dm | emailVerification
  content_version  TEXT NOT NULL,
  status           TEXT NOT NULL CHECK (status IN
                     ('dry_run','awaiting_approval','submitted','email_verification_pending',
                      'published','ambiguous','failed','needs_remap')),
  listing_url      TEXT,
  approved_by      TEXT,
  approved_at      TEXT,
  created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE audit_log (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  occurred_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  idempotency_key  TEXT REFERENCES submissions(idempotency_key),
  event            TEXT NOT NULL,      -- preflight | policy_check | dry_run | approval | submit | success_assertion | drift_detected
  detail_json      TEXT NOT NULL       -- maskelenmiş yapısal detay
);

CREATE TABLE policy_checks (
  site_id          TEXT NOT NULL,
  checked_at       TEXT NOT NULL,
  source_url       TEXT NOT NULL,
  execution        TEXT NOT NULL,
  result           TEXT NOT NULL,      -- pass | stale | violation
  PRIMARY KEY (site_id, checked_at)
);
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

