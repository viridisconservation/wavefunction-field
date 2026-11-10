# SPDX-License-Identifier: Apache-2.0
"""Well-known field manifest (PROTOCOL §10.1)."""

from __future__ import annotations

from typing import Any

from wavefunction_field import __version__
from wavefunction_field.api.untrusted import DATA_NOTICE, PUBLIC_NOTICE
from wavefunction_field.identity.envelope import PROTOCOL
from wavefunction_field.service.field import FieldService


def manifest(svc: FieldService, public_url: str = "") -> dict[str, Any]:
    view = svc.default_view
    return {
        "protocol": PROTOCOL,
        "implementation": "wavefunction-field",
        "version": __version__,
        "field_agent_id": svc.signer.agent_id,
        "field_pubkey": svc.signer.public_key_b64,
        "params": svc.p.raw,
        "params_sha256": svc.p.sha256,
        "default_view": view.as_dict(),
        "default_view_sha256": view.key(),
        "limits": svc.p.limits,
        "public_content_notice": PUBLIC_NOTICE,
        "untrusted_content_notice": DATA_NOTICE,
        "endpoints": {
            "write": f"{public_url}/v1/write",
            "mcp": f"{public_url}/mcp",
            "leaderboard": f"{public_url}/leaderboard",
            "docs": "https://github.com/viridisconservation/wavefunction-field/blob/main/docs/PROTOCOL.md",
        },
    }
