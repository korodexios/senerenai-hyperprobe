"""Script-aware multilingual quality grader."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from config import SCORING_WEIGHTS
from grader.repetition import detect_degeneration


@dataclass
class GradeResult:
    dimensions: dict = field(default_factory=dict)
    weighted_score: float = 0.0
    flags: list = field(default_factory=list)
    raw_length: int = 0


def calculate_cross_similarity(text: str, previous_replies: list[str] | None) -> float:
    if not previous_replies:
        return 0.0
    words = set(text.lower().split()[:120])
    if not words:
        return 0.0
    similarities = []
    for previous in previous_replies:
        other = set(previous.lower().split()[:120])
        if other:
            similarities.append(len(words & other) / len(words | other))
    return max(similarities, default=0.0)


def _script_count(text: str, script: str) -> int:
    patterns = {
        "latin": r"[A-Za-zÀ-ÖØ-öø-ÿ]",
        "cjk": r"[\u3400-\u9fff]",
        "devanagari": r"[\u0900-\u097f]",
        "arabic": r"[\u0600-\u06ff\u0750-\u077f]",
        "bengali": r"[\u0980-\u09ff]",
        "cyrillic": r"[\u0400-\u04ff]",
        "japanese": r"[\u3040-\u30ff\u3400-\u9fff]",
        "hangul": r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]",
    }
    return len(re.findall(patterns.get(script, r"$^"), text))


def _foreign_script_count(text: str, expected_script: str, forbidden: list[str]) -> int:
    return sum(_script_count(text, script) for script in forbidden if script != expected_script)


def grade_custom_lang(response: str, prompt_meta: dict, prev_replies: list[str] | None = None) -> GradeResult:
    """Evaluate language presence, script fidelity, leakage, coherence, and repetition."""
    result = GradeResult(raw_length=len(response))
    text = response.strip()
    words = [word for word in re.findall(r"\S+", text) if len(word) > 1]
    expected_script = prompt_meta.get("expected_script", "latin")
    language = prompt_meta.get("language", "unknown")
    script_chars = _script_count(text, expected_script)
    foreign_chars = _foreign_script_count(text, expected_script, prompt_meta.get("foreign_scripts", []))

    if not text:
        result.flags.append("empty_response")
    if script_chars == 0 and len(words) >= 4:
        result.flags.append(f"missing_expected_script:{expected_script}")
    result.dimensions["language_quality"] = 1.0 if script_chars >= max(3, len(words) // 4) else 0.35 if script_chars else 0.0

    if foreign_chars:
        result.flags.append(f"foreign_script_leak:{foreign_chars}")
    result.dimensions["no_foreign_leaks"] = max(0.0, 1.0 - min(1.0, foreign_chars / max(len(text), 1) * 8))

    expected_marks = prompt_meta.get("expected_diacritics", "")
    if expected_marks and len(words) >= 12:
        mark_count = sum(text.lower().count(mark.lower()) for mark in expected_marks)
        result.dimensions["diacritics_accuracy"] = 1.0 if mark_count >= 2 else 0.55 if mark_count else 0.25
        if mark_count == 0:
            result.flags.append("missing_expected_diacritics")
    else:
        result.dimensions["diacritics_accuracy"] = 1.0

    result.dimensions["coherence"] = 1.0 if len(words) >= 18 else max(0.25, len(words) / 18.0)

    if prev_replies:
        similarity = calculate_cross_similarity(text, prev_replies)
        if similarity > 0.70:
            result.flags.append(f"cloned_sample_penalty:{similarity:.2f}")
            result.dimensions["language_quality"] *= max(0.0, 1.0 - (similarity - 0.70) * 2)

    degeneration = detect_degeneration(text)
    result.dimensions["no_repetition"] = degeneration["score"]
    result.flags.extend(degeneration["flags"])
    result.flags.append(f"language:{language}")
    result.weighted_score = sum(result.dimensions.get(name, 0.0) * weight for name, weight in SCORING_WEIGHTS["custom_lang"].items())
    return result
