# SPDX-License-Identifier: Apache-2.0
"""Per-client admission control for a public field (ASGI middleware).

The protocol already bounds each *agent* (``writes_per_minute``,
``open_intents_per_emitter``), but agent ids are free to mint, so a public
deployment also needs per-*client* limits. This middleware applies token buckets
keyed by client IP before a request reaches the field. It never changes what an
admitted request returns; it only answers 429 with ``Retry-After``.

Client IP: the last ``X-Forwarded-For`` entry (the address the nearest reverse
proxy saw, which a client cannot forge through a proxy that sets the header),
else the socket peer. Deployments without a reverse proxy should not trust
``X-Forwarded-For``; pass ``trust_forwarded=False``.

Invariants (tests/unit/test_throttle.py):
  TH1  a request within every applicable bucket is passed through unchanged (body included)
  TH2  a request over a bucket gets 429, Retry-After >= 1, and never reaches the app
  TH3  buckets are per client; one client's exhaustion never limits another
  TH4  register_agent writes also draw on a global hourly budget
  TH5  state is bounded: idle buckets are pruned past ``max_clients``
"""

from __future__ import annotations

import json
import math
import os
import time
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass
from typing import Any

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


@dataclass(frozen=True)
class Limit:
    capacity: float
    per_s: float  # refill rate, tokens per second

    @classmethod
    def per_minute(cls, n: int) -> Limit:
        return cls(float(n), n / 60.0)

    @classmethod
    def per_hour(cls, n: int) -> Limit:
        return cls(float(n), n / 3600.0)


DEFAULT_LIMITS: dict[str, Limit] = {
    "write": Limit.per_minute(120),  # signed writes per client
    "register": Limit.per_hour(20),  # new agent registrations per client
    "compute": Limit.per_minute(60),  # sense / route (CPU heavy)
    "mcp": Limit.per_minute(120),  # MCP JSON-RPC posts
    "read": Limit.per_minute(600),  # everything else
}
GLOBAL_REGISTER = Limit.per_hour(500)


class Throttle:
    def __init__(
        self,
        app: ASGIApp,
        limits: dict[str, Limit] | None = None,
        global_register: Limit = GLOBAL_REGISTER,
        trust_forwarded: bool = True,
        max_clients: int = 50_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.app = app
        self.limits = dict(DEFAULT_LIMITS if limits is None else limits)
        self.global_register = global_register
        self.trust_forwarded = trust_forwarded
        self.max_clients = max_clients
        self.clock = clock
        self.buckets: dict[tuple[str, str], tuple[float, float]] = {}
        self.global_bucket: tuple[float, float] = (global_register.capacity, clock())

    # ----------------------------------------------------------- buckets
    @staticmethod
    def _take(
        state: tuple[float, float], lim: Limit, now: float
    ) -> tuple[bool, float, tuple[float, float]]:
        tokens, last = state
        tokens = min(lim.capacity, tokens + (now - last) * lim.per_s)
        if tokens >= 1.0:
            return True, 0.0, (tokens - 1.0, now)
        wait = (1.0 - tokens) / lim.per_s if lim.per_s > 0 else 3600.0
        return False, wait, (tokens, now)

    def _admit(self, client: str, kind: str, now: float) -> float:
        """Return 0 if admitted, else seconds to wait."""
        lim = self.limits.get(kind)
        if lim is None:
            return 0.0
        key = (client, kind)
        ok, wait, state = self._take(
            self.buckets.get(key, (lim.capacity, now)), lim, now
        )
        self.buckets[key] = state
        if len(self.buckets) > self.max_clients:
            self._prune(now)
        return 0.0 if ok else wait

    def _prune(self, now: float) -> None:
        # Drop buckets that have refilled completely (indistinguishable from new).
        for key, (tokens, last) in list(self.buckets.items()):
            lim = self.limits[key[1]]
            if tokens + (now - last) * lim.per_s >= lim.capacity:
                del self.buckets[key]
        while len(self.buckets) > self.max_clients:  # still too many: oldest first
            del self.buckets[min(self.buckets, key=lambda k: self.buckets[k][1])]

    # -------------------------------------------------------------- ASGI
    def client_of(self, scope: Scope) -> str:
        if self.trust_forwarded:
            for name, value in scope.get("headers") or []:
                if name == b"x-forwarded-for":
                    last: str = value.decode("latin-1").split(",")[-1].strip()
                    if last:
                        return last
        peer = scope.get("client")
        return str(peer[0]) if peer else "unknown"

    @staticmethod
    def kind_of(method: str, path: str) -> str:
        if method == "POST" and path.endswith("/v1/write"):
            return "write"
        if method == "POST" and (
            path.endswith("/v1/sense") or path.endswith("/v1/route")
        ):
            return "compute"
        if method == "POST" and path.rstrip("/").endswith("/mcp"):
            return "mcp"
        return "read"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        now = self.clock()
        client = self.client_of(scope)
        kind = self.kind_of(scope.get("method", "GET"), scope.get("path", ""))
        wait = self._admit(client, kind, now)
        if not wait and kind == "write":
            body, receive = await _buffer(receive)
            if _action(body) == "register_agent":
                wait = self._admit(client, "register", now)
                if not wait:
                    ok, gwait, self.global_bucket = self._take(
                        self.global_bucket, self.global_register, now
                    )
                    wait = 0.0 if ok else gwait
        if wait:
            await _too_many(send, wait, kind)
            return
        await self.app(scope, receive, send)


async def _buffer(receive: Receive) -> tuple[bytes, Receive]:
    chunks: list[bytes] = []
    messages: list[Message] = []
    while True:
        msg = await receive()
        messages.append(msg)
        if msg["type"] != "http.request":
            break
        chunks.append(msg.get("body", b""))
        if not msg.get("more_body"):
            break

    async def replay() -> Message:
        if messages:
            return messages.pop(0)
        return await receive()

    return b"".join(chunks), replay


def _action(body: bytes) -> str | None:
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    env = data.get("envelope")
    action = env.get("action") if isinstance(env, dict) else data.get("action")
    return action if isinstance(action, str) else None


async def _too_many(send: Send, wait: float, kind: str) -> None:
    retry = max(1, math.ceil(wait))
    payload = json.dumps(
        {
            "error_type": "RateLimited",
            "message": f"too many {kind} requests from this client; retry later",
            "retry_after_s": retry,
        }
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 429,
            "headers": [
                (b"content-type", b"application/json"),
                (b"retry-after", str(retry).encode()),
                (b"content-length", str(len(payload)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": payload})


def enabled() -> bool:
    return os.environ.get("WF_RATE_LIMITS", "on").lower() not in {"off", "0", "false"}
