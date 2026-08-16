# Changelog

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
