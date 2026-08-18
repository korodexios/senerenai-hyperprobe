# Senerenai-HyperProbe

**Senerenai-HyperProbe** is a provider-neutral benchmark and sampler-tuning tool for language models exposed through an OpenAI-compatible API. It helps you compare sampling settings for coding, tool use, creative writing, roleplay, and multilingual prompts.

The project has two independent workflows:

| Workflow | What it does | Configure | Run |
|---|---|---|---|
| **Sampler Benchmark** | Finds and validates useful `temperature`, `min_p`, `top_p`, and `repetition_penalty` settings through Stage 1–3. | `python3 01_configure_sampler_benchmark.py` | `python3 02_run_sampler_benchmark.py` |
| **Additional Benchmarks** | Measures refusal/companion behavior and NIAH long-context retrieval. | `python3 03_configure_additional_benchmarks.py` | `python3 04_run_additional_benchmarks.py` |

## Start here

Run these commands from the project directory:

```bash
git clone https://github.com/korodexios/senerenai-hyperprobe.git
cd senerenai-hyperprobe
python3 --version
python3 01_configure_sampler_benchmark.py
python3 02_run_sampler_benchmark.py
```

Python **3.10 or newer** is required. The project uses the Python standard library for its core runtime; a virtual environment or `uv` is optional.

The first wizard saves the API address, authorization value, model ID, profiles, language choices, runtime defaults, and Stage 1–3 workflow defaults. After that, the normal runner should ask no further questions.

## If you want the additional benchmarks

Configure them separately:

```bash
python3 03_configure_additional_benchmarks.py
python3 04_run_additional_benchmarks.py
```

The additional wizard saves its own dataset and probe choices. It **reuses the API base, API key, model ID, timeout, thinking mode, and backend information from the main sampler settings**. Therefore, configure the main sampler settings first, even if you only plan to run refusal or NIAH tests.

For a private extended refusal dataset, select **Full**, then select the numbered file under `datasets/local/`. For example:

```text
Refusal benchmark size: 2. Full
Refusal dataset: datasets/local/uncensored-test-dataset.jsonl
```

## The two settings files

| File | Contains | Git status |
|---|---|---|
| `hyperprobe.local.json` | API endpoint, API key, model ID, sampler workflow, profiles, languages, and runtime defaults. | Ignored; never commit it. |
| `hyperprobe.probes.local.json` | Refusal/NIAH mode, dataset paths, preset selection, samples, and probe-specific options. | Ignored; never commit it. |

Do not replace the whole project directory by copying over local files blindly. When updating the code, preserve both local settings files, `datasets/local/`, `datasets/niah/`, and `results/`. See [`docs/SETTINGS_AND_UPDATES.md`](docs/SETTINGS_AND_UPDATES.md).

## Where to find help

| Need | Read |
|---|---|
| First run and common commands | [`docs/QUICK_START.md`](docs/QUICK_START.md) |
| What every setting means | [`docs/SETTINGS_AND_WORKFLOWS.md`](docs/SETTINGS_AND_WORKFLOWS.md) |
| Updating the project without losing settings or results | [`docs/SETTINGS_AND_UPDATES.md`](docs/SETTINGS_AND_UPDATES.md) |
| Refusal dataset format and Quick/Full modes | [`docs/REFUSAL_DATASETS.md`](docs/REFUSAL_DATASETS.md) |
| NIAH corpus preparation | [`docs/NIAH.md`](docs/NIAH.md) |
| Stage 1–3 design, calls, and handoffs | [`docs/SAMPLER_BENCHMARK.md`](docs/SAMPLER_BENCHMARK.md) |
| Dashboard and result interpretation | [`docs/RESULTS_AND_DASHBOARD.md`](docs/RESULTS_AND_DASHBOARD.md) |
| Prompt for asking another LLM for project-aware help | [`docs/LLM_SUPPORT_PROMPT.md`](docs/LLM_SUPPORT_PROMPT.md) |
| Contributing and safe bug reports | [`contributing.md`](contributing.md) and [`security.md`](security.md) |

## Useful commands

```bash
# Show the saved main settings with the API key masked
python3 01_configure_sampler_benchmark.py --show

# Edit the saved main settings
python3 01_configure_sampler_benchmark.py --edit

# Run one main stage without changing saved settings
python3 02_run_sampler_benchmark.py --workflow stage1
python3 02_run_sampler_benchmark.py --workflow stage2
python3 02_run_sampler_benchmark.py --workflow stage3

# Regenerate the dashboard without making model calls
python3 02_run_sampler_benchmark.py --workflow dashboard

# Run the offline test suite
python3 -m unittest discover -s tests -p 'test_*.py'
```

## Important limitation

A benchmark score is evidence for the tested prompts, model, backend, and sampler design. It is not a universal ranking of a model and it is not a safety certification. Backend behavior, tokenizer, prompt template, context limits, and server-specific sampler support can change the result.

## License

Released under the [MIT License](license). You may use, modify, redistribute, and use the project commercially, subject to the license terms.
