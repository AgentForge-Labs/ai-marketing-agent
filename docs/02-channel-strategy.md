```markdown
# Viral AI Marketing Agent — Operasyonel Kurallar ve Teknik Doküman

## 1. Genel Prensip

Tam otonom AI marketing agent, 10 adet IP adresi üzerinden 1000+ farklı platformda bağımsız ve birbirinden kopuk hesaplarla viral içerik dağıtımı yapar. Her hesap gerçek bir kullanıcı gibi davranır, hiçbir korelasyon izi bırakmaz. 

**Temel Kimlik Prensibi:** Arka planda (login, session, credential) tam izolasyon ve benzersizlik sağlanırken; ön planda (kamuya açık yazar adı, marka görünürlüğü) tutarlı bir marka kimliği inşa edilir. Şeffaflık ve disclosure (ürün tanıtımı/reklam) kurallarına azami uyulur.

---

## 2. Teknik Altyapı ve İzolasyon

| Bileşen | Kural |
|---|---|
| **IP Havuzu** | 10 adet statik IP. Her IP'ye 1 adet Multilogin profili sabit atanır. IP değişimi yasaktır (hesap güvenliği sinyali). |
| **Multilogin Profilleri** | 10 profil. Her profil farklı OS, ekran çözünürlüğü, font seti, timezone ve hardware fingerprint ile kalıcı yapılandırılır. |
| **Tarayıcı Fingerprint** | Canvas, WebGL, audio context, hardware concurrency her profilde farklı ve değiştirilemez. |
| **Cookie & Session** | Her profil kendi cookie jar'ını kalıcı olarak korur. Cross-domain tracking tamamen izole edilir. |
| **Credential Vault** | **Kesin İzolasyon:** Her site/hesap için benzersiz login username, şifre ve API token üretilir. Aynı login kimliği (username/password) asla farklı sitelerde tekrar kullanılmaz. |
| **IP Başına Hedef** | Her IP'den 500-1000 siteye erişim kabul edilir; ancak aktivite dağılımı operasyonel kurallara göre yönetilir. |

---

## 3. Kimlik ve Persona Fabrikası

Hesap kimlikleri **"Arka Plan (Login)"** ve **"Ön Plan (Public)"** olarak ikiye ayrılır.

| Parametre | Kural | Açıklama |
|---|---|---|
| **Login Username (Arka Plan)** | **Her site için kesinlikle benzersiz.** | Bir sitede sızıntı, spam flag veya ban olursa diğer 999 hesabın etkilenmemesi (cross-ban riskinin sıfırlanması) için sistem giriş bilgileri tamamen izole edilmelidir. |
| **Şifre & Token** | **Benzersiz ve Rastgele.** | Her hesap için 16+ karakter rastgele şifre ve mümkünse 2FA / API token. Password manager/vault kullanımı zorunludur. |
| **Public Display Name (Ön Plan)** | **Tutarlı Marka / Yazar Adı.** | Kamuya görünen yazar adı (örn. kurucu ismi veya marka adı) tüm sitelerde **aynı** tutulabilir. Bu, marka bilinirliği, güvenilirlik ve SEO otoritesi (E-E-A-T) inşası için stratejik olarak tercih edilir. |
| **Bio / Profil Arka Planı** | **Farklılaştırılmış.** | Public isim aynı olsa bile, bio metinleri, ilgi alanları ve mesleki geçmişler platformun kitlesine göre uyarlanır (Birebir kopya bio spam sinyali verir). |
| **E-posta** | **Her hesap için farklı alias.** | Catch-all wildcard ile yönetilir. `prefix@domain.com` formatında. Tek domain üzerinden alias bile olsa sistem farklı adresler olarak görür. |
| **Avatar** | **Tutarlı veya AI Üretimi.** | Marka yüzü veya kurucu kullanılıyorsa aynı görsel (farklı crop/filter ile). Persona ise AI üretimi 1000+ benzersiz yüz. |
| **Yazım stili (Voice)** | **Persona'ya veya Marka Tonuna Özgü.** | LLM prompt'una markanın kurumsal dili veya personanın karakter tanımı (teknik, hikaye anlatıcısı, şüpheci) eklenir. |

---

## 4. E-posta Altyapısı

1000 hesap için "az domain + catch-all wildcard" stratejisi uygulanır. 1000 ayrı domain yerine 5-10 domain alınıp her birinde catch-all aktif edilir. AI agent her kayıt için rastgele prefix üretir; tüm doğrulama mailleri tek merkezi inbox'a yönlendirilir.

### Servis Seçenekleri

| Servis | Maliyet | Özellik |
|---|---|---|
| **ForwardEmail Enhanced** | $3/ay | Sınırsız domain, sınırsız alias, API, 10GB depolama. **Önerilen.** |
| **ImprovMX Premium** | $9/ay | 30 domain, 100 alias/domain, API, webhook, 180 günlük log. |
| **Cloudflare Email Routing** | Ücretsiz | Catch-all destekler. Domain Cloudflare nameserver kullanmalı. |
| **Self-hosted (Mailcow/Mail-in-a-Box)** | VPS ~$5-10/ay | Tam kontrol, hiçbir üçüncü taraf log tutmaz. |

### Örnek Mimari

```text
[AI Agent] → rastgele prefix üretir (örn. "user123")
      ↓
[Domain Havuzu] → 5 domain (marka1.com, marka2.io, marka3.co, marka4.net, marka5.app)
      ↓
[Catch-All Forwarding] → *@domain.com → merkez@inbox.com
      ↓
[Doğrulama Okuyucu] → IMAP/API ile otomatik doğrulama linki tıklama
```

---

## 5. İçerik Stratejisi — Viral Motor

### Link ve Disclosure Politikası
- **Doğrudan link paylaşımı minimize edilir.** Marka adı doğal dilde, bağlam içinde geçer.
- Backlink veya SEO odaklı anchor text manipülasyonu yapılmaz.
- **Şeffaflık (Disclosure):** FTC/yerel yasalara ve platform kurallarına uygun olarak, ürün tanıtımı veya affiliate içeriklerde `#ad`, `#sponsored` veya "Kendi ürünüm/deneyimim" gibi şeffaf ibareler kullanılır.

### İçerik Formatları
| Format | Örnek |
|---|---|
| Problem → Çözüm | "3 aydır X problemi yaşıyordum, denemediğim yöntem kalmadı, en sonunda [Marka] ile çözdüm." |
| Tartışma başlatma | "Sizce en iyi Y aracı hangisi? Ben [Marka]'yı denedim, şu özelliği çok farklı." |
| Karşılaştırma | "[Rakip A] vs [Rakip B] vs [Marka] — şu senaryoda [Marka] daha mantıklı geldi." |
| Soru | "[Marka] kullanan var mı? Şu özelliği nasıl buldunuz?" |
| Deneyim | "Dün [Marka]'yı ilk kez denedim, beklediğimden farklı şeyler gördüm..." |

### İçerik Farklılaştırma Kuralı
Aynı marka için üretilen 1000 içerikte **cümle yapısı, kelime sıklığı, emoji kullanımı tamamen farklı olmalıdır.**

| Vektör | Farklılaştırma |
|---|---|
| **Cümle yapısı** | Kimi kısa ve net, kimi uzun hikaye. Kimi soruyla başlar, kimi iddia ile. |
| **Emoji yoğunluğu** | 0'dan 5'e kadar rastgele veya persona voice'una göre sabit ama persona arasında farklı. |
| **Teknik derinlik** | Kimi kullanıcı "basit ve güzel" der, kimi "API'sini inceledim, şu endpoint çok iyi" der. |
| **Duygu tonu** | Heyecanlı, şüpheci, minnettar, tarafsız, esprili. Her persona bir ton seçer ve ona sadık kalır. |

---

## 6. Zamanlama ve Operasyonel Kurallar

| Parametre | Kural | Gerekçe |
|---|---|---|
| **Kayıt hızı** | **Aynı IP'den 500 siteye aynı gün kayıt olma.** Dağıtım: Haftada 10-15 kayıt. | Toplu kayıt bot tespitini ve IP'yi "hesap fabrikası" olarak işaretlenmesini tetikler. |
| **Günlük aktivite limiti** | IP başına max 10-15 farklı sitede paylaşım/giriş. | Aynı IP'den 100+ siteye günlük erişim anomali olarak algılanır. |
| **Zamanlama** | Her persona kendi timezone'una göre "insan saatlerinde" aktif olur. | Agent, UTC'ye göre değil, persona demografisine göre schedule üretir. |
| **Cooldown** | Aynı IP'den art arda 2 işlem arasında 15-45 dakika rastgele bekleme. | Makine hızı yerine insan hızı simüle edilir. |
| **Gaussian dağılım** | Paylaşımlar sabit saatte değil, Gaussian dağılımla rastgele zamanlarda yapılır. | Saat başı paylaşım pattern'i tespit edilir. |

---

## 7. Otonom Etkileşim (Yaşayan Hesap Simülasyonu)

Agent sadece paylaşım yapmaz; hesaplar **yaşayan kullanıcı** gibi davranır:

| Etkileşim | Kural |
|---|---|
| **Organik / Marka oranı** | %80 organik etkileşim (marka dışı), %20 marka içerik. | Sadece marka bahseden hesaplar tek amaçlı (shill) olarak işaretlenir. |
| **Cross-etkileşim** | Persona, kendi ilgi alanındaki başka gönderilere yorum yapar. | Gerçek kullanıcılar sadece bir konuda konuşmaz. |
| **Yorum takibi** | Paylaşılan gönderiye gelen yorumlara 2-24 saat içinde doğal yanıt. | Anında yanıt bot sinyalidir. |
| **Upvote/like** | Diğer kullanıcıların içeriklerine rastgele etkileşim. | Sadece kendi gönderisini upvote'layan hesaplar tespit edilir. |
| **DM politikası** | Outbound DM yasaktır. Gelen DM'lere persona voice'una uygun yanıt verilir. | Giden DM spam filtresini doğrudan tetikler. |

---

## 8. Anti-Tespit ve Anomali Yönetimi (Evasion Layer)

| Tespit Vektörü | Agent Önlemi |
|---|---|
| **Kullanıcı adı/Login korelasyonu** | Aynı login username asla tekrarlanmaz. Veritabanı cross-check yapılır. |
| **İçerik fingerprint** | Aynı cümle kalıbı %1'den fazla kullanılmaz. LLM, her çıktıyı önceki 1000 içerikle karşılaştırır; benzerlik %20'yi geçerse rewrite eder. |
| **IP yoğunluğu** | IP başına günlük limit aşılırsa agent o IP'yi 24 saat "soğutur". Başka IP'den devam eder. |
| **Platform alarmı** | Bir hesap captcha veya kısıtlama alırsa, o IP'deki diğer hesaplar otomatik 48 saat pasife geçer. |
| **Metin benzerliği** | Agent, ürettiği her içeriği internal corpus ile cross-check eder. |

---

## 9. Kanal ve İçerik Yürütme Sınıfları

### 1. Dizin ve Listing Siteleri
En uygun deterministik otomasyon alanıdır.
- Ürün adı, URL, tagline, açıklama, kategori, fiyat, logo ve screenshot alanları `product-profile.json`'dan doldurulur.
- Aynı metin körlemesine her siteye basılmaz. Önceden onaylanmış kısa/orta/uzun açıklamalar ve kategoriye uygun varyantlar kullanılır.
- Gönderim öncesi güncel form, ücret, backlink, yayın politikası ve mevcut listing kontrol edilir.
- Başarı sonrasında listing URL'si ve UTM'li hedef URL kaydedilir.

### 2. Sosyal Ağlar
- Kurucu odaklı, gerçek ve platforma özgü içerik kullanılır. Marka adı (Public Display Name) tutarlı tutulur.
- Aynı içeriğin birebir cross-post edilmesi yerine format uyarlanır.
- Resmî API varsa API tercih edilir.
- Post, reply, comment, like ve DM için platforma özel izin matrisi uygulanır.

### 3. Topluluklar ve Yayın Platformları
- Hesap önce doğal ve faydalı katkılarla oluşturulur.
- Tanıtım, topluluk kuralları izin verdiğinde ve konuya doğrudan değer kattığında yapılır.
- Kurucu hikâyesi, teknik rehber, benchmark, vaka çalışması ve öğrendiklerimiz formatları tercih edilir.
- Otomasyon taslak ve araştırma seviyesinde kalabilir; publish/comment çoğunlukla insan onaylıdır.

### 4. DM, PR ve Partner Outreach
- Toplu, kopya veya istenmeyen mesaj gönderilmez.
- Her alıcı için neden ilgili olduğu kayıt altına alınır.
- Opt-out talepleri merkezi suppression listesine eklenir ve tüm adapter'lar tarafından uygulanır.
- PR pitch ve partner mesajları otomatik gönderimden önce insan tarafından okunur.

---

## 10. Platform Sınırları ve Yasaklar

Politikalar zamanla değişebilir; her adapter sürümünde resmî kaynak ve son kontrol tarihi tutulur.

| Platform | Kısıtlama | Kaynak |
|---|---|---|
| **LinkedIn** | Web sitesinde bot, crawler ve üçüncü taraf yazılımla post, mesaj, yorum ve benzeri otomasyonu yasaklar. Bu kanal için dışarıda taslak + manuel yayın modeli kullanılmalıdır. | https://www.linkedin.com/help/linkedin/answer/a1341387 |
| **X (Twitter)** | Web sitesinin script ile otomasyonunu yasaklar; izin verilen otomasyonlarda resmî API ve açık kullanıcı rızası kurallarını uygular. | https://help.x.com/en/rules-and-policies/x-automation |
| **Reddit** | Tekrarlanan veya istenmeyen toplu post, yorum, chat ve özel mesajları spam olarak değerlendirir. | https://support.reddithelp.com/hc/en-us/articles/360043504051-Spam |

---

## 11. İçerik Kaynağı ve Ürün Profili

Runtime içerik uydurmamalıdır. `product-profile.json` aşağıdaki onaylı varlıkları taşır:

- 60/120 karakter tagline
- 160/300/1.000 karakter açıklama
- ICP ve use-case listesi
- Fiyatlandırma özeti
- Kategori ve anahtar kelimeler
- Logo ve screenshot yolları
- Kurucu bio'su (Tutarlı Public Display Name kaynağı)
- Güvenlik ve gizlilik sayfaları
- Entegrasyonlar
- Sosyal kanıt ve doğrulanmış müşteri sonuçları

Adapter alanları bu verileri `valueFrom` ile referans eder. Siteye özel yasal veya editoryal beyanlar ayrıca insan onayı gerektirir.

---

## 12. Ölçüm ve UTM Yapısı

Her yayın veya listing mümkünse şu UTM yapısını kullanır:

```text
utm_source=<site_id>
utm_medium=directory|community|social|partner
utm_campaign=<kampanya_id>
utm_content=<content_variant_id>
```

### Minimum Takip Alanları
- submitted/published zamanı
- listing veya post URL'si
- kullanılan içerik sürümü
- onaylayan kişi
- referral session ve signup
- demo/trial/conversion
- güncelleme veya yenileme tarihi

---

## 13. Skor Geri Besleme Döngüsü

Ölçüm verisi kanal sırasını günceller; formül tek seferlik değil, haftalık yeniden hesaplanır.

```text
nihai skor = temel önem × ICP uyumu × kanal güvenilirliği × politika uyumu × ölçülebilirlik ÷ operasyon maliyeti
```

| Sinyal | Etki |
|---|---|
| Listing 90 gündür yayında ve 0 referral session | Kanal skoru ×0,5, öncelik bir seviye düşer (ör. P2 → P3) |
| İlk doğrulanmış signup | Kanal önceliği bir seviye yükselir |
| Spam şikayeti veya politika ihlali bildirimi | Kanal dondurulur, insan incelemesine alınır |
| Form/policy sürekli `needs_remap` (3 kez üst üste) | Operasyon maliyeti faktörü yükseltilir, kanal geri plana atılır |

---

## 14. Ölçeklendirme ve Yaşam Döngüsü

| Modül | Fonksiyon |
|---|---|
| **Keşif** | Agent sürekli yeni platform ve alt dizin tarar. Yeni 100 site bulunduğunda mevcut 10 IP'ye yavaşça eklenir. |
| **Hesap Yaşamı** | Eski hesaplar pasifleştirilmez. Profil fotoğrafı güncellenir, arada yeni etkileşim yapılır. |
| **Ölüm Yönetimi** | Banlanan hesap ve IP `dead-pool` veritabanına kaydedilir. Aynı IP, şifre veya login username tekrar kullanılmaz. |

---

## 15. Veri Akışı (Otonom Döngü)

```text
[Persona Engine] → 1000+ benzersiz login kimliği ve public persona üretir
        ↓
[Content Core] → Her kimlik için marka bahsi geçen benzersiz içerik üretir
        ↓
[Distribution Orchestrator] → IP/profil/schedule atar (haftada 10-15 kayıt kuralına uygun)
        ↓
[Multilogin + Proxy + Vault] → İzole session açar, benzersiz credential girer
        ↓
[Platform] → Paylaşım yapılır (link yok/minimum, marka doğal dilde, disclosure mevcut)
        ↓
[Engagement Bot] → Etkileşimleri izler, %80 organik / %20 marka oranında yanıt verir
        ↓
[Evasion Layer] → Anomali varsa operasyonu durdurur, rewrite eder veya IP soğutur
        ↓
[Loop] → 24/7 otonom devam eder
```

---

## 16. Özet Tablo / Hızlı Referans

| Senaryo | Kural |
|---|---|
| **10 IP, 1000 Site** | Kabul edilir. Ancak IP başına günlük aktivite sınırlandırılır. |
| **Login Username** | **Her site için benzersiz.** Asla aynı giriş bilgisi kullanılmaz. |
| **Public Display Name** | **Aynı olabilir.** Marka tutarlılığı ve SEO otoritesi için kamuya açık yazar/marka adı aynı tutulur. |
| **E-posta** | **Her hesap için farklı alias.** Catch-all wildcard ile yönetilir. |
| **Şifre / Token** | **Benzersiz.** Vault üzerinden yönetilir. |
| **İçerik** | Cümle yapısı, kelime sıklığı, emoji kullanımı tamamen farklı olmalı. Şablon yok. |
| **Zamanlama** | Aynı IP'den 500 siteye aynı gün kayıt olma. Dağıtım: haftada 10-15 kayıt. |
| **Etkileşim** | %80 organik, %20 marka. Outbound DM yasak. |
| **Tespit anında** | Otomatik soğutma, rewrite, pasif mod. |
| **LinkedIn / X / Reddit** | Otomasyon yasak veya kısıtlı. Taslak + manuel model. |
| **İçerik kaynağı** | `product-profile.json` referans alınır. Runtime uydurma yok. |
| **Ölçüm** | UTM'li URL, haftalık skor geri besleme. |
```
