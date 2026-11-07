# SPDX-License-Identifier: Apache-2.0
"""Two agents complete one intent end to end, fully in-process (no sockets).

Run:  python examples/two_agents_demo.py
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import httpx

from wavefunction_field.api.http import create_app
from wavefunction_field.identity.keys import load_or_create_key
from wavefunction_field.identity.signer import FieldSigner
from wavefunction_field.mcp.agent_server import AgentClient
from wavefunction_field.service.clock import SystemClock
from wavefunction_field.service.config import load_params
from wavefunction_field.service.field import FieldService
from wavefunction_field.store.sqlite import SQLiteStore


async def main() -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="wf-demo-"))
    alice = FieldSigner(load_or_create_key(tmp / "alice.key"))
    bob = FieldSigner(load_or_create_key(tmp / "bob.key"))
    svc = FieldService(
        SQLiteStore(tmp / "field.sqlite3"),
        load_params(),
        SystemClock(),
        FieldSigner(load_or_create_key(tmp / "field.key")),
        trusted_emitters=[alice.agent_id],
    )
    transport = httpx.ASGITransport(app=create_app(svc, mount_mcp=False))
    a = AgentClient(alice, "http://field.local", frozenset(), transport=transport)
    b = AgentClient(bob, "http://field.local", frozenset(), transport=transport)

    await a.write(
        "register_agent", {"name": "Alice (emitter)", "capabilities": ["ops"]}
    )
    await b.write(
        "register_agent",
        {"name": "Bob (carbon analyst)", "capabilities": ["carbon", "disclosure"]},
    )
    schema = {
        "type": "object",
        "required": ["scope1_tco2e"],
        "properties": {"scope1_tco2e": {"type": "number"}},
    }
    emitted = await a.write(
        "emit_intent",
        {
            "goal": "Compute scope 1 emissions for the supplied fuel log",
            "hypotheses": [
                {"id": "h1", "summary": "Use emission factors directly", "weight": 3},
                {
                    "id": "h2",
                    "summary": "Route through a GHG ledger agent",
                    "weight": 1,
                },
            ],
            "acceptance": {"kind": "json_schema", "schema": schema},
            "priority": 6,
            "ttl_s": 3600,
            "capabilities_needed": ["carbon"],
        },
    )
    iid = emitted["intent_id"]
    sensed = await b.post("/v1/sense", {"agent_id": bob.agent_id})
    assert sensed["hits"][0]["intent"]["intent_id"] == iid
    await b.write("deposit", {"intent_id": iid, "kind": "claim", "lease_s": 600})
    answer = json.dumps({"scope1_tco2e": 12.4})
    result = await b.write(
        "submit_result",
        {
            "intent_id": iid,
            "hypothesis_id": "h1",
            "artifact": {
                "content_type": "application/json",
                "inline": answer,
                "sha256": hashlib.sha256(answer.encode()).hexdigest(),
            },
            "cost_report": {"tokens": 1800, "wall_ms": 2400},
        },
    )
    agent_view = await a.get(f"/v1/agents/{bob.agent_id}")
    summary = {
        "intent_id": iid,
        "result_state": result["state"],
        "intent_state": result["intent_state"],
        "bob_carbon_trail": agent_view["trails"]["carbon"],
        "route_after": (await a.post("/v1/route", {"intent_id": iid}))["entries"][:1],
    }
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    asyncio.run(main())
