"""Shared utilities for optional Senerenai-HyperProbe diagnostic probes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from common import RESULTS_DIR, fingerprint, format_duration, safe_model_name, utc_now

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


def _percentile(values: list[float], percentile: float) -> float | None:
    """Return a linearly interpolated percentile without external dependencies."""
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 3)


def _token_summary(rows: list[dict], value_key: str, reported_key: str) -> dict[str, Any]:
    """Summarize only tokens explicitly returned by the provider, never estimates."""
    values: list[int] = []
    for row in rows:
        result = row.get("result", {})
        value = result.get(value_key)
        explicit = result.get(reported_key)
        # Older local mock records may lack the availability flag. A positive
        # value remains usable; zero with no flag is correctly treated as unknown.
        reported = bool(explicit) if explicit is not None else isinstance(value, (int, float)) and value > 0
        if reported and isinstance(value, (int, float)):
            values.append(int(value))
    attempted = len(rows)
    if not values:
        return {
            "status": "not_reported_by_api",
            "reported_calls": 0,
            "missing_calls": attempted,
            "total": None,
            "mean_per_reported_call": None,
        }
    return {
        "status": "partial" if len(values) < attempted else "reported",
        "reported_calls": len(values),
        "missing_calls": attempted - len(values),
        "total": sum(values),
        "mean_per_reported_call": round(sum(values) / len(values), 2),
    }


def build_probe_run_statistics(
    rows: list[dict],
    *,
    started_at: str,
    finished_at: str,
    wall_elapsed_seconds: float,
) -> dict[str, Any]:
    """Create one honest telemetry summary for refusal or NIAH probe runs."""
    attempted = len(rows)
    failed = sum(1 for row in rows if "error" in row.get("result", {}))
    succeeded = attempted - failed
    latencies = [float(row.get("elapsed", 0.0) or 0.0) for row in rows if float(row.get("elapsed", 0.0) or 0.0) >= 0]
    latency = {
        "mean": round(sum(latencies) / len(latencies), 3) if latencies else None,
        "p50": _percentile(latencies, 0.50),
        "p95": _percentile(latencies, 0.95),
        "minimum": round(min(latencies), 3) if latencies else None,
        "maximum": round(max(latencies), 3) if latencies else None,
        "aggregate_request_seconds": round(sum(latencies), 3) if latencies else 0.0,
    }
    wall = max(float(wall_elapsed_seconds), 0.0)
    return {
        "started_at": started_at,
        "finished_at": finished_at,
        "wall_elapsed_seconds": round(wall, 3),
        "wall_elapsed_human": format_duration(wall),
        "attempted_calls": attempted,
        "successful_calls": succeeded,
        "failed_calls": failed,
        "success_rate": round(succeeded / attempted, 4) if attempted else 0.0,
        "throughput_successful_calls_per_minute": round(succeeded / (wall / 60), 3) if wall >= 1.0 else None,
        "request_latency_seconds": latency,
        "completion_tokens": _token_summary(rows, "tokens", "completion_tokens_reported"),
        "prompt_tokens": _token_summary(rows, "prompt_tokens", "prompt_tokens_reported"),
    }


def _display_token_summary(label: str, summary: dict[str, Any]) -> str:
    if summary["status"] == "not_reported_by_api":
        return f"  {label}: not reported by API"
    missing = f"; {summary['missing_calls']} call(s) missing" if summary["missing_calls"] else ""
    return (
        f"  {label}: {summary['total']:,} total across {summary['reported_calls']} reported call(s) "
        f"({summary['mean_per_reported_call']:.1f} average){missing}"
    )


def print_probe_run_statistics(title: str, statistics: dict[str, Any]) -> None:
    """Print a compact, human-readable probe summary after a completed run."""
    latency = statistics["request_latency_seconds"]
    print("\n" + "=" * 70)
    print(f"  {title} — RUN SUMMARY")
    print(f"  Started (UTC): {statistics['started_at']}")
    print(f"  Finished (UTC): {statistics['finished_at']}")
    print(f"  Wall-clock elapsed: {statistics['wall_elapsed_human']}")
    print(
        f"  Calls: {statistics['attempted_calls']} attempted | {statistics['successful_calls']} successful | "
        f"{statistics['failed_calls']} failed | {statistics['success_rate']:.1%} success"
    )
    throughput = statistics["throughput_successful_calls_per_minute"]
    if throughput is not None:
        print(f"  Throughput: {throughput:.2f} successful calls/minute")
    if latency["mean"] is None:
        print("  Request latency: no completed request timings")
    else:
        print(
            f"  Request latency: mean {latency['mean']:.1f}s | p50 {latency['p50']:.1f}s | "
            f"p95 {latency['p95']:.1f}s | max {latency['maximum']:.1f}s"
        )
        print(
            f"  Aggregate request time: {format_duration(latency['aggregate_request_seconds'])} "
            "(can exceed wall-clock time when requests run concurrently)"
        )
    print(_display_token_summary("Output tokens", statistics["completion_tokens"]))
    print(_display_token_summary("Input tokens", statistics["prompt_tokens"]))
    print("=" * 70)
