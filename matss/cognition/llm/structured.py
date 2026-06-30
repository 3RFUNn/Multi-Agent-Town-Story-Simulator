"""Minimal JSON-schema validation and coercion for structured LLM output.

The LLM stack does not depend on third-party schema libraries (``jsonschema``,
``pydantic``); core logic is stdlib-only. This module implements just the slice
of JSON-schema the engine actually uses for structured generation:

* object ``type`` with ``properties`` and ``required`` keys;
* scalar ``type`` constraints (``string``, ``integer``, ``number``, ``boolean``,
  ``array``, ``object``);
* deterministic stub-value synthesis for required keys (used by the mock
  provider and by adapters that must guarantee a schema-shaped result).

It is intentionally permissive: extra keys are tolerated, and coercion is
best-effort so a slightly off-spec model response is repaired rather than
rejected outright.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# JSON-schema ``type`` -> the Python types accepted as already-valid.
_TYPE_MAP: Dict[str, Tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
}


class SchemaError(ValueError):
    """Raised when a value cannot be validated/coerced against a schema."""


def required_keys(schema: Dict[str, Any]) -> List[str]:
    """Return the declared ``required`` keys of an object schema (or ``[]``)."""
    req = schema.get("required")
    if not req:
        return []
    return [str(k) for k in req]


def _properties(schema: Dict[str, Any]) -> Dict[str, Any]:
    props = schema.get("properties")
    return props if isinstance(props, dict) else {}


def stub_value(schema: Dict[str, Any], seed: int = 0) -> Any:
    """Synthesise a deterministic placeholder value satisfying ``schema``.

    Args:
        schema: A JSON-schema fragment describing one value.
        seed: A deterministic integer mixed into numeric/string stubs so that
            distinct fields receive distinguishable (but stable) values.

    Returns:
        A Python value of the schema's declared ``type`` (defaulting to a
        string when no type is given).
    """
    schema_type = schema.get("type", "string")
    if schema_type == "object":
        out: Dict[str, Any] = {}
        props = _properties(schema)
        for i, key in enumerate(required_keys(schema)):
            sub = props.get(key, {"type": "string"})
            out[key] = stub_value(sub, seed + i + 1)
        return out
    if schema_type == "array":
        item_schema = schema.get("items", {"type": "string"})
        return [stub_value(item_schema, seed + 1)]
    if schema_type == "integer":
        return seed
    if schema_type == "number":
        return float(seed)
    if schema_type == "boolean":
        return bool(seed % 2)
    # string (and any unknown/leaf type) -> a stable readable placeholder.
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[seed % len(enum)]
    return f"stub_{seed}"


def build_stub(schema: Dict[str, Any], seed: int = 0) -> Dict[str, Any]:
    """Build a deterministic stub dict covering an object schema's required keys.

    Args:
        schema: A JSON-schema object (``type: object``).
        seed: Deterministic seed mixed into the generated values.

    Returns:
        A dict whose keys are exactly the schema's ``required`` keys, each mapped
        to a deterministic stub value of the declared property type.
    """
    props = _properties(schema)
    out: Dict[str, Any] = {}
    for i, key in enumerate(required_keys(schema)):
        sub = props.get(key, {"type": "string"})
        out[key] = stub_value(sub, seed + i + 1)
    return out


def _coerce_scalar(value: Any, schema_type: str) -> Any:
    """Best-effort coerce a scalar ``value`` to ``schema_type``."""
    if schema_type == "string":
        return value if isinstance(value, str) else str(value)
    if schema_type == "integer":
        if isinstance(value, bool):
            return int(value)
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise SchemaError(f"cannot coerce {value!r} to integer") from exc
    if schema_type == "number":
        if isinstance(value, bool):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise SchemaError(f"cannot coerce {value!r} to number") from exc
    if schema_type == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1", "yes")
        return bool(value)
    return value


def coerce(value: Any, schema: Dict[str, Any]) -> Any:
    """Coerce ``value`` to conform to ``schema`` (recursively for objects/arrays).

    Args:
        value: The value to coerce.
        schema: The JSON-schema fragment to coerce towards.

    Returns:
        A coerced value matching the schema's declared shape.
    """
    schema_type = schema.get("type", "string")
    if schema_type == "object":
        result = dict(value) if isinstance(value, dict) else {}
        props = _properties(schema)
        for i, key in enumerate(required_keys(schema)):
            sub = props.get(key, {"type": "string"})
            if key in result:
                result[key] = coerce(result[key], sub)
            else:
                result[key] = stub_value(sub, i + 1)
        return result
    if schema_type == "array":
        item_schema = schema.get("items", {"type": "string"})
        seq = value if isinstance(value, list) else [value]
        return [coerce(v, item_schema) for v in seq]
    return _coerce_scalar(value, schema_type)


def validate(value: Any, schema: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate ``value`` against ``schema`` without coercion.

    Args:
        value: The value to validate.
        schema: The JSON-schema fragment to validate against.

    Returns:
        ``(True, None)`` when valid; otherwise ``(False, reason)``.
    """
    schema_type = schema.get("type")
    if schema_type and schema_type in _TYPE_MAP:
        # ``bool`` is a subclass of ``int`` — reject it for integer/number.
        if schema_type in ("integer", "number") and isinstance(value, bool):
            return False, f"expected {schema_type}, got boolean"
        if not isinstance(value, _TYPE_MAP[schema_type]):
            return False, f"expected {schema_type}, got {type(value).__name__}"
    if schema_type == "object":
        if not isinstance(value, dict):
            return False, "expected object"
        props = _properties(schema)
        for key in required_keys(schema):
            if key not in value:
                return False, f"missing required key {key!r}"
            ok, reason = validate(value[key], props.get(key, {}))
            if not ok:
                return False, f"{key}: {reason}"
    elif schema_type == "array":
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(value):
                ok, reason = validate(item, item_schema)
                if not ok:
                    return False, f"[{i}]: {reason}"
    return True, None


def satisfies(value: Any, schema: Dict[str, Any]) -> bool:
    """Return ``True`` iff ``value`` validates against ``schema``."""
    ok, _ = validate(value, schema)
    return ok
