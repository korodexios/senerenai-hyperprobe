# NIAH corpus input

Place one or more UTF-8 plain-text corpora in this directory. The NIAH probe receives the path of one corpus through `--corpus` and automatically selects deterministic slices for each requested context size. You do **not** need to pre-insert needles, questions, or answer keys.

For the initial matrix of `4k`, `16k`, and `32k` target tokens, supply a corpus with at least an estimated **80,000 varied tokens**. A practical approximation is at least 320,000 readable characters, although real token counts depend on the selected model tokenizer. The probe records server-reported prompt tokens when the API supplies them and otherwise labels its sizing as a character-based estimate.

Use natural, legally reusable text. Do not add credentials, private chat logs, personal data, repetitive filler, or binary dumps. If you publish a corpus with the project, include source and license information in a separate metadata file.

Example:

```bash
python3 03_probe.py --mode niah \
  --corpus datasets/niah/corpus_en.txt \
  --preset compare
```

The default matrix sends 18 requests: three context sizes × three needle depths × baseline and final preset. It is separate from Stage 1–3 and does not alter any final preset.
