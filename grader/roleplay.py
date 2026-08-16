"""Metadata-aware roleplay grader for public persona-fidelity benchmarks."""
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


OOC_PATTERNS = (
    r"\bas an ai\b",
    r"\bas a language model\b",
    r"\bi am an ai\b",
    r"\bi am an assistant\b",
    r"\bi cannot roleplay\b",
    r"\bi don't have feelings\b",
    r"\bmy system prompt\b",
)


def calculate_cross_similarity(text: str, previous_replies: list[str] | None) -> float:
    """Return maximum Jaccard similarity with prior samples for one prompt/combo."""
    if not previous_replies:
        return 0.0
    current = set(re.findall(r"[a-z']+", text.lower()))
    if not current:
        return 0.0
    scores = []
    for previous in previous_replies:
        other = set(re.findall(r"[a-z']+", previous.lower()))
        if other:
            scores.append(len(current & other) / len(current | other))
    return max(scores, default=0.0)


def _term_hits(text: str, terms: list[str]) -> list[str]:
    lower = text.lower()
    return [term for term in terms if term.lower() in lower]


def grade_roleplay(response: str, prompt_meta: dict, prev_replies: list[str] | None = None) -> GradeResult:
    """Score roleplay quality without requiring a fixed expected completion."""
    result = GradeResult(raw_length=len(response))
    text = response.strip()
    lower = text.lower()
    words = re.findall(r"[\w'-]+", text)

    ooc_hits = [pattern for pattern in OOC_PATTERNS if re.search(pattern, lower)]
    result.dimensions["no_ooc"] = 0.0 if ooc_hits else 1.0
    if ooc_hits:
        result.flags.append("out_of_character_language")

    forbidden_hits = _term_hits(text, list(prompt_meta.get("forbidden_terms", [])))
    persona_score = 1.0
    if ooc_hits:
        persona_score -= 0.75
    if forbidden_hits:
        persona_score -= min(0.45, 0.15 * len(forbidden_hits))
        result.flags.append(f"modern_term_drift:{','.join(forbidden_hits)}")
    if "```" in text:
        persona_score -= 0.35
        result.flags.append("code_block_in_roleplay")

    style_markers = list(prompt_meta.get("style_markers", []))
    style_hits = _term_hits(text, style_markers)
    if style_markers and len(words) >= 35 and not style_hits:
        persona_score -= 0.10
        result.flags.append("weak_persona_lexicon")

    if prev_replies:
        similarity = calculate_cross_similarity(text, prev_replies)
        if similarity > 0.65:
            persona_score -= min(0.50, (similarity - 0.55) * 1.5)
            result.flags.append(f"cloned_sample_penalty:{similarity:.2f}")
    result.dimensions["persona_retention"] = max(0.0, round(persona_score, 4))

    required_markers = list(prompt_meta.get("required_markers", []))
    marker_hits = sum(marker in text for marker in required_markers)
    dialogue_signals = sum(marker in text for marker in ('?', '!', '"', '“', '”', '*'))
    engagement = min(1.0, 0.35 + min(len(words), 100) / 200 + dialogue_signals / 10)
    if required_markers:
        engagement *= marker_hits / len(required_markers)
        if marker_hits < len(required_markers):
            result.flags.append("missed_dialogue_constraint")
    result.dimensions["engagement"] = max(0.0, round(engagement, 4))

    min_words = int(prompt_meta.get("min_words", 35))
    result.dimensions["length"] = min(1.0, len(words) / max(min_words, 1))
    if len(words) < min_words:
        result.flags.append(f"short_response:{len(words)}/{min_words}")

    degeneration = detect_degeneration(text)
    result.dimensions["no_repetition"] = degeneration["score"]
    result.flags.extend(degeneration["flags"])
    result.weighted_score = sum(
        result.dimensions.get(name, 0.0) * weight
        for name, weight in SCORING_WEIGHTS["roleplay"].items()
    )
    return result
