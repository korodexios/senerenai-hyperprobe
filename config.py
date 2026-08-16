"""Central configuration for Senerenai-HyperProbe.

Saved local settings provide beginner-friendly defaults, while environment
variables always override them for CI, containers, and secret managers.
"""
from __future__ import annotations

import os
from typing import Any

from settings import load_settings

_LOCAL_SETTINGS = load_settings()


def _setting(env_name: str, local_name: str, default: Any) -> Any:
    """Use an environment value when supplied, otherwise use saved local settings."""
    return os.getenv(env_name, _LOCAL_SETTINGS.get(local_name, default))


API_BASE = str(_setting("HYPERPROBE_API_BASE", "api_base", "http://localhost:8080/v1")).rstrip("/")
API_KEY = str(_setting("HYPERPROBE_API_KEY", "api_key", "Bearer llama.cpp"))
DEFAULT_TIMEOUT = int(_setting("HYPERPROBE_TIMEOUT", "timeout", 180))
RETRY_ON_ERROR = str(_setting("HYPERPROBE_RETRY", "retry", True)).lower() not in {"0", "false", "no"}
RETRY_DELAY = float(os.getenv("HYPERPROBE_RETRY_DELAY", "3"))
MAX_CONCURRENT_REQUESTS = int(_setting("HYPERPROBE_CONCURRENCY", "concurrency", 1))
MAX_TOKENS = int(_setting("HYPERPROBE_MAX_TOKENS", "max_tokens", 2048))
ENABLE_THINKING = bool(_LOCAL_SETTINGS.get("thinking", False))

BIG_FOUR = ("temperature", "min_p", "top_p", "repetition_penalty")

# Stage 1 is an interpretable, quality-first fractional design.  It uses a
# shared baseline, a dense one-factor sweep for every primary parameter, and
# the low/high corners of three interactions.  This yields much stronger
# evidence than a small hand-picked list without the cost of a full 6^4 grid.
STAGE1_BASELINE = {"temperature": 0.6, "min_p": 0.05, "top_p": 0.9, "repetition_penalty": 1.05}
STAGE1_MAIN_EFFECT_LEVELS = {
    "temperature": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
    "min_p": [0.0, 0.02, 0.05, 0.08, 0.12, 0.16],
    "top_p": [0.65, 0.75, 0.85, 0.9, 0.95, 1.0],
    "repetition_penalty": [1.0, 1.02, 1.05, 1.08, 1.12, 1.16],
}
STAGE1_INTERACTION_PAIR_LABELS = (
    "temperature x top_p",
    "min_p x top_p",
    "temperature x repetition_penalty",
)
STAGE1_INTERACTIONS = (
    # temperature × top_p
    {"temperature": 0.2, "top_p": 0.75},
    {"temperature": 0.2, "top_p": 1.0},
    {"temperature": 1.0, "top_p": 0.75},
    {"temperature": 1.0, "top_p": 1.0},
    # min_p × top_p
    {"min_p": 0.0, "top_p": 0.75},
    {"min_p": 0.0, "top_p": 1.0},
    {"min_p": 0.16, "top_p": 0.75},
    {"min_p": 0.16, "top_p": 1.0},
    # temperature × repetition_penalty
    {"temperature": 0.2, "repetition_penalty": 1.0},
    {"temperature": 0.2, "repetition_penalty": 1.16},
    {"temperature": 1.0, "repetition_penalty": 1.0},
    {"temperature": 1.0, "repetition_penalty": 1.16},
)


def _stage1_design() -> list[dict[str, float]]:
    """Build the baseline, one-factor main-effect, and interaction rows."""
    rows = [dict(STAGE1_BASELINE)]
    for name, levels in STAGE1_MAIN_EFFECT_LEVELS.items():
        for value in levels:
            if value == STAGE1_BASELINE[name]:
                continue
            row = dict(STAGE1_BASELINE)
            row[name] = value
            rows.append(row)
    for changes in STAGE1_INTERACTIONS:
        row = dict(STAGE1_BASELINE)
        row.update(changes)
        rows.append(row)
    return rows


STAGE1_COMBOS = _stage1_design()
STAGE1_DESIGN_LABEL = "quality-first baseline + dense one-factor sweeps + three targeted pair interactions"
SEARCH_DESIGN_VERSION = "hybrid_v4"
STAGE_GRID_STEPS = 3
STAGE2_DEFAULT_MAX_COMBOS = 5
STAGE2_DEFAULT_SAMPLES = 1
STAGE3_DEFAULT_TOP_N = 2
STAGE3_DEFAULT_SAMPLES = 1
STAGE3_DRIFT_STEPS = {"temperature": 0.1, "min_p": 0.03, "top_p": 0.1, "repetition_penalty": 0.03}

PARAM_GRID_COARSE = {
    "temperature": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
    "min_p": [0.0, 0.03, 0.05, 0.1],
    "top_p": [0.7, 0.85, 0.95, 1.0],
    "top_k": [0, 20, 40, 50],
    "repetition_penalty": [1.0, 1.05, 1.1, 1.15],
    "presence_penalty": [0.0, 0.3, 0.6, 1.0],
    "frequency_penalty": [0.0, 0.2, 0.4, 0.6],
}
PARAM_COMBOS_STRATEGIC = STAGE1_COMBOS
QUICKSCAN_COMBOS = STAGE1_COMBOS
SAMPLES_PER_COMBO = 3
QUICK_SAMPLES = 1

ALL_PROFILES = ["coding", "agent_tools", "creative", "roleplay", "custom_lang"]
PROFILE_EMOJI = {"coding": "[code]", "agent_tools": "[agent]", "creative": "[creative]", "roleplay": "[roleplay]", "custom_lang": "[custom language]"}
SCORING_WEIGHTS = {
    "coding": {"correctness": .28, "completeness": .13, "code_quality": .13, "follows_spec": .13, "no_hallucination": .13, "parseable": .10, "no_repetition": .10},
    "agent_tools": {"valid_json": .40, "correct_tool": .25, "arguments_valid": .25, "no_repetition": .10},
    "creative": {"creativity": .30, "vocab_diversity": .25, "no_fluff": .15, "coherence": .15, "no_repetition": .15},
    "roleplay": {"persona_retention": .35, "no_ooc": .25, "engagement": .15, "length": .10, "no_repetition": .15},
    "custom_lang": {"language_quality": .35, "diacritics_accuracy": .25, "no_foreign_leaks": .20, "coherence": .10, "no_repetition": .10},
}
STABILITY_WEIGHTS = {"consistency": .40, "no_derail": .30, "best_quality": .30}
CHAIN_PARAM_ORDER = list(BIG_FOUR)
CHAIN_SWEEP_RANGES = {"temperature": (0.1, 1.5, .2), "min_p": (0.0, .15, .03), "top_p": (.85, 1.0, .05), "repetition_penalty": (1.0, 1.15, .05)}
CHAIN_BASE_PRESET = {"temperature": .8, "min_p": 0.0, "top_p": 1.0, "repetition_penalty": 1.0}

def round_param_value(name: str, value: float) -> float:
    """Round sampling values to realistic API precision."""
    return round(value, 1 if name in {"temperature", "top_p"} else 2 if name in {"min_p", "repetition_penalty"} else 3)

def should_skip(params: dict[str, Any]) -> bool:
    """Reject combinations with invalid probability bounds."""
    return not (0 <= params.get("temperature", 0) and 0 <= params.get("min_p", 0) <= 1 and 0 < params.get("top_p", 1) <= 1 and params.get("repetition_penalty", 1) > 0)

def generate_combos(grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Return the Cartesian product of a parameter grid, excluding invalid rows."""
    import itertools
    names = list(grid)
    return [dict(zip(names, values)) for values in itertools.product(*(grid[n] for n in names)) if not should_skip(dict(zip(names, values)))]
