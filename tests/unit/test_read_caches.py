# SPDX-License-Identifier: Apache-2.0
"""Projection read caches are pure memoisation (0.1.0a2).

C1  amplitude and evaporation reads equal a cache-free recomputation
C2  any applied event invalidates both caches (a signal at the same instant is visible)
"""

from __future__ import annotations

from tests.support import Harness, seeded
from wavefunction_field.core import dynamics as dyn


def _fresh_amp(h: Harness, iid: str, t: int) -> float:
    proj = h.svc.proj
    intent = proj.intents[iid]
    s, u = proj.amplitude_parts(intent, t, proj.default_view)
    return dyn.combine_amplitude(s, u, proj.p.untrusted_signal_cap, proj.p.A_max)


def test_c1_c2_caches_match_recomputation_and_invalidate() -> None:
    emitter, other = seeded(1), seeded(2)
    h = Harness(trusted_emitters=[emitter])
    h.register(emitter, ["carbon"])
    h.register(other, ["carbon"])
    out = h.write(
        emitter,
        "emit_intent",
        {
            "goal": "compute scope 1",
            "hypotheses": [{"id": "h1", "summary": "s", "weight": 1}],
            "acceptance": {"kind": "digest", "sha256": "0" * 64},
            "priority": 3,
            "ttl_s": 2592000,
            "capabilities_needed": ["carbon"],
        },
    )
    iid = out["intent_id"]
    proj = h.svc.proj
    t = h.clock.now_ms()
    before = proj.amplitude(proj.intents[iid], t, proj.default_view)
    assert before == _fresh_amp(h, iid, t)
    evap_before = proj.evaporation_ms(proj.intents[iid])
    assert evap_before == proj._evaporation_ms(proj.intents[iid])
    h.write(other, "deposit", {"intent_id": iid, "kind": "signal"})
    after = proj.amplitude(proj.intents[iid], t, proj.default_view)
    assert after == _fresh_amp(h, iid, t) and after > before
    assert proj.evaporation_ms(proj.intents[iid]) == proj._evaporation_ms(
        proj.intents[iid]
    )
    assert proj.evaporation_ms(proj.intents[iid]) > evap_before
