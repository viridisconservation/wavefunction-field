# SPDX-License-Identifier: Apache-2.0
"""TrustSource backed by agent-trust-oracle (``score`` action)."""

from __future__ import annotations

import os

from wavefunction_field.fleet.adapters import RailCaller, caller_from_env


class TrustOracleSource:
    """Agents scoring >= min_score join the default trust view candidates."""

    def __init__(self, call: RailCaller, min_score: float = 0.85) -> None:
        self.call = call
        self.min_score = min_score

    async def trusted(self, agent_ids: list[str]) -> list[str]:
        out = []
        for aid in sorted(agent_ids):
            res = await self.call("score", {"agent_id": aid})
            score = res.get("score")
            if isinstance(score, int | float) and score >= self.min_score:
                out.append(aid)
        return out

    @classmethod
    def from_env(cls) -> TrustOracleSource | None:
        caller = caller_from_env("WF_TRUST_ORACLE_URL")
        if caller is None:
            return None
        return cls(caller, float(os.environ.get("WF_TRUST_MIN_SCORE", "0.85")))
