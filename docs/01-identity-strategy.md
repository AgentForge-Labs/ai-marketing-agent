 # Viral AI Marketing Agent — Kimlik & Operasyon Stratejisi

## 1. Agent Mimarisi

Merkezi bir **AI Marketing Agent** kontrolcüsü (LLM tabanlı) tüm operasyonu yönetir. Agent'ın alt modülleri:

| Modül | Görev |
|---|---|
| **Persona Engine** | 1000+ benzersiz kimlik üretir, yönetir, yaşatır. |
| **Content Core** | Platforma özgü viral içerik üretir (hikaye, tartışma, meme, karşılaştırma). |
| **Distribution Orchestrator** | Hangi içeriğin hangi persona ile hangi siteye ne zaman atılacağını planlar. |
| **Engagement Bot** | Yorumlara, DM'lere, etkileşimlere otonom yanıt verir. |
| **Evasion Layer** | Tespit pattern'lerini algılar, davranışı real-time değiştirir. |

---

## 2. Persona Fabrikası (1000+ Kimlik)

Her hesap **tamamen izole bir insan** gibi davranır. AI agent, her kayıt için şu verileri üretir ve veritabanında (`persona-registry`) saklar:

- **Kullanıcı adı:** Benzersiz, platform formatına uygun, hiçbir yerde tekrar etmez.
- **Görünen isim:** Rastgele veya AI üretimi, Türkçe/İngilizce karışımı olabilir.
- **E-posta:** `alias@domain.com` veya farklı domainler üzerinden alias. Tek kullanımlık domainler tercih edilir.
- **Avatar:** AI üretimi portre veya stok fotoğraf (aynı stok sitesinden 1000 farklı yüz).
- **Bio:** Her platforma özgü, farklı ilgi alanları, farklı meslekler, farklı ton.
- **Yazım stili (Voice):** Kimi emoji sever, kimi agresif, kimi teknik, kimi hikaye anlatıcısıdır. LLM prompt'una bu voice tanımı eklenir.
- **Demografi:** Yaş, lokasyon, timezone, meslek. Bu, paylaşım saatlerini ve içerik açısını belirler.

**Kural:** Aynı IP'deki 100 hesap bile birbirinin kopyası değil, tamamen farklı yaşamlar simüle eder.

---

## 3. Teknik Altyapı: İzolasyon Katmanı

| Bileşen | Yapılandırma |
|---|---|
| **Multilogin Profilleri** | 10 adet sabit profil. Her profil farklı OS, farklı ekran çözünürlüğü, farklı font seti, farklı timezone ile kalıcı olarak yapılandırılır. |
| **IP/Proxy** | Her Multilogin profiline 1 adet **sabit** IP atanır (residential/rotating değil, statik). IP değişimi "hesap çalınmış" sinyali verir. |
| **Tarayıcı Fingerprint** | Canvas, WebGL, audio context, hardware concurrency her profilde farklı ve sabit. |
| **Cookie & LocalStorage** | Her profil kendi cookie jar'ını korur. Cross-domain tracking'e karşı izolasyon tamdır. |
| **Session Rotation** | Bir profildeki 100 hesap aynı anda açık değil. Agent, sırayla session açar, işlem yapar, kapatır. |

---

## 4. IP ve Hesap Dağılımı (10 IP × 1000 Site)

**Hedef:** 10 IP ile 1000 site. Bu yüksek yoğunluk demektir. Agent'ın dağılım mantığı:

```
IP-1: Profil-1 → 100 hesap (SaaS dizinleri, Reddit alt dizinleri, forumlar)
IP-2: Profil-2 → 100 hesap (Teknik bloglar, Medium, DEV)
IP-3: Profil-3 → 100 hesap (AI tool dizinleri, Product Hunt benzerleri)
...
IP-10: Profil-10 → 100 hesap (Genel forumlar, Q&A siteleri)
```

**Agent Kuralları:**
- **IP başına günlük kayıt limiti:** Max 3-5 yeni hesap. 100 hesabın tamamı bir günde açılmaz; 20-30 günde yayılar.
- **IP başına günlük aktivite limiti:** Max 10-15 farklı sitede paylaşım/giriş.
- **Zamanlama:** Her persona kendi timezone'una göre "insan saatlerinde" aktif olur. Agent, UTC'ye göre değil, persona'nın lokasyonuna göre schedule üretir.
- **Cooldown:** Aynı IP'den art arda 2 işlem arasında 15-45 dakika rastgele bekleme.

---

## 5. Viral İçerik Motoru (Link Yok, Marka Var)

Link paylaşımı yapılmaz. Marka **doğal dilde** bahsedilir. AI agent'ın içerik üretim stratejisi:

### Formatlar
- **Problem → Çözüm hikayesi:** "3 aydır X problemi yaşıyordum, denemediğim yöntem kalmadı, en sonunda [Marka] ile çözdüm."
- **Tartışma başlatma:** "Sizce en iyi Y aracı hangisi? Ben [Marka]'yı denedim, şu özelliği çok farklı."
- **Karşılaştırma:** "[Rakip A] vs [Rakip B] vs [Marka] — şu senaryoda [Marka] daha mantıklı geldi."
- **Soru:** "[Marka] kullanan var mı? Şu özelliği nasıl buldunuz?"
- **Meme / espri:** Marka adı doğal bir şekilde espri içinde geçer.

### İçerik Farklılaştırma
Aynı marka için 1000 farklı içerik üretilirken AI şu varyasyonları uygular:
- **Cümle yapısı:** Kimi kısa ve net, kimi uzun hikaye.
- **Emoji yoğunluğu:** 0'dan 5'e kadar rastgele.
- **Teknik derinlik:** Kimi kullanıcı "basit" bulur, kimi "API'sini inceledim" der.
- **Duygu tonu:** Heyecanlı, şüpheci, minnettar, tarafsız.

---

## 6. Otonom Etkileşim (Engagement)

Agent sadece paylaşım yapmaz, **yaşayan hesap** gibi davranır:

- **Yorum takibi:** Paylaşılan gönderiye gelen yorumlara 2-24 saat içinde doğal yanıt.
- **Cross-etkileşim:** Persona, kendi ilgi alanındaki başka gönderilere (marka dışı) de yorum yapar. Oran: %80 organik etkileşim, %20 marka içerik.
- **Upvote/like:** Diğer kullanıcıların içeriklerine rastgele etkileşim.
- **DM yönetimi:** Gelen DM'lere persona'nın voice'ine uygun yanıt. Outbound DM yok (spam sinyali).

---

## 7. Anti-Tespit Katmanı (Evasion Layer)

Agent'ın kendi kendini düzenlediği kurallar:

| Tespit Vektörü | Agent Önlemi |
|---|---|
| **Kullanıcı adı korelasyonu** | Aynı kullanıcı adı asla tekrarlanmaz. |
| **İçerik fingerprint** | Aynı cümle kalıbı %1'den fazla kullanılmaz. LLM, her çıktıyı benzersiz üretir. |
| **Zaman pattern** | Paylaşımlar sabit saatte değil, Gaussian dağılımla rastgele zamanlarda yapılır. |
| **IP yoğunluğu** | IP başına günlük limit aşılırsa agent o IP'yi 24 saat "soğutur". |
| **Platform alarmı** | Bir hesap captcha veya kısıtlama alırsa, o IP'deki diğer hesaplar otomatik 48 saat pasife geçer. |
| **Metin benzerliği** | Agent, ürettiği her içeriği önceki 1000 içerikle cross-check eder; benzerlik %20'yi geçerse rewrite eder. |

---

## 8. Ölçeklendirme ve Yaşam Döngüsü

- **Keşif modülü:** Agent, yeni platformları ve alt dizinleri sürekli tarar. Yeni 100 site bulunduğunda, mevcut 10 IP'ye yayılarak (IP başına +10) yavaşça eklenir.
- **Hesap yaşamı:** Eski hesaplar pasifleştirilmez. Aksine, eski hesaplar "sahip" gibi görünür: profil fotoğrafı güncellenir, arada yeni etkileşim yapılır.
- **Ölüm yönetimi:** Banlanan hesap ve IP, `dead-pool` veritabanına kaydedilir. Aynı IP veya persona tekrar kullanılmaz.

---

## 9. Veri Akışı (Otonom Döngü)

```
[Persona Engine] → 1000 kimlik üretir
     ↓
[Content Core] → Her kimlik için marka bahsi geçen benzersiz içerik üretir
     ↓
[Distribution Orchestrator] → IP/profil/schedule atar
     ↓
[Multilogin + Proxy] → İzole session açar
     ↓
[Platform] → Paylaşım yapılır
     ↓
[Engagement Bot] → Etkileşimleri izler ve yanıt verir
     ↓
[Evasion Layer] → Anomali varsa operasyonu durdurur/rewrite eder
     ↓
[Loop] → 24/7 otonom devam eder
```

---

**Sonuç:** Bu yapıda 10 IP ve 1000 site, 1000 benzersiz AI persona tarafından yönetilir. Her biri farklı bir insan gibi davranır, farklı zamanlarda farklı içerikler üretir ve markayı doğal dilde viral hale getirir. Link yok, şablon yok, korelasyon yok. Agent kendi kendini izler, kendi kendini düzeltir.
