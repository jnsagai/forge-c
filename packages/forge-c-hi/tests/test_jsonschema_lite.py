"""T007: the stdlib JSON-Schema subset used by the contracts."""
from __future__ import annotations

import pytest

from forge_hi.jsonschema_lite import SchemaError, validate


def errs(instance, schema):
    return validate(instance, schema)


@pytest.mark.parametrize(
    "schema,good,bad",
    [
        ({"type": "string"}, "x", 1),
        ({"type": "integer"}, 3, True),  # bool is not an integer
        ({"type": "integer"}, 3, 3.5),
        ({"type": "number"}, 3.5, "3"),
        ({"type": ["string", "null"]}, None, 1),
        ({"type": "boolean"}, False, 0),
        ({"type": "array"}, [], {}),
        ({"type": "object"}, {}, []),
        ({"enum": ["a", "b"]}, "a", "c"),
        ({"const": "k"}, "k", "K"),
        ({"pattern": "^HI-[0-4]$"}, "HI-2", "HI-5"),
        ({"minLength": 2}, "ab", "a"),
        ({"maxLength": 2}, "ab", "abc"),
        ({"minimum": 1}, 1, 0),
        ({"maximum": 100}, 100, 101),
        ({"minItems": 1}, [1], []),
        ({"maxItems": 1}, [1], [1, 2]),
        ({"items": {"type": "integer"}}, [1, 2], [1, "2"]),
        ({"required": ["a"]}, {"a": 1}, {}),
        ({"properties": {"a": {"type": "integer"}}}, {"a": 1}, {"a": "1"}),
        ({"properties": {"a": {}}, "additionalProperties": False}, {"a": 1}, {"a": 1, "b": 2}),
        ({"additionalProperties": {"type": "integer"}}, {"x": 1}, {"x": "1"}),
        ({"propertyNames": {"pattern": "^HI-"}}, {"HI-1": 1}, {"LV-1": 1}),
        ({"oneOf": [{"type": "string"}, {"type": "integer"}]}, "x", None),
        ({"allOf": [{"type": "string"}, {"minLength": 2}]}, "ab", "a"),
        (
            {"if": {"properties": {"d": {"const": True}}}, "then": {"required": ["r"]}},
            {"d": True, "r": "x"},
            {"d": True},
        ),
    ],
)
def test_keyword_good_and_bad(schema, good, bad):
    assert errs(good, schema) == []
    assert errs(bad, schema) != []


def test_oneof_rejects_multiple_matches():
    schema = {"oneOf": [{"type": "integer"}, {"minimum": 0}]}
    assert errs(5, schema) != []


def test_if_without_match_skips_then():
    schema = {"if": {"properties": {"d": {"const": True}}}, "then": {"required": ["r"]}}
    assert errs({"d": False}, schema) == []


def test_error_paths_are_json_pointers():
    schema = {"properties": {"items": {"items": {"properties": {"id": {"pattern": "^A"}}}}}}
    out = errs({"items": [{"id": "A1"}, {"id": "B2"}]}, schema)
    assert out and out[0].startswith("/items/1/id")


def test_unknown_keyword_is_refused():
    with pytest.raises(SchemaError):
        errs("x", {"format": "email"})


def test_annotation_keywords_ignored():
    schema = {"$schema": "x", "$id": "y", "title": "t", "description": "d", "default": 1, "type": "integer"}
    assert errs(1, schema) == []
