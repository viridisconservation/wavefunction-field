# SPDX-License-Identifier: Apache-2.0
"""Per-client admission control (api/throttle.py, TH1-TH5)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from wavefunction_field.api.throttle import Limit, Throttle

pytestmark = pytest.mark.anyio


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def _app() -> tuple[Starlette, list[Any]]:
    seen: list[Any] = []

    async def write(request: Request) -> JSONResponse:
        body = await request.body()
        seen.append(json.loads(body))
        return JSONResponse({"ok": True, "echo": json.loads(body)})

    async def read(request: Request) -> JSONResponse:
        seen.append("read")
        return JSONResponse({"ok": True})

    return Starlette(
        routes=[
            Route("/wavefunction/v1/write", write, methods=["POST"]),
            Route("/wavefunction/v1/sense", read, methods=["POST"]),
            Route("/wavefunction/healthz", read),
        ]
    ), seen


def _client(th: Throttle) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=th), base_url="http://t")


def _env(action: str, i: int = 0) -> dict[str, Any]:
    return {
        "envelope": {"action": action, "nonce": f"n{i:08d}", "body": {"x": i}},
        "pubkey": "p",
        "signature": "s",
    }


def _ip(addr: str) -> dict[str, str]:
    return {"x-forwarded-for": addr}


async def test_th1_admitted_requests_pass_unchanged() -> None:
    app, seen = _app()
    async with _client(Throttle(app, clock=Clock())) as c:
        r = await c.post(
            "/wavefunction/v1/write",
            json=_env("emit_intent", 7),
            headers=_ip("1.1.1.1"),
        )
    assert r.status_code == 200 and r.json()["echo"] == _env("emit_intent", 7)
    assert seen == [_env("emit_intent", 7)]


async def test_th2_over_limit_is_429_and_never_reaches_app() -> None:
    app, seen = _app()
    clock = Clock()
    th = Throttle(app, limits={"write": Limit.per_minute(3)}, clock=clock)
    async with _client(th) as c:
        codes = [
            (
                await c.post(
                    "/wavefunction/v1/write",
                    json=_env("emit_intent", i),
                    headers=_ip("2.2.2.2"),
                )
            ).status_code
            for i in range(5)
        ]
        r = await c.post(
            "/wavefunction/v1/write",
            json=_env("emit_intent", 9),
            headers=_ip("2.2.2.2"),
        )
        assert codes == [200, 200, 200, 429, 429]
        assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1
        assert r.json()["error_type"] == "RateLimited"
        assert len(seen) == 3
        clock.t += 20.0  # one token refilled (3 per 60 s)
        ok = await c.post(
            "/wavefunction/v1/write",
            json=_env("emit_intent", 10),
            headers=_ip("2.2.2.2"),
        )
        assert ok.status_code == 200


async def test_th3_buckets_are_per_client() -> None:
    app, _ = _app()
    th = Throttle(app, limits={"compute": Limit.per_minute(2)}, clock=Clock())
    async with _client(th) as c:
        a = [
            (
                await c.post("/wavefunction/v1/sense", json={}, headers=_ip("3.3.3.3"))
            ).status_code
            for _ in range(3)
        ]
        b = (
            await c.post("/wavefunction/v1/sense", json={}, headers=_ip("4.4.4.4"))
        ).status_code
    assert a == [200, 200, 429] and b == 200


async def test_forwarded_uses_last_hop_only() -> None:
    app, _ = _app()
    th = Throttle(app, limits={"read": Limit.per_minute(1)}, clock=Clock())
    async with _client(th) as c:
        first = await c.get("/wavefunction/healthz", headers=_ip("9.9.9.9, 5.5.5.5"))
        spoof = await c.get("/wavefunction/healthz", headers=_ip("8.8.8.8, 5.5.5.5"))
    assert first.status_code == 200 and spoof.status_code == 429


async def test_th4_registrations_draw_on_global_budget() -> None:
    app, _ = _app()
    th = Throttle(
        app,
        limits={"write": Limit.per_minute(100), "register": Limit.per_hour(2)},
        global_register=Limit.per_hour(3),
        clock=Clock(),
    )
    async with _client(th) as c:
        per_client = [
            (
                await c.post(
                    "/wavefunction/v1/write",
                    json=_env("register_agent", i),
                    headers=_ip("6.6.6.6"),
                )
            ).status_code
            for i in range(3)
        ]
        other = [
            (
                await c.post(
                    "/wavefunction/v1/write",
                    json=_env("register_agent", i),
                    headers=_ip(f"7.7.7.{i}"),
                )
            ).status_code
            for i in range(3)
        ]
        emit = await c.post(
            "/wavefunction/v1/write", json=_env("emit_intent"), headers=_ip("6.6.6.6")
        )
    assert per_client == [200, 200, 429]
    assert other == [200, 429, 429]  # global budget of 3 spent (2 + 1)
    assert emit.status_code == 200  # other writes are unaffected


def test_th5_state_is_bounded() -> None:
    app, _ = _app()
    clock = Clock()
    th = Throttle(app, max_clients=100, clock=clock)
    for i in range(1000):
        th._admit(f"10.0.{i // 256}.{i % 256}", "read", clock())
        clock.t += 0.001
    assert len(th.buckets) <= 100


@pytest.mark.parametrize("off", ["off", "0", "false"])
def test_kill_switch(monkeypatch: pytest.MonkeyPatch, off: str) -> None:
    from wavefunction_field.api import throttle

    monkeypatch.setenv("WF_RATE_LIMITS", off)
    assert not throttle.enabled()
