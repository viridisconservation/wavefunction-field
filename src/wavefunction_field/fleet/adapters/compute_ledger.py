# SPDX-License-Identifier: Apache-2.0
"""CostSink backed by agent-compute-ledger (``record_work`` action)."""

from __future__ import annotations

from typing import Any

from wavefunction_field.fleet.adapters import RailCaller, caller_from_env


class ComputeLedgerSink:
    def __init__(self, call: RailCaller) -> None:
        self.call = call

    async def record(self, result: dict[str, Any]) -> dict[str, Any]:
        cost = result.get("cost_report_self_reported", {})
        return await self.call(
            "record_work",
            {
                "agent_id": result.get("doer"),
                "job_id": result.get("result_id"),
                "tokens": cost.get("tokens", 0),
                "wall_ms": cost.get("wall_ms", 0),
                "source": "wavefunction-field (self-reported)",
            },
        )

    @classmethod
    def from_env(cls) -> ComputeLedgerSink | None:
        caller = caller_from_env("WF_COMPUTE_LEDGER_URL")
        return cls(caller) if caller else None
