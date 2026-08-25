```markdown
# Otonom Otomasyon Mimarisi — 0 Human-in-the-Loop

## Teknoloji Kararı

Tarayıcı adapter'ları için **Playwright** önerilir. Temel nedenler:

- Kullanıcıya görünen `role`, `label`, `placeholder` tabanlı locator'lar
- Locator seviyesinde auto-wait ve retry
- Vision-LLM destekli otomatik keşif (codegen yerine autonomous discovery)
- Trace, screenshot ve video ile otomatik hata analizi (AI triage)
- Bağımsız BrowserContext'ler (her hesap tam izolasyon)
- Kontrollü `storageState` kullanımı (Vault entegrasyonu)

Uzun CSS zincirleri ve absolute XPath kullanılmamalıdır. Locator önceliği:

1. `role + accessible name`
2. `label`
3. `placeholder`
4. Stabil `name`/`id`
5. Kısa ve bağlama alınmış CSS fallback
6. **Vision-LLM semantik eşleme** (locator drift durumunda otomatik fallback)

Kaynaklar:

- https://playwright.dev/docs/locators
- https://playwright.dev/docs/auth
- https://playwright.dev/docs/test-projects

---

## Runner Stack

| Katman | Seçim | Not |
|---|---|---|
| Dil/runtime | TypeScript + Node.js LTS | Playwright ekosistemiyle aynı dil; adapter tipleri derleme anında doğrulanır |
| Tarayıcı bağlantısı | Playwright `chromium.connectOverCDP` | Harici Chromium tabanlı tarayıcılara CDP üzerinden bağlanılır; vanilla Chromium fallback olarak kalır |
| Profil sağlayıcı | MultiLogin (Local API) | Site/hesap başına tek stabil profil: her login aynı sanal cihazdan gelir. Local API ile profil başlatılır, dönen CDP portuna bağlanılır |
| Paralellik | Worker havuzu (varsayılan 10 slot) + SQLite `jobs` tablosu | Paralellik yataydır: 10 worker = 10 farklı IP/profil eşzamanlı. Aynı IP'de eşzamanlılık 1'dir (`limits.maxConcurrency`) |
| Adapter compiler | Saf fonksiyon (TS) + Vision-LLM repair | Girdiden eylem listesi üretir; drift durumunda otomatik self-healing |
| Doğrulama Servisleri | CapSolver / 2Captcha + TOTP Vault | CAPTCHA ve 2FA tamamen otomatik çözülür |
| E-posta İstemcisi | IMAP/API + Link Extractor | Catch-all inbox otomatik okunur, doğrulama linkleri otomatik tıklanır |

### Paralel Çalışma Modeli

- Worker havuzu aynı anda en fazla N siteyi işler; her worker bir profil/IP üzerinde tek job çalıştırır.
- Job sahipliği `jobs` tablosundaki lease alanlarıyla yönetilir; worker çökerse lease süresi dolunca job yeniden kuyruğa alınır.
- MultiLogin entegrasyonu `BrowserProvider` arayüzünün arkasında durur: `launch()` (vanilla) ve `connectOverCDP(port)` (MultiLogin) aynı arayüzü uygular; flow tanımı hangi sağlayıcının kullanıldığını bilmez.
- **0 Human-in-the-Loop:** Tüm kararlar risk skoru tabanlı autonomous decision engine tarafından verilir.

---

## Bileşenler

### Channel Importer

Excel/CSV/API'yi yalnızca veri olarak okur ve normalize edilmiş `site-registry` üretir. Hücrelerdeki metinler çalıştırılmaz; yalnızca yapılandırılmış şemaya validate edilir.

### Policy Registry (Autonomous Compliance)

Her site için:

- Resmî politika URL'si
- Son doğrulama tarihi (otomatik crawler ile güncellenir)
- API/browser çalışma modu
- İzinli ve yasaklı eylemler
- Submit/comment/DM için otomatik risk skoru
- Siteye özel oran ve concurrency sınırı

Policy değişiklikleri otomatik tespit edilir; violation durumunda kanal otomatik `cool-down` moduna alınır.

### AI Discovery Agent (Human Recorder Yerine)

Autonomous agent siteyi bir kez gezer; login/register/listing/post/comment/DM akışlarını Vision-LLM ile işaretler. Agent şu artefaktları üretir:

```text
sites/<site-id>/<flow>/<version>/
  adapter.json       # JSON DSL
  form.json          # Şema-uyumlu form tanımı
  before.png
  filled-redacted.png
  success.png
  sanitized.html
  metadata.json
  vision-assertions.json  # Otomatik doğrulama noktaları
```

Ekran görüntüsü tek başına otomasyon kaynağı değildir. `form.json`, erişilebilir isimler, alan tipi, zorunluluk, seçenekler ve validation bilgilerini taşır; şeması `schemas/form.schema.json` dosyasındaki sözleşmedir. Şemaya uymayan adapter otomatik olarak `quarantine` kuyruğuna alınır ve self-healing döngüsü başlatılır.

### Adapter Compiler

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
- `solveCaptcha` (otomatik)
- `solve2FA` (TOTP Vault üzerinden)

JSON içinde serbest JavaScript veya `eval` çalıştırılmaz. Drift durumunda Vision-LLM otomatik locator repair yapar.

### Autonomous Runner

Runner akışı (0 human-in-the-loop):

```text
preflight
  → policy check (otomatik compliance crawler)
  → auth state load (Vault'tan credential + storageState)
  → entry URL allowlist check
  → form fingerprint check
  → locator uniqueness check
  → dry-run fill
  → redacted screenshot (otomatik PII masking)
  → risk score evaluation (otomatik karar)
  → submit
  → success/failure assertion (Vision-LLM + multi-signal)
  → audit + idempotency record
  → email verification (otomatik link tıklama)
```

Her site/hesap için concurrency varsayılan olarak `1` olmalıdır. Rastgele insan taklidi gecikmeleri yerine **Gaussian dağılımlı, persona timezone'una göre schedule edilmiş, politika tabanlı hız sınırı** kullanılır.

### Autonomous Decision Engine (Approval Queue Yerine)

Eylem modları risk skoru tabanlı otomatik seçilir:

- `auto_full`: Düşük risk + idempotent + izinli → tam otomatik.
- `auto_with_verification`: Orta risk → otomatik + ek assertion (örn. listing URL doğrulaması).
- `auto_quarantine`: Yüksek risk veya policy drift → otomatik quarantine, yeniden discovery kuyruğuna.
- `blocked`: Yasaklı eylem → loglanır, asla çalıştırılmaz.

Her eylem için risk skoru şu formülle hesaplanır:

```text
risk = policy_violation_weight × site_sensitivity × content_risk × history_failure_rate
```

Skor eşik altında kalırsa eylem otomatik yürütülür; eşik üstündeyse quarantine.

### Otonom E-posta Doğrulama Akışı

Dizinlerin çoğu submission sonrası e-posta onayı ister. Bu adım tamamlanmadan işlem `published` sayılmaz; `email_verification_pending` durumunda bekler. Adapter'da flows altında `emailVerification` akışı tanımlanır:

```json
"emailVerification": {
  "kind": "email",
  "execution": "auto_full",
  "mailboxRef": "vault://sites/<site-id>/<persona>/inbox",
  "timeout": 900
}
```

- Runner, catch-all inbox'ı IMAP/API üzerinden otomatik okur.
- Doğrulama bağlantısı regex + link extractor ile otomatik bulunur.
- Link, aynı profil/IP üzerinden izole bir BrowserContext'te otomatik tıklanır.
- Başarı, listing URL'sinin görünmesi ve "verified" sinyalinin alınmasıyla iki sinyal kuralına göre doğrulanır ve audit kaydına yazılır.
- Timeout durumunda retry kuyruğuna alınır; 3 başarısız denemede `failed` olarak işaretlenir.

---

## Form Fingerprint ve Self-Healing Drift

Fingerprint şu normalize edilmiş bilgilerin hash'idir:

- Form action/method
- Alanların name/type/accessible label bilgisi
- Zorunlu alanlar
- Select seçeneklerinin temel kimlikleri
- Submit düğmesinin role/name bilgisi

Hash değişirse runner submit etmez. Adapter `needs_remap` olur ve **autonomous self-healing döngüsü** başlar:

1. Vision-LLM yeni form ekranını analiz eder.
2. Semantic mapping ile eski alanları yeni locator'lara eşler.
3. Yeni `adapter.json` otomatik üretilir ve regression test'ten geçirilir.
4. Test geçerse yeni versiyon otomatik devreye alınır; geçemezse quarantine.

---

## Başarı Doğrulaması ve Idempotency

Başarı tek bir toast mesajına bağlanmamalıdır. İki veya daha fazla sinyal tercih edilir:

- Beklenen URL deseni
- Başarı heading/alert metni (Vision-LLM ile doğrulama)
- Listing/post URL'sinin oluşması
- Resmî API response ID'si
- E-posta doğrulama durumunun görünmesi

İşlem sonucu belirsizse otomatik retry yapılmaz. Önce mevcut listing/post aranır (idempotency check). İdempotency anahtarı örneği:

```text
<product-id>:<site-id>:<operation>:<content-version>:<persona-id>
```

---

## Audit ve Idempotency Deposu

Audit, idempotency ve politika kayıtları tek dosyalık SQLite veritabanında tutulur. Dosya repoya girmez; runner ile aynı makinede veya yedeklenen bir veri klasöründe durur.

Kurallar:

- Tablolar append-only'dir. `UPDATE` ve `DELETE` yapılmaz; düzeltme yeni bir event satırıdır.
- Şifre, token, cookie veya hassas form değeri yazılmaz (otomatik PII masking).
- Runner her submit öncesi idempotency anahtarını `PRIMARY KEY` üzerinden kontrol eder; aynı anahtar için ikinci submit denemesi fail-closed durur.
- WAL modu açık olur; düzenli olarak okunabilir dışa aktarım (CSV/JSONL) üretilir.

Minimum tablo seti:

```sql
CREATE TABLE submissions (
  idempotency_key  TEXT PRIMARY KEY,
  product_id       TEXT NOT NULL,
  site_id          TEXT NOT NULL,
  persona_id       TEXT NOT NULL,
  operation        TEXT NOT NULL,
  content_version  TEXT NOT NULL,
  status           TEXT NOT NULL CHECK (status IN
                     ('dry_run','auto_approved','submitted','email_verification_pending',
                      'published','ambiguous','failed','needs_remap','quarantined')),
  listing_url      TEXT,
  risk_score       REAL,
  decided_by       TEXT DEFAULT 'autonomous_engine',
  decided_at       TEXT,
  created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE audit_log (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  occurred_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  idempotency_key  TEXT REFERENCES submissions(idempotency_key),
  event            TEXT NOT NULL,
  detail_json      TEXT NOT NULL  -- maskelenmiş yapısal detay
);

CREATE TABLE policy_checks (
  site_id          TEXT NOT NULL,
  checked_at       TEXT NOT NULL,
  source_url       TEXT NOT NULL,
  execution        TEXT NOT NULL,
  result           TEXT NOT NULL,
  crawler_hash     TEXT,
  PRIMARY KEY (site_id, checked_at)
);

CREATE TABLE self_healing_events (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  site_id          TEXT NOT NULL,
  flow             TEXT NOT NULL,
  old_fingerprint  TEXT NOT NULL,
  new_fingerprint  TEXT NOT NULL,
  llm_mapping_json TEXT NOT NULL,
  regression_pass  BOOLEAN NOT NULL,
  occurred_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE jobs (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  flow_ref         TEXT NOT NULL,
  idempotency_key  TEXT REFERENCES submissions(idempotency_key),
  status           TEXT NOT NULL CHECK (status IN
                     ('queued','leased','running','done','failed','needs_remap','blocked_policy','cool_down')),
  leased_by        TEXT,
  leased_at        TEXT,
  finished_at      TEXT,
  error            TEXT
);
```

`jobs` tablosu operasyonel kuyruktur ve güncellenebilir; append-only kural `submissions`, `audit_log`, `policy_checks` ve `self_healing_events` için geçerlidir.

---

## Oturum ve Secret Yönetimi (0 Human)

- Şifreler adapter veya log içine yazılmaz.
- `storageState` cookie ve token içerebildiği için şifreli secret store'da (Vault) tutulur.
- Site/hesap başına ayrı state kullanılır (Multilogin profili ile eşleştirilir).
- **Otomatik Credential Enjeksiyonu:** Vault, TOTP secret'ı ile birlikte her login'de otomatik credential ve 2FA code üretir.
- **CAPTCHA Çözümü:** CapSolver/2Captcha API entegrasyonu ile reCAPTCHA, hCaptcha, Cloudflare Turnstile otomatik çözülür.
- State süresi dolduğunda autonomous agent otomatik re-login yapar.
- Screenshot ve HTML kaydından password, token, hidden CSRF value, cookie, e-posta ve kişisel veriler otomatik maskelenir (regex + NER tabanlı PII detector).
- Trace dosyaları kısa süreli tutulur ve hassas artefakt kabul edilir; otomatik rotation ile silinir.

---

## Comment ve DM Otonom Güvenlik Sınırları

DM job'ı şu alanlar olmadan çalışmaz (otomatik validation):

- `recipientId`
- `reason` (opt-in kaynağı)
- `consentSource` (DB referansı)
- `recipientOptInAt` (timestamp)
- `approvedBy` (autonomous_engine veya policy_hash)
- `approvedAt`
- `contentVersion`

Comment/reply; anahtar kelime taramasıyla toplu kullanıcı hedefleyemez. İçerik ilgili thread'e özel olmalı, **thread-context LLM** tarafından üretilmeli ve suppression listesi ile cross-check edilmelidir. Outbound DM varsayılan olarak engellenir; yalnızca explicit opt-in kaydı olan alıcılara gönderilir.

---

## Adapter Family Yaklaşımı

1.000 ayrı monolitik script yerine ortak family'ler kullanılır:

- `generic-directory`
- `ai-directory`
- `review-vendor-profile`
- `discourse-community`
- `content-publisher`
- `integration-marketplace`
- `cloud-marketplace`
- `autonomous-social`
- `autonomous-pr-outreach`

Family ortak alan ve doğrulamaları sağlar; site adapter'ı sadece URL, locator, politika ve siteye özgü validation farklarını içerir. Her family için ayrı risk skoru ağırlıkları ve autonomous decision policy'si tanımlanır.

---

## Veri Akışı (Tam Otonom Döngü)

```text
[Discovery Agent]       → Vision-LLM ile yeni site keşfi, adapter otomatik üretimi
        ↓
[Policy Crawler]        → Politika taraması, risk skoru ataması
        ↓
[Decision Engine]       → Risk tabanlı otomatik onay/quarantine/block kararı
        ↓
[Worker Pool]           → 10 IP/Multilogin profili üzerinden paralel job yürütme
        ↓
[Secret Vault]          → Credential + TOTP + storageState enjeksiyonu
        ↓
[CAPTCHA Solver]        → reCAPTCHA/hCaptcha/Turnstile otomatik çözüm
        ↓
[Runner]                → Form doldurma + submit
        ↓
[Email Verifier]        → IMAP üzerinden otomatik doğrulama linki tıklama
        ↓
[Assertion Engine]      → Multi-signal + Vision-LLM başarı doğrulaması
        ↓
[Self-Healing Module]   → Drift tespitinde otomatik adapter repair
        ↓
[Audit DB]              → Append-only idempotency ve compliance kaydı
        ↓
[Loop]                  → 24/7 otonom, 0 human-in-the-loop
```

---

## Hızlı Referans Tablosu

| Senaryo | Otonom Çözüm |
|---|---|
| Form drift | Vision-LLM + self-healing, otomatik adapter repair |
| CAPTCHA | CapSolver/2Captcha API entegrasyonu |
| 2FA | Vault'tan TOTP secret ile otomatik code üretimi |
| E-posta doğrulama | IMAP + link extractor + izole BrowserContext tıklaması |
| Policy değişikliği | Autonomous crawler, otomatik cool-down |
| Login state süresi doldu | Autonomous re-login, yeni storageState kaydı |
| PII log sızıntısı | Regex + NER tabanlı otomatik masking |
| Idempotency | `<product>:<site>:<op>:<version>:<persona>` key ile fail-closed |
| Banlanan hesap/IP | `dead-pool` veritabanına otomatik kayıt, bir daha kullanılmaz |
| Risk skoru | Autonomous decision engine ile eşik tabanlı karar |
```
