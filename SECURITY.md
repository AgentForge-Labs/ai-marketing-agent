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

## Fail-closed davranış

Runner aşağıdaki durumlarda submit etmeden durmalıdır:

- politika kaydı yok veya süresi geçmiş
- entry URL izin verilen domain dışında
- form fingerprint değişmiş
- locator sıfır veya birden fazla öğe bulmuş
- gerekli approval kaydı yok
- opt-out/suppression eşleşmesi var
- işlem sonucu belirsiz ve aynı idempotency anahtarı daha önce kullanılmış
- CAPTCHA, 2FA veya erişim kontrolü görülmüş

## Yasaklanan yöntemler

- CAPTCHA çözme veya bypass
- proxy/fingerprint rotasyonuyla platform denetiminden kaçma
- sahte hesap/persona üretimi
- toplu ve istenmeyen DM, reply veya comment
- fake review veya engagement manipülasyonu
- erişim kontrolü, rate limit veya site güvenlik mekanizmasını aşma

