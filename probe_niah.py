"""Standalone long-context needle-in-a-haystack diagnostic probe."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from common import append_jsonl, build_run_manifest, extract_clean_reply, fingerprint, param_hash, run_batch
from probe_utils import mean, new_probe_id, save_probe_summary

DEFAULT_CONTEXT_SIZES = (4000, 16000, 32000)
DEFAULT_DEPTHS = (10, 50, 90)
CHARACTERS_PER_TOKEN_ESTIMATE = 4


def normalize_corpus(text: str) -> str:
    """Normalize whitespace while retaining natural paragraph boundaries."""
    return "\n\n".join(" ".join(block.split()) for block in text.split("\n\n") if block.strip())


def estimated_tokens(text: str) -> int:
    """Return a documented conservative token estimate when server tokenization is unavailable."""
    return max(1, len(text) // CHARACTERS_PER_TOKEN_ESTIMATE)


def _bounded_slice(corpus: str, target_characters: int, seed: str) -> str:
    if len(corpus) < target_characters:
        available = estimated_tokens(corpus)
        requested = target_characters // CHARACTERS_PER_TOKEN_ESTIMATE
        raise ValueError(
            f"Corpus is too short for the requested {requested:,}-token context (estimated corpus: {available:,} tokens)."
        )
    max_start = len(corpus) - target_characters
    start = int(fingerprint({"seed": seed}, length=12), 16) % (max_start + 1)
    segment = corpus[start:start + target_characters]
    # Avoid leading/trailing partial words where possible.
    if " " in segment[:100]:
        segment = segment.split(" ", 1)[1]
    if " " in segment[-100:]:
        segment = segment.rsplit(" ", 1)[0]
    return segment


def build_niah_case(corpus: str, *, context_tokens: int, depth_percent: int, case_id: str) -> dict:
    """Create a deterministic exact-retrieval prompt and disclose estimated sizing."""
    target_characters = context_tokens * CHARACTERS_PER_TOKEN_ESTIMATE
    haystack = _bounded_slice(corpus, target_characters, case_id)
    answer = f"CYPRESS-{fingerprint({"case": case_id}, length=8).upper()}"
    needle = f"\n\nArchive verification note: the unique access label for this record is {answer}.\n\n"
    insertion = int(len(haystack) * (depth_percent / 100))
    insertion = max(0, min(len(haystack), insertion))
    context = haystack[:insertion] + needle + haystack[insertion:]
    question = (
        "Read the reference text below. What is the unique access label for this record? "
        "Reply with only the label and no explanation.\n\n"
        "--- BEGIN REFERENCE TEXT ---\n"
        f"{context}\n"
        "--- END REFERENCE TEXT ---"
    )
    return {
        "id": case_id,
        "prompt": question,
        "answer": answer,
        "context_tokens_target": context_tokens,
        "depth_percent": depth_percent,
        "context_characters": len(context),
        "estimated_input_tokens": estimated_tokens(question),
    }


def grade_niah_response(reply: str, expected: str) -> dict:
    normalized = " ".join(reply.upper().split())
    exact = normalized == expected
    contains = expected in normalized
    flags: list[str] = []
    if not contains:
        flags.append("needle_not_retrieved")
    elif not exact:
        flags.append("retrieved_with_extra_text")
    return {
        "weighted_score": 1.0 if exact else 0.8 if contains else 0.0,
        "dimensions": {"exact_retrieval": 1.0 if exact else 0.0, "contains_needle": 1.0 if contains else 0.0},
        "flags": flags,
    }


def run_niah_probe(
    *,
    model: str,
    preset_rows: list[dict],
    corpus_path: str | Path,
    context_sizes: tuple[int, ...] = DEFAULT_CONTEXT_SIZES,
    depths: tuple[int, ...] = DEFAULT_DEPTHS,
    timeout: int = 180,
    samples: int = 1,
    enable_thinking: bool = False,
) -> dict:
    """Run compact NIAH exact-retrieval diagnostics separate from the sampler pipeline."""
    source_path = Path(corpus_path)
    if not source_path.exists():
        raise FileNotFoundError(f"NIAH corpus not found: {source_path}")
    corpus = normalize_corpus(source_path.read_text(encoding="utf-8"))
    if not corpus:
        raise ValueError("NIAH corpus is empty after whitespace normalization.")
    if any(size < 256 for size in context_sizes) or any(depth < 0 or depth > 100 for depth in depths):
        raise ValueError("Context sizes must be at least 256 tokens and depths must be 0–100.")

    case_rows = [
        build_niah_case(corpus, context_tokens=size, depth_percent=depth, case_id=f"niah_{size}_{depth}")
        for size in context_sizes for depth in depths
    ]
    probe_id = new_probe_id("niah", model, preset_rows, {
        "corpus": str(source_path), "context_sizes": context_sizes, "depths": depths, "samples": samples,
    })
    jobs: list[dict] = []
    for preset in preset_rows:
        for case in case_rows:
            for sample_idx in range(samples):
                jobs.append({
                    "params": preset["params"],
                    "prompt": {"id": case["id"], "prompt": case["prompt"], "system": "Follow the requested output format exactly."},
                    "preset_label": preset["label"],
                    "preset_source": preset["source"],
                    "sample_idx": sample_idx,
                    "case": case,
                })
    print("=" * 70)
    print("  OPTIONAL LONG-CONTEXT NIAH DIAGNOSTIC")
    print(f"  Model: {model} | Corpus estimate: {estimated_tokens(corpus):,} tokens | Cases: {len(case_rows)} | Presets: {len(preset_rows)} | Calls: {len(jobs)}")
    print("  Token sizing uses a documented character estimate; returned prompt-token usage is recorded when supplied by the server.")
    print("=" * 70)
    rows = run_batch(model, jobs, timeout=timeout, enable_thinking=enable_thinking)

    scores_by_preset_size_depth: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    failure_count = 0
    for row in rows:
        result = row["result"]
        case = row["case"]
        reply = extract_clean_reply(result.get("reply", "")) if "reply" in result else ""
        if "error" in result:
            failure_count += 1
            grade = {"weighted_score": 0.0, "dimensions": {}, "flags": [result["error"]]}
        else:
            grade = grade_niah_response(reply, case["answer"])
            scores_by_preset_size_depth[row["preset_label"]][f"{case['context_tokens_target']}@{case['depth_percent']}"] .append(grade["weighted_score"])
        append_jsonl("probe_niah", "long_context", model, {
            "probe_id": probe_id,
            "run_id": probe_id,
            "benchmark_id": probe_id,
            "prompt_id": case["id"],
            "track": "exact_retrieval",
            "context_tokens_target": case["context_tokens_target"],
            "depth_percent": case["depth_percent"],
            "estimated_input_tokens": case["estimated_input_tokens"],
            "server_prompt_tokens": result.get("prompt_tokens"),
            "params": row["params"],
            "param_hash": row.get("param_hash") or param_hash(row["params"]),
            "preset_label": row["preset_label"],
            "preset_source": row["preset_source"],
            "sample_idx": row["sample_idx"],
            "grade": grade,
            "elapsed": round(row["elapsed"], 2),
            "completion_tokens": result.get("tokens", 0),
            "response_model": result.get("response_model", model),
            "finish_reason": result.get("finish_reason"),
            "reply_preview": reply[:300].replace("\n", " "),
        })
    by_preset = {
        label: {key: mean(values) for key, values in results.items()}
        for label, results in scores_by_preset_size_depth.items()
    }
    manifest = build_run_manifest(
        stage="probe_niah", profile="long_context", model=model, prompts=case_rows,
        samples=samples, enable_thinking=enable_thinking, parameter_combinations=len(preset_rows),
    )
    summary = {
        "kind": "niah_exact_retrieval_probe",
        "run_manifest": manifest,
        "corpus": {
            "path": str(source_path),
            "characters": len(corpus),
            "estimated_tokens": estimated_tokens(corpus),
            "characters_per_token_estimate": CHARACTERS_PER_TOKEN_ESTIMATE,
        },
        "matrix": {"context_sizes": list(context_sizes), "depths": list(depths), "samples": samples},
        "presets": preset_rows,
        "summary": {
            "attempted_calls": len(jobs),
            "successful_calls": len(jobs) - failure_count,
            "failed_calls": failure_count,
            "scores_by_preset_case": by_preset,
        },
        "method_note": "Version 1 is deterministic exact retrieval. It is a smoke test, not a complete long-context capability claim.",
    }
    save_probe_summary("niah", model, probe_id, summary)
    for label, scores in by_preset.items():
        print(f"  {label}: " + " | ".join(f"{case}={score:.2f}" for case, score in sorted(scores.items())))
    return summary
