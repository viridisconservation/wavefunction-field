# SPDX-License-Identifier: Apache-2.0
"""Conservatively reject core imports and calls that can perform side effects."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_IMPORTS = {
    "time",
    "random",
    "os",
    "socket",
    "sqlite3",
    "httpx",
    "asyncio",
    "datetime",
    "secrets",
    "uuid",
    "pathlib",
    "io",
    "subprocess",
    "requests",
    "importlib",
}
FORBIDDEN_CALLS = {"open", "input", "print", "exec", "eval", "__import__", "breakpoint"}


def check(root: Path) -> list[str]:
    errors = []
    for path in sorted((root / "src/wavefunction_field/core").rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        builtins_aliases = {"builtins"}
        forbidden_aliases = set(FORBIDDEN_CALLS)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split(".")[0]
                    if module == "builtins":
                        builtins_aliases.add(alias.asname or alias.name)
                    if module in FORBIDDEN_IMPORTS:
                        errors.append(
                            f"{path.relative_to(root)}:{node.lineno}: "
                            f"forbidden import {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = (node.module or "").split(".")[0]
                if module in FORBIDDEN_IMPORTS:
                    errors.append(
                        f"{path.relative_to(root)}:{node.lineno}: "
                        f"forbidden import {node.module}"
                    )
                if module == "builtins":
                    forbidden_aliases.update(
                        alias.asname or alias.name
                        for alias in node.names
                        if alias.name in FORBIDDEN_CALLS or alias.name == "*"
                    )
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            forbidden = (
                isinstance(function, ast.Name) and function.id in forbidden_aliases
            )
            if isinstance(function, ast.Attribute) and isinstance(
                function.value, ast.Name
            ):
                forbidden = forbidden or (
                    function.value.id in builtins_aliases
                    and function.attr in FORBIDDEN_CALLS
                )
            if forbidden:
                errors.append(
                    f"{path.relative_to(root)}:{node.lineno}: "
                    f"forbidden core call {ast.unparse(function)}"
                )
    return errors


def main() -> int:
    errors = check(ROOT)
    for error in errors:
        print(error)
    if not errors:
        print("core purity: PASS")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
