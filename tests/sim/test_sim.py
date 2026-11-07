# SPDX-License-Identifier: Apache-2.0
"""WP-7 simulator invariants."""

from __future__ import annotations

import ast
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from scripts import check_prereg_lock
from wavefunction_field.sim import stats
from wavefunction_field.sim.cli import main as sim_main

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = {
    "wavefunction_field.core.routing",
    "wavefunction_field.core.dynamics",
    "wavefunction_field.core.projection",
    "wavefunction_field.core.resonance",
    "wavefunction_field.core.similarity",
}


def test_INV_SIM1_sim_never_imports_dynamics_or_routing() -> None:
    for path in (ROOT / "src/wavefunction_field/sim").glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module not in FORBIDDEN, (path.name, node.module)
                if node.module == "wavefunction_field.core":
                    assert not {a.name for a in node.names} & {
                        "routing",
                        "dynamics",
                        "projection",
                        "resonance",
                    }
            if isinstance(node, ast.Import):
                assert not {a.name for a in node.names} & FORBIDDEN


def _digest(out: Path) -> dict[str, str]:
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(out.iterdir())
    }


def test_INV_SIM2_deterministic_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(ROOT)
    a, b = tmp_path / "a", tmp_path / "b"
    sim_main(
        [
            "run",
            "--quick",
            "--seeds",
            "1",
            "--scenario",
            "S2_shock",
            "--out",
            str(a),
            "--commit",
            "test",
        ]
    )
    sim_main(
        [
            "run",
            "--quick",
            "--seeds",
            "1",
            "--scenario",
            "S2_shock",
            "--out",
            str(b),
            "--commit",
            "test",
        ]
    )
    assert _digest(a) == _digest(b)


def test_INV_SIM3_thresholds_from_locked_prereg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(ROOT)
    out = tmp_path / "r"
    sim_main(
        [
            "run",
            "--quick",
            "--seeds",
            "1",
            "--scenario",
            "S3_sybil",
            "--out",
            str(out),
            "--commit",
            "test",
        ]
    )
    report = json.loads((out / "report.json").read_text())
    lock = (ROOT / "spec/PREREG_LOCK").read_text().strip()
    assert report["hypotheses"]["prereg_sha256"] == lock
    rule = json.loads((ROOT / "spec/sim_preregistration.json").read_text())[
        "hypotheses"
    ]["H4_sybil_resistance"]["pass"]
    assert report["hypotheses"]["H4_sybil_resistance"]["rule"] == rule
    # tampering with the prereg is caught by the lock check
    shutil.copytree(ROOT / "spec", tmp_path / "spec")
    shutil.copytree(ROOT / "docs/decisions", tmp_path / "docs/decisions")
    p = tmp_path / "spec/sim_preregistration.json"
    data = json.loads(p.read_text())
    data["hypotheses"]["H2_learning_beats_registry"]["pass"] = "anything goes"
    p.write_text(json.dumps(data))
    assert check_prereg_lock.check(tmp_path)


def test_INV_SIM4_report_units_and_no_energy_claims(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(ROOT)
    out = tmp_path / "r"
    sim_main(
        [
            "run",
            "--quick",
            "--seeds",
            "1",
            "--scenario",
            "S1_steady",
            "--out",
            str(out),
            "--commit",
            "test",
        ]
    )
    md = (out / "report.md").read_text().lower()
    assert "self-reported tokens" in md
    body = md.replace("no energy or carbon figures are measured or implied", "")
    for word in ("joule", "kwh", "co2e", "energy sav"):
        assert word not in body


def test_stats_fixtures() -> None:
    assert stats.ranks([10, 20, 20, 30]) == [1.0, 2.5, 2.5, 4.0]
    assert stats.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert stats.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert stats.spearman([1, 2, 3, 4, 5], [2, 1, 4, 3, 5]) == pytest.approx(0.8)
    assert stats.median([3, 1, 2]) == 2 and stats.median([1, 2, 3, 4]) == 2.5
