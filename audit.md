# Technical Audit and Improvement Record

This document records the review of the supplied alternative implementation against the public Senerenai-HyperProbe release. It distinguishes improvements accepted into the public codebase from ideas rejected because they reduce safety, portability, correctness, or maintainability.

## Accepted improvements

| Area | Accepted improvement | Reason |
|---|---|---|
| Prompt banks | Broader roleplay coverage with pressure, negotiation, constrained dialogue, moral dilemma, and adversarial instruction-resistance scenarios. | A single persona with varied pressure better reveals sampling failures than several similar tavern prompts. |
| Roleplay grading | Metadata-aware persona, modern-term, required-marker, clone, and OOC checks. | Avoids using response length alone as a proxy for character fidelity. |
| Degeneration analysis | Retain repeated-line, n-gram-loop, low-uniqueness, and cross-combination invariance diagnostics. | These detect failures that a simple mean score can hide. |
| Coding benchmark | Retain the supplied diverse categories: algorithms, systems, bug fixing, specification implementation, and refactoring. | The category mix is broad and public-friendly. |
| Stage workflow | Retain bounded Stage 1–3 progression and explicit handoff files. | It controls API cost while preserving reviewable intermediate outputs. |
| Dashboard | Retain model-scoped JSONL ingestion and phase separation. | Pooling phases with different sample counts can create misleading summaries. |
| Public release | Retain environment-driven endpoint configuration, static HTML output, CI, unit tests, changelog, MIT licensing, and GitHub templates. | These are appropriate for a portable public repository. |

## Strengthened beyond the supplied implementation

| Area | Improvement | Rationale |
|---|---|---|
| Code execution | Add AST-based preflight checks before running generated Python. | A subprocess timeout alone is not a security boundary. Static checks can block obvious filesystem, process, network, and dynamic-execution patterns. |
| Stage integrity | Validate handoff schema, profile, model, and candidate data before launching downstream stages. | Prevents accidental reuse of stale or mismatched benchmark files. |
| Reproducibility | Add a run manifest with runtime configuration, prompt-bank fingerprints, and stage settings. | Results should be comparable only when their measurement context is known. |
| Scoring diagnostics | Surface scoring components, error rates, sample counts, and confidence warnings in output data. | A high mean based on few calls is weak evidence. |
| Tests | Add unit tests for safety preflight, handoff validation, roleplay constraints, and record metadata. | Public behavior requires regression coverage. |

## Rejected or constrained ideas

| Item | Decision | Reason |
|---|---|---|
| Treating a temporary subprocess as a hardened code sandbox | Rejected. | A process timeout and temporary directory do not protect a host from all malicious generated code. |
| Unbounded parameter grids | Rejected. | They can create excessive request cost and do not reliably improve decisions. |
| Universal quality claims from one benchmark | Rejected. | Scores depend on model revision, provider implementation, prompt bank, token limit, and sample count. |
| Relying on fixed “creative words” as a dominant creativity score | Constrained. | Fixed vocabulary rewards keyword insertion rather than genuine writing quality. |
| Mixing results from different stages into one mean | Rejected. | Different prompts, combinations, and sample counts make blended means misleading. |
| Including user-specific legacy files in the public repository | Rejected. | The release should remain clean, universal, and public. |

## Release standard

The public repository must remain fully English outside intentional multilingual benchmark prompts and script metadata. Generated results, credentials, private prompts, and personal files are excluded from version control.
