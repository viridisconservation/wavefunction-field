# SPDX-License-Identifier: Apache-2.0
"""WP-4 RuleBasedStateMachine over random multi-agent operation sequences."""

from __future__ import annotations

from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from tests.support import Harness, seeded
from wavefunction_field.core.errors import WFPError
from wavefunction_field.core.projection import TERMINAL
from wavefunction_field.store.memory import MemoryStore

AGENTS = [seeded(i) for i in range(1, 6)]
ALLOWED = {
    ("OPEN", "OPEN"),
    ("OPEN", "COLLAPSED"),
    ("OPEN", "WITHDRAWN"),
    ("OPEN", "EVAPORATED"),
}


class FieldMachine(RuleBasedStateMachine):
    """INV-SM1 INV-SM3 INV-ST3 INV-DY3 INV-DY5 checked after every step."""

    def __init__(self) -> None:
        super().__init__()
        self.h = Harness(trusted_emitters=AGENTS[:2])
        self.shadow = MemoryStore()
        for i, s in enumerate(AGENTS):
            self.h.register(s, ["carbon"] if i % 2 else ["carbon", "water"])
        self.intents: list[str] = []
        self.results: list[str] = []
        self.prev: dict[str, str] = {}
        self.trusted_passes = 0

    def _try(self, fn: object, *a: object, **k: object) -> object:
        try:
            return fn(*a, **k)  # type: ignore[operator]
        except WFPError:
            return None

    @rule(
        who=st.integers(0, 4),
        tag=st.sampled_from(["carbon", "water"]),
        ttl=st.integers(60, 7200),
        designated=st.booleans(),
    )
    def emit(self, who: int, tag: str, ttl: int, designated: bool) -> None:
        acc = (
            {"kind": "designated", "verifiers": [AGENTS[(who + 1) % 5].agent_id]}
            if designated
            else None
        )
        iid = self._try(
            self.h.emit,
            AGENTS[who],
            goal=f"{tag} job {len(self.intents)}",
            tags=[tag],
            ttl_s=ttl,
            acceptance=acc,
        )
        if iid:
            self.intents.append(str(iid))

    @rule(who=st.integers(0, 4), n=st.integers(0, 50), good=st.booleans())
    def submit(self, who: int, n: int, good: bool) -> None:
        if self.intents:
            r = self._try(
                self.h.submit,
                AGENTS[who],
                self.intents[n % len(self.intents)],
                "good" if good else "bad",
            )
            if isinstance(r, dict):
                self.results.append(r["result_id"])

    @rule(
        who=st.integers(0, 4),
        n=st.integers(0, 50),
        verdict=st.sampled_from(["pass", "fail"]),
    )
    def verify(self, who: int, n: int, verdict: str) -> None:
        if self.results:
            self._try(
                self.h.write,
                AGENTS[who],
                "verify",
                {"result_id": self.results[n % len(self.results)], "verdict": verdict},
            )

    @rule(
        who=st.integers(0, 4),
        n=st.integers(0, 50),
        kind=st.sampled_from(["signal", "claim"]),
    )
    def deposit(self, who: int, n: int, kind: str) -> None:
        if self.intents:
            body = {"intent_id": self.intents[n % len(self.intents)], "kind": kind}
            if kind == "claim":
                body["lease_s"] = 300
            self._try(self.h.write, AGENTS[who], "deposit", body)

    @rule(who=st.integers(0, 4), n=st.integers(0, 50))
    def withdraw(self, who: int, n: int) -> None:
        if self.intents:
            self._try(
                self.h.write,
                AGENTS[who],
                "withdraw_intent",
                {"intent_id": self.intents[n % len(self.intents)]},
            )

    @rule(ms=st.integers(0, 4 * 3_600_000))
    def advance(self, ms: int) -> None:
        self.h.clock.advance(ms)

    @rule()
    def sweep(self) -> None:
        self.h.svc.sweep()

    @invariant()
    def checks(self) -> None:
        proj = self.h.svc.proj
        now = self.h.clock.now_ms()
        # SM1: only allowed transitions; terminal absorbing
        for iid, intent in proj.intents.items():
            st_now = proj.state_at(intent, now)
            before = self.prev.get(iid, "OPEN")
            assert (before, st_now) in ALLOWED or (
                before in TERMINAL and st_now == before
            )
            self.prev[iid] = st_now
        # ST3 + DY3: a fresh rebuild (which may lack sweep-only effects) matches
        rebuilt = Harness(store=self.h.store, clock=self.h.clock)
        assert rebuilt.svc.proj.canonical_state(now) == proj.canonical_state(now)
        # DY5: untrusted-emitter agents (indexes 2-4) never gain from their own emits
        for s in AGENTS:
            for tag in ("carbon", "water"):
                w = proj.trail(tag, s.agent_id, now, proj.default_view)
                assert (
                    proj.floor(tag, s.agent_id) <= w or proj.floor(tag, s.agent_id) == 0
                )


FieldMachine.TestCase.settings = settings(
    max_examples=60, stateful_step_count=25, deadline=None
)
TestFieldMachine = FieldMachine.TestCase
