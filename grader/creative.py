"""Creative-writing grader based on lexical diversity, coherence, and degeneration."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from grader.repetition import detect_degeneration
from config import SCORING_WEIGHTS
@dataclass
class GradeResult:
    dimensions: dict = field(default_factory=dict)
    weighted_score: float = 0.0
    flags: list = field(default_factory=list)
    raw_length: int = 0

def grade_creative(response: str, prompt_meta: dict, prev_replies: list[str] | None = None) -> GradeResult:
    result = GradeResult(raw_length=len(response)); words = re.findall(r"[\w'-]+", response.lower()); unique = len(set(words))
    result.dimensions['vocab_diversity'] = min(unique / max(len(words), 1) * 2.0, 1.0)
    result.dimensions['creativity'] = min(0.35 + min(len(words), 250) / 500, 1.0) if words else 0.0
    result.dimensions['coherence'] = 1.0 if len(words) >= 25 and response.count('.') + response.count('!') + response.count('?') >= 2 else 0.5 if words else 0.0
    fluff = len(re.findall(r"\b(as an ai|in conclusion|sure, here|certainly)\b", response, re.I))
    result.dimensions['no_fluff'] = max(0.0, 1.0 - fluff * 0.25)
    degen = detect_degeneration(response); result.dimensions['no_repetition'] = degen['score']; result.flags.extend(degen['flags'])
    result.weighted_score = sum(result.dimensions.get(k, 0.0) * v for k, v in SCORING_WEIGHTS['creative'].items())
    return result

def calculate_cross_similarity(text: str, previous: list[str]) -> float:
    a = set(re.findall(r"\w+", text.lower()))
    return max((len(a & set(re.findall(r"\w+", item.lower()))) / max(len(a | set(re.findall(r"\w+", item.lower()))), 1) for item in previous), default=0.0)

def calculate_cross_sample_similarity(text: str, previous: list[str]) -> float:
    return calculate_cross_similarity(text, previous)
