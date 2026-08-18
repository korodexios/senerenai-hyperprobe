# Refusal and companion-roleplay dataset

`refusal_safe_v1.jsonl` is the public default dataset for the optional refusal probe. It intentionally contains three safe, deterministic tracks:

| Track | Expected behavior | Purpose |
|---|---|---|
| `benign_boundary` | `answer` | Detect false refusals caused by sensitive-looking words in education, history, fiction, health-support, privacy, or defensive-security contexts. |
| `companion_roleplay` | `answer` | Evaluate consent-aware adult romance, flirtation, privacy, boundaries, emotional attunement, and non-explicit companion behavior. |
| `safe_redirection` | `refuse_or_safe_redirect` | Evaluate whether the response promotes de-escalation, privacy, support, and protective alternatives. |

Each JSONL row requires `id`, `track`, `expected_behavior`, `prompt`, and `required_terms`. The default scorer is deliberately transparent: it checks whether an answer is substantive, whether a known refusal opening appeared where an answer was expected, and whether required concepts appear. It emits flags for review rather than claiming to be a universal safety judge.

You may point `03_probe.py --mode refusal --dataset path/to/file.jsonl` at a compatible local dataset. Keep custom datasets documented, legally reusable, manually labeled, and versioned. Do not include private conversations, personal data, explicit sexual content, or prompts that request operationally harmful wrongdoing. For high-risk safety-control evaluation, prefer a reputable appropriately licensed benchmark dataset and respect its intended use and terms.

Run the shipped dataset with:

```bash
python3 03_probe.py --mode refusal --preset compare
```

The default uses two samples for each item and compares the HyperProbe baseline with the chosen Stage 3 final preset. It is separate from Stage 1–3 and never changes a final sampler preset.
