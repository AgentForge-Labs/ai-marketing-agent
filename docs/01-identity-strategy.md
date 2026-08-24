# Kimlik stratejisi

## Ana prensip

Çok sayıda sahte veya birbirinden kopuk persona yerine iki şeffaf kimlik kullanılır:

1. Kurucu: gerçek ve profesyonel kişi kimliği.
2. Marka: SaaS ürününün resmî vendor/company kimliği.

`Ertuğrul Murat` gerçek veya profesyonel olarak kullanılan isimse kurucu profillerinde görünen ad şu formatta olabilir:

```text
Ertuğrul Murat — Founder of [Ürün]
```

İsim gerçek/profesyonel kimlik değilse kullanılmamalıdır. Güven gerektiren ağlarda tam profesyonel isim tercih edilir.

## Kullanıcı adı standardı

Önerilen sıra:

1. `ertugrulmurat`
2. `ertugrulmurat_[marka]`
3. `ertugrul_[marka]`

Görünen isimde Türkçe karakter kullanılabilir. Handle için ASCII sürüm daha taşınabilirdir.

Her site için rastgele farklı kullanıcı adı üretmek önerilmez. Sadece handle müsaitliği veya site formatı nedeniyle fallback kullanılmalıdır. Gerçek kullanılan handle `identity-registry` içinde kaydedilir.

## Kanal tipine göre hesap

| Kanal | Önerilen kimlik | Not |
|---|---|---|
| LinkedIn, Reddit, X, Indie Hackers, Hacker News | Kurucu | Ürün bağlantısı ve ilişki açıkça belirtilir. |
| DEV, Medium ve teknik yayınlar | Kurucu/yazar | Deneyim ve teknik değer önce gelir. |
| SaaS/AI dizinleri | Marka/vendor | Owner veya submitter olarak kurucu kaydedilir. |
| G2/Capterra benzeri review siteleri | Marka/vendor | Yalnızca gerçek müşterilerden bağımsız inceleme istenir. |
| Marketplace ve entegrasyon mağazaları | Marka/vendor | Resmî şirket ve geliştirici hesabı kullanılır. |
| Basın ve partner iletişimi | Kurucu | Kurumsal alan adından kişisel gönderim yapılır. |

## Profil tutarlılığı

- Kurucu profillerinde aynı profesyonel fotoğraf kullanılır.
- Marka profillerinde aynı güncel logo kullanılır.
- Bio; rol, ürün, hedef kullanıcı ve doğrulanabilir ürün bağlantısını içerir.
- Kurucu ile ürün arasındaki ilişki saklanmaz.
- Disposable e-posta kullanılmaz.
- Kurucu hesapları için `ertugrul@alanadi.com`, ekip/vendor hesapları için gerekiyorsa `listings@alanadi.com` veya `partners@alanadi.com` tercih edilir.
- Ortak inbox kullanılan sitelerde hesap sahibinin ve erişimi olan ekip üyelerinin kaydı tutulur.

## Yorum, review ve DM kimliği

- Ürünün sahibi kendi ürünü için bağımsız kullanıcı gibi review yazmaz.
- Sahte kullanıcı veya müşteri hesabı açılmaz.
- Yorumlarda kurucu/ürün ilişkisi bağlam gerektiriyorsa açıklanır.
- DM yalnızca açıkça ilgili, kişiselleştirilmiş ve platform kurallarına uygun olduğunda gönderilir.
- Otomatik DM için alıcının opt-in veya açık iletişim niyeti audit kaydında bulunmalıdır.

