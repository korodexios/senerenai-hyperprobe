# Implementation Brief: Add a Curated Hugging Face Refusal Subset to Senerenai-HyperProbe

You are helping improve an existing project called **Senerenai-HyperProbe**. It is a Python 3.10+ standard-library project for benchmarking and tuning sampling parameters through OpenAI-compatible APIs.

The project already has:

- A three-stage sampler-tuning workflow: Stage 1 screening, Stage 2 interaction refinement, and Stage 3 holdout stability.
- Profiles such as `coding`, `agent_tools`, `creative`, `roleplay`, and `custom_lang`.
- Persistent main settings configured through `01_configure_sampler_benchmark.py` and executed through `02_run_sampler_benchmark.py`.
- Separate additional benchmarks configured through `03_configure_additional_benchmarks.py` and executed through `04_run_additional_benchmarks.py`.
- A refusal/companion benchmark runner that reads JSONL items and produces separate results.
- A long-context NIAH benchmark that reads one user-provided text corpus.
- Benchmark-chain IDs, backend provenance, sampler metadata, JSONL records, and an HTML dashboard.
- A public safe refusal dataset at `datasets/refusal/refusal_safe_v1.jsonl`.
- A private local-data convention at `datasets/local/`, which is ignored by Git.
- Python standard-library-only requirements. Do not add a dependency unless there is a compelling reason and it is documented.

## Objective

Extend the refusal benchmark with a **small, curated, provenance-preserving subset** inspired by the Hugging Face dataset:

`MultiverseComputingCAI/llm-refusal-evaluation`

The Hugging Face collection is large and heterogeneous. It contains approximately 3,650 rows across multiple source splits, including:

- `general_prompts`
- `xstest_safe`
- `xstest_unsafe`
- `sorrybench`
- `jailbreakbench`
- `harmbench_sampled`
- `adversarial_unsafe_prompts`
- politically focused and censorship-related splits

Do **not** import the entire collection into the default benchmark. Do not mix all of its splits into one headline score. The project should remain understandable, efficient, and reproducible.

The preferred first integration is:

1. A curated subset of approximately 10 `xstest_safe` rows.
2. A curated subset of approximately 10 `xstest_unsafe` rows.
3. An optional subset of approximately 10 `sorrybench` rows for a separate reference track.

The first default extension should therefore be approximately:

```text
existing project dataset + 10 xstest_safe + 10 xstest_unsafe
```

The optional extended reference mode may add the SORRY-Bench subset separately.

## Important source and licensing rule

The implementation must not pretend to have access to the Hugging Face JSON if the user has not supplied it locally. Do not fabricate source rows and do not copy prompts from memory.

Implement one of these safe approaches:

### Preferred approach: local import tool

Create a small offline/local import utility that accepts a user-provided Hugging Face export, Parquet/CSV/JSON/JSONL file, or a manually prepared compatible subset. It should convert only selected rows into the project schema.

Example conceptual command:

```bash
python3 import_refusal_subset.py \
  --input datasets/local/hf_llm_refusal_evaluation.jsonl \
  --splits xstest_safe,xstest_unsafe \
  --per-split 10 \
  --output datasets/local/hf_xstest_subset.jsonl
```

The exact command may be adapted to the project’s conventions. It must not require the entire Hugging Face dataset to be committed to GitHub.

### Acceptable alternative: user-supplied converted JSONL

If an importer is not practical, document the exact expected input schema and ask the user to place a converted subset under:

```text
datasets/local/hf_xstest_subset.jsonl
```

The default public repository must not contain private or unverified external prompt data.

## Required normalized JSONL schema

Every imported row must be converted to a schema compatible with the existing refusal runner. Preserve source provenance on every row:

```json
{
  "id": "hf_xstest_safe_001",
  "source": "MultiverseComputingCAI/llm-refusal-evaluation",
  "source_split": "xstest_safe",
  "source_id": "original-row-id-if-available",
  "track": "hf_benign_boundary",
  "expected_behavior": "answer",
  "prompt": "The original prompt from the user-provided source file.",
  "required_terms": [],
  "forbidden_refusal": true,
  "manual_review": false,
  "notes": "Imported from the user-supplied XSTest safe subset."
}
```

For unsafe/refusal-control rows, use a separate track:

```json
{
  "id": "hf_xstest_unsafe_001",
  "source": "MultiverseComputingCAI/llm-refusal-evaluation",
  "source_split": "xstest_unsafe",
  "source_id": "original-row-id-if-available",
  "track": "hf_appropriate_refusal",
  "expected_behavior": "refuse_or_safe_redirect",
  "prompt": "The original prompt from the user-provided source file.",
  "required_terms": [],
  "forbidden_refusal": false,
  "manual_review": true,
  "notes": "Imported from the user-supplied XSTest unsafe subset; verify the expected behavior before scoring."
}
```

Do not assume that a source split alone determines the correct behavior. Each row must have an explicit expected behavior. The converter should support a review/override file if the source dataset does not contain reliable labels.

## Recommended track mapping

Use the following mappings unless the source row clearly requires manual review:

| Source split | Project track | Typical expected behavior |
|---|---|---|
| `xstest_safe` | `hf_benign_boundary` | `answer` |
| `xstest_unsafe` | `hf_appropriate_refusal` | `refuse_or_safe_redirect` |
| `sorrybench` | `hf_sorrybench_reference` | Usually `refuse_or_safe_redirect`, but preserve per-row labels and manual review. |
| `general_prompts` | `hf_general_answerability` | Usually `answer`; do not treat it as a safety track automatically. |
| `harmbench_sampled` | `hf_harmbench_reference` | Optional only; do not put in the default dataset. |
| `jailbreakbench` | `hf_jailbreak_reference` | Optional only; report separately. |
| `adversarial_unsafe_prompts` | `hf_adversarial_reference` | Optional only; report separately. |

Do not import the political/censorship-oriented splits into the default refusal score. They may be useful for a separate research track, but they can measure political knowledge, topical bias, or censorship behavior rather than general refusal calibration.

## Dataset selection and CLI requirements

The normal user workflow must remain low-typing and number-first.

Update `03_configure_additional_benchmarks.py` so the wizard can show numbered dataset choices discovered from:

```text
datasets/refusal/*.jsonl
datasets/local/*.jsonl
```

The wizard should offer choices similar to:

```text
Refusal dataset
  1. datasets/refusal/refusal_safe_v1.jsonl
  2. datasets/local/my_refusal_v1.jsonl
  3. datasets/local/hf_xstest_subset.jsonl
  4. Use a different path (advanced)
  Select 1–4 [Enter keeps 1]:
```

The user should not have to type `my_refusal_v1.jsonl` if the file is already in `datasets/local/`.

Add a numbered source-mode choice such as:

```text
1. Own dataset only
2. Own dataset + imported HF XSTest subset
3. Own dataset + HF XSTest + optional SORRY-Bench reference
```

Keep the existing default as option 1 so current users do not unexpectedly double the benchmark duration.

The optional external subsets must remain separate in the results and dashboard. Do not silently merge them into the core refusal score.

## Scoring and reporting requirements

The dashboard and summary JSON should report these metrics separately:

```text
benign_answer_rate
false_refusal_rate
appropriate_refusal_rate
safe_support_rate
companion_consistency
manual_review_rate
```

For external sources, report at least:

```text
source
source_split
imported_count
scored_count
manual_review_count
answer_rate
refusal_rate
false_refusal_rate
```

Do not calculate a single aggregate across own and external datasets unless the weighting is explicit. A recommended dashboard layout is:

```text
Own refusal benchmark
  Own dataset
  Companion roleplay
  Boundary cases

External reference benchmarks
  HF / XSTest safe
  HF / XSTest unsafe
  HF / SORRY-Bench
```

The imported rows must not affect Stage 1–3 sampler recommendations. They are additional evaluation evidence only. The final sampler preset selected by the main sampler benchmark must remain unchanged by external refusal records.

## Safety and content boundaries

The goal is to evaluate model behavior, not to generate harmful instructions. Do not create new operational instructions for violence, self-harm, abuse, illegal activity, evasion, hacking, weapons, or other serious harm merely for benchmarking.

Do not generate explicit sexual prompts. The project may test adult romance, consent, boundaries, non-explicit intimacy, and companion-roleplay behavior, but explicit graphic sexual content should not be authored as part of this implementation.

If the user provides an external dataset containing sensitive or risky prompts, preserve it only as a local, user-controlled input. Do not include it in the public GitHub archive by default. Keep `datasets/local/` in `.gitignore`.

## Provenance and reproducibility

Every imported result must retain:

```text
benchmark_id
run_id
source
source_split
source_id
track
model
preset_label
parameter_hash
backend provenance
```

Record the external dataset identifier and, when available, its revision/commit hash. Record the importer version and conversion timestamp in the subset manifest. Never silently remove duplicate rows; either deduplicate with a recorded rule or retain the duplicate warning.

## Testing requirements

Add offline tests for:

1. Importing valid JSONL rows.
2. Rejecting rows without `prompt`, `id`, `track`, or `expected_behavior`.
3. Preserving `source`, `source_split`, and `source_id`.
4. Selecting only `xstest_safe` and `xstest_unsafe` when requested.
5. Enforcing the requested per-split sample cap.
6. Keeping external source tracks separate from the core refusal score.
7. Verifying that external refusal records do not enter core Stage 1–3 preset recommendation logic.
8. Discovering datasets under `datasets/local/` in the numbered settings wizard.
9. Keeping custom path entry as an explicit advanced option.
10. Running the importer and refusal runner with mocked model responses and no network dependency.

## Documentation requirements

Update the English README with a beginner-friendly section explaining:

- The project’s own refusal dataset remains the default.
- The Hugging Face-derived subset is optional and local unless the user explicitly supplies it.
- The recommended first extension is 10 `xstest_safe` plus 10 `xstest_unsafe` rows.
- The optional SORRY-Bench subset is a separate reference track.
- Users select datasets by number in `03_configure_additional_benchmarks.py`.
- The main sampler benchmark does not become longer unless the user selects the external subset.
- External prompts may have different licenses and must not be redistributed blindly.
- How to inspect source provenance in the dashboard.

## Deliverables

Please implement the smallest clean solution that satisfies the requirements above. Do not redesign the entire benchmark.

Return or create:

1. The importer or clearly documented compatible local-subset workflow.
2. Updated numbered additional-benchmark setup.
3. Separate external-source result reporting.
4. Provenance-preserving JSONL records and summary JSON.
5. Offline regression tests.
6. Updated English README and changelog.
7. A clean release archive that excludes `results/`, `hyperprobe.local.json`, `hyperprobe.probes.local.json`, `datasets/local/`, caches, credentials, and bytecode.

Before changing code, explain which files you will modify and why. Do not claim to have imported the Hugging Face rows unless the user has actually supplied the source file or authorized a network download and the licensing conditions have been checked.
