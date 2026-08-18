"""Zero-prompt runner for the optional refusal and NIAH probes."""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from common import format_duration, utc_now
from settings import load_settings
from probe_settings import load_probe_settings
from probe_utils import select_presets


def main() -> None:
    workflow_started_at = utc_now()
    workflow_started_monotonic = time.monotonic()
    settings = load_probe_settings()
    shared = load_settings()
    model = str(shared.get("model", "")).strip()
    if not model:
        raise SystemExit("No saved model ID. Run `python3 01_configure_sampler_benchmark.py --edit` first.")

    presets = select_presets(
        settings["preset"],
        profile=settings["preset_profile"],
        model=model,
        language=settings.get("language") or None,
        manual_preset=settings.get("manual_preset") or None,
    )
    thinking = bool(settings.get("thinking", False))
    project_root = Path(__file__).resolve().parent
    def resolve_saved_path(raw: str) -> Path:
        path = Path(raw)
        return path if path.is_absolute() else project_root / path
    print("Using saved configuration for additional benchmarks")
    print(f"  Modes: {', '.join(settings['enabled_modes'])}")
    print(f"  Model: {model}")
    print(f"  Presets: {', '.join(row['label'] for row in presets)}")

    probe_started_monotonic = time.monotonic()
    if "refusal" in settings["enabled_modes"]:
        from probe_refusal import run_refusal_probe
        refusal_mode = str(settings.get("refusal_dataset_mode", "quick"))
        refusal_key = "refusal_full_dataset" if refusal_mode == "full" else "refusal_dataset"
        refusal_path = resolve_saved_path(str(settings.get(refusal_key, "")))
        if not refusal_path.exists():
            raise SystemExit(
                f"Saved refusal dataset ({refusal_mode}) was not found: {refusal_path}. "
                "Run `python3 03_configure_additional_benchmarks.py` and choose a valid numbered dataset."
            )
        print(f"  Refusal dataset: {refusal_mode} | {refusal_path}")
        run_refusal_probe(
            model=model,
            preset_rows=presets,
            dataset_path=refusal_path,
            dataset_mode=refusal_mode,
            timeout=int(settings["timeout"]),
            samples=int(settings["refusal_samples"]),
            enable_thinking=thinking,
        )

    if "niah" in settings["enabled_modes"]:
        corpus = str(settings.get("niah_corpus", "")).strip()
        if not corpus:
            raise SystemExit("NIAH is enabled but no corpus path is saved. Run `python3 03_configure_additional_benchmarks.py`.")
        from probe_niah import run_niah_probe
        run_niah_probe(
            model=model,
            preset_rows=presets,
            corpus_path=resolve_saved_path(corpus),
            context_sizes=tuple(settings["niah_context_sizes"]),
            depths=tuple(settings["niah_depths"]),
            timeout=int(settings["timeout"]),
            samples=int(settings["niah_samples"]),
            enable_thinking=thinking,
        )

    probe_elapsed = time.monotonic() - probe_started_monotonic
    dashboard_elapsed = 0.0
    if settings.get("regenerate_dashboard", True):
        print("\nGenerating the dashboard from all available result records...")
        dashboard_started_monotonic = time.monotonic()
        import visualizer
        visualizer.main()
        dashboard_elapsed = time.monotonic() - dashboard_started_monotonic
    workflow_elapsed = time.monotonic() - workflow_started_monotonic
    print("\n" + "=" * 70)
    print("  ADDITIONAL BENCHMARKS — WORKFLOW SUMMARY")
    print(f"  Started (UTC): {workflow_started_at}")
    print(f"  Finished (UTC): {utc_now()}")
    print(f"  Probe execution elapsed: {format_duration(probe_elapsed)}")
    if settings.get("regenerate_dashboard", True):
        print(f"  Dashboard generation elapsed: {format_duration(dashboard_elapsed)}")
    print(f"  Total additional workflow elapsed: {format_duration(workflow_elapsed)}")
    print("=" * 70)


def cli() -> None:
    """Provide standard command help without changing zero-prompt execution."""
    parser = argparse.ArgumentParser(
        description=(
            "Run the saved refusal/companion and NIAH benchmark configuration. "
            "Configure it first with 03_configure_additional_benchmarks.py."
        )
    )
    parser.parse_args()
    main()


if __name__ == "__main__":
    cli()
