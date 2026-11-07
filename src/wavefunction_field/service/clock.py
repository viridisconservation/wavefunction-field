# SPDX-License-Identifier: Apache-2.0
"""Clocks. The core never reads time; the service injects one of these."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol


class Clock(Protocol):
    def now_ms(self) -> int: ...


class SystemClock:
    def now_ms(self) -> int:
        return time.time_ns() // 1_000_000


@dataclass
class FakeClock:
    time_ms: int = 1_794_063_600_000

    def now_ms(self) -> int:
        return self.time_ms

    def advance(self, delta_ms: int) -> None:
        if delta_ms < 0:
            raise ValueError("clock cannot move backwards")
        self.time_ms += delta_ms
