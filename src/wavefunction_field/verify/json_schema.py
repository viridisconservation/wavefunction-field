# SPDX-License-Identifier: Apache-2.0
"""JSON Schema 2020-12 machine verifier with remote $ref retrieval disabled."""

from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry
from referencing.exceptions import NoSuchResource, Unresolvable

from wavefunction_field.core.errors import validation
from wavefunction_field.verify.base import Verdict


def _no_retrieve(uri: str) -> Any:
    raise NoSuchResource(ref=uri)  # type: ignore[call-arg]


_REGISTRY: Registry[Any] = Registry(retrieve=_no_retrieve)  # type: ignore[call-arg]


def _refs(node: Any) -> list[str]:
    out: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("$ref", "$dynamicRef") and isinstance(v, str):
                out.append(v)
            out.extend(_refs(v))
    elif isinstance(node, list):
        for v in node:
            out.extend(_refs(v))
    return out


class JsonSchemaVerifier:
    kind = "json_schema"

    def check_spec(self, acceptance: dict[str, Any]) -> None:
        schema = acceptance["schema"]
        for ref in _refs(schema):
            if not ref.startswith("#"):
                raise validation(
                    "remote $ref is not allowed",
                    "body.acceptance.schema",
                    "local_refs_only",
                )
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            raise validation(
                f"invalid JSON Schema: {exc.message}", "body.acceptance.schema"
            ) from None

    def verify(self, acceptance: dict[str, Any], artifact: dict[str, Any]) -> Verdict:
        if "inline" not in artifact:
            return Verdict("fail", "json_schema requires an inline artifact")
        try:
            instance = json.loads(artifact["inline"])
        except ValueError:
            return Verdict("fail", "artifact is not JSON")
        validator = Draft202012Validator(acceptance["schema"], registry=_REGISTRY)
        try:
            errors = list(validator.iter_errors(instance))
        except (Unresolvable, NoSuchResource):
            return Verdict("fail", "unresolvable reference")
        return Verdict("fail", errors[0].message[:200]) if errors else Verdict("pass")
