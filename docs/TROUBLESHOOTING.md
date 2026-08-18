# Troubleshooting

## `No saved model ID`

The Additional Benchmark runner intentionally reads the model from the main settings file. Fix it from the project directory:

```bash
python3 01_configure_sampler_benchmark.py --edit
```

Save the API base, API key, and model ID. Then run:

```bash
python3 04_run_additional_benchmarks.py
```

Do not recreate the probe dataset settings unless the probe file itself is missing.

## The API address disappeared after copying files

This usually means a new `hyperprobe.local.json` replaced the old local file, or the command is being run from a different checkout. Check the current directory and inspect the saved summary:

```bash
pwd
python3 01_configure_sampler_benchmark.py --show
```

If the model is missing, use `--edit` and save it again. For future updates, preserve both local JSON files and use the procedure in [`SETTINGS_AND_UPDATES.md`](SETTINGS_AND_UPDATES.md).

## The Full option is not visible

The Full/Quick choice appears only when the Refusal benchmark is enabled. In `03_configure_additional_benchmarks.py`, first select:

```text
1. Refusal & companion benchmark
```

or:

```text
3. Both benchmarks
```

Then the wizard displays **Refusal benchmark size**, where `2` is Full. NIAH-only runs do not display refusal settings.

## The private JSONL file is not listed

The wizard searches:

```text
datasets/refusal/*.jsonl
datasets/local/*.jsonl
```

Confirm the file is in one of those directories and has a `.jsonl` extension:

```bash
ls -la datasets/refusal datasets/local
```

If it is stored elsewhere, use the advanced “Type a different JSONL path” option. Relative paths are resolved from the project root.

## `wc -l` shows 167 but the dataset contains 168 objects

`wc -l` counts newline characters. A final JSON object without a trailing newline causes the count to be one lower. Count parsed objects instead:

```bash
python3 -c 'import json; from pathlib import Path; rows=[json.loads(x) for x in Path("datasets/local/uncensored-test-dataset.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]; print(len(rows))'
```

If it prints `168`, the dataset contains 168 valid records. A trailing newline may be added without changing the JSON content:

```bash
printf '\n' >> datasets/local/uncensored-test-dataset.jsonl
```

Only do this when you have confirmed the file does not already end with a newline.

## The runner takes a long time without printing a line

A request can take up to the configured per-request timeout, and some backends do not stream progress while a completion is being generated. Check the initial planned-call count before stopping the process. For a first compatibility check, use one profile, one sample, Baseline, and the smallest practical matrix.

Do not raise concurrency automatically. A higher value can overload a local model server and create more errors rather than reducing elapsed time.

## Stage 2 or Stage 3 cannot find earlier results

Run the stages from the same project directory and preserve `results/`. Stage 2 depends on Stage 1 evidence, and Stage 3 depends on Stage 2 candidates. If results were deleted, the missing stage must be rerun. A new Stage 1 creates a new benchmark chain; it does not reconstruct deleted evidence.

## Dashboard looks incomplete or contains old runs

The dashboard reads available local records. Old records can remain if `results/` was not cleared. This is useful for history but can be confusing. Inspect the model/profile labels and benchmark chain metadata before comparing runs. To regenerate without model calls:

```bash
python3 02_run_sampler_benchmark.py --workflow dashboard
```

## Request errors

Check the API base, authorization value, model ID, server availability, context limit, timeout, and sampler capability configuration. The benchmark records failed requests so they can be investigated; errors should not be treated as successful model quality results.
