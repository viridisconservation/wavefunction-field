# SPDX-License-Identifier: Apache-2.0
"""Caller-side signer, mirroring AgentMarketSigner ergonomics."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from wavefunction_field.core.canonical import canonical_bytes
from wavefunction_field.identity.envelope import PROTOCOL
from wavefunction_field.identity.keys import agent_id_from_pubkey, b64url, public_raw


class FieldSigner:
    """Signs WFP envelopes with a caller-owned Ed25519 key. Never exposes the key."""

    __slots__ = ("_key", "agent_id", "public_key_b64")

    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self._key = private_key
        raw = public_raw(private_key)
        self.public_key_b64 = b64url(raw)
        self.agent_id = agent_id_from_pubkey(raw)

    def __repr__(self) -> str:
        return f"FieldSigner(agent_id={self.agent_id!r})"

    @classmethod
    def generate_ephemeral(cls) -> FieldSigner:
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def from_private_bytes(cls, seed: bytes) -> FieldSigner:
        return cls(Ed25519PrivateKey.from_private_bytes(seed))

    def sign_bytes(self, message: bytes) -> str:
        return b64url(self._key.sign(message))

    def request(
        self,
        action: str,
        body: dict[str, Any],
        *,
        nonce: str | None = None,
        signed_at: str | None = None,
    ) -> dict[str, Any]:
        envelope = {
            "protocol": PROTOCOL,
            "action": action,
            "actor_id": self.agent_id,
            "nonce": nonce or "nonce-" + uuid.uuid4().hex,
            "signed_at": signed_at or datetime.now(UTC).isoformat(),
            "body": body,
        }
        return {
            "envelope": envelope,
            "pubkey": self.public_key_b64,
            "signature": self.sign_bytes(canonical_bytes(envelope)),
        }
