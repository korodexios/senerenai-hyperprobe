"""Generate readable, self-contained HTML dashboards for Senerenai-HyperProbe.

The dashboard separates sampler tuning from refusal and long-context probes.
It intentionally presents a plain-language conclusion before technical evidence.
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from html import escape
from pathlib import Path
from typing import Any

from common import format_duration

RESULTS_DIR = Path(__file__).parent / "results"
DASH_DIR = RESULTS_DIR / "dashboards"
DASH_DIR.mkdir(parents=True, exist_ok=True)

DEGEN_FLAG_PREFIXES = ("ngram5_loop", "ngram8_loop", "repeated_lines", "low_unique_ratio")
PROF_ICONS = {
    "coding": "Coding",
    "agent_tools": "Agent tools",
    "creative": "Creative",
    "roleplay": "Roleplay",
    "custom_lang": "Custom language",
    "safety_refusal": "Refusal",
    "long_context": "Long context",
}
PHASE_LABELS = {
    "stage1": "Stage 1 — screening",
    "stage2": "Stage 2 — refinement",
    "stage3": "Stage 3 — stability",
    "probe_refusal": "Refusal & companion",
    "probe_niah": "NIAH long context",
    "quickscan": "Quickscan (legacy)",
    "sweep": "Sweep (legacy)",
    "focused": "Focused (legacy)",
}
CORE_PROFILES = {"coding", "agent_tools", "creative", "roleplay", "custom_lang"}


def model_safe_name(model: str) -> str:
    """Create a filesystem-safe model label."""
    return model.replace("/", "_").replace("\\", "_")


def split_display_model(model: str) -> tuple[str, str | None]:
    """Separate a model ID from an optional dashboard-only label."""
    marker = " ["
    if marker in model and model.endswith("]"):
        base, label = model.rsplit(marker, 1)
        return base, label[:-1]
    return model, None


def dashboard_filename(model: str) -> str:
    base, label = split_display_model(model)
    suffix = "_" + model_safe_name(label.lower()).replace(" ", "-") if label else ""
    return f"dashboard_{model_safe_name(base)}{suffix}.html"


def load_all_data() -> list[dict[str, Any]]:
    """Load valid JSONL records stored at the project results root."""
    records: list[dict[str, Any]] = []
    for path in RESULTS_DIR.glob("*.jsonl"):
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "phase" not in record or "model" not in record:
                    parts = path.stem.split("_")
                    record.setdefault("phase", parts[0] if parts else "unknown")
                    if "model" not in record:
                        profile = record.get("profile", "")
                        prefix = f"{record['phase']}_{profile}_"
                        record["model"] = path.stem[len(prefix):] if path.stem.startswith(prefix) else "unknown_model"
                records.append(record)
    return records


def benchmark_variant(record: dict[str, Any]) -> str:
    """Keep methodology variants separate while avoiding internal labels in filenames."""
    if str(record.get("phase", "")).startswith("probe_"):
        return "Current benchmark"
    internal = str(record.get("search_design") or "legacy")
    labels = {
        "legacy": "Older results",
        "hybrid_v1": "Earlier benchmark",
        "hybrid_v4": "Previous benchmark",
        "hybrid_v5": "Current benchmark",
    }
    return labels.get(internal, "Previous benchmark" if internal.startswith("hybrid_") else "Older results")


def group_by_model(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group records by model and methodology label."""
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    variants = {benchmark_variant(record) for record in records}
    show_variant = len(variants) > 1
    for record in records:
        model = str(record.get("model", "unknown_model"))
        label = f"{model} [{benchmark_variant(record)}]" if show_variant else model
        by_model[label].append(record)
    return by_model


def calculate_stats(scores: list[float]) -> dict[str, float | int]:
    if not scores:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "n": 0}
    mean_value = sum(scores) / len(scores)
    variance = sum((score - mean_value) ** 2 for score in scores) / len(scores)
    return {
        "mean": round(mean_value, 4),
        "std": round(math.sqrt(variance), 4),
        "min": round(min(scores), 4),
        "max": round(max(scores), 4),
        "n": len(scores),
    }


def _nested_probe_track() -> dict[str, Any]:
    return {"attempted": 0, "errors": 0, "manual_review": 0, "scores": [], "flags": Counter(), "expected": Counter()}


def run_deep_analysis(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Build independent sampler and probe aggregates from local JSONL records.

    A refusal row marked manual review is intentionally excluded from automated
    probe scores. It remains visible as a count and an audit requirement.
    """
    by_phase_prof_hash_scores: dict[str, Any] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    by_phase_prof_hash_elapsed: dict[str, Any] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    by_prof_hash_dims: dict[str, Any] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    hash_params: dict[str, dict[str, Any]] = {}
    param_impact: dict[str, Any] = defaultdict(lambda: defaultdict(list))
    param_dim_impact: dict[str, Any] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    param_flags: dict[str, Any] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    prompt_matrix: dict[str, Any] = defaultdict(lambda: defaultdict(list))
    language_scores: dict[str, list[float]] = defaultdict(list)
    run_record_counts: dict[str, int] = defaultdict(int)
    failed_records_by_run: dict[str, int] = defaultdict(int)
    run_details: dict[str, dict[str, Any]] = {}
    run_sequence = 0
    combo_degen_hits: dict[str, int] = defaultdict(int)
    combo_degen_total: dict[str, int] = defaultdict(int)
    combo_degen_examples: dict[str, list[str]] = defaultdict(list)
    phases_seen: set[str] = set()
    backend_labels: set[str] = set()
    declared_capabilities: set[str] = set()
    probe_scores: dict[str, Any] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    probe_tracks: dict[str, Any] = defaultdict(lambda: defaultdict(lambda: defaultdict(_nested_probe_track)))
    raw_output_paths: set[str] = set()

    for record in records:
        grade = record.get("grade")
        if not isinstance(grade, dict) or "weighted_score" not in grade:
            continue
        phase = str(record.get("phase", "unknown"))
        profile = str(record.get("profile", "unknown"))
        params = record.get("params") if isinstance(record.get("params"), dict) else {}
        score = float(grade.get("weighted_score", 0.0))
        elapsed = float(record.get("elapsed", 0.0) or 0.0)
        flags = [str(flag) for flag in grade.get("flags", [])]
        dimensions = grade.get("dimensions") if isinstance(grade.get("dimensions"), dict) else {}
        run_id = str(record.get("run_id", "legacy-record"))
        run_key = str(record.get("benchmark_id") or run_id)
        if run_key not in run_details:
            run_sequence += 1
            run_details[run_key] = {
                "label": f"Benchmark run {run_sequence}" if record.get("benchmark_id") else f"Legacy run {run_sequence}",
                "benchmark_id": record.get("benchmark_id"),
                "run_ids": set(),
                "phases": set(),
                "profiles": set(),
            }
        run_details[run_key]["run_ids"].add(run_id)
        run_details[run_key]["phases"].add(phase)
        run_details[run_key]["profiles"].add(profile)
        run_record_counts[run_key] += 1
        phases_seen.add(phase)
        backend_labels.add(str(record.get("backend_label", "legacy/unspecified")))
        declared_capabilities.update(str(item) for item in record.get("declared_sampler_capabilities", []) if item)

        is_failed = not dimensions
        if phase.startswith("probe_"):
            if record.get("raw_output_path"):
                raw_output_paths.add(str(record["raw_output_path"]))
            preset = str(record.get("preset_label", "unspecified"))
            track = str(record.get("track", "overall"))
            bucket = probe_tracks[phase][preset][track]
            bucket["attempted"] += 1
            bucket["expected"][str(record.get("expected_behavior", "not recorded"))] += 1
            bucket["flags"].update(flags)
            manual = bool(record.get("manual_review", False)) or bool(grade.get("manual_review", False)) or not bool(grade.get("scored", True))
            if is_failed:
                bucket["errors"] += 1
                failed_records_by_run[run_key] += 1
            elif manual:
                bucket["manual_review"] += 1
            else:
                bucket["scores"].append(score)
                probe_scores[phase][preset][track].append(score)
            continue

        if is_failed:
            failed_records_by_run[run_key] += 1
            continue

        param_hash = str(record.get("param_hash", "untracked"))
        hash_params[param_hash] = params
        by_phase_prof_hash_scores[phase][profile][param_hash].append(score)
        if elapsed > 0:
            by_phase_prof_hash_elapsed[phase][profile][param_hash].append(elapsed)
        prompt_id = str(record.get("prompt_id", "unknown"))
        prompt_matrix[f"{profile} :: {prompt_id}"][param_hash].append(score)
        language = record.get("language")
        if language:
            language_scores[str(language)].append(score)
        for dimension_name, dimension_value in dimensions.items():
            by_prof_hash_dims[profile][param_hash][dimension_name].append(float(dimension_value))
        for parameter_name, parameter_value in params.items():
            param_impact[parameter_name][parameter_value].append(score)
            for dimension_name, dimension_value in dimensions.items():
                param_dim_impact[parameter_name][parameter_value][dimension_name].append(float(dimension_value))
            for flag_name in (flag.split(":")[0] for flag in flags):
                param_flags[parameter_name][parameter_value][flag_name] += 1
        combo_degen_total[param_hash] += 1
        degen_flags = [flag for flag in flags if flag.split(":")[0] in DEGEN_FLAG_PREFIXES]
        if degen_flags:
            combo_degen_hits[param_hash] += 1
            if len(combo_degen_examples[param_hash]) < 3:
                combo_degen_examples[param_hash].append(degen_flags[0])

    return {
        "by_phase_prof_hash_scores": by_phase_prof_hash_scores,
        "by_phase_prof_hash_elapsed": by_phase_prof_hash_elapsed,
        "by_prof_hash_dims": by_prof_hash_dims,
        "hash_params": hash_params,
        "param_impact": param_impact,
        "param_dim_impact": param_dim_impact,
        "param_flags": param_flags,
        "prompt_matrix": prompt_matrix,
        "language_scores": language_scores,
        "run_record_counts": run_record_counts,
        "failed_records_by_run": failed_records_by_run,
        "run_details": run_details,
        "combo_degen_hits": combo_degen_hits,
        "combo_degen_total": combo_degen_total,
        "combo_degen_examples": combo_degen_examples,
        "phases_seen": phases_seen,
        "backend_labels": backend_labels,
        "declared_capabilities": declared_capabilities,
        "probe_scores": probe_scores,
        "probe_tracks": probe_tracks,
        "raw_output_paths": sorted(raw_output_paths),
    }


def generate_specialized_presets(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Create practical core-benchmark preset views without using probe records."""
    by_scores = analysis["by_phase_prof_hash_scores"]
    by_elapsed = analysis["by_phase_prof_hash_elapsed"]
    params_by_hash = analysis["hash_params"]
    pooled_scores: dict[str, Any] = defaultdict(lambda: defaultdict(list))
    pooled_elapsed: dict[str, Any] = defaultdict(lambda: defaultdict(list))
    for phase, profiles in by_scores.items():
        if phase.startswith("probe_"):
            continue
        for profile, hashes in profiles.items():
            if profile not in CORE_PROFILES:
                continue
            for param_hash, scores in hashes.items():
                pooled_scores[profile][param_hash].extend(scores)
        for profile, hashes in by_elapsed.get(phase, {}).items():
            if profile not in CORE_PROFILES:
                continue
            for param_hash, elapsed in hashes.items():
                pooled_elapsed[profile][param_hash].extend(elapsed)

    all_hashes = {param_hash for hashes in pooled_scores.values() for param_hash in hashes}
    presets: list[dict[str, Any]] = []
    for param_hash in all_hashes:
        profile_stats = []
        elapsed_values: list[float] = []
        for profile, hashes in pooled_scores.items():
            if param_hash in hashes and hashes[param_hash]:
                profile_stats.append(calculate_stats(hashes[param_hash]))
            elapsed_values.extend(pooled_elapsed.get(profile, {}).get(param_hash, []))
        if not profile_stats:
            continue
        average_mean = sum(float(stats["mean"]) for stats in profile_stats) / len(profile_stats)
        average_std = sum(float(stats["std"]) for stats in profile_stats) / len(profile_stats)
        minimum = min(float(stats["min"]) for stats in profile_stats)
        average_elapsed = sum(elapsed_values) / len(elapsed_values) if elapsed_values else 0.0
        logic_profiles = [profile for profile in ("coding", "agent_tools", "custom_lang") if param_hash in pooled_scores.get(profile, {})]
        story_profiles = [profile for profile in ("creative", "roleplay") if param_hash in pooled_scores.get(profile, {})]
        logic_means = [float(calculate_stats(pooled_scores[profile][param_hash])["mean"]) for profile in logic_profiles]
        story_means = [float(calculate_stats(pooled_scores[profile][param_hash])["mean"]) for profile in story_profiles]
        presets.append({
            "param_hash": param_hash,
            "params": params_by_hash.get(param_hash, {}),
            "average_mean": round(average_mean, 4),
            "average_std": round(average_std, 4),
            "minimum": round(minimum, 4),
            "average_elapsed": round(average_elapsed, 2),
            "balanced": round(average_mean * 0.65 + minimum * 0.25 - average_std * 0.10, 4),
            "logic": round(sum(logic_means) / len(logic_means), 4) if logic_means else 0.0,
            "stories": round(sum(story_means) / len(story_means), 4) if story_means else 0.0,
        })
    return presets


BASE_CSS = """
:root { --bg:#0b1220; --panel:#121c2d; --panel-2:#17243a; --text:#edf4ff; --muted:#9db0c8; --border:#2b3b55; --primary:#53c7f2; --green:#58d68d; --yellow:#ffd166; --red:#ff7b7b; --purple:#a78bfa; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; line-height:1.45; }
 .header { background:linear-gradient(135deg,var(--panel),#0f1a2c); border-bottom:1px solid var(--border); padding:20px clamp(18px,4vw,46px); display:flex; flex-direction:column; gap:14px; }
.header-main { width:100%; min-width:0; }
.header-title-row { display:flex; align-items:baseline; gap:10px; min-width:0; }
.header-kicker { color:var(--muted); font-size:11px; font-weight:800; letter-spacing:.12em; text-transform:uppercase; white-space:nowrap; }
 .header h1 { min-width:0; margin:0; color:var(--primary); font-size:clamp(19px,2.2vw,27px); line-height:1.2; overflow-wrap:break-word; word-break:normal; }

.header-subtitle { margin-top:7px; color:var(--muted); font-size:13px; max-width:760px; }
 .header-side { width:100%; display:flex; flex-direction:row; align-items:center; justify-content:space-between; gap:12px 20px; }
.header-back { color:var(--primary); text-decoration:none; font-weight:700; font-size:13px; white-space:nowrap; }
.header-meta { flex:1 1 auto; display:flex; justify-content:flex-end; align-items:center; flex-wrap:wrap; gap:5px; }

.header-meta .badge { margin:0; max-width:100%; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.header-meta .meta-wide { max-width:360px; }
.header a { color:var(--primary); text-decoration:none; }

.container { max-width:1440px; margin:0 auto; padding:24px clamp(16px,3vw,30px) 54px; }
.tabs { position:sticky; top:0; z-index:5; display:flex; overflow-x:auto; gap:2px; background:var(--bg); border-bottom:1px solid var(--border); margin:0 -2px 24px; }
.tab-btn { background:none; border:0; border-bottom:3px solid transparent; color:var(--muted); cursor:pointer; padding:14px 18px; font-weight:700; font-size:14px; white-space:nowrap; }
.tab-btn:hover,.tab-btn.active { color:var(--primary); border-bottom-color:var(--primary); }
.tab-content { display:none; }
.tab-content.active { display:block; }
.grid-2 { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; margin:18px 0; }
.grid-3 { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:15px; margin:18px 0; }
.grid-4 { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; margin:18px 0; }
.preset-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:15px; margin:18px 0; }
.card { background:var(--panel); border:1px solid var(--border); border-radius:12px; padding:18px; box-shadow:0 8px 25px rgba(0,0,0,.13); }
.card h2,.card h3 { margin:0 0 10px; color:var(--primary); font-size:16px; }
.section-title { margin:30px 0 12px; color:var(--primary); font-size:20px; font-weight:800; letter-spacing:.02em; }
.metric-label { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.06em; }
.metric-value { margin-top:4px; color:var(--text); font-size:27px; font-weight:800; }
.metric-sub { color:var(--muted); font-size:12px; margin-top:4px; }
.badge { display:inline-block; border:1px solid var(--border); border-radius:999px; padding:3px 8px; color:var(--muted); font-size:12px; margin:2px; }
.badge.good { color:#092616; background:var(--green); border-color:var(--green); }
.badge.warn { color:#362800; background:var(--yellow); border-color:var(--yellow); }
.badge.bad { color:#3d0d0d; background:var(--red); border-color:var(--red); }
.callout { border-left:4px solid var(--primary); background:var(--panel-2); border-radius:8px; padding:14px 16px; margin:14px 0; }
.callout.good { border-left-color:var(--green); }
.callout.warn { border-left-color:var(--yellow); }
.callout.bad { border-left-color:var(--red); }
.callout b { color:var(--text); }
.note,.empty-note { color:var(--muted); font-size:13px; }
table { width:100%; border-collapse:collapse; font-size:13px; margin-top:10px; }
th,td { padding:10px; border-bottom:1px solid var(--border); text-align:left; vertical-align:top; }
th { color:var(--muted); text-transform:uppercase; font-size:11px; letter-spacing:.05em; background:#0d1727; }
tr:hover td { background:rgba(255,255,255,.02); }
pre { margin:9px 0 0; padding:11px; border-radius:8px; overflow-x:auto; background:#0a1220; color:#dcecff; font-size:12px; }
.score-cell { min-width:150px; }
.score-number { font-weight:800; white-space:nowrap; }
.metric-bar { height:10px; margin-top:5px; border-radius:999px; overflow:hidden; background:#020712; border:1px solid #263854; }
.metric-bar > span { height:100%; display:block; min-width:2px; border-radius:999px; }
.fill-good { background:var(--green); } .fill-warn { background:var(--yellow); } .fill-bad { background:var(--red); }
.chart { width:100%; overflow-x:auto; margin-top:8px; }
.chart svg { min-width:540px; width:100%; height:auto; display:block; }
.chart-label { fill:#c8d7ed; font-size:12px; } .chart-value { fill:#9db0c8; font-size:11px; } .chart-grid { stroke:#2b3b55; stroke-width:1; }
.details { margin:14px 0; border:1px solid var(--border); border-radius:10px; background:var(--panel); }
.details summary { cursor:pointer; padding:13px 15px; color:var(--primary); font-weight:700; }
.details > div { padding:0 15px 15px; }
 .param { display:inline-block; margin:2px 3px 2px 0; border-radius:5px; padding:2px 6px; font:11px ui-monospace,SFMono-Regular,Menlo,monospace; background:#24344e; color:#dcecff; }
.subtabs { display:flex; gap:7px; flex-wrap:wrap; margin:10px 0 14px; border-bottom:1px solid var(--border); padding-bottom:9px; }
.subtab-btn { border:1px solid var(--border); border-radius:999px; background:#0d1727; color:var(--muted); padding:7px 11px; cursor:pointer; font-weight:700; font-size:12px; }
.subtab-btn:hover,.subtab-btn.active { background:#213752; color:var(--primary); border-color:var(--primary); }
.subtab-content { display:none; } .subtab-content.active { display:block; }
.stage-card { border-top:4px solid var(--primary); } .stage-card.stage1 { border-top-color:#60a5fa; } .stage-card.stage2 { border-top-color:#fbbf24; } .stage-card.stage3 { border-top-color:#a78bfa; }
.stage-label { font-size:12px; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }
.stage1-text { color:#93c5fd; } .stage2-text { color:#fcd34d; } .stage3-text { color:#c4b5fd; }
.pipeline { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin:18px 0; }
.pipeline-arrow { display:none; }
@media (max-width:900px) { .grid-4,.grid-3 { grid-template-columns:repeat(2,minmax(0,1fr)); } .grid-2,.pipeline { grid-template-columns:1fr; } }
@media (max-width:900px) { .header-side { align-items:flex-start; flex-direction:column; } .header-meta { justify-content:flex-start; width:100%; } }
@media (max-width:540px) { .grid-4,.grid-3 { grid-template-columns:1fr; } .header { padding:17px 16px; gap:13px; } .header-title-row { display:block; } .header-kicker { display:block; margin-bottom:5px; } .header-side { min-width:0; width:100%; } .header-meta { width:100%; } .header-meta .badge { max-width:100%; } .tab-btn { padding:12px 14px; } }
"""

TABLE_JS = """
function openTab(event, tabId) {
  document.querySelectorAll('.tab-content').forEach(function(node) { node.classList.remove('active'); });
  document.querySelectorAll('.tab-btn').forEach(function(node) { node.classList.remove('active'); });
  document.getElementById(tabId).classList.add('active');
  event.currentTarget.classList.add('active');
}
function openSubtab(event, groupId, tabId) {
  var group = document.getElementById(groupId);
  if (!group) return;
  group.querySelectorAll('.subtab-content').forEach(function(node) { node.classList.remove('active'); });
  group.querySelectorAll('.subtab-btn').forEach(function(node) { node.classList.remove('active'); });
  var target = document.getElementById(tabId);
  if (target) target.classList.add('active');
  event.currentTarget.classList.add('active');
}
"""


def score_class(value: float) -> str:
    if value >= 0.85:
        return "good"
    if value >= 0.70:
        return "warn"
    return "bad"


def score_band(value: float) -> tuple[str, str]:
    if value >= 0.90:
        return "strong automated agreement", "good"
    if value >= 0.75:
        return "mixed; inspect weaker tracks", "warn"
    return "inconsistent; inspect raw replies", "bad"


def parameter_badges(params: dict[str, Any]) -> str:
    if not params:
        return "<span class='note'>Not recorded</span>"
    return " ".join(
        f"<span class='param'>{escape(str(key))}={escape(str(value))}</span>" for key, value in params.items()
    )


def dimension_badges(dimensions: dict[str, float]) -> str:
    """Render grader dimensions as color-coded diagnostic evidence."""
    if not dimensions:
        return "<span class='note'>Not recorded</span>"
    return " ".join(
        f"<span class='badge {score_class(float(value))}'>{escape(str(name))}={float(value):.2f}</span>"
        for name, value in sorted(dimensions.items())
    )


def score_bar(value: float | None, label: str | None = None) -> str:
    if value is None:
        return "<span class='note'>Manual review only</span>"
    bounded = max(0.0, min(1.0, value))
    percentage = bounded * 100
    text = label if label is not None else f"{percentage:.1f}%"
    klass = score_class(bounded)
    return (
        f"<div class='score-cell'><span class='score-number'>{escape(text)}</span>"
        f"<div class='metric-bar'><span class='fill-{klass}' style='width:{percentage:.2f}%'></span></div></div>"
    )


def svg_bar_chart(rows: list[tuple[str, float, str]], title: str) -> str:
    """Render a dependency-free horizontal SVG bar chart on a 0–100% scale."""
    if not rows:
        return "<div class='empty-note'>No automated rows are available for this chart.</div>"
    height = 48 + len(rows) * 34
    parts = [f"<div class='chart' role='img' aria-label='{escape(title)}'><svg viewBox='0 0 760 {height}'>"]
    for x, label in ((230, "0%"), (430, "50%"), (630, "100%")):
        parts.append(f"<line x1='{x}' y1='24' x2='{x}' y2='{height - 16}' class='chart-grid'></line>")
        parts.append(f"<text x='{x}' y='16' text-anchor='middle' class='chart-value'>{label}</text>")
    for index, (name, value, color_class) in enumerate(rows):
        y = 38 + index * 34
        percent = max(0.0, min(1.0, value))
        color = {"good": "#58d68d", "warn": "#ffd166", "bad": "#ff7b7b"}[color_class]
        width = percent * 400
        label = name if len(name) <= 29 else name[:28] + "…"
        parts.append(f"<text x='218' y='{y + 12}' text-anchor='end' class='chart-label'>{escape(label)}</text>")
        parts.append(f"<rect x='230' y='{y}' width='400' height='16' rx='8' fill='#020712'></rect>")
        parts.append(f"<rect x='230' y='{y}' width='{width:.1f}' height='16' rx='8' fill='{color}'></rect>")
        parts.append(f"<text x='642' y='{y + 12}' class='chart-value'>{percent * 100:.1f}%</text>")
    parts.append("</svg></div>")
    return "".join(parts)


def profile_winners(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    winners: list[dict[str, Any]] = []
    by_scores = analysis["by_phase_prof_hash_scores"]
    by_elapsed = analysis["by_phase_prof_hash_elapsed"]
    for profile in sorted(CORE_PROFILES):
        pooled: dict[str, list[float]] = defaultdict(list)
        elapsed: dict[str, list[float]] = defaultdict(list)
        for phase, profiles in by_scores.items():
            for param_hash, scores in profiles.get(profile, {}).items():
                pooled[param_hash].extend(scores)
                elapsed[param_hash].extend(by_elapsed.get(phase, {}).get(profile, {}).get(param_hash, []))
        if not pooled:
            continue
        best_hash = max(pooled, key=lambda key: calculate_stats(pooled[key])["mean"])
        stats = calculate_stats(pooled[best_hash])
        winners.append({
            "profile": profile,
            "params": analysis["hash_params"].get(best_hash, {}),
            "stats": stats,
            "elapsed": round(sum(elapsed[best_hash]) / len(elapsed[best_hash]), 2) if elapsed[best_hash] else 0.0,
        })
    return winners


def refusal_preset_summary(tracks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    automated_scores: list[float] = []
    automated_count = 0
    manual_count = 0
    errors = 0
    for bucket in tracks.values():
        automated_scores.extend(bucket["scores"])
        automated_count += len(bucket["scores"])
        manual_count += int(bucket["manual_review"])
        errors += int(bucket["errors"])
    stats = calculate_stats(automated_scores)
    return {
        "score": float(stats["mean"]) if automated_scores else None,
        "scored_items": automated_count,
        "manual_items": manual_count,
        "errors": errors,
        "attempted": sum(int(bucket["attempted"]) for bucket in tracks.values()),
    }


def build_refusal_tab(analysis: dict[str, Any]) -> str:
    probes = analysis["probe_tracks"].get("probe_refusal", {})
    if not probes:
        return ""
    html = ["<div id='tab-refusal' class='tab-content'><div class='section-title'>Refusal & companion results</div>"]
    html.append("<div class='callout'><b>What this score means.</b> It is the average result of transparent, dataset-defined checks: expected behaviour, required concepts, and simple refusal/support signals. It is not a universal safety score and it does not prove that a single answer was objectively correct or incorrect.</div>")
    if analysis.get("raw_output_paths"):
        raw_links = []
        for raw_path in analysis["raw_output_paths"]:
            relative = raw_path.replace("results/", "../", 1)
            raw_links.append(f"<a href='{escape(relative)}' style='color:var(--primary)'>{escape(raw_path)}</a>")
        html.append("<div class='callout good'><b>Complete replies available.</b> The full cleaned replies are stored locally in the raw audit file. Open it when reviewing individual cases or giving the results to another LLM: " + ", ".join(raw_links) + "</div>")
    for preset, tracks in sorted(probes.items()):
        summary = refusal_preset_summary(tracks)
        if summary["score"] is None:
            band, klass = "no automated rows", "warn"
            score_display = "—"
        else:
            band, klass = score_band(float(summary["score"]))
            score_display = f"{float(summary['score']) * 100:.1f}%"
        html.append(f"<div class='card' style='margin-top:18px'><h2>Sampler preset: {escape(preset)}</h2>")
        html.append("<div class='grid-4'>")
        html.append(f"<div><div class='metric-label'>Automated agreement</div><div class='metric-value'>{score_display}</div><div class='metric-sub'><span class='badge {klass}'>{escape(band)}</span></div></div>")
        html.append(f"<div><div class='metric-label'>Automatically scored</div><div class='metric-value'>{summary['scored_items']}</div><div class='metric-sub'>Only non-manual, valid responses</div></div>")
        html.append(f"<div><div class='metric-label'>Manual review</div><div class='metric-value'>{summary['manual_items']}</div><div class='metric-sub'>Visible, but excluded from the headline score</div></div>")
        html.append(f"<div><div class='metric-label'>Request errors</div><div class='metric-value'>{summary['errors']}</div><div class='metric-sub'>{summary['attempted']} attempted rows</div></div>")
        html.append("</div>")
        chart_rows = []
        for track_name, bucket in tracks.items():
            if bucket["scores"]:
                chart_rows.append((track_name, float(calculate_stats(bucket["scores"])["mean"]), score_class(float(calculate_stats(bucket["scores"])["mean"]))))
        chart_rows.sort(key=lambda item: item[1])
        html.append("<h3>Track comparison</h3>")
        html.append(svg_bar_chart(chart_rows, f"Refusal track scores for {preset}"))
        html.append("<div class='note'>Lower tracks identify where the model least often met this dataset’s expected behaviour. Read them as investigation priorities, not as a direct instruction to make the model more or less restrictive.</div>")
        html.append("<table><thead><tr><th>Track</th><th>Expected behaviour</th><th>Automated score</th><th>Auto-scored</th><th>Manual review</th><th>Signals to inspect</th></tr></thead><tbody>")
        rows = []
        for track_name, bucket in tracks.items():
            stats = calculate_stats(bucket["scores"])
            score = float(stats["mean"]) if bucket["scores"] else None
            expected = ", ".join(f"{name} ×{count}" for name, count in sorted(bucket["expected"].items()))
            flags = [flag for flag, _count in bucket["flags"].most_common(3) if flag not in {"manual_review", "not_in_automated_headline_score"}]
            rows.append((score if score is not None else 2.0, track_name, bucket, expected, ", ".join(flags) if flags else "—"))
        for _sort, track_name, bucket, expected, flags in sorted(rows):
            stats = calculate_stats(bucket["scores"])
            value = float(stats["mean"]) if bucket["scores"] else None
            html.append("<tr>"
                        f"<td><b>{escape(track_name)}</b></td>"
                        f"<td>{escape(expected)}</td>"
                        f"<td>{score_bar(value)}</td>"
                        f"<td>{len(bucket['scores'])}</td>"
                        f"<td>{bucket['manual_review']}</td>"
                        f"<td>{escape(flags)}</td></tr>")
        html.append("</tbody></table>")
        if summary["manual_items"]:
            html.append("<div class='callout warn'><b>Manual-review rule.</b> The headline result excludes these rows because their expected behaviour is intentionally ambiguous. Review their reply previews or raw JSONL records separately; do not treat them as automatic passes or failures.</div>")
        html.append("</div>")
    html.append("</div>")
    return "".join(html)


def build_niah_tab(analysis: dict[str, Any]) -> str:
    probes = analysis["probe_tracks"].get("probe_niah", {})
    if not probes:
        return ""
    html = ["<div id='tab-niah' class='tab-content'><div class='section-title'>NIAH long-context results</div>"]
    html.append("<div class='callout'><b>What this measures.</b> NIAH is an exact-retrieval diagnostic at the tested context sizes and positions. It does not by itself measure general reasoning or the full usable context window.</div>")
    for preset, tracks in sorted(probes.items()):
        summary = refusal_preset_summary(tracks)
        score = summary["score"]
        html.append(f"<div class='card'><h2>Sampler preset: {escape(preset)}</h2>")
        html.append(f"<div class='grid-3'><div><div class='metric-label'>Automated retrieval score</div><div class='metric-value'>{'—' if score is None else f'{score * 100:.1f}%'}</div></div><div><div class='metric-label'>Scored cases</div><div class='metric-value'>{summary['scored_items']}</div></div><div><div class='metric-label'>Request errors</div><div class='metric-value'>{summary['errors']}</div></div></div>")
        rows = [(track, float(calculate_stats(bucket["scores"])["mean"]), score_class(float(calculate_stats(bucket["scores"])["mean"]))) for track, bucket in tracks.items() if bucket["scores"]]
        html.append(svg_bar_chart(sorted(rows, key=lambda item: item[1]), f"NIAH retrieval scores for {preset}"))
        html.append("</div>")
    html.append("</div>")
    return "".join(html)


STAGE_DESCRIPTIONS = {
    "stage1": "Broad screening: compare many combinations to identify meaningful parameter regions. A Stage 1 winner is a candidate, not a final recommendation.",
    "stage2": "Focused refinement: test the strongest Stage 1 evidence and likely parameter interactions more carefully.",
    "stage3": "Final stability check: validate narrowed candidates on holdout prompts. This is the strongest sampler evidence in the current benchmark chain.",
}


def stage_profile_rows(analysis: dict[str, Any], phase: str) -> list[dict[str, Any]]:
    """Return one best-observed row per core profile within one distinct stage."""
    rows: list[dict[str, Any]] = []
    phase_scores = analysis["by_phase_prof_hash_scores"].get(phase, {})
    phase_elapsed = analysis["by_phase_prof_hash_elapsed"].get(phase, {})
    for profile in sorted(profile for profile in phase_scores if profile in CORE_PROFILES):
        combinations = phase_scores[profile]
        if not combinations:
            continue
        best_hash = max(combinations, key=lambda item: float(calculate_stats(combinations[item])["mean"]))
        stats = calculate_stats(combinations[best_hash])
        elapsed = phase_elapsed.get(profile, {}).get(best_hash, [])
        rows.append({
            "profile": profile,
            "param_hash": best_hash,
            "params": analysis["hash_params"].get(best_hash, {}),
            "stats": stats,
            "latency": round(sum(elapsed) / len(elapsed), 2) if elapsed else 0.0,
            "combination_count": len(combinations),
            "record_count": sum(len(values) for values in combinations.values()),
        })
    return rows


def final_stage_name(analysis: dict[str, Any]) -> str | None:
    """Prefer Stage 3; otherwise expose the most advanced available core stage."""
    phase_scores = analysis["by_phase_prof_hash_scores"]
    for phase in ("stage3", "stage2", "stage1"):
        if any(profile in CORE_PROFILES and hashes for profile, hashes in phase_scores.get(phase, {}).items()):
            return phase
    return None


def build_stage_snapshot(analysis: dict[str, Any]) -> str:
    """Create the concise final-stage view shown on the Overview tab."""
    phase = final_stage_name(analysis)
    if not phase:
        return "<div class='empty-note'>No completed Stage 1–3 sampler records are available yet.</div>"
    rows = stage_profile_rows(analysis, phase)
    if not rows:
        return "<div class='empty-note'>No core-profile summary is available for the latest stage.</div>"
    colour_class = phase
    chart_rows = [
        (PROF_ICONS.get(row["profile"], row["profile"]), float(row["stats"]["mean"]), score_class(float(row["stats"]["mean"])))
        for row in rows
    ]
    html = [f"<div class='section-title'>Latest sampler evidence — {escape(PHASE_LABELS.get(phase, phase))}</div>",
            f"<div class='callout'><b>Why this stage is shown here.</b> {escape(STAGE_DESCRIPTIONS[phase])}</div>",
            "<div class='preset-grid'>"]
    for row in rows:
        stats = row["stats"]
        html.append(
            f"<div class='card stage-card {colour_class}'><div class='stage-label {colour_class}-text'>{escape(PROF_ICONS.get(row['profile'], row['profile']))}</div>"
            f"<div class='metric-value'>{float(stats['mean']) * 100:.1f}%</div>"
            f"<div class='metric-sub'>Best observed {phase} score · ±{float(stats['std']):.3f} · n={stats['n']} · {row['latency']:.1f}s</div>"
            f"<div style='margin-top:9px'>{parameter_badges(row['params'])}</div></div>"
        )
    html.append("</div><div class='card'><h3>Best observed score by profile</h3>")
    html.append(svg_bar_chart(chart_rows, f"Best {phase} scores by profile"))
    html.append("<div class='note'>This chart compares outcomes only within their own benchmark profiles. It is an orientation aid, not a claim that one profile is objectively easier or harder than another.</div></div>")
    return "".join(html)


def build_stage_tab(analysis: dict[str, Any], phase: str) -> str:
    """Render one stage as a primary tab with all-profile and profile-specific views."""
    phase_scores = analysis["by_phase_prof_hash_scores"].get(phase, {})
    profiles = sorted(profile for profile in phase_scores if profile in CORE_PROFILES and phase_scores[profile])
    tab_id = f"tab-{phase}"
    if not profiles:
        return f"<div id='{tab_id}' class='tab-content'><div class='empty-note'>{escape(PHASE_LABELS.get(phase, phase))} has no completed records for this model.</div></div>"
    group_id = f"{phase}-profiles"
    stage_rows = stage_profile_rows(analysis, phase)
    stage_colour = phase
    html = [f"<div id='{tab_id}' class='tab-content'><div class='section-title'>{escape(PHASE_LABELS.get(phase, phase))}</div>",
            f"<div class='callout'><b>Purpose.</b> {escape(STAGE_DESCRIPTIONS[phase])}</div>",
            f"<div id='{group_id}' class='card stage-card {stage_colour}'>",
            "<div class='subtabs'>",
            f"<button class='subtab-btn active' onclick=\"openSubtab(event,'{group_id}','{group_id}-all')\">All profiles</button>"]
    for profile in profiles:
        html.append(f"<button class='subtab-btn' onclick=\"openSubtab(event,'{group_id}','{group_id}-{profile}')\">{escape(PROF_ICONS.get(profile, profile))}</button>")
    html.append("</div>")
    chart_rows = [
        (PROF_ICONS.get(row["profile"], row["profile"]), float(row["stats"]["mean"]), score_class(float(row["stats"]["mean"])))
        for row in stage_rows
    ]
    html.append(f"<div id='{group_id}-all' class='subtab-content active'><h3>Best observed combination per profile</h3>")
    html.append(svg_bar_chart(chart_rows, f"{phase} best scores by profile"))
    html.append("<table><thead><tr><th>Profile</th><th>Best score</th><th>Evidence</th><th>Combinations</th><th>Parameters</th></tr></thead><tbody>")
    for row in stage_rows:
        stats = row["stats"]
        html.append(
            f"<tr><td><b>{escape(PROF_ICONS.get(row['profile'], row['profile']))}</b></td>"
            f"<td>{score_bar(float(stats['mean']))}</td>"
            f"<td>±{float(stats['std']):.3f} · n={stats['n']} · {row['latency']:.1f}s</td>"
            f"<td>{row['combination_count']} combinations / {row['record_count']} scored records</td>"
            f"<td>{parameter_badges(row['params'])}</td></tr>"
        )
    html.append("</tbody></table><div class='note'>Select a profile above to view its ranked combinations. Scores remain stage-specific; Stage 1, Stage 2, and Stage 3 are not pooled here.</div></div>")
    phase_elapsed = analysis["by_phase_prof_hash_elapsed"].get(phase, {})
    phase_dims = analysis["by_prof_hash_dims"]
    for profile in profiles:
        combinations = []
        for param_hash, scores in phase_scores[profile].items():
            stats = calculate_stats(scores)
            elapsed = phase_elapsed.get(profile, {}).get(param_hash, [])
            dimensions = {name: sum(values) / len(values) for name, values in phase_dims[profile][param_hash].items() if values}
            combinations.append((float(stats["mean"]), param_hash, stats, elapsed, dimensions))
        combinations.sort(reverse=True)
        html.append(f"<div id='{group_id}-{profile}' class='subtab-content'><h3>{escape(PROF_ICONS.get(profile, profile))} — ranked combinations</h3>")
        html.append("<table><thead><tr><th>Rank</th><th>Mean score</th><th>Spread / samples</th><th>Latency</th><th>Parameters</th><th>Dimensions</th></tr></thead><tbody>")
        for rank, (_mean, param_hash, stats, elapsed, dimensions) in enumerate(combinations[:20], 1):
            latency = sum(elapsed) / len(elapsed) if elapsed else 0.0
            html.append(
                f"<tr><td><span class='badge {score_class(float(stats['mean']))}'>#{rank}</span></td>"
                f"<td>{score_bar(float(stats['mean']))}</td>"
                f"<td>±{float(stats['std']):.3f} · n={stats['n']}</td><td>{latency:.1f}s</td>"
                f"<td>{parameter_badges(analysis['hash_params'].get(param_hash, {}))}</td><td>{dimension_badges(dimensions)}</td></tr>"
            )
        html.append("</tbody></table></div>")
    html.append("</div></div>")
    return "".join(html)


def build_sampler_tab(analysis: dict[str, Any], presets: list[dict[str, Any]]) -> str:
    if not presets:
        return "<div id='tab-sampler' class='tab-content'><div class='empty-note'>No completed Stage 1–3 sampler records are available for this model.</div></div>"
    best_balanced = max(presets, key=lambda item: item["balanced"])
    best_logic = max(presets, key=lambda item: item["logic"])
    best_story = max(presets, key=lambda item: item["stories"])
    best_floor = max(presets, key=lambda item: item["minimum"])
    card_specs = [
        ("Assistant & logic", best_logic, "logic"),
        ("Stories & roleplay", best_story, "stories"),
        ("All-rounder", best_balanced, "balanced"),
        ("Strongest observed floor", best_floor, "minimum"),
    ]
    html = ["<div id='tab-sampler' class='tab-content'><div class='section-title'>Sampler tuning</div>"]
    html.append("<div class='callout'><b>Use these settings for the tested workload.</b> The recommendations come only from Stage 1–3 records. Refusal and NIAH probes are intentionally not used to alter these sampler recommendations.</div>")
    html.append("<div class='preset-grid'>")
    for title, preset, key in card_specs:
        value = float(preset[key])
        html.append(f"<div class='card'><h3>{escape(title)}</h3><pre>{escape(json.dumps(preset['params'], indent=2))}</pre><div class='metric-sub'>Evidence score: <b>{value:.4f}</b> · Mean latency: {preset['average_elapsed']:.1f}s</div></div>")
    html.append("</div><h2>Best observed combination by profile</h2><div class='preset-grid'>")
    for winner in profile_winners(analysis):
        stats = winner["stats"]
        html.append(f"<div class='card'><h3>{escape(PROF_ICONS.get(winner['profile'], winner['profile']))}</h3><pre>{escape(json.dumps(winner['params'], indent=2))}</pre><div class='metric-sub'>Mean {float(stats['mean']):.4f} · spread ±{float(stats['std']):.3f} · n={stats['n']} · {winner['elapsed']:.1f}s</div></div>")
    html.append("</div><div class='note'>Scores from different profiles should not be treated as a universal ranking because the prompt banks and grading dimensions differ.</div></div>")
    return "".join(html)


def build_technical_tab(analysis: dict[str, Any]) -> str:
    by_scores = analysis["by_phase_prof_hash_scores"]
    by_elapsed = analysis["by_phase_prof_hash_elapsed"]
    by_dims = analysis["by_prof_hash_dims"]
    params_by_hash = analysis["hash_params"]
    parameter_impact = analysis["param_impact"]
    run_rows = []
    for run_key, count in analysis["run_record_counts"].items():
        details = analysis["run_details"][run_key]
        failures = analysis["failed_records_by_run"].get(run_key, 0)
        run_rows.append((details, count, failures))
    run_rows.sort(key=lambda row: (row[2] / max(row[1], 1), -row[1]))
    html = ["<div id='tab-technical' class='tab-content'><div class='section-title'>Technical details</div>"]
    html.append("<div class='callout'><b>Technical evidence is intentionally separate.</b> Start with Overview, Sampler tuning, or Refusal & companion. Use this tab when you need to audit coverage, failures, sensitivity, or individual combinations.</div>")
    backend_text = escape(', '.join(sorted(analysis['backend_labels'])) or 'legacy/unspecified')
    sampler_text = escape(', '.join(sorted(analysis['declared_capabilities'])) or 'not recorded')
    html.append("<div class='grid-2'><div class='card'><h3>Environment provenance</h3><div class='metric-label'>Backend</div><div>{}</div><div class='metric-label' style='margin-top:12px'>Declared samplers</div><div>{}</div></div>".format(backend_text, sampler_text))
    html.append("<div class='card'><h3>Run quality and coverage</h3><table><thead><tr><th>Benchmark run</th><th>Stages</th><th>Profiles</th><th>Records</th><th>Failures</th></tr></thead><tbody>")
    for details, count, failures in run_rows:
        html.append(f"<tr title='{escape(', '.join(sorted(details['run_ids'])))}'><td><b>{escape(details['label'])}</b><br><span class='note'>{escape(str(details['benchmark_id'] or 'legacy result set'))}</span></td><td>{escape(', '.join(sorted(details['phases'])))}</td><td>{escape(', '.join(sorted(details['profiles'])))}</td><td>{count}</td><td>{failures} ({failures / max(count, 1):.1%})</td></tr>")
    html.append("</tbody></table><div class='note'>A high failure rate can make a benchmark ranking unreliable. Probe rows are included here for coverage, but their scores remain separate from sampler recommendations.</div></div></div>")

    language_scores = analysis["language_scores"]
    if language_scores:
        html.append("<div class='card' style='margin-top:18px'><h3>Multilingual coverage</h3><table><thead><tr><th>Language</th><th>Mean score</th><th>Spread</th><th>Records</th></tr></thead><tbody>")
        for language, scores in sorted(language_scores.items()):
            stats = calculate_stats(scores)
            html.append(f"<tr><td>{escape(language)}</td><td>{float(stats['mean']):.4f}</td><td>±{float(stats['std']):.4f}</td><td>{stats['n']}</td></tr>")
        html.append("</tbody></table><div class='note'>These rows are descriptive diagnostics, not direct cross-language quality rankings.</div></div>")

    temperature_rows = []
    for value, scores in parameter_impact.get("temperature", {}).items():
        stats = calculate_stats(scores)
        temperature_rows.append((str(value), float(stats["mean"]), score_class(float(stats["mean"]))))
    if temperature_rows:
        html.append("<div class='card' style='margin-top:18px'><h3>Temperature sensitivity</h3>")
        html.append(svg_bar_chart(sorted(temperature_rows, key=lambda row: float(row[0])), "Temperature sensitivity"))
        html.append("<div class='note'>This is pooled evidence across core sampler records. It is not a causal claim because other parameters and prompts also vary.</div></div>")

    html.append("<div class='callout good'><b>Stage combinations moved.</b> The color-coded ranked combinations, parameters, latency, and grading dimensions now live inside the dedicated Stage 1, Stage 2, and Stage 3 tabs. This Technical details tab keeps only cross-stage diagnostics, provenance, coverage, and parameter sensitivity.</div></div>")
    return "".join(html)


def generate_model_dashboard(model: str, records: list[dict[str, Any]]) -> Path:
    """Render one model dashboard with concise primary tabs and clear probe reporting."""
    DASH_DIR.mkdir(parents=True, exist_ok=True)
    base_model, variant_label = split_display_model(model)
    output_path = DASH_DIR / dashboard_filename(model)
    analysis = run_deep_analysis(records)
    presets = generate_specialized_presets(analysis)
    probe_tracks = analysis["probe_tracks"]
    phases = sorted(analysis["phases_seen"], key=lambda value: list(PHASE_LABELS).index(value) if value in PHASE_LABELS else 99)
    all_elapsed = [float(record.get("elapsed", 0.0) or 0.0) for record in records if record.get("elapsed")]
    total_time = format_duration(sum(all_elapsed)) if all_elapsed else "0s"
    average_latency = sum(all_elapsed) / len(all_elapsed) if all_elapsed else 0.0
    core_record_count = sum(1 for record in records if not str(record.get("phase", "")).startswith("probe_"))
    refusal_summary = None
    refusal_presets = probe_tracks.get("probe_refusal", {})
    if refusal_presets:
        first_label = sorted(refusal_presets)[0]
        refusal_summary = refusal_preset_summary(refusal_presets[first_label])

    stage_tabs = [
        phase for phase in ("stage1", "stage2", "stage3")
        if any(profile in CORE_PROFILES and hashes for profile, hashes in analysis["by_phase_prof_hash_scores"].get(phase, {}).items())
    ]
    tab_buttons = ["<button class='tab-btn active' onclick=\"openTab(event,'tab-overview')\">Overview</button>"]
    for phase in stage_tabs:
        label = PHASE_LABELS.get(phase, phase)
        tab_buttons.append(f"<button class='tab-btn' onclick=\"openTab(event,'tab-{phase}')\">{escape(label)}</button>")
    tab_buttons.append("<button class='tab-btn' onclick=\"openTab(event,'tab-sampler')\">Sampler tuning</button>")
    if refusal_presets:
        tab_buttons.append("<button class='tab-btn' onclick=\"openTab(event,'tab-refusal')\">Refusal & companion</button>")
    if probe_tracks.get("probe_niah"):
        tab_buttons.append("<button class='tab-btn' onclick=\"openTab(event,'tab-niah')\">NIAH long context</button>")
    tab_buttons.append("<button class='tab-btn' onclick=\"openTab(event,'tab-technical')\">Technical details</button>")

    html = ["<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>",
            f"<title>Senerenai-HyperProbe — {escape(model)}</title>",
            f"<style>{BASE_CSS}</style><script>{TABLE_JS}</script></head><body>",
            "<div class='header'>",
            f"<div class='header-main'><div class='header-title-row'><span class='header-kicker'>Model report</span><h1>Senerenai-HyperProbe — {escape(base_model)}{f' — {escape(variant_label)}' if variant_label else ''}</h1></div><div class='header-subtitle'>Sampler tuning and standalone probes are deliberately reported separately.</div></div>",
            "<div class='header-side'><a class='header-back' href='index.html'>← Back to model list</a><div class='header-meta'>",
            f"<span class='badge'>{len(records)} records</span><span class='badge'>Total time: {escape(total_time)}</span><span class='badge'>Average latency: {average_latency:.1f}s</span><span class='badge meta-wide' title='{escape(', '.join(phases) or '—')}'>Stages: {escape(', '.join(phases) or '—')}</span></div></div></div>",
            "<div class='container'><div class='tabs'>", "".join(tab_buttons), "</div>"]

    html.append("<div id='tab-overview' class='tab-content active'><div class='section-title'>What this dashboard tells you</div>")
    html.append("<div class='callout'><b>Start here.</b> Use <b>Sampler tuning</b> to choose parameters for the tested workloads. Use <b>Refusal & companion</b> to see whether the model met the behaviour expected by the refusal dataset. These answers are separate and neither one overrides the other.</div>")
    html.append("<div class='grid-3'>")
    html.append(f"<div class='card'><div class='metric-label'>Sampler benchmark records</div><div class='metric-value'>{core_record_count}</div><div class='metric-sub'>Stage 1–3 evidence used for presets</div></div>")
    html.append(f"<div class='card'><div class='metric-label'>Additional probe records</div><div class='metric-value'>{len(records) - core_record_count}</div><div class='metric-sub'>Refusal and/or NIAH; never pooled into tuning</div></div>")
    if refusal_summary:
        automated = refusal_summary["score"]
        label, klass = score_band(float(automated)) if automated is not None else ("manual-review only", "warn")
        value = "—" if automated is None else f"{float(automated) * 100:.1f}%"
        html.append(f"<div class='card'><div class='metric-label'>Refusal automated agreement</div><div class='metric-value'>{value}</div><div class='metric-sub'><span class='badge {klass}'>{escape(label)}</span> · {refusal_summary['scored_items']} auto-scored · {refusal_summary['manual_items']} manual</div></div>")
    else:
        html.append("<div class='card'><div class='metric-label'>Refusal probe</div><div class='metric-value'>Not run</div><div class='metric-sub'>Configure Additional Benchmarks to add it.</div></div>")
    html.append("</div>")
    html.append(build_stage_snapshot(analysis))
    if refusal_summary and refusal_summary["score"] is not None:
        weakest = []
        for track, bucket in refusal_presets[sorted(refusal_presets)[0]].items():
            if bucket["scores"]:
                weakest.append((float(calculate_stats(bucket["scores"])["mean"]), track))
        weakest.sort()
        weak_text = ", ".join(f"{name} ({score * 100:.0f}%)" for score, name in weakest[:3])
        html.append(f"<div class='callout {score_class(float(refusal_summary['score']))}'><b>Refusal takeaway.</b> The current preset automatically matched the dataset checks on {float(refusal_summary['score']) * 100:.1f}% of {refusal_summary['scored_items']} scored rows. The first tracks to inspect are: {escape(weak_text or '—')}. Lower values mean the response less often matched the dataset’s declared expectation; review the raw replies before drawing broader conclusions.</div>")
    html.append("<div class='card'><h2>How to read scores</h2><table><thead><tr><th>Score</th><th>Meaning</th><th>Do next</th></tr></thead><tbody><tr><td>90–100%</td><td>Strong agreement with the dataset’s automatic checks.</td><td>Still inspect manual-review cases and any important flags.</td></tr><tr><td>70–89%</td><td>Mixed evidence; some prompts or dimensions did not match expectations.</td><td>Open the relevant tab and inspect weak tracks.</td></tr><tr><td>Below 70%</td><td>Inconsistent alignment with the defined dataset checks.</td><td>Review replies, labels, prompts, and sampler comparison before changing a model.</td></tr></tbody></table></div></div>")

    for phase in stage_tabs:
        html.append(build_stage_tab(analysis, phase))
    html.append(build_sampler_tab(analysis, presets))
    html.append(build_refusal_tab(analysis))
    html.append(build_niah_tab(analysis))
    html.append(build_technical_tab(analysis))
    html.append("</div></body></html>")
    output_path.write_text("".join(html), encoding="utf-8")
    return output_path


def generate_index(by_model: dict[str, list[dict[str, Any]]], dashboard_files: dict[str, Path]) -> Path:
    """Render the static multi-model index without mixing probe scores into sampler comparison."""
    DASH_DIR.mkdir(parents=True, exist_ok=True)
    index_path = DASH_DIR / "index.html"
    comparison: dict[str, dict[str, float]] = defaultdict(dict)
    profile_set: set[str] = set()
    for model, records in by_model.items():
        analysis = run_deep_analysis(records)
        for phase, profiles in analysis["by_phase_prof_hash_scores"].items():
            if phase.startswith("probe_"):
                continue
            for profile, hashes in profiles.items():
                if profile not in CORE_PROFILES:
                    continue
                profile_set.add(profile)
                for scores in hashes.values():
                    mean_value = float(calculate_stats(scores)["mean"])
                    comparison[profile][model] = max(comparison[profile].get(model, -1.0), mean_value)
    models = sorted(by_model)
    html = ["<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'><title>Senerenai-HyperProbe — Model overview</title>",
            f"<style>{BASE_CSS}</style></head><body><div class='header'><div><h1>Senerenai-HyperProbe — Model overview</h1><div class='note'>Sampler comparisons exclude refusal and NIAH probe scores.</div></div><span class='badge'>{len(models)} model result sets</span></div><div class='container'>",
            "<div class='section-title'>Benchmark result sets</div><div class='card'><table><thead><tr><th>Model and methodology</th><th>Records</th><th>Dashboard</th></tr></thead><tbody>"]
    for model in models:
        html.append(f"<tr><td><b>{escape(model)}</b></td><td>{len(by_model[model])}</td><td><a href='{escape(dashboard_files[model].name)}'>Open dashboard</a></td></tr>")
    html.append("</tbody></table></div><div class='section-title'>Sampler comparison by profile</div><div class='card'><div class='note'>Best observed core benchmark mean per profile. Do not compare different profiles as if they used the same prompt difficulty.</div><table><thead><tr><th>Profile</th>")
    for model in models:
        html.append(f"<th>{escape(model)}</th>")
    html.append("</tr></thead><tbody>")
    for profile in sorted(profile_set):
        html.append(f"<tr><td><b>{escape(PROF_ICONS.get(profile, profile))}</b></td>")
        values = comparison.get(profile, {})
        best = max(values.values()) if values else None
        for model in models:
            value = values.get(model)
            if value is None:
                html.append("<td class='note'>—</td>")
            elif value == best:
                html.append(f"<td><b style='color:var(--green)'>{value:.4f}</b></td>")
            else:
                html.append(f"<td>{value:.4f}</td>")
        html.append("</tr>")
    html.append("</tbody></table></div></div></body></html>")
    index_path.write_text("".join(html), encoding="utf-8")
    return index_path


def main() -> None:
    print("Loading and analyzing benchmark data...")
    records = load_all_data()
    if not records:
        print("No JSONL benchmark files were found in results/.")
        return
    by_model = group_by_model(records)
    print(f"Found {len(by_model)} model(s): {', '.join(sorted(by_model))}")
    dashboard_files: dict[str, Path] = {}
    for model, model_records in by_model.items():
        dashboard_files[model] = generate_model_dashboard(model, model_records)
        print(f"  {model}: {len(model_records)} records -> {dashboard_files[model]}")
    index_path = generate_index(by_model, dashboard_files)
    print(f"Dashboard generated at: {index_path}")


if __name__ == "__main__":
    main()
