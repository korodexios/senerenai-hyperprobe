# Senerenai-HyperProbe

**Universal LLM Sampling Benchmark & Tuner**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MIT License](https://img.shields.io/badge/license-MIT-green.svg)](license)
[![Zero Runtime Dependencies](https://img.shields.io/badge/runtime%20dependencies-zero-2ea44f)](pyproject.toml)
[![OpenAI-Compatible API](https://img.shields.io/badge/API-OpenAI--compatible-412991)](https://platform.openai.com/docs/api-reference)

Senerenai-HyperProbe is a lightweight, provider-neutral tool for finding reliable sampling presets for large language models exposed through an OpenAI-compatible chat-completions API. It evaluates a running model across repeated prompts and parameter combinations, then produces a stability-aware preset for coding, tool calling, creative writing, roleplay, or multilingual generation.

> Senerenai-HyperProbe tunes **inference behavior**, not model weights. It does not fine-tune, quantize, download, or modify models, and it does not claim to discover a universally optimal configuration.

## At a glance

| Question | Answer |
|---|---|
| What does it tune? | `temperature`, `min_p`, `top_p`, and `repetition_penalty` by default. |
| What does it need? | Python 3.10+ and an OpenAI-compatible `/v1` endpoint for live benchmarks. |
| Does it require PyTorch or a GPU? | No. The benchmark engine uses the Python standard library. |
| Which servers work? | Any compatible server, including llama.cpp, vLLM, Ollama, LM Studio, SGLang, and TabbyAPI-style deployments. |
| What does it produce? | JSON stage handoffs, JSONL records, final preset JSON, and static HTML dashboards. |
| Is it multilingual? | Yes. The public benchmark includes 18 language targets and per-language filtering. |

## Why Senerenai-HyperProbe exists

Sampling parameters interact with one another, and one lucky completion is a poor basis for selecting a preset. Senerenai-HyperProbe uses a bounded, interpretable three-stage funnel. It first measures each parameter's main effect against a shared baseline and probes selected interactions, then verifies the strongest interactions directly, and finally tests local drifts around the strongest candidates. Ranking rewards quality while penalizing instability, poor worst-case behavior, repetitive output, and collapsed vocabulary.

The tool is deliberately model- and provider-neutral. The same workflow can be used against a local laptop server, a workstation with multiple inference slots, or a remote OpenAI-compatible deployment. Results remain specific to the selected model revision, prompt bank, endpoint implementation, maximum token limit, and sample count.

## Features

| Area | Capability |
|---|---|
| Search | Interpretable three-stage screening → interaction refinement → stability search with bounded request volume. |
| API | `/v1/models` discovery and `/v1/chat/completions` requests with configurable authorization, timeout, retry, concurrency, and thinking-mode payloads. |
| Profiles | Coding, agent/tool calling, creative writing, roleplay, and multilingual quality evaluation. |
| Multilingual coverage | English, Mandarin Chinese, Hindi, Spanish, Arabic, French, Bengali, Portuguese, Indonesian, Urdu, Russian, German, Japanese, Korean, Turkish, Polish, Czech, and Slovak. |
| Quality controls | Repeated samples, variance, worst-case scoring, repeated-line detection, n-gram-loop detection, vocabulary-collapse detection, and cross-combination invariance warnings. |
| Outputs | Model-scoped JSONL logs, stage handoffs, final sampling presets, and static dashboards. |
| Runtime | Python standard library only; no GPU, model weights, framework, or database required. |

## Installation

### Option A: clone and run directly

After creating or selecting your GitHub repository, clone it and enter the project directory:

```bash
git clone https://github.com/korodexios/senerenai-hyperprobe.git senerenai-hyperprobe
cd senerenai-hyperprobe
python3 --version
```

The public repository is `https://github.com/korodexios/senerenai-hyperprobe`. The explicit destination argument keeps the local checkout directory lowercase. Senerenai-HyperProbe does not require a dependency installation for its core runtime.

### Option B: install as a local package

The project includes `pyproject.toml` for editable installation:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install --editable .
```

The executable stage scripts remain available from the repository root. A virtual environment is recommended for isolation even though the runtime dependency list is empty.

## First-time setup and guided workflow

For most users, Senerenai-HyperProbe now has a numbered two-file workflow. Run the setup wizard once after cloning:

```bash
python3 01_setup.py
```

The wizard stores the endpoint, authorization value, default model, selected profile set, language filter, timeout, concurrency, token limit, retry choice, thinking-mode default, and Stage 1–3 request-volume defaults in `hyperprobe.local.json`. That file is ignored by Git and is written with owner-only permissions where the operating system permits it. You do **not** need to type the same endpoint and model configuration every time.

Then run the launcher whenever you want to benchmark:

```bash
python3 02_run.py
```

The launcher supports one or more profiles in a single run. Select profile numbers or names separated by commas, for example `creative, roleplay` or `2,4`, or enter `all`. It then lets you run only Stage 1, only Stage 2, only Stage 3, the complete **Stage 1 → Stage 2 → Stage 3** pipeline, or regenerate the dashboard only.

| File | Purpose | Typical use |
|---|---|---|
| `01_setup.py` | Saves local endpoint, model, runtime, profile, and workflow defaults. | Run once, then whenever settings change. |
| `02_run.py` | Selects multiple profiles and runs a stage, full pipeline, or dashboard. | Normal interactive use. |
| `stage1_coarse.py` | Runs the coarse scan directly. | Advanced use and automation. |
| `stage2_refine.py` | Runs bounded refinement from a validated Stage 1 handoff. | Advanced use and automation. |
| `stage3_finest.py` | Runs local stability search from a validated Stage 2 handoff. | Advanced use and automation. |
| `visualizer.py` | Regenerates static HTML dashboards from JSONL results. | Analysis without new API calls. |

A fully non-interactive full-pipeline invocation is also available:

```bash
python3 02_run.py --profiles creative,roleplay --workflow full --model your-model
python3 02_run.py --profiles agent_tools --workflow stage1 --model your-model
python3 02_run.py --all-profiles --workflow full --model your-model
```

The saved setup is convenient, but environment variables retain precedence for CI, containers, external secret managers, and temporary overrides:

```bash
export HYPERPROBE_API_BASE="http://localhost:8080/v1"
export HYPERPROBE_API_KEY="Bearer llama.cpp"
python3 02_run.py --profiles coding --workflow full --model your-model
```

Use `python3 01_setup.py --show` to inspect saved values with the API key masked. Use `python3 01_setup.py --reset` to reset the local file to public defaults.

## Advanced direct workflow

The standalone scripts remain available for advanced use, CI, and custom shell automation:

```bash
python3 stage1_coarse.py --profile coding --model your-model --samples 1
python3 stage2_refine.py --profile coding --model your-model --samples 1 --max-combos 5
python3 stage3_finest.py --profile coding --model your-model --top-n 2 --samples 1
python3 visualizer.py
```

The stage scripts are intentionally separate. Stage 2 consumes the Stage 1 handoff, and Stage 3 consumes the Stage 2 handoff. Use `--think` when the target server supports a thinking-mode request extension.

### Sequential runs and result identity

Each Stage 1 run creates a stable `benchmark_id`. That identifier is carried into Stage 2 and Stage 3, including their JSONL records, stage handoffs, and final preset. The launcher also keeps a latest pointer for each `stage/profile/model/language` combination, so the simple sequence below works without additional prompts:

```bash
python3 02_run.py --workflow stage1 --profiles coding --model model-a
python3 02_run.py --workflow stage2 --profiles coding --model model-a
python3 02_run.py --workflow stage3 --profiles coding --model model-a
```

The immutable archive files contain the benchmark identifier, for example `stage1_coding_model-a_<benchmark_id>.json`. The shorter `stage1_coding_model-a.json` file is only the latest pointer used by the zero-prompt launcher. A later run for the same model creates a new archive instead of destroying the previous Stage 1, Stage 2, Stage 3, or final-preset archive. Different model IDs are also isolated by their model-specific paths. The dashboard may pool compatible JSONL records for analysis, but every record retains `benchmark_id`, `run_id`, model, profile, stage, language, and search-design provenance so future reporting can reconstruct which stages belong together.

If several independent experiments use the same model and profile, run them as separate Stage 1 chains. Stage 2 and Stage 3 will continue the most recently completed Stage 1/Stage 2 chain through the latest pointer. Use the archived JSON handoff path with the standalone stage scripts when you intentionally want to continue an older chain rather than the newest one.

## The three-stage search

### Stage 1 — interpretable screening

Stage 1 uses **33 deliberate combinations**, not an opaque random sweep. It tests one shared baseline, then runs five non-baseline levels for each of `temperature`, `min_p`, `top_p`, and `repetition_penalty`, changing only one parameter at a time. It then adds twelve targeted interaction rows: four `temperature × top_p` corners, four `min_p × top_p` corners, and four `temperature × repetition_penalty` corners. Its purpose is to establish credible parameter influence and useful value ranges before refinement, not to claim an exact optimum. Every combination receives one broad screening sample. When Stage 1 is configured with `samples=2`, only the baseline and eight strongest first-pass combinations receive a second confirmation sample; the second sample is not wasted on every weak combination. Use three samples only for visibly noisy models or high-confidence production tuning.

The handoff records the baseline, the ranking of every tested main-effect value, an effect span for each parameter, selected values for refinement, and targeted-interaction evidence. Failed API calls remain in JSONL diagnostics but are excluded from ranking evidence. Records generated by this design are tagged `hybrid_v5`; the dashboard displays them separately from older `legacy` and earlier hybrid search records, even when they use the same model, so their rankings are never silently mixed.

### Stage 2 — targeted interaction refinement

Stage 2 uses the Stage 1 handoff to identify the two parameters with the strongest measured main effects. It narrows each to two measured values and tests only the **four corners of their primary interaction plus the baseline**, for a default of **five candidates**. The candidates are evaluated once on the harder Stage 2 prompt subset; a candidate with a failed or missing response is excluded from ranking. This is a deliberate reduction, not a lower-quality shortcut: Stage 1 has already supplied the broad evidence, so Stage 2 spends its budget on a compact two-parameter interaction decision. Manual `--range` overrides retain the legacy bounded-grid fallback for expert use.

### Stage 3 — holdout stability validation

Stage 3 validates the **top two** Stage 2 candidates rather than trusting only one winner. For coding, agents, creative writing, and roleplay it uses up to two compact prompts that Stage 2 did not see. Around each candidate it tests the base point, eight one-parameter local drifts, and four diagonal drifts for the measured primary interaction pair. It uses one sample by default because the complexity comes from holdout prompts and paired perturbations rather than repeated copies of the same test. Failed or incomplete candidates cannot produce a final preset. The selected `final_preset_*.json` stores `sampling_parameters`, holdout prompt identifiers, selected-pair evidence, selected-candidate metrics, run manifest, and warnings. Copy the nested `sampling_parameters` object into another compatible client.

### Typical quality/cost budget

For a profile with three quick Stage 1 prompts and the default two requested samples, the adaptive workflow uses **99 broad Stage 1 calls plus 27 confirmation calls**, **15 Stage 2 calls** (three prompts × five targeted candidates × one sample), and **52 Stage 3 calls** (two holdout prompts × two Stage 2 candidates × thirteen local combinations × one sample), for a practical total of about **193 calls**. A full all-profile run with the current prompt banks uses approximately 546 Stage 1 calls instead of 858 calls under a naive 33-combination × 2-sample sweep. This is the intended funnel: broad evidence first, selective confirmation second, narrow interaction decision third, and complex local validation last. Increase Stage 1 samples to three only when the model is visibly noisy or the preset will be used in a high-stakes repeated workflow.

The exact count depends on the selected profile’s prompt bank. The general formulas are:

```text
Stage 1 broad pass = 33 combinations × Stage 1 prompts
Stage 1 confirmation pass = 9 combinations × Stage 1 prompts, only when requested samples ≥ 2
Stage 2 = 5 candidates × Stage 2 prompts × Stage 2 samples
Stage 3 = 2 candidates × 13 local combinations × Stage 3 holdout prompts × Stage 3 samples
```

For example, the current `coding` output uses five Stage 2 prompts, so Stage 2 shows `5 × 5 × 1 = 25` calls. The table’s 15 Stage 2 calls is only the three-prompt example, not a universal count for every profile. The launcher always prints the actual prompt, candidate, sample, and total-call counts before making requests. A custom-language run with one selected language has one language prompt; selecting all 18 languages intentionally multiplies the multilingual workload.

## Profiles

| Profile | What it measures | Typical use |
|---|---|---|
| `coding` | Executable code shape, expected markers, static safety preflight, and bounded subprocess behavior for eligible code. | Coding assistants and code generation. |
| `agent_tools` | JSON validity, tool selection, required arguments, nested argument schemas, types, and literal constraints. | Tool-calling agents and automation. |
| `creative` | Vocabulary diversity, coherence, and repetition resistance. | Brainstorming, fiction, and open-ended writing. |
| `roleplay` | Persona retention, out-of-character leakage, modern-term drift, dialogue constraints, and clone resistance. | Character and instruction-following evaluation. |
| `custom_lang` | Script fidelity, foreign-script leakage, diacritics, coherence, cloning, and degeneration. | Multilingual model comparison. |

## Multilingual benchmark

The `custom_lang` profile includes one representative prompt for each of 18 target languages. Without `--language`, all 18 prompts are evaluated consistently in all three stages. A language code passed with `--language` runs that language independently and is stored in benchmark records for later analysis.

| Code | Language | Writing system |
|---|---|---|
| `en` | English | Latin |
| `zh` | Mandarin Chinese | Han characters |
| `hi` | Hindi | Devanagari |
| `es` | Spanish | Latin |
| `ar` | Arabic | Arabic |
| `fr` | French | Latin |
| `bn` | Bengali | Bengali |
| `pt` | Portuguese | Latin |
| `id` | Indonesian | Latin |
| `ur` | Urdu | Arabic-derived |
| `ru` | Russian | Cyrillic |
| `de` | German | Latin |
| `ja` | Japanese | Japanese scripts |
| `ko` | Korean | Hangul |
| `tr` | Turkish | Latin |
| `pl` | Polish | Latin |
| `cs` | Czech | Latin |
| `sk` | Slovak | Latin |

Run every language:

```bash
python3 stage1_coarse.py --profile custom_lang --model your-model --samples 1
```

Run one language at a time:

```bash
python3 stage1_coarse.py --profile custom_lang --language es --model your-model --samples 2
python3 stage2_refine.py --profile custom_lang --language zh --model your-model --samples 1
python3 stage3_finest.py --profile custom_lang --language sk --model your-model --top-n 1 --samples 2
```

Language counts and rankings differ depending on whether native speakers, total speakers, dialect groups, or macrolanguages are counted. The benchmark is therefore a practical coverage set, not a claim that one language is more important than another.[^1] [^2]

## Command reference

### Stage 1

```text
python3 stage1_coarse.py [--profile PROFILE | --all] [--language CODE]
                         [--model MODEL] [--samples N] [--timeout SECONDS]
                         [--think]
```

`--language` applies to `custom_lang`. The available codes are defined in `tests/custom_lang.py` under `LANGUAGE_PROFILES`.

### Stage 2

```text
python3 stage2_refine.py [--profile PROFILE | --all] [--language CODE]
                         [--model MODEL] [--samples N] [--max-combos N]
                         [--stage1 PATH] [--ranges PATH] [--timeout SECONDS]
                         [--think]
```

### Stage 3

```text
python3 stage3_finest.py [--profile PROFILE | --all] [--language CODE]
                         [--model MODEL] [--samples N] [--top-n N]
                         [--stage2 PATH] [--timeout SECONDS] [--think]
```

Run `--help` on any stage for the exact defaults in the installed version.

## Configuration reference

Configuration is read from environment variables with safe local defaults.

| Variable | Default | Meaning |
|---|---|---|
| `HYPERPROBE_API_BASE` | `http://localhost:8080/v1` | OpenAI-compatible API root. |
| `HYPERPROBE_API_KEY` | `Bearer llama.cpp` | Authorization header value. |
| `HYPERPROBE_TIMEOUT` | `180` | Per-request timeout in seconds. |
| `HYPERPROBE_RETRY` | `1` | Whether a failed request is retried once. |
| `HYPERPROBE_CONCURRENCY` | `1` | Number of concurrent requests. Increase only when the server supports multiple inference slots. |
| `HYPERPROBE_MAX_TOKENS` | `2048` | Maximum completion length. |
| `STAGE2_DEFAULT_MAX_COMBOS` | `5` | Default Stage 2 candidate cap: baseline plus four primary-interaction corners. |
| `STAGE2_DEFAULT_SAMPLES` | `1` | Samples per Stage 2 candidate and prompt. |
| `STAGE3_DEFAULT_TOP_N` | `2` | Number of Stage 2 candidates locally validated in Stage 3. |
| `STAGE3_DEFAULT_SAMPLES` | `1` | Samples per Stage 3 candidate, drift, and holdout prompt. |

The values in `config.py` define parameter boundaries, profile weights, prompt mappings, and stage defaults. Keep provider-specific assumptions isolated there or in `common.py`.

## Complete Beginner’s Guide

This section is for someone using Senerenai-HyperProbe for the first time. You do not need prior experience with LLM benchmarking, sampling parameters, Python packaging, or OpenAI-compatible APIs. Follow the steps in order, and keep this section open while the terminal asks questions.

### Step 1: make sure a model server is running

Senerenai-HyperProbe does not download or start a model. It connects to a model server that is already running and exposes two standard endpoints:

```text
GET  /v1/models
POST /v1/chat/completions
```

Your server may be local or remote. The base URL usually ends in `/v1`, for example `http://localhost:8080/v1`. You also need the exact model ID returned by `/v1/models`. If the server requires authentication, you need the authorization value expected by that server, such as `Bearer your-token`. Senerenai-HyperProbe sends this value as the `Authorization` header.

Before running a large benchmark, confirm that the server is reachable and that the model can answer a normal chat-completions request. If `/v1/models` cannot be reached, setup cannot discover the model automatically; you can still enter the model ID manually, but the server connection must be repaired before the benchmark itself can succeed.

### Step 2: choose an installation style

The simplest option uses the Python installation already available on your system:

```bash
python3 01_setup.py
```

For an isolated standard Python environment, use `venv`:

```bash
python3 -m venv .venv
. .venv/bin/activate                 # macOS/Linux
# .venv\\Scripts\\activate          # Windows PowerShell
python3 -m pip install --editable .
python3 01_setup.py
```

For `uv`, either create and synchronize an environment explicitly:

```bash
uv venv
uv sync
uv run python 01_setup.py
```

or let `uv` manage the command environment directly:

```bash
uv run python 01_setup.py
```

The core project intentionally has no mandatory runtime dependency outside the Python standard library. A virtual environment is still recommended so future optional tooling does not affect the rest of your system.

### Step 3: run the setup wizard

Run:

```bash
python3 01_setup.py
```

If `hyperprobe.local.json` already exists, the wizard first shows a summary and asks whether you want to edit it. Press **Enter** at that opening prompt to keep every saved value and exit immediately. Use `python3 01_setup.py --edit` when you actually want to review or change settings. During editing, every question shows the current saved value, the developer’s original default, a short explanation, and an **Enter keeps the saved value** instruction.

The wizard asks the following questions:

| Setup question | What it means | Typical first value |
|---|---|---|
| OpenAI-compatible API base | The server root before `/models` and `/chat/completions`. Do not add `/chat/completions`. | `http://localhost:8080/v1` |
| Authorization value | The complete value for the `Authorization` header. | `Bearer llama.cpp`, or the token format required by your server |
| Default model ID | The model identifier returned by `/v1/models`. | Choose the listed model number |
| Profiles | The benchmark families to use by default. You can select several. | `coding`, or `creative, roleplay` |
| Default languages | Applies only to `custom_lang`; choose several numbered languages, or option `19` for all 18. | `1,4,18`, or `19` for all |
| Per-request timeout | Maximum seconds to wait for one response. | `180` |
| Concurrent requests | Number of requests sent at once. Keep `1` unless your server supports parallel slots. | `1` |
| Maximum completion tokens | Upper bound for each generated answer. | `2048` |
| Retry one failed request | Whether one failed request is retried. | `yes` |
| Thinking mode | Sends the supported thinking-mode extension when enabled. | `no` unless your server documents support |
| Stage 1 samples | Repeated answers per Stage 1 prompt/combination. | `2` |
| Stage 2 samples | Samples per focused interaction candidate and prompt. | `1` |
| Stage 2 maximum combinations | Baseline plus four primary-interaction corners. | `5` |
| Stage 3 samples | Samples per local drift and holdout prompt. | `1` |
| Stage 3 top candidates | Number of Stage 2 candidates explored locally. | `2` |

The wizard writes these values to `hyperprobe.local.json`. This is a private local file, is ignored by Git, and is not included in the public release archive. If the file already exists, running `01_setup.py` again does not reopen every question: press Enter at the opening prompt to keep all saved values, or type `edit` (or use `--edit`) to review them.
To inspect it later without revealing the complete API key, run `python3 01_setup.py --show`. To edit saved values explicitly, run `python3 01_setup.py --edit`. To return to public defaults, run `python3 01_setup.py --reset`.

### Step 4: choose what to benchmark

Run the launcher:

```bash
python3 02_run.py
```

The launcher reuses the saved model, profiles, custom-language selection, workflow, timeouts, samples, retries, and thinking-mode default. After setup, plain `python3 02_run.py` is **zero-prompt**: it immediately runs the saved configuration without asking for profiles, model, workflow, or languages. Use an explicit flag only when you want a temporary one-run change, or use `python3 01_setup.py --edit` to change the saved configuration permanently.

When you use `--choose-profiles` or `--interactive`, the profile menu accepts one name, several comma-separated names, one-based menu numbers, `6` for **ALL profiles**, or `all`:

```text
coding
creative, roleplay
2,4
all
```

The profiles mean the following:

| Profile | Choose it when you want to evaluate |
|---|---|
| `coding` | Code structure, expected behavior, specification following, and safe execution eligibility. |
| `agent_tools` | JSON tool calls, tool choice, required arguments, types, enums, and nested schemas. |
| `creative` | Originality, vocabulary diversity, coherence, and resistance to repetitive output. |
| `roleplay` | Persona consistency, natural dialogue, emotional depth, out-of-character leakage, and modern-term drift. |
| `custom_lang` | Language fidelity, writing-system fidelity, diacritics, foreign-language leakage, and multilingual coherence. |

For `custom_lang`, the setup wizard displays a numbered three-column language grid. The launcher automatically reuses the saved selection; use `python3 02_run.py --choose-languages` to show the grid for a one-run override, or `python3 02_run.py --interactive` to show every run-time menu. Choose several numbers or codes such as `1,4,18` or `en,es,sk`, or choose `19` for all 18 languages. `cz` is accepted as a friendly alias for the canonical Czech code `cs`. When several languages are selected, the launcher runs them independently and writes language-scoped Stage 1/2/3 handoffs and final preset files so results cannot overwrite one another.

### Step 5: choose a workflow

The launcher offers five choices:

| Choice | What happens next |
|---|---|
| Stage 1 only | Performs the 33-combination quality-first screening and writes a validated handoff. |
| Stage 2 only | Loads the matching Stage 1 handoff and tests the five-candidate primary interaction refinement. |
| Stage 3 only | Loads the matching Stage 2 handoff and tests two candidates with holdouts, axial drifts, and paired interaction drifts. |
| Full pipeline | Runs Stage 1, automatically passes its output to Stage 2, then passes Stage 2 to Stage 3. |
| Dashboard only | Makes HTML reports from results already collected; it does not call the model. |

For a first run, select one profile and **Full pipeline** in `01_setup.py`. On later runs, plain `python3 02_run.py` uses the saved workflow automatically without a prompt. To choose a different workflow only once, use `python3 02_run.py --choose-workflow`; to show every run-time menu, use `python3 02_run.py --interactive`; to change the saved default permanently, use `python3 01_setup.py --edit`. Start with conservative sample counts and one profile so that you can confirm the endpoint, model, prompt bank, and output format before increasing the request volume.

The same actions can be scripted without interactive questions:

```bash
python3 02_run.py --profiles coding --workflow full --model your-model
python3 02_run.py --profiles creative,roleplay --workflow full --model your-model
python3 02_run.py --profiles custom_lang --language es,sk --workflow full --model your-model
python3 02_run.py --all-profiles --workflow full --model your-model
python3 02_run.py --choose-workflow
python3 02_run.py --choose-languages
python3 02_run.py --interactive
```

### Step 6: understand what the stages are doing

Stage 1 tries a bounded set of deliberately different sampling combinations. It is looking for useful regions, obvious degeneration, errors, and suspiciously invariant behavior; it is not claiming that one response is the universal winner.

Stage 2 takes the validated Stage 1 handoff, identifies the two parameters with the largest measured effect spans, and tests only the baseline plus four corners of that primary interaction. This is a focused refinement decision, not another broad scan. It ranks candidates by quality, variance, worst-case behavior, and reliability flags.

Stage 3 takes the top two validated Stage 2 candidates and evaluates them on compact holdout prompts that Stage 2 did not see. It tests the base point, eight one-parameter local drifts, and four diagonal drifts for the measured interaction pair. Its goal is to discover whether the apparent best result generalizes and remains stable in its local neighborhood. It writes the final preset together with provenance, metrics, warnings, holdout evidence, and the selected `sampling_parameters` object.

### Step 7: find and interpret the results

All generated artifacts are placed under `results/`, which is intentionally ignored by Git. The most useful files are:

| Result | Meaning |
|---|---|
| Stage 1 JSON | Coarse scores, warnings, suggested ranges, and top combinations. |
| Stage 2 JSON | Refined combinations and narrowed ranges. |
| Stage 3 JSON | Local drift tests and stability metrics. |
| `final_preset_*.json` | The recommended parameters plus metrics, warnings, and reproducibility metadata. |
| `*.jsonl` | Detailed append-only records for individual prompts and samples. |
| `results/dashboards/index.html` | Cross-model dashboard entry point. |
| `results/dashboards/dashboard_*.html` | Detailed model-specific dashboard. |

Open the dashboard in a browser after the run, or serve it from the results directory if your browser cannot open local files:

```bash
python3 -m http.server 8000 --directory results/dashboards
```

Then open `http://localhost:8000`. A high score is not enough by itself: inspect failure rate, worst-case score, stability, degeneration flags, latency, and the prompt-level details before adopting a preset.

### First-run troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| `Connection refused` | The model server is stopped or the API base is wrong. | Start the server and verify the `/v1` URL in `01_setup.py`. |
| `404` for `/models` | The endpoint is not OpenAI-compatible or the `/v1` suffix is wrong. | Check the server documentation and remove or add `/v1` as required. |
| No models are listed | The server returned an empty model list. | Confirm the model is loaded, then enter its exact ID manually. |
| `401` or `403` | The authorization value is missing or formatted incorrectly. | Re-run setup and enter the complete header value required by the server. |
| Stage 2 cannot find Stage 1 | Stage 1 was not run for the same model/profile, or output was moved. | Run the full pipeline or repeat Stage 1 with the same model and profile. |
| Stage handoff mismatch | Results belong to another model, profile, or stage. | Do not rename files to bypass validation; rerun the matching earlier stage. |
| Very slow run | Completion length, timeout, or request volume is high. | Lower max tokens, reduce samples, use one profile, and keep concurrency at `1`. |
| Many degeneration flags | The model is repeating or the sampling region is unsuitable. | Inspect the dashboard, compare worst-case scores, and try another region or preset. |
| Dashboard is empty | No valid JSONL records exist in `results/`. | Complete at least one benchmark and run `python3 visualizer.py`. |
| Thinking-mode errors | The server does not support the extension used by the selected model. | Disable thinking mode in setup or use `--no-think` where available. |

If the project has been configured incorrectly, the safest reset is:

```bash
python3 01_setup.py --reset
python3 01_setup.py
```

Never paste an API key into a public issue, commit `hyperprobe.local.json`, or upload the `results/` directory if replies contain sensitive prompts or private data.

## Outputs and dashboard

Benchmark artifacts are written below `results/` and are ignored by Git:

| Output | Purpose |
|---|---|
| `results/stages/stage1_*.json` | Stage 1 sensitivity, suggested ranges, warnings, and top combinations. |
| `results/stages/stage2_*.json` | Stage 2 grid analysis, narrowed ranges, and ranked combinations. |
| `results/stages/stage3_*.json` | Stage 3 drift analysis and stability metrics. |
| `results/final_preset_*.json` | Selected sampling parameters, stability metrics, run manifest, and warnings. |
| `results/*.jsonl` | Model-scoped append-only records for dashboard analysis. |
| `results/dashboards/index.html` | Cross-model comparison page. |
| `results/dashboards/dashboard_*.html` | Per-model searchable dashboard. |

Run `python3 visualizer.py` after at least one benchmark. The dashboard separates phases instead of mixing records with different sample counts, shows specialized presets, exposes parameter sensitivity, lists difficult prompts, reports degeneration rates, summarizes per-run failure rates, and shows descriptive multilingual coverage statistics.

## Reliability and reproducibility

Every stage handoff contains schema-versioned `_meta` provenance and a `run_manifest`. The manifest records the stage, profile, model identifier, Python/runtime context, prompt-bank fingerprint, sample count, parameter-combination count, token limit, and thinking-mode state. It intentionally does **not** store API keys. Downstream stages validate the upstream stage name, profile, model, and required fields before using a handoff, which prevents accidental chaining of mismatched results.

JSONL records include stable `run_id`, timestamp, schema version, phase, profile, model, prompt ID, language where applicable, parameter hash, score dimensions, flags, elapsed time, and a short reply preview. Compare scores only when model revision, provider implementation, prompt-bank fingerprint, token limit, and sample count are aligned.

### Coding execution safety

Senerenai-HyperProbe performs a conservative AST preflight before it executes generated Python. Obvious process, network, filesystem, and dynamic-evaluation patterns are flagged and skipped rather than executed. This protects routine benchmark use, but it is **not a hardened sandbox**. Treat all model-generated code as untrusted, run benchmarks in an isolated environment, and do not mount confidential data or production credentials into the benchmark host.

## Troubleshooting

### No models are listed

Confirm that `HYPERPROBE_API_BASE` points to the API root rather than the host root, that the server exposes `/v1/models`, and that the authorization header format matches the provider. Use the connectivity snippet above before running a benchmark.

### The server rejects `min_p` or `repetition_penalty`

Provider support for sampling fields differs. Remove unsupported fields in `config.py` or adapt the request payload in `common.py`. Keep the change provider-specific rather than weakening the general benchmark schema.

### Results are too noisy

Increase `--samples`, use a smaller `--max-combos` only after Stage 1 has produced useful ranges, and keep the model revision and prompt bank fixed. Stage 3 is specifically designed to prefer stable candidates over one-off high scores.

### The multilingual grader reports a script leak

Inspect the raw response in the JSONL record. A small amount of code, a URL, or an English technical term may be legitimate, but repeated output in the wrong script is evidence that the selected preset or prompt needs review.

### The dashboard is empty

The visualizer reads JSONL records below `results/`. Run at least one stage successfully, confirm that the process can write to the repository, and then run `python3 visualizer.py` again.

## Testing and CI

The repository is designed to validate offline without contacting a model server:

```bash
python3 -m compileall -q .
python3 -m unittest discover -s tests -p 'test_*.py'
python3 smoke_check.py
python3 stage1_coarse.py --help
python3 stage2_refine.py --help
python3 stage3_finest.py --help
```

GitHub Actions runs the same checks on pushes and pull requests. Live API benchmarks are intentionally not part of CI because they require operator credentials and a model endpoint.

## Repository layout

| Path | Purpose |
|---|---|
| `config.py` | Defaults, parameter grids, profiles, weights, and stage controls. |
| `common.py` | API client, retries, batching, model discovery, persistence, and response cleaning. |
| `runner.py` | Shared sweep and grading orchestration. |
| `stage1_coarse.py` | Coarse parameter-range discovery. |
| `stage2_refine.py` | Bounded refinement grid. |
| `stage3_finest.py` | Local drift and stability-aware final selection. |
| `grader/` | Modular profile graders and degeneration detection. |
| `tests/` | Prompt banks and offline unit tests. |
| `visualizer.py` | Static dashboard generator. |
| `contributing.md` | Friendly guide for bug reports, documentation fixes, testing, and pull requests. |
| `code_of_conduct.md` | Basic respectful-community guidelines. |
| `security.md` | Safe handling of credentials, private data, and generated code. |
| `.github/` | Optional issue templates, pull-request template, and CI workflow. |

## Safety and use at your own risk

Coding responses are executed in a temporary subprocess with a timeout. This is a lightweight benchmark safeguard, not a hardened security boundary. Never evaluate untrusted generated code on a sensitive host, mount confidential directories into the process, or send private prompts to a remote provider without approval.

Do not commit API keys, model outputs containing personal data, private prompt banks, or generated `results/`. Use environment variables or an external secret manager for credentials.

## Helping the project

You do not need to be a developer to help. You can report a bug, explain that a command is confusing, suggest a better benchmark prompt, confirm that the tool works with another server, or correct the documentation. The file [`contributing.md`](contributing.md) explains these options in simple language.

A developer can also **fork** the repository, make a change in their copy, and open a **pull request**. A pull request is only a proposal for review; it does not change the main project automatically. The maintainer can discuss it, request changes, accept it, or decline it.

The files [`code_of_conduct.md`](code_of_conduct.md) and [`security.md`](security.md) are human-facing safeguards. They are not required for running the benchmark. They explain respectful collaboration and how to avoid exposing credentials or private information.

## License and permissions

Senerenai-HyperProbe is released under the **MIT License**. This is an unrestricted public-use project: you may use, modify, redistribute, and include it in commercial work. In practical terms, the license allows anyone to use, copy, modify, merge, publish, distribute, sublicense, and sell copies of the software, including in commercial products, provided that the copyright and license notice remain with substantial copies of the software. The software is provided without warranty, and the authors are not liable for damages arising from its use. Read the complete text in [`license`](license) before redistributing.

## Project metadata

Suggested GitHub repository slug and technical path: **`senerenai-hyperprobe`**. The human-facing project name is **Senerenai-HyperProbe**.

Suggested description: **Universal, lightweight LLM sampling benchmark and tuner for OpenAI-compatible APIs.**

Suggested topics: `llm`, `large-language-models`, `sampling`, `temperature`, `min-p`, `top-p`, `repetition-penalty`, `benchmark`, `evaluation`, `openai-compatible`, `llama-cpp`, `vllm`, `ollama`, `multilingual`, `python`, `ai-tools`.

## References

[^1]: [Ethnologue 200 methodology and language-ranking scope](https://www.ethnologue.com/insights/ethnologue200/).
[^2]: [Ranked: The World’s Most Spoken Languages in 2026](https://www.visualcapitalist.com/ranked-the-worlds-most-spoken-languages-in-2026/), a total-speaker summary based on Ethnologue data.
