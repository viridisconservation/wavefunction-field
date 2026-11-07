# SPDX-License-Identifier: Apache-2.0
"""WP-5 verifier permissions and json_schema behaviour."""

from __future__ import annotations

import json

import pytest

from tests.support import Harness, seeded, sha
from wavefunction_field.core.errors import WFPError

SCHEMA = {
    "type": "object",
    "required": ["summary"],
    "properties": {"summary": {"type": "string"}},
}


def _h() -> tuple[Harness, dict[str, object]]:
    roles = {
        "emitter": seeded(1),
        "doer": seeded(2),
        "listed": seeded(3),
        "unlisted": seeded(4),
        "revoked": seeded(5),
    }
    h = Harness(trusted_emitters=[roles["emitter"]])
    for s in roles.values():
        h.register(s, ["carbon"])
    h.write(roles["revoked"], "revoke_agent", {"agent_id": roles["revoked"].agent_id})
    return h, roles


@pytest.mark.parametrize(
    "role,allowed",
    [
        ("emitter", True),
        ("listed", True),
        ("doer", False),
        ("unlisted", False),
        ("revoked", False),
    ],
)
def test_INV_SM4_designated_permission_matrix(role: str, allowed: bool) -> None:
    h, r = _h()
    iid = h.emit(
        r["emitter"],
        acceptance={
            "kind": "designated",
            "verifiers": [
                r["emitter"].agent_id,
                r["listed"].agent_id,
                r["doer"].agent_id,
            ],
        },
    )
    res = h.submit(r["doer"], iid)
    if allowed:
        out = h.write(
            r[role], "verify", {"result_id": res["result_id"], "verdict": "pass"}
        )
        assert out["intent_state"] == "COLLAPSED"
    else:
        with pytest.raises(WFPError) as exc:
            h.write(
                r[role], "verify", {"result_id": res["result_id"], "verdict": "pass"}
            )
        assert exc.value.error_type == "PermissionError"


@pytest.mark.parametrize("action", ["withdraw_intent", "reweight"])
def test_INV_SM4_only_emitter_withdraws_or_reweights(action: str) -> None:
    h, r = _h()
    iid = h.emit(r["emitter"])
    body = (
        {"intent_id": iid}
        if action == "withdraw_intent"
        else {"intent_id": iid, "weights": {"h1": 9}}
    )
    with pytest.raises(WFPError) as exc:
        h.write(r["doer"], action, body)
    assert exc.value.error_type == "PermissionError"
    h.write(r["emitter"], action, body)


def test_INV_SM4_machine_intents_cannot_be_hand_verified() -> None:
    h, r = _h()
    iid = h.emit(r["emitter"], acceptance={"kind": "json_schema", "schema": SCHEMA})
    res = h.submit(r["doer"], iid, content="not json")
    assert res["state"] == "FAILED"
    with pytest.raises(WFPError) as exc:
        h.write(
            r["emitter"], "verify", {"result_id": res["result_id"], "verdict": "pass"}
        )
    assert exc.value.error_type in ("PermissionError", "ContextError")
    ok = h.submit(r["doer"], iid, content=json.dumps({"summary": "fine"}))
    assert ok["intent_state"] == "COLLAPSED"


def test_INV_SM4_lean_rejected_and_remote_ref_rejected() -> None:
    h, r = _h()
    with pytest.raises(WFPError) as exc:
        h.emit(r["emitter"], acceptance={"kind": "lean"})
    assert exc.value.constraint == "not_supported_v0_1"
    with pytest.raises(WFPError) as exc:
        h.emit(
            r["emitter"],
            acceptance={
                "kind": "json_schema",
                "schema": {"$ref": "https://evil.example/s.json"},
            },
        )
    assert exc.value.constraint == "local_refs_only"


def test_INV_SM4_designated_sybil_verifier_does_not_move_trails() -> None:
    h, r = _h()
    iid = h.emit(
        r["emitter"],
        acceptance={"kind": "designated", "verifiers": [r["listed"].agent_id]},
    )
    res = h.submit(r["doer"], iid)
    h.write(r["listed"], "verify", {"result_id": res["result_id"], "verdict": "pass"})
    proj = h.svc.proj
    now = h.clock.now_ms()
    assert proj.trail(
        "carbon", r["doer"].agent_id, now, proj.default_view
    ) == proj.floor("carbon", r["doer"].agent_id)
    assert sha("x")
