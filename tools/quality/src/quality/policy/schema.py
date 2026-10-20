"""JSON Schema export of the policy models, kept in the repository and checked."""

from __future__ import annotations

import json

from quality.diagnostics import Rule
from quality.policy.models import Policy

SCHEMA_PATH = "docs/reference/policy.schema.json"

SCHEMA_STALE = Rule(
    id="policy.schema-stale",
    title="Committed policy schema differs from the models",
    requirement="R02",
    explanation="The committed policy JSON Schema is generated from the models and must match.",
    remedy="Run 'quality policy schema --write' and commit the result.",
)
RULES = (SCHEMA_STALE,)


def policy_schema_text() -> str:
    """Render the policy JSON Schema deterministically."""
    schema = Policy.model_json_schema(by_alias=True, mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = "quality.toml"
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"
