# SPDX-License-Identifier: Apache-2.0
"""IdentitySource backed by agent-identity-registry (``resolve`` action)."""

from __future__ import annotations

from wavefunction_field.fleet.adapters import RailCaller, caller_from_env


class IdentityRegistrySource:
    def __init__(self, call: RailCaller) -> None:
        self.call = call

    async def pubkey(self, agent_id: str) -> str | None:
        res = await self.call("resolve", {"agent_id": agent_id})
        reg = res.get("registration", res)
        if not isinstance(reg, dict) or reg.get("status", "ACTIVE") != "ACTIVE":
            return None
        key = reg.get("pubkey")
        return key if isinstance(key, str) else None

    @classmethod
    def from_env(cls) -> IdentityRegistrySource | None:
        caller = caller_from_env("WF_IDENTITY_REGISTRY_URL")
        return cls(caller) if caller else None
