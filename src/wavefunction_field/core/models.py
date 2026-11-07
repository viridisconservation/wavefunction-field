# SPDX-License-Identifier: Apache-2.0
"""Strict validation of signed action bodies (PROTOCOL §3, §5).

Hand-written instead of model classes so that nothing is coerced: integers must
be integers, unknown keys are rejected, and every text field is sanitised.
"""

from __future__ import annotations

import re
from typing import Any

from wavefunction_field.core.canonical import canonical, reject_floats, sha256_hex
from wavefunction_field.core.errors import validation
from wavefunction_field.core.params import FieldParams
from wavefunction_field.core.sanitize import clean_text, validate_url

TAG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
AGENT_ID_RE = re.compile(r"^wf1_[a-z2-7]{26}$")
INTENT_ID_RE = re.compile(r"^int_[0-9a-f]{24}$")
RESULT_ID_RE = re.compile(r"^res_[0-9a-f]{24}$")
HYP_ID_RE = re.compile(r"^h[0-9]{1,2}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
IDEM_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
SIDE_EFFECTS = ("spend", "external_comm", "access_change", "production_change")
LINK_KEYS = ("mcp", "a2a_card", "homepage")
ACTIONS = (
    "register_agent",
    "revoke_agent",
    "emit_intent",
    "reweight",
    "deposit",
    "release_claim",
    "submit_result",
    "verify",
    "withdraw_intent",
)


def _keys(
    body: dict[str, Any], required: set[str], optional: set[str], where: str
) -> None:
    missing = required - body.keys()
    if missing:
        raise validation(
            f"missing field {sorted(missing)[0]}", f"{where}.{sorted(missing)[0]}"
        )
    unknown = body.keys() - required - optional
    if unknown:
        raise validation(
            f"unknown field {sorted(unknown)[0]}", f"{where}.{sorted(unknown)[0]}"
        )


def _int(value: Any, field: str, lo: int, hi: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise validation("must be an integer", field, "integer")
    if not lo <= value <= hi:
        raise validation(f"must be between {lo} and {hi}", field, "range")
    return value


def _match(value: Any, pattern: re.Pattern[str], field: str) -> str:
    if not isinstance(value, str) or not pattern.match(value):
        raise validation("invalid format", field, "pattern")
    return value


def _tags(value: Any, field: str, lo: int, hi: int) -> list[str]:
    if not isinstance(value, list):
        raise validation("must be a list of tags", field)
    if not lo <= len(value) <= hi:
        raise validation(f"must contain {lo}-{hi} tags", field, "count")
    tags = [_match(tag, TAG_RE, f"{field}[{i}]") for i, tag in enumerate(value)]
    if len(set(tags)) != len(tags):
        raise validation("tags must be unique", field, "unique")
    return tags


def _idem(body: dict[str, Any], out: dict[str, Any]) -> None:
    if "idempotency_key" in body:
        out["idempotency_key"] = _match(
            body["idempotency_key"], IDEM_RE, "body.idempotency_key"
        )


def artifact(value: Any, field: str, p: FieldParams) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise validation("must be an object", field)
    _keys(value, {"content_type", "sha256"}, {"inline", "uri"}, field)
    out: dict[str, Any] = {
        "content_type": clean_text(
            value["content_type"], f"{field}.content_type", 100, min_chars=1
        ),
        "sha256": _match(value["sha256"], SHA_RE, f"{field}.sha256"),
    }
    if ("inline" in value) == ("uri" in value):
        raise validation("exactly one of inline or uri is required", field, "one_of")
    if "inline" in value:
        inline = value["inline"]
        if not isinstance(inline, str):
            raise validation("must be a string", f"{field}.inline")
        if len(inline.encode("utf-8")) > p.limits["inline_artifact_bytes"]:
            raise validation(
                "inline artifact too large", f"{field}.inline", "max_bytes"
            )
        if sha256_hex(inline) != out["sha256"]:
            raise validation(
                "sha256 does not match inline content", f"{field}.sha256", "digest"
            )
        out["inline"] = inline
    else:
        out["uri"] = validate_url(value["uri"], f"{field}.uri")
    return out


def acceptance(value: Any, p: FieldParams) -> dict[str, Any]:
    field = "body.acceptance"
    if not isinstance(value, dict) or "kind" not in value:
        raise validation("must be an object with kind", field)
    kind = value["kind"]
    if kind == "json_schema":
        _keys(value, {"kind", "schema"}, set(), field)
        if not isinstance(value["schema"], dict):
            raise validation("schema must be an object", f"{field}.schema")
        if len(canonical(value["schema"])) > p.limits["json_schema_bytes"]:
            raise validation("schema too large", f"{field}.schema", "max_bytes")
        return {"kind": kind, "schema": value["schema"]}
    if kind == "digest":
        _keys(value, {"kind", "sha256"}, set(), field)
        return {
            "kind": kind,
            "sha256": _match(value["sha256"], SHA_RE, f"{field}.sha256"),
        }
    if kind == "designated":
        _keys(value, {"kind", "verifiers"}, set(), field)
        vs = value["verifiers"]
        cap = p.limits["max_designated_verifiers"]
        if not isinstance(vs, list) or not 1 <= len(vs) <= cap:
            raise validation(
                f"verifiers must list 1-{cap} agent ids", f"{field}.verifiers"
            )
        ids = [
            _match(v, AGENT_ID_RE, f"{field}.verifiers[{i}]") for i, v in enumerate(vs)
        ]
        if len(set(ids)) != len(ids):
            raise validation("verifiers must be unique", f"{field}.verifiers", "unique")
        return {"kind": kind, "verifiers": ids}
    if kind == "lean":
        raise validation("not_supported_v0_1", f"{field}.kind", "not_supported_v0_1")
    raise validation("unknown acceptance kind", f"{field}.kind")


def validate_body(action: str, body: Any, p: FieldParams) -> dict[str, Any]:
    """Return a normalised copy of ``body`` or raise ValidationError."""
    if action not in ACTIONS:
        raise validation("unknown action", "envelope.action")
    if not isinstance(body, dict):
        raise validation("body must be an object", "body")
    reject_floats(body)
    lim = p.limits
    out: dict[str, Any] = {}
    if action == "register_agent":
        _keys(
            body,
            {"name", "capabilities"},
            {"description", "links", "idempotency_key"},
            "body",
        )
        out["name"] = clean_text(
            body["name"], "body.name", lim["agent_name_chars"], min_chars=1
        )
        out["capabilities"] = _tags(
            body["capabilities"], "body.capabilities", 1, lim["max_capabilities"]
        )
        out["description"] = clean_text(
            body.get("description", ""),
            "body.description",
            lim["agent_description_chars"],
        )
        links = body.get("links", {})
        if not isinstance(links, dict):
            raise validation("links must be an object", "body.links")
        for key in links:
            if key not in LINK_KEYS:
                raise validation("unknown link key", f"body.links.{key}")
        out["links"] = {
            k: validate_url(v, f"body.links.{k}") for k, v in sorted(links.items())
        }
    elif action == "revoke_agent":
        _keys(body, {"agent_id"}, {"idempotency_key"}, "body")
        out["agent_id"] = _match(body["agent_id"], AGENT_ID_RE, "body.agent_id")
    elif action == "emit_intent":
        _keys(
            body,
            {"goal", "hypotheses", "acceptance", "priority", "ttl_s"},
            {
                "capabilities_needed",
                "side_effects",
                "parent_intent_id",
                "idempotency_key",
            },
            "body",
        )
        out["goal"] = clean_text(
            body["goal"], "body.goal", lim["goal_chars"], min_chars=1
        )
        hyps = body["hypotheses"]
        if not isinstance(hyps, list) or not 1 <= len(hyps) <= lim["max_hypotheses"]:
            raise validation(
                f"hypotheses must list 1-{lim['max_hypotheses']}", "body.hypotheses"
            )
        norm = []
        for i, h in enumerate(hyps):
            where = f"body.hypotheses[{i}]"
            if not isinstance(h, dict):
                raise validation("must be an object", where)
            _keys(h, {"id", "summary", "weight"}, set(), where)
            norm.append(
                {
                    "id": _match(h["id"], HYP_ID_RE, f"{where}.id"),
                    "summary": clean_text(
                        h["summary"],
                        f"{where}.summary",
                        lim["summary_chars"],
                        min_chars=1,
                    ),
                    "weight": _int(h["weight"], f"{where}.weight", 1, 1000),
                }
            )
        if len({h["id"] for h in norm}) != len(norm):
            raise validation(
                "hypothesis ids must be unique", "body.hypotheses", "unique"
            )
        out["hypotheses"] = norm
        out["acceptance"] = acceptance(body["acceptance"], p)
        out["priority"] = _int(body["priority"], "body.priority", 1, 10)
        out["ttl_s"] = _int(body["ttl_s"], "body.ttl_s", p.ttl_min_s, p.ttl_max_s)
        out["capabilities_needed"] = _tags(
            body.get("capabilities_needed", []),
            "body.capabilities_needed",
            0,
            lim["max_intent_tags"],
        )
        se = body.get("side_effects", [])
        if (
            not isinstance(se, list)
            or any(x not in SIDE_EFFECTS for x in se)
            or len(set(se)) != len(se)
        ):
            raise validation("invalid side_effects", "body.side_effects")
        out["side_effects"] = sorted(se)
        if "parent_intent_id" in body:
            out["parent_intent_id"] = _match(
                body["parent_intent_id"], INTENT_ID_RE, "body.parent_intent_id"
            )
    elif action == "reweight":
        _keys(body, {"intent_id", "weights"}, {"adopt", "idempotency_key"}, "body")
        out["intent_id"] = _match(body["intent_id"], INTENT_ID_RE, "body.intent_id")
        w = body["weights"]
        if not isinstance(w, dict) or not w:
            raise validation("weights must be a non-empty object", "body.weights")
        out["weights"] = {
            _match(k, HYP_ID_RE, f"body.weights.{k}"): _int(
                v, f"body.weights.{k}", 1, 1000
            )
            for k, v in sorted(w.items())
        }
        if "adopt" in body:
            a = body["adopt"]
            if not isinstance(a, dict):
                raise validation("adopt must be an object", "body.adopt")
            _keys(a, {"summary", "weight"}, set(), "body.adopt")
            out["adopt"] = {
                "summary": clean_text(
                    a["summary"],
                    "body.adopt.summary",
                    lim["summary_chars"],
                    min_chars=1,
                ),
                "weight": _int(a["weight"], "body.adopt.weight", 1, 1000),
            }
    elif action == "deposit":
        _keys(
            body,
            {"intent_id", "kind"},
            {"summary", "lease_s", "artifact", "idempotency_key"},
            "body",
        )
        out["intent_id"] = _match(body["intent_id"], INTENT_ID_RE, "body.intent_id")
        kind = body["kind"]
        extra = set(body) - {"intent_id", "kind", "idempotency_key"}
        needed = {
            "signal": set(),
            "hypothesis": {"summary"},
            "claim": {"lease_s"},
            "partial": {"artifact"},
        }
        if kind not in needed:
            raise validation("unknown deposit kind", "body.kind")
        if extra != needed[kind]:
            raise validation(
                f"{kind} deposit takes exactly {sorted(needed[kind])}", "body"
            )
        out["kind"] = kind
        if kind == "hypothesis":
            out["summary"] = clean_text(
                body["summary"], "body.summary", lim["summary_chars"], min_chars=1
            )
        elif kind == "claim":
            out["lease_s"] = _int(body["lease_s"], "body.lease_s", 1, p.lease_max_s)
        elif kind == "partial":
            out["artifact"] = artifact(body["artifact"], "body.artifact", p)
    elif action == "release_claim":
        _keys(body, {"intent_id"}, {"idempotency_key"}, "body")
        out["intent_id"] = _match(body["intent_id"], INTENT_ID_RE, "body.intent_id")
    elif action == "submit_result":
        _keys(
            body,
            {"intent_id", "hypothesis_id", "artifact", "cost_report"},
            {"idempotency_key"},
            "body",
        )
        out["intent_id"] = _match(body["intent_id"], INTENT_ID_RE, "body.intent_id")
        out["hypothesis_id"] = _match(
            body["hypothesis_id"], HYP_ID_RE, "body.hypothesis_id"
        )
        out["artifact"] = artifact(body["artifact"], "body.artifact", p)
        cr = body["cost_report"]
        if not isinstance(cr, dict):
            raise validation("cost_report must be an object", "body.cost_report")
        _keys(cr, {"tokens", "wall_ms"}, set(), "body.cost_report")
        out["cost_report"] = {
            "tokens": _int(cr["tokens"], "body.cost_report.tokens", 0, 10**12),
            "wall_ms": _int(cr["wall_ms"], "body.cost_report.wall_ms", 0, 10**12),
        }
    elif action == "verify":
        _keys(body, {"result_id", "verdict"}, {"evidence", "idempotency_key"}, "body")
        out["result_id"] = _match(body["result_id"], RESULT_ID_RE, "body.result_id")
        if body["verdict"] not in ("pass", "fail"):
            raise validation("verdict must be pass or fail", "body.verdict")
        out["verdict"] = body["verdict"]
        if "evidence" in body:
            ev = body["evidence"]
            if not isinstance(ev, dict):
                raise validation("evidence must be an object", "body.evidence")
            _keys(ev, {"summary"}, {"sha256"}, "body.evidence")
            out["evidence"] = {
                "summary": clean_text(
                    ev["summary"],
                    "body.evidence.summary",
                    lim["evidence_summary_chars"],
                )
            }
            if "sha256" in ev:
                out["evidence"]["sha256"] = _match(
                    ev["sha256"], SHA_RE, "body.evidence.sha256"
                )
    elif action == "withdraw_intent":
        _keys(body, {"intent_id"}, {"idempotency_key"}, "body")
        out["intent_id"] = _match(body["intent_id"], INTENT_ID_RE, "body.intent_id")
    _idem(body, out)
    return out
