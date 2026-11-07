# SPDX-License-Identifier: Apache-2.0
"""Verifiers."""

from wavefunction_field.verify.base import MachineVerifier
from wavefunction_field.verify.digest import DigestVerifier
from wavefunction_field.verify.json_schema import JsonSchemaVerifier

MACHINE_VERIFIERS: dict[str, MachineVerifier] = {
    "digest": DigestVerifier(),
    "json_schema": JsonSchemaVerifier(),
}

__all__ = ["MACHINE_VERIFIERS", "DigestVerifier", "JsonSchemaVerifier"]
