#!/usr/bin/env python3
"""Interactive first-run setup for Senerenai-HyperProbe.

The wizard remembers the last saved values. When a local settings file already
exists, simply pressing Enter at the opening prompt keeps everything unchanged.
Use `--edit` when you actually want to review or change settings.
"""
from __future__ import annotations

import argparse
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from settings import (
    DEFAULT_SETTINGS,
    LANGUAGE_CHOICES,
    PROFILE_CHOICES,
    SETTINGS_PATH,
    load_settings,
    mask_secret,
    normalize_language_code,
    parse_selection,
    save_settings,
    validate_settings,
)


def _shown(value: Any, *, secret: bool = False, empty: str = "(not set)") -> str:
    text = mask_secret(str(value)) if secret else str(value)
    return text if text else empty


def _default_hint(key: str, *, secret: bool = False) -> str:
    return _shown(DEFAULT_SETTINGS.get(key, ""), secret=secret, empty="(blank)")


def ask_text(key: str, label: str, current: str, help_text: str, *, secret: bool = False) -> str:
    print(f"\n{label}")
    print(f"  Help: {help_text}")
    print(f"  Current saved value: {_shown(current, secret=secret)}")
    print(f"  Developer default: {_default_hint(key, secret=secret)}")
    raw = input("  New value [Enter keeps the saved value]: ").strip()
    return raw if raw else current


def ask_positive_int(key: str, label: str, current: int, help_text: str) -> int:
    print(f"\n{label}")
    print(f"  Help: {help_text}")
    print(f"  Current saved value: {current}")
    print(f"  Developer default: {_default_hint(key)}")
    while True:
        raw = input("  New value [Enter keeps the saved value]: ").strip()
        if not raw:
            return current
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        print("  Enter a positive integer, or press Enter to keep the saved value.")


def ask_yes_no(key: str, label: str, current: bool, help_text: str) -> bool:
    print(f"\n{label}")
    print(f"  Help: {help_text}")
    print(f"  Current saved value: {'yes' if current else 'no'}")
    print(f"  Developer default: {'yes' if DEFAULT_SETTINGS.get(key) else 'no'}")
    suffix = "Y/n" if current else "y/N"
    while True:
        raw = input(f"  Change value [{suffix}; Enter keeps saved value]: ").strip().lower()
        if not raw:
            return current
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("  Enter y, n, or press Enter to keep the saved value.")


def fetch_models(api_base: str, api_key: str) -> tuple[list[str], str | None]:
    """Retrieve model IDs using only the standard library."""
    headers = {"Authorization": api_key} if api_key else {}
    request = Request(f"{api_base.rstrip('/')}/models", headers=headers)
    try:
        with urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
        models = [str(item["id"]) for item in data.get("data", []) if item.get("id")]
        return models, None
    except HTTPError as exc:
        return [], f"HTTP {exc.code}"
    except URLError as exc:
        return [], f"URL error: {exc.reason}"
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        return [], f"Invalid /models response: {exc}"


def choose_workflow(settings: dict[str, Any]) -> None:
    print("\nDefault workflow")
    print("  Help: the launcher uses this workflow when you press Enter; change it only when you want a different repeat-run default.")
    print("  1. stage1   — coarse scan")
    print("  2. stage2   — refine saved Stage 1 results")
    print("  3. stage3   — stability search from saved Stage 2 results")
    print("  4. full     — Stage 1 → Stage 2 → Stage 3")
    print("  5. dashboard — regenerate HTML without model calls")
    current = str(settings.get("default_workflow", DEFAULT_SETTINGS["default_workflow"]))
    labels = {"1": "stage1", "2": "stage2", "3": "stage3", "4": "full", "5": "dashboard"}
    print(f"  Current saved value: {current}")
    print(f"  Developer default: {DEFAULT_SETTINGS['default_workflow']}")
    while True:
        raw = input("  Choose 1–5 [Enter keeps saved value]: ").strip().lower()
        if not raw:
            return
        if raw in labels:
            settings["default_workflow"] = labels[raw]
            return
        if raw in labels.values():
            settings["default_workflow"] = raw
            return
        print("  Choose 1, 2, 3, 4, or 5, or press Enter to keep the saved value.")


def choose_model(settings: dict[str, Any]) -> None:
    current = str(settings.get("model", ""))
    models, error = fetch_models(str(settings["api_base"]), str(settings.get("api_key", "")))
    if error:
        print(f"\nCould not contact {settings['api_base']}/models: {error}")
        print("  Help: the model server may be offline; you can keep the saved model or enter its ID manually.")
        settings["model"] = ask_text("model", "Default model ID", current, "The exact model identifier accepted by the server.")
        return
    if not models:
        print("\nThe endpoint responded but returned no models.")
        print("  Help: load a model on the server, or enter its exact model ID manually.")
        settings["model"] = ask_text("model", "Default model ID", current, "The exact model identifier accepted by the server.")
        return
    print("\nAvailable models (press Enter to keep the saved model):")
    for index, model in enumerate(models, 1):
        marker = "  [saved]" if model == current else ""
        print(f"  {index:>2}. {model}{marker}")
    raw = input("  Choose a model number or type a model ID [Enter keeps saved value]: ").strip()
    if not raw:
        return
    settings["model"] = models[int(raw) - 1] if raw.isdigit() and 1 <= int(raw) <= len(models) else raw


def _profile_grid(current: list[str]) -> None:
    print("\nDefault benchmark profiles")
    print("  Help: choose one or more benchmark families. Option 6 selects every profile.")
    print("  1. coding          2. agent_tools      3. creative")
    print("  4. roleplay        5. custom_lang      6. ALL profiles")
    print(f"  Current saved selection: {', '.join(current)}")
    print(f"  Developer default: {', '.join(DEFAULT_SETTINGS['default_profiles'])}")


def choose_profiles(settings: dict[str, Any]) -> None:
    current = list(settings.get("default_profiles", ["coding"]))
    _profile_grid(current)
    while True:
        raw = input("  Select numbers/names, or 6 for ALL [Enter keeps saved selection]: ").strip()
        if not raw:
            return
        if raw.lower() in {"6", "all", "*"} or "6" in {token.strip() for token in raw.split(",")}:
            settings["default_profiles"] = list(PROFILE_CHOICES)
            break
        try:
            settings["default_profiles"] = parse_selection(raw, list(PROFILE_CHOICES))
            break
        except ValueError as exc:
            print(f"  {exc} Example: 1,3,5 or creative,roleplay")
    if "custom_lang" in settings["default_profiles"]:
        choose_languages(settings)
    else:
        settings["default_languages"] = []
        settings["default_language"] = ""


def _language_grid(current: list[str]) -> None:
    print("\nDefault custom_lang languages")
    print("  Help: choose one or more languages. Option 19 selects all 18 languages.")
    for offset in range(0, len(LANGUAGE_CHOICES), 3):
        row = LANGUAGE_CHOICES[offset:offset + 3]
        print("  " + "    ".join(f"{offset + i + 1:>2}. {code} ({name})" for i, (code, name) in enumerate(row)))
    print("  19. ALL languages")
    print(f"  Current saved selection: {', '.join(current) if current else 'ALL 18 languages'}")
    print("  Developer default: ALL 18 languages")


def choose_languages(settings: dict[str, Any]) -> None:
    current = list(settings.get("default_languages", []))
    _language_grid(current)
    codes = [code for code, _ in LANGUAGE_CHOICES]
    while True:
        raw = input("  Select numbers/codes, or 19 for ALL [Enter keeps saved selection]: ").strip()
        if not raw:
            return
        tokens = {token.strip().lower() for token in raw.split(",") if token.strip()}
        if "19" in tokens or "all" in tokens or "*" in tokens:
            settings["default_languages"] = []
            settings["default_language"] = ""
            return
        try:
            selected: list[str] = []
            for token in (item.strip().lower() for item in raw.split(",")):
                token = normalize_language_code(token)
                if token.isdigit() and 1 <= int(token) <= len(codes):
                    code = codes[int(token) - 1]
                elif token in codes:
                    code = token
                else:
                    raise ValueError(f"Unknown language selection: {token}")
                if code not in selected:
                    selected.append(code)
            if not selected:
                raise ValueError("Select at least one language, or choose 19 for all languages.")
            settings["default_languages"] = selected
            settings["default_language"] = selected[0] if len(selected) == 1 else ""
            return
        except ValueError as exc:
            print(f"  {exc} Example: 1,4,18 or en,es,sk")


def show_summary(settings: dict[str, Any]) -> None:
    languages = settings.get("default_languages", [])
    print("\nSaved workflow defaults")
    print(f"  API base:     {settings['api_base']}")
    print(f"  API key:      {mask_secret(str(settings.get('api_key', '')))}")
    print(f"  Model:        {settings.get('model') or '(choose in 02_run.py)'}")
    print(f"  Profiles:     {', '.join(settings['default_profiles'])}")
    print(f"  Languages:    {', '.join(languages) if languages else 'all 18 languages'}")
    print(f"  Workflow:     {settings.get('default_workflow', 'full')}")
    print(f"  Timeout:      {settings['timeout']}s")
    print(f"  Concurrency:  {settings['concurrency']}")
    print(f"  Max tokens:   {settings['max_tokens']}")
    print(
        "  Pipeline:     "
        f"S1={settings['stage1_samples']} samples, "
        f"S2={settings['stage2_samples']} samples / {settings['stage2_max_combos']} combinations, "
        f"S3={settings['stage3_samples']} samples / top {settings['stage3_top_n']}"
    )


def interactive_setup(*, force_edit: bool = False) -> None:
    existing = SETTINGS_PATH.exists()
    settings = load_settings()
    print("=" * 72)
    print("Senerenai-HyperProbe 01_setup.py — persistent local setup")
    print("Saved values are shown first. Press Enter to keep them.")
    print("=" * 72)
    if existing and not force_edit:
        show_summary(settings)
        choice = input("\nPress Enter to keep all settings and exit, or type edit to change them: ").strip().lower()
        if choice != "edit":
            print("Settings unchanged. Run `python3 02_run.py` when you are ready to benchmark.")
            return

    settings["api_base"] = ask_text("api_base", "OpenAI-compatible API base", str(settings["api_base"]), "Server root before /models and /chat/completions; normally ends in /v1.").rstrip("/")
    settings["api_key"] = ask_text("api_key", "Authorization value", str(settings.get("api_key", "")), "Complete Authorization header value, for example Bearer token.", secret=True)
    choose_model(settings)
    choose_profiles(settings)
    choose_workflow(settings)
    settings["timeout"] = ask_positive_int("timeout", "Per-request timeout (seconds)", int(settings["timeout"]), "Maximum wait for one model response.")
    settings["concurrency"] = ask_positive_int("concurrency", "Concurrent requests", int(settings["concurrency"]), "Parallel requests; keep 1 unless the server supports multiple slots.")
    settings["max_tokens"] = ask_positive_int("max_tokens", "Maximum completion tokens", int(settings["max_tokens"]), "Upper bound for each generated answer.")
    settings["retry"] = ask_yes_no("retry", "Retry one failed request", bool(settings["retry"]), "Retry once after a transient request failure.")
    settings["thinking"] = ask_yes_no("thinking", "Enable thinking mode by default when supported", bool(settings["thinking"]), "Use only when the selected model server documents this extension.")
    settings["stage1_samples"] = ask_positive_int("stage1_samples", "Stage 1 samples per combination", int(settings["stage1_samples"]), "Repeated answers reduce the chance of selecting a lucky result.")
    settings["stage2_samples"] = ask_positive_int("stage2_samples", "Stage 2 samples per combination", int(settings["stage2_samples"]), "Repeated answers during bounded refinement.")
    settings["stage2_max_combos"] = ask_positive_int("stage2_max_combos", "Stage 2 maximum combinations", int(settings["stage2_max_combos"]), "Safety cap on Stage 2 request volume.")
    settings["stage3_samples"] = ask_positive_int("stage3_samples", "Stage 3 samples per combination", int(settings["stage3_samples"]), "Repeated answers during local stability search.")
    settings["stage3_top_n"] = ask_positive_int("stage3_top_n", "Stage 3 top candidates", int(settings["stage3_top_n"]), "Number of Stage 2 candidates explored locally.")

    errors = validate_settings(settings)
    if errors:
        print("\nSettings were not saved:")
        for error in errors:
            print(f"  - {error}")
        return
    save_settings(settings)
    show_summary(settings)
    print(f"\nSaved to {SETTINGS_PATH}")
    print("Next: run `python3 02_run.py` to select profiles and launch a stage or the full pipeline.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update local Senerenai-HyperProbe settings.")
    parser.add_argument("--show", action="store_true", help="Print saved settings with the API key masked.")
    parser.add_argument("--edit", action="store_true", help="Open the full settings editor even when values are already saved.")
    parser.add_argument("--reset", action="store_true", help="Reset local settings to developer defaults.")
    args = parser.parse_args()
    if args.show:
        show_summary(load_settings())
        print(f"Settings file: {SETTINGS_PATH}")
        return
    if args.reset:
        save_settings(dict(DEFAULT_SETTINGS))
        print(f"Reset local settings at {SETTINGS_PATH}. Run `python3 01_setup.py --edit` to configure them.")
        return
    interactive_setup(force_edit=args.edit)


if __name__ == "__main__":
    main()
