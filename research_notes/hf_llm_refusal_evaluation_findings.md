# Hugging Face dataset assessment

Source: https://huggingface.co/datasets/MultiverseComputingCAI/llm-refusal-evaluation

The dataset page reports a default configuration of approximately 3.65k rows and ten named splits: ccp_sensitive_sampled (340), ccp_sensitive (1.36k), deccp_censored (95), general_prompts (100), jailbreakbench (100), sorrybench (440), xstest_safe (250), xstest_unsafe (200), adversarial_unsafe_prompts (512), and harmbench_sampled (256). The page tags the dataset for text generation, English text, safety, censorship, politics, and instruction. It links to papers including OR-Bench, SORRY-Bench, JailbreakBench, HarmBench, and XSTest.

The dataset is a collection of multiple source benchmarks and splits, not one homogeneous hand-balanced refusal dataset. The viewer examples include political/censorship prompts and some operationally harmful or adversarial instructions, so it should not be copied wholesale into the public repository or blindly exposed through the default refusal runner. It is better treated as an optional external/local evaluation source.

For Senerenai-HyperProbe, use a selected compatible subset only after verifying the source fields, expected behavior labels, license/terms for every component, duplicate overlap, language, and prompt safety. Preserve source/split provenance for every imported row. Do not mix all splits into one headline score; report per-source/per-split metrics and a separate aggregate only when weighting is explicit.

Assessment: useful as a large reference pool and for validation, but not a direct replacement for the project's small, labeled, safe default dataset. The current 55-58-row user dataset is more controllable for a pilot; a curated 80-120 row internal/public-safe set remains preferable for the default benchmark. The Hugging Face collection can support an optional external benchmark mode later.
