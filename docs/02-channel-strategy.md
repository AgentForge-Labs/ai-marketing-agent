# Kanal ve içerik stratejisi

## Önceliklendirme

Excel sırası başlangıç hipotezidir; ürün özelindeki nihai sıra değildir. Her kanal aşağıdaki faktörlerle yeniden puanlanmalıdır:

```text
nihai skor = temel önem
            × ICP uyumu
            × kanal güvenilirliği
            × politika uyumu
            × ölçülebilirlik
            ÷ operasyon maliyeti
```

Bir kanalın yüksek trafiği olması, ürünün ICP'siyle uyuşmuyorsa onu otomatik olarak öncelikli yapmaz.

## Dört yürütme sınıfı

### 1. Dizin ve listing siteleri

En uygun deterministik otomasyon alanıdır.

- Ürün adı, URL, tagline, açıklama, kategori, fiyat, logo ve screenshot alanları ürün profilinden doldurulur.
- Aynı metin körlemesine her siteye basılmaz. Önceden onaylanmış kısa/orta/uzun açıklamalar ve kategoriye uygun varyantlar kullanılır.
- Gönderim öncesi güncel form, ücret, backlink, yayın politikası ve mevcut listing kontrol edilir.
- Başarı sonrasında listing URL'si ve UTM'li hedef URL kaydedilir.
- Aynı ürün/site kombinasyonu ikinci kez gönderilmez.

### 2. Sosyal ağlar

- Kurucu odaklı, gerçek ve platforma özgü içerik kullanılır.
- Aynı içeriğin birebir cross-post edilmesi yerine format uyarlanır.
- Resmî API varsa API tercih edilir.
- Post, reply, comment, like ve DM için platforma özel izin matrisi uygulanır.
- Toplu reply, toplu takip, etkileşim manipülasyonu veya anahtar kelimeye dayalı istenmeyen cevap üretilmez.

### 3. Topluluklar ve yayın platformları

- Hesap önce doğal ve faydalı katkılarla oluşturulur.
- Tanıtım, topluluk kuralları izin verdiğinde ve konuya doğrudan değer kattığında yapılır.
- Kurucu hikâyesi, teknik rehber, benchmark, vaka çalışması ve öğrendiklerimiz formatları tercih edilir.
- Otomasyon taslak ve araştırma seviyesinde kalabilir; publish/comment çoğunlukla insan onaylıdır.

### 4. DM, PR ve partner outreach

- Toplu, kopya veya istenmeyen mesaj gönderilmez.
- Her alıcı için neden ilgili olduğu kayıt altına alınır.
- Kaynak, iletişim nedeni, son temas, opt-in/opt-out ve sonraki uygun tarih tutulur.
- Opt-out talepleri merkezi suppression listesine eklenir ve tüm adapter'lar tarafından uygulanır.
- PR pitch ve partner mesajları otomatik gönderimden önce insan tarafından okunur.

## Platform sınırları

Politikalar zamanla değişebilir; her adapter sürümünde resmî kaynak ve son kontrol tarihi tutulur.

- LinkedIn, web sitesinde bot, crawler ve üçüncü taraf yazılımla post, mesaj, yorum ve benzeri otomasyonu yasaklar. Bu kanal için dışarıda taslak + manuel yayın modeli kullanılmalıdır.
  - https://www.linkedin.com/help/linkedin/answer/a1341387/prohibited-software-and-extensions?lang=en
- X, web sitesinin script ile otomasyonunu yasaklar; izin verilen otomasyonlarda resmî API ve açık kullanıcı rızası kurallarını uygular.
  - https://help.x.com/en/rules-and-policies/x-automation
- Reddit, tekrarlanan veya istenmeyen toplu post, yorum, chat ve özel mesajları spam olarak değerlendirir.
  - https://support.reddithelp.com/hc/en-us/articles/360043504051-Spam

## İçerik kaynağı

Runtime içerik uydurmamalıdır. `product-profile.json` aşağıdaki onaylı varlıkları taşır:

- 60/120 karakter tagline
- 160/300/1.000 karakter açıklama
- ICP ve use-case listesi
- fiyatlandırma özeti
- kategori ve anahtar kelimeler
- logo ve screenshot yolları
- kurucu bio'su
- güvenlik ve gizlilik sayfaları
- entegrasyonlar
- sosyal kanıt ve doğrulanmış müşteri sonuçları

Adapter alanları bu verileri `valueFrom` ile referans eder. Siteye özel yasal veya editoryal beyanlar ayrıca insan onayı gerektirir.

## Ölçüm

Her yayın veya listing mümkünse şu UTM yapısını kullanır:

```text
utm_source=<site_id>
utm_medium=directory|community|social|partner
utm_campaign=<kampanya_id>
utm_content=<content_variant_id>
```

Minimum takip alanları:

- submitted/published zamanı
- listing veya post URL'si
- kullanılan içerik sürümü
- onaylayan kişi
- referral session ve signup
- demo/trial/conversion
- güncelleme veya yenileme tarihi

## Skor geri besleme döngüsü

Ölçüm verisi kanal sırasını günceller; formül tek seferlik değil, haftalık yeniden hesaplanır.

Kurallar:

| Sinyal | Etki |
|---|---|
| Listing 90 gündür yayında ve 0 referral session | Kanal skoru ×0,5, öncelik bir seviye düşer (ör. P2 → P3) |
| İlk doğrulanmış signup | Kanal önceliği bir seviye yükselir |
| Spam şikayeti veya politika ihlali bildirimi | Kanal dondurulur, insan incelemesine alınır |
| Form/policy sürekli `needs_remap` (3 kez üst üste) | Operasyon maliyeti faktörü yükseltilir, kanal geri plana atılır |

Değişiklikler kanal başına geçmişte saklanır; skor güncellemeleri hangi veriyle tetiklendiğini kaydeder. Böylece insan inceleme zamanı conversion üreten kanallara otomatik kayar.

