# SPDX-License-Identifier: Apache-2.0
"""Event store interface (PROTOCOL §8)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class IdemRecord:
    body_sha256: str
    result_json: str


@dataclass(frozen=True, slots=True)
class WriteMeta:
    """Nonce and optional idempotency record committed with the events."""

    actor_id: str
    nonce: str
    idem_key: str | None = None
    body_sha256: str | None = None
    result_json: str | None = None


class EventStore(Protocol):
    def append(
        self, cores: list[dict[str, Any]], meta: WriteMeta | None = None
    ) -> list[dict[str, Any]]:
        """Append events (and the nonce/idempotency record) in one transaction."""
        ...

    def iter_events(self, after_seq: int = 0) -> Iterator[dict[str, Any]]: ...

    def head(self) -> tuple[int, str]: ...

    def has_nonce(self, actor_id: str, nonce: str) -> bool: ...

    def get_idempotent(self, actor_id: str, key: str) -> IdemRecord | None: ...

    def close(self) -> None: ...
