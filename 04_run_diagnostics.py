"""Legacy compatibility launcher for the additional-benchmark runner.

Use 04_run_additional_benchmarks.py for new work.
"""
from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == "__main__":
    target = Path(__file__).with_name("04_run_additional_benchmarks.py")
    runpy.run_path(str(target), run_name="__main__")
