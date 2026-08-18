## What does this change do?

Explain the change in simple terms and why it is useful.

## What was checked?

- [ ] `python3 -m compileall -q .`
- [ ] `python3 -m unittest discover -s tests -p 'test_*.py' -q`
- [ ] `python3 smoke_check.py`
- [ ] `python3 01_configure_sampler_benchmark.py --help`
- [ ] `python3 02_run_sampler_benchmark.py --help`
- [ ] `python3 03_configure_additional_benchmarks.py` was reviewed without saving local credentials
- [ ] `python3 04_run_additional_benchmarks.py` was validated with saved probe settings or mocks
- [ ] Documentation was updated if needed.

## Safety and privacy

- [ ] No API keys, passwords, private prompts, private model outputs, or local settings were committed.
- [ ] No generated `results/` or cache files were committed.

## Compatibility notes

Mention any change to commands, settings, result files, prompt banks, grading, or supported servers.
