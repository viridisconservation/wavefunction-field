# SPDX-License-Identifier: Apache-2.0
"""Exercise acceptance-check failure paths on isolated miniature repositories."""

import json
from pathlib import Path

from scripts import (
    check_claims,
    check_core_purity,
    check_deps,
    check_headers,
    check_prereg_lock,
    check_traceability,
)


def write(root: Path, name: str, content: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_traceability_requires_ids_in_test_name_or_docstring(tmp_path: Path) -> None:
    write(
        tmp_path,
        "spec/invariants.json",
        json.dumps({"invariants": [{"id": "INV-ID1", "wp": "WP-2"}]}),
    )
    write(tmp_path, "spec/BUILD_STATE.json", '{"completed_wps":["WP-2"]}')
    test = write(
        tmp_path,
        "tests/test_fixture.py",
        "# INV-ID1\ndef test_placeholder():\n    pass\n",
    )
    assert check_traceability.check(tmp_path) == ["missing named test for INV-ID1"]
    test.write_text('def test_identity():\n    """INV-ID1"""\n    pass\n')
    assert check_traceability.check(tmp_path) == []
    test.write_text("def test_INV_ID1():\n    pass\n")
    assert check_traceability.check(tmp_path) == []
    test.write_text('def test_unknown():\n    """INV-UNKNOWN999"""\n    pass\n')
    assert any(
        "unknown INV-UNKNOWN999" in error
        for error in check_traceability.check(tmp_path)
    )


def test_dependency_checker_rejects_unlisted_and_dynamic(tmp_path: Path) -> None:
    valid = (
        '[build-system]\nrequires=["hatchling"]\n'
        'build-backend="hatchling.build"\n'
        '[project]\ndependencies=["mcp>=1.25,<2", '
        '"cryptography>=42", "jsonschema>=4.21"]\n'
        '[project.optional-dependencies]\ndev=["pytest", '
        '"hypothesis", "ruff", "mypy"]\n'
    )
    project = write(tmp_path, "pyproject.toml", valid)
    assert check_deps.check(tmp_path) == []
    for original, changed in (
        ('"mcp>=1.25,<2"', '"mcp>=2"'),
        ('"pytest"', '"pytest-socket"'),
        ('"hatchling"', '"setuptools"'),
        ("dependencies=[", 'dynamic=["dependencies"]\ndependencies=['),
    ):
        project.write_text(valid.replace(original, changed))
        assert check_deps.check(tmp_path)


def test_claims_exempts_only_exact_note_and_decisions(tmp_path: Path) -> None:
    readme = write(tmp_path, "README.md", check_claims.TERMINOLOGY_NOTE)
    write(tmp_path, "docs/decisions/0001-test.md", "A rejected quantum claim.")
    assert check_claims.check(tmp_path) == []
    readme.write_text(check_claims.TERMINOLOGY_NOTE + "\nGuaranteed results.")
    assert any("Guaranteed" in error for error in check_claims.check(tmp_path))
    readme.write_text("No energy savings are measured.")
    assert check_claims.check(tmp_path)


def test_headers_inspects_source_file_prefix(tmp_path: Path) -> None:
    source = write(
        tmp_path, "src/wavefunction_field/main.py", "def example():\n    pass\n"
    )
    assert check_headers.check(tmp_path)
    source.write_text(
        "# SPDX-License-Identifier: Apache-2.0\ndef example():\n    pass\n"
    )
    assert check_headers.check(tmp_path) == []


def test_purity_detects_aliased_imports_and_builtin_io(tmp_path: Path) -> None:
    source = write(
        tmp_path,
        "src/wavefunction_field/core/example.py",
        "import math\nvalue = math.sqrt(4)\n",
    )
    assert check_core_purity.check(tmp_path) == []
    for content in (
        "import time as innocent\n",
        "from random import random as value\n",
        "open('file')\n",
        "import builtins as b\nb.open('file')\n",
        "from builtins import open as load\nload('file')\n",
        "__import__('time')\n",
    ):
        source.write_text(content)
        assert check_core_purity.check(tmp_path)


def test_prereg_lock_requires_new_hash_decision(tmp_path: Path) -> None:
    prereg = write(tmp_path, "spec/sim_preregistration.json", '{"threshold":10}')
    locked = check_prereg_lock.canonical_hash(prereg)
    write(tmp_path, "spec/PREREG_LOCK", locked + "\n")
    assert check_prereg_lock.check(tmp_path) == []
    prereg.write_text('{"threshold":11}')
    assert check_prereg_lock.check(tmp_path)
    actual = check_prereg_lock.canonical_hash(prereg)
    write(tmp_path, "docs/decisions/0001-v0.1-foundations.md", actual)
    assert check_prereg_lock.check(tmp_path)
    write(
        tmp_path,
        "docs/decisions/0002-change.md",
        "New preregistration hash: " + actual,
    )
    assert check_prereg_lock.check(tmp_path) == []
