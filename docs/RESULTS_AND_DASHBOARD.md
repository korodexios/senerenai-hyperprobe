# Results and Dashboard

## Where files are written

| Location | Contents |
|---|---|
| `results/stages/` | Immutable stage archives and handoff records. |
| `results/*.jsonl` | Result records and compatibility/latest-pointer files. |
| `results/probes/` | Refusal and NIAH probe archives and latest pointers. |
| `results/dashboards/` | Static HTML dashboards. |

Generated results are local output and are ignored by Git. Keep a private backup if the results are important.

## Benchmark chains

A Stage 1 run creates a stable `benchmark_id`. Stage 2 and Stage 3 inherit it when they continue the same model/profile chain. This allows the following sequence:

```bash
python3 02_run_sampler_benchmark.py --workflow stage1
# You can stop here and continue later.
python3 02_run_sampler_benchmark.py --workflow stage2
python3 02_run_sampler_benchmark.py --workflow stage3
```

Older chains are archived instead of being silently relabeled as the current run. The latest-pointer files support the zero-prompt workflow, while immutable archive records preserve reproducibility.

The chain identity is not based only on the filename. It is carried in result metadata together with the model, profile, prompt fingerprints, stage, and design provenance. If you intentionally start a new Stage 1 benchmark, it creates a new chain.

## Additional probes are separate

Refusal and NIAH records use their own `probe_id` and are shown in a separate **Additional benchmark probes** section of the dashboard. They are not pooled into the sampler-tuning recommendation. This is intentional: a refusal or retrieval test answers a different question from “which sampler preset performs best on this profile?”

## Reading the dashboard

The per-model dashboard now uses primary tabs so the first page is not overloaded with implementation details.

| Tab | Question it answers |
|---|---|
| **Overview** | What was tested, what are the main sampler and probe findings, and where should I look next? |
| **Stage 1 — screening** | Which broad parameter regions looked promising across all profiles, and how did the initial combinations rank? |
| **Stage 2 — refinement** | How did the focused interaction candidates perform after Stage 1 narrowing? |
| **Stage 3 — stability** | Which narrowed presets held up on the final holdout/stability evidence across all profiles? This is the preferred final sampler view when it exists. |
| **Sampler tuning** | Which practical parameter presets are supported by Stage 1–3 evidence for the tested profiles? |
| **Refusal & companion** | How often did each preset meet the refusal dataset's defined automated checks, and which tracks should be investigated? |
| **NIAH long context** | How did exact retrieval perform at the tested context positions and sizes? |
| **Technical details** | What were the runs, backend, sampler declarations, coverage, errors, sensitivity, and individual combinations? |

Start with **Overview**. When a completed Stage 3 exists, it shows a concise, color-coded **latest sampler evidence** snapshot with one best-observed result per profile and a profile comparison chart. Then open **Stage 3 — stability** for the all-profile final table or a profile-specific sub-tab. Use Stage 1 and Stage 2 when you need to understand how the search narrowed; their results are deliberately not pooled with Stage 3. The Technical details tab is intentionally secondary; it exists for reproducibility and investigation rather than everyday preset selection.

### What the refusal score means

The Refusal & companion tab shows an **automated agreement score**. It is the average of transparent, dataset-defined checks such as the expected behavior, presence of a required concept, and simple refusal or support indicators. It is **not** a universal safety score, a measurement of morality, or proof that every individual response is correct.

The dashboard shows a track chart and a row for every dataset track. Lower values identify tracks where the model less often met the dataset's declared expectation. They are investigation priorities: inspect reply previews and the dataset labels before deciding whether the model is too restrictive, too permissive, missing support, or simply encountering an ambiguous prompt.

Rows marked `manual_review: true` remain visible, but are **excluded from the automated refusal headline score**. They must not be treated as automatic passes or failures. The tab explicitly displays their count next to the automatically scored count.

Technical run IDs are retained for traceability, but they are not intended to be the main user-facing label. If the dashboard contains a short hexadecimal ID, treat it as an internal reference and use the surrounding stage, model, profile, and record-count information to identify the run.

## Additional benchmark run statistics

Every new refusal or NIAH probe archive records a `run_statistics` object and prints the same essential summary in the terminal. It contains the UTC start and finish times, wall-clock elapsed time, attempted/successful/failed call counts, success rate, successful calls per minute, request-latency mean/p50/p95/min/max, and aggregate request time.

The terminal distinguishes **wall-clock time** from **aggregate request time**. With one concurrent request they are similar; with multiple concurrent requests, aggregate request time can be larger than wall-clock time because several requests overlap.

| Token field | Meaning |
|---|---|
| `completion_tokens` / output tokens | Included only when the API explicitly returns completion-token usage. |
| `prompt_tokens` / input tokens | Included only when the API explicitly returns prompt-token usage. |
| `not_reported_by_api` | The server did not provide this telemetry. It does **not** mean zero tokens. |
| NIAH `estimated_input_tokens` | A character-based construction estimate for the generated NIAH prompt; it is clearly not server tokenizer telemetry. |

## Coverage and integrity

A low error count does not automatically mean that a run is scientifically strong. Check whether the expected prompts and combinations were covered, whether records are missing, and whether the model returned valid outputs. Failed requests remain visible for diagnostics and should not improve a ranking.

Run integrity is most useful when interpreted alongside the plan printed at the beginning of a stage. A partially completed run can be technically valid JSONL while still being incomplete for comparison.

## Regenerate without model calls

To rebuild the dashboard from all available result records:

```bash
python3 02_run_sampler_benchmark.py --workflow dashboard
```

This does not rerun the model. It only re-reads the local records and writes the HTML dashboard.
