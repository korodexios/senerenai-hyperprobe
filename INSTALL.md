# Senerenai-HyperProbe v1.11.11 Header Polish

Replace only visualizer.py, tests/test_visualizer.py, docs/RESULTS_AND_DASHBOARD.md, changelog.md, and pyproject.toml. Keep hyperprobe.local.json, hyperprobe.probes.local.json, datasets/local/, datasets/niah/, and results/ unchanged.

Regenerate the dashboard without model calls:

    python3 02_run_sampler_benchmark.py --workflow dashboard

Verify:

    python3 -m unittest tests.test_visualizer
