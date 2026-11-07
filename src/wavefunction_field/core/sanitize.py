# SPDX-License-Identifier: Apache-2.0
"""Write-time text and URL hygiene (PROTOCOL §9.2-§9.3)."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

from wavefunction_field.core.errors import validation

_BIDI = {chr(c) for c in range(0x202A, 0x202F)} | {
    chr(c) for c in range(0x2066, 0x206A)
}


def _drop(ch: str) -> bool:
    code = ord(ch)
    if ch in ("\n", "\t"):
        return False
    if code < 0x20 or code == 0x7F or 0x80 <= code <= 0x9F:
        return True
    return ch in _BIDI


def clean_text(value: object, field: str, max_chars: int, *, min_chars: int = 0) -> str:
    """Strip control/bidi characters, then reject (never truncate) bad lengths."""
    if not isinstance(value, str):
        raise validation("must be a string", field)
    cleaned = "".join(ch for ch in value if not _drop(ch))
    if len(cleaned) > max_chars:
        raise validation(f"longer than {max_chars} characters", field, "max_length")
    if len(cleaned.strip()) < min_chars:
        raise validation("too short", field, "min_length")
    return cleaned


_HOST_LABEL = re.compile(r"^[a-z0-9-]{1,63}$")


def validate_url(value: object, field: str) -> str:
    """https only; reject loopback/private/link-local/.local hosts. Never fetched."""
    if not isinstance(value, str) or len(value) > 2048:
        raise validation("invalid URL", field)
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname:
        raise validation("only https URLs are accepted", field, "https_only")
    host = parts.hostname.lower().rstrip(".")
    if parts.username or parts.password:
        raise validation("credentials in URLs are not allowed", field)
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise validation("local hosts are not allowed", field, "public_host")
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        labels = host.split(".")
        if len(labels) < 2 or not all(_HOST_LABEL.match(lab) for lab in labels):
            raise validation("invalid host", field) from None
        return value
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        raise validation(
            "private or local addresses are not allowed", field, "public_host"
        )
    return value
