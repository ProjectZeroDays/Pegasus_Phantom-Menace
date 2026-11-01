import pytest

from pegasus.modules.ai import grammar, schema_lint, schemas

WIDE = {"type": "object", "additionalProperties": False, "required": ["a"],
        "properties": {**{f"o{i}": {"type": "string"} for i in range(9)},
                       "a": {"type": "string"}}}


def test_all_schemas_lint_clean():
    for name, schema in schemas.REGISTRY.items():
        assert schema_lint.lint(schema) == [], name


def test_open_schema_rejected():
    with pytest.raises(ValueError):
        grammar.gbnf({"type": "object"})


def test_wide_schema_promotes():
    compiled = grammar.gbnf(WIDE)
    assert compiled.count("?") <= 6
    assert len(compiled) < grammar.MAX_CHARS


def test_nested_object_flagged():
    bad = {"type": "object", "additionalProperties": False, "properties": {
        "a": {"type": "object"}}}
    assert any("nested" in e for e in schema_lint.lint(bad))
