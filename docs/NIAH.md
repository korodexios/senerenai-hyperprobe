# NIAH Long-Context Benchmark

NIAH means **Needle in a Haystack**. HyperProbe uses one UTF-8 corpus, creates deterministic test cases, inserts a unique synthetic fact at a controlled position, asks the model to retrieve it, and scores exact retrieval.

## What you provide

Prepare one varied UTF-8 text file. It can be documentation, public-domain text, technical material, or another corpus that you are allowed to use. The corpus should be substantially longer than the largest requested context size and should not consist entirely of repeated filler.

Example location:

```text
datasets/niah/corpus_en.txt
```

You do not insert needles, questions, or answer keys yourself. The probe creates those parts so that the retrieval task is controlled and reproducible.

## Common matrices

| Matrix | Context sizes | Needle depths | Use |
|---|---|---|---|
| **Quick** | 4k, 16k, 32k | 10%, 50%, 90% | General first run. |
| **Light** | 4k, 16k | 10%, 50%, 90% | Fast compatibility check. |
| **Deep** | 4k, 16k, 32k, 64k | 10%, 50%, 90% | More demanding long-context study. |

The real token count depends on the model tokenizer. The probe records server-reported prompt-token metadata when available and identifies estimates when it is not available. Make the corpus comfortably larger than the largest requested context; a corpus of approximately 80,000 varied tokens is a practical starting point for a 4k/16k/32k matrix.

## Configure and run

```bash
python3 03_configure_additional_benchmarks.py
python3 04_run_additional_benchmarks.py
```

Choose NIAH or Both in the first menu, provide the corpus path the first time, then select a matrix by number. Pressing Enter keeps the saved corpus and matrix on later runs.

## Interpretation

NIAH v1 measures exact retrieval under the selected context sizes and positions. It does not by itself measure general reasoning, summarization, instruction following, or the full usable context window. Results can be affected by tokenizer choice, prompt template, server truncation, context limits, and backend implementation.

Keep NIAH results separate from the sampler-tuning recommendation. A sampler preset that is good for retrieval need not be the best preset for coding, creative writing, or roleplay.
