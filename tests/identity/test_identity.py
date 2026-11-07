# SPDX-License-Identifier: Apache-2.0
"""WP-2 identity invariants: derived ids, signatures, skew."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from wavefunction_field.core.canonical import canonical_bytes, sha256_hex
from wavefunction_field.core.errors import WFPError
from wavefunction_field.identity.envelope import (
    format_ms,
    parse_signed_at,
    verify_request,
)
from wavefunction_field.identity.keys import agent_id_from_b64, b64url, b64url_decode
from wavefunction_field.identity.signer import FieldSigner

ROOT = Path(__file__).resolve().parents[2]
TV = json.loads((ROOT / "spec/test_vectors.json").read_text())
SIGNER = FieldSigner.from_private_bytes(bytes.fromhex(TV["identity"]["seed_hex"]))
NOW = parse_signed_at(TV["envelope"]["signed_at"])


def _tv_request() -> dict[str, object]:
    return {
        "envelope": copy.deepcopy(TV["envelope"]),
        "pubkey": TV["identity"]["pubkey_b64url"],
        "signature": TV["signature_b64url"],
    }


def test_INV_ID1_test_vector_identity() -> None:
    assert SIGNER.public_key_b64 == TV["identity"]["pubkey_b64url"]
    assert SIGNER.agent_id == TV["identity"]["agent_id"]
    assert (
        agent_id_from_b64(TV["identity"]["pubkey_b64url"]) == TV["identity"]["agent_id"]
    )


def test_INV_ID2_test_vector_signature() -> None:
    req = SIGNER.request(
        "emit_intent",
        TV["envelope"]["body"],
        nonce=TV["envelope"]["nonce"],
        signed_at=TV["envelope"]["signed_at"],
    )
    assert req["signature"] == TV["signature_b64url"]
    assert sha256_hex(canonical_bytes(req["envelope"])) == TV["canonical_sha256"]
    assert (
        verify_request(_tv_request(), NOW, 300)["actor_id"]
        == TV["identity"]["agent_id"]
    )


def test_INV_ID1_mismatched_actor_rejected() -> None:
    other = FieldSigner.generate_ephemeral()
    req = other.request(
        "register_agent", {"name": "x", "capabilities": ["a"]}, signed_at=format_ms(NOW)
    )
    req["envelope"]["actor_id"] = SIGNER.agent_id
    with pytest.raises(WFPError) as exc:
        verify_request(req, NOW, 300)
    assert exc.value.field == "envelope.actor_id"


@settings(max_examples=300)
@given(st.data())
def test_INV_ID2_any_byte_flip_rejected(data: st.DataObject) -> None:
    req = _tv_request()
    target = data.draw(st.sampled_from(["envelope", "signature"]))
    if target == "signature":
        raw = bytearray(b64url_decode(str(req["signature"])))
        i = data.draw(st.integers(0, len(raw) - 1))
        raw[i] ^= 1 << data.draw(st.integers(0, 7))
        req["signature"] = b64url(bytes(raw))
    else:
        text = TV["canonical_ascii"]
        i = data.draw(st.integers(0, len(text) - 1))
        ch = data.draw(
            st.characters(min_codepoint=32, max_codepoint=126).filter(
                lambda c: c != text[i]
            )
        )
        mutated = text[:i] + ch + text[i + 1 :]
        try:
            env = json.loads(mutated)
        except ValueError:
            return
        if canonical_bytes(env).decode() == text:
            return
        req["envelope"] = env
    with pytest.raises(WFPError):
        verify_request(req, NOW, 300)


@pytest.mark.parametrize(
    "offset_s,ok", [(-300, True), (300, True), (-301, False), (301, False)]
)
def test_INV_ID4_skew_boundaries(offset_s: int, ok: bool) -> None:
    req = SIGNER.request(
        "register_agent", {"name": "x", "capabilities": ["a"]}, signed_at=format_ms(NOW)
    )
    now = NOW + offset_s * 1000
    if ok:
        verify_request(req, now, 300)
    else:
        with pytest.raises(WFPError) as exc:
            verify_request(req, now, 300)
        assert exc.value.error_type == "ValidationError"
