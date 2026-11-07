# SPDX-License-Identifier: Apache-2.0
"""WP-3 event store invariants."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tests.support import Harness, seeded
from wavefunction_field.service.clock import FakeClock
from wavefunction_field.store.base import WriteMeta
from wavefunction_field.store.chain import verify_chain
from wavefunction_field.store.memory import MemoryStore
from wavefunction_field.store.sqlite import SQLiteStore


def _core(i: int) -> dict[str, object]:
    return {
        "event_id": f"evt_{i}",
        "type": "t",
        "actor_id": "a",
        "server_ms": i,
        "payload": {"i": i, "f": 0.25},
        "envelope": None,
        "pubkey": None,
        "signature": None,
    }


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
def test_INV_ID3_nonce_once_including_restart(tmp_path: Path, kind: str) -> None:
    path = tmp_path / "s.db"
    store = MemoryStore() if kind == "memory" else SQLiteStore(path)
    store.append([_core(1)], WriteMeta("a", "nonce-00000001"))
    with pytest.raises(ValueError):
        store.append([_core(2)], WriteMeta("a", "nonce-00000001"))
    assert store.head()[0] == 1
    if kind == "sqlite":
        store.close()
        store = SQLiteStore(path)
        assert store.has_nonce("a", "nonce-00000001")
        with pytest.raises(ValueError):
            store.append([_core(3)], WriteMeta("a", "nonce-00000001"))


def test_INV_ID3_service_replay_rejected_after_restart(tmp_path: Path) -> None:
    clock = FakeClock()
    a = seeded(1)
    h = Harness(store=SQLiteStore(tmp_path / "f.db"), clock=clock)
    req = h.req(
        a,
        "register_agent",
        {"name": "a", "capabilities": ["x"]},
        nonce="nonce-replay-1",
    )
    h.svc.apply(req)
    h.store.close()
    h2 = Harness(store=SQLiteStore(tmp_path / "f.db"), clock=clock)
    with pytest.raises(Exception) as exc:
        h2.svc.apply(req)
    assert "nonce" in str(exc.value)


def test_INV_ST1_append_only(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "s.db")
    store.append([_core(1)])
    assert not hasattr(store, "update") and not hasattr(store, "delete")
    raw = sqlite3.connect(tmp_path / "s.db")
    with pytest.raises(sqlite3.DatabaseError):
        raw.execute("UPDATE events SET type='x'")
    with pytest.raises(sqlite3.DatabaseError):
        raw.execute("DELETE FROM events")


@pytest.mark.parametrize(
    "field",
    ["event_id", "type", "actor_id", "server_ms", "payload", "prev_hash", "seq"],
)
def test_INV_ST2_chain_detects_mutation(field: str) -> None:
    store = MemoryStore()
    store.append([_core(i) for i in range(1, 5)])
    events = list(store.iter_events())
    assert verify_chain(events)
    tampered = [dict(e) for e in events]
    victim = tampered[2]
    victim[field] = (
        {"x": 1}
        if field == "payload"
        else (99 if field in ("server_ms", "seq") else "zz")
    )
    assert not verify_chain(tampered)


def test_INV_ST2_sqlite_tamper_detected(tmp_path: Path) -> None:
    path = tmp_path / "s.db"
    store = SQLiteStore(path)
    store.append([_core(i) for i in range(1, 4)])
    assert verify_chain(store.iter_events())
    store.close()
    raw = sqlite3.connect(path)
    raw.execute("DROP TRIGGER events_no_update")
    raw.execute(
        "UPDATE events SET body_json = replace(body_json, '0.25', '0.5') WHERE seq = 2"
    )
    raw.commit()
    raw.close()
    assert not verify_chain(SQLiteStore(path).iter_events())


def test_INV_ST4_wal_full_and_durable(tmp_path: Path) -> None:
    path = tmp_path / "s.db"
    store = SQLiteStore(path)
    assert str(store.pragma("journal_mode")).lower() == "wal"
    assert int(store.pragma("synchronous")) == 2  # FULL
    store.append([_core(1)], WriteMeta("a", "nonce-durable1"))
    store._db.close()  # simulate a crash: no checkpoint, no clean shutdown path
    again = SQLiteStore(path)
    assert again.head()[0] == 1
    assert again.has_nonce("a", "nonce-durable1")
