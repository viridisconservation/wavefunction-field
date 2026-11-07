# SPDX-License-Identifier: Apache-2.0
"""Hypothesis entropy (PROTOCOL §3.2)."""

from __future__ import annotations

import math
from collections.abc import Sequence


def probabilities(weights: Sequence[int]) -> list[float]:
    total = sum(weights)
    if total <= 0 or any(w <= 0 for w in weights):
        raise ValueError("weights must be positive integers")
    return [w / total for w in weights]


def entropy_bits(weights: Sequence[int]) -> float:
    """H = -sum p log2 p with p from positive integer weights."""
    if len(weights) == 1:
        if weights[0] <= 0:
            raise ValueError("weights must be positive integers")
        return 0.0
    return -sum(p * math.log2(p) for p in probabilities(weights))
