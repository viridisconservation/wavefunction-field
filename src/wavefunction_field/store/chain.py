# SPDX-License-Identifier: Apache-2.0
"""Event hash chain (PROTOCOL §8)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from wavefunction_field.core.canonical import canonical, sha256_hex

GENESIS_PREV = "0" * 64
CORE_FIELDS = (
    "event_id",
    "type",
    "actor_id",
    "server_ms",
    "payload",
    "envelope",
    "pubkey",
    "signature",
)


def event_hash(event_without_hash: dict[str, Any]) -> str:
    body = {k: v for k, v in event_without_hash.items() if k != "hash"}
    return sha256_hex(body["prev_hash"] + canonical(body))


def seal(core: dict[str, Any], seq: int, prev_hash: str) -> dict[str, Any]:
    event = {k: core.get(k) for k in CORE_FIELDS}
    event["seq"] = seq
    event["prev_hash"] = prev_hash
    event["hash"] = event_hash(event)
    return event


def verify_chain(events: Iterable[dict[str, Any]]) -> bool:
    prev = GENESIS_PREV
    expected_seq = 1
    for event in events:
        if event.get("prev_hash") != prev or event.get("seq") != expected_seq:
            return False
        if event_hash(event) != event.get("hash"):
            return False
        prev = event["hash"]
        expected_seq += 1
    return True
