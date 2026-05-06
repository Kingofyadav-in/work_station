#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT_DIR / "shared" / "intent_schema.json"


class ValidationError(Exception):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid JSON in {path}: {exc}") from exc


def load_schema(path: Path = SCHEMA_PATH) -> dict[str, Any]:
    return load_json(path)


def _require(message: dict[str, Any], field: str) -> None:
    if field not in message:
        raise ValidationError(f"Missing required field: {field}")


def _expect_type(name: str, value: Any, typ: type) -> None:
    if not isinstance(value, typ):
        raise ValidationError(f"{name} must be {typ.__name__}, got {type(value).__name__}")


def _expect_enum(name: str, value: str, allowed: list[str]) -> None:
    if value not in allowed:
        raise ValidationError(f"{name} must be one of {allowed}, got {value!r}")


def validate_message_dict(message: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = schema or load_schema()

    for field in schema.get("required", []):
        _require(message, field)

    allowed_top = set(schema.get("properties", {}).keys())
    extra = set(message.keys()) - allowed_top
    if extra:
        raise ValidationError(f"Unexpected top-level field(s): {sorted(extra)}")

    _expect_type("version", message["version"], str)
    _expect_type("intent", message["intent"], str)
    _expect_type("source", message["source"], str)
    _expect_type("target", message["target"], str)
    _expect_type("payload", message["payload"], dict)
    _expect_type("timestamp", message["timestamp"], str)

    _expect_enum("source", message["source"], schema["properties"]["source"]["enum"])
    _expect_enum("target", message["target"], schema["properties"]["target"]["enum"])
    intent_enum = schema["properties"].get("intent", {}).get("enum")
    if intent_enum:
        _expect_enum("intent", message["intent"], intent_enum)

    if "priority" in message:
        _expect_type("priority", message["priority"], str)
        _expect_enum("priority", message["priority"], schema["properties"]["priority"]["enum"])

    if "request_id" in message:
        _expect_type("request_id", message["request_id"], str)

    if "meta" in message:
        _expect_type("meta", message["meta"], dict)

    payload = message["payload"]
    if "text" in payload:
        _expect_type("payload.text", payload["text"], str)
    if "args" in payload:
        _expect_type("payload.args", payload["args"], dict)

    return message


def validate_message_file(path: Path) -> dict[str, Any]:
    return validate_message_dict(load_json(path))
