# SPDX-License-Identifier: Apache-2.0
"""Routing (who should do intent i?) and sensing (what should agent a do?).

PROTOCOL §7.5-§7.6. Pure functions of a Projection, a time and a view.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from wavefunction_field.core.projection import STAR, Intent, Projection
from wavefunction_field.core.similarity import LexicalSimilarity, TextProfile
from wavefunction_field.core.views import TrustView


@dataclass(frozen=True, slots=True)
class RouteEntry:
    agent_id: str
    p: float
    psi: float
    w_bar: float
    eta: float
    explore: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "p": self.p,
            "psi": self.psi,
            "w_bar": self.w_bar,
            "eta": self.eta,
            "explore": self.explore,
        }


@dataclass(frozen=True, slots=True)
class RouteResult:
    intent_id: str
    entries: tuple[RouteEntry, ...]
    distribution: dict[str, float]

    def as_dict(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "entries": [e.as_dict() for e in self.entries],
            "distribution": dict(sorted(self.distribution.items())),
        }


def _sim(proj: Projection) -> LexicalSimilarity:
    return LexicalSimilarity(proj.p.w_tag, proj.p.w_text)


def route(
    proj: Projection,
    intent: Intent,
    t_ms: int,
    view: TrustView,
    *,
    k: int | None = None,
    k_explore: int | None = None,
) -> RouteResult:
    """ACO routing distribution p(a) ∝ W̄^α · max(η, η_min)^β (§7.5)."""
    p = proj.p
    k = p.route_k if k is None else k
    k_explore = p.route_k_explore if k_explore is None else k_explore
    tags = intent.tags
    pool: set[str] = set()
    for tag in tags:
        if tag == STAR:
            pool.update(a for a, ag in proj.agents.items() if ag.status == "ACTIVE")
        else:
            pool.update(proj.by_cap.get(tag, set()))
        pool.update(proj.trail_agents(tag, view))
    pool.discard(intent.emitter)
    if proj.field_agent:
        pool.discard(proj.field_agent)
    sim = _sim(proj)
    scored: list[tuple[str, float, float]] = []
    for aid in pool:
        agent = proj.agents.get(aid)
        if agent is None or agent.status != "ACTIVE":
            continue
        w_bar = sum(proj.trail(t, aid, t_ms, view) for t in tags) / len(tags)
        if w_bar <= 0.0:
            continue
        eta = sim.score(intent.tag_set, intent.text, agent.caps, agent.text)
        scored.append((aid, w_bar, eta))
    scored.sort(key=lambda x: (-x[2], x[0]))
    scored = scored[: p.max_candidates]
    raw = {
        aid: (w_bar**p.route_alpha) * (max(eta, p.eta_min) ** p.route_beta)
        for aid, w_bar, eta in scored
    }
    total = sum(raw[a] for a in sorted(raw))
    if total <= 0.0:
        return RouteResult(intent.intent_id, (), {})
    dist = {a: raw[a] / total for a in sorted(raw)}
    info = {aid: (w, e) for aid, w, e in scored}
    ranked = sorted(dist, key=lambda a: (-dist[a], a))
    top = ranked[:k]
    top_set = set(top)

    def at_floor(aid: str) -> bool:
        return all(proj.trail(t, aid, t_ms, view) == proj.floor(t, aid) for t in tags)

    explore_pool = [a for a in dist if a not in top_set and at_floor(a)]
    explore_pool.sort(key=lambda a: (-info[a][1], a))
    explore = explore_pool[:k_explore]
    entries = [
        RouteEntry(a, dist[a], math.sqrt(dist[a]), info[a][0], info[a][1], False)
        for a in top
    ] + [
        RouteEntry(a, dist[a], math.sqrt(dist[a]), info[a][0], info[a][1], True)
        for a in explore
    ]
    return RouteResult(intent.intent_id, tuple(entries), dist)


@dataclass(frozen=True, slots=True)
class SenseHit:
    intent_id: str
    score: float
    amplitude_eff: float
    eta: float
    leased_by_other: bool


def sense(
    proj: Projection,
    caller: str | None,
    caps: frozenset[str],
    text: TextProfile,
    t_ms: int,
    view: TrustView,
    *,
    k: int | None = None,
) -> list[SenseHit]:
    """Rank OPEN intents for an agent profile (§7.6)."""
    p = proj.p
    k = p.sense_k if k is None else k
    sim = _sim(proj)
    hits: list[SenseHit] = []
    for intent in proj.open_intents_at(t_ms):
        if caller is not None and intent.emitter == caller:
            continue
        a_eff = proj.amplitude_eff(intent, t_ms, view)
        eta = sim.score(intent.tag_set, intent.text, caps, text)
        leases = proj.active_leases(intent, t_ms)
        other = any(a != caller for a in leases)
        q = (a_eff**p.sense_alpha) * (max(eta, p.eta_min) ** p.sense_beta)
        if other:
            q *= p.lambda_lease
        hits.append(SenseHit(intent.intent_id, q, a_eff, eta, other))
    hits.sort(key=lambda h: (-h.score, h.intent_id))
    return hits[:k]
