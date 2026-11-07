# SPDX-License-Identifier: Apache-2.0
"""WP-1 routing, sensing and resonance invariants over real projections."""

from __future__ import annotations

import math
import random

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.support import Harness, seeded
from wavefunction_field.core import routing
from wavefunction_field.core.resonance import links_for, symmetric

TAGS = ["carbon", "water", "soil", "forest"]


def _field(
    n_agents: int, seed: int, successes: int = 0
) -> tuple[Harness, str, list[str]]:
    rnd = random.Random(seed)
    emitter = seeded(1000)
    h = Harness(trusted_emitters=[emitter])
    h.register(emitter, ["ops"])
    agents = []
    for i in range(n_agents):
        s = seeded(i + 1)
        h.register(
            s,
            rnd.sample(TAGS, 2),
            name=f"agent {i}",
            description=rnd.choice(["carbon ledger", "water", "soil maps"]),
        )
        agents.append(s)
    for j in range(successes):
        iid = h.emit(emitter, goal=f"job {j}", tags=[rnd.choice(TAGS)])
        h.submit(agents[rnd.randrange(n_agents)], iid)
        h.clock.advance(1000)
    iid = h.emit(emitter, goal="carbon ledger summary", tags=["carbon"])
    return h, iid, [a.agent_id for a in agents]


@settings(max_examples=40, deadline=None)
@given(st.integers(1, 25), st.integers(0, 10_000), st.integers(0, 12))
def test_INV_RT1_distribution_normalised(n: int, seed: int, succ: int) -> None:
    h, iid, _ = _field(n, seed, succ)
    r = h.svc.route(iid)
    dist = r["distribution"]
    if dist:
        assert all(v >= 0 for v in dist.values())
        assert abs(sum(dist.values()) - 1) < 1e-9
        assert abs(sum(math.sqrt(v) ** 2 for v in dist.values()) - 1) < 1e-9
        for e in r["entries"]:
            assert abs(e["psi"] ** 2 - e["p"]) < 1e-12


def test_INV_RT2_raising_trail_raises_probability() -> None:
    h, iid, agents = _field(6, 3)
    proj = h.svc.proj
    intent = proj.intents[iid]
    before = routing.route(
        proj, intent, h.clock.now_ms(), proj.default_view
    ).distribution
    target = next(a for a in sorted(before) if before[a] < 1)
    emitter = seeded(1000)
    # one qualifying PASS for target on tag carbon raises its W
    job = h.emit(emitter, goal="side job", tags=["carbon"])
    signer = next(seeded(i + 1) for i in range(6) if seeded(i + 1).agent_id == target)
    h.submit(signer, job)
    after = routing.route(
        proj, intent, h.clock.now_ms(), proj.default_view
    ).distribution
    assert after[target] > before[target]


def test_INV_RT3_exploration_slots() -> None:
    h, iid, _ = _field(20, 11, successes=15)
    r = h.svc.route(iid, k=3)
    exploit = [e for e in r["entries"] if not e["explore"]]
    explore = [e for e in r["entries"] if e["explore"]]
    assert len(exploit) == 3
    proj = h.svc.proj
    floor_pool = [
        a
        for a in r["distribution"]
        if a not in {e["agent_id"] for e in exploit}
        and all(
            proj.trail(t, a, h.clock.now_ms(), proj.default_view) == proj.floor(t, a)
            for t in ["carbon"]
        )
    ]
    assert len(explore) == min(2, len(floor_pool))
    assert not {e["agent_id"] for e in explore} & {e["agent_id"] for e in exploit}
    keys = [(-e["eta"], e["agent_id"]) for e in explore]
    assert keys == sorted(keys)


@settings(max_examples=25, deadline=None)
@given(st.integers(0, 10_000))
def test_INV_RT4_deterministic_total_order(seed: int) -> None:
    h1, iid1, _ = _field(12, seed, 5)
    h2, iid2, _ = _field(12, seed, 5)
    assert iid1 == iid2
    assert h1.svc.route(iid1) == h2.svc.route(iid2)
    r = h1.svc.route(iid1)
    exploit = [e for e in r["entries"] if not e["explore"]]
    assert exploit == sorted(exploit, key=lambda e: (-e["p"], e["agent_id"]))
    s = h1.svc.sense(agent_id=seeded(1).agent_id)
    keys = [(-x["score"], x["intent"]["intent_id"]) for x in s["hits"]]
    assert keys == sorted(keys)


def test_INV_RT5_k18_counterexample_bounded_symmetric() -> None:
    """18+ identical intents: degree <= 16, symmetric, reference ordering."""
    emitters = [seeded(500 + i) for i in range(20)]
    h = Harness()
    for e in emitters:
        h.register(e, ["carbon"])
    ids = []
    for e in emitters:
        ids.append(h.emit(e, goal="identical carbon summary goal", tags=["carbon"]))
        h.clock.advance(1)
    proj = h.svc.proj
    links = {i: proj.intents[i].links for i in ids}
    assert symmetric(links)
    assert all(len(v) <= 16 for v in links.values())
    assert all(i not in v for i, v in links.items())
    # reference: replay the rule on the recorded emit order
    degree: dict[str, int] = {}
    ref: dict[str, set[str]] = {i: set() for i in ids}
    for n, i in enumerate(ids):
        cands = [(j, 1.0) for j in ids[:n]]
        chosen = links_for(i, cands, degree, 0.6, 16)
        for j in chosen:
            ref[i].add(j)
            ref[j].add(i)
            degree[j] = degree.get(j, 0) + 1
        degree[i] = len(chosen)
    assert ref == links


@given(
    st.lists(
        st.tuples(st.text("abc", min_size=1, max_size=3), st.floats(0, 1)), max_size=40
    ),
    st.dictionaries(st.text("abc", min_size=1, max_size=3), st.integers(0, 20)),
)
def test_INV_RT5_links_for_respects_caps(
    cands: list[tuple[str, float]], degree: dict[str, int]
) -> None:
    chosen = links_for("new", cands, degree, 0.6, 16)
    assert len(chosen) <= 16
    assert "new" not in chosen
    assert all(degree.get(j, 0) < 16 for j in chosen)
    assert all(
        dict(cands).get(j, 0) >= 0.6 or any(s >= 0.6 for x, s in cands if x == j)
        for j in chosen
    )


def test_INV_RT6_one_boost_per_distinct_emitter() -> None:
    spam, honest, target = seeded(900), seeded(901), seeded(902)
    h = Harness()
    for s in (spam, honest, target):
        h.register(s, ["carbon"])
    victim = h.emit(target, goal="identical carbon summary goal", tags=["carbon"])
    for n in range(50):
        h.emit(
            spam, goal="identical carbon summary goal", tags=["carbon"], ttl_s=86400 + n
        )
    proj = h.svc.proj
    intent = proj.intents[victim]
    now = h.clock.now_ms()
    a = proj.amplitude(intent, now, proj.default_view)
    linked_spam = [j for j in intent.links if proj.intents[j].emitter == spam.agent_id]
    best = max(
        proj.amplitude(proj.intents[j], now, proj.default_view) for j in linked_spam
    )
    eff = proj.amplitude_eff(intent, now, proj.default_view)
    assert abs(eff - min(1.0, a + 0.25 * best)) < 1e-12
    assert eff <= 1.0
