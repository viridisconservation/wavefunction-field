# SPDX-License-Identifier: Apache-2.0
"""Immutable field parameters (spec/params.json).

Loading from disk happens outside ``core`` (see ``service.config``); this module
only turns an already-parsed mapping into a frozen object.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from wavefunction_field.core.canonical import digest


def _strip_comment(raw: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in raw.items() if k != "$comment"}


@dataclass(frozen=True, slots=True)
class FieldParams:
    raw: dict[str, Any] = field(repr=False, compare=False)
    sha256: str
    # auth
    skew_s: int
    nonce_pattern: str
    # amplitude
    A_max: float
    a_per_priority: float
    h_A_s: float
    A_alive: float
    delta_signal: float
    untrusted_signal_cap: float
    # resonance
    theta_res: float
    gamma_res: float
    max_links: int
    # trail
    r_base: float
    r_fail: float
    h_trail_s: float
    w_min: float
    w_max: float
    # route
    route_alpha: float
    route_beta: float
    eta_min: float
    route_k: int
    route_k_explore: int
    max_candidates: int
    # sense
    sense_alpha: float
    sense_beta: float
    lambda_lease: float
    sense_k: int
    # similarity
    w_tag: float
    w_text: float
    stopwords: frozenset[str]
    # intent / lease
    ttl_min_s: int
    ttl_max_s: int
    max_depth: int
    verify_window_s: int
    lease_max_s: int
    limits: dict[str, int] = field(compare=False)

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> FieldParams:
        data = _strip_comment(copy.deepcopy(raw))
        a, r, t, ro, se, si = (
            data["amplitude"],
            data["resonance"],
            data["trail"],
            data["route"],
            data["sense"],
            data["similarity"],
        )
        return cls(
            raw=data,
            sha256=digest(data),
            skew_s=int(data["auth"]["skew_s"]),
            nonce_pattern=str(data["auth"]["nonce_pattern"]),
            A_max=float(a["A_max"]),
            a_per_priority=float(a["a_per_priority"]),
            h_A_s=float(a["half_life_s"]),
            A_alive=float(a["A_alive"]),
            delta_signal=float(a["delta_signal"]),
            untrusted_signal_cap=float(a["untrusted_signal_cap"]),
            theta_res=float(r["theta_res"]),
            gamma_res=float(r["gamma_res"]),
            max_links=int(r["max_links_per_intent"]),
            r_base=float(t["r_base"]),
            r_fail=float(t["r_fail"]),
            h_trail_s=float(t["half_life_s"]),
            w_min=float(t["w_min"]),
            w_max=float(t["w_max"]),
            route_alpha=float(ro["alpha"]),
            route_beta=float(ro["beta"]),
            eta_min=float(ro["eta_min"]),
            route_k=int(ro["k"]),
            route_k_explore=int(ro["k_explore"]),
            max_candidates=int(ro["max_candidates"]),
            sense_alpha=float(se["alpha"]),
            sense_beta=float(se["beta"]),
            lambda_lease=float(se["lambda_lease"]),
            sense_k=int(se["k"]),
            w_tag=float(si["w_tag"]),
            w_text=float(si["w_text"]),
            stopwords=frozenset(si["stopwords"]),
            ttl_min_s=int(data["intent"]["ttl_min_s"]),
            ttl_max_s=int(data["intent"]["ttl_max_s"]),
            max_depth=int(data["intent"]["max_depth"]),
            verify_window_s=int(data["intent"]["verify_window_s"]),
            lease_max_s=int(data["lease"]["max_s"]),
            limits={k: int(v) for k, v in data["limits"].items()},
        )

    def with_overrides(self, overrides: dict[str, Any]) -> FieldParams:
        """Return new params with dotted-path overrides, e.g. {"trail.w_min": 1e-6}."""
        data = copy.deepcopy(self.raw)
        for dotted, value in overrides.items():
            section, _, key = dotted.partition(".")
            if section not in data or key not in data[section]:
                raise KeyError(dotted)
            data[section][key] = value
        return FieldParams.from_mapping(data)
