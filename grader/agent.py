"""Deterministic grader for structured tool-calling benchmark responses."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from config import SCORING_WEIGHTS
from grader.repetition import detect_degeneration


@dataclass
class GradeResult:
    dimensions: dict = field(default_factory=dict)
    weighted_score: float = 0.0
    flags: list = field(default_factory=list)
    raw_length: int = 0


def extract_json_object(text: str) -> tuple[dict | None, float]:
    """Parse one JSON object and return a syntax-fidelity score."""
    candidate = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, re.DOTALL | re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1)
    try:
        parsed = json.loads(candidate)
        return (parsed if isinstance(parsed, dict) else None), 1.0 if isinstance(parsed, dict) else 0.0
    except json.JSONDecodeError:
        fragment = re.search(r"(\{.*\})", text, re.DOTALL)
        if not fragment:
            return None, 0.0
        try:
            parsed = json.loads(fragment.group(1))
            return (parsed if isinstance(parsed, dict) else None), 0.70 if isinstance(parsed, dict) else 0.0
        except json.JSONDecodeError:
            return None, 0.0


def _matches_type(value: Any, expected: str) -> bool:
    types = {
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "array": lambda item: isinstance(item, list),
        "object": lambda item: isinstance(item, dict),
    }
    return types.get(expected, lambda _: False)(value)


def validate_value(value: Any, schema: dict, path: str = "parameter") -> list[str]:
    """Return deterministic schema validation errors for one JSON value."""
    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type and not _matches_type(value, expected_type):
        return [f"{path}:expected_{expected_type}"]
    if "equals" in schema and value != schema["equals"]:
        errors.append(f"{path}:unexpected_value")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}:not_in_enum")
    if "contains" in schema and str(schema["contains"]).lower() not in str(value).lower():
        errors.append(f"{path}:missing_expected_content")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}:below_minimum")
    if isinstance(value, list):
        if "min_items" in schema and len(value) < schema["min_items"]:
            errors.append(f"{path}:too_few_items")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                errors.extend(validate_value(item, item_schema, f"{path}[{index}]"))
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}:missing")
        for key, child_schema in schema.get("properties", {}).items():
            if key in value:
                errors.extend(validate_value(value[key], child_schema, f"{path}.{key}"))
    return errors


def grade_agent(response: str, prompt_meta: dict) -> GradeResult:
    """Score JSON syntax, tool selection, argument shape, and output degeneration."""
    result = GradeResult(raw_length=len(response))
    text = response.strip()
    parsed, json_score = extract_json_object(text)
    result.dimensions["valid_json"] = json_score
    if json_score < 1.0:
        result.flags.append("invalid_or_embedded_json")

    expected_tool = prompt_meta.get("expected_tool")
    schema = prompt_meta.get("argument_schema", {})
    expected_args = prompt_meta.get("expected_args", list(schema))
    correct_tool = 0.0
    arguments_score = 0.0

    if parsed is not None:
        tool_name = parsed.get("tool") or parsed.get("name") or parsed.get("function")
        if tool_name == expected_tool:
            correct_tool = 1.0
        else:
            result.flags.append(f"wrong_tool:{tool_name}")

        arguments = parsed.get("parameters") or parsed.get("arguments")
        if arguments is None and all(key in parsed for key in expected_args):
            arguments = parsed
        if isinstance(arguments, dict):
            if schema:
                valid_fields = 0
                for field_name, field_schema in schema.items():
                    if field_name not in arguments:
                        result.flags.append(f"argument_missing:{field_name}")
                        continue
                    errors = validate_value(arguments[field_name], field_schema, field_name)
                    if errors:
                        result.flags.extend(f"argument_invalid:{error}" for error in errors)
                    else:
                        valid_fields += 1
                arguments_score = valid_fields / max(len(schema), 1)
            elif expected_args:
                arguments_score = sum(name in arguments for name in expected_args) / len(expected_args)
            else:
                arguments_score = 1.0
        else:
            result.flags.append("arguments_not_object")

    result.dimensions["correct_tool"] = correct_tool
    result.dimensions["arguments_valid"] = arguments_score
    degeneration = detect_degeneration(text)
    result.dimensions["no_repetition"] = degeneration["score"]
    result.flags.extend(degeneration["flags"])
    result.weighted_score = sum(
        result.dimensions.get(name, 0.0) * weight
        for name, weight in SCORING_WEIGHTS["agent_tools"].items()
    )
    return result
