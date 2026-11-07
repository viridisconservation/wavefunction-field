# SPDX-License-Identifier: Apache-2.0
"""Check named invariant coverage for completed work packages."""

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ID_PATTERN = re.compile(r"\bINV-[A-Z]+\d+\b")
NAME_PATTERN = re.compile(r"INV[-_]([A-Z]+)(\d+)")


def check(root: Path) -> list[str]:
    registry = json.loads((root / "spec/invariants.json").read_text())
    state = json.loads((root / "spec/BUILD_STATE.json").read_text())
    completed = state["completed_wps"]
    invariants = registry["invariants"]
    known = {item["id"] for item in invariants}
    required = {item["id"] for item in invariants if item["wp"] in completed}
    referenced: set[str] = set()
    errors = []
    for path in sorted((root / "tests").rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if not node.name.startswith("test"):
                continue
            ids = set(ID_PATTERN.findall(ast.get_docstring(node) or ""))
            ids.update(
                f"INV-{area}{number}"
                for area, number in NAME_PATTERN.findall(node.name)
            )
            referenced.update(ids)
            for unknown in sorted(ids - known):
                errors.append(
                    f"{path.relative_to(root)}:{node.lineno}: unknown {unknown}"
                )
    for missing in sorted(required - referenced):
        errors.append(f"missing named test for {missing}")
    return errors


def main() -> int:
    errors = check(ROOT)
    for error in errors:
        print(error)
    if not errors:
        print("traceability: PASS")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
