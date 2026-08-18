#!/usr/bin/env python3
"""Interactive multi-profile launcher for Senerenai-HyperProbe.

The launcher provides a simple numbered workflow while preserving the standalone
stage scripts for scripting, CI, and expert workflows.
"""
from __future__ import annotations

import argparse
import time
from typing import Any

from settings import LANGUAGE_CHOICES, LANGUAGE_CODES, PROFILE_CHOICES, load_settings, normalize_language_code, parse_selection


WORKFLOW_OPTIONS = {
    "1": "stage1",
    "2": "stage2",
    "3": "stage3",
    "4": "full",
    "5": "dashboard",
}


def choose_profiles(saved: list[str]) -> list[str]:
    print("\nChoose one or more benchmark profiles:")
    for index, profile in enumerate(PROFILE_CHOICES, 1):
        marker = " (saved default)" if profile in saved else ""
        print(f"  {index}. {profile}{marker}")
    print("  6. ALL profiles")
    while True:
        raw = input(f"Profiles, comma-separated numbers/names, or 6 for ALL [Enter keeps {', '.join(saved)}]: ").strip()
        if not raw:
            return list(saved)
        if "6" in {token.strip() for token in raw.split(",")} or raw.lower() in {"all", "*"}:
            return list(PROFILE_CHOICES)
        try:
            return parse_selection(raw, list(PROFILE_CHOICES))
        except ValueError as exc:
            print(exc)


def choose_workflow(saved: str = "full") -> str:
    print("\nChoose what to run:")
    print("  1. Stage 1 only — coarse scan")
    print("  2. Stage 2 only — refine using saved Stage 1 results")
    print("  3. Stage 3 only — stability search using saved Stage 2 results")
    print("  4. Full pipeline — Stage 1 → Stage 2 → Stage 3")
    print("  5. Dashboard only — regenerate HTML from existing JSONL records")
    while True:
        raw = input(f"Workflow [Enter keeps {saved}]: ").strip() or saved
        if raw in WORKFLOW_OPTIONS:
            return WORKFLOW_OPTIONS[raw]
        print("Choose 1, 2, 3, 4, or 5.")


def choose_model(saved_model: str) -> str:
    raw = input(f"Model ID [Enter keeps {saved_model or 'no saved model'}]: ").strip()
    model = raw or saved_model
    if not model:
        raise ValueError("A model ID is required. Run 01_configure_sampler_benchmark.py or provide --model.")
    return model


def choose_languages(profiles: list[str], saved: list[str]) -> list[str]:
    if "custom_lang" not in profiles:
        return []
    print("\nChoose custom_lang languages:")
    print("  Help: select one or more numbers/codes; 19 means all 18 languages.")
    for offset in range(0, len(LANGUAGE_CHOICES), 3):
        row = LANGUAGE_CHOICES[offset:offset + 3]
        print("  " + "    ".join(f"{offset + i + 1:>2}. {code} ({name})" for i, (code, name) in enumerate(row)))
    print("  19. ALL languages")
    print(f"  Saved selection: {', '.join(saved) if saved else 'all 18 languages'}")
    codes = [code for code, _ in LANGUAGE_CHOICES]
    while True:
        raw = input("  Selection [Enter keeps saved selection]: ").strip().lower()
        if not raw:
            return list(saved)
        tokens = {token.strip() for token in raw.split(",") if token.strip()}
        if tokens & {"19", "all", "*"}:
            return []
        try:
            selected: list[str] = []
            for token in (item.strip() for item in raw.split(",")):
                token = normalize_language_code(token)
                if token.isdigit() and 1 <= int(token) <= len(codes):
                    code = codes[int(token) - 1]
                elif token in codes:
                    code = token
                else:
                    raise ValueError(f"Unknown language selection: {token}")
                if code not in selected:
                    selected.append(code)
            if selected:
                return selected
            raise ValueError("Select at least one language or choose 19 for all.")
        except ValueError as exc:
            print(f"  {exc} Example: 1,4,18 or en,es,sk")


def load_runtime_modules() -> dict[str, Any]:
    """Import runtime modules only after the saved settings are established."""
    from common import load_stage
    from stage1_coarse import run_stage1
    from stage2_refine import run_stage2
    from stage3_finest import run_stage3
    import visualizer
    return {
        "load_stage": load_stage,
        "run_stage1": run_stage1,
        "run_stage2": run_stage2,
        "run_stage3": run_stage3,
        "visualizer": visualizer,
    }


def stage2_ranges(load_stage, profile: str, model: str, language: str | None = None) -> dict:
    handoff = load_stage(
        "stage1", profile, model, language=language,
        expected_stage="stage1", required_keys=("suggested_ranges", "top_combos"),
    )
    ranges = dict(handoff["suggested_ranges"])
    top = handoff["top_combos"]
    if top:
        ranges["_base"] = top[0]["params"]
    return ranges


def run_selected(
    *,
    profiles: list[str],
    model: str,
    workflow: str,
    settings: dict[str, Any],
    languages: list[str],
    think: bool | None = None,
) -> None:
    """Execute the requested workflow for every selected profile/language target."""
    runtime = load_runtime_modules()
    if workflow == "dashboard":
        runtime["visualizer"].main()
        return

    enable_thinking = settings["thinking"] if think is None else think
    total_start = time.monotonic()
    failures: list[str] = []
    for profile in profiles:
        targets = languages if profile == "custom_lang" and languages else [None]
        for selected_language in targets:
            label = f"{profile} | language={selected_language}" if selected_language else profile
            print("\n" + "=" * 72)
            print(f"Senerenai-HyperProbe launcher: {label} | {workflow} | {model}")
            print("=" * 72)
            started = time.monotonic()
            try:
                if workflow == "stage1":
                    runtime["run_stage1"](
                        profile, model, timeout=settings["timeout"],
                        n_samples=settings["stage1_samples"],
                        enable_thinking=enable_thinking, language=selected_language,
                    )
                elif workflow == "stage2":
                    stage1 = runtime["load_stage"](
                        "stage1", profile, model, language=selected_language,
                        expected_stage="stage1", required_keys=("suggested_ranges", "top_combos"),
                    )
                    ranges = dict(stage1["suggested_ranges"])
                    runtime["run_stage2"](
                        profile, model, ranges, timeout=settings["timeout"],
                        n_samples=settings["stage2_samples"], max_combos=settings["stage2_max_combos"],
                        enable_thinking=enable_thinking, language=selected_language, stage1_evidence=stage1,
                    )
                elif workflow == "stage3":
                    handoff = runtime["load_stage"](
                        "stage2", profile, model, language=selected_language,
                        expected_stage="stage2", required_keys=("top_combos", "narrowed_ranges"),
                    )
                    runtime["run_stage3"](
                        profile, model, handoff["top_combos"], timeout=settings["timeout"],
                        n_samples=settings["stage3_samples"], top_n=settings["stage3_top_n"],
                        enable_thinking=enable_thinking, language=selected_language,
                        primary_pair=handoff.get("search_strategy", {}).get("primary_interaction"),
                        benchmark_id=handoff.get("benchmark_id"),
                    )
                elif workflow == "full":
                    stage1 = runtime["run_stage1"](
                        profile, model, timeout=settings["timeout"],
                        n_samples=settings["stage1_samples"],
                        enable_thinking=enable_thinking, language=selected_language,
                    )
                    ranges = dict(stage1["suggested_ranges"])
                    stage2 = runtime["run_stage2"](
                        profile, model, ranges, timeout=settings["timeout"],
                        n_samples=settings["stage2_samples"], max_combos=settings["stage2_max_combos"],
                        enable_thinking=enable_thinking, language=selected_language, stage1_evidence=stage1,
                    )
                    runtime["run_stage3"](
                        profile, model, stage2["top_combos"], timeout=settings["timeout"],
                        n_samples=settings["stage3_samples"], top_n=settings["stage3_top_n"],
                        enable_thinking=enable_thinking, language=selected_language,
                        primary_pair=stage2.get("search_strategy", {}).get("primary_interaction"),
                        benchmark_id=stage2.get("benchmark_id"),
                    )
                else:
                    raise ValueError(f"Unsupported workflow: {workflow}")
                print(f"Completed {label} in {time.monotonic() - started:.1f}s")
            except Exception as exc:
                failures.append(f"{label}: {exc}")
                print(f"FAILED {label}: {exc}")

    print("\nGenerating the dashboard from all available result records...")
    runtime["visualizer"].main()
    print(f"\nWorkflow elapsed time: {time.monotonic() - total_start:.1f}s")
    if failures:
        raise RuntimeError("One or more targets failed: " + " | ".join(failures))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run saved Senerenai-HyperProbe settings immediately, or apply explicit one-run overrides."
    )
    parser.add_argument("--profiles", help="Temporary comma-separated profile override.")
    parser.add_argument("--all-profiles", action="store_true", help="Temporarily run every benchmark profile.")
    parser.add_argument("--choose-profiles", action="store_true", help="Show the profile menu for this run.")
    parser.add_argument("--workflow", choices=("stage1", "stage2", "stage3", "full", "dashboard"), help="Temporary workflow override.")
    parser.add_argument("--choose-workflow", action="store_true", help="Show the workflow menu for this run.")
    parser.add_argument("--choose-languages", action="store_true", help="Show the language grid for this run.")
    parser.add_argument("--interactive", action="store_true", help="Show all run-time menus instead of using saved values.")
    parser.add_argument("--model", help="Temporary model ID override.")
    parser.add_argument("--language", help="Temporarily restrict custom_lang to one or more comma-separated language codes.")
    parser.add_argument("--think", action="store_true", help="Enable thinking mode for this run.")
    parser.add_argument("--no-think", action="store_true", help="Disable saved thinking-mode default for this run.")
    args = parser.parse_args()
    if args.think and args.no_think:
        parser.error("Use either --think or --no-think, not both.")
    if args.all_profiles and args.profiles:
        parser.error("Use either --all-profiles or --profiles, not both.")

    settings = load_settings()
    # No flags means zero-prompt execution: every choice comes from 01_configure_sampler_benchmark.py.
    if args.all_profiles:
        profiles = list(PROFILE_CHOICES)
    elif args.profiles:
        profiles = parse_selection(args.profiles, list(PROFILE_CHOICES))
    elif args.interactive or args.choose_profiles:
        profiles = choose_profiles(settings["default_profiles"])
    else:
        profiles = list(settings["default_profiles"])

    if args.workflow:
        workflow = args.workflow
    elif args.interactive or args.choose_workflow:
        workflow = choose_workflow(str(settings.get("default_workflow", "full")))
    else:
        workflow = str(settings.get("default_workflow", "full"))

    if workflow == "dashboard":
        model = args.model or str(settings.get("model") or "dashboard")
    elif args.model:
        model = args.model
    elif args.interactive:
        model = choose_model(str(settings.get("model", "")))
    else:
        model = str(settings.get("model", "")).strip()
        if not model:
            parser.error("No saved model ID. Run `python3 01_configure_sampler_benchmark.py --edit` or provide --model.")

    saved_languages = list(settings.get("default_languages", []))
    if args.language:
        languages = [normalize_language_code(item) for item in args.language.split(",") if item.strip()]
    elif args.interactive or args.choose_languages:
        languages = choose_languages(profiles, saved_languages)
    else:
        languages = saved_languages if "custom_lang" in profiles else []
    invalid_languages = [code for code in languages if code not in LANGUAGE_CODES]
    if invalid_languages:
        parser.error("Unknown language code(s): " + ", ".join(invalid_languages))

    think = True if args.think else False if args.no_think else None
    language_label = ",".join(languages) if languages else ("all 18" if "custom_lang" in profiles else "not applicable")
    print(
        "Using saved configuration" if not any((args.profiles, args.all_profiles, args.choose_profiles, args.workflow, args.choose_workflow, args.choose_languages, args.interactive, args.model, args.language, args.think, args.no_think))
        else "Using saved configuration with one-run overrides",
    )
    print(f"  Profiles: {', '.join(profiles)} | Workflow: {workflow} | Model: {model} | Languages: {language_label}")
    run_selected(
        profiles=profiles, model=model, workflow=workflow, settings=settings,
        languages=languages, think=think,
    )


if __name__ == "__main__":
    main()
