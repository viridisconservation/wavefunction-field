# SPDX-License-Identifier: Apache-2.0
"""Enforce the closed direct-dependency allowlist."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = {"mcp>=1.25,<2", "cryptography>=42", "jsonschema>=4.21"}
DEV = {"pytest>=8", "hypothesis>=6.100", "ruff>=0.6", "mypy>=1.11"}
BUILD = {"hatchling"}


def normalise(requirement: str) -> str:
    return re.sub(r"\s+", "", requirement).lower()


def check(root: Path) -> list[str]:
    document = tomllib.loads((root / "pyproject.toml").read_text())
    project = document.get("project", {})
    groups = project.get("optional-dependencies", {})
    errors = []
    if "dependencies" in project.get("dynamic", []):
        errors.append("dynamic runtime dependencies are not permitted")
    if "optional-dependencies" in project.get("dynamic", []):
        errors.append("dynamic optional dependencies are not permitted")
    for requirement in project.get("dependencies", []):
        if normalise(requirement) not in RUNTIME:
            errors.append(f"runtime dependency outside allowlist: {requirement}")
    for group, requirements in groups.items():
        if group != "dev":
            errors.append(f"optional dependency group outside allowlist: {group}")
        for requirement in requirements:
            if normalise(requirement) not in DEV:
                errors.append(f"dev dependency outside allowlist: {requirement}")
    for requirement in document.get("build-system", {}).get("requires", []):
        if normalise(requirement) not in BUILD:
            errors.append(f"build dependency outside allowlist: {requirement}")
    if document.get("build-system", {}).get("build-backend") != "hatchling.build":
        errors.append("build backend must be hatchling.build")
    for group, requirements in document.get("dependency-groups", {}).items():
        for requirement in requirements:
            if not isinstance(requirement, str) or normalise(requirement) not in DEV:
                errors.append(
                    f"dependency group {group} outside dev allowlist: {requirement}"
                )
    return errors


def main() -> int:
    errors = check(ROOT)
    for error in errors:
        print(error)
    if not errors:
        print("dependencies: PASS (closed direct runtime/dev/build allowlist)")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
