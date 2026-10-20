import json

from quality.policy.schema import policy_schema_text


def test_schema_is_deterministic_and_closed() -> None:
    text = policy_schema_text()
    assert text == policy_schema_text()
    assert text.endswith("}\n")
    schema = json.loads(text)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["title"] == "quality.toml"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "schema_version",
        "repository",
        "thresholds",
        "coverage",
        "components",
    }
    for definition in schema["$defs"].values():
        if definition.get("type") == "object":
            assert definition["additionalProperties"] is False


def test_schema_uses_toml_spelling_of_aliased_keys() -> None:
    edge = json.loads(policy_schema_text())["$defs"]["Edge"]
    assert set(edge["properties"]) == {"from", "to"}
