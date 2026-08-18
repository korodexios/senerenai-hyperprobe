"""Persistent settings for the optional refusal and NIAH probes."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent
PROBE_SETTINGS_PATH = Path(os.getenv("HYPERPROBE_PROBE_SETTINGS_FILE", ROOT_DIR / "hyperprobe.probes.local.json"))
PROBE_SETTINGS_SCHEMA_VERSION = 1
PROBE_MODES = ("refusal", "niah")
PRESET_MODES = ("baseline", "final", "compare", "mini-sweep", "manual")
DEFAULT_NIAH_CONTEXT_SIZES = [4000, 16000, 32000]
DEFAULT_NIAH_DEPTHS = [10, 50, 90]

DEFAULT_PROBE_SETTINGS: dict[str, Any] = {
    "schema_version": PROBE_SETTINGS_SCHEMA_VERSION,
    "enabled_modes": ["refusal"],
    "preset": "compare",
    "manual_preset": "",
    "preset_profile": "roleplay",
    "language": "",
    "refusal_dataset": "datasets/refusal/refusal_safe_v1.jsonl",
    "niah_corpus": "",
    "niah_context_sizes": DEFAULT_NIAH_CONTEXT_SIZES,
    "niah_depths": DEFAULT_NIAH_DEPTHS,
    "refusal_samples": 2,
    "niah_samples": 1,
    "timeout": 180,
    "thinking": False,
    "regenerate_dashboard": True,
}


def _merge(raw: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(DEFAULT_PROBE_SETTINGS)
    if isinstance(raw, dict):
        for key in DEFAULT_PROBE_SETTINGS:
            if key in raw:
                merged[key] = raw[key]
    merged["schema_version"] = PROBE_SETTINGS_SCHEMA_VERSION
    modes = merged.get("enabled_modes", [])
    if isinstance(modes, str):
        modes = [item.strip().lower() for item in modes.split(",")]
    merged["enabled_modes"] = [mode for mode in modes if mode in PROBE_MODES] or ["refusal"]
    merged["preset"] = str(merged.get("preset", "compare")) if merged.get("preset") in PRESET_MODES else "compare"
    merged["preset_profile"] = str(merged.get("preset_profile", "roleplay"))
    merged["language"] = str(merged.get("language", "")).strip()
    merged["refusal_dataset"] = str(merged.get("refusal_dataset", DEFAULT_PROBE_SETTINGS["refusal_dataset"])).strip()
    merged["niah_corpus"] = str(merged.get("niah_corpus", "")).strip()
    for key, default, minimum, maximum in (
        ("niah_context_sizes", DEFAULT_NIAH_CONTEXT_SIZES, 256, 1_000_000),
        ("niah_depths", DEFAULT_NIAH_DEPTHS, 0, 100),
    ):
        values = merged.get(key, default)
        if isinstance(values, str):
            try:
                values = [int(item.strip()) for item in values.split(",") if item.strip()]
            except ValueError:
                values = list(default)
        if not isinstance(values, list) or not values or any(not isinstance(item, int) or item < minimum or item > maximum for item in values):
            values = list(default)
        merged[key] = values
    for key, default in (("refusal_samples", 2), ("niah_samples", 1), ("timeout", 180)):
        value = merged.get(key, default)
        merged[key] = value if isinstance(value, int) and value >= 1 else default
    merged["thinking"] = bool(merged.get("thinking", False))
    merged["regenerate_dashboard"] = bool(merged.get("regenerate_dashboard", True))
    return merged


def load_probe_settings(path: Path = PROBE_SETTINGS_PATH) -> dict[str, Any]:
    try:
        return _merge(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_PROBE_SETTINGS)


def validate_probe_settings(settings: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not settings.get("enabled_modes") or any(mode not in PROBE_MODES for mode in settings["enabled_modes"]):
        errors.append("enabled_modes must contain refusal and/or niah")
    if settings.get("preset") not in PRESET_MODES:
        errors.append("preset must be baseline, final, compare, mini-sweep, or manual")
    if settings.get("preset") == "manual" and not settings.get("manual_preset"):
        errors.append("manual_preset is required when preset is manual")
    if "niah" in settings.get("enabled_modes", []) and not str(settings.get("niah_corpus", "")).strip():
        errors.append("niah_corpus is required when niah mode is enabled")
    for key in ("refusal_samples", "niah_samples", "timeout"):
        if not isinstance(settings.get(key), int) or settings[key] < 1:
            errors.append(f"{key} must be a positive integer")
    return errors


def save_probe_settings(settings: dict[str, Any], path: Path = PROBE_SETTINGS_PATH) -> Path:
    normalized = _merge(settings)
    errors = validate_probe_settings(normalized)
    if errors:
        raise ValueError("Invalid probe settings: " + "; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path
