# SPDX-License-Identifier: Apache-2.0
"""WP-4 FieldService invariants and the end-to-end story."""

from __future__ import annotations

import pytest

from tests.support import PARAMS, Harness, seeded, sha
from wavefunction_field.core.errors import WFPError


def _err(fn: object, *args: object, **kw: object) -> WFPError:
    with pytest.raises(WFPError) as exc:
        fn(*args, **kw)  # type: ignore[operator]
    return exc.value


@pytest.mark.parametrize("emitter_trusted", [False, True])
def test_end_to_end_story(emitter_trusted: bool) -> None:
    a, b = seeded(1), seeded(2)
    h = Harness(trusted_emitters=[a] if emitter_trusted else [])
    h.register(a, ["ops"])
    h.register(b, ["carbon"])
    iid = h.emit(a, tags=["carbon"])
    sensed = h.svc.sense(agent_id=b.agent_id)["hits"]
    assert sensed and sensed[0]["intent"]["intent_id"] == iid
    h.write(b, "deposit", {"intent_id": iid, "kind": "claim", "lease_s": 600})
    proj = h.svc.proj
    now = h.clock.now_ms
    floor = proj.floor("carbon", b.agent_id)
    bad = h.submit(b, iid, content="bad")
    assert bad["state"] == "FAILED" and h.svc.get_intent(iid)["state"] == "OPEN"
    assert proj.trail("carbon", b.agent_id, now(), proj.default_view) == floor
    good = h.submit(b, iid, content="good")
    assert good["intent_state"] == "COLLAPSED"
    w = proj.trail("carbon", b.agent_id, now(), proj.default_view)
    assert (w > floor) is emitter_trusted


def test_INV_ID6_idempotency() -> None:
    a = seeded(1)
    h = Harness()
    h.register(a, ["ops"])
    body = {
        "goal": "g",
        "hypotheses": [{"id": "h1", "summary": "s", "weight": 1}],
        "acceptance": {"kind": "digest", "sha256": sha("x")},
        "priority": 3,
        "ttl_s": 3600,
        "idempotency_key": "job-1",
    }
    first = h.write(a, "emit_intent", body)
    n = h.store.head()[0]
    req = h.req(a, "emit_intent", body)
    assert h.svc.apply(req) == first  # new nonce
    assert h.svc.apply(req) == first  # replayed nonce, same body
    assert h.store.head()[0] == n
    changed = dict(body, goal="different")
    assert _err(h.write, a, "emit_intent", changed).message == "idempotency_conflict"
    assert h.store.head()[0] == n


def test_INV_DY3_sweep_equivalence() -> None:
    def run(sweep: bool) -> tuple[str, dict[str, object], dict[str, object]]:
        a, b = seeded(1), seeded(2)
        h = Harness(trusted_emitters=[a])
        h.register(a, ["ops"])
        h.register(b, ["carbon"])
        ids = [
            h.emit(a, goal=f"g{i}", tags=["carbon"], ttl_s=600 + i) for i in range(4)
        ]
        designated = h.emit(
            a,
            goal="review me",
            tags=["carbon"],
            ttl_s=3600,
            acceptance={"kind": "designated", "verifiers": [a.agent_id]},
        )
        h.submit(b, designated)
        h.write(b, "deposit", {"intent_id": ids[0], "kind": "signal"})
        h.clock.advance(5 * 86_400_000)
        if sweep:
            assert h.svc.sweep() >= 1
        now = h.clock.now_ms()
        sense = h.svc.sense(agent_id=b.agent_id)
        return h.svc.proj.canonical_state(now), h.svc.metrics(), sense

    s1, m1, k1 = run(False)
    s2, m2, k2 = run(True)
    assert s1 == s2 and m1 == m2 and k1 == k2


def test_INV_DY5_only_qualifying_verifications_move_trails() -> None:
    emitter, doer, sybil_v, untrusted = seeded(1), seeded(2), seeded(3), seeded(4)
    h = Harness(trusted_emitters=[emitter])
    for s, caps in (
        (emitter, ["ops"]),
        (doer, ["carbon"]),
        (sybil_v, ["ops"]),
        (untrusted, ["ops"]),
    ):
        h.register(s, caps)
    proj = h.svc.proj
    # self-dealing: emitter does its own job (machine verified)
    iid = h.emit(emitter, tags=["carbon"])
    h.submit(emitter, iid)
    # untrusted emitter's job verified by the field
    iid = h.emit(untrusted, tags=["carbon"])
    h.submit(doer, iid)
    # trusted emitter, designated sybil verifier not in the view
    iid = h.emit(
        emitter,
        tags=["carbon"],
        acceptance={"kind": "designated", "verifiers": [sybil_v.agent_id]},
    )
    res = h.submit(doer, iid)
    h.write(sybil_v, "verify", {"result_id": res["result_id"], "verdict": "pass"})
    now = h.clock.now_ms()
    for s in (emitter, doer, sybil_v, untrusted):
        assert proj.trail("carbon", s.agent_id, now, proj.default_view) == proj.floor(
            "carbon", s.agent_id
        )
    # a qualifying pass does move it
    iid = h.emit(emitter, tags=["carbon"])
    h.submit(doer, iid)
    assert proj.trail("carbon", doer.agent_id, now, proj.default_view) > proj.floor(
        "carbon", doer.agent_id
    )


def test_INV_RT7_revoked_field_key_emitter_and_terminal_excluded() -> None:
    a, b, c = seeded(1), seeded(2), seeded(3)
    h = Harness()
    for s in (a, b, c):
        h.register(s, ["carbon"])
    iid = h.emit(a, tags=["carbon"])
    h.write(c, "revoke_agent", {"agent_id": c.agent_id})
    dist = h.svc.route(iid)["distribution"]
    assert (
        a.agent_id not in dist
        and c.agent_id not in dist
        and h.field.agent_id not in dist
    )
    assert b.agent_id in dist
    h.write(a, "withdraw_intent", {"intent_id": iid})
    assert not h.svc.sense(agent_id=b.agent_id)["hits"]
    field_req = h.field.request(
        "emit_intent", {}, signed_at=h.req(a, "x", {})["envelope"]["signed_at"]
    )
    assert _err(h.svc.apply, field_req).error_type == "PermissionError"


def test_INV_SM1_terminal_states_absorb() -> None:
    a, b = seeded(1), seeded(2)
    h = Harness()
    h.register(a, ["ops"])
    h.register(b, ["carbon"])
    iid = h.emit(a)
    h.write(a, "withdraw_intent", {"intent_id": iid})
    for action, body in (
        ("deposit", {"intent_id": iid, "kind": "signal"}),
        ("withdraw_intent", {"intent_id": iid}),
        ("reweight", {"intent_id": iid, "weights": {"h1": 2}}),
    ):
        assert (
            _err(h.write, a if action != "deposit" else b, action, body).error_type
            == "ContextError"
        )
    assert _err(h.submit, b, iid).error_type == "ContextError"
    assert h.svc.get_intent(iid)["state"] == "WITHDRAWN"


def test_INV_SM2_collapse_once() -> None:
    a, b, c = seeded(1), seeded(2), seeded(3)
    h = Harness()
    for s in (a, b, c):
        h.register(s, ["carbon"])
    iid = h.emit(a, acceptance={"kind": "designated", "verifiers": [a.agent_id]})
    r1, r2 = h.submit(b, iid), h.submit(c, iid)
    h.write(a, "verify", {"result_id": r1["result_id"], "verdict": "pass"})
    assert h.svc.get_intent(iid)["collapsed_result"] == r1["result_id"]
    assert (
        _err(
            h.write, a, "verify", {"result_id": r2["result_id"], "verdict": "pass"}
        ).error_type
        == "ContextError"
    )
    assert _err(h.submit, c, iid, "other").error_type == "ContextError"
    states = {r["result_id"]: r["state"] for r in h.svc.get_intent(iid)["results"]}
    assert states == {r1["result_id"]: "PASSED", r2["result_id"]: "VOID"}


def test_INV_SM3_isolated_transitions() -> None:
    a, b = seeded(1), seeded(2)
    h = Harness()
    h.register(a, ["carbon"])
    h.register(b, ["carbon"])
    parent = h.emit(a, goal="identical carbon summary goal")
    child = h.emit(a, goal="identical carbon summary goal", parent_intent_id=parent)
    twin = h.emit(b, goal="identical carbon summary goal")
    assert twin in h.svc.proj.intents[parent].links
    now = h.clock.now_ms
    before = {
        i: h.svc.proj.intent_view(h.svc.proj.intents[i], now()) for i in (child, twin)
    }
    h.submit(b, parent)
    after = {
        i: h.svc.proj.intent_view(h.svc.proj.intents[i], now()) for i in (child, twin)
    }
    assert before == after
    assert h.svc.get_intent(parent)["state"] == "COLLAPSED"


def test_INV_SM5_leases_advisory_and_expiring() -> None:
    a, b, c = seeded(1), seeded(2), seeded(3)
    h = Harness()
    for s in (a, b, c):
        h.register(s, ["carbon"])
    iid = h.emit(a)
    h.write(b, "deposit", {"intent_id": iid, "kind": "claim", "lease_s": 60})
    h.write(b, "deposit", {"intent_id": iid, "kind": "claim", "lease_s": 120})
    assert list(h.svc.get_intent(iid)["leases"]) == [b.agent_id]
    assert (
        _err(
            h.write,
            b,
            "deposit",
            {"intent_id": iid, "kind": "claim", "lease_s": PARAMS.lease_max_s + 1},
        ).error_type
        == "ValidationError"
    )
    hit = h.svc.sense(agent_id=c.agent_id)["hits"][0]
    assert hit["leased_by_other"]
    h.clock.advance(121_000)
    assert not h.svc.sense(agent_id=c.agent_id)["hits"][0]["leased_by_other"]
    h.write(b, "deposit", {"intent_id": iid, "kind": "claim", "lease_s": 600})
    assert h.submit(c, iid)["intent_state"] == "COLLAPSED"


def test_INV_SM6_subintent_depth_and_parent_state() -> None:
    a = seeded(1)
    h = Harness()
    h.register(a, ["ops"])
    chain = [h.emit(a, goal="root")]
    for d in range(4):
        chain.append(h.emit(a, goal=f"depth {d + 1}", parent_intent_id=chain[-1]))
    assert (
        _err(h.emit, a, goal="too deep", parent_intent_id=chain[-1]).constraint
        == "max_depth"
    )
    h.write(a, "withdraw_intent", {"intent_id": chain[0]})
    assert (
        _err(h.emit, a, goal="orphan", parent_intent_id=chain[0]).error_type
        == "ContextError"
    )


def test_INV_ST3_rebuild_equals_live() -> None:
    a, b = seeded(1), seeded(2)
    h = Harness(trusted_emitters=[a])
    h.register(a, ["ops"])
    h.register(b, ["carbon"])
    for i in range(6):
        iid = h.emit(a, goal=f"g{i}")
        h.write(b, "deposit", {"intent_id": iid, "kind": "signal"})
        h.submit(b, iid, content="good" if i % 2 else "bad")
        h.clock.advance(3_600_000)
    now = h.clock.now_ms()
    rebuilt = Harness(store=h.store, clock=h.clock)
    assert rebuilt.svc.proj.canonical_state(now) == h.svc.proj.canonical_state(now)


@pytest.mark.parametrize("text", ["evil‮txt.exe", "a\x00b\x1bc\x9f", "x⁦y⁩"])
def test_INV_SF2_controls_stripped(text: str) -> None:
    a = seeded(1)
    h = Harness()
    h.register(a, ["ops"])
    iid = h.emit(a, goal=text)
    stored = h.svc.proj.intents[iid].goal
    assert all(ord(ch) >= 0x20 or ch in "\n\t" for ch in stored)
    assert not any(
        0x202A <= ord(ch) <= 0x202E
        or 0x2066 <= ord(ch) <= 0x2069
        or 0x80 <= ord(ch) <= 0x9F
        for ch in stored
    )


def test_INV_SF2_overlength_rejected_not_truncated() -> None:
    a = seeded(1)
    h = Harness()
    h.register(a, ["ops"])
    err = _err(h.emit, a, goal="x" * (PARAMS.limits["goal_chars"] + 1))
    assert err.constraint == "max_length"


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://localhost/x",
        "https://10.0.0.1/",
        "https://[::1]/",
        "https://printer.local/",
        "https://169.254.1.1/",
        "https://user:pw@example.com/",
    ],
)
def test_INV_SF3_bad_urls_rejected(url: str) -> None:
    a = seeded(1)
    h = Harness()
    err = _err(
        h.write,
        a,
        "register_agent",
        {"name": "a", "capabilities": ["x"], "links": {"mcp": url}},
    )
    assert err.error_type == "ValidationError"


def test_INV_SF3_urls_never_fetched(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    calls: list[object] = []
    monkeypatch.setattr(httpx.Client, "send", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(httpx.AsyncClient, "send", lambda *a, **k: calls.append(a))
    a, b = seeded(1), seeded(2)
    h = Harness()
    h.register(a, ["ops"])
    h.write(
        b,
        "register_agent",
        {
            "name": "b",
            "capabilities": ["x"],
            "links": {"mcp": "https://example.com/mcp"},
        },
    )
    iid = h.emit(a)
    h.write(
        b,
        "submit_result",
        {
            "intent_id": iid,
            "hypothesis_id": "h1",
            "cost_report": {"tokens": 1, "wall_ms": 1},
            "artifact": {
                "content_type": "x",
                "sha256": sha("good"),
                "uri": "https://example.com/r",
            },
        },
    )
    assert calls == []


def test_INV_SF5_quotas() -> None:
    a, b = seeded(1), seeded(2)
    h = Harness()
    h.register(a, ["ops"])
    h.register(b, ["carbon"])
    iid = h.emit(a)
    for i in range(PARAMS.limits["results_per_intent_per_doer"]):
        h.submit(b, iid, content=f"bad{i}")
    n = h.store.head()[0]
    assert _err(h.submit, b, iid, "bad-x").error_type == "BudgetError"
    assert h.store.head()[0] == n
    h.clock.advance(61_000)
    c = seeded(3)
    h.register(c, ["ops"])
    for i in range(
        PARAMS.limits["writes_per_minute"] - 1
    ):  # registration counts as a write
        h.write(
            c,
            "deposit",
            {"intent_id": iid, "kind": "hypothesis", "summary": f"idea {i}"},
        )
    assert (
        _err(h.write, c, "deposit", {"intent_id": iid, "kind": "signal"}).error_type
        == "BudgetError"
    )
    h.clock.advance(61_000)
    h.write(c, "deposit", {"intent_id": iid, "kind": "signal"})


def test_INV_SF5_open_intent_quota() -> None:
    a = seeded(1)
    h = Harness()
    h.register(a, ["ops"])
    for i in range(PARAMS.limits["open_intents_per_emitter"]):
        h.emit(a, goal=f"g{i}")
        if i % 50 == 49:
            h.clock.advance(61_000)
    assert _err(h.emit, a, goal="one more").error_type == "BudgetError"
