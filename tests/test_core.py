"""Offline unit tests for public Senerenai-HyperProbe behavior and safety controls."""
from __future__ import annotations

import unittest

from common import (
    build_run_manifest,
    extract_clean_reply,
    format_duration,
    prompt_bank_fingerprint,
    stage_file,
    validate_stage_handoff,
)
from config import ALL_PROFILES, STAGE1_BASELINE, STAGE1_COMBOS, round_param_value
from grader.agent import grade_agent
from grader.coder import preflight_code_safety
from grader.repetition import detect_degeneration
from grader.roleplay import grade_roleplay
from stage1_coarse import changed_parameters
from stage2_refine import PROMPTS as STAGE2_PROMPTS, build_interaction_candidates
from stage3_finest import local_drift_combos
from tests.agent_tools import AGENT_PROMPTS
from tests.custom_lang import CUSTOM_LANG_PROMPTS, LANGUAGE_PROFILES
from tests.roleplay import ROLEPLAY_PROMPTS


class CoreTests(unittest.TestCase):
    def test_clean_reply_removes_reasoning(self):
        self.assertEqual(extract_clean_reply("<think>hidden</think>visible"), "visible")
        self.assertEqual(extract_clean_reply("<think>unfinished"), "")

    def test_duration_formatting(self):
        self.assertEqual(format_duration(8.4), "8.4s")
        self.assertEqual(format_duration(65), "1m 05s")

    def test_parameter_rounding(self):
        self.assertEqual(round_param_value("temperature", 0.26), 0.3)
        self.assertEqual(round_param_value("min_p", 0.126), 0.13)

    def test_stage_one_is_an_interpretable_fractional_design(self):
        self.assertEqual(len(STAGE1_COMBOS), 33)
        self.assertEqual(STAGE1_COMBOS[0], STAGE1_BASELINE)
        main_effect_rows = [combo for combo in STAGE1_COMBOS if len(changed_parameters(combo)) == 1]
        interaction_rows = [combo for combo in STAGE1_COMBOS if len(changed_parameters(combo)) == 2]
        self.assertEqual(len(main_effect_rows), 20)
        self.assertEqual(len(interaction_rows), 12)
        self.assertEqual(
            {tuple(changed_parameters(combo)) for combo in interaction_rows},
            {("temperature", "top_p"), ("min_p", "top_p"), ("temperature", "repetition_penalty")},
        )

    def test_stage_two_builds_targeted_interaction_candidates(self):
        evidence = {
            "design": {"baseline": STAGE1_BASELINE},
            "main_effects": {
                "temperature": {"effect_span": 0.30, "selected_values": [{"value": 0.3}, {"value": 0.9}]},
                "top_p": {"effect_span": 0.20, "selected_values": [{"value": 0.7}, {"value": 1.0}]},
                "min_p": {"effect_span": 0.10, "selected_values": [{"value": 0.0}, {"value": 0.10}]},
                "repetition_penalty": {"effect_span": 0.05, "selected_values": [{"value": 1.0}, {"value": 1.12}]},
            },
            "top_combos": [],
        }
        candidates, strategy = build_interaction_candidates(evidence, {}, max_combos=8)
        self.assertEqual(strategy["mode"], "targeted_interaction_refinement")
        self.assertEqual(strategy["primary_interaction"], ["temperature", "top_p"])
        self.assertTrue(any(item["role"] == "assembled_main_effect_winners" for item in candidates))
        self.assertLessEqual(len(candidates), 8)

    def test_stage_three_drift_respects_probability_bounds(self):
        combos = local_drift_combos({"temperature": 0.0, "min_p": 0.0, "top_p": 1.0, "repetition_penalty": 1.0})
        for combo in combos:
            self.assertGreaterEqual(combo["temperature"], 0.0)
            self.assertGreaterEqual(combo["min_p"], 0.0)
            self.assertGreater(combo["top_p"], 0.0)
            self.assertLessEqual(combo["top_p"], 1.0)
            self.assertGreater(combo["repetition_penalty"], 0.0)

    def test_stage_three_adds_primary_pair_diagonal_drifts(self):
        base = {"temperature": 0.6, "min_p": 0.05, "top_p": 0.9, "repetition_penalty": 1.05}
        axial = local_drift_combos(base)
        paired = local_drift_combos(base, ("temperature", "top_p"))
        self.assertEqual(len(axial), 9)
        self.assertEqual(len(paired), 13)

    def test_profiles_are_public_and_multilingual(self):
        self.assertIn("custom_lang", ALL_PROFILES)
        self.assertEqual(len(CUSTOM_LANG_PROMPTS), len(LANGUAGE_PROFILES))
        self.assertGreaterEqual(len(LANGUAGE_PROFILES), 15)
        for prompt in CUSTOM_LANG_PROMPTS:
            self.assertIn(prompt["language"], LANGUAGE_PROFILES)
            self.assertIn("expected_script", prompt)

    def test_stage_two_custom_language_includes_slovak(self):
        languages = {prompt["language"] for prompt in STAGE2_PROMPTS["custom_lang"]}
        self.assertIn("sk", languages)
        self.assertIn("cs", languages)

    def test_degenerate_text_is_penalized(self):
        result = detect_degeneration("same same same same same same")
        self.assertLess(result["score"], 1.0)

    def test_prompt_fingerprint_is_deterministic(self):
        prompts = [{"id": "p1", "system": "s", "prompt": "u"}]
        self.assertEqual(prompt_bank_fingerprint(prompts), prompt_bank_fingerprint(prompts))

    def test_run_manifest_contains_non_secret_reproducibility_fields(self):
        manifest = build_run_manifest(
            stage="stage1", profile="coding", model="demo", prompts=[{"id": "p"}],
            samples=2, enable_thinking=False, parameter_combinations=12,
        )
        self.assertEqual(manifest["schema_version"], "1.1")
        self.assertEqual(manifest["prompt_count"], 1)
        self.assertNotIn("api_key", manifest)

    def test_stage_handoff_validation_rejects_mismatch(self):
        payload = {"_meta": {"stage": "stage1", "profile": "coding", "model": "demo"}, "top_combos": []}
        validate_stage_handoff(payload, expected_stage="stage1", expected_profile="coding", expected_model="demo")
        with self.assertRaises(ValueError):
            validate_stage_handoff(payload, expected_stage="stage2")

    def test_language_scoped_stage_handoffs_are_distinct(self):
        spanish = stage_file("stage1", "custom_lang", "demo", "es")
        slovak = stage_file("stage1", "custom_lang", "demo", "sk")
        self.assertNotEqual(spanish, slovak)
        self.assertTrue(str(spanish).endswith("_es.json"))
        payload = {"_meta": {"stage": "stage1", "profile": "custom_lang", "model": "demo", "language": "es"}, "top_combos": []}
        validate_stage_handoff(payload, expected_stage="stage1", expected_profile="custom_lang", expected_model="demo")
        with self.assertRaises(ValueError):
            from common import load_stage
            import tempfile
            from pathlib import Path
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "stage.json"
                path.write_text(__import__("json").dumps(payload), encoding="utf-8")
                load_stage(path, profile="custom_lang", model="demo", language="sk", expected_stage="stage1")

    def test_safety_preflight_blocks_process_and_dynamic_execution(self):
        self.assertIn("blocked_import:subprocess", preflight_code_safety("import subprocess"))
        self.assertIn("blocked_call:eval", preflight_code_safety("eval('2 + 2')"))
        self.assertEqual(preflight_code_safety("def add(a, b):\n    return a + b\n"), [])

    def test_agent_grader_validates_nested_schema(self):
        prompt = next(item for item in AGENT_PROMPTS if item["id"] == "agent_03_nested_order")
        valid = '{"tool":"create_order","parameters":{"customer_id":4082,"priority":true,"items":[{"sku":"KB-990","qty":2},{"sku":"MS-102","qty":1}]}}'
        result = grade_agent(valid, prompt)
        self.assertEqual(result.dimensions["correct_tool"], 1.0)
        self.assertEqual(result.dimensions["arguments_valid"], 1.0)

    def test_agent_grader_rejects_invalid_nested_schema(self):
        prompt = next(item for item in AGENT_PROMPTS if item["id"] == "agent_03_nested_order")
        invalid = '{"tool":"create_order","parameters":{"customer_id":"4082","priority":"yes","items":[{"sku":"KB-990"}]}}'
        result = grade_agent(invalid, prompt)
        self.assertLess(result.dimensions["arguments_valid"], 1.0)
        self.assertTrue(any(flag.startswith("argument_invalid") or flag.startswith("argument_missing") for flag in result.flags))

    def test_roleplay_grader_catches_ooc_and_modern_drift(self):
        prompt = next(item for item in ROLEPLAY_PROMPTS if item["id"] == "rp_09")
        result = grade_roleplay("As an AI, I would use an algorithm on the internet.", prompt)
        self.assertEqual(result.dimensions["no_ooc"], 0.0)
        self.assertIn("out_of_character_language", result.flags)
        self.assertTrue(any(flag.startswith("modern_term_drift") for flag in result.flags))

    def test_roleplay_constraint_is_scored(self):
        prompt = next(item for item in ROLEPLAY_PROMPTS if item["id"] == "rp_10")
        response = "*Kael kneels beside the child.* Steel holds when hands do not. Will you stand by the hearth until I return?"
        result = grade_roleplay(response, prompt)
        self.assertGreater(result.dimensions["engagement"], 0.0)
        self.assertNotIn("missed_dialogue_constraint", result.flags)


if __name__ == "__main__":
    unittest.main()
