# Abliteration Eval assessment

Source: https://huggingface.co/datasets/treadon/abliteration-eval

The Hugging Face page reports Apache-2.0 licensing, 283 default rows, and two named splits: `harmful` (200 rows) and `over_refusal` (83 rows). The dataset card also describes a `multilingual` split of 50 rows across Spanish, French, German, Hindi, and Japanese, although the viewer summary may expose it separately from the default configuration. The schema includes `prompt`, `category`, `type`, and `note` for harmful/over_refusal rows; multilingual rows include `prompt`, `language`, `type`, and `english` translation.

The harmful split has 200 prompts across 20 categories, 10 each, covering weapons, drugs, hacking, malware, fraud/scams, identity theft, theft/burglary, violence/harm, harassment/stalking, surveillance/privacy, and related categories. The over_refusal split has 83 safe prompts using sensitive trigger words and is structured across 10 types. The dataset card frames the benchmark around both refusal removal for harmful prompts and over-refusal correction for safe prompts.

For Senerenai-HyperProbe, the `over_refusal` split is the most directly useful addition: it complements benign_boundary and boundary_edge. A small curated subset of 10-15 rows could be imported into a separate `hf_over_refusal` or `abliteration_over_refusal` track. The harmful split is not suitable for the public default dataset because it contains explicit operational harmful requests; it should remain an optional, local, provenance-preserving control set if used at all. Do not add its prompt text to public project documentation or generate more such prompts.

Potential normalized mapping:
- `type=over_refusal` -> `track=abliteration_over_refusal`, `expected_behavior=answer`, `manual_review` if unclear.
- `type=harmful` -> `track=abliteration_harmful_reference`, `expected_behavior=refuse_or_safe_redirect` for a safety-aligned evaluation, but this conflicts with the dataset card's abliteration objective (which may expect compliance). The objective must be chosen explicitly; do not silently treat compliance with harmful requests as a quality target.
- multilingual harmless -> separate optional multilingual boundary track with translated/English provenance.

Assessment: more focused and structurally cleaner than the larger mixed Hugging Face collection for over-refusal evaluation. Use over_refusal as a small optional subset or as an external reference track, not necessarily as part of Quick. Verify license and source provenance in any import manifest even though the dataset card reports Apache-2.0.
