# SPDX-License-Identifier: Apache-2.0
"""The shipped demo runs, and the field MCP is reachable at /mcp over HTTP."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

from starlette.testclient import TestClient

from tests.support import Harness
from wavefunction_field.api.http import create_app

ROOT = Path(__file__).resolve().parents[2]


def test_two_agents_demo_runs() -> None:
    spec = importlib.util.spec_from_file_location(
        "demo", ROOT / "examples/two_agents_demo.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = asyncio.run(mod.main())
    assert out["intent_state"] == "COLLAPSED"
    assert out["bob_carbon_trail"] > 0.05


def test_mcp_mounted_over_streamable_http() -> None:
    h = Harness()
    with TestClient(
        create_app(h.svc, public_url="https://field.example"),
        base_url="https://field.example",
    ) as c:
        headers = {
            "accept": "application/json, text/event-stream",
            "content-type": "application/json",
        }
        init = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "t", "version": "0"},
            },
        }
        r = c.post("/mcp", json=init, headers=headers)
        assert r.status_code == 200, r.text
        r = c.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=headers,
        )
        names = {t["name"] for t in r.json()["result"]["tools"]}
        assert "sense" in names and "submit_signed" in names
        assert c.get("/healthz").json()["status"] == "ok"
