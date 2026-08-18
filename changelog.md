# Changelog

## 1.11.11 — 2026-08-18

This patch polishes the dashboard header and metadata presentation.

| Area | Change |
|---|---|
| Header layout | Replaced loose flex wrapping with a structured two-row layout for the report title, subtitle, back link, and metadata. |
| Long model names | Added stable full-width title wrapping without competing against the record, timing, latency, and stage badges. |
| Metadata badges | Added consistent spacing, truncation, title tooltips for long stage lists, and responsive behavior below desktop width. |
| Mobile behavior | Header metadata stacks cleanly on narrow screens and no longer overlaps the title or tabs. |
| Tests | Added regression coverage for the structured header containers. |

## 1.11.10 — 2026-08-18

This focused dashboard cleanup removes the remaining duplicate technical stage dump.

| Area | Change |
|---|---|
| Stage detail placement | Moved the remaining profile × Stage top-combination rows out of Technical details and into the dedicated Stage 1, Stage 2, and Stage 3 profile sub-tabs. |
| Visual evidence | Detailed Stage rows now use colored rank badges, score bars, and per-dimension status badges instead of an uncolored text list. |
| Technical tab | Retains only cross-stage provenance, coverage, multilingual diagnostics, and parameter sensitivity, with a clear pointer to the Stage tabs for combinations. |
| Tests | Added a regression check ensuring the legacy uncolored stage dump does not return. |

## 1.11.9 — 2026-08-18

This patch restores the depth of sampler analysis while retaining the clearer high-level dashboard.

| Area | Change |
|---|---|
| Stage navigation | Restored distinct primary tabs for Stage 1 screening, Stage 2 refinement, and Stage 3 stability. |
| Final evidence | Overview now presents a Stage 3-first summary across all available profiles, with a visible fallback to the most advanced completed stage. |
| Stage analytics | Each stage has an all-profiles score chart/table and profile-specific sub-tabs with ranked combinations, parameter badges, evidence counts, latency, and dimensions. |
| Visual hierarchy | Restored stage-specific color accents and score bars so screening, refinement, and final stability evidence are easier to distinguish. |
| Method integrity | Stage scores remain isolated; the dashboard does not pool Stage 1–3 averages into a misleading single ranking. |
| Tests | Added regression coverage for Stage 1–3 primary tabs and the Stage 3 overview snapshot. |

## 1.11.8 — 2026-08-18

This patch gives Additional Benchmarks the same whole-run visibility expected from the Stage 1–3 workflow.

| Area | Change |
|---|---|
| Whole-run timing | Refusal and NIAH now print UTC start/end times and actual wall-clock elapsed time. The Additional Benchmarks launcher also prints probe-only, dashboard-only, and total workflow elapsed time. |
| Reliability | Probe archives report attempted, successful, failed, and success-rate counts. |
| Latency | Summaries provide mean, p50, p95, minimum, maximum, and aggregate request time, with an explicit explanation for concurrent execution. |
| Throughput | Reports successful calls per minute when the wall-clock duration is meaningful. |
| Token telemetry | Reports input/output token totals only when the API returned them. Missing telemetry is labeled `not_reported_by_api`, never treated as zero. |
| NIAH estimates | Separately reports a clearly labeled character-based estimated input total for constructed NIAH prompts. |
| Tests | Added archived-statistics assertions for refusal and NIAH mock runs. |

## 1.11.7 — 2026-08-18

This patch makes refusal results auditable at the individual-response level.

| Area | Change |
|---|---|
| Full raw replies | Every refusal probe row now writes the complete cleaned reply, prompt, expected behavior, grade, flags, preset, and response metadata to a local `results/raw/` JSONL file. |
| Compact public records | Dashboard records retain the short `reply_preview` and link to the local raw-output file rather than embedding long replies. |
| Safe redirection grading | `refuse_or_safe_redirect` now requires an actual refusal prefix or a recognized safe-redirection cue; length and required terms alone no longer pass it. |
| External review | Added a reusable prompt for another LLM to audit the original dataset together with the raw-output JSONL row by row. |
| Privacy | Raw outputs remain under ignored `results/` and are excluded from public archives. |
| Tests | Added regression coverage for refusal/safe-redirection detection and full raw-reply preservation. |

## 1.11.6 — 2026-08-18

This patch makes the dashboard understandable as a decision tool rather than a long technical report.

| Area | Change |
|---|---|
| Dashboard navigation | Added primary tabs for Overview, Sampler tuning, Refusal & companion, NIAH long context, and Technical details. |
| Plain-language summary | Added a first-screen explanation of what sampler and probe results answer, plus score interpretation guidance. |
| Refusal analysis | Added a preset-level automated-agreement headline, track comparison chart, score bars, auto-scored counts, manual-review counts, errors, and visible investigation signals. |
| Correct review handling | Dashboard aggregation now excludes `manual_review` probe rows from the refusal headline score while keeping their counts and rows visible. |
| Result separation | Sampler recommendations, refusal results, and NIAH results are now visibly separated in both the per-model dashboard and multi-model comparison. |
| Compatibility maintenance | Replaced stale duplicated legacy launchers with current delegates and added non-interactive `--help` support for the additional-benchmark configuration and runner. |
| Tests | Added regression coverage proving manual-review rows cannot inflate or distort automated refusal summaries. |

## 1.11.5 — 2026-08-18

This release supports expanded refusal datasets while keeping normal runs quick.

| Area | Change |
|---|---|
| Refusal schema | Accepts `answer`, `refuse_or_safe_redirect`, `supportive_response`, and `manual_review`. |
| Review handling | `manual_review` rows are retained and reported but excluded from the automated headline score. |
| Support scoring | Sensitive-support rows receive a dedicated `safe_support` dimension. |
| Refusal metadata | Records preserve `source`, `source_split`, `source_id`, `forbidden_refusal`, and review flags when supplied. |
| Dataset modes | Added saved `Quick` and `Full` refusal modes. Quick is the default; Full is selected explicitly for larger datasets. |

## 1.11.4 — 2026-08-18

This maintenance release makes the additional-benchmark wizard faster to use from a keyboard.

| Area | Change |
|---|---|
| Number-first controls | Preset, profile, language, dataset, common NIAH matrix, samples, timeout, thinking mode, and dashboard behavior now use numbered choices with Enter-preserving defaults. |
| Dataset discovery | The wizard automatically lists public refusal JSONL files and private `datasets/local/` JSONL files as numbered choices. |
| Advanced-only typing | Custom paths, custom matrices, custom counts, custom timeout, and manual sampler JSON remain available only as explicit advanced choices. |
| Git privacy | Added `datasets/local/` to `.gitignore` for private user-provided datasets. |

## 1.11.3 — 2026-08-18

This maintenance release clarifies the public workflow terminology for first-time users.

| Area | Change |
|---|---|
| Main workflow | Renamed the recommended public entry points to `01_configure_sampler_benchmark.py` and `02_run_sampler_benchmark.py`. |
| Additional workflows | Renamed the refusal/NIAH entry points to `03_configure_additional_benchmarks.py` and `04_run_additional_benchmarks.py`. |
| Documentation | Replaced the potentially confusing public word `diagnostics` with `additional benchmarks`; technical diagnostic descriptions remain where they are useful. |
| Compatibility | Existing entry points remain available for older scripts and users. |

## 1.11.2 — 2026-08-18

This maintenance release makes the public workflow clearer for first-time users.

| Area | Change |
|---|---|
| Entry points | Added descriptive names: `01_configure_benchmark.py`, `02_run_benchmark.py`, `03_configure_diagnostics.py`, and `04_run_diagnostics.py`. |
| Compatibility | The older `01_setup.py`, `02_run.py`, `03_probe_setup.py`, and `04_probe.py` commands remain available for existing scripts and imports. |
| Documentation | Reorganized the README so the beginner quick start, configuration, zero-prompt execution, optional probes, and override commands appear before methodology and technical details. |

## 1.11.1 — 2026-08-18

This maintenance release adds persistent optional-probe settings and a zero-prompt runner.

| Area | Change |
|---|---|
| Probe setup | Added `03_probe_setup.py` to save enabled modes, dataset/corpus paths, preset source, matrix, sample counts, timeout, thinking mode, and dashboard behavior. |
| Zero-prompt execution | Added `04_probe.py`; after setup, optional probes run without command-line tags or further questions. |
| Safety | The dedicated local probe settings file is ignored by Git and relative dataset/corpus paths resolve from the project directory. |

## 1.11.0 — 2026-08-18

This feature release adds optional diagnostic probes without changing the efficient Stage 1 → Stage 2 → Stage 3 sampler-tuning workflow.

| Area | Change |
|---|---|
| Optional launcher | Added `03_probe.py`, which reuses saved API, model, runtime, thinking, backend, and sampler settings while keeping probe execution separate from the main tuner. |
| Preset reuse | Supports `baseline`, `final`, `compare`, `mini-sweep`, and explicit `manual` preset modes. The default comparison is baseline plus a selected saved Stage 3 final preset. |
| Refusal diagnostic | Added a public deterministic dataset with benign-boundary, consent-aware adult companion-roleplay, and safe-redirection tracks. It records transparent answerability/false-refusal signals without explicit sexual content or operationally harmful instructions. |
| Long context | Added deterministic NIAH exact-retrieval probing. One user-supplied UTF-8 corpus is sliced automatically, a unique needle is inserted at controlled depths, and exact retrieval is scored separately for each preset. |
| Result isolation | Probe JSONL records, immutable summaries, and dashboard rows are separated from Stage 1–3 recommendations. Probe scores never affect final sampler presets. |
| Telemetry | Records server-reported input token usage when available and otherwise clearly marks NIAH sizing as a character-based estimate. |
| Tests | Added offline coverage for public refusal dataset validation, false-refusal flagging, NIAH case construction/scoring, preset loading, and dashboard isolation. |
| Zero-prompt probes | Added `03_probe_setup.py` for persistent refusal/NIAH settings and `04_probe.py` for running all enabled probes without command-line tags. |

## 1.10.1 — 2026-08-18

This maintenance release improves reproducibility and diagnostics without expanding the universal four-parameter tuning space.

| Area | Change |
|---|---|
| Backend provenance | Added an optional human-readable backend label, a privacy-preserving endpoint fingerprint, declared sampler capabilities, and an explicit provider-defined sampler-order note to run manifests. |
| Capability safety | A requested known sampling parameter that is excluded by declared capabilities now produces a visible configuration error instead of being silently dropped from an API request. |
| JSONL diagnostics | New records retain backend provenance, completion-token count, returned response model, and finish reason when supplied by the provider. |
| Dashboard | Shows backend and declared sampler information for new records; uses readable benchmark-chain labels rather than opaque run hashes; completes English-only labels and repairs degeneration-rate bars. |
| Benchmark chains | Stage 1, Stage 2, Stage 3, and final preset archives preserve a shared benchmark ID while latest pointers support zero-prompt sequential continuation. |
| Tests | Added regression coverage for backend settings, capability validation, manifest privacy/provenance, visible parameter-rejection errors, and dashboard provenance rendering. |

## 1.10.0 — 2026-08-16

This release keeps the broad 33-combination Stage 1 design but avoids spending a second sample on every combination. All combinations receive one screening sample; when Stage 1 samples are set to 2, only the baseline and eight strongest first-pass combinations receive confirmation. The Stage 2 and Stage 3 narrowing strategy is unchanged, while total runtime is substantially reduced for multi-profile runs.

| Area | Change |
|---|---|
| Stage 1 coverage | Retains all 33 quality-first combinations. |
| Stage 1 confirmation | Adaptive second sample for nine informative combinations instead of every combination. |
| Search design | Versioned as `hybrid_v5`; downstream stages require matching provenance. |
| Runtime | Default all-profile Stage 1 drops from 858 calls to approximately 546 calls at the current prompt set. |


## 1.9.1 — 2026-08-16

This patch prevents silent mixing of search methodologies across stages. Stage 2 now requires a matching `hybrid_v4` Stage 1 handoff, and Stage 3 requires a matching `hybrid_v4` Stage 2 handoff. Older handoffs are rejected with a clear provenance mismatch instead of producing a dashboard bucket containing only Stage 2 and Stage 3 records.


## 1.9.0 — 2026-08-16

This efficiency release keeps Stage 1 broad and makes the later stages progressively narrower and more complex instead of simply increasing request volume.

| Area | Change |
|---|---|
| Stage 2 candidate budget | Reduced the default from eight to five candidates: baseline plus four corners of the measured primary interaction. |
| Stage 2 samples | Returned the default to one sample because Stage 1 already provides broad repeated evidence and Stage 2 is a focused interaction decision. |
| Stage 3 validation | Retains two top candidates, unseen holdout prompts, eight axial drifts, and four diagonal interaction drifts, but returns to one sample by default. |
| Efficiency | The representative three-prompt workflow drops from 350 to 265 calls while retaining the richer interaction and holdout structure. |
| Result isolation | Introduced `hybrid_v4` so this reduced-call methodology is not pooled with earlier designs. |

## 1.8.0 — 2026-08-16

This validation release strengthens the later stages so broader Stage 1 evidence is confirmed on repeated measurements and unseen prompts before a final preset is selected.

| Area | Change |
|---|---|
| Stage 2 confirmation | Changed the default from one to two samples per candidate; any candidate with incomplete prompt/sample coverage is excluded from Stage 2 ranking. |
| Stage 2 ranking | Added worst-case quality to the bounded refinement score alongside mean and variance. |
| Stage 3 candidates | Changed the default from the top one to the top two Stage 2 candidates. |
| Stage 3 validation | Uses up to two prompts not evaluated by Stage 2 for coding, tools, creative writing, and roleplay, providing a compact generalization check. |
| Stage 3 drift | Added four diagonal local drifts for the Stage 2 primary interaction pair, in addition to baseline and one-parameter drifts. |
| Final-preset integrity | Candidates with incomplete holdout coverage cannot enter the final ranking or produce a preset. Final preset JSON now records holdout prompts and the tested interaction pair. |
| Result isolation | Introduced `hybrid_v3` so the dashboard keeps this validation design separate from earlier `hybrid_v2`, `hybrid_v1`, and legacy runs. |

## 1.7.0 — 2026-08-16

This quality-first release expands the initial screening evidence while preserving the bounded and interpretable three-stage workflow.

| Area | Change |
|---|---|
| Stage 1 coverage | Expanded Stage 1 from 18 to 33 combinations: one baseline, five non-baseline main-effect levels for each of four parameters, and twelve interaction corners across three parameter pairs. |
| Interaction coverage | Added `temperature × repetition_penalty` alongside the existing `temperature × top_p` and `min_p × top_p` interaction checks. |
| Stage 2 explanation | The terminal now prints all measured effect spans and explicitly states why it selected the primary interaction pair. |
| Result isolation | Introduced `hybrid_v2`, so the dashboard keeps this broader design separate from `legacy` and prior `hybrid_v1` evidence for the same model. |
| Quality budget | Kept the default two Stage 1 samples, with documentation for three samples when model output is noisy or high-confidence tuning is required. |

## 1.6.0 — 2026-08-16

This methodology release replaces the opaque coarse parameter bundles with an efficient, interpretable experimental funnel designed to improve output quality without an unbounded request budget.

| Area | Change |
|---|---|
| Stage 1 design | Replaced twelve fully changed parameter bundles with 18 labeled rows: one baseline, eleven one-factor main-effect variations, and six targeted `temperature × top_p` or `min_p × top_p` interactions. |
| Stage 1 handoff | Added baseline metadata, ranked main-effect values, effect spans, selected refinement values, interaction evidence, and candidate roles. |
| Stage 2 design | Replaced arbitrary Cartesian-grid downsampling with targeted interaction refinement. The default cap is now eight candidates: a primary interaction pair, top coarse evidence, assembled main-effect winners, and a compact secondary check. |
| Stage 3 safeguards | Local drifts are bounded to valid parameter ranges, and failed API calls cannot influence stability scores or create a final preset. |
| Failure handling | Stage 1 and Stage 2 now also exclude failed API calls from their ranking evidence while preserving them in JSONL diagnostics. |
| Tests | Added regressions for the fractional Stage 1 layout, targeted Stage 2 candidate construction, and Stage 3 parameter bounds. |
| Documentation | Rewrote the pipeline explanation with the quality/cost rationale and default call budgets. |

## 1.5.0 — 2026-08-16

This release completes the one-time setup workflow: a plain launcher command now runs the saved benchmark without any follow-up terminal questions.

| Area | Change |
|---|---|
| Zero-prompt execution | `python3 02_run.py` now directly uses every saved setting: model, profiles, languages, workflow, and runtime defaults. |
| Temporary changes | Added `--choose-profiles` and `--interactive`; the existing explicit flags remain available for one-run overrides. |
| Missing model protection | The launcher fails with a clear setup instruction instead of opening an unexpected model prompt. |
| Tests | Added a regression test that patches `input()` and proves the default launcher path never asks a question. |
| Documentation | Rewrote the beginner launcher guidance around the hands-free default and opt-in interactive menus. |

## 1.4.0 — 2026-08-16

This usability release removes redundant repeat-run questions while keeping explicit per-run overrides available.

| Area | Change |
|---|---|
| Saved workflow | Added `default_workflow` to local settings; the launcher uses it automatically on repeat runs. |
| Repeat runs | The launcher no longer asks for the workflow or language grid unless the user requests `--choose-workflow` or `--choose-languages`. |
| Overrides | Added `--choose-workflow`, `--choose-languages`, `--workflow`, and `--language` for intentional one-run changes. |
| Setup summary | The saved workflow is displayed alongside the model, profiles, languages, and runtime values. |
| Documentation | Clarified the difference between permanent setup changes and temporary launcher overrides. |

## 1.3.0 — 2026-08-16

This usability release makes repeated setup fast and makes multilingual selection visible and resumable.

| Area | Change |
|---|---|
| Saved settings | Running `01_setup.py` with an existing settings file now shows a summary and exits on Enter; use `--edit` to reopen the full editor. |
| Inline help | Every editable setting shows its purpose, current saved value, and developer default before asking for a change. |
| Profile selection | Added explicit option `6` for all profiles in the setup wizard and launcher. |
| Language selection | Added a three-column numbered language grid, multi-language selection, `19` for all languages, and friendly aliases such as `cz` → `cs`. |
| Pipeline execution | Multiple saved custom languages run independently through Stage 1 → Stage 2 → Stage 3. |
| Handoff safety | Stage handoffs and final presets now include language-scoped filenames and validation, preventing one language from overwriting another. |
| Tests | Added regression tests for language aliases, multi-language persistence, language-scoped handoffs, and multi-language orchestration. |

## 1.2.0 — 2026-08-16

This usability release adds a persistent, beginner-friendly terminal workflow without removing the advanced standalone stage scripts.

| Area | Change |
|---|---|
| Numbered startup | Added `01_setup.py` and `02_run.py` so public instructions have a clear first and second command. |
| Persistent settings | Added `hyperprobe.local.json` with endpoint, authorization, model, runtime, selected-profile, language, and Stage 1–3 defaults. The file is ignored by Git and written with restrictive permissions where supported. |
| Configuration precedence | Environment variables continue to override saved local values, preserving CI, container, and secret-manager workflows. |
| Multi-profile execution | The launcher accepts multiple comma-separated profile names or numbers, as well as `all`. |
| Pipeline orchestration | The launcher can run one stage, the complete Stage 1 → Stage 2 → Stage 3 pipeline, or the dashboard only. |
| Compatibility | Replaced the outdated sweep-only `runner.py` implementation with a compatibility entry point to `02_run.py`. |
| Tests | Added offline tests for settings validation, persistence, selection parsing, environment construction, and multi-profile full-pipeline orchestration. |

## 1.1.0 — 2026-08-16

This reliability release audits the public implementation against an alternative benchmark design and adopts the improvements that strengthen correctness, portability, and safety without weakening the provider-neutral architecture.

| Area | Change |
|---|---|
| Roleplay benchmark | Expanded from seven to twelve Kael scenarios, including negotiation, moral dilemmas, constrained dialogue, modern-term pressure, and adversarial instruction resistance. |
| Roleplay grader | Added metadata-aware OOC detection, modern-term drift detection, style-cue checks, required-dialogue-marker validation, minimum-length metadata, and cross-sample clone penalties. |
| Agent benchmark | Added two public tasks and deterministic schemas for argument types, nested objects, arrays, literal values, minimum values, and required fields. |
| Agent grader | Replaced presence-only argument checks with deterministic nested-schema validation. |
| Coding execution | Added conservative AST preflight checks that avoid executing obvious filesystem, process, network, and dynamic-evaluation patterns. This is a safeguard, not a hardened sandbox. |
| Reproducibility | Added schema-versioned stage handoffs, prompt-bank fingerprints, run manifests, stable run IDs, record timestamps, and failure-rate summaries. |
| Stage integrity | Added downstream validation of stage, profile, model, and required handoff fields. |
| Dashboard | Repaired HTML output, completed English labels, and added run-integrity and multilingual-coverage panels. |
| Tests | Expanded offline coverage for manifests, handoff validation, safety preflight, nested agent schemas, and roleplay constraints. |

## 1.0.0 — 2026-08-16

Initial public release with a three-stage OpenAI-compatible sampling workflow, five evaluation profiles, multilingual benchmark coverage, static dashboards, CI, public documentation, and the MIT License.
