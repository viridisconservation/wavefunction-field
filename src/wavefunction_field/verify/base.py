# SPDX-License-Identifier: Apache-2.0
"""Verifier interface (PROTOCOL §6)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class Verdict:
    verdict: str  # "pass" | "fail"
    reason: str = ""


class MachineVerifier(Protocol):
    kind: str

    def check_spec(self, acceptance: dict[str, Any]) -> None:
        """Raise ValidationError if the acceptance spec is unusable."""

    def verify(
        self, acceptance: dict[str, Any], artifact: dict[str, Any]
    ) -> Verdict: ...
