"""Persistent local settings for the beginner-friendly Senerenai-HyperProbe workflow.

The local JSON file is deliberately ignored by Git because it may contain an API
key or a private endpoint. Environment variables always override saved values.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = Path(os.getenv("HYPERPROBE_SETTINGS_FILE", ROOT_DIR / "hyperprobe.local.json"))
SETTINGS_SCHEMA_VERSION = 2
PROFILE_CHOICES = ("coding", "agent_tools", "creative", "roleplay", "custom_lang")
LANGUAGE_CHOICES = (
    ("en", "English"), ("zh", "Mandarin Chinese"), ("hi", "Hindi"), ("es", "Spanish"),
    ("ar", "Arabic"), ("fr", "French"), ("bn", "Bengali"), ("pt", "Portuguese"),
    ("id", "Indonesian"), ("ur", "Urdu"), ("ru", "Russian"), ("de", "German"),
    ("ja", "Japanese"), ("ko", "Korean"), ("tr", "Turkish"), ("pl", "Polish"),
    ("cs", "Czech"), ("sk", "Slovak"),
)
LANGUAGE_CODES = tuple(code for code, _ in LANGUAGE_CHOICES)
LANGUAGE_ALIASES = {"cz": "cs", "cn": "zh", "jp": "ja", "kr": "ko"}
SAMPLER_CAPABILITY_CHOICES = (
    "temperature", "min_p", "top_p", "top_k", "repetition_penalty",
    "presence_penalty", "frequency_penalty",
)
CORE_SAMPLER_CAPABILITIES = ("temperature", "min_p", "top_p", "repetition_penalty")


def normalize_language_code(value: str) -> str:
    code = value.strip().lower()
    return LANGUAGE_ALIASES.get(code, code)


DEFAULT_SETTINGS: dict[str, Any] = {
    "schema_version": SETTINGS_SCHEMA_VERSION,
    "api_base": "http://localhost:8080/v1",
    "api_key": "Bearer llama.cpp",
    "model": "",
    "backend_label": "",
    "sampler_capabilities": list(CORE_SAMPLER_CAPABILITIES),
    "timeout": 180,
    "concurrency": 1,
    "max_tokens": 2048,
    "retry": True,
    "thinking": False,
    "stage1_samples": 2,
    "stage2_samples": 1,
    "stage2_max_combos": 5,
    "stage3_samples": 1,
    "stage3_top_n": 2,
    "default_profiles": ["coding"],
    "default_languages": [],
    "default_workflow": "full",
    # Kept for compatibility with settings files created before multi-language selection.
    "default_language": "",
}


def _merged_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Merge a safe subset of local JSON values with public defaults."""
    merged = dict(DEFAULT_SETTINGS)
    if not isinstance(raw, dict):
        return merged
    for key in DEFAULT_SETTINGS:
        if key in raw:
            merged[key] = raw[key]
    merged["schema_version"] = SETTINGS_SCHEMA_VERSION
    profiles = merged.get("default_profiles", [])
    merged["default_profiles"] = [name for name in profiles if name in PROFILE_CHOICES] or ["coding"]
    languages = merged.get("default_languages", [])
    if not languages:
        legacy_language = str(merged.get("default_language", "")).strip()
        languages = [item.strip().lower() for item in legacy_language.split(",") if item.strip()]
    merged["default_languages"] = [normalize_language_code(str(code)) for code in languages if normalize_language_code(str(code)) in LANGUAGE_CODES]
    merged["default_language"] = merged["default_languages"][0] if len(merged["default_languages"]) == 1 else ""
    raw_capabilities = merged.get("sampler_capabilities", CORE_SAMPLER_CAPABILITIES)
    if isinstance(raw_capabilities, str):
        raw_capabilities = [item.strip() for item in raw_capabilities.split(",")]
    merged["sampler_capabilities"] = [
        str(item).strip() for item in raw_capabilities
        if str(item).strip() in SAMPLER_CAPABILITY_CHOICES
    ] or list(CORE_SAMPLER_CAPABILITIES)
    merged["backend_label"] = str(merged.get("backend_label", "")).strip()
    return merged


def load_settings(path: Path = SETTINGS_PATH) -> dict[str, Any]:
    """Load local settings; malformed or missing files fall back to defaults."""
    try:
        return _merged_settings(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_SETTINGS)


def validate_settings(settings: dict[str, Any]) -> list[str]:
    """Return human-readable validation errors without exposing secret values."""
    errors: list[str] = []
    api_base = str(settings.get("api_base", "")).strip()
    if not api_base.startswith(("http://", "https://")):
        errors.append("api_base must start with http:// or https://")
    for field in ("timeout", "concurrency", "max_tokens", "stage1_samples", "stage2_samples", "stage2_max_combos", "stage3_samples", "stage3_top_n"):
        value = settings.get(field)
        if not isinstance(value, int) or value < 1:
            errors.append(f"{field} must be a positive integer")
    languages = settings.get("default_languages", [])
    if not isinstance(languages, list) or any(code not in LANGUAGE_CODES for code in languages):
        errors.append("default_languages must contain only supported language codes")
    if settings.get("default_workflow") not in {"stage1", "stage2", "stage3", "full", "dashboard"}:
        errors.append("default_workflow must be stage1, stage2, stage3, full, or dashboard")
    backend_label = str(settings.get("backend_label", ""))
    if len(backend_label) > 120:
        errors.append("backend_label must be at most 120 characters")
    capabilities = settings.get("sampler_capabilities", [])
    if not isinstance(capabilities, list) or any(item not in SAMPLER_CAPABILITY_CHOICES for item in capabilities):
        errors.append("sampler_capabilities must contain only supported parameter names")
    elif not set(CORE_SAMPLER_CAPABILITIES).issubset(capabilities):
        errors.append("sampler_capabilities must include the four core benchmark parameters")
    return errors


def save_settings(settings: dict[str, Any], path: Path = SETTINGS_PATH) -> Path:
    """Validate and persist settings with owner-only permissions where possible."""
    normalized = _merged_settings(settings)
    errors = validate_settings(normalized)
    if errors:
        raise ValueError("Invalid local settings: " + "; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def mask_secret(value: str) -> str:
    """Display an API key safely in terminal summaries."""
    if not value:
        return "(not set)"
    if len(value) <= 8:
        return "********"
    return f"{value[:4]}…{value[-4:]}"


def parse_selection(raw: str, options: list[str]) -> list[str]:
    """Parse comma-separated one-based indexes, names, or `all` without duplicates."""
    choice = raw.strip().lower()
    if choice in {"all", "*"}:
        return list(options)
    selected: list[str] = []
    for token in (item.strip() for item in raw.split(",")):
        if not token:
            continue
        if token.isdigit() and 1 <= int(token) <= len(options):
            value = options[int(token) - 1]
        elif token in options:
            value = token
        else:
            raise ValueError(f"Unknown selection: {token}")
        if value not in selected:
            selected.append(value)
    if not selected:
        raise ValueError("Select at least one option.")
    return selected


def settings_environment(settings: dict[str, Any]) -> dict[str, str]:
    """Build child-process environment values; do not print this mapping."""
    env = os.environ.copy()
    values = {
        "HYPERPROBE_API_BASE": str(settings["api_base"]).rstrip("/"),
        "HYPERPROBE_API_KEY": str(settings.get("api_key", "")),
        "HYPERPROBE_TIMEOUT": str(settings["timeout"]),
        "HYPERPROBE_CONCURRENCY": str(settings["concurrency"]),
        "HYPERPROBE_MAX_TOKENS": str(settings["max_tokens"]),
        "HYPERPROBE_RETRY": "1" if settings.get("retry", True) else "0",
        "HYPERPROBE_BACKEND_LABEL": str(settings.get("backend_label", "")),
        "HYPERPROBE_SAMPLER_CAPABILITIES": ",".join(settings.get("sampler_capabilities", CORE_SAMPLER_CAPABILITIES)),
    }
    env.update(values)
    return env
