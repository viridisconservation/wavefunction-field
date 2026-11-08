# SPDX-License-Identifier: Apache-2.0
"""Deterministic read model folded from the event log (PROTOCOL §4, §7, §8).

``Projection.apply`` mutates in place for speed but is deterministic: it reads
no clock, RNG or I/O, and folding the same events in the same order always gives
the same state (INV-ST3). All time-dependent answers take an explicit ``t_ms``.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from wavefunction_field.core import dynamics as dyn
from wavefunction_field.core.canonical import canonical
from wavefunction_field.core.entropy import entropy_bits
from wavefunction_field.core.params import FieldParams
from wavefunction_field.core.similarity import TextProfile, profile
from wavefunction_field.core.views import TrustView

OPEN, COLLAPSED, WITHDRAWN, EVAPORATED = "OPEN", "COLLAPSED", "WITHDRAWN", "EVAPORATED"
TERMINAL = frozenset({COLLAPSED, WITHDRAWN, EVAPORATED})
SUBMITTED, PASSED, FAILED, VOID = "SUBMITTED", "PASSED", "FAILED", "VOID"
STAR = "*"


@dataclass(slots=True)
class Agent:
    agent_id: str
    pubkey: str
    name: str
    description: str
    capabilities: tuple[str, ...]
    links: dict[str, str]
    status: str
    registered_ms: int
    updated_ms: int
    text: TextProfile
    caps: frozenset[str]


@dataclass(slots=True)
class Result:
    result_id: str
    intent_id: str
    doer: str
    hypothesis_id: str
    artifact: dict[str, Any]
    cost: dict[str, int]
    submitted_ms: int
    state: str = SUBMITTED
    verified_ms: int | None = None
    verifier: str | None = None
    evidence: str = ""


@dataclass(slots=True)
class Intent:
    intent_id: str
    emitter: str
    goal: str
    declared_tags: tuple[str, ...]
    hypotheses: list[dict[str, Any]]
    acceptance: dict[str, Any]
    side_effects: tuple[str, ...]
    priority: int
    ttl_s: int
    parent: str | None
    depth: int
    created_ms: int
    density_at_emit: float
    h_bits_at_emit: float
    text: TextProfile
    links: set[str] = field(default_factory=set)
    signals: dict[str, int] = field(default_factory=dict)
    proposals: list[dict[str, Any]] = field(default_factory=list)
    partials: list[dict[str, Any]] = field(default_factory=list)
    leases: dict[str, int] = field(default_factory=dict)
    results: list[str] = field(default_factory=list)
    recorded_state: str = OPEN
    terminal_ms: int | None = None
    collapsed_result: str | None = None

    @property
    def tags(self) -> tuple[str, ...]:
        return self.declared_tags or (STAR,)

    @property
    def tag_set(self) -> frozenset[str]:
        return frozenset(self.declared_tags)

    @property
    def ttl_end_ms(self) -> int:
        return self.created_ms + self.ttl_s * 1000


@dataclass(frozen=True, slots=True)
class TrailRecord:
    t_ms: int
    doer: str
    emitter: str
    verifier: str
    verdict: str
    tags: tuple[str, ...]


@dataclass(slots=True)
class _ViewTrails:
    processed: int = 0
    acc: dict[tuple[str, str], dyn.Accumulator] = field(default_factory=dict)
    by_tag: dict[str, set[str]] = field(default_factory=dict)


def qualifies(rec: TrailRecord, view: TrustView) -> bool:
    """Trail qualification under a view (PROTOCOL §7.3)."""
    return (
        rec.verifier in view.verifiers
        and rec.emitter in view.emitters
        and rec.doer != rec.emitter
        and rec.doer != rec.verifier
    )


class Projection:
    def __init__(self, params: FieldParams) -> None:
        self.p = params
        self.field_agent: str | None = None
        self.field_pubkey: str | None = None
        self.default_view = TrustView.of()
        self.operators: frozenset[str] = frozenset()
        self.agents: dict[str, Agent] = {}
        self.intents: dict[str, Intent] = {}
        self.results: dict[str, Result] = {}
        self.open_ids: set[str] = set()
        self.by_cap: dict[str, set[str]] = {}
        self.trail_log: list[TrailRecord] = []
        self._views: dict[str, _ViewTrails] = {}
        self.write_times: dict[str, deque[int]] = {}
        self.last_ms = 0
        # Read caches (pure memoisation, no semantic effect). Every mutation goes
        # through apply(), which bumps _rev and so invalidates both caches.
        self._rev = 0
        self._evap_rev = -1
        self._evap: dict[str, int] = {}
        self._amp_tag: tuple[int, int, TrustView] | None = None
        self._amp: dict[str, float] = {}

    # ------------------------------------------------------------------ fold
    def apply(self, event: dict[str, Any]) -> None:
        self._rev += 1
        etype = event["type"]
        pl = event["payload"]
        ms = int(event["server_ms"])
        self.last_ms = max(self.last_ms, ms)
        if event.get("envelope") is not None:
            dq = self.write_times.setdefault(event["actor_id"], deque())
            dq.append(ms)
            while dq and dq[0] <= ms - 60_000:
                dq.popleft()
        handler = getattr(self, "_on_" + etype, None)
        if handler is None:
            raise ValueError(f"unknown event type {etype}")
        handler(pl, ms)

    def _on_field_genesis(self, pl: dict[str, Any], ms: int) -> None:
        self.field_agent = pl["field_agent_id"]
        self.field_pubkey = pl["field_pubkey"]
        self.default_view = TrustView.of(
            pl["default_view"]["verifiers"], pl["default_view"]["emitters"]
        )
        self.operators = frozenset(pl.get("operators", []))

    def _on_agent_registered(self, pl: dict[str, Any], ms: int) -> None:
        aid = pl["agent_id"]
        old = self.agents.get(aid)
        if old is not None:
            for cap in old.caps:
                self.by_cap.get(cap, set()).discard(aid)
        caps = tuple(pl["capabilities"])
        text = profile(
            f"{pl['name']} {pl['description']} {' '.join(caps)}", self.p.stopwords
        )
        self.agents[aid] = Agent(
            agent_id=aid,
            pubkey=pl["pubkey"],
            name=pl["name"],
            description=pl["description"],
            capabilities=caps,
            links=dict(pl["links"]),
            status="ACTIVE",
            registered_ms=old.registered_ms if old else ms,
            updated_ms=ms,
            text=text,
            caps=frozenset(caps),
        )
        for cap in caps:
            self.by_cap.setdefault(cap, set()).add(aid)

    def _on_agent_revoked(self, pl: dict[str, Any], ms: int) -> None:
        agent = self.agents[pl["agent_id"]]
        agent.status = "REVOKED"
        agent.updated_ms = ms
        for cap in agent.caps:
            self.by_cap.get(cap, set()).discard(agent.agent_id)

    def _on_intent_emitted(self, pl: dict[str, Any], ms: int) -> None:
        tags = tuple(pl["capabilities_needed"])
        hyps = [dict(h) for h in pl["hypotheses"]]
        text = profile(
            f"{pl['goal']} {' '.join(h['summary'] for h in hyps)} {' '.join(tags)}",
            self.p.stopwords,
        )
        intent = Intent(
            intent_id=pl["intent_id"],
            emitter=pl["emitter"],
            goal=pl["goal"],
            declared_tags=tags,
            hypotheses=hyps,
            acceptance=dict(pl["acceptance"]),
            side_effects=tuple(pl["side_effects"]),
            priority=int(pl["priority"]),
            ttl_s=int(pl["ttl_s"]),
            parent=pl.get("parent_intent_id"),
            depth=int(pl["depth"]),
            created_ms=ms,
            density_at_emit=float(pl["density_at_emit"]),
            h_bits_at_emit=entropy_bits([h["weight"] for h in hyps]),
            text=text,
        )
        self.intents[intent.intent_id] = intent
        self.open_ids.add(intent.intent_id)
        for other in pl["links"]:
            intent.links.add(other)
            self.intents[other].links.add(intent.intent_id)

    def _on_intent_reweighted(self, pl: dict[str, Any], ms: int) -> None:
        intent = self.intents[pl["intent_id"]]
        for h in intent.hypotheses:
            if h["id"] in pl["weights"]:
                h["weight"] = int(pl["weights"][h["id"]])
        if pl.get("adopt"):
            intent.hypotheses.append(dict(pl["adopt"]))

    def _on_deposit_recorded(self, pl: dict[str, Any], ms: int) -> None:
        intent = self.intents[pl["intent_id"]]
        agent = pl["agent"]
        kind = pl["kind"]
        if kind in ("signal", "partial") and agent != intent.emitter:
            intent.signals.setdefault(agent, ms)
        if kind == "hypothesis":
            intent.proposals.append(
                {"author": agent, "summary": pl["summary"], "t_ms": ms}
            )
        elif kind == "claim":
            intent.leases[agent] = int(pl["lease_until_ms"])
        elif kind == "partial":
            intent.partials.append(
                {"author": agent, "artifact": pl["artifact"], "t_ms": ms}
            )

    def _on_claim_released(self, pl: dict[str, Any], ms: int) -> None:
        self.intents[pl["intent_id"]].leases.pop(pl["agent"], None)

    def _on_result_submitted(self, pl: dict[str, Any], ms: int) -> None:
        res = Result(
            result_id=pl["result_id"],
            intent_id=pl["intent_id"],
            doer=pl["doer"],
            hypothesis_id=pl["hypothesis_id"],
            artifact=dict(pl["artifact"]),
            cost=dict(pl["cost_report"]),
            submitted_ms=ms,
        )
        self.results[res.result_id] = res
        self.intents[res.intent_id].results.append(res.result_id)

    def _on_verification_recorded(self, pl: dict[str, Any], ms: int) -> None:
        res = self.results[pl["result_id"]]
        res.state = PASSED if pl["verdict"] == "pass" else FAILED
        res.verified_ms = ms
        res.verifier = pl["verifier"]
        res.evidence = str(pl.get("evidence", {}).get("summary", ""))
        intent = self.intents[res.intent_id]
        rec = TrailRecord(
            t_ms=ms,
            doer=res.doer,
            emitter=intent.emitter,
            verifier=pl["verifier"],
            verdict=pl["verdict"],
            tags=intent.tags,
        )
        self.trail_log.append(rec)

    def _terminate(self, intent: Intent, state: str, ms: int) -> None:
        intent.recorded_state = state
        intent.terminal_ms = ms
        intent.leases.clear()
        self.open_ids.discard(intent.intent_id)
        for rid in intent.results:
            if self.results[rid].state == SUBMITTED:
                self.results[rid].state = VOID

    def _on_intent_collapsed(self, pl: dict[str, Any], ms: int) -> None:
        intent = self.intents[pl["intent_id"]]
        intent.collapsed_result = pl["result_id"]
        self._terminate(intent, COLLAPSED, ms)

    def _on_intent_withdrawn(self, pl: dict[str, Any], ms: int) -> None:
        self._terminate(self.intents[pl["intent_id"]], WITHDRAWN, ms)

    def _on_intent_evaporated(self, pl: dict[str, Any], ms: int) -> None:
        self._terminate(
            self.intents[pl["intent_id"]], EVAPORATED, int(pl["evaporated_at_ms"])
        )

    def _on_result_voided(self, pl: dict[str, Any], ms: int) -> None:
        res = self.results[pl["result_id"]]
        if res.state == SUBMITTED:
            res.state = VOID

    # ----------------------------------------------------- amplitude & life
    def amplitude_parts(
        self, intent: Intent, t_ms: int, view: TrustView
    ) -> tuple[float, float]:
        p = self.p
        return dyn.amplitude_parts(
            p.a_per_priority * intent.priority,
            intent.created_ms,
            intent.signals.items(),
            view.trusted,
            t_ms,
            p.h_A_s,
            p.delta_signal,
        )

    def amplitude(self, intent: Intent, t_ms: int, view: TrustView) -> float:
        tag = (self._rev, t_ms, view)
        if self._amp_tag != tag:
            self._amp_tag, self._amp = tag, {}
        cached = self._amp.get(intent.intent_id)
        if cached is not None:
            return cached
        s, u = self.amplitude_parts(intent, t_ms, view)
        out = dyn.combine_amplitude(s, u, self.p.untrusted_signal_cap, self.p.A_max)
        self._amp[intent.intent_id] = out
        return out

    def evaporation_ms(self, intent: Intent) -> int:
        """Closed-form t_evap under the default view, from recorded events (§7.2)."""
        if self._evap_rev != self._rev:
            self._evap_rev, self._evap = self._rev, {}
        cached = self._evap.get(intent.intent_id)
        if cached is None:
            cached = self._evap[intent.intent_id] = self._evaporation_ms(intent)
        return cached

    def _evaporation_ms(self, intent: Intent) -> int:
        p = self.p
        last = intent.created_ms
        if intent.signals:
            last = max(last, max(intent.signals.values()))
        s, u = self.amplitude_parts(intent, last, self.default_view)
        t_amp = dyn.amplitude_crossing_ms(
            last, s, u, p.untrusted_signal_cap, p.A_alive, p.h_A_s
        )
        holds = []
        for rid in intent.results:
            r = self.results[rid]
            end = r.submitted_ms + p.verify_window_s * 1000
            if r.verified_ms is not None:
                end = min(end, r.verified_ms)
            if end > r.submitted_ms:
                holds.append((r.submitted_ms, end))
        t = t_amp
        for start, end in sorted(holds):
            if start <= t < end:
                t = end
        return min(intent.ttl_end_ms, t)

    def state_at(self, intent: Intent, t_ms: int) -> str:
        if intent.recorded_state != OPEN:
            return intent.recorded_state
        return EVAPORATED if self.evaporation_ms(intent) <= t_ms else OPEN

    def terminal_ms_at(self, intent: Intent, t_ms: int) -> int | None:
        if intent.recorded_state != OPEN:
            return intent.terminal_ms
        t_evap = self.evaporation_ms(intent)
        return t_evap if t_evap <= t_ms else None

    def result_state_at(self, res: Result, t_ms: int) -> str:
        if (
            res.state == SUBMITTED
            and self.state_at(self.intents[res.intent_id], t_ms) in TERMINAL
        ):
            return VOID
        return res.state

    def open_intents_at(self, t_ms: int) -> list[Intent]:
        out = [self.intents[i] for i in sorted(self.open_ids)]
        return [i for i in out if self.state_at(i, t_ms) == OPEN]

    def active_leases(self, intent: Intent, t_ms: int) -> dict[str, int]:
        if self.state_at(intent, t_ms) != OPEN:
            return {}
        return {a: until for a, until in intent.leases.items() if until > t_ms}

    def amplitude_eff(self, intent: Intent, t_ms: int, view: TrustView) -> float:
        """A_eff with one linked intent per distinct other emitter (§7.1, INV-RT6)."""
        base = self.amplitude(intent, t_ms, view)
        best: dict[str, float] = {}
        for jid in intent.links:
            j = self.intents[jid]
            if j.emitter == intent.emitter or self.state_at(j, t_ms) != OPEN:
                continue
            a = self.amplitude(j, t_ms, view)
            if a > best.get(j.emitter, -1.0):
                best[j.emitter] = a
        boost = sum(best[e] for e in sorted(best))
        return min(self.p.A_max, base + self.p.gamma_res * boost)

    # ---------------------------------------------------------------- trails
    def _trails(self, view: TrustView) -> _ViewTrails:
        key = view.key()
        vt = self._views.get(key)
        if vt is None:
            vt = self._views[key] = _ViewTrails()
        p = self.p
        while vt.processed < len(self.trail_log):
            rec = self.trail_log[vt.processed]
            vt.processed += 1
            if not qualifies(rec, view):
                continue
            amount = p.r_base if rec.verdict == "pass" else -p.r_fail
            for tag in rec.tags:
                k = (tag, rec.doer)
                vt.acc[k] = vt.acc.get(k, dyn.Accumulator(0.0, rec.t_ms)).add(
                    amount, rec.t_ms, p.h_trail_s
                )
                vt.by_tag.setdefault(tag, set()).add(rec.doer)
        return vt

    def floor(self, tag: str, agent_id: str) -> float:
        a = self.agents.get(agent_id)
        if a is None or a.status != "ACTIVE" or agent_id == self.field_agent:
            return 0.0
        return self.p.w_min if (tag == STAR or tag in a.caps) else 0.0

    def raw_trail(self, tag: str, agent_id: str, t_ms: int, view: TrustView) -> float:
        acc = self._trails(view).acc.get((tag, agent_id))
        return acc.at(t_ms, self.p.h_trail_s) if acc is not None else 0.0

    def trail(self, tag: str, agent_id: str, t_ms: int, view: TrustView) -> float:
        return dyn.trail_weight(
            self.raw_trail(tag, agent_id, t_ms, view),
            self.floor(tag, agent_id),
            self.p.w_max,
        )

    def trail_agents(self, tag: str, view: TrustView) -> set[str]:
        return set(self._trails(view).by_tag.get(tag, set()))

    def density(self, tags: tuple[str, ...], t_ms: int) -> float:
        v = self.default_view
        total = 0.0
        for tag in tags:
            for aid in sorted(self.trail_agents(tag, v)):
                total += self.trail(tag, aid, t_ms, v) - self.floor(tag, aid)
        return total

    # -------------------------------------------------------------- export
    def canonical_state(self, t_ms: int) -> str:
        """Canonical read-model bytes for equivalence tests (no seq/hash/counts)."""
        return canonical(
            {
                "agents": {
                    k: self.agent_view(a, t_ms) for k, a in sorted(self.agents.items())
                },
                "intents": {
                    k: self.intent_view(i, t_ms)
                    for k, i in sorted(self.intents.items())
                },
            }
        )

    def agent_view(self, a: Agent, t_ms: int) -> dict[str, Any]:
        v = self.default_view
        tags = sorted(
            a.caps
            | {
                t
                for t in self._trails(v).by_tag
                if a.agent_id in self._trails(v).by_tag[t]
            }
        )
        return {
            "agent_id": a.agent_id,
            "pubkey": a.pubkey,
            "name": {"untrusted": {"author": a.agent_id, "text": a.name}},
            "description": {"untrusted": {"author": a.agent_id, "text": a.description}},
            "capabilities": list(a.capabilities),
            "links": {
                k: {"untrusted": {"author": a.agent_id, "text": v}}
                for k, v in sorted(a.links.items())
            },
            "status": a.status,
            "trails": {t: round(self.trail(t, a.agent_id, t_ms, v), 12) for t in tags},
        }

    def intent_view(self, i: Intent, t_ms: int) -> dict[str, Any]:
        def wrap(author: str, text: str) -> dict[str, Any]:
            return {"untrusted": {"author": author, "text": text}}

        state = self.state_at(i, t_ms)
        weights = [h["weight"] for h in i.hypotheses]
        return {
            "intent_id": i.intent_id,
            "emitter": i.emitter,
            "goal": wrap(i.emitter, i.goal),
            "capabilities_needed": list(i.declared_tags),
            "hypotheses": [
                {
                    "id": h["id"],
                    "summary": wrap(i.emitter, h["summary"]),
                    "weight": h["weight"],
                }
                for h in i.hypotheses
            ],
            "entropy_bits": entropy_bits(weights),
            "acceptance": self._acceptance_view(i),
            "side_effects": list(i.side_effects),
            "priority": i.priority,
            "ttl_s": i.ttl_s,
            "parent_intent_id": i.parent,
            "created_ms": i.created_ms,
            "density_at_emit": i.density_at_emit,
            "state": state,
            "terminal_ms": self.terminal_ms_at(i, t_ms),
            "amplitude": self.amplitude(i, t_ms, self.default_view)
            if state == OPEN
            else 0.0,
            "links": sorted(i.links),
            "signals": sorted(i.signals),
            "proposals": [
                {"summary": wrap(x["author"], x["summary"]), "t_ms": x["t_ms"]}
                for x in i.proposals
            ],
            "partials": [
                {
                    "author": x["author"],
                    "artifact": self._artifact_view(x["author"], x["artifact"]),
                    "t_ms": x["t_ms"],
                }
                for x in i.partials
            ],
            "leases": dict(sorted(self.active_leases(i, t_ms).items())),
            "results": [self.result_view(self.results[r], t_ms) for r in i.results],
            "collapsed_result": i.collapsed_result,
        }

    @staticmethod
    def _acceptance_view(i: Intent) -> dict[str, Any]:
        acc = i.acceptance
        out: dict[str, Any] = {"kind": acc["kind"]}
        if acc["kind"] == "json_schema":
            out["schema"] = {
                "untrusted": {"author": i.emitter, "text": canonical(acc["schema"])}
            }
        elif acc["kind"] == "digest":
            out["sha256"] = acc["sha256"]
        elif acc["kind"] == "designated":
            out["verifiers"] = list(acc["verifiers"])
        return out

    @staticmethod
    def _artifact_view(author: str, art: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {"sha256": art["sha256"]}
        for key in ("content_type", "inline", "uri"):
            if key in art:
                out[key] = {"untrusted": {"author": author, "text": art[key]}}
        return out

    def result_view(self, r: Result, t_ms: int) -> dict[str, Any]:
        return {
            "result_id": r.result_id,
            "intent_id": r.intent_id,
            "doer": r.doer,
            "hypothesis_id": r.hypothesis_id,
            "artifact": self._artifact_view(r.doer, r.artifact),
            "cost_report_self_reported": dict(r.cost),
            "state": self.result_state_at(r, t_ms),
            "submitted_ms": r.submitted_ms,
            "verified_ms": r.verified_ms,
            "verifier": r.verifier,
            "evidence": {"untrusted": {"author": r.verifier or "", "text": r.evidence}},
        }
