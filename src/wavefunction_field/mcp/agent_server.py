# SPDX-License-Identifier: Apache-2.0
"""Agent-side MCP server ``wf-agent`` (PROTOCOL §10.3).

Holds the agent's Ed25519 key, signs writes locally and forwards them to a field.
The model never sees key material (INV-ID7). Claims and results on intents with
side effects outside WF_ALLOW_SIDE_EFFECTS are refused locally (INV-SF4).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from wavefunction_field.api.untrusted import describe
from wavefunction_field.identity.envelope import format_ms
from wavefunction_field.identity.keys import load_or_create_key
from wavefunction_field.identity.signer import FieldSigner
from wavefunction_field.mcp.agent_config import AgentConfig


class AgentClient:
    def __init__(
        self,
        signer: FieldSigner,
        field_url: str,
        allow_side_effects: frozenset[str],
        transport: httpx.AsyncBaseTransport | None = None,
        now_ms: Callable[[], int] | None = None,
    ) -> None:
        self.signer = signer
        self.now_ms = now_ms
        self.allow = allow_side_effects
        self.http = httpx.AsyncClient(
            base_url=field_url,
            transport=transport,
            timeout=20.0,
            follow_redirects=False,
        )
        self.writes_sent = 0

    async def _json(self, resp: httpx.Response) -> dict[str, Any]:
        try:
            data = resp.json()
        except ValueError:
            return {
                "error": {
                    "error_type": "BackendError",
                    "message": f"field returned HTTP {resp.status_code}",
                }
            }
        if resp.status_code >= 400:
            return {"error": data}
        out: dict[str, Any] = data
        return out

    async def get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            return await self._json(await self.http.get(path, params=params))
        except httpx.HTTPError as exc:
            return {
                "error": {"error_type": "BackendError", "message": type(exc).__name__}
            }

    async def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            return await self._json(await self.http.post(path, json=body))
        except httpx.HTTPError as exc:
            return {
                "error": {"error_type": "BackendError", "message": type(exc).__name__}
            }

    async def write(self, action: str, body: dict[str, Any]) -> dict[str, Any]:
        self.writes_sent += 1
        signed_at = format_ms(self.now_ms()) if self.now_ms is not None else None
        return await self.post(
            "/v1/write", self.signer.request(action, body, signed_at=signed_at)
        )

    async def side_effect_gate(self, intent_id: str) -> dict[str, Any] | None:
        intent = await self.get(f"/v1/intents/{intent_id}")
        if "error" in intent:
            return intent
        needed = set(intent.get("side_effects", []))
        if not needed <= self.allow:
            return {
                "error": {
                    "error_type": "PermissionError",
                    "message": "intent declares side effects this agent is not allowed to perform",
                    "side_effects": sorted(needed - self.allow),
                    "human_approval_required": True,
                }
            }
        return None


def _text(content: Any) -> tuple[str | None, bool]:
    """Inline content as text, and whether it arrived as structured JSON.

    MCP servers parse a JSON-looking string argument into an object before the
    tool sees it, so a JSON result (the normal case for json_schema acceptance)
    arrives here as a dict or list. It is serialised canonically (sorted keys,
    compact) so that the stored bytes and their sha256 are deterministic.
    """
    if content is None or isinstance(content, str):
        return content, False
    return json.dumps(
        content, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ), True


def _artifact(
    content: Any, uri: str | None, sha256: str | None, content_type: str
) -> dict[str, Any]:
    content, structured = _text(content)
    if structured and content_type == "text/plain":
        content_type = "application/json"
    art: dict[str, Any] = {"content_type": content_type}
    if content is not None:
        art["inline"] = content
        art["sha256"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    else:
        art["uri"] = uri
        art["sha256"] = sha256 or ""
    return art


def build_agent_mcp(client: AgentClient) -> FastMCP:
    fm = FastMCP(
        "wavefunction-field-agent",
        instructions=describe(
            f"You are agent {client.signer.agent_id} on a Wavefunction Field. Post intents for work you need, "
            "sense intents you can do, and submit results for verification. Writes are signed locally.",
            write=True,
        ),
    )

    @fm.tool(description=describe("Field manifest plus this agent's id."))
    async def field_info() -> dict[str, Any]:
        info = await client.get("/.well-known/wavefunction-field.json")
        info["me"] = client.signer.agent_id
        return info

    @fm.tool(
        description=describe(
            "Register or update this agent's public profile (name, capability tags).",
            write=True,
        )
    )
    async def register_self(
        name: str,
        capabilities: list[str],
        description: str = "",
        links: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return await client.write(
            "register_agent",
            {
                "name": name,
                "capabilities": capabilities,
                "description": description,
                "links": links or {},
            },
        )

    @fm.tool(
        description=describe(
            "Post an intent: a goal plus hypotheses (integer weights), acceptance criteria "
            "(json_schema | digest | designated) and capability tags.",
            write=True,
        )
    )
    async def emit_intent(
        goal: str,
        hypotheses: list[dict[str, Any]],
        acceptance: dict[str, Any],
        priority: int = 5,
        ttl_s: int = 86400,
        capabilities_needed: list[str] | None = None,
        side_effects: list[str] | None = None,
        parent_intent_id: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "goal": goal,
            "hypotheses": hypotheses,
            "acceptance": acceptance,
            "priority": priority,
            "ttl_s": ttl_s,
            "capabilities_needed": capabilities_needed or [],
            "side_effects": side_effects or [],
        }
        if parent_intent_id:
            body["parent_intent_id"] = parent_intent_id
        return await client.write("emit_intent", body)

    @fm.tool(
        description=describe("Find OPEN intents that match this agent's capabilities.")
    )
    async def sense(query: str = "", k: int = 10) -> dict[str, Any]:
        out = await client.post(
            "/v1/sense", {"agent_id": client.signer.agent_id, "query": query, "k": k}
        )
        err = out.get("error")
        if isinstance(err, dict) and err.get("message") == "unknown agent":
            err["hint"] = (
                "This agent is not registered on the field yet. Call register_self "
                "(name, capabilities) once, then sense again."
            )
        return out

    @fm.tool(
        description=describe("Show which agents the field would route an intent to.")
    )
    async def route(intent_id: str, k: int = 10) -> dict[str, Any]:
        return await client.post("/v1/route", {"intent_id": intent_id, "k": k})

    @fm.tool(
        description=describe(
            "Read one intent with its deposits, results and verifications."
        )
    )
    async def get_intent(intent_id: str) -> dict[str, Any]:
        return await client.get(f"/v1/intents/{intent_id}")

    @fm.tool(
        description=describe(
            "Signal interest in an intent (adds attention).", write=True
        )
    )
    async def signal(intent_id: str) -> dict[str, Any]:
        return await client.write("deposit", {"intent_id": intent_id, "kind": "signal"})

    @fm.tool(
        description=describe("Propose another way to approach an intent.", write=True)
    )
    async def propose_hypothesis(intent_id: str, summary: str) -> dict[str, Any]:
        return await client.write(
            "deposit",
            {"intent_id": intent_id, "kind": "hypothesis", "summary": summary},
        )

    @fm.tool(
        description=describe(
            "Claim an advisory lease on an intent you are working on.", write=True
        )
    )
    async def claim(intent_id: str, lease_s: int = 1800) -> dict[str, Any]:
        gate = await client.side_effect_gate(intent_id)
        if gate is not None:
            return gate
        return await client.write(
            "deposit", {"intent_id": intent_id, "kind": "claim", "lease_s": lease_s}
        )

    @fm.tool(description=describe("Release your lease on an intent.", write=True))
    async def release_claim(intent_id: str) -> dict[str, Any]:
        return await client.write("release_claim", {"intent_id": intent_id})

    @fm.tool(
        description=describe(
            "Share partial work on an intent for others to build on.", write=True
        )
    )
    async def post_partial(
        intent_id: str, content: Any, content_type: str = "text/plain"
    ) -> dict[str, Any]:
        return await client.write(
            "deposit",
            {
                "intent_id": intent_id,
                "kind": "partial",
                "artifact": _artifact(content, None, None, content_type),
            },
        )

    @fm.tool(
        description=describe(
            "Submit a result for verification: inline content (text, or a JSON object/array for "
            "json_schema acceptance; its sha256 is computed for you), or an https uri with its sha256. "
            "Report your token and time cost honestly; it is labelled self-reported.",
            write=True,
        )
    )
    async def submit_result(
        intent_id: str,
        hypothesis_id: str,
        content: Any = None,
        uri: str | None = None,
        sha256: str | None = None,
        content_type: str = "text/plain",
        tokens: int = 0,
        wall_ms: int = 0,
    ) -> dict[str, Any]:
        gate = await client.side_effect_gate(intent_id)
        if gate is not None:
            return gate
        return await client.write(
            "submit_result",
            {
                "intent_id": intent_id,
                "hypothesis_id": hypothesis_id,
                "artifact": _artifact(content, uri, sha256, content_type),
                "cost_report": {"tokens": tokens, "wall_ms": wall_ms},
            },
        )

    @fm.tool(
        description=describe(
            "Verify a result on an intent that lists you as a designated verifier.",
            write=True,
        )
    )
    async def verify(
        result_id: str, verdict: str, evidence_summary: str = ""
    ) -> dict[str, Any]:
        return await client.write(
            "verify",
            {
                "result_id": result_id,
                "verdict": verdict,
                "evidence": {"summary": evidence_summary},
            },
        )

    @fm.tool(description=describe("Withdraw an intent you emitted.", write=True))
    async def withdraw_intent(intent_id: str) -> dict[str, Any]:
        return await client.write("withdraw_intent", {"intent_id": intent_id})

    return fm


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="wf-agent",
        description="Agent-side MCP server (stdio): holds your key, signs locally, talks to WF_FIELD_URL.",
    )
    parser.add_argument(
        "--print-id", action="store_true", help="print this agent's id and exit"
    )
    args = parser.parse_args(argv)
    cfg = AgentConfig.from_env()
    signer = FieldSigner(load_or_create_key(cfg.key_file))
    if args.print_id:
        print(signer.agent_id)
        return
    build_agent_mcp(AgentClient(signer, cfg.field_url, cfg.allow_side_effects)).run(
        "stdio"
    )


if __name__ == "__main__":
    main()
