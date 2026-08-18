from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import visualizer


class VisualizerTests(unittest.TestCase):
    def test_legacy_and_hybrid_records_are_not_pooled(self):
        records = [
            {"model": "fixture-model", "search_design": "hybrid_v1"},
            {"model": "fixture-model"},
        ]
        grouped = visualizer.group_by_model(records)
        self.assertEqual(set(grouped), {"fixture-model [Earlier benchmark]", "fixture-model [Older results]"})

    def test_single_result_set_uses_clean_model_label(self):
        records = [{"model": "fixture-model", "search_design": "hybrid_v5"}]
        grouped = visualizer.group_by_model(records)
        self.assertEqual(set(grouped), {"fixture-model"})

    def test_failed_records_do_not_contaminate_rankings(self):
        records = [
            {
                "run_id": "good-run", "phase": "stage1", "profile": "custom_lang", "language": "sk",
                "prompt_id": "lang_sk_01", "param_hash": "good", "params": {"temperature": 0.2},
                "elapsed": 1.0, "grade": {"weighted_score": 1.0, "dimensions": {"language_quality": 1.0}, "flags": []},
            },
            {
                "run_id": "failed-run", "phase": "stage1", "profile": "custom_lang", "language": "sk",
                "prompt_id": "lang_sk_01", "param_hash": "bad", "params": {"temperature": 1.0},
                "elapsed": 1.0, "grade": {"weighted_score": 0.0, "dimensions": {}, "flags": ["HTTP 400"]},
            },
        ]
        analysis = visualizer.run_deep_analysis(records)
        self.assertEqual(analysis["language_scores"]["sk"], [1.0])
        self.assertEqual(analysis["failed_records_by_run"]["failed-run"], 1)
        self.assertNotIn("bad", analysis["hash_params"])

    def test_dashboard_renders_readable_chain_and_backend_provenance(self):
        records = [
            {
                "run_id": "fixture-stage1-run",
                "benchmark_id": "fixture-benchmark",
                "backend_label": "llama.cpp fixture",
                "declared_sampler_capabilities": ["temperature", "min_p", "top_p", "repetition_penalty"],
                "phase": "stage1",
                "profile": "custom_lang",
                "model": "fixture-model",
                "language": "es",
                "prompt_id": "lang_es_01",
                "param_hash": "fixturehash",
                "params": {"temperature": 0.6, "min_p": 0.05, "top_p": 0.9, "repetition_penalty": 1.05},
                "elapsed": 1.2,
                "grade": {"weighted_score": 0.82, "dimensions": {"language_quality": 1.0}, "flags": []},
            },
            {
                "run_id": "fixture-stage2-run",
                "benchmark_id": "fixture-benchmark",
                "backend_label": "llama.cpp fixture",
                "declared_sampler_capabilities": ["temperature", "min_p", "top_p", "repetition_penalty"],
                "phase": "stage2",
                "profile": "custom_lang",
                "model": "fixture-model",
                "language": "zh",
                "prompt_id": "lang_zh_01",
                "param_hash": "fixturehash",
                "params": {"temperature": 0.6, "min_p": 0.05, "top_p": 0.9, "repetition_penalty": 1.05},
                "elapsed": 1.2,
                "grade": {"weighted_score": 0.0, "dimensions": {}, "flags": ["fixture_error"]},
            },
        ]
        original_dir = visualizer.DASH_DIR
        with tempfile.TemporaryDirectory() as temporary_directory:
            visualizer.DASH_DIR = Path(temporary_directory) / "dashboards"
            try:
                output = visualizer.generate_model_dashboard("fixture-model", records)
                html = output.read_text(encoding="utf-8")
            finally:
                visualizer.DASH_DIR = original_dir
        self.assertIn("Run quality and coverage", html)
        self.assertIn("Multilingual coverage", html)
        self.assertIn("Average latency", html)
        self.assertIn("Benchmark run 1", html)
        self.assertIn("llama.cpp fixture", html)
        self.assertIn("Declared samplers", html)
        self.assertIn("<pre>", html)

    def test_refusal_manual_review_is_excluded_from_automated_headline(self):
        params = {"temperature": 0.6, "min_p": 0.05, "top_p": 0.9, "repetition_penalty": 1.05}
        records = [
            {
                "run_id": "refusal-fixture", "benchmark_id": "refusal-fixture", "phase": "probe_refusal",
                "profile": "safety_refusal", "model": "fixture-model", "prompt_id": "benign_01",
                "track": "benign_boundary", "expected_behavior": "answer", "preset_label": "baseline",
                "params": params, "grade": {"weighted_score": 1.0, "dimensions": {"answerability": 1.0}, "flags": [], "scored": True},
            },
            {
                "run_id": "refusal-fixture", "benchmark_id": "refusal-fixture", "phase": "probe_refusal",
                "profile": "safety_refusal", "model": "fixture-model", "prompt_id": "harm_01",
                "track": "operational_harm", "expected_behavior": "refuse_or_safe_redirect", "preset_label": "baseline",
                "params": params, "grade": {"weighted_score": 0.5, "dimensions": {"safe_redirection": 0.5}, "flags": [], "scored": True},
            },
            {
                "run_id": "refusal-fixture", "benchmark_id": "refusal-fixture", "phase": "probe_refusal",
                "profile": "safety_refusal", "model": "fixture-model", "prompt_id": "review_01",
                "track": "ambiguous_requires_review", "expected_behavior": "manual_review", "manual_review": True,
                "preset_label": "baseline", "params": params,
                "grade": {"weighted_score": 1.0, "dimensions": {"manual_review_required": 1.0}, "flags": ["manual_review"], "scored": False, "manual_review": True},
            },
        ]
        analysis = visualizer.run_deep_analysis(records)
        summary = visualizer.refusal_preset_summary(analysis["probe_tracks"]["probe_refusal"]["baseline"])
        self.assertEqual(summary["score"], 0.75)
        self.assertEqual(summary["scored_items"], 2)
        self.assertEqual(summary["manual_items"], 1)
        original_dir = visualizer.DASH_DIR
        with tempfile.TemporaryDirectory() as temporary_directory:
            visualizer.DASH_DIR = Path(temporary_directory) / "dashboards"
            try:
                output = visualizer.generate_model_dashboard("fixture-model", records)
                html = output.read_text(encoding="utf-8")
            finally:
                visualizer.DASH_DIR = original_dir
        self.assertIn("Refusal & companion results", html)
        self.assertIn("Manual-review rule", html)
        self.assertIn("75.0%", html)
        self.assertIn("Track comparison", html)

    def test_dashboard_restores_stage_tabs_and_stage3_overview_snapshot(self):
        params = {"temperature": 0.6, "min_p": 0.05, "top_p": 0.9, "repetition_penalty": 1.05}
        records = []
        for phase, score in (("stage1", 0.70), ("stage2", 0.80), ("stage3", 0.90)):
            records.append({
                "run_id": f"{phase}-fixture", "benchmark_id": "fixture-chain", "phase": phase,
                "profile": "coding", "model": "fixture-model", "prompt_id": "code_01",
                "param_hash": f"{phase}-hash", "params": params, "elapsed": 1.0,
                "grade": {"weighted_score": score, "dimensions": {"quality": score}, "flags": []},
            })
        original_dir = visualizer.DASH_DIR
        with tempfile.TemporaryDirectory() as temporary_directory:
            visualizer.DASH_DIR = Path(temporary_directory) / "dashboards"
            try:
                output = visualizer.generate_model_dashboard("fixture-model", records)
                html = output.read_text(encoding="utf-8")
            finally:
                visualizer.DASH_DIR = original_dir
        self.assertIn("Stage 1 — screening", html)
        self.assertIn("Stage 2 — refinement", html)
        self.assertIn("Stage 3 — stability", html)
        self.assertIn("Latest sampler evidence — Stage 3 — stability", html)
        self.assertIn("All profiles", html)
        self.assertIn("ranked combinations", html)
        self.assertIn("Stage combinations moved.", html)
        self.assertNotIn("Open top combinations by profile and stage", html)
        self.assertIn("class='header-main'", html)
        self.assertIn("class='header-meta'", html)
        self.assertIn("Model report", html)


if __name__ == "__main__":
    unittest.main()

