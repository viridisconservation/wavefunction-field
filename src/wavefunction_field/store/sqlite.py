# SPDX-License-Identifier: Apache-2.0
"""Durable SQLite event store: WAL, synchronous=FULL, append-only (PROTOCOL §8)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from wavefunction_field.core.canonical import canonical
from wavefunction_field.store.base import IdemRecord, WriteMeta
from wavefunction_field.store.chain import GENESIS_PREV, seal

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY,
    event_id TEXT NOT NULL,
    type TEXT NOT NULL,
    actor_id TEXT,
    server_ms INTEGER NOT NULL,
    body_json TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS nonces (
    actor_id TEXT NOT NULL,
    nonce TEXT NOT NULL,
    PRIMARY KEY (actor_id, nonce)
);
CREATE TABLE IF NOT EXISTS idempotency (
    actor_id TEXT NOT NULL,
    key TEXT NOT NULL,
    body_sha256 TEXT NOT NULL,
    result_json TEXT NOT NULL,
    PRIMARY KEY (actor_id, key)
);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
"""


class SQLiteStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._db = sqlite3.connect(
            self.path, isolation_level=None, check_same_thread=False
        )
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript(SCHEMA)

    def pragma(self, name: str) -> Any:
        return self._db.execute(f"PRAGMA {name}").fetchone()[0]

    def append(
        self, cores: list[dict[str, Any]], meta: WriteMeta | None = None
    ) -> list[dict[str, Any]]:
        db = self._db
        db.execute("BEGIN IMMEDIATE")
        try:
            if meta is not None:
                db.execute(
                    "INSERT INTO nonces(actor_id, nonce) VALUES (?, ?)",
                    (meta.actor_id, meta.nonce),
                )
            seq, prev = self.head()
            sealed = []
            for core in cores:
                seq += 1
                event = seal(core, seq, prev)
                prev = event["hash"]
                body = {
                    k: v
                    for k, v in event.items()
                    if k not in ("seq", "prev_hash", "hash")
                }
                db.execute(
                    "INSERT INTO events(seq, event_id, type, actor_id, server_ms, body_json, prev_hash, hash)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        seq,
                        event["event_id"],
                        event["type"],
                        event["actor_id"],
                        event["server_ms"],
                        canonical(body),
                        event["prev_hash"],
                        event["hash"],
                    ),
                )
                sealed.append(event)
            if meta is not None and meta.idem_key is not None:
                db.execute(
                    "INSERT INTO idempotency(actor_id, key, body_sha256, result_json) VALUES (?, ?, ?, ?)",
                    (meta.actor_id, meta.idem_key, meta.body_sha256, meta.result_json),
                )
            db.execute("COMMIT")
        except sqlite3.IntegrityError as exc:
            db.execute("ROLLBACK")
            raise ValueError(str(exc)) from exc
        except BaseException:
            db.execute("ROLLBACK")
            raise
        return sealed

    def iter_events(self, after_seq: int = 0) -> Iterator[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT seq, body_json, prev_hash, hash FROM events WHERE seq > ? ORDER BY seq",
            (after_seq,),
        ).fetchall()
        for seq, body_json, prev_hash, hash_ in rows:
            event = json.loads(body_json)
            event["seq"] = seq
            event["prev_hash"] = prev_hash
            event["hash"] = hash_
            yield event

    def head(self) -> tuple[int, str]:
        row = self._db.execute(
            "SELECT seq, hash FROM events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return (0, GENESIS_PREV) if row is None else (int(row[0]), str(row[1]))

    def has_nonce(self, actor_id: str, nonce: str) -> bool:
        row = self._db.execute(
            "SELECT 1 FROM nonces WHERE actor_id = ? AND nonce = ?", (actor_id, nonce)
        ).fetchone()
        return row is not None

    def get_idempotent(self, actor_id: str, key: str) -> IdemRecord | None:
        row = self._db.execute(
            "SELECT body_sha256, result_json FROM idempotency WHERE actor_id = ? AND key = ?",
            (actor_id, key),
        ).fetchone()
        return None if row is None else IdemRecord(row[0], row[1])

    def close(self) -> None:
        self._db.close()
