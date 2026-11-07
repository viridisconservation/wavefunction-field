# SPDX-License-Identifier: Apache-2.0
"""Canonical JSON (PROTOCOL §1.3), byte-compatible with viridis-agent-market-v1."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from wavefunction_field.core.errors import validation


def canonical(value: Any) -> str:
    """Return the canonical ASCII JSON text of ``value``."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def canonical_bytes(value: Any) -> bytes:
    return canonical(value).encode("ascii")


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def digest(value: Any) -> str:
    """sha256 hex of the canonical encoding of ``value``."""
    return sha256_hex(canonical_bytes(value))


def reject_floats(value: Any, path: str = "body") -> None:
    """Raise ValidationError if ``value`` contains any float (signed bodies, §1.3)."""
    if isinstance(value, bool) or value is None or isinstance(value, int | str):
        return
    if isinstance(value, float):
        raise validation(
            "floating-point numbers are not allowed", path, "integers_only"
        )
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise validation("object keys must be strings", path)
            reject_floats(item, f"{path}.{key}")
        return
    if isinstance(value, list | tuple):
        for index, item in enumerate(value):
            reject_floats(item, f"{path}[{index}]")
        return
    raise validation(f"unsupported JSON type {type(value).__name__}", path)
