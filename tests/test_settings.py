"""Offline tests for the persistent setup and multi-profile workflow helpers."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from probe_settings import DEFAULT_PROBE_SETTINGS, load_probe_settings, save_probe_settings, validate_probe_settings
from settings import (
    DEFAULT_SETTINGS,
    normalize_language_code,
    load_settings,
    parse_selection,
    save_settings,
    settings_environment,
    validate_settings,
)


class SettingsTests(unittest.TestCase):
    def test_missing_file_uses_public_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = load_settings(Path(directory) / "missing.json")
        self.assertEqual(settings["api_base"], DEFAULT_SETTINGS["api_base"])
        self.assertEqual(settings["default_profiles"], ["coding"])

    def test_settings_round_trip_and_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "local.json"
            saved = dict(DEFAULT_SETTINGS)
            saved.update({"api_base": "http://example.test/v1", "model": "demo", "default_profiles": ["creative", "roleplay"]})
            save_settings(saved, path)
            loaded = load_settings(path)
        self.assertEqual(loaded["api_base"], "http://example.test/v1")
        self.assertEqual(loaded["model"], "demo")
        self.assertEqual(loaded["default_profiles"], ["creative", "roleplay"])

    def test_invalid_settings_are_rejected(self):
        bad = dict(DEFAULT_SETTINGS)
        bad["api_base"] = "localhost:8080"
        bad["timeout"] = 0
        errors = validate_settings(bad)
        self.assertTrue(any("api_base" in error for error in errors))
        self.assertTrue(any("timeout" in error for error in errors))

    def test_multi_profile_selection_accepts_indexes_names_and_all(self):
        options = ["coding", "agent_tools", "creative", "roleplay"]
        self.assertEqual(parse_selection("1, creative, 4", options), ["coding", "creative", "roleplay"])
        self.assertEqual(parse_selection("all", options), options)
        with self.assertRaises(ValueError):
            parse_selection("99", options)

    def test_saved_workflow_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "local.json"
            saved = dict(DEFAULT_SETTINGS)
            saved["default_workflow"] = "stage2"
            save_settings(saved, path)
            loaded = load_settings(path)
        self.assertEqual(loaded["default_workflow"], "stage2")

    def test_saved_languages_round_trip_and_aliases(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "local.json"
            saved = dict(DEFAULT_SETTINGS)
            saved.update({"default_profiles": ["custom_lang"], "default_languages": ["es", "cz", "sk"]})
            save_settings(saved, path)
            loaded = load_settings(path)
        self.assertEqual(loaded["default_languages"], ["es", "cs", "sk"])
        self.assertEqual(normalize_language_code("cz"), "cs")

    def test_environment_contains_saved_runtime_values(self):
        settings = dict(DEFAULT_SETTINGS)
        settings.update({
            "api_base": "http://example.test/v1",
            "api_key": "Bearer secret",
            "timeout": 42,
            "backend_label": "llama.cpp b5000",
        })
        environment = settings_environment(settings)
        self.assertEqual(environment["HYPERPROBE_API_BASE"], "http://example.test/v1")
        self.assertEqual(environment["HYPERPROBE_TIMEOUT"], "42")
        self.assertEqual(environment["HYPERPROBE_API_KEY"], "Bearer secret")
        self.assertEqual(environment["HYPERPROBE_BACKEND_LABEL"], "llama.cpp b5000")
        self.assertEqual(environment["HYPERPROBE_SAMPLER_CAPABILITIES"], "temperature,min_p,top_p,repetition_penalty")

    def test_backend_provenance_and_capabilities_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "local.json"
            saved = dict(DEFAULT_SETTINGS)
            saved.update({
                "backend_label": "vLLM 0.8",
                "sampler_capabilities": ["temperature", "min_p", "top_p", "top_k", "repetition_penalty"],
            })
            save_settings(saved, path)
            loaded = load_settings(path)
        self.assertEqual(loaded["backend_label"], "vLLM 0.8")
        self.assertIn("top_k", loaded["sampler_capabilities"])

    def test_probe_settings_round_trip_and_niah_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probes.json"
            saved = dict(DEFAULT_PROBE_SETTINGS)
            saved.update({"enabled_modes": ["refusal", "niah"], "niah_corpus": "corpus.txt", "niah_context_sizes": [4000, 16000]})
            save_probe_settings(saved, path)
            loaded = load_probe_settings(path)
        self.assertEqual(loaded["enabled_modes"], ["refusal", "niah"])
        self.assertEqual(loaded["niah_context_sizes"], [4000, 16000])
        invalid = dict(DEFAULT_PROBE_SETTINGS)
        invalid["enabled_modes"] = ["niah"]
        invalid["niah_corpus"] = ""
        self.assertTrue(any("niah_corpus" in error for error in validate_probe_settings(invalid)))

    def test_capabilities_require_the_core_benchmark_parameters(self):
        settings = dict(DEFAULT_SETTINGS)
        settings["sampler_capabilities"] = ["temperature", "top_p"]
        errors = validate_settings(settings)
        self.assertTrue(any("four core" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
