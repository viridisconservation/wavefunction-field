# SPDX-License-Identifier: Apache-2.0
"""A new agent's first job through wf-agent's real MCP call path (0.1.0a3).

OB1  a JSON result passed as a JSON string or as an object is accepted, stored
     canonically, and machine-verified against a json_schema acceptance
OB2  the stored artifact's sha256 matches its stored bytes (computed by wf-agent)
OB3  plain text content is passed through byte for byte
OB4  sense before register_self explains what to do
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from tests.api.surface import agent, call
from tests.support import Harness
from wavefunction_field.identity.keys import load_or_create_key
from wavefunction_field.identity.signer import FieldSigner

pytestmark = pytest.mark.anyio
SCHEMA = {
    "type": "object",
    "required": ["sha256", "commit"],
    "properties": {
        "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "commit": {"type": "string"},
    },
}
RESULT = {"sha256": hashlib.sha256(b"hello").hexdigest(), "commit": "abc"}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def _field(tmp_path: Path) -> tuple[Harness, Any, Any]:
    a, b = (FieldSigner(load_or_create_key(tmp_path / f"{n}.key")) for n in "ab")
    h = Harness(trusted_emitters=[a])
    ca, cb = agent(h, a), agent(h, b)
    await call(ca, "register_self", name="emitter", capabilities=["ops"])
    return h, ca, cb


async def _emit(ca: Any, acceptance: dict[str, Any]) -> str:
    out = await call(
        ca,
        "emit_intent",
        goal="hash the word hello",
        capabilities_needed=["hashing"],
        hypotheses=[{"id": "h1", "summary": "sha256", "weight": 1}],
        acceptance=acceptance,
    )
    return str(out["intent_id"])


@pytest.mark.parametrize("as_string", [True, False])
async def test_ob1_ob2_json_result_collapses(tmp_path: Path, as_string: bool) -> None:
    h, ca, cb = await _field(tmp_path)
    await call(cb, "register_self", name="doer", capabilities=["hashing"])
    iid = await _emit(ca, {"kind": "json_schema", "schema": SCHEMA})
    hits = await call(cb, "sense")
    assert [x["intent"]["intent_id"] for x in hits["hits"]] == [iid]
    await call(cb, "claim", intent_id=iid)
    content: Any = json.dumps(RESULT, indent=2) if as_string else RESULT
    out = await call(
        cb, "submit_result", intent_id=iid, hypothesis_id="h1", content=content
    )
    assert out.get("intent_state") == "COLLAPSED", out
    art = h.svc.proj.results[out["result_id"]].artifact
    assert json.loads(art["inline"]) == RESULT
    assert art["content_type"] == "application/json"
    assert art["sha256"] == hashlib.sha256(art["inline"].encode()).hexdigest()


async def test_ob3_plain_text_is_unchanged(tmp_path: Path) -> None:
    h, ca, cb = await _field(tmp_path)
    await call(cb, "register_self", name="doer", capabilities=["hashing"])
    text = "plain  text, not JSON\n"
    iid = await _emit(
        ca, {"kind": "digest", "sha256": hashlib.sha256(text.encode()).hexdigest()}
    )
    out = await call(
        cb, "submit_result", intent_id=iid, hypothesis_id="h1", content=text
    )
    assert out.get("intent_state") == "COLLAPSED", out
    assert h.svc.proj.results[out["result_id"]].artifact["inline"] == text


async def test_ob4_sense_before_register_gives_a_hint(tmp_path: Path) -> None:
    _, _, cb = await _field(tmp_path)
    out = await call(cb, "sense")
    assert "register_self" in out["error"]["hint"]
