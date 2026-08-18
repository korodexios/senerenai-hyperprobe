# Settings and Workflows

## Main sampler settings

The main wizard is `01_configure_sampler_benchmark.py`. It writes `hyperprobe.local.json` and controls the sampler benchmark runner.

| Setting | Meaning | Practical guidance |
|---|---|---|
| API base | OpenAI-compatible server root, normally ending in `/v1`. | It must be reachable and must expose `/models` and chat completion behavior expected by the project. |
| Authorization value | Complete authorization header value, for example `Bearer your-token`. | Keep it private. The wizard masks it in summaries. |
| Model ID | Exact model identifier accepted by the server. | This is required by both the sampler and additional benchmark runners. |
| Backend label | Human-readable server/version label. | Optional, but useful for reproducibility. |
| Profiles | `coding`, `agent_tools`, `creative`, `roleplay`, and `custom_lang`. | Select several profiles or use the `ALL` number. |
| Languages | Languages used by `custom_lang`. | Select by number; the all-languages option is supported. |
| Workflow | `stage1`, `stage2`, `stage3`, `full`, or `dashboard`. | Use `full` for a complete chain and individual stages for staged work. |
| Timeout | Maximum seconds allowed for one request. | Increase it if the model regularly needs more time. |
| Concurrency | Number of simultaneous requests. | Keep `1` unless the server has enough slots and memory. |
| Maximum tokens | Completion-token ceiling. | Set this high enough for the longest expected answer. |
| Retry | Whether one failed request is retried. | Keeping retry enabled is usually sensible for transient failures. |
| Thinking mode | Backend-specific thinking extension when supported. | Enable only when the server exposes compatible behavior. |

## Stage defaults

The shipped developer defaults are intentionally conservative and can be changed in the wizard:

| Stage | Default samples | Default candidate cap | Purpose |
|---|---:|---:|---|
| Stage 1 | 2 | 33 deliberate combinations in the design | Broad, interpretable screening of the sampler space. |
| Stage 2 | 1 | 5 combinations by default | Narrow refinement around the strongest measured effects. |
| Stage 3 | 1 | Top 2 candidates | Holdout and local stability validation. |

The exact number of API calls also depends on the selected profiles, prompt counts, language selections, confirmation logic, and whether a stage is resumed from existing records. The terminal prints the planned call count before execution.

## What the sampler parameters do

`temperature` controls the strength of randomness in token selection. Lower values usually make outputs more conservative and repeatable; higher values can increase variety. The best value is task-dependent.

`top_p` limits sampling to a probability mass. `min_p` removes tokens below a probability threshold relative to the most likely token. `repetition_penalty` changes the likelihood of repeating tokens. These parameters interact, so a value that works for coding may not be best for roleplay or creative writing.

The benchmark does not assume that one universal parameter setting is correct for every profile. It searches and scores each profile separately, then reports a profile-specific final preset where enough data exists.

## Why the stages are not one giant grid

Stage 1 is a broad screen. It should provide enough coverage to identify useful value regions, but it is not intended to prove an exact optimum. Stage 2 uses evidence from Stage 1 to investigate a small number of informative interactions instead of multiplying every parameter combination. Stage 3 applies the strongest candidates to more demanding holdout prompts and local drifts, emphasizing stability rather than a single lucky answer.

This staged design is deliberately more efficient than increasing every later-stage combination. Later stages should use fewer, better-targeted combinations and more discriminating prompts.

## Additional benchmark sampler presets

The Additional Benchmark wizard does not independently ask for temperature, `top_p`, and `min_p` in normal mode. It selects a preset source:

| Choice | Meaning |
|---|---|
| **Baseline** | Uses the stable public reference preset: `temperature=0.6`, `min_p=0.05`, `top_p=0.9`, `repetition_penalty=1.05`. |
| **Final** | Uses the saved Stage 3 final preset for the selected profile. |
| **Compare** | Runs both Baseline and Final. This is useful when you want to compare a public reference with your tuned result. |
| **Mini sweep** | Runs Baseline, Final, and low/high-temperature variants. It makes more calls. |
| **Manual** | Accepts one complete sampler JSON object, including all required sampler fields. |

A manual preset looks like this:

```json
{
  "temperature": 0.6,
  "min_p": 0.05,
  "top_p": 0.9,
  "repetition_penalty": 1.05
}
```

Therefore, selecting **Baseline** is not a missing configuration step. It is an intentional choice to benchmark one fixed reference preset. Select **Final** or **Compare** when you want to use the settings discovered by Stage 1–3.
