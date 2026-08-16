"""Fast, offline public-interface smoke checks for Senerenai-HyperProbe."""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

MODULES = [
    "config", "common", "stage1_coarse", "stage2_refine", "stage3_finest", "visualizer", "runner",
    "grader.coder", "grader.agent", "grader.creative", "grader.roleplay", "grader.repetition", "grader.custom_lang",
    "tests.coding", "tests.agent_tools", "tests.creative", "tests.roleplay", "tests.custom_lang",
]
for module_name in MODULES:
    importlib.import_module(module_name)

from common import build_run_manifest, extract_clean_reply, format_duration, validate_stage_handoff
from grader.coder import preflight_code_safety
from grader.repetition import detect_degeneration
from grader.roleplay import grade_roleplay
from tests.roleplay import ROLEPLAY_PROMPTS

assert extract_clean_reply("<think>hidden</think>visible") == "visible"
assert format_duration(8.4) == "8.4s"
assert detect_degeneration("same same same same same same")["score"] < 1.0
assert "blocked_import:subprocess" in preflight_code_safety("import subprocess")

manifest = build_run_manifest(
    stage="stage1", profile="roleplay", model="demo", prompts=ROLEPLAY_PROMPTS[:1],
    samples=1, enable_thinking=False, parameter_combinations=1,
)
assert manifest["schema_version"] == "1.1"
validate_stage_handoff(
    {"_meta": {"stage": "stage1", "profile": "roleplay", "model": "demo"}, "top_combos": []},
    expected_stage="stage1", expected_profile="roleplay", expected_model="demo", required_keys=("top_combos",),
)
roleplay_result = grade_roleplay("As an AI, I cannot roleplay this scene.", ROLEPLAY_PROMPTS[0])
assert roleplay_result.dimensions["no_ooc"] == 0.0

print(f"smoke-ok: {len(MODULES)} modules")
