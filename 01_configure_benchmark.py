"""Legacy compatibility launcher for the main sampler-benchmark settings wizard.

Use 01_configure_sampler_benchmark.py for new work.
"""
from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == "__main__":
    target = Path(__file__).with_name("01_configure_sampler_benchmark.py")
    runpy.run_path(str(target), run_name="__main__")
