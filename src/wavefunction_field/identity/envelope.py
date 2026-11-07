# SPDX-License-Identifier: Apache-2.0
"""Signed-write envelopes (PROTOCOL §2.1-§2.2 rules 1-4)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from cryptography.exceptions import InvalidSignature

from wavefunction_field.core.canonical import canonical_bytes
from wavefunction_field.core.errors import validation
from wavefunction_field.identity.keys import (
    agent_id_from_b64,
    b64url_decode,
    load_public,
)

PROTOCOL = "wavefunction-field-v1"
NONCE_RE = re.compile(r"^[A-Za-z0-9._:-]{8,160}$")
ENVELOPE_KEYS = {"protocol", "action", "actor_id", "nonce", "signed_at", "body"}


def parse_signed_at(value: str) -> int:
    """RFC 3339 UTC timestamp (+00:00 or Z) to epoch milliseconds."""
    if not isinstance(value, str) or not (
        value.endswith("Z") or value.endswith("+00:00")
    ):
        raise validation("signed_at must be RFC 3339 UTC", "envelope.signed_at")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise validation(
            "signed_at must be RFC 3339 UTC", "envelope.signed_at"
        ) from None
    if dt.tzinfo is None or dt.utcoffset() != UTC.utcoffset(None):
        raise validation("signed_at must be UTC", "envelope.signed_at")
    return int(dt.timestamp() * 1000)


def format_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).isoformat()


def verify_request(request: Any, now_ms: int, skew_s: int) -> dict[str, Any]:
    """Apply rules 1-4 and return the envelope. Raises ValidationError/PermissionError."""
    if not isinstance(request, dict):
        raise validation("request must be an object", "request")
    for key in ("envelope", "pubkey", "signature"):
        if key not in request:
            raise validation(f"missing {key}", key)
    env = request["envelope"]
    if not isinstance(env, dict) or set(env) != ENVELOPE_KEYS:
        raise validation(
            "envelope must have exactly " + ", ".join(sorted(ENVELOPE_KEYS)), "envelope"
        )
    if env["protocol"] != PROTOCOL:
        raise validation("unsupported protocol", "envelope.protocol")
    pub, sig = request["pubkey"], request["signature"]
    if not isinstance(pub, str) or not isinstance(sig, str):
        raise validation("pubkey and signature must be base64url strings", "pubkey")
    try:
        actor = agent_id_from_b64(pub)
        public = load_public(pub)
        signature = b64url_decode(sig)
    except (ValueError, TypeError):
        raise validation("malformed pubkey or signature", "pubkey") from None
    if env["actor_id"] != actor:
        raise validation(
            "actor_id does not match pubkey", "envelope.actor_id", "derived_id"
        )
    try:
        message = canonical_bytes(env)
    except (TypeError, ValueError):
        raise validation("envelope is not canonical JSON", "envelope") from None
    try:
        public.verify(signature, message)
    except InvalidSignature:
        raise validation("signature does not verify", "signature", "ed25519") from None
    signed = parse_signed_at(env["signed_at"])
    if abs(signed - now_ms) > skew_s * 1000:
        raise validation(
            "signed_at outside the allowed clock skew", "envelope.signed_at", "skew"
        )
    if not isinstance(env["nonce"], str) or not NONCE_RE.match(env["nonce"]):
        raise validation("invalid nonce", "envelope.nonce", "pattern")
    if not isinstance(env["action"], str):
        raise validation("invalid action", "envelope.action")
    return env
