# AI Marketing Agent

Compliance-first SaaS dağıtım ve pazarlama otomasyonu için strateji, veri seti ve adapter sözleşmeleri.

Bu repo şu an dokümantasyon ve şema aşamasındadır. Amaç, 1.000 kanala aynı içeriği topluca gönderen bir bot yapmak değildir. Amaç; izinli dizin/listing işlemlerini deterministik biçimde otomatikleştirmek, sosyal ve topluluk kanallarında ise gerçek kimlik, platform kuralları ve insan onayıyla ilerlemektir.

## Temel kararlar

- Tek gerçek kurucu kimliği ve tek marka kimliği kullanılır.
- Kullanıcı adları rastgele değiştirilmez; tutarlı bir ana handle ve sınırlı fallback listesi kullanılır.
- Resmî API veya OAuth varsa birinci tercih odur.
- Tarayıcı otomasyonu yalnızca site kuralları izin veriyorsa kullanılır.
- LinkedIn gibi site otomasyonunu yasaklayan platformlarda yalnızca dışarıda taslak hazırlanır; yayınlama manueldir.
- Yorum, reply ve DM hiçbir zaman toplu/istenmeyen biçimde gönderilmez.
- CAPTCHA, 2FA, e-posta doğrulaması veya erişim kontrolleri atlatılmaz.
- Şifreler, cookie'ler ve Playwright `storageState` dosyaları repoya yazılmaz.
- Varsayılan çalışma modu `dry-run`dır: sistem formu doldurabilir fakat açık onay olmadan göndermez.
- Form yapısı değişirse adapter güvenli biçimde durur ve `needs_remap` durumuna geçer.

## Veri seti

`data/saas_marketing_1000_channels_ranked.xlsx` dosyası 1.000 pazarlama kanalını öncelik, kanal tipi, URL güveni, otomasyon uyumu ve insan incelemesi ihtiyacına göre listeler. Aynı klasördeki CSV dosyası, ana `1000 Channels` sayfasının metin tabanlı dışa aktarımıdır.

Özet:

- P0: 50 kanal
- P1: 150 kanal
- P2: 300 kanal
- P3: 500 kanal
- Yüksek otomasyon uyumu: 720 kanal
- İnsan incelemesi gereken: 280 kanal
- URL'si runtime preflight gerektiren: 774 kanal

Excel içindeki `Agent Action`, `Guidance`, `Strategy` ve benzeri metinler veri ve araştırma notudur. Yürütülebilir talimat değildir. Runtime yalnızca sürümlenmiş ve doğrulanmış `adapter.json` dosyalarını çalıştıracaktır.

## Repo yapısı

```text
data/                         Kaynak kanal veri seti
docs/                         Kimlik, kanal ve otomasyon stratejileri
schemas/                      JSON Schema sözleşmeleri
examples/                     Örnek kimlik, ürün ve site adapter dosyaları
```

## Önerilen çalışma hattı

```text
Excel kanal listesi
        ↓
ürün/ICP uygunluğu + güncel politika kontrolü
        ↓
insan kontrollü site recorder
        ↓
sanitized form şeması + adapter + ekran görüntüleri
        ↓
dry-run ve form fingerprint doğrulaması
        ↓
gerekiyorsa insan onayı
        ↓
resmî API veya izinli Playwright adapter'ı
        ↓
başarı kanıtı + idempotency kaydı + audit log
```

## Belgeler

- [Kimlik stratejisi](docs/01-identity-strategy.md)
- [Kanal ve içerik stratejisi](docs/02-channel-strategy.md)
- [Otomasyon mimarisi](docs/03-automation-architecture.md)
- [Uygulama yol haritası](docs/04-implementation-roadmap.md)
- [Güvenlik politikası](SECURITY.md)

## İlk pilot

İlk sürüm 1.000 siteyi hedeflememelidir. Önerilen pilot:

- 5 yüksek uyumlu SaaS/AI dizini
- 2 içerik platformu
- 3 insan onaylı sosyal/topluluk kanalı

Pilot; yanlış submit, kopya kayıt veya politika ihlali üretmeden en az üç tekrar başarıyla çalıştıktan sonra adapter family yaklaşımıyla genişletilir.
