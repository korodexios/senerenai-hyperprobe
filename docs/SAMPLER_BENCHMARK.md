# Sampler Benchmark: Stage 1–3

## Purpose

The Sampler Benchmark searches for useful sampler settings for a selected model and benchmark profile. It is not a generic model leaderboard. Each result is tied to a model, backend, profile, prompts, sampler design, and benchmark chain.

The core parameters are:

```text
temperature
min_p
top_p
repetition_penalty
```

Backend-specific parameters may exist, but they are not included in the portable default design because they would reduce compatibility and expand the search space.

## Stage 1: broad interpretable screening

Stage 1 uses a deliberate screening design rather than an uncontrolled full Cartesian grid. It includes a baseline, main-effect comparisons, and selected interaction rows. Its goal is to identify which parameters appear influential and which regions deserve refinement.

Stage 1 is a **coarse but evidence-based scan**. It does not claim that the highest-scoring row is the universal optimum. When more than one sample is configured, the runner can use confirmation for informative candidates, helping distinguish a stable signal from a lucky completion.

The terminal prints the number of prompts, combinations, samples, confirmation calls, and planned calls before the run starts. The number changes with selected profiles and prompt sets.

## Stage 2: targeted interaction refinement

Stage 2 reads the Stage 1 evidence and focuses on the strongest measured effects and interactions. It normally includes a baseline, a small set of interaction corners, and a useful Stage 1 candidate. It is intentionally not a large grid over every parameter.

Stage 2 answers a narrower question: which nearby combinations deserve further testing after the broad scan? If Stage 1 has not completed or its records were deleted, Stage 2 cannot make a valid handoff.

## Stage 3: holdout stability validation

Stage 3 takes the strongest Stage 2 candidates and evaluates them on more demanding holdout prompts and bounded local variations. It emphasizes mean quality, consistency, and worst-case behavior rather than a single unusually good response.

The strongest validated result becomes the profile’s saved final preset. Additional Benchmarks can later use this preset through the `Final` or `Compare` options.

## Sequential execution

You can run the chain in one command when the saved workflow is `full`:

```bash
python3 02_run_sampler_benchmark.py
```

Or run each stage separately:

```bash
python3 02_run_sampler_benchmark.py --workflow stage1
python3 02_run_sampler_benchmark.py --workflow stage2
python3 02_run_sampler_benchmark.py --workflow stage3
```

The stage metadata carries a stable `benchmark_id` so that Stage 2 and Stage 3 can continue a Stage 1 chain days later. Preserve `results/` between stages.

## Why profiles can produce different presets

Coding often rewards conservative, repeatable outputs. Creative writing and roleplay may benefit from more variation. Tool use can require a balance between exploration and exactness. These are tendencies, not rules; the benchmark exists to measure the selected prompts on the selected model rather than rely on assumptions.

A lower temperature for coding and a higher temperature for creative writing is plausible, but the measured profile result should be interpreted with prompt coverage, errors, and stability—not temperature alone.

## Quality checks

Before accepting a recommendation, check:

| Check | Question |
|---|---|
| Coverage | Did the planned prompts and combinations run? |
| Errors | Were requests failed, truncated, or invalid? |
| Stability | Does the candidate remain good across samples and holdout prompts? |
| Scope | Are you comparing the same model, backend, profile, and benchmark chain? |
| Reproducibility | Are the backend label and relevant metadata recorded? |

A result with a high score but poor coverage or many errors should not be treated as a reliable final preset.
