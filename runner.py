"""Compatibility launcher for Senerenai-HyperProbe's numbered workflow.

For new users, run `python3 01_setup.py` once and then `python3 02_run.py`.
This file remains so existing references to `runner.py` continue to open the
current public launcher instead of an outdated separate sweep engine.
"""
from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    """Run the interactive multi-profile launcher."""
    runpy.run_path(str(Path(__file__).with_name("02_run.py")), run_name="__main__")


if __name__ == "__main__":
    main()
