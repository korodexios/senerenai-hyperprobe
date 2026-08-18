"""Run optional Senerenai-HyperProbe refusal or long-context diagnostics.

This launcher reuses saved local API/runtime settings but never changes Stage 1–3
handoffs or final sampler presets.
"""
from __future__ import annotations

import argparse

from settings import load_settings
from probe_utils import select_presets


def parse_int_csv(raw: str, *, label: str, minimum: int, maximum: int) -> tuple[int, ...]:
    try:
        values = tuple(int(item.strip()) for item in raw.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{label} must be comma-separated integers.") from exc
    if not values or any(value < minimum or value > maximum for value in values):
        raise argparse.ArgumentTypeError(f"{label} values must be between {minimum} and {maximum}.")
    return values


def main() -> None:
    settings = load_settings()
    parser = argparse.ArgumentParser(
        description="Run optional standalone Senerenai-HyperProbe refusal or NIAH diagnostics using saved settings."
    )
    parser.add_argument("--mode", required=True, choices=("refusal", "niah"), help="Separate diagnostic mode; it does not run or alter Stage 1–3.")
    parser.add_argument("--model", default=str(settings.get("model", "")), help="Temporary model override; default is the saved model.")
    parser.add_argument("--preset", choices=("baseline", "final", "compare", "mini-sweep", "manual"), default="compare", help="Sampling preset source; compare = baseline plus saved Stage 3 final preset.")
    parser.add_argument("--preset-profile", default="roleplay", choices=("coding", "agent_tools", "creative", "roleplay", "custom_lang"), help="Profile whose final Stage 3 preset is reused when applicable.")
    parser.add_argument("--language", help="Language suffix for a custom_lang final preset.")
    parser.add_argument("--manual-preset", help="JSON object containing temperature, min_p, top_p, and repetition_penalty; required only for --preset manual.")
    parser.add_argument("--dataset", help="Refusal JSONL dataset path. Defaults to the public safe dataset shipped with the project.")
    parser.add_argument("--corpus", help="UTF-8 text corpus required for --mode niah.")
    parser.add_argument("--context-sizes", default="4000,16000,32000", help="NIAH target input-token estimates, comma-separated.")
    parser.add_argument("--depths", default="10,50,90", help="NIAH needle depths as percentages, comma-separated.")
    parser.add_argument("--samples", type=int, help="Samples per probe case; default 2 for refusal and 1 for NIAH.")
    parser.add_argument("--timeout", type=int, default=int(settings["timeout"]), help="Per-request timeout in seconds.")
    parser.add_argument("--think", action="store_true", help="Enable thinking mode for this probe run.")
    parser.add_argument("--no-dashboard", action="store_true", help="Do not regenerate the existing HTML dashboard after the probe finishes.")
    args = parser.parse_args()

    model = str(args.model).strip()
    if not model:
        parser.error("No saved model ID. Run `python3 01_setup.py --edit` or provide --model.")
    if args.samples is not None and args.samples < 1:
        parser.error("--samples must be a positive integer.")

    presets = select_presets(
        args.preset,
        profile=args.preset_profile,
        model=model,
        language=args.language,
        manual_preset=args.manual_preset,
    )
    enable_thinking = True if args.think else bool(settings.get("thinking", False))
    print("Using saved configuration for an optional probe")
    print(f"  Mode: {args.mode} | Model: {model} | Preset mode: {args.preset} | Presets: {', '.join(row['label'] for row in presets)}")

    if args.mode == "refusal":
        from probe_refusal import run_refusal_probe
        run_refusal_probe(
            model=model,
            preset_rows=presets,
            dataset_path=args.dataset or None,
            timeout=args.timeout,
            samples=args.samples or 2,
            enable_thinking=enable_thinking,
        )
    else:
        if not args.corpus:
            parser.error("--corpus PATH is required for --mode niah. Provide one UTF-8 text corpus file.")
        from probe_niah import run_niah_probe
        context_sizes = parse_int_csv(args.context_sizes, label="--context-sizes", minimum=256, maximum=1_000_000)
        depths = parse_int_csv(args.depths, label="--depths", minimum=0, maximum=100)
        run_niah_probe(
            model=model,
            preset_rows=presets,
            corpus_path=args.corpus,
            context_sizes=context_sizes,
            depths=depths,
            timeout=args.timeout,
            samples=args.samples or 1,
            enable_thinking=enable_thinking,
        )

    if not args.no_dashboard:
        print("\nGenerating the dashboard from all available result records...")
        import visualizer
        visualizer.main()


if __name__ == "__main__":
    main()
