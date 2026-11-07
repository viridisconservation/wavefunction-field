# SPDX-License-Identifier: Apache-2.0
"""WP-1 property tests for canonical JSON, entropy, decay, amplitude and trails."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from wavefunction_field.core import dynamics as dyn
from wavefunction_field.core.canonical import canonical, reject_floats
from wavefunction_field.core.entropy import entropy_bits
from wavefunction_field.core.errors import WFPError

ROOT = Path(__file__).resolve().parents[2]
TV = json.loads((ROOT / "spec/test_vectors.json").read_text())

json_values = st.recursive(
    st.none() | st.booleans() | st.integers(-(2**53), 2**53) | st.text(max_size=20),
    lambda c: (
        st.lists(c, max_size=4) | st.dictionaries(st.text(max_size=8), c, max_size=4)
    ),
    max_leaves=20,
)


def _market_stable(value: object) -> str:
    """viridis-agent-market-v1 _stable()."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def test_INV_ID5_canonical_reproduces_test_vector() -> None:
    assert canonical(TV["envelope"]) == TV["canonical_ascii"]


@given(json_values)
def test_INV_ID5_canonical_matches_agent_market(value: object) -> None:
    assert canonical(value) == _market_stable(value)


@pytest.mark.parametrize(
    "bad", [1.0, {"a": [0.5]}, {"x": float("nan")}, [float("inf")]]
)
def test_INV_ID5_floats_rejected(bad: object) -> None:
    with pytest.raises(WFPError) as exc:
        reject_floats(bad)
    assert exc.value.error_type == "ValidationError"


def test_INV_DY6_entropy_test_vector() -> None:
    e = TV["entropy"]
    assert abs(entropy_bits(e["weights"]) - e["H_bits"]) < e["tolerance"]


@given(st.lists(st.integers(1, 1000), min_size=1, max_size=8))
def test_INV_DY6_entropy_bounds(weights: list[int]) -> None:
    h = entropy_bits(weights)
    assert -1e-12 <= h <= math.log2(len(weights)) + 1e-12
    assert (h == 0.0) == (len(weights) == 1)


def test_INV_DY6_entropy_zero_iff_single() -> None:
    assert entropy_bits([7]) == 0.0
    assert entropy_bits([1, 1]) == 1.0


@pytest.mark.parametrize("case", TV["decay"]["cases"])
def test_INV_DY1_decay_vectors(case: dict[str, float]) -> None:
    assert dyn.decay(case["dt_s"], case["h_s"]) == pytest.approx(
        case["value"], rel=1e-12
    )


@given(
    st.lists(
        st.tuples(st.sampled_from(["a", "b", "c", "x", "y"]), st.integers(0, 10**7)),
        max_size=30,
    ),
    st.integers(0, 10**7),
    st.integers(0, 10**8),
)
def test_INV_DY1_exact_decay_of_both_parts(
    signals: list[tuple[str, int]], t1_off: int, gap: int
) -> None:
    t_emit = 1_000_000
    sig = [(a, t_emit + ms) for a, ms in signals]
    t1 = t_emit + 10**7 + t1_off
    t2 = t1 + gap
    trusted = frozenset({"a", "b"})
    s1, u1 = dyn.amplitude_parts(0.5, t_emit, sig, trusted, t1, 86400.0, 0.05)
    s2, u2 = dyn.amplitude_parts(0.5, t_emit, sig, trusted, t2, 86400.0, 0.05)
    d = dyn.decay_ms(gap, 86400.0)
    assert s2 == pytest.approx(s1 * d, rel=1e-12, abs=1e-300)
    assert u2 == pytest.approx(u1 * d, rel=1e-12, abs=1e-300)


@given(
    st.floats(0, 10),
    st.floats(0, 100),
    st.floats(0.0, 1.0),
    st.floats(0.01, 2.0),
)
def test_INV_DY2_amplitude_bounded(
    s: float, u: float, cap: float, a_max: float
) -> None:
    a = dyn.combine_amplitude(s, u, cap, a_max)
    assert 0.0 <= a <= a_max


@given(st.integers(0, 20_000))
def test_INV_DY8_untrusted_contribution_capped(n: int) -> None:
    sig = [(f"u{i}", 0) for i in range(n)]
    s, u = dyn.amplitude_parts(0.0, 0, sig, frozenset(), 0, 86400.0, 0.05)
    assert dyn.combine_amplitude(s, u, 0.1, 1.0) <= 0.1 + 1e-15


@given(
    st.lists(st.tuples(st.booleans(), st.integers(0, 10**6)), max_size=40),
    st.sampled_from([0.0, 0.05]),
)
def test_INV_DY4_trail_bounds(stream: list[tuple[bool, int]], floor: float) -> None:
    acc = dyn.Accumulator()
    t = 0
    for ok, gap in stream:
        t += gap
        acc = acc.add(1.0 if ok else -0.5, t, 1_209_600.0)
        w = dyn.trail_weight(acc.at(t, 1_209_600.0), floor, 5.0)
        assert floor <= w <= 5.0


@given(st.floats(1e-6, 10), st.floats(0, 10), st.floats(0.0, 0.5))
def test_INV_DY1_crossing_is_first_ms_below(s: float, u: float, cap: float) -> None:
    alive = 0.01
    t = dyn.amplitude_crossing_ms(0, s, u, cap, alive, 86400.0)
    if t >= 2**62:
        return

    def amp(ms: int) -> float:
        d = dyn.decay_ms(ms, 86400.0)
        return s * d + min(cap, u * d)

    assert amp(t) < alive or t == 0
    if t > 0:
        assert amp(t - 1) >= alive * (1 - 1e-9)
