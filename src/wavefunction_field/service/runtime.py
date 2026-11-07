# SPDX-License-Identifier: Apache-2.0
"""Assemble a production FieldService from configuration."""

from __future__ import annotations

from pathlib import Path

from wavefunction_field.identity.keys import load_or_create_key
from wavefunction_field.identity.signer import FieldSigner
from wavefunction_field.service.clock import SystemClock
from wavefunction_field.service.config import FieldConfig, load_params
from wavefunction_field.service.field import FieldService
from wavefunction_field.store.sqlite import SQLiteStore


def build_service(config_path: str | None) -> tuple[FieldService, FieldConfig]:
    cfg = FieldConfig.load(config_path)
    key = load_or_create_key(Path(cfg.field_key_path))
    svc = FieldService(
        SQLiteStore(cfg.db_path),
        load_params(cfg.params_path),
        SystemClock(),
        FieldSigner(key),
        trusted_emitters=cfg.trusted_emitters,
        trusted_verifiers=cfg.trusted_verifiers,
        operators=cfg.operators,
    )
    return svc, cfg
