"""Offline tests for the numbered multi-profile launcher."""
from __future__ import annotations

import builtins
import importlib.util
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

from settings import DEFAULT_SETTINGS


LAUNCHER_PATH = Path(__file__).resolve().parents[1] / "02_run.py"
SPEC = importlib.util.spec_from_file_location("hyperprobe_launcher", LAUNCHER_PATH)
launcher = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(launcher)


class _FakeVisualizer:
    def __init__(self, calls: list):
        self.calls = calls

    def main(self):
        self.calls.append(("dashboard",))


class LauncherTests(unittest.TestCase):
    def test_full_pipeline_runs_for_every_selected_profile(self):
        calls: list[tuple] = []

        def fake_stage1(profile, model, **kwargs):
            calls.append(("stage1", profile, model, kwargs.get("language")))
            return {
                "suggested_ranges": {"temperature": [0.2, 0.6]},
                "top_combos": [{"params": {"temperature": 0.4, "min_p": 0.05, "top_p": 0.9, "repetition_penalty": 1.05}}],
            }

        def fake_stage2(profile, model, ranges, **kwargs):
            calls.append(("stage2", profile, model, ranges.get("_base", {}).get("temperature")))
            return {"top_combos": [{"params": {"temperature": 0.4, "min_p": 0.05, "top_p": 0.9, "repetition_penalty": 1.05}}]}

        def fake_stage3(profile, model, top_combos, **kwargs):
            calls.append(("stage3", profile, model, len(top_combos)))
            return {"ranked": []}

        original_loader = launcher.load_runtime_modules
        launcher.load_runtime_modules = lambda: {
            "load_stage": lambda *args, **kwargs: {},
            "run_stage1": fake_stage1,
            "run_stage2": fake_stage2,
            "run_stage3": fake_stage3,
            "visualizer": _FakeVisualizer(calls),
        }
        try:
            settings = dict(DEFAULT_SETTINGS)
            launcher.run_selected(
                profiles=["creative", "roleplay"], model="demo", workflow="full",
                settings=settings, languages=[], think=False,
            )
        finally:
            launcher.load_runtime_modules = original_loader

        self.assertEqual([call[:2] for call in calls[:6]], [
            ("stage1", "creative"), ("stage2", "creative"), ("stage3", "creative"),
            ("stage1", "roleplay"), ("stage2", "roleplay"), ("stage3", "roleplay"),
        ])
        self.assertEqual(calls[-1], ("dashboard",))


    def test_full_pipeline_runs_each_saved_custom_language(self):
        calls: list[tuple] = []

        def fake_stage1(profile, model, **kwargs):
            calls.append(("stage1", kwargs.get("language")))
            return {"suggested_ranges": {"temperature": [0.2, 0.6]}, "top_combos": [{"params": {"temperature": 0.4}}]}

        def fake_stage2(profile, model, ranges, **kwargs):
            calls.append(("stage2", kwargs.get("language")))
            return {"top_combos": [{"params": {"temperature": 0.4}}]}

        def fake_stage3(profile, model, top_combos, **kwargs):
            calls.append(("stage3", kwargs.get("language")))
            return {"ranked": []}

        original_loader = launcher.load_runtime_modules
        launcher.load_runtime_modules = lambda: {
            "load_stage": lambda *args, **kwargs: {},
            "run_stage1": fake_stage1,
            "run_stage2": fake_stage2,
            "run_stage3": fake_stage3,
            "visualizer": _FakeVisualizer(calls),
        }
        try:
            launcher.run_selected(
                profiles=["custom_lang"], model="demo", workflow="full",
                settings=dict(DEFAULT_SETTINGS), languages=["es", "sk"], think=False,
            )
        finally:
            launcher.load_runtime_modules = original_loader

        self.assertEqual(calls[:6], [
            ("stage1", "es"), ("stage2", "es"), ("stage3", "es"),
            ("stage1", "sk"), ("stage2", "sk"), ("stage3", "sk"),
        ])
        self.assertEqual(calls[-1], ("dashboard",))


    def test_main_uses_saved_configuration_without_prompting(self):
        captured: dict = {}
        settings = dict(DEFAULT_SETTINGS)
        settings.update({
            "model": "saved-model",
            "default_profiles": ["creative", "custom_lang"],
            "default_languages": ["es", "sk"],
            "default_workflow": "full",
        })
        original_settings = launcher.load_settings
        original_run = launcher.run_selected
        launcher.load_settings = lambda: settings
        launcher.run_selected = lambda **kwargs: captured.update(kwargs)
        try:
            with patch.object(sys, "argv", ["02_run.py"]), patch.object(
                builtins, "input", side_effect=AssertionError("zero-prompt mode must not call input")
            ):
                launcher.main()
        finally:
            launcher.load_settings = original_settings
            launcher.run_selected = original_run

        self.assertEqual(captured["profiles"], ["creative", "custom_lang"])
        self.assertEqual(captured["model"], "saved-model")
        self.assertEqual(captured["workflow"], "full")
        self.assertEqual(captured["languages"], ["es", "sk"])


if __name__ == "__main__":
    unittest.main()
