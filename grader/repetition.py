"""
Shared degeneration / repetition-loop detector
=================================================
Used by ALL graders (coding, creative, roleplay) as a dedicated
"no_repetition" scoring dimension. Motivation: a response can score well on
every other axis (persona, vocab, correctness...) while actually being a
looped / near-identical boilerplate answer — a common failure mode at
certain sampling settings (very low temperature combined with a high
repetition_penalty can paradoxically loop between 2-3 alternating phrases;
some combos also just collapse to the same generic answer regardless of the
prompt). That was invisible in the old per-profile grading, this closes the
gap.

Two independent checks are provided:

  detect_degeneration(text)
      Per-RESPONSE check: n-gram loops, repeated lines, low unique-word
      ratio. Feeds a numeric dimension straight into a grader.

  cross_combo_invariance(replies_by_hash)
      Per-PROMPT, cross-COMBO diagnostic (used at analysis/report time, not
      as a per-sample score): flags when many *different* sampling combos
      produced near-identical output for the same prompt. If sampling
      params don't actually change the output, a high score there says
      nothing about which sampling params are good — it says the model is
      stuck in some other way (e.g. the prompt itself over-determines the
      answer, or KV-cache/prompt caching is returning a cached completion).
"""
import re
from collections import Counter


def detect_degeneration(text: str) -> dict:
    """Returns {"score": 0.0-1.0 (1.0 = clean), "flags": [...]}"""
    flags = []
    score = 1.0
    words = text.split()
    if len(words) < 8:
        unique_ratio = len(set(w.lower() for w in words)) / max(len(words), 1)
        if len(words) >= 5 and unique_ratio < 0.4:
            return {"score": 0.0, "flags": [f"short_low_unique_ratio:{unique_ratio:.2f}"]}
        return {"score": 1.0, "flags": []}  # too short to judge meaningfully

    # 1. Exact-line repetition (e.g. same sentence repeated as "paragraphs")
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) >= 4:
        counts = Counter(lines)
        repeated_lines = sum(c - 1 for c in counts.values() if c > 1)
        if repeated_lines >= 2:
            score -= min(0.5, repeated_lines * 0.1)
            flags.append(f"repeated_lines:{repeated_lines}")

    # 2. N-gram loop detection — catches "stuck" generation that alternates
    #    between a couple of phrases (won't show as identical lines).
    lw = [w.lower().strip('.,;:!?"()\'') for w in words]
    for n in (5, 8):
        if len(lw) < n * 3:
            continue
        grams = [" ".join(lw[i:i + n]) for i in range(len(lw) - n + 1)]
        counts = Counter(grams)
        top_gram, top_count = counts.most_common(1)[0]
        if top_count >= 3:
            score -= min(0.6, (top_count - 2) * 0.15)
            flags.append(f"ngram{n}_loop:{top_count}x")

    # 3. Global repetition ratio — low unique-word ratio despite decent length
    if len(lw) > 40:
        unique_ratio = len(set(lw)) / len(lw)
        if unique_ratio < 0.35:
            score -= (0.35 - unique_ratio) * 1.5
            flags.append(f"low_unique_ratio:{unique_ratio:.2f}")

    return {"score": max(0.0, round(score, 4)), "flags": flags}


def cross_combo_invariance(replies_by_hash: dict, similarity_threshold: float = 0.85) -> dict:
    """
    replies_by_hash: {param_hash: [reply_text, ...]}  (for ONE prompt)
    Returns {"invariant": bool, "groups": [[hash, ...], ...], "note": str}
    """
    reps = {ph: texts[0][:400].lower().split() for ph, texts in replies_by_hash.items() if texts}
    hashes = list(reps.keys())
    groups = []
    used = set()
    for i, h1 in enumerate(hashes):
        if h1 in used:
            continue
        group = [h1]
        w1 = set(reps[h1][:60])
        for h2 in hashes[i + 1:]:
            if h2 in used:
                continue
            w2 = set(reps[h2][:60])
            if not w1 or not w2:
                continue
            jacc = len(w1 & w2) / len(w1 | w2)
            if jacc >= similarity_threshold:
                group.append(h2)
                used.add(h2)
        if len(group) > 1:
            groups.append(group)
            used.add(h1)

    invariant = len(groups) > 0 and any(len(g) >= max(3, len(hashes) * 0.4) for g in groups)
    note = ""
    if invariant:
        note = ("The model produced nearly identical replies across different "
                "sampling combinations for this prompt. Sampling may not be the "
                "limiting factor; inspect the prompt or server-side caching.")
    return {"invariant": invariant, "groups": groups, "note": note}
