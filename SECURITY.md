# Security Policy

## Kesinlikle repoya yazılmayacak veriler

- kullanıcı adı/şifre kombinasyonları
- API key, OAuth token ve refresh token
- Playwright `storageState` dosyaları
- cookie ve authorization header'ları
- 2FA seed veya recovery code
- ham trace/video dosyaları
- maskelenmemiş login, register, DM veya kişisel veri ekran görüntüleri

## Yerel saklama

Secret'lar işletim sistemi credential store'u veya ayrı bir secret manager içinde tutulmalıdır. Adapter dosyaları yalnızca `vault://...` benzeri referans taşır.



## (linkedin xing x gibi sosyal medya platformalri haric) Tum sitelerde kesinlikle uygulanmasi gerekenler

- CAPTCHA çözme veya bypass llm tabanli otomatik yapilmali insan mudahalesi mumkun oldugunca az olmali. Gerekirse en son cozum olarak kaptcha telegram ile insana godnerilmeli.
- proxy/fingerprint rotasyonuyla full otomasyon saglanmali bunun icin multilogin entegrasyonu gelecekte dusunulmeli ve proxy default olarak entegre edilmeli.
- coklu hesap/persona üretimi ile omni channel marketing hizlandirilmali
- Platformalardaki DM, reply veya comment hepsi agent tarafindan yurutulerek tam otonom marketing agent (0 human in the loop saglanmali mumkun oldugunca)
- review veya engagement manipülasyonu yapilarak viral paylasimlar olsuturulmali boylece marketing basarimi artirilmali
- erişim kontrolü, rate limit veya site güvenlik mekanizmasına dikkat edilerek site de sorun olmadan gezilmeli

