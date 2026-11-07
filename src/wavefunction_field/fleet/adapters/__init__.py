# SPDX-License-Identifier: Apache-2.0
"""Optional Viridis rail adapters. Each is disabled unless its env var is set (INV-FL3)."""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

import httpx


class RailCaller(Protocol):
    async def __call__(
        self, action: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...


class GatewayCaller:
    """Calls a fleet agent's MCP endpoint (streamable HTTP, JSON response).

    [CONFIRM] per rail: the tool name exposed by each agent's MCP adapter is
    assumed to equal the contract action name (e.g. ``score``, ``resolve``).
    """

    def __init__(self, url: str, timeout: float = 10.0) -> None:
        self.url = url
        self.http = httpx.AsyncClient(timeout=timeout, follow_redirects=False)
        self._id = 0

    async def __call__(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._id += 1
        req = {
            "jsonrpc": "2.0",
            "id": self._id,
            "method": "tools/call",
            "params": {"name": action, "arguments": payload},
        }
        headers = {"accept": "application/json, text/event-stream"}
        resp = await self.http.post(self.url, json=req, headers=headers)
        data = resp.json()
        content = data.get("result", {}).get("content", [])
        if content and content[0].get("type") == "text":
            out: dict[str, Any] = json.loads(content[0]["text"])
            return out
        return {"error": data.get("error", {"message": "empty response"})}


def caller_from_env(name: str) -> GatewayCaller | None:
    url = os.environ.get(name, "").strip()
    return GatewayCaller(url) if url else None
