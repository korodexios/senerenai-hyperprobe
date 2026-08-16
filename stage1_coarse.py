"""Stage 1: interpretable coarse sampling-parameter screening.

The design starts from one baseline, changes one parameter at a time to estimate
main effects, then probes a few high-value two-parameter interactions.  It is a
fractional experiment: broad enough to guide Stage 2, but bounded enough for
practical local inference servers.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from typing import Any

from config import (
    ALL_PROFILES,
    BIG_FOUR,
    PROFILE_EMOJI,
    STAGE1_BASELINE,
    STAGE1_COMBOS,
    STAGE1_DESIGN_LABEL,
    STAGE1_INTERACTION_PAIR_LABELS,
    SEARCH_DESIGN_VERSION,
    round_param_value,
)
from common import (
    append_jsonl,
    build_run_manifest,
    extract_clean_reply,
    fingerprint,
    param_hash,
    pick_model,
    prompt_int,
    prompt_select,
    run_batch,
    save_stage,
)
from grader.repetition import cross_combo_invariance

from tests.coding import CODING_QUICK
from tests.agent_tools import AGENT_QUICK
from tests.creative import CREATIVE_QUICK
from tests.roleplay import ROLEPLAY_QUICK
from tests.custom_lang import CUSTOM_LANG_PROMPTS

from grader.coder import grade_coder
from grader.agent import grade_agent
from grader.creative import grade_creative
from grader.roleplay import grade_roleplay
from grader.custom_lang import grade_custom_lang

PROMPTS = {
    "coding": CODING_QUICK,
    "agent_tools": AGENT_QUICK,
    "creative": CREATIVE_QUICK,
    "roleplay": ROLEPLAY_QUICK,
    "custom_lang": CUSTOM_LANG_PROMPTS,
}


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


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def changed_parameters(params: dict[str, float]) -> list[str]:
    """Return parameters whose value differs from the Stage 1 baseline."""
    return [name for name in BIG_FOUR if params.get(name) != STAGE1_BASELINE[name]]


def design_role(params: dict[str, float]) -> str:
    changed = changed_parameters(params)
    if not changed:
        return "baseline"
    if len(changed) == 1:
        return f"main_effect:{changed[0]}"
    return "interaction:" + "x".join(changed)


def analyze_screening(
    combos: list[dict[str, float]],
    scores_by_hash: dict[str, list[float]],
) -> tuple[dict[str, dict], dict[str, list[float]], dict[str, dict], list[dict[str, Any]]]:
    """Build main-effect and interaction evidence from successful calls only."""
    combo_stats: list[dict[str, Any]] = []
    sensitivity: dict[str, dict] = {name: {} for name in BIG_FOUR}
    main_effects: dict[str, dict] = {}
    interactions: list[dict[str, Any]] = []

    baseline_hash = param_hash(STAGE1_BASELINE)
    baseline_scores = scores_by_hash.get(baseline_hash, [])
    baseline_mean = _mean(baseline_scores)

    for params in combos:
        ph = param_hash(params)
        scores = scores_by_hash.get(ph, [])
        if not scores:
            continue
        changed = changed_parameters(params)
        stat = {
            "params": params,
            "param_hash": ph,
            "mean": round(_mean(scores), 4),
            "n": len(scores),
            "role": design_role(params),
            "changed_parameters": changed,
        }
        combo_stats.append(stat)
        if len(changed) == 2:
            interactions.append(stat)

    for parameter in BIG_FOUR:
        levels: dict[float, list[float]] = defaultdict(list)
        if baseline_scores:
            levels[float(STAGE1_BASELINE[parameter])].extend(baseline_scores)
        for params in combos:
            changed = changed_parameters(params)
            if changed != [parameter]:
                continue
            levels[float(params[parameter])].extend(scores_by_hash.get(param_hash(params), []))

        level_stats = {
            str(value): {"mean": round(_mean(scores), 4), "n": len(scores)}
            for value, scores in sorted(levels.items())
            if scores
        }
        sensitivity[parameter] = level_stats
        ranked = sorted(
            (
                {"value": value, "mean": round(_mean(scores), 4), "n": len(scores)}
                for value, scores in levels.items()
                if scores
            ),
            key=lambda item: (-item["mean"], item["value"]),
        )
        selected = ranked[:2] if ranked else []
        effect_span = (max(item["mean"] for item in ranked) - min(item["mean"] for item in ranked)) if len(ranked) > 1 else 0.0
        main_effects[parameter] = {
            "baseline_value": STAGE1_BASELINE[parameter],
            "baseline_mean": round(baseline_mean, 4) if baseline_scores else None,
            "levels": level_stats,
            "ranked_values": ranked,
            "selected_values": selected,
            "effect_span": round(effect_span, 4),
        }

    combo_stats.sort(key=lambda item: (-item["mean"], item["param_hash"]))
    interactions.sort(key=lambda item: (-item["mean"], item["param_hash"]))
    return main_effects, sensitivity, {"baseline": {"params": STAGE1_BASELINE, "mean": round(baseline_mean, 4) if baseline_scores else None, "n": len(baseline_scores)}, "targeted": interactions}, combo_stats


def run_stage1(
    profile: str,
    model: str,
    timeout: int = 180,
    n_samples: int = 2,
    enable_thinking: bool = False,
    language: str | None = None,
) -> dict:
    prompts = PROMPTS[profile]
    if language and profile == "custom_lang":
        prompts = [prompt for prompt in prompts if prompt.get("language") == language]
        if not prompts:
            raise ValueError(f"No custom-language prompts found for language: {language}")
    combos = STAGE1_COMBOS

    jobs = [
        {"prompt": prompt, "params": params, "sample_idx": sample_idx, "design_role": design_role(params)}
        for prompt in prompts
        for params in combos
        for sample_idx in range(n_samples)
    ]
    run_manifest = build_run_manifest(
        stage="stage1",
        profile=profile,
        model=model,
        prompts=prompts,
        samples=n_samples,
        enable_thinking=enable_thinking,
        parameter_combinations=len(combos),
    )
    run_id = fingerprint(run_manifest)

    print(
        f"\n{'=' * 62}\n  🔎 STAGE 1 — INTERPRETABLE SCREENING — {profile.upper()}\n"
        f"  Design: {STAGE1_DESIGN_LABEL}\n"
        f"  Model: {model} | Prompts: {len(prompts)} | Combinations: {len(combos)} "
        f"| Samples: {n_samples} | Total calls: {len(jobs)}\n{'=' * 62}"
    )
    batch = run_batch(model, jobs, timeout=timeout, enable_thinking=enable_thinking)

    scores_by_hash: dict[str, list[float]] = defaultdict(list)
    elapsed_by_hash: dict[str, list[float]] = defaultdict(list)
    failed_by_hash: dict[str, int] = defaultdict(int)
    replies_per_prompt_hash: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    for row in batch:
        prompt, params, result = row["prompt"], row["params"], row["result"]
        ph = param_hash(params)
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
            "stage1",
            profile,
            model,
            {
                "run_id": run_id,
                "search_design": SEARCH_DESIGN_VERSION,
                "prompt_id": prompt["id"],
                "profile": profile,
                "language": prompt.get("language"),
                "param_hash": ph,
                "params": params,
                "design_role": row["design_role"],
                "sample_idx": row["sample_idx"],
                "grade": {"weighted_score": round(score, 4), "dimensions": dimensions, "flags": flags},
                "elapsed": round(row["elapsed"], 2),
                "reply_preview": reply[:300].replace("\n", " "),
            },
        )

    main_effects, sensitivity, interaction_evidence, combo_stats = analyze_screening(combos, scores_by_hash)
    if not combo_stats:
        raise RuntimeError("Stage 1 received no successful model responses; inspect the API errors before running Stage 2.")

    suggested_ranges: dict[str, list[float]] = {}
    suggested_ranges_n: dict[str, int] = {}
    for parameter, evidence in main_effects.items():
        selected = evidence["selected_values"]
        if not selected:
            continue
        values = [item["value"] for item in selected]
        suggested_ranges[parameter] = [round_param_value(parameter, min(values)), round_param_value(parameter, max(values))]
        suggested_ranges_n[parameter] = sum(item["n"] for item in selected)

    warnings = []
    for prompt_id, hashes in replies_per_prompt_hash.items():
        diagnostic = cross_combo_invariance(hashes)
        if diagnostic["invariant"]:
            warnings.append(f"{prompt_id}: {diagnostic['note']}")
    if any(failed_by_hash.values()):
        warnings.append(f"{sum(failed_by_hash.values())} failed call(s) were excluded from Stage 1 ranking evidence.")

    print("\n  📈 Main effects selected for Stage 2:")
    for parameter in BIG_FOUR:
        evidence = main_effects[parameter]
        ranked_text = ", ".join(f"{item['value']} ({item['mean']:.3f}, n={item['n']})" for item in evidence["ranked_values"])
        selected_text = ", ".join(str(item["value"]) for item in evidence["selected_values"])
        print(f"    {parameter:<20} selected [{selected_text}] | effect span={evidence['effect_span']:.3f} | all: {ranked_text}")

    print("\n  🔗 Targeted interaction evidence:")
    for item in interaction_evidence["targeted"][:6]:
        print(f"    {item['role']:<35} mean={item['mean']:.3f} n={item['n']} | {item['params']}")

    print("\n  🏆 Top 5 combinations (screening):")
    for index, item in enumerate(combo_stats[:5], 1):
        avg_time = _mean(elapsed_by_hash.get(item["param_hash"], []))
        print(f"    #{index} mean={item['mean']:.3f} | n={item['n']} | ⏱️ {avg_time:.1f}s | {item['role']} | {item['params']}")

    if warnings:
        print("\n  ⚠️  WARNINGS:")
        for warning in warnings:
            print(f"    - {warning}")

    error_count = sum(failed_by_hash.values())
    data = {
        "run_manifest": run_manifest,
        "summary": {
            "attempted_calls": len(jobs),
            "successful_calls": len(jobs) - error_count,
            "failed_calls": error_count,
            "failure_rate": round(error_count / max(len(jobs), 1), 4),
        },
        "design": {
            "version": SEARCH_DESIGN_VERSION,
            "name": STAGE1_DESIGN_LABEL,
            "baseline": STAGE1_BASELINE,
            "combination_count": len(combos),
            "main_effect_parameters": list(BIG_FOUR),
            "interaction_pairs": list(STAGE1_INTERACTION_PAIR_LABELS),
        },
        "sensitivity": sensitivity,
        "main_effects": main_effects,
        "interaction_evidence": interaction_evidence,
        "suggested_ranges": suggested_ranges,
        "suggested_ranges_n": suggested_ranges_n,
        "top_combos": combo_stats[:10],
        "warnings": warnings,
    }
    save_stage("stage1", profile, model, data, language=language)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Senerenai-HyperProbe Stage 1 — interpretable coarse sampling screening."
    )
    parser.add_argument("--profile", "-p", default=None, choices=ALL_PROFILES)
    parser.add_argument("--language", help="Restrict custom_lang to one language code, for example en, es, zh, or sk.")
    parser.add_argument("--all", action="store_true", help="Run sequentially for all profiles")
    parser.add_argument("--model", "-m", default=None, help="Model ID. If omitted, an interactive model picker is used.")
    parser.add_argument("--samples", type=int, default=None, help="Samples per combination; 2 is the reliable default.")
    parser.add_argument("--think", action="store_true", help="Enable thinking mode (Qwen-compatible endpoints).")
    parser.add_argument("--timeout", "-t", type=int, default=180)
    args = parser.parse_args()

    if args.all:
        profiles = ALL_PROFILES
    elif args.profile:
        profiles = [args.profile]
    else:
        options = [f"{PROFILE_EMOJI.get(profile, '[profile]')} {profile}" for profile in ALL_PROFILES] + ["All profiles sequentially"]
        index = prompt_select("Which profile do you want to test?", options, default=1)
        profiles = ALL_PROFILES if index == len(ALL_PROFILES) else [ALL_PROFILES[index]]

    model = args.model or pick_model()
    samples = args.samples
    if samples is None:
        samples = prompt_int("How many samples per combination?", default=2, hint="2 is the quality/cost default; 1 is fastest; 3 is more robust")

    think_mode = args.think
    if not args.think and len(sys.argv) == 1:
        from common import prompt_yes_no
        think_mode = prompt_yes_no("Test the model in THINKING mode (Qwen-compatible endpoints)?", default=False)

    import time
    from common import format_duration

    started = time.time()
    durations = {}
    for profile in profiles:
        profile_started = time.time()
        run_stage1(profile, model, args.timeout, n_samples=samples, enable_thinking=think_mode, language=args.language)
        durations[profile] = time.time() - profile_started
        print(f"\n⏱️ Profile {profile.upper()} completed in: {format_duration(durations[profile])}")

    print(f"\n{'=' * 62}\n🏁 TOTAL ELAPSED TIME STAGE 1: {format_duration(time.time() - started)}")
    for profile, duration in durations.items():
        print(f"   • {profile:<15}: {format_duration(duration)}")
    print(f"{'=' * 62}")

    print("\n📊 Generating the updated HTML dashboard...")
    import visualizer
    visualizer.main()


if __name__ == "__main__":
    main()
