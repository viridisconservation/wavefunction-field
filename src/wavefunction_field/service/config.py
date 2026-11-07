# SPDX-License-Identifier: Apache-2.0
"""Field configuration and parameter loading (I/O lives here, not in core)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

from wavefunction_field.core.params import FieldParams


def default_params_mapping() -> dict[str, Any]:
    text = (
        resources.files("wavefunction_field")
        .joinpath("data/params.json")
        .read_text("utf-8")
    )
    data: dict[str, Any] = json.loads(text)
    return data


def load_params(path: str | Path | None = None) -> FieldParams:
    if path is None:
        return FieldParams.from_mapping(default_params_mapping())
    return FieldParams.from_mapping(json.loads(Path(path).read_text("utf-8")))


@dataclass
class FieldConfig:
    db_path: str = "wavefunction-field.sqlite3"
    field_key_path: str = "field.key"
    trusted_emitters: list[str] = field(default_factory=list)
    trusted_verifiers: list[str] = field(default_factory=list)
    operators: list[str] = field(default_factory=list)
    params_path: str | None = None
    public_url: str = ""

    @classmethod
    def load(cls, path: str | Path | None) -> FieldConfig:
        data: dict[str, Any] = {}
        if path is not None:
            data = json.loads(Path(path).read_text("utf-8"))
        cfg = cls(**data)
        env = os.environ
        cfg.db_path = env.get("WF_DB_PATH", cfg.db_path)
        cfg.field_key_path = env.get("WF_FIELD_KEY_FILE", cfg.field_key_path)
        cfg.public_url = env.get("WF_PUBLIC_URL", cfg.public_url)
        for name, attr in (
            ("WF_TRUSTED_EMITTERS", "trusted_emitters"),
            ("WF_TRUSTED_VERIFIERS", "trusted_verifiers"),
            ("WF_OPERATORS", "operators"),
        ):
            if env.get(name):
                setattr(
                    cfg, attr, [x.strip() for x in env[name].split(",") if x.strip()]
                )
        return cfg
