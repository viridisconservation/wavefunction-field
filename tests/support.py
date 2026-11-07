# SPDX-License-Identifier: Apache-2.0
"""Shared builders for service-level tests."""

from __future__ import annotations

import hashlib
import itertools
from typing import Any

from wavefunction_field.identity.envelope import format_ms
from wavefunction_field.identity.signer import FieldSigner
from wavefunction_field.service.clock import FakeClock
from wavefunction_field.service.config import load_params
from wavefunction_field.service.field import FieldService
from wavefunction_field.store.memory import MemoryStore

PARAMS = load_params()


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def seeded(n: int) -> FieldSigner:
    return FieldSigner.from_private_bytes(
        hashlib.sha256(f"agent-{n}".encode()).digest()
    )


class Harness:
    def __init__(
        self,
        *,
        trusted_emitters: list[FieldSigner] | None = None,
        store: Any = None,
        clock: FakeClock | None = None,
        params: Any = None,
        field: FieldSigner | None = None,
        operators: list[FieldSigner] | None = None,
    ) -> None:
        self._n = itertools.count(1)
        self.clock = clock or FakeClock()
        self.store = store or MemoryStore()
        self.field = field or seeded(0)
        self.svc = FieldService(
            self.store,
            params or PARAMS,
            self.clock,
            self.field,
            trusted_emitters=[s.agent_id for s in trusted_emitters or []],
            operators=[s.agent_id for s in operators or []],
        )

    def req(
        self,
        signer: FieldSigner,
        action: str,
        body: dict[str, Any],
        nonce: str | None = None,
    ) -> dict[str, Any]:
        return signer.request(
            action,
            body,
            nonce=nonce or f"nonce-{next(self._n):08d}",
            signed_at=format_ms(self.clock.now_ms()),
        )

    def write(
        self,
        signer: FieldSigner,
        action: str,
        body: dict[str, Any],
        nonce: str | None = None,
    ) -> dict[str, Any]:
        return self.svc.apply(self.req(signer, action, body, nonce))

    def register(
        self,
        signer: FieldSigner,
        caps: list[str],
        name: str = "agent",
        description: str = "",
    ) -> None:
        self.write(
            signer,
            "register_agent",
            {"name": name, "capabilities": caps, "description": description},
        )

    def emit(
        self,
        signer: FieldSigner,
        goal: str = "summarise carbon data",
        tags: list[str] | None = None,
        acceptance: dict[str, Any] | None = None,
        **extra: Any,
    ) -> str:
        body: dict[str, Any] = {
            "goal": goal,
            "hypotheses": [{"id": "h1", "summary": "do it directly", "weight": 1}],
            "acceptance": acceptance or {"kind": "digest", "sha256": sha("good")},
            "priority": 5,
            "ttl_s": 86400,
            "capabilities_needed": ["carbon"] if tags is None else tags,
        }
        body.update(extra)
        return str(self.write(signer, "emit_intent", body)["intent_id"])

    def submit(
        self,
        signer: FieldSigner,
        intent_id: str,
        content: str = "good",
        tokens: int = 100,
    ) -> dict[str, Any]:
        return self.write(
            signer,
            "submit_result",
            {
                "intent_id": intent_id,
                "hypothesis_id": "h1",
                "artifact": {
                    "content_type": "text/plain",
                    "sha256": sha(content),
                    "inline": content,
                },
                "cost_report": {"tokens": tokens, "wall_ms": 10},
            },
        )
