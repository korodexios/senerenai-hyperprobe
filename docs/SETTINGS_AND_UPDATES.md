# Settings, Inheritance, and Safe Updates

## Why there are two settings files

HyperProbe contains two workflows with different responsibilities. Keeping their settings separate prevents a refusal dataset choice from changing the sampler-tuning design, and prevents sampler-stage edits from rewriting probe choices.

| File | Owner | Main contents |
|---|---|---|
| `hyperprobe.local.json` | Sampler Benchmark | API base, API key, model ID, backend label, profiles, languages, runtime defaults, and Stage 1–3 defaults. |
| `hyperprobe.probes.local.json` | Additional Benchmarks | Enabled probe modes, baseline/final/compare/manual preset mode, refusal dataset and Quick/Full mode, NIAH corpus and matrix, probe samples, timeout, thinking mode, and dashboard regeneration. |

Both files are local configuration. Both are ignored by Git. Neither belongs in a public GitHub commit.

## What is shared

The Additional Benchmark runner loads the model connection from `hyperprobe.local.json`. It reuses the API base, authorization value, model ID, timeout, thinking mode, backend label, and sampler capability information. Probe-specific choices come from `hyperprobe.probes.local.json`.

This design means that Additional Benchmarks do not ask for the API address and model again. It also means that a probe settings file by itself is not sufficient to run a benchmark. The main settings must contain a model ID.

> If `04_run_additional_benchmarks.py` reports `No saved model ID`, run `python3 01_configure_sampler_benchmark.py --edit` in the same project directory and save the model connection.

## Saved values and developer defaults

The main wizard displays both the current saved value and the developer default. Pressing **Enter** keeps the saved value; it does not reset it to the developer default.

The additional wizard follows the same principle for numbered choices. A `[saved]` marker identifies the value that will be used if you press Enter.

This distinction matters when tuning a project over several days. You can update the code while preserving the user’s local choices, and you can change one choice without retyping all other settings.

## Inspect and edit settings

Use the main wizard to inspect or edit the main settings:

```bash
python3 01_configure_sampler_benchmark.py --show
python3 01_configure_sampler_benchmark.py --edit
```

Use the additional wizard to inspect and edit probe settings:

```bash
python3 03_configure_additional_benchmarks.py
```

The API key is masked in the main settings summary. Do not paste the complete local JSON files into public issue reports.

## Safe project replacement

A common source of confusion is copying a fresh project directory over an existing working directory. If the copy contains a new or empty `hyperprobe.local.json`, it can appear as though the server address, API key, or model disappeared. The same problem can happen to the probe settings file and local datasets.

Before replacing project files, make a private backup:

```bash
mkdir -p ../senerenai-hyperprobe-backup
cp -p hyperprobe.local.json ../senerenai-hyperprobe-backup/ 2>/dev/null || true
cp -p hyperprobe.probes.local.json ../senerenai-hyperprobe-backup/ 2>/dev/null || true
cp -a datasets/local ../senerenai-hyperprobe-backup/ 2>/dev/null || true
cp -a datasets/niah ../senerenai-hyperprobe-backup/ 2>/dev/null || true
cp -a results ../senerenai-hyperprobe-backup/ 2>/dev/null || true
```

Then update the tracked project code while preserving the local material. With Git, the safest normal workflow is:

```bash
git pull --ff-only
```

If you are copying files from an archive, extract the public project into a new directory first. Copy only the tracked source and documentation files into the working checkout, and then restore the backed-up local files if they are missing. Do not replace local settings or local datasets with empty template files.

After an update, verify:

```bash
python3 01_configure_sampler_benchmark.py --show
python3 -c 'import json; from pathlib import Path; p=Path("datasets/local/uncensored-test-dataset.jsonl"); rows=[json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]; print(len(rows), rows[0]["id"], rows[-1]["id"])'
```

## Environment-variable overrides

Environment variables are useful for CI, containers, or a temporary run. They take precedence over saved connection values for the process that launches the benchmark:

```bash
export HYPERPROBE_API_BASE="http://localhost:8080/v1"
export HYPERPROBE_API_KEY="Bearer your-token"
export HYPERPROBE_TIMEOUT="180"
python3 02_run_sampler_benchmark.py
```

Treat shell history and CI logs as sensitive when using API keys. Never commit secrets, private datasets, model outputs containing personal information, or endpoint URLs that should remain private.
