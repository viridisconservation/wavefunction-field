# SPDX-License-Identifier: Apache-2.0
"""Verify the canonical preregistration hash against its frozen lock."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def canonical_hash(path: Path) -> str:
    value = json.loads(path.read_text(encoding="utf-8"))
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def check(root: Path) -> list[str]:
    actual = canonical_hash(root / "spec/sim_preregistration.json")
    expected = (root / "spec/PREREG_LOCK").read_text().strip()
    if not re.fullmatch(r"[a-f0-9]{64}", expected):
        return ["preregistration lock is not a lowercase SHA-256 hex digest"]
    if actual == expected:
        return []
    # The baseline decision records the original lock; only a new decision may
    # authorise a replacement, and it must name the complete new digest.
    for path in sorted((root / "docs/decisions").glob("*.md")):
        if path.name == "0001-v0.1-foundations.md":
            continue
        if re.search(rf"(?<![a-f0-9]){actual}(?![a-f0-9])", path.read_text()):
            return []
    return [
        f"preregistration hash mismatch: locked={expected} "
        f"actual={actual}; new decision required"
    ]


def main() -> int:
    errors = check(ROOT)
    for error in errors:
        print(error)
    if not errors:
        actual = canonical_hash(ROOT / "spec/sim_preregistration.json")
        print(f"preregistration: PASS {actual}")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
