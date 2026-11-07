# SPDX-License-Identifier: Apache-2.0
"""Bootstrap checks for network isolation, clocks, profiles and entry points."""

from __future__ import annotations

import asyncio
import socket
import subprocess
from typing import Any

import httpx
import pytest
from hypothesis import settings

# This reference models a socket class retained before the autouse guard runs.
_ORIGINAL_SOCKET = socket.socket


@pytest.mark.parametrize("family", [socket.AF_INET, socket.AF_INET6])
def test_outbound_socket_creation_is_blocked(family: int) -> None:
    with pytest.raises(RuntimeError, match="outbound network access"):
        socket.socket(family, socket.SOCK_STREAM)


@pytest.mark.parametrize("method", ["connect", "connect_ex"])
@pytest.mark.parametrize("family", [socket.AF_INET, socket.AF_INET6])
def test_connections_on_existing_socket_classes_are_blocked(
    method: str, family: int
) -> None:
    address = ("127.0.0.1", 9) if family == socket.AF_INET else ("::1", 9, 0, 0)
    with _ORIGINAL_SOCKET(family, socket.SOCK_STREAM) as sock:
        with pytest.raises(RuntimeError, match="outbound network access"):
            getattr(sock, method)(address)


@pytest.mark.parametrize("method", ["send", "sendall"])
def test_sends_on_existing_socket_classes_are_blocked(method: str) -> None:
    with _ORIGINAL_SOCKET(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with pytest.raises(RuntimeError, match="outbound network access"):
            getattr(sock, method)(b"blocked")


def test_udp_sends_and_dns_are_blocked() -> None:
    with _ORIGINAL_SOCKET(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        with pytest.raises(RuntimeError, match="outbound network access"):
            sock.sendto(b"blocked", ("127.0.0.1", 9))
    with pytest.raises(RuntimeError, match="outbound network access"):
        socket.getaddrinfo("example.invalid", 443)
    with pytest.raises(RuntimeError, match="outbound network access"):
        socket.create_connection(("example.invalid", 443))


def test_unix_socketpair_remains_usable() -> None:
    sender, receiver = socket.socketpair(socket.AF_UNIX)
    with sender, receiver:
        sender.sendall(b"local")
        assert receiver.recv(5) == b"local"


def test_fake_clock_is_injectable(fake_clock: Any) -> None:
    initial = fake_clock.now_ms()
    fake_clock.advance(1_234)
    assert fake_clock.now_ms() == initial + 1_234
    with pytest.raises(ValueError, match="backwards"):
        fake_clock.advance(-1)
    assert fake_clock.now_ms() == initial + 1_234


def test_property_profiles_meet_minimum_example_counts() -> None:
    assert settings.get_profile("local").max_examples >= 500
    assert settings.get_profile("ci").max_examples >= 200
    assert settings.get_profile("local").deadline is None
    assert settings.get_profile("ci").deadline is None


@pytest.mark.parametrize("command", ["wf-field", "wf-agent", "wf-sim"])
def test_console_script_help(command: str) -> None:
    completed = subprocess.run(
        [command, "--help"], capture_output=True, text=True, check=True, timeout=10
    )
    assert "usage:" in completed.stdout.lower()
    assert command in completed.stdout
    assert completed.stderr == ""


def test_asgi_in_process_transport_remains_usable() -> None:
    async def application(
        scope: dict[str, Any], receive: Any, send: Any
    ) -> None:
        assert scope["type"] == "http"
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"in process"})

    async def request() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application), base_url="http://in-process"
        ) as client:
            response = await client.get("/")
        assert response.status_code == 200
        assert response.text == "in process"

    asyncio.run(request())
