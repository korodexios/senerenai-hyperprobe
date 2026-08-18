"""Stage 2: targeted interaction refinement.

Stage 2 consumes Stage 1 main-effect evidence.  It tests the strongest two-way
interaction explicitly, carries forward the strongest coarse candidates, and
checks the assembled per-parameter winner.  A legacy bounded-grid fallback is
retained for manually supplied ranges and older Stage 1 handoffs.
"""
from __future__ import annotations

import argparse
import itertools
import sys
from collections import defaultdict
from typing import Any

from config import (
    ALL_PROFILES,
    BIG_FOUR,
    PROFILE_EMOJI,
    STAGE1_BASELINE,
    STAGE2_DEFAULT_MAX_COMBOS,
    STAGE2_DEFAULT_SAMPLES,
    STAGE_GRID_STEPS,
    SEARCH_DESIGN_VERSION,
    round_param_value,
)
from common import (
    append_jsonl,
    build_run_manifest,
    extract_clean_reply,
    fingerprint,
    format_duration,
    load_stage,
    param_hash,
    pick_model,
    prompt_int,
    prompt_select,
    run_batch,
    save_stage,
)
from grader.repetition import cross_combo_invariance

from tests.coding import CODING_PROMPTS
from tests.agent_tools import AGENT_PROMPTS
from tests.creative import CREATIVE_PROMPTS
from tests.roleplay import ROLEPLAY_PROMPTS
from tests.custom_lang import CUSTOM_LANG_PROMPTS

from grader.coder import grade_coder
from grader.agent import grade_agent
from grader.creative import grade_creative
from grader.roleplay import grade_roleplay
from grader.custom_lang import grade_custom_lang

PROMPTS = {
    "coding": CODING_PROMPTS[:5],
    "agent_tools": AGENT_PROMPTS[:3],
    "creative": CREATIVE_PROMPTS[:3],
    "roleplay": ROLEPLAY_PROMPTS[:3],
    "custom_lang": CUSTOM_LANG_PROMPTS,
}
GRID_PARAMS = list(BIG_FOUR)
_PAIR_TIE_BREAK = {"temperature": 0, "top_p": 1, "min_p": 2, "repetition_penalty": 3}


def get_grader(profile: str, prompt: dict):
    if profile == "coding":
        return grade_coder
    if profile == "agent_tools":
        return grade_agent
    if profile == "creative":
        return grade_creative
    if profile == "roleplay":
        return grade_roleplay
    return grade_custom_lang


def parse_range_args(range_args: list[str] | None) -> dict:
    out = {}
    for item in range_args or []:
        name, values = item.split("=", 1)
        low, high = values.split(":", 1)
        out[name] = [float(low), float(high)]
    return out


def build_grid(ranges: dict, base_params: dict, steps: int = STAGE_GRID_STEPS) -> list[dict]:
    """Legacy/manual grid fallback, used when Stage 1 evidence is unavailable."""
    axes = {}
    for parameter in GRID_PARAMS:
        if parameter in ranges:
            low, high = ranges[parameter]
            if low == high:
                axes[parameter] = [round_param_value(parameter, low)]
            else:
                axes[parameter] = list(
                    dict.fromkeys(round_param_value(parameter, low + index * (high - low) / (steps - 1)) for index in range(steps))
                )
        else:
            axes[parameter] = [round_param_value(parameter, base_params.get(parameter, STAGE1_BASELINE[parameter]))]
    return [
        {"temperature": temperature, "min_p": min_p, "top_p": top_p, "repetition_penalty": repetition_penalty}
        for temperature, min_p, top_p, repetition_penalty in itertools.product(
            axes["temperature"], axes["min_p"], axes["top_p"], axes["repetition_penalty"]
        )
    ]


def _add_unique(candidates: list[dict[str, Any]], params: dict, role: str) -> None:
    key = param_hash(params)
    if not any(param_hash(item["params"]) == key for item in candidates):
        candidates.append({"params": dict(params), "role": role})


def _selected_values(main_effects: dict, parameter: str, base: dict) -> list[float]:
    raw = main_effects.get(parameter, {}).get("selected_values", [])
    values = [item["value"] if isinstance(item, dict) else item for item in raw]
    if not values:
        values = [base[parameter]]
    return list(dict.fromkeys(values))[:2]


def build_interaction_candidates(stage1_data: dict | None, ranges: dict, max_combos: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return a small, labeled Stage 2 design from interpretable Stage 1 evidence."""
    stage1_data = stage1_data or {}
    main_effects = stage1_data.get("main_effects")
    top_combos = stage1_data.get("top_combos", [])
    if not main_effects:
        base = dict(ranges.pop("_base", {})) or dict(STAGE1_BASELINE)
        grid = build_grid(ranges, base)
        return ([{"params": params, "role": "legacy_grid"} for params in grid[:max_combos]], {"mode": "legacy_bounded_grid", "base_params": base})

    base = dict(stage1_data.get("design", {}).get("baseline", STAGE1_BASELINE))
    strengths = sorted(
        GRID_PARAMS,
        key=lambda parameter: (-float(main_effects.get(parameter, {}).get("effect_span", 0.0)), _PAIR_TIE_BREAK[parameter]),
    )
    primary = strengths[:2]
    candidates: list[dict[str, Any]] = []
    _add_unique(candidates, base, "baseline")

    first_values = _selected_values(main_effects, primary[0], base)
    second_values = _selected_values(main_effects, primary[1], base)
    for first, second in itertools.product(first_values, second_values):
        params = dict(base)
        params[primary[0]] = first
        params[primary[1]] = second
        _add_unique(candidates, params, f"primary_interaction:{primary[0]}x{primary[1]}")

    for index, combo in enumerate(top_combos[:2], 1):
        if combo.get("params"):
            _add_unique(candidates, combo["params"], f"stage1_top_combo:{index}")

    assembled = dict(base)
    for parameter in GRID_PARAMS:
        assembled[parameter] = _selected_values(main_effects, parameter, base)[0]
    _add_unique(candidates, assembled, "assembled_main_effect_winners")

    remaining = strengths[2:]
    if len(remaining) >= 2:
        params = dict(assembled)
        for parameter in remaining[:2]:
            values = _selected_values(main_effects, parameter, base)
            params[parameter] = values[1] if len(values) > 1 else values[0]
        _add_unique(candidates, params, f"secondary_interaction:{remaining[0]}x{remaining[1]}")

    return candidates[:max_combos], {
        "mode": "targeted_interaction_refinement",
        "base_params": base,
        "primary_interaction": primary,
        "parameter_priority": strengths,
        "effect_spans": {parameter: float(main_effects.get(parameter, {}).get("effect_span", 0.0)) for parameter in GRID_PARAMS},
        "selected_values": {parameter: _selected_values(main_effects, parameter, base) for parameter in GRID_PARAMS},
        "candidate_count_before_cap": len(candidates),
    }


def run_stage2(
    profile: str,
    model: str,
    ranges: dict,
    n_samples: int = STAGE2_DEFAULT_SAMPLES,
    timeout: int = 180,
    max_combos: int = STAGE2_DEFAULT_MAX_COMBOS,
    enable_thinking: bool = False,
    language: str | None = None,
    stage1_evidence: dict | None = None,
) -> dict:
    prompts = PROMPTS[profile]
    if language and profile == "custom_lang":
        prompts = [prompt for prompt in prompts if prompt.get("language") == language]
        if not prompts:
            raise ValueError(f"No custom-language prompts found for language: {language}")

    candidates, strategy = build_interaction_candidates(stage1_evidence, dict(ranges), max_combos)
    combos = [item["params"] for item in candidates]
    if not combos:
        raise ValueError("Stage 2 has no valid parameter candidates.")

    total = len(prompts) * len(combos) * n_samples
    run_manifest = build_run_manifest(
        stage="stage2",
        profile=profile,
        model=model,
        prompts=prompts,
        samples=n_samples,
        enable_thinking=enable_thinking,
        parameter_combinations=len(combos),
    )
    run_id = fingerprint(run_manifest)
    benchmark_id = (stage1_evidence or {}).get("benchmark_id") or run_id
    print(
        f"\n{'=' * 62}\n  🔬 STAGE 2 — INTERACTION REFINEMENT — {profile.upper()}\n"
        f"  Strategy: {strategy['mode']} | Candidates: {len(combos)}\n"
        f"  Model: {model} | Prompts: {len(prompts)} | Combinations: {len(combos)} "
        f"| Samples: {n_samples} | Total calls: {total}\n{'=' * 62}"
    )
    if strategy["mode"] == "targeted_interaction_refinement":
        spans = strategy["effect_spans"]
        priority = strategy["parameter_priority"]
        print("  Evidence: " + ", ".join(f"{parameter} Δ={spans[parameter]:.3f}" for parameter in priority))
        print(f"  Primary pair: {strategy['primary_interaction'][0]} × {strategy['primary_interaction'][1]} (largest measured main-effect spans)")
    for index, candidate in enumerate(candidates, 1):
        print(f"    {index}. {candidate['role']} | {candidate['params']}")

    jobs = [
        {"prompt": prompt, "params": candidate["params"], "sample_idx": sample_idx, "candidate_role": candidate["role"]}
        for prompt in prompts
        for candidate in candidates
        for sample_idx in range(n_samples)
    ]
    batch = run_batch(model, jobs, timeout=timeout, enable_thinking=enable_thinking)

    scores_by_hash: dict[str, list[float]] = defaultdict(list)
    params_by_hash: dict[str, dict] = {}
    elapsed_by_hash: dict[str, list[float]] = defaultdict(list)
    failed_by_hash: dict[str, int] = defaultdict(int)
    role_by_hash: dict[str, str] = {}
    replies_per_prompt_hash: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    for row in batch:
        prompt, params, result = row["prompt"], row["params"], row["result"]
        ph = param_hash(params)
        params_by_hash[ph] = params
        role_by_hash[ph] = row["candidate_role"]
        if "error" in result:
            score, reply, dimensions, flags = 0.0, "", {}, [result["error"]]
            failed_by_hash[ph] += 1
        else:
            grader = get_grader(profile, prompt)
            reply = extract_clean_reply(result["reply"])
            previous = replies_per_prompt_hash[prompt["id"]][ph]
            grade = grader(reply, prompt, prev_replies=previous) if profile in ("creative", "roleplay", "custom_lang") else grader(reply, prompt)
            score, dimensions, flags = grade.weighted_score, grade.dimensions, grade.flags
            scores_by_hash[ph].append(score)
            elapsed_by_hash[ph].append(row.get("elapsed", 0.0))
            replies_per_prompt_hash[prompt["id"]][ph].append(reply)

        append_jsonl(
            "stage2",
            profile,
            model,
            {
                "run_id": run_id,
                "benchmark_id": benchmark_id,
                "search_design": SEARCH_DESIGN_VERSION,
                "prompt_id": prompt["id"],
                "profile": profile,
                "language": prompt.get("language"),
                "param_hash": ph,
                "params": params,
                "candidate_role": row["candidate_role"],
                "sample_idx": row["sample_idx"],
                "grade": {"weighted_score": round(score, 4), "dimensions": dimensions, "flags": flags},
                "elapsed": round(row["elapsed"], 2),
                "completion_tokens": result.get("tokens", 0),
                "response_model": result.get("response_model", model),
                "finish_reason": result.get("finish_reason"),
                "reply_preview": reply[:300].replace("\n", " "),
            },
        )

    expected_observations = len(prompts) * n_samples
    incomplete_candidates = {}
    combo_scores = []
    for ph, scores in scores_by_hash.items():
        if len(scores) < expected_observations:
            incomplete_candidates[ph] = {"successful": len(scores), "expected": expected_observations}
            continue
        mean = sum(scores) / len(scores)
        std = (sum((score - mean) ** 2 for score in scores) / len(scores)) ** 0.5
        worst = min(scores)
        combo_scores.append(
            {
                "params": params_by_hash[ph],
                "param_hash": ph,
                "role": role_by_hash[ph],
                "mean": round(mean, 4),
                "std": round(std, 4),
                "worst": round(worst, 4),
                "combined": round(mean - 0.5 * std + 0.1 * worst, 4),
                "n": len(scores),
                "avg_time": round(sum(elapsed_by_hash[ph]) / len(elapsed_by_hash[ph]), 2),
            }
        )
    if not combo_scores:
        raise RuntimeError("Stage 2 received no successful model responses; inspect API errors before running Stage 3.")
    combo_scores.sort(key=lambda item: (-item["combined"], item["param_hash"]))

    top = combo_scores[: max(3, len(combo_scores) // 3)]
    narrowed = {
        parameter: [min(item["params"][parameter] for item in top), max(item["params"][parameter] for item in top)]
        for parameter in GRID_PARAMS
    }

    warnings = []
    for prompt_id, hashes in replies_per_prompt_hash.items():
        diagnostic = cross_combo_invariance(hashes)
        if diagnostic["invariant"]:
            warnings.append(f"{prompt_id}: {diagnostic['note']}")
    if incomplete_candidates:
        warnings.append(f"{len(incomplete_candidates)} candidate(s) had incomplete confirmation coverage and were excluded from Stage 2 ranking.")
    if any(failed_by_hash.values()):
        warnings.append(f"{sum(failed_by_hash.values())} failed call(s) were excluded from Stage 2 ranking evidence.")

    print("\n  🏆 Top 5 combinations (Stage 2):")
    for index, item in enumerate(combo_scores[:5], 1):
        print(f"    #{index} combined={item['combined']:.3f} mean={item['mean']:.3f}±{item['std']:.3f} | {item['role']} | {item['params']}")
    print("\n  📈 Narrowed ranges passed to Stage 3:")
    for parameter, (low, high) in narrowed.items():
        print(f"    {parameter:<20} [{low}, {high}]")
    if warnings:
        print("\n  ⚠️  WARNINGS:")
        for warning in warnings:
            print(f"    - {warning}")

    error_count = sum(failed_by_hash.values())
    data = {
        "benchmark_id": benchmark_id,
        "run_manifest": run_manifest,
        "summary": {
            "attempted_calls": len(jobs),
            "successful_calls": len(jobs) - error_count,
            "failed_calls": error_count,
            "failure_rate": round(error_count / max(len(jobs), 1), 4),
        },
        "search_design": SEARCH_DESIGN_VERSION,
        "search_strategy": strategy,
        "expected_observations_per_candidate": expected_observations,
        "excluded_incomplete_candidates": incomplete_candidates,
        "input_ranges": dict(ranges),
        "top_combos": combo_scores[:15],
        "narrowed_ranges": narrowed,
        "warnings": warnings,
    }
    save_stage("stage2", profile, model, data, language=language, benchmark_id=benchmark_id)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Senerenai-HyperProbe Stage 2 — targeted interaction refinement.")
    parser.add_argument("--profile", "-p", default=None, choices=ALL_PROFILES)
    parser.add_argument("--language", help="Restrict custom_lang to one language code, for example en, es, zh, or sk.")
    parser.add_argument("--all", action="store_true", help="Run sequentially for all profiles (each profile needs Stage 1 data).")
    parser.add_argument("--model", "-m", default=None, help="Model ID. If omitted, an interactive model picker is used.")
    parser.add_argument("--stage1", default=None, help="Path to Stage 1 JSON (default: locate it by profile/model).")
    parser.add_argument("--range", action="append", help="Manual range override, for example temperature=0.2:0.6. Uses the legacy grid fallback.")
    parser.add_argument("--samples", type=int, default=None)
    parser.add_argument("--max-combos", type=int, default=None)
    parser.add_argument("--think", action="store_true", help="Enable thinking mode")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    if args.all:
        profiles = ALL_PROFILES
    elif args.profile:
        profiles = [args.profile]
    else:
        options = [f"{PROFILE_EMOJI.get(profile, '[profile]')} {profile}" for profile in ALL_PROFILES] + ["All profiles sequentially"]
        index = prompt_select("Which profile should be refined (Stage 2)?", options, default=1)
        profiles = ALL_PROFILES if index == len(ALL_PROFILES) else [ALL_PROFILES[index]]

    model = args.model or pick_model()
    samples = args.samples if args.samples is not None else prompt_int("How many samples per combination?", default=STAGE2_DEFAULT_SAMPLES, hint="1 is the efficient default; use 2 for noisier models")
    max_combos = args.max_combos if args.max_combos is not None else prompt_int("Maximum interaction candidates?", default=STAGE2_DEFAULT_MAX_COMBOS, hint="5 is the efficient interaction default")
    think_mode = args.think
    if not args.think and len(sys.argv) == 1:
        from common import prompt_yes_no
        think_mode = prompt_yes_no("Test the model in THINKING mode?", default=False)

    import time
    started = time.time()
    durations = {}
    for profile in profiles:
        if args.range:
            ranges = parse_range_args(args.range)
            stage1_data = None
        else:
            stage1_data = load_stage(
                args.stage1 or "stage1", profile, model, language=args.language,
                expected_stage="stage1", expected_search_design=SEARCH_DESIGN_VERSION,
                required_keys=("suggested_ranges", "top_combos"),
            )
            ranges = dict(stage1_data.get("suggested_ranges", {}))
        profile_started = time.time()
        run_stage2(profile, model, ranges, n_samples=samples, timeout=args.timeout, max_combos=max_combos, enable_thinking=think_mode, language=args.language, stage1_evidence=stage1_data)
        durations[profile] = time.time() - profile_started
        print(f"\n⏱️ Profile {profile.upper()} completed in: {format_duration(durations[profile])}")

    print(f"\n{'=' * 62}\n🏁 TOTAL ELAPSED TIME STAGE 2: {format_duration(time.time() - started)}")
    for profile, duration in durations.items():
        print(f"   • {profile:<15}: {format_duration(duration)}")
    print(f"{'=' * 62}")
    print("\n📊 Generating the updated HTML dashboard...")
    import visualizer
    visualizer.main()


if __name__ == "__main__":
    main()
