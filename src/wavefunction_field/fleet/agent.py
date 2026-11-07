# SPDX-License-Identifier: Apache-2.0
"""Fleet contract adapter for ``wavefunction-search-agent`` (Harness Playbook v1.1).

``process(input)`` never raises (INV-FL1); every output carries session_id and
budget_consumed (INV-FL2); routing returns the full distribution and amplitudes
ψ with Σψ² = 1 (fleet I-6); with an IdentitySource configured, agents whose
registry pubkey is missing or different are excluded (INV-FL4).
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from typing import Any

from wavefunction_field import __version__
from wavefunction_field.api.manifest import manifest
from wavefunction_field.core.errors import WFPError
from wavefunction_field.fleet.adapters.compute_ledger import ComputeLedgerSink
from wavefunction_field.fleet.adapters.identity_registry import IdentityRegistrySource
from wavefunction_field.service.field import FieldService

# Fleet-contract version of the wavefunction-search-agent mount (agent.yaml);
# the prototype it replaces shipped 0.1.x (production) and 0.2.0 (open core).
FLEET_VERSION = "0.3.0"
ACTIONS = ("sense", "route", "get_intent", "list_intents", "field_info", "write")


class WavefunctionSearchAgent:
    name = "wavefunction-search-agent"

    def __init__(
        self,
        svc: FieldService,
        *,
        identity: IdentityRegistrySource | None = None,
        ledger: ComputeLedgerSink | None = None,
        session_id: str | None = None,
    ) -> None:
        self.svc = svc
        self.identity = identity
        self.ledger = ledger
        self.session_id = session_id or "sess_" + uuid.uuid4().hex[:16]
        self.calls = 0

    def _wrap(self, body: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        return {
            **body,
            "status": "ok" if body.get("ok") else "error",
            "session_id": self.session_id,
            "budget_consumed": {"calls": self.calls},
        }

    async def process(self, input: Any) -> dict[str, Any]:
        try:
            if not isinstance(input, dict):
                raise WFPError("ValidationError", "input must be an object")
            action = input.get("action")
            if action not in ACTIONS:
                raise WFPError(
                    "ValidationError",
                    f"unknown action; expected one of {', '.join(ACTIONS)}",
                    field="action",
                )
            if action == "sense":
                out = self.svc.sense(
                    agent_id=input.get("agent_id"),
                    capabilities=input.get("capabilities"),
                    query=input.get("query", ""),
                    k=input.get("k"),
                    view=input.get("view"),
                )
            elif action == "route":
                out = await self._route(input)
            elif action == "get_intent":
                out = self.svc.get_intent(str(input.get("intent_id", "")))
            elif action == "list_intents":
                out = self.svc.list_intents(
                    input.get("state"),
                    input.get("tag"),
                    input.get("emitter"),
                    int(input.get("limit", 50)),
                    input.get("cursor"),
                )
            elif action == "field_info":
                out = manifest(self.svc)
            else:
                out = self.svc.apply(input.get("request"))
                if self.ledger is not None and out.get("intent_state") == "COLLAPSED":
                    res = self.svc.proj.result_view(
                        self.svc.proj.results[out["result_id"]], self.svc.clock.now_ms()
                    )
                    out["ledger"] = await self.ledger.record(res)
            return self._wrap({"ok": True, "result": out})
        except WFPError as exc:
            return self._wrap({"ok": False, "error": exc.envelope()})
        except Exception as exc:  # noqa: BLE001 - the fleet contract forbids raising
            return self._wrap(
                {
                    "ok": False,
                    "error": {
                        "error_type": "RuntimeError",
                        "message": type(exc).__name__,
                    },
                }
            )

    async def _route(self, input: dict[str, Any]) -> dict[str, Any]:
        out = self.svc.route(
            str(input.get("intent_id", "")), input.get("k"), input.get("view")
        )
        dist: dict[str, float] = dict(out["distribution"])
        if self.identity is not None:
            for aid in sorted(dist):
                agent = self.svc.proj.agents.get(aid)
                if agent is None or await self.identity.pubkey(aid) != agent.pubkey:
                    dist.pop(aid)
            total = sum(dist.values())
            dist = {a: p / total for a, p in sorted(dist.items())} if total > 0 else {}
            out["entries"] = [
                dict(e, p=dist[e["agent_id"]], psi=math.sqrt(dist[e["agent_id"]]))
                for e in out["entries"]
                if e["agent_id"] in dist
            ]
        out["distribution"] = dist
        out["amplitudes"] = {a: math.sqrt(p) for a, p in dist.items()}
        return out

    async def health(self) -> dict[str, Any]:
        h = self.svc.health()
        return {
            "status": h["status"],
            "agent": self.name,
            "version": FLEET_VERSION,
            "implementation": f"wavefunction-field {__version__}",
            "timestamp": datetime.now(UTC).isoformat(),
            "checks": {"store_head_seq": h["head_seq"]},
        }

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": FLEET_VERSION,
            "implementation": f"wavefunction-field {__version__}",
            "capabilities": ["intent-routing", "stigmergic-field", "verified-trails"],
            "inputs": {"action": list(ACTIONS)},
            "outputs": [
                "full routing distribution with amplitudes",
                "sense rankings",
                "intent read models",
            ],
            "a2a_role": "router",
        }
