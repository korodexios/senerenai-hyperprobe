"""Stage 3: perform local parameter drift and stability-aware selection.

Candidates are ranked using mean quality, variance, and worst-case quality so a
single lucky completion cannot dominate the final preset.
"""
import argparse
import itertools
import json
import sys
from collections import defaultdict
from pathlib import Path

from config import ALL_PROFILES, PROFILE_EMOJI, SEARCH_DESIGN_VERSION, STAGE3_DEFAULT_TOP_N, STAGE3_DEFAULT_SAMPLES, STAGE3_DRIFT_STEPS, round_param_value
from common import (append_jsonl, build_run_manifest, extract_clean_reply, fingerprint, format_duration, load_stage, param_hash, pick_model, prompt_int, prompt_select, RESULTS_DIR, run_batch, save_stage)
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


def _holdout(prompts: list[dict], stage2_count: int) -> list[dict]:
    """Return up to two prompts not used by Stage 2, with a safe fallback."""
    held_out = prompts[stage2_count:stage2_count + 2]
    return held_out or prompts[-min(2, len(prompts)):]


PROMPTS = {
    "coding": _holdout(CODING_PROMPTS, 5),
    "agent_tools": _holdout(AGENT_PROMPTS, 3),
    "creative": _holdout(CREATIVE_PROMPTS, 3),
    "roleplay": _holdout(ROLEPLAY_PROMPTS, 3),
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


def _bounded_value(parameter: str, value: float) -> float:
    """Keep local drift candidates inside valid API sampling bounds."""
    bounds = {
        "temperature": (0.0, 2.0),
        "min_p": (0.0, 1.0),
        "top_p": (0.01, 1.0),
        "repetition_penalty": (0.01, 2.0),
    }
    low, high = bounds.get(parameter, (float("-inf"), float("inf")))
    return round_param_value(parameter, min(high, max(low, value)))


def local_drift_combos(base_params: dict, primary_pair: tuple[str, str] | None = None) -> list[dict]:
    """Return axial drifts plus four diagonal checks for the primary interaction."""
    combos = [dict(base_params)]
    for parameter, step in STAGE3_DRIFT_STEPS.items():
        for delta in (-step, step):
            combo = dict(base_params)
            combo[parameter] = _bounded_value(parameter, combo.get(parameter, 0.0) + delta)
            combos.append(combo)

    if primary_pair and all(parameter in STAGE3_DRIFT_STEPS for parameter in primary_pair):
        first, second = primary_pair
        for first_sign, second_sign in itertools.product((-1, 1), repeat=2):
            combo = dict(base_params)
            combo[first] = _bounded_value(first, combo.get(first, 0.0) + first_sign * STAGE3_DRIFT_STEPS[first])
            combo[second] = _bounded_value(second, combo.get(second, 0.0) + second_sign * STAGE3_DRIFT_STEPS[second])
            combos.append(combo)

    seen, unique = set(), []
    for combo in combos:
        key = json.dumps(combo, sort_keys=True)
        if key not in seen:
            seen.add(key)
            unique.append(combo)
    return unique


def run_stage3(profile: str, model: str, top_from_stage2: list[dict],
               n_samples: int = STAGE3_DEFAULT_SAMPLES, timeout: int = 180,
               top_n: int = STAGE3_DEFAULT_TOP_N, enable_thinking: bool = False,
               language: str | None = None, primary_pair: tuple[str, str] | list[str] | None = None) -> dict:
    prompts = PROMPTS[profile]
    if language and profile == "custom_lang":
        prompts = [prompt for prompt in prompts if prompt.get("language") == language]
        if not prompts:
            raise ValueError(f"No custom-language prompts found for language: {language}")
    candidates = top_from_stage2[:top_n]

    normalized_pair = tuple(primary_pair) if primary_pair and len(primary_pair) == 2 else None
    seen, combos = set(), []
    for cand in candidates:
        for c in local_drift_combos(cand["params"], normalized_pair):
            k = json.dumps(c, sort_keys=True)
            if k not in seen:
                seen.add(k)
                combos.append(c)

    if not candidates:
        raise ValueError("Stage 3 requires at least one Stage 2 candidate.")
    total = len(prompts) * len(combos) * n_samples
    run_manifest = build_run_manifest(
        stage="stage3", profile=profile, model=model, prompts=prompts,
        samples=n_samples, enable_thinking=enable_thinking,
        parameter_combinations=len(combos),
    )
    run_id = fingerprint(run_manifest)
    validation_kind = "unseen holdout prompts" if profile != "custom_lang" else "language-scoped validation prompts"
    pair_label = " × ".join(normalized_pair) if normalized_pair else "none"
    print(f"\n{'='*62}\n  🎯 STAGE 3 — HOLDOUT STABILITY VALIDATION — {profile.upper()}\n"
          f"  Validation: {validation_kind} | Primary pair diagonals: {pair_label}\n"
          f"  Model: {model} | Candidates: {len(candidates)} | Drift combinations: {len(combos)} "
          f"| Samples: {n_samples} | Total calls: {total}\n{'='*62}")

    jobs = [{"prompt": p, "params": c, "sample_idx": si}
            for p in prompts for c in combos for si in range(n_samples)]

    batch = run_batch(model, jobs, timeout=timeout, enable_thinking=enable_thinking)

    by_hash = defaultdict(list)
    by_hash_elapsed = defaultdict(list)
    by_hash_params = {}
    failed_by_hash = defaultdict(int)
    replies_per_prompt_hash = defaultdict(lambda: defaultdict(list))

    for row in batch:
        prompt, params, res = row["prompt"], row["params"], row["result"]
        ph = param_hash(params)
        by_hash_params[ph] = params

        if "error" in res:
            score, reply, dims, flags = 0.0, "", {}, [res["error"]]
            failed_by_hash[ph] += 1
        else:
            grader = get_grader(profile, prompt)
            clean_reply = extract_clean_reply(res["reply"])
            prev_samples = replies_per_prompt_hash[prompt["id"]][ph]
            if profile in ("creative", "roleplay", "custom_lang"):
                g = grader(clean_reply, prompt, prev_replies=prev_samples)
            else:
                g = grader(clean_reply, prompt)
            score, reply, dims, flags = g.weighted_score, clean_reply, g.dimensions, g.flags
            by_hash[ph].append(score)
            by_hash_elapsed[ph].append(row.get("elapsed", 0.0))
            replies_per_prompt_hash[prompt["id"]][ph].append(reply)

        append_jsonl("stage3", profile, model, {
            "run_id": run_id, "search_design": SEARCH_DESIGN_VERSION, "prompt_id": prompt["id"], "profile": profile, "language": prompt.get("language"), "param_hash": ph,
            "params": params, "sample_idx": row["sample_idx"],
            "grade": {"weighted_score": round(score, 4), "dimensions": dims, "flags": flags},
            "elapsed": round(row["elapsed"], 2),
            "reply_preview": reply[:300].replace("\n", " "),
        })

    expected_observations = len(prompts) * n_samples
    incomplete_candidates = {}
    ranked = []
    for ph, scores in by_hash.items():
        if len(scores) < expected_observations:
            incomplete_candidates[ph] = {"successful": len(scores), "expected": expected_observations}
            continue
        mean = sum(scores) / len(scores)
        std = (sum((s - mean) ** 2 for s in scores) / len(scores)) ** 0.5
        worst = min(scores)
        avg_time = sum(by_hash_elapsed[ph]) / len(by_hash_elapsed[ph]) if by_hash_elapsed[ph] else 0.0
        combined = mean - 0.6 * std + 0.2 * worst
        ranked.append({"params": by_hash_params[ph], "param_hash": ph,
                        "mean": round(mean, 4), "std": round(std, 4),
                        "worst": round(worst, 4), "combined": round(combined, 4),
                        "n": len(scores), "avg_time": round(avg_time, 2)})
    ranked.sort(key=lambda x: x["combined"], reverse=True)

    if not ranked:
        raise RuntimeError("Stage 3 received no successful model responses; inspect API errors before trusting a preset.")

    warnings = []
    for pid, hashes in replies_per_prompt_hash.items():
        diag = cross_combo_invariance(hashes)
        if diag["invariant"]:
            warnings.append(f"{pid}: {diag['note']}")

    print(f"\n  🏆 Top 5 final candidates (stability-first score):")
    for i, cs in enumerate(ranked[:5]):
        print(f"    #{i+1} combined={cs['combined']:.3f} mean={cs['mean']:.3f}±{cs['std']:.3f} "
              f"worst={cs['worst']:.3f}  {cs['params']}")

    if incomplete_candidates:
        warnings.append(f"{len(incomplete_candidates)} candidate(s) had incomplete holdout coverage and were excluded from the final preset ranking.")
    if any(failed_by_hash.values()):
        warnings.append(f"{sum(failed_by_hash.values())} failed call(s) were excluded from the final stability ranking.")

    if warnings:
        print(f"\n  ⚠️  WARNINGS:")
        for w in warnings:
            print(f"    - {w}")

    error_count = sum(failed_by_hash.values())
    data = {
        "run_manifest": run_manifest,
        "summary": {
            "attempted_calls": len(jobs),
            "successful_calls": len(jobs) - error_count,
            "failed_calls": error_count,
            "failure_rate": round(error_count / max(len(jobs), 1), 4),
        },
        "search_design": SEARCH_DESIGN_VERSION,
        "validation": {
            "prompt_ids": [prompt["id"] for prompt in prompts],
            "prompt_source": validation_kind,
            "primary_pair": list(normalized_pair) if normalized_pair else [],
            "expected_observations_per_candidate": expected_observations,
            "excluded_incomplete_candidates": incomplete_candidates,
        },
        "ranked": ranked[:15],
        "warnings": warnings,
    }
    save_stage("stage3", profile, model, data, language=language)

    if ranked:
        final = ranked[0]["params"]
        model_safe = model.replace("/", "_").replace("\\", "_")
        language_suffix = f"_{language}" if language else ""
        final_file = RESULTS_DIR / f"final_preset_{profile}_{model_safe}{language_suffix}.json"
        final_payload = {
            "search_design": SEARCH_DESIGN_VERSION,
            "sampling_parameters": final,
            "selection": ranked[0],
            "validation": data["validation"],
            "run_manifest": run_manifest,
            "warnings": warnings,
        }
        with open(final_file, "w", encoding="utf-8") as f:
            json.dump(final_payload, f, indent=2, ensure_ascii=False)
        print(f"\n  ✅ FINAL PRESET for {profile}: {final_file}")
        print(json.dumps(final, indent=4))

    return data


def main():
    ap = argparse.ArgumentParser(
        description="Senerenai-HyperProbe Stage 3 — finest drift + stability lock. "
                     "Run without arguments for interactive mode.")
    ap.add_argument("--profile", "-p", default=None, choices=ALL_PROFILES)
    ap.add_argument("--language", help="Restrict the custom_lang profile to a language code, for example en, es, zh, or sk.")
    ap.add_argument("--all", action="store_true", help="Run sequentially for all profiles (each profile must have its own stage2 JSON)")
    ap.add_argument("--model", "-m", default=None, help="Model ID. If omitted, an interactive model picker is used.")
    ap.add_argument("--stage2", default=None, help="Path to Stage 2 JSON (default: locate it by profile/model)")
    ap.add_argument("--top-n", type=int, default=None,
                     help="Number of top Stage 2 candidates to drift")
    ap.add_argument("--samples", type=int, default=None)
    ap.add_argument("--think", action="store_true", help="Enable thinking mode")
    ap.add_argument("--timeout", type=int, default=180)
    args = ap.parse_args()

    if args.all:
        profiles = ALL_PROFILES
    elif args.profile:
        profiles = [args.profile]
    else:
        options = [f"{PROFILE_EMOJI.get(p, '📋')} {p}" for p in ALL_PROFILES] + ["All profiles sequentially"]
        idx = prompt_select("Which profile should be fine-tuned (Stage 3)?", options, default=1)
        profiles = ALL_PROFILES if idx == len(ALL_PROFILES) else [ALL_PROFILES[idx]]

    model = args.model or pick_model()

    top_n = args.top_n
    if top_n is None:
        top_n = prompt_int("How many top Stage 2 candidates should be fine-tuned locally?",
                            default=STAGE3_DEFAULT_TOP_N, hint="more = more thorough, but slower")

    samples = args.samples
    if samples is None:
        samples = prompt_int("How many samples per combination (for stability checking)?",
                              default=STAGE3_DEFAULT_SAMPLES, hint="more = more reliable detection of unstable presets")

    think_mode = args.think
    if not args.think and len(sys.argv) == 1:
        from common import prompt_yes_no
        think_mode = prompt_yes_no("Test the model in THINKING mode?", default=False)

    import time

    t_start_total = time.time()
    profile_durations = {}

    for profile in profiles:
        stage2 = load_stage(
            args.stage2 or "stage2", profile, model, language=args.language,
            expected_stage="stage2", expected_search_design=SEARCH_DESIGN_VERSION,
            required_keys=("top_combos", "narrowed_ranges"),
        )
        top = stage2.get("top_combos", [])
        if not top:
            print(f"❌ Stage 2 JSON for {profile} has no top_combos — run stage2_refine.py first.")
            continue

        t_start_prof = time.time()
        run_stage3(profile, model, top, n_samples=samples,
                   timeout=args.timeout, top_n=top_n, enable_thinking=think_mode,
                   language=args.language, primary_pair=stage2.get("search_strategy", {}).get("primary_interaction"))
        prof_dur = time.time() - t_start_prof
        profile_durations[profile] = prof_dur
        print(f"\n⏱️ Profile {profile.upper()} completed in: {format_duration(prof_dur)}")

    total_dur = time.time() - t_start_total
    print(f"\n{'='*62}")
    print(f"🏁 TOTAL ELAPSED TIME STAGE 3: {format_duration(total_dur)}")
    for p, d in profile_durations.items():
        print(f"   • {p:<15}: {format_duration(d)}")
    print(f"{'='*62}")

    # Automatically generate the visualization
    print("\n📊 Generating the updated HTML dashboard...")
    import visualizer
    visualizer.main()


if __name__ == "__main__":
    main()