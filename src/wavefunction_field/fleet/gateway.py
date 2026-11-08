# SPDX-License-Identifier: Apache-2.0
"""Mount surface for the Viridis fleet gateway (``/wavefunction``).

The gateway loads ``wavefunction-search-agent/adapters/mcp_server.py`` and reads
two module attributes: ``mcp`` (a FastMCP server, mounted at /wavefunction) and
``agent`` (the fleet-contract core it persists with pickle snapshots).

The field keeps its own durable, hash-chained SQLite log, so ``agent`` holds no
instance state of its own: gateway snapshots of it are empty (no-op writes) and
can never fork or roll back field history.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from wavefunction_field.fleet.agent import WavefunctionSearchAgent
from wavefunction_field.mcp.field_server import build_field_mcp
from wavefunction_field.service.runtime import build_service

_FIELD: WavefunctionSearchAgent | None = None


def _defaults() -> None:
    data = Path("/data")
    if data.is_dir() and os.access(data, os.W_OK):
        base = data
    else:  # tests / golden fixtures: never litter the working tree
        base = Path(tempfile.mkdtemp(prefix="wavefunction-field-"))
    os.environ.setdefault("WF_DB_PATH", str(base / "wavefunction_field.sqlite3"))
    os.environ.setdefault("WF_FIELD_KEY_FILE", str(base / "wavefunction_field.key"))
    public = os.environ.get(
        "PUBLIC_BASE", "https://mcp.viridisconservation.com"
    ).rstrip("/")
    os.environ.setdefault("WF_PUBLIC_URL", public + "/wavefunction")


class GatewayAgent:
    """Stateless fleet core: delegates to the module-level field agent."""

    def _field(self) -> WavefunctionSearchAgent:
        if _FIELD is None:
            raise RuntimeError("field not initialised")
        return _FIELD

    async def process(self, input: Any) -> dict[str, Any]:
        return await self._field().process(input)

    async def health(self) -> dict[str, Any]:
        return await self._field().health()

    def describe(self) -> dict[str, Any]:
        return self._field().describe()


def build_gateway_surface() -> tuple[FastMCP, GatewayAgent]:
    global _FIELD
    _defaults()
    # Optional pre-genesis config written by the release (trusted emitters,
    # operators). It only matters before the first boot: the default trust
    # view is fixed in the genesis event.
    config = os.environ.get("WF_CONFIG_FILE") or str(
        Path(os.environ["WF_DB_PATH"]).with_name("wavefunction_field.config.json")
    )
    svc, cfg = build_service(config if Path(config).is_file() else None)
    _FIELD = WavefunctionSearchAgent(svc)
    fm = build_field_mcp(svc, public=True, rest=True, public_url=cfg.public_url)
    from wavefunction_field.api import throttle

    if throttle.enabled():
        # The gateway mounts fm.streamable_http_app(); wrap it with per-client
        # admission control (agent ids are free to mint, client IPs are not).
        inner = fm.streamable_http_app
        fm.streamable_http_app = lambda: throttle.Throttle(inner())  # type: ignore[method-assign,assignment,return-value]
    return fm, GatewayAgent()
