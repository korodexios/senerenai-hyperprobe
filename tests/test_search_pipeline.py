"""Offline integration test for the interpretable sampling-search handoff."""
from __future__ import annotations

import unittest

import stage1_coarse
import stage2_refine
import stage3_finest


class SearchPipelineTests(unittest.TestCase):
    def test_interpretable_handoff_drives_targeted_full_pipeline(self):
        originals = {
            "stage1_run_batch": stage1_coarse.run_batch,
            "stage1_append": stage1_coarse.append_jsonl,
            "stage1_save": stage1_coarse.save_stage,
            "stage2_run_batch": stage2_refine.run_batch,
            "stage2_append": stage2_refine.append_jsonl,
            "stage2_save": stage2_refine.save_stage,
            "stage3_run_batch": stage3_finest.run_batch,
            "stage3_append": stage3_finest.append_jsonl,
            "stage3_save": stage3_finest.save_stage,
        }

        def fake_batch(_model, jobs, **_kwargs):
            return [
                {
                    **job,
                    "result": {"reply": "Toto je správna slovenská veta s diakritikou a prirodzeným slovosledom."},
                    "elapsed": 0.01,
                }
                for job in jobs
            ]

        try:
            stage1_coarse.run_batch = fake_batch
            stage2_refine.run_batch = fake_batch
            stage3_finest.run_batch = fake_batch
            stage1_coarse.append_jsonl = lambda *_args, **_kwargs: None
            stage2_refine.append_jsonl = lambda *_args, **_kwargs: None
            stage3_finest.append_jsonl = lambda *_args, **_kwargs: None
            stage1_coarse.save_stage = lambda *_args, **_kwargs: None
            stage2_refine.save_stage = lambda *_args, **_kwargs: None
            stage3_finest.save_stage = lambda *_args, **_kwargs: None

            stage1 = stage1_coarse.run_stage1("custom_lang", "fixture", n_samples=1, language="sk")
            self.assertEqual(stage1["design"]["combination_count"], 33)
            self.assertIn("main_effects", stage1)
            self.assertIn("interaction_evidence", stage1)

            stage2 = stage2_refine.run_stage2(
                "custom_lang",
                "fixture",
                stage1["suggested_ranges"],
                n_samples=1,
                max_combos=8,
                language="sk",
                stage1_evidence=stage1,
            )
            self.assertEqual(stage2["search_strategy"]["mode"], "targeted_interaction_refinement")
            self.assertGreaterEqual(len(stage2["top_combos"]), 1)

            stage3 = stage3_finest.run_stage3(
                "custom_lang",
                "fixture",
                stage2["top_combos"],
                n_samples=1,
                top_n=1,
                language="sk",
                primary_pair=stage2["search_strategy"]["primary_interaction"],
            )
            self.assertGreaterEqual(len(stage3["ranked"]), 1)
        finally:
            stage1_coarse.run_batch = originals["stage1_run_batch"]
            stage1_coarse.append_jsonl = originals["stage1_append"]
            stage1_coarse.save_stage = originals["stage1_save"]
            stage2_refine.run_batch = originals["stage2_run_batch"]
            stage2_refine.append_jsonl = originals["stage2_append"]
            stage2_refine.save_stage = originals["stage2_save"]
            stage3_finest.run_batch = originals["stage3_run_batch"]
            stage3_finest.append_jsonl = originals["stage3_append"]
            stage3_finest.save_stage = originals["stage3_save"]


if __name__ == "__main__":
    unittest.main()
