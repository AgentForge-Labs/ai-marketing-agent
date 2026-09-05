# Contributing

## Branch / test kuralı

- Her issue için `feat/<kısa-ad>` branch'i aç; bitince `main`'e `--no-ff` merge + push + branch sil (lokal + remote). Sahipsiz worktree/branch bırakma.
- Feat PR'ı SADECE `tests/test_<feat>.py` feat-scoped testleri + etkilenen hızlı regression'ı (unit/schema/policy, mock'lı) içerir ve HER PR'da koşar.
- Pahalı canlı E2E/pilot tekrarları feat'lerde KOŞULMAZ; yalnızca FINAL regression issue'sunda (#16), TÜM feat'ler kapandıktan sonra koşulur.
- Her PR öncesi yerelde: `python scripts/check_policy_contract.py` + `python -m unittest discover -s tests` + `python scripts/scan_secrets.py` yeşil olmalı.

## Vault kuralı

- Ham secret (şifre, token, API key, `storageState`, TOTP seed) ASLA repoya girmez.
- Yerel dosyalar (`C:\Users\ahmet\Downloads\DIGER\sunucular`) → `vault://` referansları; harita: `docs/05-vault-credentials-mapping.md`.
- Adapter `*.Ref` alanları `vault://` formatında zorunludur; düz-metin secret şemada reddedilir.

## Sözleşme önceliği

- Çelişkide `schemas/policy-contract.json` kazanır; drift bulursan kodu değil önce sözleşmeyi ve `scripts/check_policy_contract.py` guard'ını güncelleme teklifini issue'ya yaz.
