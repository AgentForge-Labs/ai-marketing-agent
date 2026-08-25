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



# Otonom Viral AI Marketing Agent — 0-HITL Drop-in Mimarisi

Bu doküman, Playwright/SQLite tabanlı otomasyon altyapısı ile 1000+ persona'lı viral AI marketing agent'ını **sıfır insan müdahalesi** prensibiyle bütünleştirir. İlk dokümanın tüm teknik katmanları (audit, idempotency, form fingerprint, adapter compiler) korunur; "human in the loop" gerektiren her nokta otonom karar motoruna devredilir.

---

## 1. Felsefe: 0-HITL (Zero Human In The Loop)

| İlk Doküman | 0-HITL Dönüşümü |
|---|---|
| `manual_only` execution | Kaldırılır. Yerine `risk_threshold` tabanlı otomatik karar motoru gelir. |
| `browser_with_submit_approval` | `browser_auto_submit` + `risk_score < threshold` koşulu. |
| `emailVerification: manual_only` | `emailVerification: auto` — IMAP polling + link extraction + otomatik tıklama. |
| Human recorder gezintisi | AI-assisted bootstrap recorder: agent, yeni siteyi keşfedip form şemasını otomatik üretir; insan onayı yerine `confidence_score > 0.85` kontrolü. |
| 2FA/CAPTCHA = human | TOTP secret vault'tan otomatik üretilir; CAPTCHA çözüm servisi (Capsolver/2Captcha) entegre edilir. |
| Comment/DM `approvedBy` | `consentScore` + `contentSafetyScore` + `rateLimitCheck` üçlüsü; onay yerine policy enforcement. |

**Temel Kural:** Sistem `fail-closed` çalışır. Belirsizlik durumunda işlem durur, audit kaydı oluşturulur, ancak retry veya fallback mekanizmaları devreye girer. İnsan müdahalesi yoktur; karar verme yetkisi LLM tabanlı `Autonomy Engine`'e aittir.

---

## 2. Teknoloji Stack

| Katman | Seçim | 0-HITL Notu |
|---|---|---|
| Dil/runtime | TypeScript + Node.js LTS | Playwright ekosistemiyle uyum; adapter tipleri derleme anında doğrulanır |
| Tarayıcı bağlantısı | Playwright `chromium.connectOverCDP` | MultiLogin/Browserless üzerinden 10 sabit profil |
| Profil sağlayıcı | MultiLogin (10 profil, statik) | Her profil farklı OS, ekran, font, timezone; değiştirilemez |
| IP/Proxy | 10 statik residential IP | IP başına 100 persona; IP değişimi yasak (hesap güvenliği sinyali) |
| Paralellik | Worker havuzu (10 slot) + SQLite `jobs` tablosu | Aynı sitede concurrency = 1; farklı siteler paralel |
| Adapter compiler | Saf fonksiyon (TS) | JSON DSL → Playwright eylemleri; `eval` yok |
| LLM | OpenAI/Anthropic API | Content generation, persona voice, risk assessment |
| Email | IMAP + Catch-all (5 domain) | ForwardEmail/Cloudflare Email Routing; merkezi inbox |
| CAPTCHA | Capsolver/2Captcha API | Headless çözüm; başarısız olursa job `failed` → cooldown |
| 2FA | `otpauth` TOTP üretimi | Secret vault'ta; zaman senkronizasyonu NTP ile |
| Secret store | HashiCorp Vault veya encrypted SQLite | `storageState`, password, TOTP secret, API key |

---

## 3. Veri Modeli (SQLite)

İlk dokümandaki tablolara eklenecek minimum şema:

```sql
-- Persona registry (1000+ kimlik)
CREATE TABLE personas (
  persona_id       TEXT PRIMARY KEY,
  handle           TEXT NOT NULL UNIQUE,  -- platform bazında benzersiz
  display_name     TEXT NOT NULL,
  email_prefix     TEXT NOT NULL,
  email_domain     TEXT NOT NULL,
  avatar_seed      TEXT NOT NULL,         -- AI generation seed veya stok ID
  voice_profile    TEXT NOT NULL,         -- JSON: ton, emoji yoğunluğu, cümle yapısı
  demographics     TEXT NOT NULL,         -- JSON: yaş, lokasyon, timezone, meslek
  assigned_ip      TEXT NOT NULL,
  assigned_profile TEXT NOT NULL,         -- MultiLogin profil ID
  created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  status           TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','dead'))
);

-- Content corpus (üretilmiş içerikler)
CREATE TABLE contents (
  content_id       TEXT PRIMARY KEY,
  persona_id       TEXT NOT NULL REFERENCES personas(persona_id),
  site_id          TEXT NOT NULL,
  operation        TEXT NOT NULL,         -- submitListing | post | comment | reply
  content_body     TEXT NOT NULL,
  brand_mention    TEXT NOT NULL,
  similarity_hash  TEXT NOT NULL,         -- semantic fingerprint
  created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  used_at          TEXT
);

-- Email inbox (catch-all merkezi kutusu)
CREATE TABLE email_inbox (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  received_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  to_address       TEXT NOT NULL,          -- prefix@domain.com
  from_address     TEXT NOT NULL,
  subject          TEXT NOT NULL,
  body_text        TEXT,
  body_html        TEXT,
  verification_link TEXT,               -- extract edilmiş link
  extracted_code   TEXT,                  -- OTP kodu
  status           TEXT NOT NULL DEFAULT 'unread' CHECK (status IN ('unread','processing','clicked','verified','expired')),
  related_job_id   INTEGER REFERENCES jobs(id)
);

-- Risk assessment log (0-HITL karar gerekçeleri)
CREATE TABLE risk_decisions (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  idempotency_key  TEXT NOT NULL,
  decision         TEXT NOT NULL CHECK (decision IN ('auto_execute','auto_reject','needs_fallback')),
  risk_score       REAL NOT NULL,         -- 0.0 - 1.0
  reasoning        TEXT NOT NULL,         -- LLM/Rule-based gerekçe
  model_version    TEXT,
  created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- Session & auth state
CREATE TABLE sessions (
  session_id       TEXT PRIMARY KEY,
  persona_id       TEXT NOT NULL REFERENCES personas(persona_id),
  site_id          TEXT NOT NULL,
  storage_state    BLOB NOT NULL,         -- encrypted Playwright storageState
  totp_secret      TEXT,                   -- encrypted base32 secret
  last_refresh     TEXT,
  expires_at       TEXT NOT NULL
);
```

---

## 4. Otonom Email Verification Akışı

İlk dokümandaki `emailVerification: manual_only` yerine tam otonom akış:

```json
"emailVerification": {
  "kind": "email",
  "execution": "auto",
  "mailboxRef": "vault://email/inbox",
  "pollingIntervalSec": 30,
  "maxWaitMin": 15,
  "linkSelector": "a[href*='verify']",
  "fallbackCodeRegex": "\\b\\d{6}\\b"
}
```

**Akış:**

1. **Submit sonrası** runner `emailVerification` job'u oluşturur; `submissions.status = 'email_verification_pending'`
2. **IMAP poller** (ayrı lightweight process) `email_inbox`'ı tarar; `to_address` = `persona.email_prefix@persona.email_domain`
3. **Link extraction:** HTML body'den `verification_link` çıkarılır (selector veya regex)
4. **Otomatik tıklama:** Yeni BrowserContext'te (aynı profil/IP) link açılır; success assertion çalıştırılır
5. **Two-signal rule:** 
   - Beklenen URL pattern'i görünür mü?
   - Başarı mesajı/assertion geçti mi?
6. **Durum güncelleme:** `submissions.status = 'published'`; audit log'a `email_verified` event'i yazılır
7. **Timeout:** 15 dakika içinde gelmezse job `failed`; idempotency key ile retry yapılmaz (önce inbox kontrol edilir, duplicate submit engellenir)

**CAPTCHA/2FA durumu:** Email verification sayfasında CAPTCHA çıkarsa, Capsolver devreye girer. 2FA istenirse (nadir), `needs_fallback` → `failed` (0-HITL prensibi: email verification'da 2FA beklenmez, site `policy_registry`'den `email_verification_complexity = high` olarak işaretlenip farklı strateji uygulanır).

---

## 5. Persona Engine (1000+ Kimlik)

### Üretim ve İzolasyon

```
[Persona Engine]
    ↓
SQLite `personas` tablosuna batch insert
    ↓
Her persona'ya atanır:
  - 1 IP (10 IP havuzundan)
  - 1 MultiLogin profili (10 profilden)
  - 1 email domain (5 domain havuzundan)
  - 1 unique handle (cross-site unique, veritabanı constraint)
```

**Kısıtlar:**
- `handle` alanı **global unique**; aynı kullanıcı adı hiçbir platformda tekrarlanamaz
- `assigned_ip` sabit; IP değişimi `persona.status = 'suspended'` tetikler
- `voice_profile` JSON'u LLM prompt'una enjekte edilir; her persona sabit ton kullanır
- `demographics.timezone` schedule üretiminde kullanılır; UTC değil, persona lokasyonuna göre Gaussian dağılımlı paylaşım saatleri

### Session Rotation

Bir MultiLogin profilinde 100 persona sırayla çalışır. Aynı anda tek session açık:
- Agent login → işlem → `storageState` kaydet → logout/context close → sonraki persona
- Her session sonrası 15-45 dakika rastgele cooldown (IP başına rate limit)

---

## 6. Content Core — Viral DSL

### İçerik Üretim Akışı

```
[Distribution Orchestrator]
    ↓
site_id + persona_id + operation → Content Core
    ↓
LLM prompt: voice_profile + brand_mention + content_format + anti_fingerprint_rules
    ↓
content_body + similarity_hash
    ↓
SQLite `contents` tablosuna kaydet
```

**Formatlar (DSL):**
```json
{
  "format": "problem_solution",
  "brand_mention": "MarkaX",
  "include_link": false,
  "tone": "grateful",
  "emoji_count": 2,
  "technical_depth": "medium",
  "max_similarity": 0.20
}
```

**Anti-Fingerprint Kuralları (0-HITL Enforcement):**
1. Yeni içerik üretildiğinde `similarity_hash` hesaplanır (semantic embedding veya MinHash)
2. Aynı `brand_mention` için son 1000 içerikle cross-check
3. Benzerlik > 0.20 ise LLM'e `rewrite` talimatı verilir; maksimum 3 deneme
4. Başarısız olursa content `rejected` olarak işaretlenir; audit log'a `content_fingerprint_reject` yazılır

**Link Politikası:** Doğrudan URL paylaşımı yasak. Marka adı doğal dilde geçer. Adapter compiler `goto` ve `fill` ile form doldurur; içerikte URL yoksa bile marka mention kontrolü yapılır.

---

## 7. Distribution Orchestrator

### Scheduler (Zamanlama)

| Parametre | Kural | Gerekçe |
|---|---|---|
| Kayıt hızı | IP başına haftada max 15 yeni hesap | Toplu kayıt bot sinyali |
| Günlük aktivite | IP başına max 15 farklı sitede paylaşım | 100+ site/gün anomali |
| Zamanlama | Persona timezone'ına göre Gaussian dağılım | Saat başı pattern tespiti |
| Cooldown | Aynı IP'de art arda 15-45 dk rastgele bekleme | Makine hızı simülasyonu |
| IP soğutma | Günlük limit aşılırsa 24 saat pasif | IP reputation koruma |

### Queue Yönetimi

```sql
-- jobs tablosuna eklenecek alanlar
ALTER TABLE jobs ADD COLUMN persona_id TEXT REFERENCES personas(persona_id);
ALTER TABLE jobs ADD COLUMN content_id TEXT REFERENCES contents(content_id);
ALTER TABLE jobs ADD COLUMN scheduled_at TEXT NOT NULL;
ALTER TABLE jobs ADD COLUMN risk_score REAL;
```

Orchestrator, `scheduled_at` zamanı gelen job'ları `jobs.status = 'queued'` yapar. Worker havuzu lease mekanizmasıyla çeker.

---

## 8. Runner Akışı (0-HITL)

İlk dokümandaki akış, onay adımları kaldırılarak:

```text
preflight
  → policy check (site registry'den execution mode oku)
  → auth state load (vault'tan decrypt et, storageState uygula)
  → 2FA/CAPTCHA auto-solve (gerekirse)
  → entry URL allowlist check
  → form fingerprint check (hash match?)
  → locator uniqueness check
  → dry-run fill (değerler maskeli)
  → risk assessment (LLM/rule engine: risk_score < 0.3?)
  → auto-submit (risk_score threshold altındaysa)
  → success/failure assertion (2+ sinyal)
  → email verification (auto polling)
  → audit + idempotency record
```

**Risk Assessment (Yeni):**
- `risk_score` 0.0-1.0 arası
- Girdiler: site trust score, persona age, content safety score, operation type (comment > post > listing)
- `risk_score < 0.3`: `auto_execute`
- `0.3 <= risk_score < 0.7`: `auto_execute` ama `audit_log` detaylı
- `risk_score >= 0.7`: `auto_reject`; job `blocked_policy` durumuna geçer

**Comment/DM Güvenlik Sınırları (0-HITL Uyumlu):**
```json
{
  "recipientId": "required",
  "reason": "required",
  "consentSource": "required",
  "recipientOptInAt": "required",
  "contentSafetyScore": 0.15,
  "rateLimitBucket": "dm_daily_5"
}
```
Outbound DM için `consentSource` ve `recipientOptInAt` zorunlu; yoksa `auto_reject`. Comment için keyword taraması yok; ancak `contentSafetyScore < 0.2` ve thread-specific içerik şartı.

---

## 9. Evasion Layer (Anti-Tespit)

| Tespit Vektörü | Otonom Önlem |
|---|---|
| Kullanıcı adı korelasyonu | `personas.handle` UNIQUE constraint; veritabanı cross-check |
| İçerik fingerprint | `similarity_hash` cross-check; %20 threshold; otomatik rewrite |
| Zaman pattern | Gaussian dağılım; sabit saat yok |
| IP yoğunluğu | IP başına günlük limit; aşılırsa 24 saat cooldown |
| Platform alarmı | Captcha/kısıtlama → o IP'deki tüm aktif job'lar 48 saat `paused` |
| Tarayıcı fingerprint | MultiLogin profili sabit; Canvas/WebGL/OS spoofing profil seviyesinde |
| Cookie izolasyonu | Her profil kendi `storageState`'ini korur; cross-domain tracking yok |

**Evasion Engine:** Runner içinde `evasion_check()` fonksiyonu; her submit öncesi:
1. Son 24 saatte aynı IP'den kaç submit?
2. Aynı sitede son submit ne zaman?
3. Platform response'unda ban/captcha sinyali var mı?
Anomali tespit edilirse job `paused` → cooldown → retry (exponential backoff).

---

## 10. Engagement Bot (Yaşayan Hesap Simülasyonu)

| Etkileşim | Kural | Otonom Yürütüm |
|---|---|---|
| Organik/Marka oranı | %80 organik, %20 marka | Orchestrator schedule'ına göre |
| Cross-etkileşim | İlgi alanındaki başka gönderilere yorum | Content Core'dan "organic_comment" formatı üretilir |
| Yorum takibi | Paylaşıma gelen yorumlara 2-24 saat içinde yanıt | Inbound webhook/polling → LLM yanıt üretimi → Adapter ile reply submit |
| Upvote/like | Rastgele etkileşim | `organic_interaction` job tipi; rate limit dahilinde |
| DM politikası | Outbound DM yasak | `auto_reject`; inbound DM'ler `reply` job'una dönüşür |

**Inbound DM/Comment Okuma:** Playwright ile platforma login olup notification/comment alanı taranır; yeni etkileşim tespit edilirse `engagement_queue`'ya job düşer.

---

## 11. Adapter Family (Viral Marketing)

1000 monolitik script yerine family'ler:

| Family | Kullanım Alanı | Özellik |
|---|---|---|
| `viral-directory` | AI tool dizinleri, SaaS dizinleri | Form submit, kategori seçimi, logo upload |
| `viral-forum` | Reddit, Discourse, özel forumlar | Post, comment, upvote; markdown desteği |
| `viral-social` | Twitter/X, LinkedIn, Mastodon | Short-form content; thread desteği; no-link policy |
| `viral-marketplace` | Product Hunt benzeri | Launch form; upvote interaction (organik) |
| `viral-qna` | Stack Overflow, Quora | Soru cevap; teknik derinlik varyasyonu |

Her family ortak alan doğrulamalarını sağlar; site adapter'ı sadece URL, locator, politika ve locale farklarını içerir.

---

## 12. Oturum ve Secret Yönetimi (0-HITL)

| Secret | Yönetim |
|---|---|
| Password | Vault'ta şifreli; adapter'a runtime decrypt; log'da maskeli |
| TOTP Secret | `sessions.totp_secret`; `otpauth` ile kod üretimi; NTP senkronizasyonu |
| `storageState` | `sessions.storage_state` BLOB; AES-256; per persona + site |
| API Key (LLM, CAPTCHA) | Environment variable; rotation desteği |
| Email IMAP şifresi | Vault; IMAP client başlangıcında decrypt |

**2FA Akışı:**
1. Login formunda TOTP alanı tespit edilirse `sessions.totp_secret`'ı oku
2. `otpauth` ile 6 haneli kod üret
3. `fill` ile alana yaz
4. Başarısız olursa (clock drift) 1 retry; yine başarısızsa `failed`

---

## 13. Form Fingerprint ve Drift (0-HITL)

Fingerprint hash'i ilk dokümanla aynı:
- form action/method
- alanların name/type/accessible label
- zorunlu alanlar
- select seçenekleri
- submit düğmesi role/name

**Drift Tespiti:**
- Hash değişirse runner submit etmez
- `needs_remap` durumunda job `recorder_queue`'ya düşer
- 0-HITL'de "human recorder" yerine **AI Bootstrap Recorder** devreye girer:
  - Playwright codegen benzeri keşif: sayfada gezilir, formlar taranır
  - LLM ile `form.json` üretimi (confidence > 0.85 ise auto-accept)
  - Confidence düşükse site `policy_registry.execution = 'manual_bootstrap'` olarak işaretlenir (bu durumda site 0-HITL dışına çıkar; kullanıcı isterse manuel recorder çalıştırır)

---

## 14. Audit ve Idempotency (0-HITL)

İlk dokümanın `submissions`, `audit_log`, `policy_checks` tabloları korunur. Eklentiler:

**`risk_decisions` Tablosu:**
Her otonom kararın gerekçesi kaydedilir. LLM tabanlı kararlarda `model_version` ve `reasoning` zorunlu.

**Idempotency:**
- Anahtar: `<persona_id>:<site_id>:<operation>:<content_version>`
- `PRIMARY KEY` üzerinden fail-closed; duplicate submit engellenir
- `status = 'ambiguous'` durumunda: otomatik retry yok; önce mevcut listing aranır (search adapter'ı ile); bulunamazsa yeni job `queued` (farklı content_version)

**WAL ve Export:**
- WAL modu açık
- Günlük CSV/JSONL export; PII maskeli

---

## 15. Ölçeklendirme ve Ölüm Yönetimi

| Senaryo | Yönetim |
|---|---|
| 10 IP × 100 persona = 1000 hesap | Her IP'ye 100 persona; MultiLogin profili başına 100 |
| Banlanan hesap | `personas.status = 'dead'`; `dead-pool` tablosuna kaydet; aynı handle/email/IP tekrar kullanılmaz |
| Banlanan IP | IP havuzundan çıkar; yedek IP varsa yerine atar; yoksa capacity düşürülür |
| Yeni site keşfi | Keşif modülü tarar; AI Bootstrap Recorder ile form.json üretilir; confidence > 0.85 ise otomatik devreye alınır |
| Eski hesap bakımı | Pasifleştirilmez; arada `organic_interaction` job'u üretilir; profil fotoğrafı güncelleme (aylık) |

---

## 16. Operasyonel Akış (24/7 Otonom Döngü)

```
[Persona Engine] → 1000 kayıtlı persona
        ↓
[Content Core] → Her persona/site için benzersiz içerik + similarity check
        ↓
[Distribution Orchestrator] → IP/profil/schedule atar (rate limit + Gaussian)
        ↓
[Job Queue] → SQLite `jobs` tablosu (scheduled_at + lease)
        ↓
[Worker Havuzu] → 10 slot; lease alır; MultiLogin + statik IP ile izole session
        ↓
[Runner] → Preflight → Auth → Fingerprint → Risk Assessment → Auto-Submit
        ↓
[CAPTCHA/2FA Engine] → Gerekirse otomatik çözüm
        ↓
[Email Verification] → IMAP polling → Link extraction → Auto-click → Two-signal verify
        ↓
[Engagement Bot] → Inbound yorum/DM'leri izler; LLM yanıt üretir; reply submit
        ↓
[Evasion Layer] → Anomali varsa cooldown/rewrite/pasif mod
        ↓
[Audit + Idempotency] → Tüm adımlar kaydedilir; fail-closed
        ↓
[Loop] → 7/24 otonom devam
```

---

## 17. Hızlı Başlangıç Checklist

1. **Domain:** 5 adet domain al (farklı TLD, farklı registrar); Cloudflare Email Routing veya ForwardEmail ile catch-all yapılandır
2. **MultiLogin:** 10 profil oluştur; her profil farklı OS, ekran, timezone
3. **IP:** 10 statik residential IP al; profil başına sabit ata
4. **VPS:** 1 adet (runner + SQLite + IMAP poller); 2-4GB RAM
5. **Vault:** `storageState`, password, TOTP secret, API key'leri şifrele
6. **Persona Engine:** 1000 persona üret; SQLite `personas` tablosuna batch insert
7. **Site Registry:** Hedef siteleri ekle; `policy_registry`'den execution mode = `auto`
8. **Bootstrap:** AI Recorder ile ilk 10 siteyi keşfet; `form.json` üret
9. **Adapter Compiler:** Family'leri tanımla; site adapter'larını yaz
10. **Dry-Run:** `--dry-run` flag ile 10 job çalıştır; screenshot + audit log kontrol et
11. **Live:** Dry-run başarılı ise orchestrator'ı başlat; 7/24 otonom çalışmaya başlar

---

Bu mimari, ilk dokümanın tüm teknik disiplinlerini (Playwright locator stratejisi, SQLite audit, form fingerprint, idempotency, adapter compiler) korurken, viral marketing agent'ının 1000+ persona, içerik üretimi, dağıtım ve anti-tespit gereksinimlerini **sıfır insan müdahalesi** ile çalışacak şekilde entegre eder. Tüm kararlar `risk_decisions` tablosunda gerekçeleriyle kayıtlıdır; sistem tamamen gözlemlenebilir ve tekrar üretilebilir şekilde çalışır.


