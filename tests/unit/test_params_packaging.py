# SPDX-License-Identifier: Apache-2.0
"""The packaged params copy must equal spec/params.json (hatch data inclusion)."""

from __future__ import annotations

import json
from pathlib import Path

from wavefunction_field.service.config import default_params_mapping, load_params

ROOT = Path(__file__).resolve().parents[2]


def test_packaged_params_match_spec() -> None:
    assert default_params_mapping() == json.loads((ROOT / "spec/params.json").read_text())
    assert load_params().sha256 == "10991006b2c282c7065af2d1ea8f78a2c258b1037c7daacdb52443a1ea56d873"
