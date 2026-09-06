# Vendored: AgentForge-Labs/mail-bridge (private)

- Source: `https://github.com/AgentForge-Labs/mail-bridge` (private)
- Pinned commit: `b1435f3` (v1, 2026-09-06)
- Sync: copy `mail_bridge/` here on every mail-bridge release; update the pin above.
- Import path: `services/mail-bridge` is added to `sys.path` by `email_verification.py`
  (same pattern as `services/semantic-browser`), then `import mail_bridge`.
- Do NOT edit vendored code in place — fix upstream, re-vendor.
