# SPDX-License-Identifier: Apache-2.0
"""Helpers for driving the HTTP app and both MCP servers in-process."""

from __future__ import annotations

import json
from typing import Any

import httpx
from mcp.shared.memory import create_connected_server_and_client_session

from tests.support import Harness
from wavefunction_field.api.http import create_app
from wavefunction_field.identity.signer import FieldSigner
from wavefunction_field.mcp.agent_server import AgentClient, build_agent_mcp


class Recorder:
    """Collects every payload that leaves a surface, for leak/wrapping scans."""

    def __init__(self) -> None:
        self.outputs: list[Any] = []

    def add(self, value: Any) -> Any:
        self.outputs.append(value)
        return value


def agent(
    h: Harness, signer: FieldSigner, allow: frozenset[str] = frozenset()
) -> AgentClient:
    app = create_app(h.svc, mount_mcp=False)
    return AgentClient(
        signer,
        "http://field.test",
        allow,
        transport=httpx.ASGITransport(app=app),
        now_ms=h.clock.now_ms,
    )


async def call(
    client: AgentClient, tool: str, rec: Recorder | None = None, **args: Any
) -> dict[str, Any]:
    async with create_connected_server_and_client_session(
        build_agent_mcp(client)
    ) as session:
        result = await session.call_tool(tool, args)
        text = result.content[0].text if result.content else "{}"  # type: ignore[union-attr]
        data: dict[str, Any] = json.loads(text)
        if rec is not None:
            rec.add(data)
        return data


async def tool_descriptions(client: AgentClient) -> list[str]:
    async with create_connected_server_and_client_session(
        build_agent_mcp(client)
    ) as session:
        tools = await session.list_tools()
        return [t.description or "" for t in tools.tools]
