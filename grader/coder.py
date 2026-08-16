"""
Coder Grader — Sandbox Execution + AST + 7-Dimension Evaluation
================================================================
Scores coding responses on 7 weighted dimensions (0.0–1.0 each),
then combines into a weighted final score (0.0–1.0).

Dimensions:
  1. correctness      (0.28) — actual code execution + test results
  2. completeness     (0.13) — covers all requirements
  3. code_quality      (0.13) — AST analysis: structure, naming, docstrings, type hints
  4. follows_spec      (0.13) — instruction following
  5. no_hallucination  (0.13) — no fake APIs, imports, or AI self-talk
  6. parseable         (0.10) — valid Python syntax
  7. no_repetition     (0.10) — not a looped / degenerate answer (shared detector)
"""

import re
import ast
import json
import subprocess
import tempfile
import os
import time
from dataclasses import dataclass, field

from grader.repetition import detect_degeneration


@dataclass
class GradeResult:
    dimensions: dict = field(default_factory=dict)   # dim_name → 0.0-1.0
    weighted_score: float = 0.0
    flags: list = field(default_factory=list)         # warning strings
    raw_length: int = 0
    code_blocks: int = 0
    exec_result: dict = field(default_factory=dict)


# ── Known real Python libraries (for hallucination detection) ──
REAL_LIBS = {
    'os', 'sys', 'json', 're', 'ast', 'math', 'random', 'time', 'datetime',
    'collections', 'itertools', 'functools', 'typing', 'dataclasses', 'enum',
    'threading', 'multiprocessing', 'queue', 'asyncio', 'socket', 'http',
    'urllib', 'pathlib', 'io', 'abc', 'copy', 'hashlib', 'hmac', 'logging',
    'unittest', 'heapq', 'bisect', 'contextlib', 'concurrent',
    'aiohttp', 'requests', 'flask', 'fastapi', 'pydantic', 'sqlalchemy',
    'numpy', 'pandas', 'redis', 'celery', 'django', 'starlette',
    'textwrap', 'string', 'struct', 'traceback', 'warnings', 'weakref',
    'tempfile', 'shutil', 'glob', 'fnmatch', 'stat', 'csv', 'xml', 'html',
    'email', 'pickle', 'shelve', 'dbm', 'sqlite3', 'zlib', 'gzip', 'bz2',
    'lzma', 'zipfile', 'tarfile', 'configparser', 'argparse', 'getopt',
    'pdb', 'profile', 'cProfile', 'timeit', 'dis', 'inspect', 'importlib',
    'signal', 'select', 'selectors', 'ssl', 'ftplib', 'smtplib', 'poplib',
    'imaplib', 'uuid', 'base64', 'binascii', 'secrets', 'operator',
    'decimal', 'fractions', 'statistics', 'array',
}

# Fake method names commonly hallucinated
FAKE_METHODS = {
    'to_list', 'to_str', 'to_int', 'to_dict', 'to_set',
    'contains', 'size', 'length', 'is_empty', 'to_array',
    'add_all', 'remove_all', 'each', 'map_values',
}


def extract_code_blocks(text: str) -> list[str]:
    """Extract all fenced code blocks from a response."""
    code_pattern = r'```(?:python|py)?\s*\n(.*?)```'
    blocks = re.findall(code_pattern, text, re.DOTALL)
    if blocks:
        return blocks

    # Fallback: response is mostly code without fences
    lines = text.split("\n")
    code_lines = sum(1 for l in lines if re.match(
        r'^(import |from |def |class |    |if |for |while |return |#|@)', l))
    if code_lines > len(lines) * 0.4:
        return [text]
    return []


DISALLOWED_IMPORT_ROOTS = {
    "ctypes", "http", "httplib", "ftplib", "imaplib", "multiprocessing",
    "os", "pathlib", "pickle", "requests", "shutil", "socket", "smtplib",
    "subprocess", "urllib", "webbrowser", "aiohttp",
}
DISALLOWED_CALLS = {"compile", "eval", "exec", "input", "open", "__import__"}


def preflight_code_safety(code: str) -> list[str]:
    """Return static findings that make direct execution unsafe.

    This deliberately conservative gate is not a hardened sandbox. It prevents
    executing obvious process, network, filesystem, and dynamic-evaluation
    patterns during an offline benchmark, while still allowing pure algorithmic
    and concurrency exercises using safe standard-library modules.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    findings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in DISALLOWED_IMPORT_ROOTS:
                    findings.append(f"blocked_import:{root}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in DISALLOWED_IMPORT_ROOTS:
                findings.append(f"blocked_import:{root}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in DISALLOWED_CALLS:
                findings.append(f"blocked_call:{node.func.id}")
    return sorted(set(findings))


def execute_code_safely(code: str, timeout: int = 15) -> dict:
    """Execute only code that passes a conservative AST safety preflight."""
    result = {
        "ran": False, "exit_code": None, "stdout": "", "stderr": "",
        "error_type": None, "tests_found": 0, "tests_passed": 0,
        "assertions_found": 0, "assertions_passed": 0,
    }
    result["assertions_found"] = len(re.findall(r'\bassert\b', code))
    result["tests_found"] = len(re.findall(r'\bdef\s+test_\w+', code))
    findings = preflight_code_safety(code)
    if findings:
        result["error_type"] = "execution_skipped_safety"
        result["stderr"] = "; ".join(findings)
        return result

    tmpfile = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False,
                                          dir=tempfile.gettempdir(),
                                          encoding='utf-8') as f:
            f.write(code)
            f.flush()
            tmpfile = f.name

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            ["python3", "-u", tmpfile],
            capture_output=True, text=True, timeout=timeout,
            cwd=tempfile.gettempdir(), env=env,
        )
        result["ran"] = True
        result["exit_code"] = proc.returncode
        result["stdout"] = proc.stdout[:2000]
        result["stderr"] = proc.stderr[:2000]

        if proc.returncode != 0:
            stderr = proc.stderr
            if "SyntaxError" in stderr:
                result["error_type"] = "syntax_error"
            elif "NameError" in stderr:
                result["error_type"] = "name_error"
            elif "TypeError" in stderr:
                result["error_type"] = "type_error"
            elif "AssertionError" in stderr:
                result["error_type"] = "assertion_error"
            elif "ImportError" in stderr or "ModuleNotFoundError" in stderr:
                result["error_type"] = "import_error"
            elif "RecursionError" in stderr:
                result["error_type"] = "recursion_error"
            elif "AttributeError" in stderr:
                result["error_type"] = "attribute_error"
            elif "IndexError" in stderr or "KeyError" in stderr:
                result["error_type"] = "index_key_error"
            else:
                result["error_type"] = "runtime_error"
            result["assertions_passed"] = max(0, result["assertions_found"] - 1)
        else:
            result["assertions_passed"] = result["assertions_found"]

    except subprocess.TimeoutExpired:
        result["ran"] = True
        result["exit_code"] = -1
        result["error_type"] = "timeout"
        result["stderr"] = f"Execution timed out after {timeout}s"
    except Exception as e:
        result["error_type"] = "execution_failed"
        result["stderr"] = str(e)
    finally:
        if tmpfile:
            try:
                os.unlink(tmpfile)
            except:
                pass

    return result


def _try_parse(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def grade_coder(response: str, prompt_meta: dict) -> GradeResult:
    """Grade a coding response with sandbox execution + AST analysis."""
    result = GradeResult()
    result.raw_length = len(response)
    text = response.strip()

    code_blocks = extract_code_blocks(text)
    result.code_blocks = len(code_blocks)
    all_code = "\n".join(code_blocks) if code_blocks else ""

    # ── 1. Parseable (0.10) ──
    parseable = 0.0
    if all_code:
        try:
            ast.parse(all_code)
            parseable = 1.0
        except SyntaxError:
            good = sum(1 for b in code_blocks if _try_parse(b))
            parseable = good / max(len(code_blocks), 1) * 0.8
    else:
        result.flags.append("no_code_found")
    result.dimensions["parseable"] = parseable

    # ── 2. Correctness (0.28) — execution-based ──
    correctness = 0.0
    if all_code and parseable >= 0.5:
        exec_result = execute_code_safely(all_code, timeout=15)
        result.exec_result = exec_result

        if exec_result["ran"]:
            if exec_result["exit_code"] == 0:
                correctness = 0.6
                if exec_result["assertions_found"] > 0:
                    correctness += 0.25
                if exec_result["stdout"].strip():
                    correctness += 0.10
                if not exec_result["stderr"].strip():
                    correctness += 0.05
            elif exec_result["error_type"] == "import_error":
                correctness = 0.35
                result.flags.append(f"import_error: {exec_result['stderr'][:80]}")
            elif exec_result["error_type"] == "assertion_error":
                correctness = 0.30
                if exec_result["assertions_found"] > 1:
                    pass_ratio = max(0, exec_result["assertions_found"] - 1) / exec_result["assertions_found"]
                    correctness += pass_ratio * 0.15
                result.flags.append("assertion_failed")
            elif exec_result["error_type"] == "timeout":
                correctness = 0.15
                result.flags.append("execution_timeout")
            else:
                correctness = 0.15
                result.flags.append(f"runtime_error: {exec_result['error_type']}")
        else:
            if exec_result["error_type"] == "execution_skipped_safety":
                correctness = 0.30
                result.flags.append(f"execution_skipped_safety:{exec_result['stderr']}")
            else:
                correctness = 0.10
    elif all_code:
        correctness = 0.05

    # Heuristic bonus for structure
    if all_code:
        has_func = bool(re.search(r'\bdef\s+\w+', all_code))
        has_class = bool(re.search(r'\bclass\s+\w+', all_code))
        if has_func or has_class:
            correctness = min(correctness + 0.05, 1.0)
    result.dimensions["correctness"] = min(correctness, 1.0)

    # ── 3. Completeness (0.13) ──
    prompt_lower = prompt_meta.get("prompt", "").lower()
    completeness = 0.0
    checks, hits = 0, 0

    if "class " in prompt_lower:
        checks += 1
        if re.search(r'\bclass\s+\w+', all_code):
            hits += 1

    method_matches = re.findall(r'`(\w+)`\(', prompt_lower)
    func_sigs = re.findall(r'def (\w+)\(', prompt_lower)
    for name in set(m for m in method_matches + func_sigs if m not in ('def', 'class', 'self')):
        checks += 1
        if re.search(rf'\bdef\s+{re.escape(name)}\b', all_code):
            hits += 1

    if "test" in prompt_lower:
        checks += 1
        if len(re.findall(r'\bassert\b', all_code)) > 0:
            hits += 1

    if "raise" in prompt_lower or "error" in prompt_lower or "exception" in prompt_lower:
        checks += 1
        if re.search(r'\braise\b|\bexcept\b', all_code):
            hits += 1

    if checks > 0:
        completeness = hits / checks

    code_lines = len([l for l in all_code.split("\n") if l.strip() and not l.strip().startswith("#")])
    if code_lines > 50:
        completeness = min(completeness + 0.15, 1.0)
    elif code_lines > 25:
        completeness = min(completeness + 0.08, 1.0)
    result.dimensions["completeness"] = min(completeness, 1.0)

    # ── 4. Code Quality (0.13) ──
    quality = 0.0
    if all_code:
        try:
            tree = ast.parse(all_code)
            quality += 0.15  # parseable baseline

            funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
            if len(funcs) >= 2 or len(classes) >= 1:
                quality += 0.10

            # Docstrings
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if (node.body and isinstance(node.body[0], ast.Expr) and
                        isinstance(node.body[0].value, (ast.Constant, ast.Str))):
                        quality += 0.10
                        break

            # Type hints
            has_type_hints = any(
                f.returns is not None or any(a.annotation is not None for a in f.args.args)
                for f in funcs
            )
            if has_type_hints:
                quality += 0.10

            # Short functions
            func_lengths = []
            for f in funcs:
                func_lengths.append(f.end_lineno - f.lineno if hasattr(f, 'end_lineno') else 10)
            if func_lengths:
                avg_len = sum(func_lengths) / len(func_lengths)
                if avg_len < 20:
                    quality += 0.10
                elif avg_len < 40:
                    quality += 0.05

        except SyntaxError:
            pass

        comment_lines = len(re.findall(r'#\s+\w+', all_code))
        if comment_lines >= 3:
            quality += 0.10
        elif comment_lines >= 1:
            quality += 0.05

        if not re.search(r'from \w+ import \*', all_code):
            quality += 0.05

        # Naming conventions
        func_names = re.findall(r'\bdef\s+(\w+)', all_code)
        class_names = re.findall(r'\bclass\s+(\w+)', all_code)
        good_func = sum(1 for n in func_names if re.match(r'^[a-z_]\w*$', n) or n.startswith('__'))
        good_cls = sum(1 for n in class_names if re.match(r'^[A-Z]\w*$', n))
        total_names = len(func_names) + len(class_names)
        if total_names > 0:
            quality += ((good_func + good_cls) / total_names) * 0.10

    result.dimensions["code_quality"] = min(quality, 1.0)

    # ── 5. Follows Spec (0.13) ──
    follows = 0.0
    if result.code_blocks == 0:
        follows = 0.05
    else:
        follows = 0.4  # has code

        code_ratio = len(all_code) / max(len(text), 1)
        if code_ratio > 0.6:
            follows += 0.2
        elif code_ratio > 0.3:
            follows += 0.1

        if re.search(r'\bdef\s|\bclass\s|\bimport\s', all_code):
            follows += 0.15

        imports = re.findall(r'(?:from|import)\s+(\w+)', all_code)
        if len(imports) <= 5:
            follows += 0.10

        if not re.search(r'\b(note that|please note|keep in mind|disclaimer)\b', text, re.IGNORECASE):
            follows += 0.10
    result.dimensions["follows_spec"] = min(follows, 1.0)

    # ── 6. No Hallucination (0.13) ──
    hall_score = 1.0

    # Suspicious imports
    import_lines = re.findall(r'^\s*(?:from|import)\s+(\w+)', all_code, re.MULTILINE)
    for imp in import_lines:
        if imp.lower() not in REAL_LIBS and not imp.startswith('_'):
            hall_score -= 0.08
            result.flags.append(f"suspicious_import:{imp}")

    # Self-referential AI talk
    if re.search(r'\b(as an ai|i am a language model|i cannot)\b', text, re.IGNORECASE):
        hall_score -= 0.15
        result.flags.append("self_referential")

    # Hallucinated methods on built-in types
    hall_methods = re.findall(r'\.(\w+)\(', all_code)
    for m in hall_methods:
        if m in FAKE_METHODS:
            hall_score -= 0.05
            result.flags.append(f"hallucinated_method:{m}")

    result.dimensions["no_hallucination"] = max(hall_score, 0.0)

    # ── 7. No Repetition (0.10) — shared degeneration/loop detector ──
    degen = detect_degeneration(text)
    result.dimensions["no_repetition"] = degen["score"]
    result.flags.extend(degen["flags"])

    # ── Weighted Score ──
    from config import SCORING_WEIGHTS
    weights = SCORING_WEIGHTS["coding"]
    result.weighted_score = sum(
        result.dimensions.get(dim, 0) * w for dim, w in weights.items()
    )
    return result
