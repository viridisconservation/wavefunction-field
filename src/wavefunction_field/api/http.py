# SPDX-License-Identifier: Apache-2.0
"""Starlette HTTP surface (PROTOCOL §10.1) with the field MCP server mounted at /mcp."""

from __future__ import annotations

import contextlib
import json
from collections.abc import AsyncIterator
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from wavefunction_field.api.manifest import manifest
from wavefunction_field.core.errors import HTTP_STATUS, WFPError
from wavefunction_field.service.field import FieldService

MAX_BODY = 256 * 1024


def _err(exc: WFPError) -> JSONResponse:
    return JSONResponse(
        exc.envelope(), status_code=HTTP_STATUS.get(exc.error_type, 400)
    )


def _bad(message: str) -> JSONResponse:
    return JSONResponse(
        {"error_type": "ValidationError", "message": message}, status_code=400
    )


async def _json(request: Request) -> Any:
    raw = await request.body()
    if len(raw) > MAX_BODY:
        raise WFPError(
            "ValidationError", "request body too large", constraint="max_bytes"
        )
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise WFPError("ValidationError", "body is not valid JSON") from None


def _int_param(request: Request, name: str, default: int) -> int:
    value = request.query_params.get(name)
    if value is None:
        return default
    if not value.isdigit():
        raise WFPError(
            "ValidationError", f"{name} must be a non-negative integer", field=name
        )
    return int(value)


def rest_routes(svc: FieldService, public_url: str = "") -> list[Route]:
    """The REST surface as plain routes (reused by the fleet gateway mount)."""

    async def guarded(fn: Any) -> JSONResponse:
        try:
            return JSONResponse(fn())
        except WFPError as exc:
            return _err(exc)
        except (
            KeyError,
            TypeError,
            ValueError,
            AttributeError,
        ) as exc:  # malformed input (INV-SF7)
            return _bad(f"malformed request: {type(exc).__name__}")

    async def write(request: Request) -> JSONResponse:
        try:
            body = await _json(request)
        except WFPError as exc:
            return _err(exc)
        return await guarded(lambda: svc.apply(body))

    async def sense(request: Request) -> JSONResponse:
        try:
            body = await _json(request)
        except WFPError as exc:
            return _err(exc)
        if not isinstance(body, dict):
            return _bad("body must be an object")
        allowed = {"agent_id", "capabilities", "text", "query", "k", "view"}
        if set(body) - allowed:
            return _bad("unknown field")
        return await guarded(lambda: svc.sense(**body))

    async def route(request: Request) -> JSONResponse:
        try:
            body = await _json(request)
        except WFPError as exc:
            return _err(exc)
        if not isinstance(body, dict) or not isinstance(body.get("intent_id"), str):
            return _bad("intent_id is required")
        if set(body) - {"intent_id", "k", "view"}:
            return _bad("unknown field")
        return await guarded(
            lambda: svc.route(body["intent_id"], body.get("k"), body.get("view"))
        )

    async def get_intent(request: Request) -> JSONResponse:
        return await guarded(lambda: svc.get_intent(request.path_params["intent_id"]))

    async def list_intents(request: Request) -> JSONResponse:
        q = request.query_params
        return await guarded(
            lambda: svc.list_intents(
                q.get("state"),
                q.get("tag"),
                q.get("emitter"),
                _int_param(request, "limit", 50),
                q.get("cursor"),
            )
        )

    async def get_agent(request: Request) -> JSONResponse:
        return await guarded(lambda: svc.get_agent(request.path_params["agent_id"]))

    async def events(request: Request) -> JSONResponse:
        return await guarded(
            lambda: svc.events(
                _int_param(request, "after_seq", 0), _int_param(request, "limit", 100)
            )
        )

    async def metrics(request: Request) -> JSONResponse:
        return await guarded(svc.metrics)

    async def well_known(request: Request) -> JSONResponse:
        return JSONResponse(manifest(svc, public_url))

    async def healthz(request: Request) -> JSONResponse:
        return JSONResponse(svc.health())

    return [
        Route("/v1/write", write, methods=["POST"]),
        Route("/v1/sense", sense, methods=["POST"]),
        Route("/v1/route", route, methods=["POST"]),
        Route("/v1/intents/{intent_id}", get_intent, methods=["GET"]),
        Route("/v1/intents", list_intents, methods=["GET"]),
        Route("/v1/agents/{agent_id}", get_agent, methods=["GET"]),
        Route("/v1/events", events, methods=["GET"]),
        Route("/v1/metrics", metrics, methods=["GET"]),
        Route("/.well-known/wavefunction-field.json", well_known, methods=["GET"]),
        Route("/healthz", healthz, methods=["GET"]),
    ]


def create_app(
    svc: FieldService, *, public_url: str = "", mount_mcp: bool = True
) -> Starlette:
    routes: list[Any] = list(rest_routes(svc, public_url))
    lifespan = None
    if mount_mcp:
        from wavefunction_field.mcp.field_server import build_field_mcp

        fm = build_field_mcp(svc, public=bool(public_url))
        mcp_app = fm.streamable_http_app()
        routes.append(Mount("/", app=mcp_app))

        @contextlib.asynccontextmanager
        async def lifespan_cm(app: Starlette) -> AsyncIterator[None]:
            async with fm.session_manager.run():
                yield

        lifespan = lifespan_cm
    return Starlette(routes=routes, lifespan=lifespan)
