# SPDX-License-Identifier: Apache-2.0
"""Ed25519 keys and pubkey-derived agent ids (PROTOCOL §1.1)."""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def agent_id_from_pubkey(pubkey_raw: bytes) -> str:
    digest = hashlib.sha256(pubkey_raw).digest()[:16]
    return "wf1_" + base64.b32encode(digest).decode("ascii").lower().rstrip("=")


def agent_id_from_b64(pubkey_b64: str) -> str:
    return agent_id_from_pubkey(b64url_decode(pubkey_b64))


def public_raw(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )


def private_raw(key: Ed25519PrivateKey) -> bytes:
    return key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )


def load_public(pubkey_b64: str) -> Ed25519PublicKey:
    raw = b64url_decode(pubkey_b64)
    if len(raw) != 32:
        raise ValueError("Ed25519 public keys are 32 bytes")
    return Ed25519PublicKey.from_public_bytes(raw)


def load_or_create_key(path: Path) -> Ed25519PrivateKey:
    """Load a raw 32-byte seed file, creating it atomically with mode 0600."""
    path = Path(path)
    if path.exists():
        seed = path.read_bytes()
        if len(seed) != 32:
            raise ValueError("key file must contain a raw 32-byte Ed25519 seed")
        return Ed25519PrivateKey.from_private_bytes(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, private_raw(key))
    finally:
        os.close(fd)
    os.replace(tmp, path)
    os.chmod(path, 0o600)
    return key
