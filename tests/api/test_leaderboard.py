# SPDX-License-Identifier: Apache-2.0
"""Leaderboard and badges (0.1.0a3).

LB1  only qualifying verifications count (PROTOCOL 7.3): an untrusted emitter's
     collapsed intent adds nothing to the board
LB2  ordering is by verified jobs, then most recent, and ranks are 1..n
LB3  agent-supplied text is wrapped as untrusted in JSON, escaped in HTML, and
     never appears in a badge
LB4  badge states: not registered, none yet, n verified
"""

from __future__ import annotations

import hashlib
from typing import Any

from starlette.testclient import TestClient

from tests.support import Harness, seeded
from wavefunction_field.api.http import create_app

EVIL = "<script>alert(1)</script>"


def _job(h: Harness, emitter: Any, doer: Any, n: int) -> None:
    text = f"answer {n}"
    out = h.write(
        emitter,
        "emit_intent",
        {
            "goal": f"job {n}",
            "hypotheses": [{"id": "h1", "summary": "s", "weight": 1}],
            "acceptance": {
                "kind": "digest",
                "sha256": hashlib.sha256(text.encode()).hexdigest(),
            },
            "priority": 3,
            "ttl_s": 3600,
            "capabilities_needed": ["hashing"],
        },
    )
    res = h.write(
        doer,
        "submit_result",
        {
            "intent_id": out["intent_id"],
            "hypothesis_id": "h1",
            "artifact": {
                "content_type": "text/plain",
                "inline": text,
                "sha256": hashlib.sha256(text.encode()).hexdigest(),
            },
            "cost_report": {"tokens": 0, "wall_ms": 0},
        },
    )
    assert res["intent_state"] == "COLLAPSED", res


def _field() -> tuple[Harness, Any, Any, Any, Any]:
    trusted, stranger, d1, d2 = seeded(1), seeded(2), seeded(3), seeded(4)
    h = Harness(trusted_emitters=[trusted])
    h.register(trusted, ["ops"])
    h.register(stranger, ["ops"])
    h.write(d1, "register_agent", {"name": EVIL, "capabilities": ["hashing"]})
    h.write(d2, "register_agent", {"name": "second", "capabilities": ["hashing"]})
    return h, trusted, stranger, d1, d2


def test_lb1_lb2_only_qualifying_work_counts_and_orders() -> None:
    h, trusted, stranger, d1, d2 = _field()
    _job(h, trusted, d2, 1)
    h.clock.advance(1000)
    _job(h, trusted, d1, 2)
    h.clock.advance(1000)
    _job(h, trusted, d1, 3)
    _job(h, stranger, d2, 4)  # collapses, but the emitter is not in the default view
    board = h.svc.leaderboard()
    assert [
        (r["agent_id"], r["verified_jobs"], r["rank"]) for r in board["agents"]
    ] == [(d1.agent_id, 2, 1), (d2.agent_id, 1, 2)]
    assert board["verified_jobs_total"] == 3 and board["agents_ranked"] == 2
    assert h.svc.verified_jobs(d2.agent_id) == 1
    assert h.svc.verified_jobs(stranger.agent_id) == 0
    assert h.svc.verified_jobs("wf1_nobody") is None


def test_lb3_lb4_surfaces_handle_untrusted_names() -> None:
    h, trusted, _, d1, _ = _field()
    _job(h, trusted, d1, 1)
    with TestClient(
        create_app(h.svc, public_url="https://f.test", mount_mcp=False)
    ) as c:
        data = c.get("/v1/leaderboard").json()
        assert data["agents"][0]["name"] == {
            "untrusted": {"author": d1.agent_id, "text": EVIL}
        }
        page = c.get("/leaderboard")
        assert page.status_code == 200 and EVIL not in page.text
        assert (
            "&lt;script&gt;" in page.text
            and "default-src 'none'" in page.headers["content-security-policy"]
        )
        assert "https://f.test/v1/agents/YOUR_AGENT_ID/badge.svg" in page.text
        one = c.get(f"/v1/agents/{d1.agent_id}/badge.svg")
        assert one.headers["content-type"].startswith("image/svg+xml")
        assert "1 verified job<" in one.text and "script" not in one.text
        assert (
            "no verified jobs yet"
            in c.get(f"/v1/agents/{trusted.agent_id}/badge.svg").text
        )
        assert "not registered" in c.get("/v1/agents/wf1_nobody/badge.svg").text
        assert c.get("/v1/leaderboard?limit=0").status_code == 400
        assert c.get(f"/v1/agents/{d1.agent_id}").json()["agent_id"] == d1.agent_id
        assert (
            c.get("/.well-known/wavefunction-field.json").json()["endpoints"][
                "leaderboard"
            ]
            == "https://f.test/leaderboard"
        )
