# SPDX-License-Identifier: Apache-2.0
"""Bounded, deterministic resonance linking (PROTOCOL §7.1, decision 0002 C1)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping


def links_for(
    new_id: str,
    candidates: Iterable[tuple[str, float]],
    degree: Mapping[str, int],
    theta: float,
    cap: int,
) -> list[str]:
    """Choose link partners for a newly emitted intent.

    ``candidates`` are (intent_id, sim) for OPEN intents other than ``new_id``.
    Visit by sim descending then id ascending; link iff both endpoints are
    below ``cap``. Links are permanent, so ``degree`` counts all recorded links.
    """
    ordered = sorted(
        ((jid, s) for jid, s in candidates if jid != new_id and s >= theta),
        key=lambda x: (-x[1], x[0]),
    )
    chosen: list[str] = []
    for jid, _ in ordered:
        if len(chosen) >= cap:
            break
        if degree.get(jid, 0) < cap:
            chosen.append(jid)
    return chosen


def symmetric(links: Mapping[str, set[str]]) -> bool:
    return all(
        i in links.get(j, set()) and i != j for i, js in links.items() for j in js
    )


SimFn = Callable[[str, str], float]
