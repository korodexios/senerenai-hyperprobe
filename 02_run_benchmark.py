"""Legacy compatibility launcher for the sampler-benchmark runner.

Use 02_run_sampler_benchmark.py for new work.
"""
from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == "__main__":
    target = Path(__file__).with_name("02_run_sampler_benchmark.py")
    runpy.run_path(str(target), run_name="__main__")
