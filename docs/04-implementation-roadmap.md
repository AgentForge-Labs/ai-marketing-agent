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

## Ölçekleme kuralı

Yeni site sayısı hedef değildir. Aşağıdakiler ölçülmeden P2/P3 long-tail kanallara geçilmez:

- başarılı yayın oranı
- kabul/indexlenme oranı
- referral trafik
- signup/demo dönüşümü
- kanal başına insan zamanı
- politika ve hesap riski

