# SPDX-License-Identifier: Apache-2.0
"""Digest machine verifier: pass iff artifact.sha256 equals the expected digest."""

from __future__ import annotations

from typing import Any

from wavefunction_field.verify.base import Verdict


class DigestVerifier:
    kind = "digest"

    def check_spec(self, acceptance: dict[str, Any]) -> None:
        return None

    def verify(self, acceptance: dict[str, Any], artifact: dict[str, Any]) -> Verdict:
        if artifact.get("sha256") == acceptance["sha256"]:
            return Verdict("pass")
        return Verdict("fail", "digest mismatch")
