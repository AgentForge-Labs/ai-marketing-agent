# AI Marketing Agent

Compliance-first SaaS dağıtım ve pazarlama otomasyonu için strateji, veri seti ve adapter sözleşmeleri.

Bu repo şu an dokümantasyon ve şema aşamasındadır. Amaç, 1.000 kanala ozgun ve faydali içeriği tam otonom gönderen bir agent gelistimektir. Amaç; izinli dizin/listing işlemlerini deterministik biçimde otomatikleştirmek, sosyal kanallarda insan onayıyla ilerlemektir (zorunlu olanlarda).

## Temel kararlar

- Kesinlikle her sitede farkli kullanici adi kullanilmali , kullanici adlari mantikli ve rasgele olmali ama spma izlenimi vermemelidir
- Kullanıcı adları hangi sitede hangi kullanici adi ve sifresi ile giris yapildigi sqlite da tutulmalidir
- Resmî API veya OAuth varsa birinci tercih odur, yoksa site apisi networkden tespit edildiyse o kullanilmalidir.
- Tarayıcı otomasyonu mumkun olan heryerde uygulanarak eger mumkun 0 human in the loop full otonom gelecegin sistemi insanlik icin yapilmalidir.
- LinkedIn gibi site sitelerde banlanmamak icin paylasilacka post olsuturlmalidir o isnan tarafindan girilmelidir.
- Yorum, reply ve DM olan sistemlerde otonom ve site guvenligini tetiklemeyecek sekilde yapilmalidir spam oalrka degil.
- CAPTCHA, 2FA, e-posta doğrulaması veya erişim kontrolleri tam otonom olarka yapilmalidir.
- Şifreler, cookie'ler ve Playwright `storageState` dosyaları repoya yazılmaz.
- Varsayılan çalışma modu full otonom moddur. Sistem formu doldurup gonderiri tum islemleri insan gibi yapar amac insanin yerine gecmektir.
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
