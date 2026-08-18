"""Shared utilities for optional Senerenai-HyperProbe diagnostic probes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from common import RESULTS_DIR, fingerprint, safe_model_name, utc_now

PROBE_RESULTS_DIR = RESULTS_DIR / "probes"
PROBE_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

BASELINE_PRESET = {
    "temperature": 0.6,
    "min_p": 0.05,
    "top_p": 0.9,
    "repetition_penalty": 1.05,
}


def final_preset_path(profile: str, model: str, language: str | None = None) -> Path:
    suffix = f"_{language}" if language else ""
    return RESULTS_DIR / f"final_preset_{profile}_{safe_model_name(model)}{suffix}.json"


def load_final_preset(profile: str, model: str, language: str | None = None) -> tuple[dict, dict]:
    """Load the latest final Stage 3 preset for a profile and model."""
    path = final_preset_path(profile, model, language)
    if not path.exists():
        raise FileNotFoundError(
            f"Final preset not found: {path}. Run the Stage 1–3 pipeline first, or use --preset baseline."
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    params = payload.get("sampling_parameters")
    if not isinstance(params, dict):
        raise ValueError(f"Final preset has no sampling_parameters object: {path}")
    return params, payload


def parse_manual_preset(raw: str) -> dict:
    """Parse a JSON sampling-parameter object supplied by an advanced user."""
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("--manual-preset must be a JSON object.") from exc
    if not isinstance(value, dict):
        raise ValueError("--manual-preset must be a JSON object.")
    required = set(BASELINE_PRESET)
    missing = sorted(required - set(value))
    if missing:
        raise ValueError("Manual preset is missing: " + ", ".join(missing))
    return {key: value[key] for key in BASELINE_PRESET}


def select_presets(
    mode: str,
    *,
    profile: str,
    model: str,
    language: str | None = None,
    manual_preset: str | None = None,
) -> list[dict]:
    """Return labelled probe presets without mutating the tuning pipeline."""
    rows: list[dict] = []
    if mode in {"baseline", "compare", "mini-sweep"}:
        rows.append({"label": "baseline", "params": dict(BASELINE_PRESET), "source": "probe baseline"})
    if mode in {"final", "compare", "mini-sweep"}:
        final, payload = load_final_preset(profile, model, language)
        rows.append({
            "label": f"final_{profile}",
            "params": final,
            "source": "Stage 3 final preset",
            "benchmark_id": payload.get("benchmark_id"),
        })
    if mode == "mini-sweep":
        rows.extend([
            {"label": "low_temperature", "params": {**BASELINE_PRESET, "temperature": 0.2}, "source": "probe mini-sweep"},
            {"label": "high_temperature", "params": {**BASELINE_PRESET, "temperature": 0.9}, "source": "probe mini-sweep"},
        ])
    if mode == "manual":
        if not manual_preset:
            raise ValueError("--manual-preset is required when --preset manual is selected.")
        rows.append({"label": "manual", "params": parse_manual_preset(manual_preset), "source": "manual"})

    deduplicated: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        key = fingerprint(row["params"], length=64)
        if key not in seen:
            seen.add(key)
            row["param_hash"] = fingerprint(row["params"])
            deduplicated.append(row)
    return deduplicated


def new_probe_id(mode: str, model: str, preset_rows: list[dict], extra: dict[str, Any]) -> str:
    """Create a stable per-execution identity while retaining collision resistance."""
    return fingerprint({
        "kind": f"probe_{mode}", "model": model, "presets": preset_rows,
        "extra": extra, "created_at": utc_now(),
    })


def probe_summary_path(mode: str, model: str, probe_id: str) -> Path:
    return PROBE_RESULTS_DIR / f"{mode}_{safe_model_name(model)}_{probe_id}.json"


def save_probe_summary(mode: str, model: str, probe_id: str, payload: dict) -> Path:
    """Write an immutable probe summary and an updated latest pointer."""
    payload = {**payload, "probe_id": probe_id, "saved_at": utc_now()}
    archive = probe_summary_path(mode, model, probe_id)
    latest = PROBE_RESULTS_DIR / f"{mode}_{safe_model_name(model)}.json"
    encoded = json.dumps(payload, indent=2, ensure_ascii=False)
    archive.write_text(encoded, encoding="utf-8")
    latest.write_text(encoded, encoding="utf-8")
    print(f"Saved probe archive to {archive}")
    print(f"Updated latest {mode} probe pointer: {latest}")
    return archive


def mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0
