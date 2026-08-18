"""Legacy compatibility adapter for the main sampler-benchmark settings wizard.

Use 01_configure_sampler_benchmark.py for new work.  The canonical module is
loaded here so older integrations that import helper functions continue to work.
"""
from __future__ import annotations

import runpy
from pathlib import Path


_target = Path(__file__).with_name("01_configure_sampler_benchmark.py")
_namespace = runpy.run_path(str(_target), run_name="senerenai_hyperprobe_legacy_setup")
for _name, _value in _namespace.items():
    if not (_name.startswith("__") and _name.endswith("__")):
        globals()[_name] = _value


if __name__ == "__main__":
    main()
