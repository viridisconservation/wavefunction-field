# SPDX-License-Identifier: Apache-2.0
"""Agent-side configuration (environment only)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

SIDE_EFFECTS = frozenset(
    {"spend", "external_comm", "access_change", "production_change"}
)


@dataclass(frozen=True)
class AgentConfig:
    field_url: str
    key_file: Path
    allow_side_effects: frozenset[str]

    @classmethod
    def from_env(cls) -> AgentConfig:
        allow = frozenset(
            x.strip()
            for x in os.environ.get("WF_ALLOW_SIDE_EFFECTS", "").split(",")
            if x.strip()
        )
        unknown = allow - SIDE_EFFECTS
        if unknown:
            raise ValueError(
                f"unknown side effects in WF_ALLOW_SIDE_EFFECTS: {sorted(unknown)}"
            )
        key = os.environ.get(
            "WF_AGENT_KEY_FILE",
            str(Path.home() / ".config/wavefunction-field/agent.key"),
        )
        return cls(
            field_url=os.environ.get("WF_FIELD_URL", "http://127.0.0.1:8787").rstrip(
                "/"
            ),
            key_file=Path(key),
            allow_side_effects=allow,
        )
