# SPDX-License-Identifier: Apache-2.0
"""The gateway mount: MCP and REST under /wavefunction; empty pickle snapshots."""

from __future__ import annotations

import asyncio
import contextlib
import pickle
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient

from tests.support import seeded
from wavefunction_field.fleet import gateway
from wavefunction_field.identity.envelope import format_ms


def test_gateway_surface_mounts_mcp_and_rest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WF_DB_PATH", str(tmp_path / "f.sqlite3"))
    monkeypatch.setenv("WF_FIELD_KEY_FILE", str(tmp_path / "f.key"))
    monkeypatch.setenv("PUBLIC_BASE", "https://gw.example")
    monkeypatch.delenv("WF_PUBLIC_URL", raising=False)
    fm, agent = gateway.build_gateway_surface()
    assert vars(agent) == {}
    assert pickle.loads(pickle.dumps(vars(agent))) == {}

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with fm.session_manager.run():
            yield

    app = Starlette(
        routes=[Mount("/wavefunction", app=fm.streamable_http_app())], lifespan=lifespan
    )
    h = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
    }
    with TestClient(app, base_url="https://gw.example") as c:
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
        assert c.post("/wavefunction/mcp", json=init, headers=h).status_code == 200
        tools = c.post(
            "/wavefunction/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=h,
        ).json()
        assert "describe_agent" in {t["name"] for t in tools["result"]["tools"]}
        m = c.get("/wavefunction/.well-known/wavefunction-field.json").json()
        assert m["endpoints"]["mcp"] == "https://gw.example/wavefunction/mcp"
        a = seeded(1)
        now = int(__import__("time").time() * 1000)
        req = a.request(
            "register_agent",
            {"name": "a", "capabilities": ["ops"]},
            signed_at=format_ms(now),
        )
        assert c.post("/wavefunction/v1/write", json=req).json()["status"] == "ACTIVE"
        assert c.get("/wavefunction/healthz").json()["status"] == "ok"
    out = asyncio.run(agent.process({"action": "field_info"}))
    assert out["ok"] and "session_id" in out
    assert asyncio.run(agent.health())["agent"] == "wavefunction-search-agent"


def test_gateway_reads_pre_genesis_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    op = seeded(42)
    (tmp_path / "wavefunction_field.config.json").write_text(
        json.dumps(
            {
                "db_path": str(tmp_path / "wavefunction_field.sqlite3"),
                "field_key_path": str(tmp_path / "wavefunction_field.key"),
                "trusted_emitters": [op.agent_id],
                "operators": [op.agent_id],
            }
        )
    )
    monkeypatch.setenv("WF_DB_PATH", str(tmp_path / "wavefunction_field.sqlite3"))
    monkeypatch.setenv("WF_FIELD_KEY_FILE", str(tmp_path / "wavefunction_field.key"))
    monkeypatch.delenv("WF_CONFIG_FILE", raising=False)
    gateway.build_gateway_surface()
    assert gateway._FIELD is not None
    view = gateway._FIELD.svc.default_view
    assert (
        op.agent_id in view.emitters
        and op.agent_id in gateway._FIELD.svc.proj.operators
    )


def test_gateway_mount_applies_per_client_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TH2/TH3 through the real gateway mount: sense is limited per client IP."""
    monkeypatch.setenv("WF_DB_PATH", str(tmp_path / "f.sqlite3"))
    monkeypatch.setenv("WF_FIELD_KEY_FILE", str(tmp_path / "f.key"))
    monkeypatch.delenv("WF_RATE_LIMITS", raising=False)
    fm, _ = gateway.build_gateway_surface()
    app = Starlette(routes=[Mount("/wavefunction", app=fm.streamable_http_app())])
    body = {"capabilities": ["carbon"]}
    with TestClient(app) as c:
        a = [
            c.post(
                "/wavefunction/v1/sense",
                json=body,
                headers={"x-forwarded-for": "1.2.3.4"},
            ).status_code
            for _ in range(61)
        ]
        b = c.post(
            "/wavefunction/v1/sense", json=body, headers={"x-forwarded-for": "5.6.7.8"}
        ).status_code
    assert a[:60] == [200] * 60 and a[60] == 429 and b == 200


def test_gateway_mount_serves_leaderboard_and_badge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WF_DB_PATH", str(tmp_path / "f.sqlite3"))
    monkeypatch.setenv("WF_FIELD_KEY_FILE", str(tmp_path / "f.key"))
    fm, _ = gateway.build_gateway_surface()
    app = Starlette(routes=[Mount("/wavefunction", app=fm.streamable_http_app())])
    with TestClient(app) as c:
        assert c.get("/wavefunction/v1/leaderboard").json()["agents"] == []
        page = c.get("/wavefunction/leaderboard")
        assert page.status_code == 200 and "Wavefunction Field leaderboard" in page.text
        badge = c.get("/wavefunction/v1/agents/wf1_nobody/badge.svg")
        assert badge.status_code == 200 and "not registered" in badge.text
