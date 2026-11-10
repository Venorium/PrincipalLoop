"""Exchange validation: versioned shapes, no network resolution."""

from __future__ import annotations

from functools import lru_cache
from importlib.metadata import distribution
import json
import math
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource


class ContractError(ValueError):
    """Non-conforming output; never converted into NO_CHANGE."""


MAX_JSON_BYTES = 1_048_576


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ContractError(f"Non-finite JSON number: {value}")


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ContractError("JSON number exceeds finite float range")
    return number


def decode_json(payload: str | bytes) -> Any:
    try:
        if not isinstance(payload, (str, bytes)):
            raise ContractError("Expected JSON text or bytes")
        if len(payload) > MAX_JSON_BYTES or (isinstance(payload, str) and len(payload.encode("utf-8")) > MAX_JSON_BYTES):
            raise ContractError("JSON payload exceeds 1 MiB admission limit")
        return json.loads(payload, object_pairs_hook=_object, parse_constant=_reject_constant, parse_float=_finite_float)
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise ContractError(str(error)) from error


def _no_remote(uri):
    raise NoSuchResource(ref=uri)


@lru_cache(maxsize=1)
def _catalog():
    schemas = {}
    registry = Registry(retrieve=_no_remote)
    # The data ships inside the distribution, editable installs included.
    # Never look up the repository through cwd: a wheel must be self-contained.
    schema_directory = distribution("principalloop").locate_file("principalloop/schemas")
    for path in schema_directory.iterdir():
        if path.name.endswith(".schema.json"):
            schema = decode_json(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            schemas[path.name.removesuffix(".schema.json")] = schema
            registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    checker = FormatChecker()
    if checker.conforms("invalid-date", "date-time"):
        raise RuntimeError("RFC3339 validation unavailable; install the locked dependencies")
    return {name: Draft202012Validator(schema, registry=registry, format_checker=checker) for name, schema in schemas.items()}


def contract_names() -> tuple[str, ...]:
    return tuple(sorted(_catalog()))


def validate_contract(name: str, payload: str | bytes | dict) -> dict:
    """Return a JSON copy; infer neither authority nor truth from the content."""
    if name not in _catalog():
        raise ContractError(f"Unknown contract: {name}")
    try:
        raw = json.dumps(payload, allow_nan=False) if isinstance(payload, dict) else payload
        value = decode_json(raw)
    except (TypeError, ValueError, RecursionError) as error:
        raise ContractError(str(error)) from error
    errors = sorted(_catalog()[name].iter_errors(value), key=lambda error: str(list(error.path)))
    if errors:
        error = errors[0]
        location = "/".join(map(str, error.path)) or "$"
        raise ContractError(f"{name}:{location}: {error.message[:512]}")
    if name == "director-turn" and value["proposal"] is not None:
        proposal = value["proposal"]
        if value["project_id"] != proposal["project_id"] or value["snapshot_id"] != proposal["basis_snapshot_id"]:
            raise ContractError("director-turn: proposal and envelope must reference the same project and snapshot")
    return value
