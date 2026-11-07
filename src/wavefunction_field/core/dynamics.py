# SPDX-License-Identifier: Apache-2.0
"""Decay, amplitude, trails and evaporation (PROTOCOL §7.1-§7.3)."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass


def decay(dt_s: float, h_s: float) -> float:
    """2^(-dt/h)."""
    return float(2.0 ** (-dt_s / h_s))


def decay_ms(dt_ms: int, h_s: float) -> float:
    return decay(dt_ms / 1000.0, h_s)


@dataclass(frozen=True, slots=True)
class Accumulator:
    """A decayed sum stored relative to a reference time (no epoch exponents)."""

    value: float = 0.0
    t_ref_ms: int = 0

    def at(self, t_ms: int, h_s: float) -> float:
        if t_ms <= self.t_ref_ms:
            return self.value
        return self.value * decay_ms(t_ms - self.t_ref_ms, h_s)

    def add(self, amount: float, t_ms: int, h_s: float) -> Accumulator:
        base = self.at(t_ms, h_s) if t_ms >= self.t_ref_ms else self.value
        return Accumulator(base + amount, max(t_ms, self.t_ref_ms))


def amplitude_parts(
    a0: float,
    t_emit_ms: int,
    signals: Iterable[tuple[str, int]],
    trusted: frozenset[str],
    t_ms: int,
    h_s: float,
    delta: float,
) -> tuple[float, float]:
    """Return (S_trusted, U) at ``t_ms``; U is the raw pre-cap untrusted sum."""
    s_trusted = a0 * decay_ms(max(0, t_ms - t_emit_ms), h_s)
    untrusted = 0.0
    for agent, ms in signals:
        if ms > t_ms:
            continue
        contribution = delta * decay_ms(t_ms - ms, h_s)
        if agent in trusted:
            s_trusted += contribution
        else:
            untrusted += contribution
    return s_trusted, untrusted


def combine_amplitude(
    s_trusted: float, untrusted: float, cap: float, a_max: float
) -> float:
    return max(0.0, min(a_max, s_trusted + min(cap, untrusted)))


def trail_weight(raw: float, floor: float, w_max: float) -> float:
    """W = clamp(raw, floor, w_max) (MAX-MIN bounds, §7.3)."""
    return min(w_max, max(floor, raw))


def amplitude_crossing_ms(
    t_last_ms: int,
    s_trusted: float,
    untrusted: float,
    cap: float,
    a_alive: float,
    h_s: float,
) -> int:
    """First integer ms after ``t_last_ms`` at which the amplitude is below A_alive.

    Both parts decay with the same factor d, so f(d) = S d + min(cap, U d) is
    monotone; solve f(d) = A_alive piecewise, then convert d to time.
    """
    total = s_trusted + min(cap, untrusted)
    if total < a_alive:
        return t_last_ms
    d_star = a_alive / (s_trusted + untrusted) if s_trusted + untrusted > 0 else 0.0
    if untrusted * d_star > cap:
        # Cap still binding at the crossing: S d + cap = A_alive.
        if a_alive <= cap or s_trusted <= 0:
            d_star = 0.0
        else:
            d_star = (a_alive - cap) / s_trusted
    if d_star <= 0.0:
        return 2**62
    dt_s = h_s * math.log2(1.0 / d_star)
    return t_last_ms + math.floor(dt_s * 1000.0) + 1
