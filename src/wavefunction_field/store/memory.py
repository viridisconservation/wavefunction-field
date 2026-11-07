# SPDX-License-Identifier: Apache-2.0
"""In-memory event store for tests and simulations."""

from __future__ import annotations

import copy
from collections.abc import Iterator
from typing import Any

from wavefunction_field.store.base import IdemRecord, WriteMeta
from wavefunction_field.store.chain import GENESIS_PREV, seal


class MemoryStore:
    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []
        self._nonces: set[tuple[str, str]] = set()
        self._idem: dict[tuple[str, str], IdemRecord] = {}

    def append(
        self, cores: list[dict[str, Any]], meta: WriteMeta | None = None
    ) -> list[dict[str, Any]]:
        if meta is not None and (meta.actor_id, meta.nonce) in self._nonces:
            raise ValueError("nonce already used")
        seq, prev = self.head()
        sealed = []
        for core in cores:
            seq += 1
            event = seal(core, seq, prev)
            prev = event["hash"]
            sealed.append(event)
        self._events.extend(sealed)
        if meta is not None:
            self._nonces.add((meta.actor_id, meta.nonce))
            if (
                meta.idem_key is not None
                and meta.body_sha256 is not None
                and meta.result_json is not None
            ):
                self._idem[(meta.actor_id, meta.idem_key)] = IdemRecord(
                    meta.body_sha256, meta.result_json
                )
        return sealed

    def iter_events(self, after_seq: int = 0) -> Iterator[dict[str, Any]]:
        for event in self._events[after_seq:]:
            yield copy.deepcopy(event)

    def head(self) -> tuple[int, str]:
        if not self._events:
            return 0, GENESIS_PREV
        return self._events[-1]["seq"], self._events[-1]["hash"]

    def has_nonce(self, actor_id: str, nonce: str) -> bool:
        return (actor_id, nonce) in self._nonces

    def get_idempotent(self, actor_id: str, key: str) -> IdemRecord | None:
        return self._idem.get((actor_id, key))

    def close(self) -> None:
        return None
