# SPDX-License-Identifier: Apache-2.0
"""INV-DY7: the core package is pure and deterministic."""

from __future__ import annotations

from pathlib import Path

from scripts import check_core_purity
from tests.support import PARAMS
from wavefunction_field.core.projection import Projection

ROOT = Path(__file__).resolve().parents[2]


def test_INV_DY7_core_imports_are_pure() -> None:
    assert check_core_purity.check(ROOT) == []


def test_INV_DY7_identical_inputs_identical_outputs() -> None:
    events = [
        {
            "type": "field_genesis",
            "actor_id": "f",
            "server_ms": 1,
            "envelope": None,
            "payload": {
                "field_agent_id": "f",
                "field_pubkey": "k",
                "params_sha256": "x",
                "default_view": {"verifiers": ["f"], "emitters": []},
                "operators": [],
            },
        },
    ]
    a, b = Projection(PARAMS), Projection(PARAMS)
    for e in events:
        a.apply(e)
        b.apply(e)
    assert a.canonical_state(10) == b.canonical_state(10)
