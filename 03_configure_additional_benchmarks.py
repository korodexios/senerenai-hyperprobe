"""Configure additional benchmarks once for later zero-prompt runs.

The normal interface is deliberately number-first: press Enter to keep a saved
choice, or press one digit to change it. Text entry is reserved for advanced
custom paths, unusual NIAH matrices, or manually supplied sampler parameters.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from probe_settings import (
    DEFAULT_NIAH_CONTEXT_SIZES,
    REFUSAL_DATASET_MODES,
    DEFAULT_NIAH_DEPTHS,
    DEFAULT_PROBE_SETTINGS,
    PROBE_SETTINGS_PATH,
    load_probe_settings,
    save_probe_settings,
)
from probe_utils import parse_manual_preset
from settings import LANGUAGE_CHOICES, PROFILE_CHOICES

ROOT_DIR = Path(__file__).resolve().parent
PRESET_OPTIONS = ("baseline", "final", "compare", "mini-sweep", "manual")
PROFILE_OPTIONS = tuple(PROFILE_CHOICES)
COMMON_NIAH_MATRICES: tuple[tuple[str, list[int], list[int]], ...] = (
    ("Quick — 4k, 16k, 32k × 10%, 50%, 90%", [4000, 16000, 32000], [10, 50, 90]),
    ("Light — 4k, 16k × 10%, 50%, 90%", [4000, 16000], [10, 50, 90]),
    ("Deep — 4k, 16k, 32k, 64k × 10%, 50%, 90%", [4000, 16000, 32000, 64000], [10, 50, 90]),
)
TIMEOUT_OPTIONS = (120, 180, 300)


def ask_text(prompt: str, default: str = "") -> str:
    suffix = f" [Enter keeps {default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value if value else default


def choose_number(title: str, options: list[str], default_index: int) -> int:
    """Print numbered options and return a zero-based selection with Enter default."""
    print(f"\n{title}")
    for index, label in enumerate(options, 1):
        marker = "  [saved]" if index - 1 == default_index else ""
        print(f"  {index}. {label}{marker}")
    while True:
        raw = input(f"  Select 1–{len(options)} [Enter keeps {default_index + 1}]: ").strip()
        if not raw:
            return default_index
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print(f"  Press one number from 1 to {len(options)}, or Enter to keep the saved choice.")


def choose_yes_no(title: str, current: bool, *, yes_label: str = "Yes", no_label: str = "No") -> bool:
    index = choose_number(title, [yes_label, no_label], 0 if current else 1)
    return index == 0


def ask_positive_int(title: str, current: int, minimum: int = 1) -> int:
    while True:
        raw = ask_text(title, str(current))
        if raw.isdigit() and int(raw) >= minimum:
            return int(raw)
        print(f"  Enter an integer >= {minimum}, or press Enter to keep the saved value.")


def choose_modes(current: list[str]) -> list[str]:
    print("\nAdditional benchmarks to run")
    print("  1. Refusal & companion benchmark")
    print("     Checks false refusals, safe redirection, adult consent-aware non-explicit roleplay.")
    print("  2. NIAH long-context benchmark")
    print("     Checks retrieval from long text at different context sizes and positions.")
    print("  3. Both benchmarks")
    default = 2 if set(current) == {"refusal", "niah"} else 1 if current == ["niah"] else 0
    selected = choose_number("Select what will run when you start 04_run_additional_benchmarks.py", ["Refusal & companion", "NIAH long context", "Both"], default)
    return (["refusal"], ["niah"], ["refusal", "niah"])[selected]


def choose_preset(current: str) -> str:
    labels = [
        "Baseline — one stable public sampler preset",
        "Final — saved Stage 3 sampler preset only",
        "Compare — baseline + saved Stage 3 final preset (recommended)",
        "Mini sweep — baseline + final + low/high temperature",
        "Manual — enter one complete sampler JSON preset (advanced)",
    ]
    default = PRESET_OPTIONS.index(current) if current in PRESET_OPTIONS else PRESET_OPTIONS.index("compare")
    return PRESET_OPTIONS[choose_number("Sampler presets to benchmark", labels, default)]


def choose_profile(current: str) -> str:
    labels = [
        "coding", "agent_tools", "creative", "roleplay", "custom_lang",
    ]
    default = labels.index(current) if current in labels else labels.index("roleplay")
    return labels[choose_number("Profile supplying the saved Stage 3 final preset", labels, default)]


def choose_language(current: str) -> str:
    print("\nLanguage for a custom_lang final preset")
    print("  1. Not applicable / no language suffix")
    for index, (code, name) in enumerate(LANGUAGE_CHOICES, 2):
        marker = "  [saved]" if code == current else ""
        print(f"  {index:>2}. {code} ({name}){marker}")
    default = 0 if not current else next((index for index, (code, _) in enumerate(LANGUAGE_CHOICES, 1) if code == current), 0)
    while True:
        raw = input(f"  Select 1–{len(LANGUAGE_CHOICES) + 1} [Enter keeps {default + 1}]: ").strip()
        if not raw:
            selected = default
            break
        if raw.isdigit() and 1 <= int(raw) <= len(LANGUAGE_CHOICES) + 1:
            selected = int(raw) - 1
            break
        print("  Press one number, or Enter to keep the saved choice.")
    return "" if selected == 0 else LANGUAGE_CHOICES[selected - 1][0]


def discover_refusal_datasets() -> list[Path]:
    """Return public and local JSONL datasets in a stable, user-friendly order."""
    candidates: list[Path] = []
    for directory in (ROOT_DIR / "datasets" / "refusal", ROOT_DIR / "datasets" / "local"):
        if directory.is_dir():
            candidates.extend(sorted(directory.glob("*.jsonl")))
    return candidates


def relative_to_project(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT_DIR).as_posix()
    except ValueError:
        return str(path)


def choose_refusal_mode(current: str) -> str:
    labels = [
        "Quick — public compact dataset; recommended default",
        "Full — extended dataset; more calls and more detailed coverage",
    ]
    default = REFUSAL_DATASET_MODES.index(current) if current in REFUSAL_DATASET_MODES else 0
    return REFUSAL_DATASET_MODES[choose_number("Refusal benchmark size", labels, default)]


def choose_refusal_dataset(current: str) -> str:
    datasets = discover_refusal_datasets()
    labels = [relative_to_project(path) for path in datasets]
    labels.append("Type a different JSONL path (advanced)")
    default = labels.index(current) if current in labels else 0
    choice = choose_number("Refusal dataset", labels, default)
    if choice < len(datasets):
        return labels[choice]
    return ask_text("Custom JSONL dataset path", current)


def choose_niah_matrix(current_sizes: list[int], current_depths: list[int]) -> tuple[list[int], list[int]]:
    labels = [entry[0] for entry in COMMON_NIAH_MATRICES]
    labels.append("Keep current saved matrix")
    labels.append("Type custom sizes and depths (advanced)")
    default = next(
        (index for index, (_, sizes, depths) in enumerate(COMMON_NIAH_MATRICES) if sizes == current_sizes and depths == current_depths),
        len(COMMON_NIAH_MATRICES),
    )
    choice = choose_number("NIAH context matrix", labels, default)
    if choice < len(COMMON_NIAH_MATRICES):
        _, sizes, depths = COMMON_NIAH_MATRICES[choice]
        return list(sizes), list(depths)
    if choice == len(COMMON_NIAH_MATRICES):
        return current_sizes, current_depths
    sizes = ask_int_list("Custom context sizes in tokens, comma-separated", current_sizes, 256, 1_000_000)
    depths = ask_int_list("Custom needle depths in percent, comma-separated", current_depths, 0, 100)
    return sizes, depths


def ask_int_list(title: str, current: list[int], minimum: int, maximum: int) -> list[int]:
    while True:
        raw = ask_text(title, ",".join(str(item) for item in current))
        try:
            values = [int(item.strip()) for item in raw.split(",") if item.strip()]
            if values and all(minimum <= value <= maximum for value in values):
                return values
        except ValueError:
            pass
        print(f"  Enter comma-separated integers between {minimum} and {maximum}.")


def choose_timeout(current: int) -> int:
    labels = [f"{seconds} seconds" for seconds in TIMEOUT_OPTIONS] + ["Keep current value", "Type a custom timeout (advanced)"]
    default = TIMEOUT_OPTIONS.index(current) if current in TIMEOUT_OPTIONS else len(TIMEOUT_OPTIONS)
    choice = choose_number("Per-request timeout", labels, default)
    if choice < len(TIMEOUT_OPTIONS):
        return TIMEOUT_OPTIONS[choice]
    if choice == len(TIMEOUT_OPTIONS):
        return current
    return ask_positive_int("Custom timeout in seconds", current)


def choose_samples(title: str, current: int, default: int) -> int:
    values = list(dict.fromkeys([default, 2, 3]))
    labels = [f"{value} sample{'s' if value != 1 else ''}" for value in values] + ["Keep current value", "Type a custom number (advanced)"]
    default_index = values.index(current) if current in values else len(values)
    choice = choose_number(title, labels, default_index)
    if choice < len(values):
        return values[choice]
    if choice == len(values):
        return current
    return ask_positive_int("Custom sample count", current)


def prompt_manual_preset(current: str) -> str:
    print("\nManual sampler preset is not a dataset path.")
    print("It is only for advanced users who want to type a complete sampler JSON object.")
    print("For a normal refusal dataset such as datasets/local/my_refusal_v1.jsonl, choose Compare, Final, or Baseline instead.")
    while True:
        raw = ask_text("Manual sampler JSON", current or json.dumps({"temperature": 0.6, "min_p": 0.05, "top_p": 0.9, "repetition_penalty": 1.05}))
        try:
            parse_manual_preset(raw)
            return raw
        except ValueError as exc:
            print(f"  {exc}")


def main() -> None:
    current = load_probe_settings()
    print("=" * 72)
    print("Senerenai-HyperProbe — ADDITIONAL BENCHMARK SETTINGS")
    print("Normal use: press Enter to keep saved choices or press one number to change them.")
    print(f"Settings file: {PROBE_SETTINGS_PATH}")
    print("=" * 72)
    settings: dict[str, Any] = dict(current)
    settings["enabled_modes"] = choose_modes(list(current["enabled_modes"]))
    settings["preset"] = choose_preset(str(current.get("preset", "compare")))
    if settings["preset"] in {"final", "compare", "mini-sweep"}:
        settings["preset_profile"] = choose_profile(str(current.get("preset_profile", "roleplay")))
        settings["language"] = choose_language(str(current.get("language", ""))) if settings["preset_profile"] == "custom_lang" else ""
    else:
        # Baseline and manual presets do not reuse a Stage 3 profile or language suffix.
        settings["language"] = ""
    if settings["preset"] == "manual":
        settings["manual_preset"] = prompt_manual_preset(str(current.get("manual_preset", "")))

    if "refusal" in settings["enabled_modes"]:
        settings["refusal_dataset_mode"] = choose_refusal_mode(str(current.get("refusal_dataset_mode", "quick")))
        dataset_key = "refusal_full_dataset" if settings["refusal_dataset_mode"] == "full" else "refusal_dataset"
        current_dataset = str(current.get(dataset_key, DEFAULT_PROBE_SETTINGS[dataset_key]))
        settings[dataset_key] = choose_refusal_dataset(current_dataset)
        settings["refusal_samples"] = choose_samples("Refusal samples per item", int(current.get("refusal_samples", 2)), 2)

    if "niah" in settings["enabled_modes"]:
        default_corpus = str(current.get("niah_corpus", ""))
        print("\nNIAH corpus")
        print("  Press Enter to keep the saved corpus path. You only type a path the first time or when changing corpus.")
        while True:
            corpus = ask_text("UTF-8 corpus path", default_corpus)
            if corpus:
                settings["niah_corpus"] = corpus
                break
            print("  A corpus path is required when NIAH is enabled.")
        sizes, depths = choose_niah_matrix(
            list(current.get("niah_context_sizes", DEFAULT_NIAH_CONTEXT_SIZES)),
            list(current.get("niah_depths", DEFAULT_NIAH_DEPTHS)),
        )
        settings["niah_context_sizes"] = sizes
        settings["niah_depths"] = depths
        settings["niah_samples"] = choose_samples("NIAH samples per case", int(current.get("niah_samples", 1)), 1)

    settings["timeout"] = choose_timeout(int(current.get("timeout", 180)))
    settings["thinking"] = choose_yes_no("Thinking mode", bool(current.get("thinking", False)), yes_label="Enabled", no_label="Disabled")
    settings["regenerate_dashboard"] = choose_yes_no("Regenerate dashboard after benchmarks", bool(current.get("regenerate_dashboard", True)), yes_label="Yes", no_label="No")
    path = save_probe_settings(settings)

    print("\nSaved additional benchmark settings")
    print(f"  Benchmarks:   {', '.join(settings['enabled_modes'])}")
    print(f"  Samplers:     {settings['preset']} ({settings['preset_profile']})")
    if "refusal" in settings["enabled_modes"]:
        refusal_key = "refusal_full_dataset" if settings.get("refusal_dataset_mode") == "full" else "refusal_dataset"
        print(f"  Refusal:      {settings['refusal_dataset_mode']} | {settings[refusal_key]} | {settings['refusal_samples']} samples/item")
    if "niah" in settings["enabled_modes"]:
        print(f"  NIAH corpus:  {settings['niah_corpus']}")
        print(f"  NIAH matrix:  {settings['niah_context_sizes']} tokens × {settings['niah_depths']}% × {settings['niah_samples']} sample(s)")
    print(f"  Saved to:     {path}")
    print("Next: python3 04_run_additional_benchmarks.py")


if __name__ == "__main__":
    main()
