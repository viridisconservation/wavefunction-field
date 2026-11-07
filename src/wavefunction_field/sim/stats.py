# SPDX-License-Identifier: Apache-2.0
"""Dependency-free statistics used by the preregistered tests."""

from __future__ import annotations

import math
from collections.abc import Sequence


def ranks(values: Sequence[float]) -> list[float]:
    """1-based ranks with ties given their average rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def pearson(x: Sequence[float], y: Sequence[float]) -> float:
    n = len(x)
    if n < 2:
        return math.nan
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx == 0 or syy == 0:
        return math.nan
    return sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True)) / math.sqrt(
        sxx * syy
    )


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    return pearson(ranks(x), ranks(y))


def mean(x: Sequence[float]) -> float:
    return sum(x) / len(x) if x else math.nan


def median(x: Sequence[float]) -> float:
    s = sorted(x)
    n = len(s)
    if n == 0:
        return math.nan
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0
