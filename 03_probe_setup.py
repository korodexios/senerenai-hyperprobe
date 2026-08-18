"""Configure optional refusal and NIAH probes once for later zero-prompt runs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from probe_settings import (
    DEFAULT_NIAH_CONTEXT_SIZES,
    DEFAULT_NIAH_DEPTHS,
    DEFAULT_PROBE_SETTINGS,
    PRESET_MODES,
    PROBE_SETTINGS_PATH,
    load_probe_settings,
    save_probe_settings,
)
from probe_utils import parse_manual_preset


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [Enter keeps {default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value if value else default


def ask_int(prompt: str, default: int, minimum: int = 1) -> int:
    while True:
        raw = ask(prompt, str(default))
        try:
            value = int(raw)
            if value >= minimum:
                return value
        except ValueError:
            pass
        print(f"  Please enter an integer >= {minimum}.")


def ask_csv_ints(prompt: str, default: list[int], minimum: int, maximum: int) -> list[int]:
    while True:
        raw = ask(prompt, ",".join(str(item) for item in default))
        try:
            values = [int(item.strip()) for item in raw.split(",") if item.strip()]
            if values and all(minimum <= item <= maximum for item in values):
                return values
        except ValueError:
            pass
        print(f"  Enter comma-separated integers between {minimum} and {maximum}.")


def choose_modes(current: list[str]) -> list[str]:
    print("\nProbe modes to run (you can select both):")
    print("  1. refusal — false-refusal, safe redirection, companion roleplay")
    print("  2. niah    — long-context needle-in-a-haystack retrieval")
    print("  3. both    — run refusal and NIAH sequentially")
    options = {"1": ["refusal"], "2": ["niah"], "3": ["refusal", "niah"]}
    default = "3" if set(current) == {"refusal", "niah"} else "2" if current == ["niah"] else "1"
    while True:
        raw = ask("Select 1, 2, or 3", default)
        if raw in options:
            return options[raw]
        print("  Choose 1, 2, or 3.")


def main() -> None:
    current = load_probe_settings()
    print("=" * 72)
    print("Senerenai-HyperProbe — OPTIONAL PROBE SETTINGS")
    print("Configure once here, then run `python3 04_probe.py` without extra prompts.")
    print(f"Settings file: {PROBE_SETTINGS_PATH}")
    print("=" * 72)
    settings = dict(current)
    settings["enabled_modes"] = choose_modes(current["enabled_modes"])

    print("\nPreset selection")
    print("  baseline   = one stable public baseline")
    print("  final      = one saved Stage 3 preset")
    print("  compare    = baseline + saved Stage 3 preset (recommended)")
    print("  mini-sweep = baseline + final + low/high temperature")
    print("  manual     = one JSON preset entered below")
    preset_default = current.get("preset", "compare")
    while True:
        preset = ask("Preset mode", preset_default).lower()
        if preset in PRESET_MODES:
            settings["preset"] = preset
            break
        print("  Choose: " + ", ".join(PRESET_MODES))
    settings["preset_profile"] = ask("Profile supplying the final preset (coding/creative/roleplay/etc.)", current.get("preset_profile", "roleplay"))
    settings["language"] = ask("Optional custom_lang code", current.get("language", ""))
    if settings["preset"] == "manual":
        while True:
            raw = ask("Manual preset JSON", current.get("manual_preset", json.dumps({"temperature": 0.6, "min_p": 0.05, "top_p": 0.9, "repetition_penalty": 1.05})) )
            try:
                parse_manual_preset(raw)
                settings["manual_preset"] = raw
                break
            except ValueError as exc:
                print(f"  {exc}")

    if "refusal" in settings["enabled_modes"]:
        print("\nRefusal dataset")
        settings["refusal_dataset"] = ask("JSONL dataset path", current.get("refusal_dataset", DEFAULT_PROBE_SETTINGS["refusal_dataset"]))
        settings["refusal_samples"] = ask_int("Samples per refusal item", int(current.get("refusal_samples", 2)))

    if "niah" in settings["enabled_modes"]:
        print("\nNIAH corpus and matrix")
        while True:
            corpus = ask("UTF-8 corpus path (at least ~80k varied tokens recommended)", current.get("niah_corpus", ""))
            if corpus:
                settings["niah_corpus"] = corpus
                break
            print("  A corpus path is required when NIAH is enabled.")
        settings["niah_context_sizes"] = ask_csv_ints("Target context sizes in tokens", list(current.get("niah_context_sizes", DEFAULT_NIAH_CONTEXT_SIZES)), 256, 1_000_000)
        settings["niah_depths"] = ask_csv_ints("Needle depths as percentages", list(current.get("niah_depths", DEFAULT_NIAH_DEPTHS)), 0, 100)
        settings["niah_samples"] = ask_int("Samples per NIAH case", int(current.get("niah_samples", 1)))

    settings["timeout"] = ask_int("Probe request timeout in seconds", int(current.get("timeout", 180)))
    settings["thinking"] = ask("Enable thinking mode by default? (y/N)", "y" if current.get("thinking") else "N").lower() in {"y", "yes"}
    settings["regenerate_dashboard"] = ask("Regenerate dashboard after probe? (Y/n)", "Y" if current.get("regenerate_dashboard", True) else "n").lower() not in {"n", "no"}
    path = save_probe_settings(settings)

    print("\nSaved optional probe settings")
    print(f"  Modes:        {', '.join(settings['enabled_modes'])}")
    print(f"  Preset:       {settings['preset']} ({settings['preset_profile']})")
    if "refusal" in settings["enabled_modes"]:
        print(f"  Refusal:      {settings['refusal_dataset']} | {settings['refusal_samples']} samples/item")
    if "niah" in settings["enabled_modes"]:
        print(f"  NIAH corpus:  {settings['niah_corpus']}")
        print(f"  NIAH matrix:   {settings['niah_context_sizes']} tokens × {settings['niah_depths']}% × {settings['niah_samples']} sample(s)")
    print(f"  Saved to:     {path}")
    print("Next: python3 04_probe.py")


if __name__ == "__main__":
    main()
