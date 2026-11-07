# SPDX-License-Identifier: Apache-2.0
"""WP-9 fleet contract adapter and rail adapters (fakes only, no network)."""

from __future__ import annotations

import math
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.support import Harness, seeded
from wavefunction_field.fleet.adapters.compute_ledger import ComputeLedgerSink
from wavefunction_field.fleet.adapters.identity_registry import IdentityRegistrySource
from wavefunction_field.fleet.adapters.trust_oracle import TrustOracleSource
from wavefunction_field.fleet.agent import WavefunctionSearchAgent

pytestmark = pytest.mark.anyio
TAXONOMY = {
    "PermissionError",
    "ValidationError",
    "BudgetError",
    "ContextError",
    "BackendError",
    "RuntimeError",
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeRail:
    def __init__(self, table: dict[tuple[str, str], dict[str, Any]]) -> None:
        self.table = table
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def __call__(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((action, payload))
        return self.table.get(
            (action, str(payload.get("agent_id"))), {"recorded": True}
        )


def _field() -> tuple[Harness, str, list[Any]]:
    e = seeded(1)
    workers = [seeded(i) for i in range(2, 6)]
    h = Harness(trusted_emitters=[e])
    h.register(e, ["ops"])
    for w in workers:
        h.register(w, ["carbon"])
    return h, h.emit(e), workers


@settings(max_examples=100, deadline=None)
@given(
    st.one_of(
        st.none(),
        st.integers(),
        st.text(),
        st.dictionaries(st.text(max_size=8), st.text(max_size=8) | st.integers()),
    )
)
async def test_INV_FL1_process_never_raises(payload: Any) -> None:
    h, _, _ = _field()
    out = await WavefunctionSearchAgent(h.svc).process(payload)
    assert out["ok"] in (True, False)
    assert out["status"] == ("ok" if out["ok"] else "error")
    if not out["ok"]:
        assert out["error"]["error_type"] in TAXONOMY


async def test_INV_FL2_metadata_and_full_distribution() -> None:
    h, iid, _ = _field()
    agent = WavefunctionSearchAgent(h.svc, session_id="sess_test")
    for req in (
        {"action": "field_info"},
        {"action": "route", "intent_id": iid},
        {"action": "bogus"},
    ):
        out = await agent.process(req)
        assert out["session_id"] == "sess_test" and "calls" in out["budget_consumed"]
    out = await agent.process({"action": "route", "intent_id": iid})
    dist, amps = out["result"]["distribution"], out["result"]["amplitudes"]
    assert (
        abs(sum(dist.values()) - 1) < 1e-9
        and abs(sum(a * a for a in amps.values()) - 1) < 1e-9
    )
    assert (await agent.health())["status"] == "ok" and agent.describe()[
        "name"
    ] == "wavefunction-search-agent"


async def test_INV_FL3_adapters_disabled_without_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "WF_TRUST_ORACLE_URL",
        "WF_IDENTITY_REGISTRY_URL",
        "WF_COMPUTE_LEDGER_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    assert TrustOracleSource.from_env() is None
    assert IdentityRegistrySource.from_env() is None
    assert ComputeLedgerSink.from_env() is None
    h, iid, _ = _field()
    out = await WavefunctionSearchAgent(h.svc).process(
        {"action": "route", "intent_id": iid}
    )
    assert out["ok"]


async def test_INV_FL4_identity_mismatch_excluded() -> None:
    h, iid, workers = _field()
    table = {
        ("resolve", w.agent_id): {
            "registration": {"pubkey": w.public_key_b64, "status": "ACTIVE"}
        }
        for w in workers[:2]
    }
    table[("resolve", workers[2].agent_id)] = {
        "registration": {"pubkey": "different", "status": "ACTIVE"}
    }
    rail = FakeRail(table)  # workers[3] missing entirely
    agent = WavefunctionSearchAgent(h.svc, identity=IdentityRegistrySource(rail))
    out = await agent.process({"action": "route", "intent_id": iid})
    dist = out["result"]["distribution"]
    assert set(dist) == {workers[0].agent_id, workers[1].agent_id}
    assert math.isclose(sum(dist.values()), 1.0)
    assert all(e["agent_id"] in dist for e in out["result"]["entries"])


async def test_trust_oracle_and_ledger_adapters_with_fakes() -> None:
    a, b = seeded(1), seeded(2)
    rail = FakeRail(
        {("score", a.agent_id): {"score": 0.9}, ("score", b.agent_id): {"score": 0.5}}
    )
    assert await TrustOracleSource(rail).trusted([a.agent_id, b.agent_id]) == [
        a.agent_id
    ]
    h, iid, workers = _field()
    ledger_rail = FakeRail({})
    agent = WavefunctionSearchAgent(h.svc, ledger=ComputeLedgerSink(ledger_rail))
    req = h.req(
        workers[0],
        "submit_result",
        {
            "intent_id": iid,
            "hypothesis_id": "h1",
            "cost_report": {"tokens": 7, "wall_ms": 1},
            "artifact": {
                "content_type": "text/plain",
                "inline": "good",
                "sha256": "770e607624d689265ca6c44884d0807d9b054d23c473c106c72be9de08b7376c",
            },
        },
    )
    out = await agent.process({"action": "write", "request": req})
    assert out["ok"] and out["result"]["intent_state"] == "COLLAPSED"
    assert (
        ledger_rail.calls[0][0] == "record_work"
        and ledger_rail.calls[0][1]["tokens"] == 7
    )
