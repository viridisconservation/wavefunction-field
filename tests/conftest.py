# SPDX-License-Identifier: Apache-2.0
"""Shared offline test isolation, deterministic time, and property-test profiles."""

from __future__ import annotations

import socket
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from hypothesis import settings

settings.register_profile("local", max_examples=500, deadline=None)
settings.register_profile("ci", max_examples=200, deadline=None)
settings.load_profile("local")


@dataclass
class FakeClock:
    """A caller-controlled integer millisecond clock with no wall-clock reads."""

    time_ms: int = 1_794_063_600_000

    def now_ms(self) -> int:
        return self.time_ms

    def advance(self, delta_ms: int) -> None:
        if delta_ms < 0:
            raise ValueError("clock cannot move backwards")
        self.time_ms += delta_ms


@pytest.fixture
def fake_clock() -> FakeClock:
    """Each test receives an independent clock."""
    return FakeClock()


@pytest.fixture(autouse=True)
def block_outbound_sockets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject network sockets, including operations on pre-existing sockets.

    Unix sockets remain usable for local event-loop plumbing. ASGI in-process
    transports do not open sockets, so they remain usable without exemptions.
    """
    original_socket = socket.socket

    def network_error(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("outbound network access is disabled in tests")

    def guarded_method(method: Callable[..., Any]) -> Callable[..., Any]:
        def call(sock: socket.socket, *args: Any, **kwargs: Any) -> Any:
            if sock.family != socket.AF_UNIX:
                return network_error()
            return method(sock, *args, **kwargs)

        return call

    for name in (
        "connect",
        "connect_ex",
        "send",
        "sendall",
        "sendto",
        "sendmsg",
        "sendfile",
    ):
        method = getattr(original_socket, name, None)
        if method is not None:
            monkeypatch.setattr(original_socket, name, guarded_method(method))

    class OfflineSocket(original_socket):
        def __init__(
            self,
            family: int = socket.AF_INET,
            type: int = socket.SOCK_STREAM,
            proto: int = 0,
            fileno: int | None = None,
        ) -> None:
            if family != socket.AF_UNIX:
                network_error()
            super().__init__(family, type, proto, fileno=fileno)

    monkeypatch.setattr(socket, "socket", OfflineSocket)
    monkeypatch.setattr(socket, "create_connection", network_error)
    monkeypatch.setattr(socket, "getaddrinfo", network_error)
    monkeypatch.setattr(socket, "getnameinfo", network_error)
    monkeypatch.setattr(socket, "gethostbyname", network_error)
    monkeypatch.setattr(socket, "gethostbyname_ex", network_error)
    monkeypatch.setattr(socket, "gethostbyaddr", network_error)
