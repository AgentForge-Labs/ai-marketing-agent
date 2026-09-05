"""Vault abstraction — secrets never live in Git, DB plaintext, or logs.

Providers resolve `vault://...` references. Prototype uses environment
variables; production plugs HashiCorp Vault/KMS behind the same protocol.
"""
from __future__ import annotations

import os
from typing import Optional, Protocol


class VaultProvider(Protocol):
    def resolve(self, ref: str) -> Optional[str]: ...


class EnvVault:
    """Env-backed vault: vault://a/b/c -> A_B_C (+ TENANT_ prefix + suffix fallbacks)."""

    def resolve(self, ref: str) -> Optional[str]:
        if not ref.startswith("vault://"):
            return ref
        key = ref.replace("vault://", "").replace("/", "_").upper()
        for cand in (key, f"TENANT_{key}", key.replace("MAIL_", "")):
            value = os.getenv(cand)
            if value:
                return value
        return None


def resolve_secret(ref: str, provider: Optional[VaultProvider] = None) -> Optional[str]:
    return (provider or EnvVault()).resolve(ref)
