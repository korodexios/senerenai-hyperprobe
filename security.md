# Security and responsible use

Senerenai-HyperProbe is a benchmark and tuning tool, not a hardened sandbox. Use it only with systems, models, prompts, and data that you are authorized to use.

Never commit API keys, passwords, private prompts, confidential model outputs, or `hyperprobe.local.json`. Remove sensitive information before opening an issue or sharing a dashboard.

The coding profile may inspect and run eligible generated Python in a temporary subprocess with limited safeguards. This is not a security boundary. Do not run benchmarks on a host containing sensitive files, production credentials, or unrestricted network access unless you have independently isolated and reviewed the environment.

If you believe you found a security-sensitive problem, do not publish credentials or an exploit in a public issue. Contact the repository owner privately through the available GitHub contact method and provide a minimal sanitized description. Ordinary bugs and documentation problems may be reported publicly.

The software is provided under the MIT License, without warranty, and for use at the operator’s own risk.
