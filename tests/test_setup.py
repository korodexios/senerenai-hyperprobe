"""Offline tests for numbered setup selections."""
from __future__ import annotations

import builtins
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

from settings import DEFAULT_SETTINGS, PROFILE_CHOICES

SETUP_PATH = Path(__file__).resolve().parents[1] / "01_setup.py"
SPEC = importlib.util.spec_from_file_location("hyperprobe_setup", SETUP_PATH)
setup = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def test_profile_option_six_selects_every_profile(self):
        settings = dict(DEFAULT_SETTINGS)
        with patch.object(builtins, "input", return_value="6"):
            setup.choose_profiles(settings)
        self.assertEqual(settings["default_profiles"], list(PROFILE_CHOICES))

    def test_language_grid_accepts_multiple_numbers_and_cz_alias(self):
        settings = {"default_languages": [], "default_language": ""}
        with patch.object(builtins, "input", return_value="1,cz,18"):
            setup.choose_languages(settings)
        self.assertEqual(settings["default_languages"], ["en", "cs", "sk"])
        self.assertEqual(settings["default_language"], "")

    def test_language_option_nineteen_means_all_languages(self):
        settings = {"default_languages": ["es"], "default_language": "es"}
        with patch.object(builtins, "input", return_value="19"):
            setup.choose_languages(settings)
        self.assertEqual(settings["default_languages"], [])
        self.assertEqual(settings["default_language"], "")


if __name__ == "__main__":
    unittest.main()
