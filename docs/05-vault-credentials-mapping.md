# Vault Credentials Mapping — `C:\Users\ahmet\Downloads\DIGER\sunucular` → `vault://`

Bu dosya **ham secret içermez**. Sadece yerel dosyaların Vault referanslarına nasıl taşınacağını tanımlar. Runner asla repodaki düz metin secret'ı okumaz; yalnızca `vault://` referansını çözer.

> Kaynak klasör: `C:\Users\ahmet\Downloads\DIGER\sunucular` (user-provided). Buradaki her dosya Vault'a import edilir, repo'ya yazılmaz. `SECURITY.md` gereği `storageState`, `password`, `apiKey`, `totp_secret` repoya commitlenmez.

## Harita

| Yerel dosya | vault:// ref | Kullanım | Not |
|---|---|---|---|
| `openai_platform.txt` | `vault://llm/openai/apiKey` | `ai-captcha-bypass` GPT-4o (`gpt-4o`) + içerik üretimi | `OPENAI_API_KEY` env olarak da enjekte edilebilir |
| `openai_platform.txt` (aynı dosya, Gemini anahtarı varsa) | `vault://llm/gemini/apiKey` | `ai-captcha-bypass` Gemini (`gemini-2.5-pro`) fallback | `GOOGLE_API_KEY` |
| `capsolver*.txt` — yoksa capsolver.com'dan alınır | `vault://captcha/capsolver/apiKey` | CapSolver `createTask` — primary solver (`CAPSOLVER_API_KEY`) | En ucuz/hızlı: $0.80/1k |
| `2captcha*.txt` — yoksa 2captcha.com'dan alınır | `vault://captcha/2captcha/apiKey` | `2captcha-python` `TwoCaptcha(apiKey)` — coverage fallback | `twocaptcha` `AsyncTwoCaptcha` için aynı |
| `cloudflare.txt` | `vault://captcha/cloudflare/apiKey` + `vault://proxy/cloudflare/waf` | Cloudflare Turnstile çözümünde gerekebilir | WAF bypass değil, token çözüm |
| `hetzner.txt` / `hostinger.txt` / `hostinger2.txt` / `netcup/*` | `vault://infra/hetzner/apiKey` vb. | VPS / domain otomasyonu değil, proxy/VPS yönetimi için | Runner'ın kendi VPS'si değil, gerekirse proxy havuzu için |
| `github_no_org_token.txt` / `netcup_git_PAT.txt` | `vault://git/github/pat` | Repo otomasyonu değil, adapter versioning için | Site adapter'ları için değil |
| `chatgpt-mcp-connector-bilgileri.md` | `vault://mcp/openai/connector` | MCP connector bilgisi | `docs/03` runner'da kullanılmaz, sadece referans |
| `mediaharvester_api_credentials.txt` | `vault://media/harvester/apiKey` | İçerik hasatı için (opsiyonel) | Adapter `valueFrom` ile kullanılmaz, sadece enrichment |
| `remote_desktop.txt` / `web-tasarimci.com_credentials.txt` | `vault://sites/<site-id>/brand/credential` | Örnek site credential'ları şablon olarak | Her site `vault://sites/<site-id>/<persona>/password` + `vault://sites/<site-id>/<persona>/inbox` |

## Import Komutu (örnek)

```bash
# 1) Vault'a aktar (1Password / HashiCorp Vault / encrypted SQLite)
vault kv put secret/llm/openai apiKey="$(cat 'C:\Users\ahmet\Downloads\DIGER\sunucular/openai_platform.txt')"
vault kv put secret/captcha/capsolver apiKey="$(cat 'C:\Users\ahmet\Downloads\DIGER\sunucular/capsolver.txt')"
vault kv put secret/captcha/2captcha apiKey="$(cat 'C:\Users\ahmet\Downloads\DIGER\sunucular/2captcha.txt')"
vault kv put secret/mouse/profile mouse_profile="$(cat profile/mouse_profile.json)"

# 2) Adapter'da kullanım (düz metin yok)
# site-adapter.json
# "capSolver": { "apiKeyRef": "vault://captcha/capsolver/apiKey" }
# "twoCaptcha": { "apiKeyRef": "vault://captcha/2captcha/apiKey" }
# "aiLmm": { "apiKeyRef": "vault://llm/openai/apiKey" }
# "biometricMouse": { "profileRef": "vault://mouse/profile/mouse_profile.json" }
```

## Doğrulama

```bash
# Vault'tan okuma testi (ham değer log'a yazılmaz)
vault kv get -field=apiKey secret/captcha/2captcha | wc -c  # >0 ise ok
```

## Güvenlik Kuralları

- `C:\Users\ahmet\Downloads\DIGER\sunucular` içindeki hiçbir dosya **repoya kopyalanmaz**, `git add` yapılmaz.
- `schemas/site-adapter.schema.json` `*.Ref` alanları `vault://` formatını zorunlu kılar (düz metin validation'da reddedilir).
- `services/biometric-mouse/profile/mouse_profile.json` ve `storageState` dosyaları `.gitignore`'da.
- Her site `C:\...\sunucular` içindeki tek bir dosya değil, **site/hesap başına ayrı vault entry** olarak izole edilir.
