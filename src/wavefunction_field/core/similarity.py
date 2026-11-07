# SPDX-License-Identifier: Apache-2.0
"""Deterministic, offline lexical similarity (PROTOCOL §7.4)."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

_SPLIT = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class TextProfile:
    """Pre-tokenised text: term frequencies and their L2 norm."""

    tf: dict[str, int]
    norm: float


def tokens(text: str, stopwords: frozenset[str]) -> list[str]:
    return [
        tok
        for tok in _SPLIT.split(text.lower())
        if len(tok) >= 2 and tok not in stopwords
    ]


def profile(text: str, stopwords: frozenset[str]) -> TextProfile:
    tf = dict(Counter(tokens(text, stopwords)))
    norm = math.sqrt(sum(v * v for v in tf.values()))
    return TextProfile(tf, norm)


def cosine(a: TextProfile, b: TextProfile) -> float:
    if a.norm == 0.0 or b.norm == 0.0:
        return 0.0
    small, large = (a.tf, b.tf) if len(a.tf) <= len(b.tf) else (b.tf, a.tf)
    dot = sum(v * large.get(k, 0) for k, v in small.items())
    return dot / (a.norm * b.norm)


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


class Similarity(Protocol):
    def score(
        self,
        tags_a: frozenset[str],
        text_a: TextProfile,
        tags_b: frozenset[str],
        text_b: TextProfile,
    ) -> float: ...


@dataclass(frozen=True, slots=True)
class LexicalSimilarity:
    w_tag: float
    w_text: float

    def score(
        self,
        tags_a: frozenset[str],
        text_a: TextProfile,
        tags_b: frozenset[str],
        text_b: TextProfile,
    ) -> float:
        return self.w_tag * jaccard(tags_a, tags_b) + self.w_text * cosine(
            text_a, text_b
        )
