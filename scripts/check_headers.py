# SPDX-License-Identifier: Apache-2.0
"""Require Apache-2.0 SPDX identifiers in source files."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SUFFIXES = {".py", ".sh", ".js", ".mjs", ".ts", ".tsx"}
HEADER = "SPDX-License-Identifier: Apache-2.0"


def check(root: Path) -> list[str]:
    errors = []
    for directory in ("src", "scripts", "tests", "examples"):
        for path in sorted((root / directory).rglob("*")):
            if path.is_file() and path.suffix in SOURCE_SUFFIXES:
                if not any(
                    HEADER in line for line in path.read_text().splitlines()[:5]
                ):
                    errors.append(
                        f"{path.relative_to(root)}: missing SPDX Apache-2.0 header"
                    )
    return errors


def main() -> int:
    errors = check(ROOT)
    for error in errors:
        print(error)
    if not errors:
        print("headers: PASS")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
