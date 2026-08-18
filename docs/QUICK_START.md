# Quick Start

This page is for a first-time user who wants the shortest reliable path from a fresh checkout to a completed benchmark.

## 1. Check the project directory

Every command below must be run inside the project directory:

```bash
cd senerenai-hyperprobe
python3 --version
```

Use Python 3.10 or newer. A virtual environment is optional. If you use `uv`, create and activate an environment in the normal way for your system; HyperProbe does not require a special environment manager.

## 2. Configure the main sampler benchmark once

Run:

```bash
python3 01_configure_sampler_benchmark.py
```

Enter the API base, authorization value, and exact model ID accepted by your server. The wizard then asks which benchmark profiles and workflow should be used. For a first complete run, a practical selection is:

| Choice | Suggested value |
|---|---|
| Profiles | `coding, agent_tools, creative, roleplay`, or `6` for all profiles |
| Languages | Keep all languages unless you specifically need `custom_lang` only |
| Workflow | `full` |
| Timeout | `180` seconds |
| Concurrency | `1` unless the server has multiple reliable slots |
| Stage 1 samples | `2` for a quality-oriented run; `1` for a smoke test |
| Stage 2 samples | `1` |
| Stage 2 maximum combinations | `5` |
| Stage 3 samples | `1` |
| Stage 3 top candidates | `2` |

The wizard remembers the last saved values. When it displays a saved value, pressing **Enter** keeps it. You only need to use `--edit` when you want to review or change the main settings.

## 3. Run the sampler benchmark

After saving the main settings, run:

```bash
python3 02_run_sampler_benchmark.py
```

With no flags, the launcher uses the saved profiles, languages, model, workflow, timeout, and stage defaults. It should not ask you to enter them again.

You can also run stages separately:

```bash
python3 02_run_sampler_benchmark.py --workflow stage1
python3 02_run_sampler_benchmark.py --workflow stage2
python3 02_run_sampler_benchmark.py --workflow stage3
```

Running the stages on different days is supported. The result metadata links later stages to the earlier benchmark chain.

## 4. Configure the additional benchmarks, if wanted

Run:

```bash
python3 03_configure_additional_benchmarks.py
```

For a full private refusal run using a discovered local JSONL file, the choices are:

```text
Additional benchmarks: 1 — Refusal & companion
Sampler presets: 1 — Baseline, or 3 — Compare if Stage 3 results already exist
Refusal benchmark size: 2 — Full
Refusal dataset: choose datasets/local/uncensored-test-dataset.jsonl by number
Refusal samples: 1 sample for a first verification run; 2 for a more stable run
```

The wizard should list every `.jsonl` file found in `datasets/refusal/` and `datasets/local/`. You normally select the file by number rather than typing its path.

Then run:

```bash
python3 04_run_additional_benchmarks.py
```

## 5. Understand the model error

If the runner prints:

```text
No saved model ID. Run 'python3 01_configure_sampler_benchmark.py --edit' first.
```

run the requested command in the **same project directory**:

```bash
python3 01_configure_sampler_benchmark.py --edit
```

Save the API base, API key, and model ID. The additional benchmark settings are not lost; they remain in `hyperprobe.probes.local.json`. The runner needs the main model settings because both workflows use the same model connection.

## 6. Check the output

Results normally appear in:

```text
results/stages/
results/probes/
results/dashboards/
```

Open the generated `results/dashboards/index.html` in a browser. If you only need to rebuild the dashboard from existing result records:

```bash
python3 02_run_sampler_benchmark.py --workflow dashboard
```

## 7. Fast verification versus a serious run

A fast verification checks wiring, paths, schema, and server compatibility. Use one profile, one sample, and a small refusal run if available. A serious run uses the intended profiles, the complete Stage 1–3 workflow, and the desired Full refusal dataset or NIAH matrix.

Do not confuse a successful fast verification with a statistically stable benchmark. The fast run is only a transport and configuration check.
