"""Shared API, persistence, reproducibility, and CLI utilities for Senerenai-HyperProbe."""
from __future__ import annotations

import hashlib
import json
import platform
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import (
    API_BASE,
    API_KEY,
    BACKEND_LABEL,
    SAMPLER_CAPABILITIES,
    DEFAULT_TIMEOUT,
    MAX_CONCURRENT_REQUESTS,
    MAX_TOKENS,
    RETRY_DELAY,
    RETRY_ON_ERROR,
)

PROJECT_SCHEMA_VERSION = "1.3"
ROOT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = ROOT_DIR / "results"
STAGES_DIR = RESULTS_DIR / "stages"
RESULTS_DIR.mkdir(exist_ok=True)
STAGES_DIR.mkdir(exist_ok=True)


def utc_now() -> str:
    """Return a stable UTC timestamp suitable for result metadata."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def canonical_json(value: Any) -> str:
    """Encode JSON consistently for fingerprints and deterministic record IDs."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def fingerprint(value: Any, length: int = 12) -> str:
    """Return a compact SHA-256 fingerprint for public benchmark metadata."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:length]


def prompt_bank_fingerprint(prompts: list[dict]) -> str:
    """Fingerprint only benchmark-relevant public prompt content and metadata."""
    normalized = [
        {
            "id": prompt.get("id"),
            "category": prompt.get("category"),
            "difficulty": prompt.get("difficulty"),
            "language": prompt.get("language"),
            "system": prompt.get("system"),
            "prompt": prompt.get("prompt"),
        }
        for prompt in prompts
    ]
    return fingerprint(normalized)


def build_run_manifest(
    *,
    stage: str,
    profile: str,
    model: str,
    prompts: list[dict],
    samples: int,
    enable_thinking: bool,
    parameter_combinations: int,
) -> dict:
    """Build non-secret metadata needed to compare benchmark runs responsibly."""
    return {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "stage": stage,
        "profile": profile,
        "model": model,
        "created_at": utc_now(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "prompt_count": len(prompts),
        "prompt_bank_fingerprint": prompt_bank_fingerprint(prompts),
        "samples_per_combination": samples,
        "parameter_combinations": parameter_combinations,
        "max_tokens": MAX_TOKENS,
        "thinking_enabled": enable_thinking,
        "backend_label": BACKEND_LABEL or "unspecified",
        "endpoint_fingerprint": fingerprint({"api_base": API_BASE}),
        "declared_sampler_capabilities": list(SAMPLER_CAPABILITIES),
        "sampler_order": "provider-defined; not inferred by HyperProbe",
    }


def call_model(
    model: str,
    params: dict,
    prompt: dict,
    timeout: int = DEFAULT_TIMEOUT,
    allow_retry: bool = True,
    enable_thinking: bool = False,
) -> dict:
    """Call an OpenAI-compatible `/chat/completions` endpoint."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt.get("system", "You are a helpful assistant.")},
            {"role": "user", "content": prompt["prompt"]},
        ],
        "max_tokens": MAX_TOKENS,
    }
    supported_parameters = {
        "temperature", "min_p", "top_p", "top_k", "repetition_penalty",
        "presence_penalty", "frequency_penalty",
    }
    requested_parameters = {key for key in params if key in supported_parameters}
    unsupported = sorted(requested_parameters - set(SAMPLER_CAPABILITIES))
    if unsupported:
        return {
            "error": "Configured sampler capabilities exclude requested parameter(s): " + ", ".join(unsupported),
            "unsupported_parameters": unsupported,
        }
    payload.update({key: params[key] for key in params if key in requested_parameters})
    if enable_thinking:
        payload["chat_template_kwargs"] = {"enable_thinking": True}

    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = API_KEY
    request = Request(
        f"{API_BASE.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        message = data["choices"][0].get("message", {})
        choice = data["choices"][0]
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        completion_tokens = usage.get("completion_tokens")
        prompt_tokens = usage.get("prompt_tokens")
        completion_reported = isinstance(completion_tokens, (int, float))
        prompt_reported = isinstance(prompt_tokens, (int, float))
        return {
            "reply": message.get("content", "") or "",
            "tokens": int(completion_tokens) if completion_reported else 0,
            "completion_tokens_reported": completion_reported,
            "prompt_tokens": int(prompt_tokens) if prompt_reported else None,
            "prompt_tokens_reported": prompt_reported,
            "response_model": data.get("model", model),
            "finish_reason": choice.get("finish_reason"),
        }
    except HTTPError as exc:
        error = f"HTTP {exc.code}: {exc.read().decode(errors='replace')[:300]}"
    except URLError as exc:
        error = f"URL error: {exc.reason}"
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        error = f"Invalid API response: {exc}"
    except Exception as exc:
        error = str(exc)

    if RETRY_ON_ERROR and allow_retry:
        time.sleep(RETRY_DELAY)
        return call_model(model, params, prompt, timeout, False, enable_thinking)
    return {"error": error}


def run_batch(
    model: str,
    jobs: list[dict],
    timeout: int = DEFAULT_TIMEOUT,
    max_workers: int | None = None,
    progress: bool = True,
    enable_thinking: bool = False,
) -> list[dict]:
    """Execute jobs while preserving input order and recording elapsed time."""
    workers = max_workers or MAX_CONCURRENT_REQUESTS
    output: list[dict | None] = [None] * len(jobs)

    def run_one(index: int) -> tuple[int, dict, float]:
        started = time.monotonic()
        result = call_model(
            model,
            jobs[index]["params"],
            jobs[index]["prompt"],
            timeout=timeout,
            enable_thinking=enable_thinking,
        )
        return index, result, time.monotonic() - started

    if workers <= 1:
        completed = (run_one(index) for index in range(len(jobs)))
        pool = None
    else:
        pool = ThreadPoolExecutor(max_workers=workers)
        futures = [pool.submit(run_one, index) for index in range(len(jobs))]
        completed = (future.result() for future in as_completed(futures))

    for completed_count, (index, result, elapsed) in enumerate(completed, 1):
        output[index] = {**jobs[index], "result": result, "elapsed": elapsed}
        if progress:
            status = "OK" if "reply" in result else "ERROR"
            detail = ""
            if status == "ERROR":
                detail = f": {str(result.get('error', 'unknown error')).replace(chr(10), ' ')[:240]}"
            print(
                f"[{completed_count}/{len(jobs)}] "
                f"{jobs[index]['prompt'].get('id', '?')} | "
                f"{param_hash(jobs[index]['params'])} | {elapsed:.1f}s | {status}{detail}"
            )
    if pool:
        pool.shutdown()
    return [item for item in output if item is not None]


def warmup(model: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Make one low-cost request to verify a model endpoint is responsive."""
    return call_model(model, {}, {"prompt": "Reply with OK."}, timeout, allow_retry=False)


def param_hash(params: dict) -> str:
    """Return a stable compact identifier for one sampling parameter combination."""
    return fingerprint(params, length=10)


def safe_model_name(model: str) -> str:
    """Create a filesystem-safe model identifier while preserving readability."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", model).strip("_") or "unknown_model"


def stage_file(stage_name: str, profile: str, model: str, language: str | None = None) -> Path:
    """Return the latest-pointer path used by the zero-prompt launcher."""
    language_suffix = f"_{safe_model_name(language)}" if language else ""
    return STAGES_DIR / f"{stage_name}_{profile}_{safe_model_name(model)}{language_suffix}.json"


def archived_stage_file(
    stage_name: str,
    profile: str,
    model: str,
    benchmark_id: str,
    language: str | None = None,
) -> Path:
    """Return an immutable archive path for one benchmark chain."""
    language_suffix = f"_{safe_model_name(language)}" if language else ""
    return STAGES_DIR / f"{stage_name}_{profile}_{safe_model_name(model)}_{safe_model_name(benchmark_id)}{language_suffix}.json"


def save_stage(
    stage_name: str,
    profile: str,
    model: str,
    data: dict,
    language: str | None = None,
    benchmark_id: str | None = None,
) -> Path:
    """Write an immutable stage archive plus a latest pointer for zero-prompt continuation."""
    payload = dict(data)
    supplied_meta = dict(payload.pop("_meta", {}))
    benchmark_id = benchmark_id or payload.get("benchmark_id") or supplied_meta.get("benchmark_id") or fingerprint({"stage": stage_name, "profile": profile, "model": model, "created_at": utc_now()})
    search_design = payload.get("search_design") or supplied_meta.get("search_design")
    payload["benchmark_id"] = benchmark_id
    payload["_meta"] = {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "stage": stage_name,
        "profile": profile,
        "model": model,
        "language": language,
        "benchmark_id": benchmark_id,
        "saved_at": utc_now(),
        **supplied_meta,
    }
    if search_design:
        payload["_meta"]["search_design"] = search_design
    archive = archived_stage_file(stage_name, profile, model, benchmark_id, language)
    latest = stage_file(stage_name, profile, model, language)
    encoded = json.dumps(payload, indent=2, ensure_ascii=False)
    archive.write_text(encoded, encoding="utf-8")
    latest.write_text(encoded, encoding="utf-8")
    print(f"Saved stage archive to {archive}")
    print(f"Updated latest {stage_name} pointer: {latest}")
    return archive


def validate_stage_handoff(
    data: dict,
    *,
    expected_stage: str | None = None,
    expected_profile: str | None = None,
    expected_model: str | None = None,
    expected_search_design: str | None = None,
    required_keys: tuple[str, ...] = (),
) -> None:
    """Reject a stale, mismatched, or incomplete downstream stage handoff."""
    if not isinstance(data, dict):
        raise ValueError("Stage handoff must be a JSON object.")
    meta = data.get("_meta")
    if not isinstance(meta, dict):
        raise ValueError("Stage handoff is missing _meta provenance data.")
    checks = {
        "stage": expected_stage,
        "profile": expected_profile,
        "model": expected_model,
        "search_design": expected_search_design,
    }
    for field, expected in checks.items():
        if expected is not None and meta.get(field) != expected:
            raise ValueError(
                f"Stage handoff {field} mismatch: expected {expected!r}, found {meta.get(field)!r}."
            )
    missing = [key for key in required_keys if key not in data]
    if missing:
        raise ValueError(f"Stage handoff is missing required fields: {', '.join(missing)}.")


def load_stage(
    path_or_stage_name: str,
    profile: str | None = None,
    model: str | None = None,
    *,
    language: str | None = None,
    expected_stage: str | None = None,
    expected_search_design: str | None = None,
    required_keys: tuple[str, ...] = (),
) -> dict:
    """Load and validate a stage handoff from a path or inferred stage name."""
    path = Path(path_or_stage_name)
    if not path.exists() and profile and model:
        path = stage_file(path_or_stage_name, profile, model, language)
    if not path.exists():
        raise FileNotFoundError(f"Stage file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Stage file is not valid JSON: {path}") from exc
    validate_stage_handoff(
        data,
        expected_stage=expected_stage,
        expected_profile=profile,
        expected_model=model,
        expected_search_design=expected_search_design,
        required_keys=required_keys,
    )
    if language is not None and data.get("_meta", {}).get("language") != language:
        raise ValueError(
            f"Stage handoff language mismatch: expected {language!r}, "
            f"found {data.get('_meta', {}).get('language')!r}."
        )
    return data


def append_jsonl(phase_name: str, profile: str, model: str, record: dict) -> None:
    """Append a schema-versioned model-scoped benchmark record."""
    path = RESULTS_DIR / f"{phase_name}_{profile}_{safe_model_name(model)}.jsonl"
    payload = {
        **record,
        "record_schema_version": PROJECT_SCHEMA_VERSION,
        "recorded_at": utc_now(),
        "phase": phase_name,
        "profile": profile,
        "model": model,
        "backend_label": BACKEND_LABEL or "unspecified",
        "endpoint_fingerprint": fingerprint({"api_base": API_BASE}),
        "declared_sampler_capabilities": list(SAMPLER_CAPABILITIES),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def prompt_select(
    question: str,
    options: list,
    descriptions: list | None = None,
    default: int = 1,
) -> int:
    """Show an indexed interactive selector and return a zero-based choice."""
    print(f"\n{question}")
    for index, option in enumerate(options, 1):
        description = f" — {descriptions[index - 1]}" if descriptions else ""
        marker = " (default)" if index == default else ""
        print(f"  {index}. {option}{description}{marker}")
    while True:
        raw = input(f"Choice [1-{len(options)}]: ").strip()
        if not raw:
            return default - 1
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print("Please enter a valid number.")


def prompt_int(question: str, default: int, hint: str = "") -> int:
    """Ask for an integer and use a documented default on blank or invalid input."""
    raw = input(f"{question}{f' ({hint})' if hint else ''} [Enter={default}]: ").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        print(f"Invalid integer; using default {default}.")
        return default


def prompt_yes_no(question: str, default: bool = True) -> bool:
    """Prompt for a yes/no answer using English terminal labels."""
    suffix = "Y/n" if default else "y/N"
    answer = input(f"{question} [{suffix}]: ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def extract_clean_reply(text: str) -> str:
    """Remove thinking blocks before a public grader receives model output."""
    return re.sub(r"<think>.*?(?:</think>|$)", "", text or "", flags=re.I | re.S).strip()


def format_duration(seconds: float) -> str:
    """Format elapsed seconds for human-readable terminal output."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, remainder = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m {remainder:02d}s" if hours else f"{minutes}m {remainder:02d}s"


def pick_model(api_base: str | None = None, api_key: str | None = None) -> str:
    """Interactively select a model returned by an OpenAI-compatible endpoint."""
    headers = {"Authorization": api_key or API_KEY} if (api_key or API_KEY) else {}
    request = Request(f"{(api_base or API_BASE).rstrip('/')}/models", headers=headers)
    with urlopen(request, timeout=10) as response:
        models = [item["id"] for item in json.loads(response.read().decode("utf-8"))["data"]]
    if not models:
        raise RuntimeError("The endpoint returned no models.")
    for index, model in enumerate(models, 1):
        print(f"  {index}. {model}")
    while True:
        raw = input("Select a model: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(models):
            return models[int(raw) - 1]
        print("Please enter a valid model number.")
