# SPDX-License-Identifier: Apache-2.0
"""Designated-verifier permission rule (PROTOCOL §6, INV-SM4)."""

from __future__ import annotations

from typing import Any


def may_verify(acceptance: dict[str, Any], verifier: str, doer: str) -> bool:
    return (
        acceptance.get("kind") == "designated"
        and verifier in acceptance.get("verifiers", [])
        and verifier != doer
    )
