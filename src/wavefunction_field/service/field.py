# SPDX-License-Identifier: Apache-2.0
"""FieldService: signed write in -> validated transition -> events -> projection.

Implements PROTOCOL §2.2 (acceptance order, decision 0002 C8), §4 lifecycle,
§5 actions, §6 verification and §9.5 quotas. Reads are computed lazily at now.
"""

from __future__ import annotations

import json
import statistics
from typing import Any

from wavefunction_field.core import routing
from wavefunction_field.core.canonical import (
    canonical,
    canonical_bytes,
    digest,
    sha256_hex,
)
from wavefunction_field.core.errors import (
    WFPError,
    budget,
    context,
    permission,
    validation,
)
from wavefunction_field.core.models import AGENT_ID_RE, TAG_RE, validate_body
from wavefunction_field.core.params import FieldParams
from wavefunction_field.core.projection import (
    COLLAPSED,
    EVAPORATED,
    OPEN,
    SUBMITTED,
    TERMINAL,
    Intent,
    Projection,
)
from wavefunction_field.core.resonance import links_for
from wavefunction_field.core.similarity import LexicalSimilarity, profile
from wavefunction_field.core.views import TrustView
from wavefunction_field.identity.envelope import verify_request
from wavefunction_field.identity.signer import FieldSigner
from wavefunction_field.service.clock import Clock
from wavefunction_field.store.base import EventStore, WriteMeta
from wavefunction_field.verify import MACHINE_VERIFIERS
from wavefunction_field.verify.designated import may_verify

INTENT_ACTIONS = (
    "reweight",
    "deposit",
    "release_claim",
    "submit_result",
    "withdraw_intent",
)


class FieldService:
    def __init__(
        self,
        store: EventStore,
        params: FieldParams,
        clock: Clock,
        field_signer: FieldSigner,
        *,
        trusted_emitters: list[str] | None = None,
        trusted_verifiers: list[str] | None = None,
        operators: list[str] | None = None,
    ) -> None:
        self.store = store
        self.p = params
        self.clock = clock
        self.signer = field_signer
        self.proj = Projection(params)
        events = list(store.iter_events())
        if not events:
            verifiers = sorted({field_signer.agent_id, *(trusted_verifiers or [])})
            genesis = {
                "type": "field_genesis",
                "actor_id": field_signer.agent_id,
                "payload": {
                    "field_agent_id": field_signer.agent_id,
                    "field_pubkey": field_signer.public_key_b64,
                    "params_sha256": params.sha256,
                    "default_view": {
                        "verifiers": verifiers,
                        "emitters": sorted(trusted_emitters or []),
                    },
                    "operators": sorted(operators or []),
                },
            }
            self._commit([genesis], None)
        else:
            for event in events:
                self.proj.apply(event)
        if self.proj.field_agent != field_signer.agent_id:
            raise ValueError("field key does not match the genesis event of this store")

    # --------------------------------------------------------------- plumbing
    @property
    def default_view(self) -> TrustView:
        return self.proj.default_view

    def _core(
        self,
        etype: str,
        actor: str,
        payload: dict[str, Any],
        now: int,
        request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        core: dict[str, Any] = {
            "type": etype,
            "actor_id": actor,
            "server_ms": now,
            "payload": payload,
            "envelope": None,
            "pubkey": None,
            "signature": None,
        }
        if request is not None:
            core["envelope"] = request["envelope"]
            core["pubkey"] = request["pubkey"]
            core["signature"] = request["signature"]
        elif actor == self.signer.agent_id:
            core["signature"] = self.signer.sign_bytes(
                canonical_bytes({"type": etype, "payload": payload, "server_ms": now})
            )
        core["event_id"] = (
            "evt_"
            + digest(
                {
                    k: core[k]
                    for k in ("type", "actor_id", "server_ms", "payload", "envelope")
                }
            )[:24]
        )
        return core

    def _commit(
        self, cores: list[dict[str, Any]], meta: WriteMeta | None
    ) -> list[dict[str, Any]]:
        for core in cores:
            core.setdefault("server_ms", self.clock.now_ms())
            core.setdefault("envelope", None)
            core.setdefault("pubkey", None)
            if "signature" not in core:
                core["signature"] = self.signer.sign_bytes(
                    canonical_bytes(
                        {
                            "type": core["type"],
                            "payload": core["payload"],
                            "server_ms": core["server_ms"],
                        }
                    )
                )
            core.setdefault(
                "event_id",
                "evt_"
                + digest(
                    {
                        k: core[k]
                        for k in (
                            "type",
                            "actor_id",
                            "server_ms",
                            "payload",
                            "envelope",
                        )
                    }
                )[:24],
            )
        try:
            sealed = self.store.append(cores, meta)
        except ValueError as exc:
            if "nonce" in str(exc).lower() or "unique" in str(exc).lower():
                raise validation(
                    "nonce already used", "envelope.nonce", "replay"
                ) from None
            raise WFPError("BackendError", "store rejected the write") from None
        for event in sealed:
            self.proj.apply(event)
        return sealed

    def _lazy_terminal(self, intent: Intent, now: int) -> None:
        """Record a lazily-computed evaporation before acting on/rejecting (§7.2)."""
        if (
            intent.recorded_state == OPEN
            and self.proj.state_at(intent, now) == EVAPORATED
        ):
            t_evap = self.proj.evaporation_ms(intent)
            cores = [
                self._core(
                    "intent_evaporated",
                    self.signer.agent_id,
                    {
                        "intent_id": intent.intent_id,
                        "evaporated_at_ms": t_evap,
                        "reason": "ttl" if t_evap == intent.ttl_end_ms else "amplitude",
                    },
                    now,
                )
            ]
            cores += [
                self._core(
                    "result_voided", self.signer.agent_id, {"result_id": rid}, now
                )
                for rid in intent.results
                if self.proj.results[rid].state == SUBMITTED
            ]
            self._commit(cores, None)

    def sweep(self) -> int:
        """Append evaporation events for intents that are lazily terminal now."""
        now = self.clock.now_ms()
        count = 0
        for iid in sorted(self.proj.open_ids):
            intent = self.proj.intents[iid]
            if self.proj.state_at(intent, now) == EVAPORATED:
                self._lazy_terminal(intent, now)
                count += 1
        return count

    # ----------------------------------------------------------------- writes
    def apply(self, request: Any) -> dict[str, Any]:
        """Apply one signed write; returns the result or raises WFPError."""
        now = self.clock.now_ms()
        env = verify_request(request, now, self.p.skew_s)  # rules 1-4
        actor = env["actor_id"]
        action = env["action"]
        agent = self.proj.agents.get(actor)
        if actor == self.signer.agent_id:
            raise permission("the field key cannot submit writes")
        if action != "register_agent":  # rule 5
            if agent is None:
                raise permission("actor is not registered", "envelope.actor_id")
            if agent.status != "ACTIVE":
                raise permission("actor is revoked", "envelope.actor_id")
            if agent.pubkey != request["pubkey"]:
                raise permission("pubkey does not match the registered key", "pubkey")
        elif agent is not None and agent.status != "ACTIVE":
            raise permission("actor is revoked", "envelope.actor_id")
        body = validate_body(action, env["body"], self.p)  # rule 6
        idem_key = body.get("idempotency_key")
        body_sha = sha256_hex(canonical_bytes(env["body"]))
        if idem_key is not None:  # rule 7 (before nonce, decision 0002 C8)
            rec = self.store.get_idempotent(actor, idem_key)
            if rec is not None:
                if rec.body_sha256 == body_sha:
                    result: dict[str, Any] = json.loads(rec.result_json)
                    return result
                raise context("idempotency_conflict", "body.idempotency_key")
        if self.store.has_nonce(actor, env["nonce"]):  # rule 8
            raise validation("nonce already used", "envelope.nonce", "replay")
        if action != "register_agent":  # rule 9
            recent = self.proj.write_times.get(actor)
            n = sum(1 for ms in recent if ms > now - 60_000) if recent else 0
            if n >= self.p.limits["writes_per_minute"]:
                raise budget("writes_per_minute exceeded", "writes_per_minute")
        handler = getattr(self, "_do_" + action)
        cores, result = handler(actor, body, request, now)
        meta = WriteMeta(
            actor_id=actor,
            nonce=env["nonce"],
            idem_key=idem_key,
            body_sha256=body_sha if idem_key else None,
            result_json=canonical(result) if idem_key else None,
        )
        self._commit(cores, meta)
        out: dict[str, Any] = result
        return out

    def _intent(self, intent_id: str, now: int) -> Intent:
        intent = self.proj.intents.get(intent_id)
        if intent is None:
            raise context("unknown intent", "body.intent_id")
        self._lazy_terminal(intent, now)
        if intent.recorded_state in TERMINAL:
            raise context(f"intent is {intent.recorded_state}", "body.intent_id")
        return intent

    def _do_register_agent(
        self, actor: str, body: dict[str, Any], req: dict[str, Any], now: int
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        payload = {
            "agent_id": actor,
            "pubkey": req["pubkey"],
            "name": body["name"],
            "description": body["description"],
            "capabilities": body["capabilities"],
            "links": body["links"],
        }
        return [self._core("agent_registered", actor, payload, now, req)], {
            "agent_id": actor,
            "status": "ACTIVE",
        }

    def _do_revoke_agent(
        self, actor: str, body: dict[str, Any], req: dict[str, Any], now: int
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        target = body["agent_id"]
        if target != actor and actor not in self.proj.operators:
            raise permission(
                "only the agent itself or an operator may revoke", "body.agent_id"
            )
        agent = self.proj.agents.get(target)
        if agent is None or agent.status != "ACTIVE":
            raise context("agent is not active", "body.agent_id")
        return [self._core("agent_revoked", actor, {"agent_id": target}, now, req)], {
            "agent_id": target,
            "status": "REVOKED",
        }

    def _do_emit_intent(
        self, actor: str, body: dict[str, Any], req: dict[str, Any], now: int
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        p = self.p
        open_count = sum(
            1 for i in self.proj.open_intents_at(now) if i.emitter == actor
        )
        if open_count >= p.limits["open_intents_per_emitter"]:
            raise budget(
                "open_intents_per_emitter exceeded", "open_intents_per_emitter"
            )
        acc = body["acceptance"]
        if acc["kind"] in MACHINE_VERIFIERS:
            MACHINE_VERIFIERS[acc["kind"]].check_spec(acc)
        depth = 0
        parent_id = body.get("parent_intent_id")
        if parent_id is not None:
            parent = self._intent(parent_id, now)
            depth = parent.depth + 1
            if depth > p.max_depth:
                raise validation(
                    "sub-intent depth exceeds max_depth",
                    "body.parent_intent_id",
                    "max_depth",
                )
        intent_id = "int_" + sha256_hex(canonical_bytes(req["envelope"]))[:24]
        if intent_id in self.proj.intents:
            raise context("intent already exists", "envelope")
        tags = tuple(body["capabilities_needed"])
        text = profile(
            f"{body['goal']} {' '.join(h['summary'] for h in body['hypotheses'])} {' '.join(tags)}",
            p.stopwords,
        )
        sim = LexicalSimilarity(p.w_tag, p.w_text)
        tagset = frozenset(tags)
        candidates = [
            (j.intent_id, sim.score(tagset, text, j.tag_set, j.text))
            for j in self.proj.open_intents_at(now)
        ]
        degree = {iid: len(self.proj.intents[iid].links) for iid, _ in candidates}
        links = links_for(intent_id, candidates, degree, p.theta_res, p.max_links)
        payload = {
            "intent_id": intent_id,
            "emitter": actor,
            "goal": body["goal"],
            "hypotheses": body["hypotheses"],
            "acceptance": acc,
            "priority": body["priority"],
            "ttl_s": body["ttl_s"],
            "capabilities_needed": list(tags),
            "side_effects": body["side_effects"],
            "parent_intent_id": parent_id,
            "depth": depth,
            "density_at_emit": self.proj.density(tags or ("*",), now),
            "links": links,
        }
        return [self._core("intent_emitted", actor, payload, now, req)], {
            "intent_id": intent_id,
            "state": OPEN,
            "links": links,
        }

    def _do_reweight(
        self, actor: str, body: dict[str, Any], req: dict[str, Any], now: int
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        intent = self._intent(body["intent_id"], now)
        if actor != intent.emitter:
            raise permission("only the emitter may reweight", "body.intent_id")
        ids = {h["id"] for h in intent.hypotheses}
        for hid in body["weights"]:
            if hid not in ids:
                raise validation("unknown hypothesis id", f"body.weights.{hid}")
        payload: dict[str, Any] = {
            "intent_id": intent.intent_id,
            "weights": body["weights"],
        }
        if "adopt" in body:
            if len(intent.hypotheses) >= self.p.limits["max_hypotheses"]:
                raise validation("too many hypotheses", "body.adopt")
            n = 1
            while f"h{n}" in ids:
                n += 1
            payload["adopt"] = {"id": f"h{n}", **body["adopt"]}
        return [self._core("intent_reweighted", actor, payload, now, req)], {
            "intent_id": intent.intent_id
        }

    def _do_deposit(
        self, actor: str, body: dict[str, Any], req: dict[str, Any], now: int
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        intent = self._intent(body["intent_id"], now)
        payload: dict[str, Any] = {
            "intent_id": intent.intent_id,
            "agent": actor,
            "kind": body["kind"],
        }
        result: dict[str, Any] = {"intent_id": intent.intent_id, "kind": body["kind"]}
        if body["kind"] == "hypothesis":
            payload["summary"] = body["summary"]
        elif body["kind"] == "claim":
            payload["lease_until_ms"] = now + body["lease_s"] * 1000
            result["lease_until_ms"] = payload["lease_until_ms"]
        elif body["kind"] == "partial":
            payload["artifact"] = body["artifact"]
        return [self._core("deposit_recorded", actor, payload, now, req)], result

    def _do_release_claim(
        self, actor: str, body: dict[str, Any], req: dict[str, Any], now: int
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        intent = self._intent(body["intent_id"], now)
        if actor not in self.proj.active_leases(intent, now):
            raise context("no active lease", "body.intent_id")
        return [
            self._core(
                "claim_released",
                actor,
                {"intent_id": intent.intent_id, "agent": actor},
                now,
                req,
            )
        ], {"intent_id": intent.intent_id}

    def _do_submit_result(
        self, actor: str, body: dict[str, Any], req: dict[str, Any], now: int
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        intent = self._intent(body["intent_id"], now)
        if body["hypothesis_id"] not in {h["id"] for h in intent.hypotheses}:
            raise validation("unknown hypothesis id", "body.hypothesis_id")
        mine = sum(1 for rid in intent.results if self.proj.results[rid].doer == actor)
        if mine >= self.p.limits["results_per_intent_per_doer"]:
            raise budget(
                "results_per_intent_per_doer exceeded", "results_per_intent_per_doer"
            )
        result_id = "res_" + sha256_hex(canonical_bytes(req["envelope"]))[:24]
        submitted = {
            "result_id": result_id,
            "intent_id": intent.intent_id,
            "doer": actor,
            "hypothesis_id": body["hypothesis_id"],
            "artifact": body["artifact"],
            "cost_report": body["cost_report"],
        }
        cores = [self._core("result_submitted", actor, submitted, now, req)]
        out: dict[str, Any] = {
            "result_id": result_id,
            "intent_id": intent.intent_id,
            "state": SUBMITTED,
            "intent_state": OPEN,
        }
        acc = intent.acceptance
        verifier = MACHINE_VERIFIERS.get(acc["kind"])
        if verifier is not None:
            verdict = verifier.verify(acc, body["artifact"])
            fid = self.signer.agent_id
            cores.append(
                self._core(
                    "verification_recorded",
                    fid,
                    {
                        "result_id": result_id,
                        "intent_id": intent.intent_id,
                        "verifier": fid,
                        "verdict": verdict.verdict,
                        "assurance": "machine",
                        "evidence": {"summary": verdict.reason},
                    },
                    now,
                )
            )
            out["state"] = "PASSED" if verdict.verdict == "pass" else "FAILED"
            if verdict.verdict == "pass":
                cores += self._collapse_cores(intent, result_id, now)
                out["intent_state"] = COLLAPSED
        return cores, out

    def _collapse_cores(
        self, intent: Intent, result_id: str, now: int
    ) -> list[dict[str, Any]]:
        fid = self.signer.agent_id
        cores = [
            self._core(
                "intent_collapsed",
                fid,
                {"intent_id": intent.intent_id, "result_id": result_id},
                now,
            )
        ]
        cores += [
            self._core("result_voided", fid, {"result_id": rid}, now)
            for rid in intent.results
            if self.proj.results[rid].state == SUBMITTED and rid != result_id
        ]
        return cores

    def _do_verify(
        self, actor: str, body: dict[str, Any], req: dict[str, Any], now: int
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        res = self.proj.results.get(body["result_id"])
        if res is None:
            raise context("unknown result", "body.result_id")
        intent = self._intent(res.intent_id, now)
        if not may_verify(intent.acceptance, actor, res.doer):
            raise permission(
                "not a permitted verifier for this result", "body.result_id"
            )
        if res.state != SUBMITTED:
            raise context(f"result is {res.state}", "body.result_id")
        payload = {
            "result_id": res.result_id,
            "intent_id": intent.intent_id,
            "verifier": actor,
            "verdict": body["verdict"],
            "assurance": "designated",
            "evidence": body.get("evidence", {"summary": ""}),
        }
        cores = [self._core("verification_recorded", actor, payload, now, req)]
        out = {
            "result_id": res.result_id,
            "state": "PASSED" if body["verdict"] == "pass" else "FAILED",
            "intent_state": OPEN,
        }
        if body["verdict"] == "pass":
            cores += self._collapse_cores(intent, res.result_id, now)
            out["intent_state"] = COLLAPSED
        return cores, out

    def _do_withdraw_intent(
        self, actor: str, body: dict[str, Any], req: dict[str, Any], now: int
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        intent = self._intent(body["intent_id"], now)
        if actor != intent.emitter:
            raise permission("only the emitter may withdraw", "body.intent_id")
        cores = [
            self._core(
                "intent_withdrawn", actor, {"intent_id": intent.intent_id}, now, req
            )
        ]
        cores += [
            self._core("result_voided", self.signer.agent_id, {"result_id": rid}, now)
            for rid in intent.results
            if self.proj.results[rid].state == SUBMITTED
        ]
        return cores, {"intent_id": intent.intent_id, "state": "WITHDRAWN"}

    # ------------------------------------------------------------------ reads
    def parse_view(self, view: Any) -> TrustView:
        if view is None:
            return self.default_view
        if not isinstance(view, dict) or set(view) - {"verifiers", "emitters"}:
            raise validation("view must be {verifiers, emitters}", "view")
        lists = []
        for key in ("verifiers", "emitters"):
            ids = view.get(key, [])
            if not isinstance(ids, list) or len(ids) > self.p.limits["max_view_ids"]:
                raise validation(
                    f"view.{key} must be a list of at most {self.p.limits['max_view_ids']} ids",
                    f"view.{key}",
                )
            for x in ids:
                if not isinstance(x, str) or not AGENT_ID_RE.match(x):
                    raise validation("invalid agent id", f"view.{key}")
            lists.append(ids)
        return TrustView.of(lists[0], lists[1])

    def get_intent(self, intent_id: str) -> dict[str, Any]:
        intent = self.proj.intents.get(intent_id)
        if intent is None:
            raise context("unknown intent", "intent_id")
        return self.proj.intent_view(intent, self.clock.now_ms())

    def list_intents(
        self,
        state: str | None = None,
        tag: str | None = None,
        emitter: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        now = self.clock.now_ms()
        limit = max(1, min(int(limit), self.p.limits["list_limit"]))
        items = []
        for iid in sorted(self.proj.intents):
            if cursor is not None and iid <= cursor:
                continue
            i = self.proj.intents[iid]
            if state and self.proj.state_at(i, now) != state:
                continue
            if tag and tag not in i.declared_tags:
                continue
            if emitter and i.emitter != emitter:
                continue
            items.append(self.proj.intent_view(i, now))
            if len(items) >= limit:
                break
        nxt = items[-1]["intent_id"] if len(items) == limit else None
        return {"intents": items, "next_cursor": nxt}

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        agent = self.proj.agents.get(agent_id)
        if agent is None:
            raise context("unknown agent", "agent_id")
        return self.proj.agent_view(agent, self.clock.now_ms())

    def route(
        self, intent_id: str, k: int | None = None, view: Any = None
    ) -> dict[str, Any]:
        intent = self.proj.intents.get(intent_id)
        if intent is None:
            raise context("unknown intent", "intent_id")
        now = self.clock.now_ms()
        if k is not None and (not isinstance(k, int) or not 1 <= k <= 100):
            raise validation("k must be 1-100", "k")
        out = routing.route(
            self.proj, intent, now, self.parse_view(view), k=k
        ).as_dict()
        out["state"] = self.proj.state_at(intent, now)
        return out

    def sense(
        self,
        agent_id: str | None = None,
        capabilities: list[str] | None = None,
        text: str = "",
        query: str = "",
        k: int | None = None,
        view: Any = None,
    ) -> dict[str, Any]:
        now = self.clock.now_ms()
        if k is not None and (not isinstance(k, int) or not 1 <= k <= 100):
            raise validation("k must be 1-100", "k")
        if (
            not isinstance(query, str)
            or len(query) > 2000
            or not isinstance(text, str)
            or len(text) > 2000
        ):
            raise validation("query/text too long", "query")
        if agent_id is not None:
            agent = self.proj.agents.get(agent_id)
            if agent is None:
                raise context("unknown agent", "agent_id")
            caps = agent.caps
            prof_text = f"{agent.name} {agent.description} {' '.join(agent.capabilities)} {query}"
        else:
            if not isinstance(capabilities, list) or not all(
                isinstance(c, str) and TAG_RE.match(c) for c in capabilities
            ):
                raise validation("capabilities must be a list of tags", "capabilities")
            caps = frozenset(capabilities)
            prof_text = f"{text} {' '.join(capabilities)} {query}"
        hits = routing.sense(
            self.proj,
            agent_id,
            caps,
            profile(prof_text, self.p.stopwords),
            now,
            self.parse_view(view),
            k=k,
        )
        return {
            "hits": [
                {
                    "score": h.score,
                    "amplitude_eff": h.amplitude_eff,
                    "eta": h.eta,
                    "leased_by_other": h.leased_by_other,
                    "intent": self.proj.intent_view(
                        self.proj.intents[h.intent_id], now
                    ),
                }
                for h in hits
            ]
        }

    def events(self, after_seq: int = 0, limit: int = 100) -> dict[str, Any]:
        limit = max(1, min(int(limit), self.p.limits["events_limit"]))
        out = []
        for event in self.store.iter_events(int(after_seq)):
            out.append(event)
            if len(out) >= limit:
                break
        return {"events": out}

    def metrics(self) -> dict[str, Any]:
        """Semantic metrics only: no event counts, seq or hashes (decision 0002 C2)."""
        now = self.clock.now_ms()
        states: dict[str, int] = {
            "OPEN": 0,
            "COLLAPSED": 0,
            "WITHDRAWN": 0,
            "EVAPORATED": 0,
        }
        costs: list[int] = []
        buckets: dict[str, list[int]] = {"0": [], "(0,1]": [], "(1,5]": [], ">5": []}
        for i in self.proj.intents.values():
            st = self.proj.state_at(i, now)
            states[st] += 1
            if st == COLLAPSED:
                c = sum(self.proj.results[r].cost["tokens"] for r in i.results)
                costs.append(c)
                d = i.density_at_emit
                key = (
                    "0"
                    if d <= 0
                    else "(0,1]"
                    if d <= 1
                    else "(1,5]"
                    if d <= 5
                    else ">5"
                )
                buckets[key].append(c)
        terminal = states["COLLAPSED"] + states["WITHDRAWN"] + states["EVAPORATED"]
        return {
            "agents_active": sum(
                1 for a in self.proj.agents.values() if a.status == "ACTIVE"
            ),
            "intents_by_state": states,
            "collapse_rate": states["COLLAPSED"] / terminal if terminal else 0.0,
            "median_cost_to_collapse_tokens_self_reported": statistics.median(costs)
            if costs
            else None,
            "median_cost_by_density_bucket_self_reported": {
                k: (statistics.median(v) if v else None) for k, v in buckets.items()
            },
        }

    def health(self) -> dict[str, Any]:
        seq, head = self.store.head()
        return {
            "status": "ok",
            "head_seq": seq,
            "head_hash": head,
            "field_agent_id": self.signer.agent_id,
        }
