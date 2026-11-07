# SPDX-License-Identifier: Apache-2.0
"""Simulation world for the preregistered experiments (spec/sim_preregistration.json).

Every write is a signed envelope applied to the production FieldService
(INV-SIM1). Arms differ only by params overrides and the trust view used for
routing. The simulator alone owns randomness: one random.Random per purpose,
seeded deterministically from (seed, purpose).
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field
from typing import Any

from wavefunction_field.core.params import FieldParams
from wavefunction_field.identity.envelope import format_ms
from wavefunction_field.identity.signer import FieldSigner
from wavefunction_field.service.clock import FakeClock
from wavefunction_field.service.field import FieldService
from wavefunction_field.store.memory import MemoryStore

T0_MS = 1_800_000_000_000


def rng(seed: int, purpose: str) -> random.Random:
    digest = hashlib.sha256(f"wf-sim|{seed}|{purpose}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def signer(seed: int, role: str, i: int) -> FieldSigner:
    return FieldSigner.from_private_bytes(
        hashlib.sha256(f"wf-sim|{seed}|{role}|{i}".encode()).digest()
    )


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


@dataclass
class SimAgent:
    signer: FieldSigner
    caps: list[str]
    competence: dict[str, float]
    sybil: bool = False

    @property
    def id(self) -> str:
        return self.signer.agent_id


@dataclass
class World:
    prereg: dict[str, Any]
    scenario: str
    arm: str
    seed: int
    params: FieldParams
    rows: list[dict[str, Any]] = field(default_factory=list)
    probe: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        w = self.prereg["world"]
        self.cfg = self.prereg["scenarios"][self.scenario]
        self.tags: list[str] = list(w["tags"])
        self.clock = FakeClock(T0_MS)
        self.r_world = rng(self.seed, "world")
        self.r_arrivals = rng(self.seed, "arrivals")
        self.r_route = rng(self.seed, "route")
        self.r_attempt = rng(self.seed, "attempt")
        self.r_ring = rng(self.seed, "ring")
        self.nonce = 0
        arm_cfg = self.prereg["arms"][self.arm]
        self.params = self.params.with_overrides(arm_cfg["params_override"])
        self.emitters = [
            signer(self.seed, "emitter", i) for i in range(w["honest_emitters"])
        ]
        self.agents: list[SimAgent] = []
        for i in range(w["honest_agents"]):
            caps = sorted(self.r_world.sample(self.tags, w["declared_tags_per_agent"]))
            comp = {t: w["competence_undeclared"] for t in self.tags}
            for t in caps:
                comp[t] = self.r_world.uniform(
                    w["competence_declared"]["low"], w["competence_declared"]["high"]
                )
            self.agents.append(SimAgent(signer(self.seed, "agent", i), caps, comp))
        syb = self.cfg.get("sybils")
        self.sybil_emitters: list[FieldSigner] = []
        if syb:
            for i in range(syb["agents"]):
                comp = {t: float(syb["competence"]) for t in self.tags}
                self.agents.append(
                    SimAgent(
                        signer(self.seed, "sybil", i), list(self.tags), comp, sybil=True
                    )
                )
            self.sybil_emitters = [
                signer(self.seed, "sybil-emitter", i) for i in range(syb["emitters"])
            ]
        self.svc = FieldService(
            MemoryStore(),
            self.params,
            self.clock,
            signer(self.seed, "field", 0),
            trusted_emitters=[e.agent_id for e in self.emitters],
        )
        for e in self.emitters:
            self.write(
                e, "register_agent", {"name": "emitter", "capabilities": ["ops"]}
            )
        for e in self.sybil_emitters:
            self.write(
                e, "register_agent", {"name": "emitter", "capabilities": ["ops"]}
            )
        for a in self.agents:
            self.write(
                a.signer, "register_agent", {"name": "agent", "capabilities": a.caps}
            )
        if arm_cfg["view"] == "ALL_REGISTERED_AGENTS":
            ids = sorted(self.svc.proj.agents)
            self.view: dict[str, list[str]] | None = {
                "verifiers": sorted({*ids, self.svc.signer.agent_id}),
                "emitters": ids,
            }
        else:
            self.view = None
        self.intent_seq = 0
        self.newcomer: SimAgent | None = None

    # -------------------------------------------------------------- plumbing
    def tick(self) -> None:
        self.clock.advance(1)

    def write(
        self, s: FieldSigner, action: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        self.nonce += 1
        self.tick()
        req = s.request(
            action,
            body,
            nonce=f"nonce-sim-{self.nonce:09d}",
            signed_at=format_ms(self.clock.now_ms()),
        )
        return self.svc.apply(req)

    def step_start(self, step: int) -> None:
        target = T0_MS + 60_000 + step * self.prereg["time"]["step_s"] * 1000
        if target > self.clock.now_ms():
            self.clock.advance(target - self.clock.now_ms())

    def poisson(self, lam: float) -> int:
        # Knuth's method; deterministic with the arrivals stream.
        limit, k, p = math.exp(-lam), 0, 1.0
        while True:
            p *= self.r_arrivals.random()
            if p <= limit:
                return k
            k += 1

    # ------------------------------------------------------------- dynamics
    def competence(self, agent_id: str, tags: list[str]) -> float:
        a = self.by_id(agent_id)
        return min(a.competence[t] for t in tags) if a else 0.0

    def by_id(self, agent_id: str) -> SimAgent | None:
        if not hasattr(self, "_index"):
            self._index: dict[str, SimAgent] = {}
        if agent_id not in self._index:
            for a in self.agents + ([self.newcomer] if self.newcomer else []):
                self._index[a.id] = a
        return self._index.get(agent_id)

    def honest_intent(self, step: int) -> None:
        w = self.prereg["world"]
        n_tags = self.r_arrivals.choices(
            w["tags_per_intent"]["choices"], w["tags_per_intent"]["probs"]
        )[0]
        tags = sorted(self.r_arrivals.sample(self.tags, n_tags))
        n_h = self.r_arrivals.randint(
            w["hypotheses_per_intent"]["low"], w["hypotheses_per_intent"]["high"]
        )
        weights = [
            self.r_arrivals.randint(
                w["hypothesis_weight"]["low"], w["hypothesis_weight"]["high"]
            )
            for _ in range(n_h)
        ]
        emitter = self.emitters[self.r_arrivals.randrange(len(self.emitters))]
        self.intent_seq += 1
        correct = f"correct-{self.seed}-{self.intent_seq}"
        out = self.write(
            emitter,
            "emit_intent",
            {
                "goal": f"task {' '.join(tags)}",
                "hypotheses": [
                    {"id": f"h{i + 1}", "summary": f"approach {i + 1}", "weight": wt}
                    for i, wt in enumerate(weights)
                ],
                "acceptance": {"kind": "digest", "sha256": sha(correct)},
                "priority": w["priority"],
                "ttl_s": w["ttl_s"],
                "capabilities_needed": tags,
            },
        )
        iid = out["intent_id"]
        intent = self.svc.get_intent(iid)
        tried: set[str] = set()
        cost = 0
        attempts = 0
        sybil_mass = None
        collapsed = False
        while attempts < w["max_attempts_per_intent"]:
            dist = self.svc.route(iid, view=self.view)["distribution"]
            if sybil_mass is None:
                sybil_mass = sum(
                    p
                    for a, p in dist.items()
                    if (x := self.by_id(a)) is not None and x.sybil
                )
            choices = [
                (a, p) for a, p in sorted(dist.items()) if a not in tried and p > 0
            ]
            if not choices:
                break
            total = sum(p for _, p in choices)
            u = self.r_route.random() * total
            acc = 0.0
            pick = choices[-1][0]
            for a, p in choices:
                acc += p
                if u < acc:
                    pick = a
                    break
            tried.add(pick)
            attempts += 1
            ok = self.r_attempt.random() < self.competence(pick, tags)
            tokens = int(
                w["attempt_tokens"]["base"]
                * (1 + abs(self.r_attempt.gauss(0.0, w["attempt_tokens"]["sigma"])))
            )
            cost += tokens
            content = correct if ok else f"wrong-{pick}-{self.intent_seq}"
            agent = self.by_id(pick)
            assert agent is not None
            res = self.write(
                agent.signer,
                "submit_result",
                {
                    "intent_id": iid,
                    "hypothesis_id": "h1",
                    "artifact": {
                        "content_type": "text/plain",
                        "sha256": sha(content),
                        "inline": content,
                    },
                    "cost_report": {"tokens": tokens, "wall_ms": 1000},
                },
            )
            if res["intent_state"] == "COLLAPSED":
                collapsed = True
                break
        if not collapsed:
            self.write(emitter, "withdraw_intent", {"intent_id": iid})
        self.rows.append(
            {
                "scenario": self.scenario,
                "arm": self.arm,
                "seed": self.seed,
                "step": step,
                "intent_id": iid,
                "tags": "|".join(tags),
                "density_at_emit": intent["density_at_emit"],
                "H_bits": intent["entropy_bits"],
                "attempts": attempts,
                "cost_to_collapse_tokens": cost,
                "collapsed": int(collapsed),
                "sybil_mass": sybil_mass if sybil_mass is not None else 0.0,
            }
        )

    def ring_intent(self) -> None:
        syb = [a for a in self.agents if a.sybil]
        e = self.sybil_emitters[self.r_ring.randrange(len(self.sybil_emitters))]
        v, d = self.r_ring.sample(syb, 2)
        n_tags = self.r_ring.choice([1, 2])
        tags = sorted(self.r_ring.sample(self.tags, n_tags))
        out = self.write(
            e,
            "emit_intent",
            {
                "goal": f"task {' '.join(tags)}",
                "hypotheses": [{"id": "h1", "summary": "approach 1", "weight": 1}],
                "acceptance": {"kind": "designated", "verifiers": [v.id]},
                "priority": 5,
                "ttl_s": 604800,
                "capabilities_needed": tags,
            },
        )
        res = self.write(
            d.signer,
            "submit_result",
            {
                "intent_id": out["intent_id"],
                "hypothesis_id": "h1",
                "artifact": {
                    "content_type": "text/plain",
                    "sha256": sha("ring"),
                    "inline": "ring",
                },
                "cost_report": {"tokens": 1, "wall_ms": 1},
            },
        )
        self.write(
            v.signer, "verify", {"result_id": res["result_id"], "verdict": "pass"}
        )

    def shock(self) -> None:
        sh = self.cfg["shock"]
        tag = sh["focus_tag"]
        for a in self.agents:
            a.competence[tag] = 0.1
        comp = {t: self.prereg["world"]["competence_undeclared"] for t in self.tags}
        comp[tag] = 0.9
        self.newcomer = SimAgent(signer(self.seed, "newcomer", 0), [tag], comp)
        self.write(
            self.newcomer.signer,
            "register_agent",
            {"name": "agent", "capabilities": [tag]},
        )
        self._index = {}

    def record_probe(self, step: int) -> None:
        tag = self.cfg["shock"]["probe_tag"]
        dist = self.svc.preview_route(f"task {tag}", [tag], view=self.view)[
            "distribution"
        ]
        e_s = sum(p * self.competence(a, [tag]) for a, p in dist.items())
        share = dist.get(self.newcomer.id, 0.0) if self.newcomer else 0.0
        self.probe.append(
            {
                "scenario": self.scenario,
                "arm": self.arm,
                "seed": self.seed,
                "step": step,
                "E_s": e_s,
                "newcomer_share": share,
            }
        )

    # ------------------------------------------------------------------ run
    def run(self, steps: int | None = None) -> None:
        steps = steps or self.prereg["time"]["steps"]
        lam = self.prereg["world"]["intents_per_step"]["lambda"]
        syb = self.cfg.get("sybils")
        shock = self.cfg.get("shock")
        for step in range(steps):
            self.step_start(step)
            if shock and step == shock["at_step"]:
                self.shock()
            if syb and step >= syb["start_step"]:
                for _ in range(syb["ring_intents_per_step"]):
                    self.ring_intent()
            for _ in range(self.poisson(lam)):
                self.honest_intent(step)
            if shock:
                self.record_probe(step)
