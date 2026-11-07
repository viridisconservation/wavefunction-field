# SPDX-License-Identifier: Apache-2.0
"""Reject unsupported claims outside the fixed terminology note and decisions."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DENY = re.compile(
    r"\bquantum\b|\bproven\b|\bguarantee\w*\b|\benergy\s+sav\w*\b"
    r"|\bjoules?\b|\bcarbon\s+neutral\b|\bverified\s+alignment\b",
    re.IGNORECASE,
)
TERMINOLOGY_NOTE = (
    '"Wavefunction", "superposition", "collapse", "resonance/entanglement" and '
    '"pheromone" are **metaphors and brand terms**. The mathematics is classical: '
    "discrete probability distributions, Shannon entropy, exponential decay and "
    "ant-colony-optimization (ACO) scoring. No document, README, tool description or "
    "report may claim quantum behaviour, physical energy measurement, "
    '"proven alignment" or energy savings unless a named artifact in this '
    "repository measures it. `[G5]`"
)


def check(root: Path) -> list[str]:
    paths = [root / "README.md"]
    for directory in ("src", "docs", "examples"):
        paths.extend((root / directory).rglob("*"))
    errors = []
    for path in sorted(set(paths)):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.is_relative_to(root / "docs/decisions"):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        # Replace only the exact immutable note, preserving line numbers.
        content = content.replace(TERMINOLOGY_NOTE, "\n" * TERMINOLOGY_NOTE.count("\n"))
        for match in DENY.finditer(content):
            line = content.count("\n", 0, match.start()) + 1
            errors.append(
                f"{path.relative_to(root)}:{line}: unsupported claim: {match.group()}"
            )
    return errors


def main() -> int:
    errors = check(ROOT)
    for error in errors:
        print(error)
    if not errors:
        print("claims: PASS")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
