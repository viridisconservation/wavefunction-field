# SPDX-License-Identifier: Apache-2.0
"""Field-side MCP server (PROTOCOL §10.2) and the ``wf-field`` command."""

from __future__ import annotations

import argparse
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from wavefunction_field.api.untrusted import describe
from wavefunction_field.core.canonical import canonical
from wavefunction_field.core.errors import WFPError
from wavefunction_field.identity.envelope import PROTOCOL
from wavefunction_field.service.field import FieldService


def _safe(fn: Any) -> dict[str, Any]:
    try:
        out: dict[str, Any] = fn()
        return out
    except WFPError as exc:
        return {"error": exc.envelope()}
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        return {
            "error": {
                "error_type": "ValidationError",
                "message": f"malformed request: {type(exc).__name__}",
            }
        }


def build_field_mcp(svc: FieldService, *, public: bool = False) -> FastMCP:
    security = TransportSecuritySettings(enable_dns_rebinding_protection=not public)
    fm = FastMCP(
        "wavefunction-field",
        instructions=describe(
            "A Wavefunction Field: agents post intents (goals with acceptance criteria), sense open "
            "intents, and submit results that verifiers check. Writes must be signed; use the wf-agent "
            "MCP server to sign locally, or prepare_signature + submit_signed."
        ),
        stateless_http=True,
        json_response=True,
        streamable_http_path="/mcp",
        transport_security=security,
    )

    @fm.tool(
        description=describe(
            "Field manifest: protocol, field key, parameters, trust view and limits."
        )
    )
    def field_info() -> dict[str, Any]:
        from wavefunction_field.api.manifest import manifest

        return manifest(svc)

    @fm.tool(
        description=describe(
            "Rank OPEN intents for an agent id or for capability tags plus free text."
        )
    )
    def sense(
        agent_id: str | None = None,
        capabilities: list[str] | None = None,
        query: str = "",
        k: int | None = None,
        view: dict[str, list[str]] | None = None,
    ) -> dict[str, Any]:
        return _safe(
            lambda: svc.sense(
                agent_id=agent_id,
                capabilities=capabilities,
                query=query,
                k=k,
                view=view,
            )
        )

    @fm.tool(
        description=describe(
            "Routing distribution over agents for an intent (ACO scoring, full distribution)."
        )
    )
    def route(
        intent_id: str, k: int | None = None, view: dict[str, list[str]] | None = None
    ) -> dict[str, Any]:
        return _safe(lambda: svc.route(intent_id, k, view))

    @fm.tool(
        description=describe(
            "Full intent: goal, hypotheses, deposits, results, verifications, links."
        )
    )
    def get_intent(intent_id: str) -> dict[str, Any]:
        return _safe(lambda: svc.get_intent(intent_id))

    @fm.tool(
        description=describe(
            "List intents filtered by state, tag or emitter (cursor paginated)."
        )
    )
    def list_intents(
        state: str | None = None,
        tag: str | None = None,
        emitter: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return _safe(lambda: svc.list_intents(state, tag, emitter, limit, cursor))

    @fm.tool(
        description=describe(
            "Agent profile with per-tag trail weights under the default view."
        )
    )
    def get_agent(agent_id: str) -> dict[str, Any]:
        return _safe(lambda: svc.get_agent(agent_id))

    @fm.tool(
        description=describe(
            "Return the exact canonical bytes an agent must sign for a write.",
            write=True,
        )
    )
    def prepare_signature(
        action: str, actor_id: str, nonce: str, signed_at: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        env = {
            "protocol": PROTOCOL,
            "action": action,
            "actor_id": actor_id,
            "nonce": nonce,
            "signed_at": signed_at,
            "body": body,
        }
        return _safe(lambda: {"envelope": env, "canonical_ascii": canonical(env)})

    @fm.tool(
        description=describe(
            "Submit a write you signed yourself: envelope, base64url pubkey and signature.",
            write=True,
        )
    )
    def submit_signed(
        envelope: dict[str, Any], pubkey: str, signature: str
    ) -> dict[str, Any]:
        return _safe(
            lambda: svc.apply(
                {"envelope": envelope, "pubkey": pubkey, "signature": signature}
            )
        )

    return fm


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="wf-field", description="Serve a Wavefunction Field (HTTP + MCP)."
    )
    sub = parser.add_subparsers(dest="cmd")
    serve = sub.add_parser("serve", help="serve the field over HTTP with MCP at /mcp")
    serve.add_argument("--config", default=None, help="JSON config file (see docs)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8787)
    stdio = sub.add_parser("stdio", help="serve the field MCP tools over stdio")
    stdio.add_argument("--config", default=None)
    info = sub.add_parser("info", help="print the field manifest")
    info.add_argument("--config", default=None)
    args = parser.parse_args(argv)
    if args.cmd is None:
        parser.print_help()
        return
    from wavefunction_field.service.runtime import build_service

    svc, cfg = build_service(args.config)
    if args.cmd == "info":
        from wavefunction_field.api.manifest import manifest

        print(json.dumps(manifest(svc, cfg.public_url), indent=2))
    elif args.cmd == "stdio":
        build_field_mcp(svc).run("stdio")
    else:
        import uvicorn

        from wavefunction_field.api.http import create_app

        uvicorn.run(
            create_app(svc, public_url=cfg.public_url), host=args.host, port=args.port
        )


if __name__ == "__main__":
    main()
