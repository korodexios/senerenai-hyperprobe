"""Offline visualizer tests using in-memory benchmark records."""
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
        self.assertEqual(set(grouped), {"fixture-model [hybrid_v1]", "fixture-model [legacy]"})

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

    def test_dashboard_renders_run_quality_and_multilingual_panels(self):
        records = [
            {
                "run_id": "fixture-run-001",
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
                "run_id": "fixture-run-001",
                "phase": "stage1",
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
        self.assertIn("<pre>", html)


if __name__ == "__main__":
    unittest.main()
