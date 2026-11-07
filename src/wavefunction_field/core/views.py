# SPDX-License-Identifier: Apache-2.0
"""Observer trust views (PROTOCOL §7)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from wavefunction_field.core.canonical import digest


@dataclass(frozen=True, slots=True)
class TrustView:
    verifiers: frozenset[str]
    emitters: frozenset[str]

    @classmethod
    def of(
        cls, verifiers: Iterable[str] = (), emitters: Iterable[str] = ()
    ) -> TrustView:
        return cls(frozenset(verifiers), frozenset(emitters))

    @property
    def trusted(self) -> frozenset[str]:
        return self.verifiers | self.emitters

    def key(self) -> str:
        return digest(
            {"emitters": sorted(self.emitters), "verifiers": sorted(self.verifiers)}
        )

    def as_dict(self) -> dict[str, list[str]]:
        return {"emitters": sorted(self.emitters), "verifiers": sorted(self.verifiers)}
