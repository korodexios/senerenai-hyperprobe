from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import probe_utils
from probe_niah import build_niah_case, grade_niah_response, normalize_corpus
from probe_refusal import grade_refusal_response, load_refusal_dataset
from probe_utils import BASELINE_PRESET, select_presets
import visualizer


class ProbeTests(unittest.TestCase):
    def test_public_refusal_dataset_is_labeled_and_safe_tracks_are_present(self):
        rows = load_refusal_dataset()
        tracks = {row["track"] for row in rows}
        self.assertIn("benign_boundary", tracks)
        self.assertIn("companion_roleplay", tracks)
        self.assertIn("safe_redirection", tracks)
        self.assertTrue(all(row["expected_behavior"] in {"answer", "refuse_or_safe_redirect"} for row in rows))

    def test_refusal_grader_flags_false_refusal_and_accepts_consent_aware_companion_reply(self):
        benign = {
            "expected_behavior": "answer",
            "required_terms": ["consent"],
        }
        accepted = grade_refusal_response("Consent matters because both adults should communicate clearly and respect boundaries.", benign)
        refused = grade_refusal_response("I cannot help with that request.", benign)
        self.assertEqual(accepted["dimensions"]["answerability"], 1.0)
        self.assertIn("possible_false_refusal", refused["flags"])

    def test_niah_case_inserts_a_unique_retrievable_needle(self):
        corpus = normalize_corpus(("A neutral document sentence with varied wording. " * 4000))
        case = build_niah_case(corpus, context_tokens=256, depth_percent=50, case_id="fixture")
        self.assertIn(case["answer"], case["prompt"])
        self.assertEqual(grade_niah_response(case["answer"], case["answer"])["weighted_score"], 1.0)
        self.assertEqual(grade_niah_response("wrong", case["answer"])["weighted_score"], 0.0)

    def test_select_presets_supports_baseline_manual_and_final(self):
        self.assertEqual(select_presets("baseline", profile="coding", model="demo")[0]["params"], BASELINE_PRESET)
        manual = json.dumps({"temperature": 0.3, "min_p": 0.02, "top_p": 0.95, "repetition_penalty": 1.04})
        self.assertEqual(select_presets("manual", profile="coding", model="demo", manual_preset=manual)[0]["params"]["temperature"], 0.3)
        original_results = probe_utils.RESULTS_DIR
        with tempfile.TemporaryDirectory() as directory:
            probe_utils.RESULTS_DIR = Path(directory)
            path = probe_utils.final_preset_path("roleplay", "demo")
            path.write_text(json.dumps({"sampling_parameters": BASELINE_PRESET, "benchmark_id": "fixture"}), encoding="utf-8")
            final = select_presets("final", profile="roleplay", model="demo")
        probe_utils.RESULTS_DIR = original_results
        self.assertEqual(final[0]["benchmark_id"], "fixture")

    def test_refusal_runner_writes_isolated_probe_records_with_mocked_responses(self):
        import probe_refusal
        original_batch, original_append, original_save = probe_refusal.run_batch, probe_refusal.append_jsonl, probe_refusal.save_probe_summary
        captured = []
        def fake_batch(model, jobs, **kwargs):
            return [{**job, "result": {"reply": "Consent and respect matter in every conversation.", "tokens": 4}, "elapsed": 0.1} for job in jobs]
        probe_refusal.run_batch = fake_batch
        probe_refusal.append_jsonl = lambda phase, profile, model, record: captured.append((phase, profile, record))
        probe_refusal.save_probe_summary = lambda mode, model, probe_id, payload: Path("/tmp/fake-refusal-summary.json")
        try:
            summary = probe_refusal.run_refusal_probe(
                model="fixture", preset_rows=[{"label": "baseline", "params": BASELINE_PRESET, "source": "test", "param_hash": "fixture"}], samples=1,
            )
        finally:
            probe_refusal.run_batch, probe_refusal.append_jsonl, probe_refusal.save_probe_summary = original_batch, original_append, original_save
        self.assertEqual(summary["summary"]["attempted_calls"], len(captured))
        self.assertTrue(captured)
        self.assertEqual(captured[0][0], "probe_refusal")
        self.assertEqual(captured[0][1], "safety_refusal")

    def test_niah_runner_writes_isolated_probe_records_with_mocked_exact_retrieval(self):
        import probe_niah
        original_batch, original_append, original_save = probe_niah.run_batch, probe_niah.append_jsonl, probe_niah.save_probe_summary
        captured = []
        def fake_batch(model, jobs, **kwargs):
            return [{**job, "result": {"reply": job["case"]["answer"], "tokens": 2, "prompt_tokens": 256}, "elapsed": 0.1} for job in jobs]
        probe_niah.run_batch = fake_batch
        probe_niah.append_jsonl = lambda phase, profile, model, record: captured.append((phase, profile, record))
        probe_niah.save_probe_summary = lambda mode, model, probe_id, payload: Path("/tmp/fake-niah-summary.json")
        try:
            with tempfile.TemporaryDirectory() as directory:
                corpus = Path(directory) / "corpus.txt"
                corpus.write_text("A neutral factual sentence for retrieval testing. " * 4000, encoding="utf-8")
                summary = probe_niah.run_niah_probe(
                    model="fixture", preset_rows=[{"label": "baseline", "params": BASELINE_PRESET, "source": "test", "param_hash": "fixture"}],
                    corpus_path=corpus, context_sizes=(256,), depths=(50,), samples=1,
                )
        finally:
            probe_niah.run_batch, probe_niah.append_jsonl, probe_niah.save_probe_summary = original_batch, original_append, original_save
        self.assertEqual(summary["summary"]["attempted_calls"], 1)
        self.assertEqual(captured[0][0], "probe_niah")
        self.assertEqual(captured[0][2]["server_prompt_tokens"], 256)

    def test_probe_scores_are_available_but_do_not_change_core_preset_pooling(self):
        records = [
            {
                "run_id": "probe", "benchmark_id": "probe", "phase": "probe_refusal", "profile": "safety_refusal",
                "model": "fixture", "preset_label": "baseline", "track": "benign_boundary", "param_hash": "p", "params": BASELINE_PRESET,
                "grade": {"weighted_score": 1.0, "dimensions": {"answerability": 1.0}, "flags": []}, "elapsed": 1.0,
            }
        ]
        analysis = visualizer.run_deep_analysis(records)
        self.assertIn("probe_refusal", analysis["probe_scores"])
        self.assertEqual(visualizer.generate_specialized_presets(analysis), [])


if __name__ == "__main__":
    unittest.main()
