# Contributing to Senerenai-HyperProbe

Thank you for helping make Senerenai-HyperProbe more useful. You do not need to be a professional developer to contribute. A clear bug report, a documentation correction, a new compatible-server example, a prompt-quality suggestion, or a successful test on another system can all help.

## The simple idea

GitHub lets somebody propose a change without directly changing the main project. They create a copy, make their improvement, and open a **pull request**. A pull request is simply a request saying: “Please review this proposed change and add it if you think it is useful.” The project owner can review it, ask questions, accept it, or decline it.

## Ways to help

| Contribution | What it means |
|---|---|
| Bug report | Explain what command you ran, what happened, and what you expected. Never include API keys. |
| Documentation correction | Fix a typo, unclear sentence, incorrect command, or missing beginner explanation. |
| Compatibility report | Tell us whether the project works with a particular OpenAI-compatible server or operating system. |
| Prompt or grading suggestion | Suggest a better benchmark prompt or a more reliable scoring rule, with an explanation of why it helps. |
| Code change | Fix a defect or add a carefully scoped feature. Include offline tests when possible. |
| Review | Look at an open pull request and explain whether the proposed change is clear and safe. |

## If you are not a developer

The easiest contribution is to open an issue. Use the issue form or write a short description in your own words. Include the operating system, Python version, command used, and the relevant error message. Remove passwords, API keys, private prompts, private model outputs, and personal information before posting.

You can also suggest documentation changes. A maintainer or another contributor can turn the suggestion into the actual file edit.

## If you want to submit a code fix

Fork the repository on GitHub, clone your fork using the lowercase repository path, create a separate branch, make the change, and open a pull request:

```bash
git clone https://github.com/korodexios/senerenai-hyperprobe.git senerenai-hyperprobe
git checkout -b fix-short-description
cd senerenai-hyperprobe
```

Before opening the pull request, run the checks described in the README:

```bash
python3 -m compileall -q .
python3 -m unittest discover -s tests -p 'test_*.py' -q
python3 smoke_check.py
python3 01_setup.py --help
python3 02_run.py --help
```

Do not commit `hyperprobe.local.json`, API credentials, generated `results/`, model outputs containing private information, or environment-specific cache files. Keep changes focused and explain any compatibility or output-format impact.

## Pull-request review

A pull request is a discussion, not a demand. The maintainer may request changes, combine ideas, or decide that a proposal does not fit the project. That is normal open-source collaboration. The goal is to improve the tool, not to make every proposed change mandatory.

Senerenai-HyperProbe is provided under the MIT License and without a warranty. Contributions are shared under the project’s licensing terms unless a contributor explicitly states another arrangement before the change is accepted.
