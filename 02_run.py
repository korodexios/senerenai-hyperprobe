"""Legacy compatibility adapter for the sampler-benchmark runner.

Use 02_run_sampler_benchmark.py for new work.  The canonical source is executed
in this module namespace so existing integrations can still import and patch its
legacy helper functions without maintaining a second implementation.
"""
from __future__ import annotations

from pathlib import Path


_target = Path(__file__).with_name("02_run_sampler_benchmark.py")
_original_name = __name__
globals()["__name__"] = "senerenai_hyperprobe_legacy_runner"
exec(compile(_target.read_text(encoding="utf-8"), str(_target), "exec"), globals())
globals()["__name__"] = _original_name


if __name__ == "__main__":
    main()
