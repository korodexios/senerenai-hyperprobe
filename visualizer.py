"""Generate static, model-scoped HTML dashboards from Senerenai-HyperProbe JSONL logs.

The dashboard keeps benchmark phases separate, provides searchable result
tables, summarizes specialized presets, and reports degeneration statistics.
"""
import json
import math
from html import escape
from pathlib import Path
from collections import defaultdict
from common import format_duration

RESULTS_DIR = Path(__file__).parent / "results"
DASH_DIR = RESULTS_DIR / "dashboards"
DASH_DIR.mkdir(parents=True, exist_ok=True)

DEGEN_FLAG_PREFIXES = ("ngram5_loop", "ngram8_loop", "repeated_lines", "low_unique_ratio")
PROF_ICONS = {"coding": "💻", "creative": "🎨", "roleplay": "🎭", "custom_lang": "🇸🇰"}
PHASE_LABELS = {
    "stage1": "🔎 Stage1 (coarse)", "stage2": "🔬 Stage2 (refined)", "stage3": "🎯 Stage3 (finest)",
    "quickscan": "⚡ Quickscan (legacy)", "sweep": "🧪 Sweep (legacy)", "focused": "🎯 Focused (legacy)",
}


def model_safe_name(model: str) -> str:
    return model.replace("/", "_").replace("\\", "_")


# ═══════════════════════════════════════════════════════════════
#  LOAD + GROUP
# ═══════════════════════════════════════════════════════════════

def load_all_data() -> list[dict]:
    records = []
    for f in RESULTS_DIR.glob("*.jsonl"):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                # Backfill "phase"/"model" for older files that fordate this
                # per-model naming scheme, so nothing silently disappears.
                if "phase" not in r or "model" not in r:
                    stem = f.stem  # e.g. stage1_roleplay_my-model  OR  quickscan_roleplay (legacy)
                    parts = stem.split("_")
                    r.setdefault("phase", parts[0] if parts else "unknown")
                    if "model" not in r:
                        prof = r.get("profile", "")
                        prefix = f"{r['phase']}_{prof}_"
                        r["model"] = stem[len(prefix):] if stem.startswith(prefix) else "unknown_model"
                records.append(r)
    return records


def benchmark_variant(record: dict) -> str:
    """Return a display-safe evidence variant; old records are explicitly legacy."""
    return str(record.get("search_design") or "legacy")


def group_by_model(records: list[dict]) -> dict:
    """Keep records from different search methodologies out of one ranking."""
    by_model = defaultdict(list)
    for record in records:
        model = record.get("model", "unknown_model")
        label = f"{model} [{benchmark_variant(record)}]"
        by_model[label].append(record)
    return by_model


# ═══════════════════════════════════════════════════════════════
#  STATS
# ═══════════════════════════════════════════════════════════════

def calculate_stats(scores: list[float]) -> dict:
    if not scores:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "n": 0}
    mean = sum(scores) / len(scores)
    variance = sum((s - mean) ** 2 for s in scores) / len(scores)
    return {
        "mean": round(mean, 4), "std": round(math.sqrt(variance), 4),
        "min": round(min(scores), 4), "max": round(max(scores), 4), "n": len(scores),
    }


def run_deep_analysis(records: list[dict]) -> dict:
    """All structures are keyed [phase][profile][param_hash] where it makes
    sense to keep phases separate (top-10 tables), and pooled across all
    phases where mixing is fine for a rough view (sensitivity, prompts,
    flags, degeneration)."""
    by_phase_prof_hash_scores = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    by_phase_prof_hash_elapsed = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    by_prof_hash_dims = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    hash_params = {}

    param_impact = defaultdict(lambda: defaultdict(list))
    param_dim_impact = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    param_flags = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    prompt_matrix = defaultdict(lambda: defaultdict(list))
    language_scores = defaultdict(list)
    run_record_counts = defaultdict(int)
    failed_records_by_run = defaultdict(int)

    # Degeneration tracking: per combination, how often did a degeneration flag fire?
    combo_degen_hits = defaultdict(int)
    combo_degen_total = defaultdict(int)
    combo_degen_examples = defaultdict(list)

    phases_seen = set()

    for r in records:
        if "grade" not in r:
            continue

        prof = r.get("profile", "unknown")
        phase = r.get("phase", "unknown")
        ph = r.get("param_hash")
        params = r["params"]
        score = r["grade"]["weighted_score"]
        elapsed = r.get("elapsed", 0.0)
        prompt_id = r.get("prompt_id", "unknown")
        flags = r["grade"].get("flags", [])
        language = r.get("language")
        run_id = r.get("run_id", "legacy-record")

        phases_seen.add(phase)
        run_record_counts[run_id] += 1
        is_failed = not r["grade"].get("dimensions")
        if is_failed:
            failed_records_by_run[run_id] += 1
            # Keep failed calls visible in run-integrity diagnostics, but do not
            # let zero-score error records contaminate rankings, presets,
            # language means, parameter sensitivity, or degeneration rates.
            continue
        if language:
            language_scores[language].append(score)
        hash_params[ph] = params
        by_phase_prof_hash_scores[phase][prof][ph].append(score)
        if elapsed > 0:
            by_phase_prof_hash_elapsed[phase][prof][ph].append(elapsed)
        prompt_matrix[f"{prof} :: {prompt_id}"][ph].append(score)

        dims = r["grade"].get("dimensions", {})
        for d_name, d_val in dims.items():
            by_prof_hash_dims[prof][ph][d_name].append(d_val)

        flag_names = [f.split(":")[0] for f in flags]
        for p_name, p_val in params.items():
            param_impact[p_name][p_val].append(score)
            for d_name, d_val in dims.items():
                param_dim_impact[p_name][p_val][d_name].append(d_val)
            for fl in flag_names:
                param_flags[p_name][p_val][fl] += 1

        combo_degen_total[ph] += 1
        degen_flags_here = [f for f in flags if f.split(":")[0] in DEGEN_FLAG_PREFIXES]
        if degen_flags_here:
            combo_degen_hits[ph] += 1
            if len(combo_degen_examples[ph]) < 3:
                combo_degen_examples[ph].append(degen_flags_here[0])

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
        "combo_degen_hits": combo_degen_hits,
        "combo_degen_total": combo_degen_total,
        "combo_degen_examples": combo_degen_examples,
        "phases_seen": phases_seen,
    }


def generate_specialized_presets(analysis: dict) -> list[dict]:
    """Pooled across all phases — a rough 'best overall' view."""
    bphs = analysis["by_phase_prof_hash_scores"]
    bphe = analysis["by_phase_prof_hash_elapsed"]
    hp = analysis["hash_params"]

    pooled_scores = defaultdict(lambda: defaultdict(list))   # prof -> ph -> [scores]
    pooled_elapsed = defaultdict(lambda: defaultdict(list))
    for phase in bphs:
        for prof in bphs[phase]:
            for ph, scores in bphs[phase][prof].items():
                pooled_scores[prof][ph].extend(scores)
        for prof in bphe.get(phase, {}):
            for ph, times in bphe[phase][prof].items():
                pooled_elapsed[prof][ph].extend(times)

    all_hashes = set()
    for prof in pooled_scores:
        all_hashes.update(pooled_scores[prof].keys())

    presets = []
    for ph in all_hashes:
        prof_means, prof_stds, prof_mins, prof_maxs, all_elapsed = [], [], [], [], []
        for prof in pooled_scores:
            if ph in pooled_scores[prof] and pooled_scores[prof][ph]:
                st = calculate_stats(pooled_scores[prof][ph])
                prof_means.append(st["mean"]); prof_stds.append(st["std"])
                prof_mins.append(st["min"]); prof_maxs.append(st["max"])
            if ph in pooled_elapsed.get(prof, {}):
                all_elapsed.extend(pooled_elapsed[prof][ph])

        if prof_means:
            avg_mean = sum(prof_means) / len(prof_means)
            avg_std = sum(prof_stds) / len(prof_stds)
            min_score = min(prof_mins)
            max_score = max(prof_maxs)
            avg_elapsed = (sum(all_elapsed) / len(all_elapsed)) if all_elapsed else 999.0
            
            # Round parameters to practical values that can be reused in client settings.
            clean_params = {}
            for k, v in hp[ph].items():
                if isinstance(v, float):
                    if k in ("min_p", "repetition_penalty", "presence_penalty", "frequency_penalty"):
                        clean_params[k] = round(v, 2)
                    else:
                        clean_params[k] = round(v, 1)  # for temperature, top_p
                else:
                    clean_params[k] = v

            # 1. Compromise for Assistant & Logic (Coding + Agent + SK/CZ)
            logic_profs = [p for p in ["coding", "agent_tools", "custom_lang"] if p in pooled_scores and ph in pooled_scores[p]]
            if logic_profs:
                l_means = [calculate_stats(pooled_scores[p][ph])["mean"] for p in logic_profs]
                l_mins = [calculate_stats(pooled_scores[p][ph])["min"] for p in logic_profs]
                l_stds = [calculate_stats(pooled_scores[p][ph])["std"] for p in logic_profs]
                logic_comp = (sum(l_means)/len(l_means))*0.6 + min(l_mins)*0.3 - (sum(l_stds)/len(l_stds))*0.1
            else:
                logic_comp = 0.0

            # 2. Compromise for Creativity & Stories (Creative + Roleplay)
            story_profs = [p for p in ["creative", "roleplay"] if p in pooled_scores and ph in pooled_scores[p]]
            if story_profs:
                s_means = [calculate_stats(pooled_scores[p][ph])["mean"] for p in story_profs]
                s_maxs = [calculate_stats(pooled_scores[p][ph])["max"] for p in story_profs]
                story_comp = (sum(s_means)/len(s_means))*0.6 + (sum(s_maxs)/len(s_maxs))*0.4
            else:
                story_comp = 0.0

            presets.append({
                "ph": ph, "params": clean_params,
                "avg_mean": round(avg_mean, 4), "avg_std": round(avg_std, 4),
                "min_score": round(min_score, 4), "max_score": round(max_score, 4),
                "avg_elapsed": round(avg_elapsed, 2),
                "balanced": round(avg_mean * 0.6 + min_score * 0.3 - avg_std * 0.1, 4),
                "zero_derail": round(min_score * 0.6 + (1.0 - avg_std) * 0.4, 4),
                "speed_ratio": round(avg_mean / max(avg_elapsed, 1.0), 4),
                "logic_compromise": round(logic_comp, 4),
                "story_compromise": round(story_comp, 4),
            })
    return presets


# ═══════════════════════════════════════════════════════════════
#  HTML BUILDING HELPERS
# ═══════════════════════════════════════════════════════════════

def build_params_badges(params: dict) -> str:
    colors = {"temperature": "bg-red-900 text-red-200", "min_p": "bg-blue-900 text-blue-200",
              "top_p": "bg-cyan-900 text-cyan-200", "repetition_penalty": "bg-green-900 text-green-200"}
    html = ""
    for k, v in params.items():
        c = colors.get(k, "bg-gray-800 text-gray-300")
        html += f'<span class="badge {c}">{k}: <b>{v}</b></span> '
    return html


def build_dims_badges(dims: dict) -> str:
    html = ""
    for k, v in dims.items():
        c = "text-green-400" if v >= 0.8 else "text-yellow-400" if v >= 0.5 else "text-red-400"
        html += f'<span class="dim-badge {c}">{k}: {v:.2f}</span> '
    return html


BASE_CSS = """
:root { --bg: #0f172a; --card: #1e293b; --text: #f8fafc; --text-muted: #94a3b8; --border: #334155; --primary: #38bdf8; --success: #4ade80; --warning: #facc15; --danger: #f87171; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 0; }
.header { background: var(--card); padding: 20px 40px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }
.header h1 { margin: 0; color: var(--primary); font-size: 22px; }
.header a { color: var(--primary); text-decoration: none; font-size: 13px; }
.container { max-width: 1400px; margin: 30px auto; padding: 0 20px; }
.section-title { color: var(--primary); font-size: 20px; border-bottom: 2px solid var(--border); padding-bottom: 8px; margin-top: 40px; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 1px; }
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 25px; }
.grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 25px; }
.grid-2 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 25px; }
.preset-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 15px; margin-bottom: 25px; }
.card { background: var(--card); border-radius: 10px; padding: 20px; border: 1px solid var(--border); box-shadow: 0 4px 6px rgba(0,0,0,0.2); }
.card h3 { margin-top: 0; font-size: 15px; color: var(--primary); border-bottom: 1px solid var(--border); padding-bottom: 8px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.tabs { display: flex; border-bottom: 2px solid var(--border); margin-bottom: 20px; overflow-x: auto; }
.tab-btn { background: none; border: none; color: var(--text-muted); padding: 12px 24px; cursor: pointer; font-size: 15px; font-weight: bold; transition: 0.2s; white-space: nowrap; }
.tab-btn:hover { color: var(--text); }
.tab-btn.active { color: var(--primary); border-bottom: 2px solid var(--primary); margin-bottom: -2px; }
.subtabs { display: flex; gap: 6px; margin-bottom: 14px; flex-wrap: wrap; }
.subtab-btn { background: #0b0f19; border: 1px solid var(--border); color: var(--text-muted); padding: 6px 14px; border-radius: 20px; cursor: pointer; font-size: 12px; font-weight: 600; }
.subtab-btn:hover { color: var(--text); }
.subtab-btn.active { color: #000; background: var(--primary); border-color: var(--primary); }
.subtab-content { display: none; }
.subtab-content.active { display: block; }
.tab-content { display: none; }
.tab-content.active { display: block; }
.search-box { background: #0b0f19; border: 1px solid var(--border); color: var(--text); padding: 8px 12px; border-radius: 6px; width: 260px; font-size: 13px; margin-bottom: 10px; }
.search-box::placeholder { color: var(--text-muted); }
table { width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 14px; }
th, td { padding: 12px; text-align: left; border-bottom: 1px solid var(--border); }
th { background: #0b0f19; color: var(--text-muted); font-weight: 600; text-transform: uppercase; font-size: 12px; cursor: pointer; user-select: none; }
th:hover { color: var(--primary); }
tr:hover { background: rgba(255,255,255,0.02); }
.badge { display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 12px; margin: 2px; white-space: nowrap; }
.dim-badge { display: inline-block; font-size: 11px; margin-right: 8px; font-family: monospace; }
.bg-red-900 { background: #7f1d1d; } .text-red-200 { color: #fecaca; }
.bg-blue-900 { background: #1e3a8a; } .text-blue-200 { color: #bfdbfe; }
.bg-cyan-900 { background: #164e63; } .text-cyan-200 { color: #cffafe; }
.bg-green-900 { background: #14532d; } .text-green-200 { color: #bbf7d0; }
.bg-gray-800 { background: #1f2937; } .text-gray-300 { color: #d1d5db; }
.text-green-400 { color: var(--success); } .text-yellow-400 { color: var(--warning); } .text-red-400 { color: var(--danger); }
for { background: #0b0f19; padding: 12px; border-radius: 8px; overflow-x: auto; font-family: monospace; font-size: 12px; color: #e2e8f0; margin: 8px 0; }
.degen-bar-track { background: #0b0f19; border-radius: 4px; overflow: hidden; height: 10px; width: 120px; display: inline-block; vertical-align: middle; }
.degen-bar-fill { background: var(--danger); height: 100%; }
.empty-note { color: var(--text-muted); font-size: 13px; padding: 12px 0; }
"""

TABLE_JS = """
function openTab(evt, tabName) {
    var els = document.getElementsByClassName("tab-content");
    for (var i = 0; i < els.length; i++) els[i].classList.remove("active");
    var btns = document.getElementsByClassName("tab-btn");
    for (var i = 0; i < btns.length; i++) btns[i].classList.remove("active");
    document.getElementById(tabName).classList.add("active");
    evt.currentTarget.classList.add("active");
}
function openSubtab(evt, groupId, tabName) {
    var card = document.getElementById(groupId).closest('.card');
    var target = document.getElementById(tabName);
    var isAlreadyActive = evt.currentTarget.classList.contains("active");

    var els = card.getElementsByClassName("subtab-content");
    for (var i = 0; i < els.length; i++) els[i].classList.remove("active");
    var btns = card.querySelectorAll(".subtab-btn");
    for (var i = 0; i < btns.length; i++) btns[i].classList.remove("active");

    // Clicking the active tab closes it; clicking another tab opens that tab.
    if (!isAlreadyActive && target) {
        target.classList.add("active");
        evt.currentTarget.classList.add("active");
    }
}
function filterTable(inputEl, tableId) {
    var q = inputEl.value.toLowerCase();
    var rows = document.getElementById(tableId).getElementsByTagName("tbody")[0].rows;
    for (var i = 0; i < rows.length; i++) {
        var txt = rows[i].innerText.toLowerCase();
        rows[i].style.display = txt.indexOf(q) === -1 ? "none" : "";
    }
}
function sortTable(tableId, colIdx, numeric) {
    var table = document.getElementById(tableId);
    var tbody = table.getElementsByTagName("tbody")[0];
    var rows = Array.prototype.slice.call(tbody.rows);
    var asc = table.getAttribute("data-sort-col") != colIdx || table.getAttribute("data-sort-dir") === "desc";
    rows.sort(function(a, b) {
        var av = a.cells[colIdx].innerText.trim();
        var bv = b.cells[colIdx].innerText.trim();
        if (numeric) { av = parseFloat(av) || 0; bv = parseFloat(bv) || 0; }
        if (av < bv) return asc ? -1 : 1;
        if (av > bv) return asc ? 1 : -1;
        return 0;
    });
    rows.forEach(function(r) { tbody.appendChild(r); });
    table.setAttribute("data-sort-col", colIdx);
    table.setAttribute("data-sort-dir", asc ? "asc" : "desc");
}
"""


# ═══════════════════════════════════════════════════════════════
#  PER-MODEL DASHBOARD
# ═══════════════════════════════════════════════════════════════

def generate_model_dashboard(model: str, records: list[dict]) -> Path:
    DASH_DIR.mkdir(parents=True, exist_ok=True)
    model_safe = model_safe_name(model)
    html_file = DASH_DIR / f"dashboard_{model_safe}.html"

    analysis = run_deep_analysis(records)
    presets = generate_specialized_presets(analysis)

    bphs = analysis["by_phase_prof_hash_scores"]
    bphe = analysis["by_phase_prof_hash_elapsed"]
    bphd = analysis["by_prof_hash_dims"]
    hp = analysis["hash_params"]
    p_imp = analysis["param_impact"]
    p_dim = analysis["param_dim_impact"]
    p_flags = analysis["param_flags"]
    pm = analysis["prompt_matrix"]
    degen_hits = analysis["combo_degen_hits"]
    degen_total = analysis["combo_degen_total"]
    degen_examples = analysis["combo_degen_examples"]
    language_scores = analysis["language_scores"]
    run_record_counts = analysis["run_record_counts"]
    failed_records_by_run = analysis["failed_records_by_run"]

    profiles_present = sorted({p for phase in bphs for p in bphs[phase]})
    phases_present = sorted(analysis["phases_seen"],
                             key=lambda x: list(PHASE_LABELS.keys()).index(x) if x in PHASE_LABELS else 99)

    total_samples = len(records)
    all_elapsed_flat = [t for phase in bphe.values() for prof in phase.values()
                         for times in prof.values() for t in times if isinstance(t, (int, float))]
    total_time_formatted = format_duration(sum(all_elapsed_flat)) if all_elapsed_flat else "0s"
    avg_latency = round(sum(all_elapsed_flat) / len(all_elapsed_flat), 1) if all_elapsed_flat else 0.0
    run_quality_rows = [
        {
            "run_id": run_id,
            "records": count,
            "failures": failed_records_by_run.get(run_id, 0),
            "failure_rate": failed_records_by_run.get(run_id, 0) / max(count, 1),
        }
        for run_id, count in run_record_counts.items()
    ]
    run_quality_rows.sort(key=lambda row: (row["failure_rate"], -row["records"]))
    language_rows = [
        {"language": language, "mean": calculate_stats(scores)["mean"], "std": calculate_stats(scores)["std"], "n": len(scores)}
        for language, scores in language_scores.items()
    ]
    language_rows.sort(key=lambda row: row["mean"], reverse=True)

    p_bal = sorted(presets, key=lambda x: x["balanced"], reverse=True)[0] if presets else {}
    p_zero = sorted(presets, key=lambda x: x["zero_derail"], reverse=True)[0] if presets else {}
    p_speed = sorted(presets, key=lambda x: x["speed_ratio"], reverse=True)[0] if presets else {}
    p_logic = sorted(presets, key=lambda x: x["logic_compromise"], reverse=True)[0] if presets else {}
    p_story = sorted(presets, key=lambda x: x["story_compromise"], reverse=True)[0] if presets else {}

    temp_vals = sorted(p_imp.get("temperature", {}).keys())
    temp_scores = [round(calculate_stats(p_imp["temperature"][v])["mean"], 4) for v in temp_vals]

    html = [f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Senerenai-HyperProbe — {model}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>{BASE_CSS}</style>
<script>{TABLE_JS}</script>
</head>
<body>
<div class="header">
    <h1>🔬 {model}</h1>
    <div>
        <a href="index.html">← back to model list</a> &nbsp;·&nbsp;
        <span class="badge" style="background:var(--primary); color:#000;">{total_samples} records</span>
        <span class="badge" style="background:var(--card); border: 1px solid var(--border);">⏱️ Total time: {total_time_formatted}</span>
        <span class="badge" style="background:var(--card); border: 1px solid var(--border);">Average latency: {avg_latency}s</span>
        <span class="badge" style="background:var(--card); border: 1px solid var(--border);">Stages: {", ".join(phases_present) or "—"}</span>
    </div>
</div>
<div class="container">
<div class="section-title">📊 1. Practical recommendations (clean values)</div>
<div class="preset-grid">
    <div class="card" style="border-top:4px solid #8b5cf6;">
        <h3>💻 Assistant & logic (coding, tools, multilingual)</h3>
        <pre>{json.dumps(p_logic.get('params', {}), indent=2)}</pre>
        <div style="font-size:13px;color:var(--text-muted);display:flex;justify-content:space-between;">
            <span>Group compromise: <b style="color:#8b5cf6;font-size:15px;">{p_logic.get('logic_compromise', 0.0):.4f}</b></span>
            <span>⏱️ {p_logic.get('avg_elapsed', 0.0):.1f}s</span>
        </div>
    </div>
    <div class="card" style="border-top:4px solid #ec4899;">
        <h3>🎨 Stories & fiction (Creative+Roleplay)</h3>
        <pre>{json.dumps(p_story.get('params', {}), indent=2)}</pre>
        <div style="font-size:13px;color:var(--text-muted);display:flex;justify-content:space-between;">
            <span>Group compromise: <b style="color:#ec4899;font-size:15px;">{p_story.get('story_compromise', 0.0):.4f}</b></span>
            <span>⏱️ {p_story.get('avg_elapsed', 0.0):.1f}s</span>
        </div>
    </div>
    <div class="card" style="border-top:4px solid var(--primary);">
        <h3>⚖️ Global compromise (all-rounder)</h3>
        <pre>{json.dumps(p_bal.get('params', {}), indent=2)}</pre>
        <div style="font-size:13px;color:var(--text-muted);display:flex;justify-content:space-between;">
            <span>Balanced score: <b style="color:var(--primary);font-size:15px;">{p_bal.get('balanced', 0.0):.4f}</b></span>
            <span>⏱️ {p_bal.get('avg_elapsed', 0.0):.1f}s</span>
        </div>
    </div>
    <div class="card" style="border-top:4px solid var(--success);">
        <h3>🛡️ Maximum safety (zero-derail)</h3>
        <pre>{json.dumps(p_zero.get('params', {}), indent=2)}</pre>
        <div style="font-size:13px;color:var(--text-muted);display:flex;justify-content:space-between;">
            <span>Worst case: <b style="color:var(--success);font-size:15px;">{p_zero.get('min_score', 0.0):.4f}</b></span>
            <span>⏱️ {p_zero.get('avg_elapsed', 0.0):.1f}s</span>
        </div>
    </div>
    <div class="card" style="border-top:4px solid var(--warning);">
        <h3>⚡ Fastest strong preset</h3>
        <pre>{json.dumps(p_speed.get('params', {}), indent=2)}</pre>
        <div style="font-size:13px;color:var(--text-muted);display:flex;justify-content:space-between;">
            <span>Speed + score: <b style="color:var(--warning);font-size:15px;">{p_speed.get('speed_ratio', 0.0):.4f}</b></span>
            <span>⏱️ <b style="color:var(--warning);">{p_speed.get('avg_elapsed', 0.0):.1f}s</b></span>
        </div>
    </div>
</div>
"""]

    if run_quality_rows:
        html.append('<div class="section-title">🧪 Run quality and coverage</div>')
        html.append('<div class="grid-2">')
        html.append('<div class="card"><h3>Run integrity</h3><table><thead><tr><th>Run ID</th><th>Records</th><th>Failures</th><th>Failure rate</th></tr></thead><tbody>')
        for row in run_quality_rows:
            html.append(
                f"<tr><td><code>{escape(str(row['run_id']))}</code></td>"
                f"<td>{row['records']}</td><td>{row['failures']}</td>"
                f"<td>{row['failure_rate']:.1%}</td></tr>"
            )
        html.append('</tbody></table><div class="empty-note">A high failure rate can make a benchmark ranking unreliable. Compare runs only when their stage, prompt-bank fingerprint, model revision, and sample count are aligned.</div></div>')
        if language_rows:
            html.append('<div class="card"><h3>Multilingual coverage</h3><table><thead><tr><th>Language</th><th>Mean score</th><th>Std. dev.</th><th>Records</th></tr></thead><tbody>')
            for row in language_rows:
                html.append(
                    f"<tr><td>{escape(str(row['language']))}</td><td>{row['mean']:.4f}</td>"
                    f"<td>{row['std']:.4f}</td><td>{row['n']}</td></tr>"
                )
            html.append('</tbody></table><div class="empty-note">Language rows are descriptive diagnostics, not cross-language quality rankings. Different scripts and prompt targets have different difficulty profiles.</div></div>')
        html.append('</div>')

    # ── winners per profile (pooled across phases, quick glance) ──
    html.append('<div style="margin-bottom:10px;font-weight:bold;color:var(--text-muted);">🏆 BEST PRESET FOR EACH PROFILE (across all stages):</div><div class="grid-4">')
    for prof in profiles_present:
        pooled = defaultdict(list)
        for phase in bphs:
            for ph, scores in bphs[phase].get(prof, {}).items():
                pooled[ph].extend(scores)
        if not pooled:
            continue
        best_ph = max(pooled, key=lambda h: sum(pooled[h]) / len(pooled[h]))
        st = calculate_stats(pooled[best_ph])
        icon = PROF_ICONS.get(prof, "📋")
        html.append(f'''<div class="card" style="border-top:4px solid var(--primary);">
    <h3>{icon} {prof.upper()} <span class="badge bg-green-900 text-green-200">#1</span></h3>
    <pre>{json.dumps(hp[best_ph], indent=2)}</pre>
    <div style="font-size:12px;color:var(--text-muted);">Mean: <b style="color:var(--success);">{st['mean']:.4f}</b> (±{st['std']:.3f}, n={st['n']})</div>
</div>''')
    html.append('</div>')

    html.append(f'''<div class="grid-2" style="margin-top:25px;">
    <div class="card"><h3>📈 Temperature sensitivity</h3><canvas id="tempChart"></canvas></div>
    <div class="card"><h3>🔁 Degeneration/loop rate by temperature</h3><canvas id="degenChart"></canvas></div>
</div>''')

    # ── tabs nav ──
    html.append('''<div class="section-title">🔍 2. Detailed analysis</div>
<div class="tabs">
    <button class="tab-btn active" onclick="openTab(event,'tab-profiles')">🏆 Top combinations</button>
    <button class="tab-btn" onclick="openTab(event,'tab-degen')">🔁 Degeneration</button>
    <button class="tab-btn" onclick="openTab(event,'tab-sensitivity')">📈 Parameter sensitivity</button>
    <button class="tab-btn" onclick="openTab(event,'tab-prompts')">🧩 Hardest prompts</button>
    <button class="tab-btn" onclick="openTab(event,'tab-flags')">🚩 Flags</button>
</div>''')

    # ── TAB: profiles (phase sub-tabs, filterable, sortable) ──
    html.append('<div id="tab-profiles" class="tab-content active">')
    html.append('<div class="empty-note">Stages are kept separate (different record counts would distort averages); switch between them below.</div>')
    for prof in profiles_present:
        icon = PROF_ICONS.get(prof, "📋")
        phases_for_prof = [ph for ph in phases_present if bphs.get(ph, {}).get(prof)]
        if not phases_for_prof:
            continue
        group_id = f"group-{prof}"
        html.append(f'<div class="card" style="margin-bottom:20px;"><h3>{icon} {prof.upper()}</h3>')
        html.append(f'<div class="subtabs" id="{group_id}">')
        for i, phase in enumerate(phases_for_prof):
            active = " active" if i == 0 else ""
            label = PHASE_LABELS.get(phase, phase)
            html.append(f'<button class="subtab-btn{active}" onclick="openSubtab(event,\'{group_id}\',\'{group_id}-{phase}\')">{label}</button>')
        html.append('</div>')

        for i, phase in enumerate(phases_for_prof):
            active = " active" if i == 0 else ""
            table_id = f"table-{group_id}-{phase}"
            combos = []
            for ph, scores in bphs[phase][prof].items():
                st = calculate_stats(scores)
                elapsed_list = bphe.get(phase, {}).get(prof, {}).get(ph, [])
                avg_e = sum(elapsed_list) / len(elapsed_list) if elapsed_list else 0.0
                dim_means = {k: sum(v) / len(v) for k, v in bphd[prof][ph].items() if v}
                combos.append({"stats": st, "elapsed": avg_e, "params": hp[ph], "dims": dim_means})
            combos.sort(key=lambda x: x["stats"]["mean"], reverse=True)

            html.append(f'<div class="subtab-content{active}" id="{group_id}-{phase}">')
            html.append(f'<input class="search-box" placeholder="🔎 filter by parameter/value..." '
                        f'oninput="filterTable(this, \'{table_id}\')">')
            html.append(f'<table id="{table_id}"><thead><tr>'
                        f'<th onclick="sortTable(\'{table_id}\',0,true)">#</th>'
                        f'<th onclick="sortTable(\'{table_id}\',1,true)">Score</th>'
                        f'<th onclick="sortTable(\'{table_id}\',2,true)">Latencia</th>'
                        f'<th>Parameters</th><th>Dimensions</th></tr></thead><tbody>')
            for i2, c in enumerate(combos[:15]):
                html.append(f'<tr><td>#{i2+1}</td>'
                            f'<td><b style="color:var(--primary);">{c["stats"]["mean"]:.4f}</b> '
                            f'<small style="color:var(--text-muted);">±{c["stats"]["std"]:.3f} (n={c["stats"]["n"]})</small></td>'
                            f'<td>{c["elapsed"]:.1f}s</td>'
                            f'<td>{build_params_badges(c["params"])}</td>'
                            f'<td>{build_dims_badges(c["dims"])}</td></tr>')
            html.append('</tbody></table></div>')
        html.append('</div>')
    html.append('</div>')

    # ── TAB: degeneration (the point of this whole feature) ──
    html.append('<div id="tab-degen" class="tab-content">')
    html.append('<div class="card"><h3>🔁 Combinations ranked by degeneration rate</h3>')
    html.append('<div class="empty-note">Percentage of records for a combination that triggered the repetition detector '
                "(n-gram loop, repeated lines, low vocabulary uniqueness), where another dimension's score "
                'could be strong even though the actual response was looped.</div>')
    degen_rows = []
    for ph, total in degen_total.items():
        hits = degen_hits.get(ph, 0)
        if total == 0:
            continue
        rate = hits / total
        degen_rows.append((rate, hits, total, ph))
    degen_rows.sort(reverse=True)
    if degen_rows:
        html.append('<table id="table-degen"><thead><tr>'
                    '<th onclick="sortTable(\'table-degen\',0,true)">Miera</th>'
                    '<th>Hits</th><th>Parameters</th><th>Example flagu</th></tr></thead><tbody>')
        for rate, hits, total, ph in degen_rows[:25]:
            pct = round(rate * 100)
            examples = ", ".join(degen_examples.get(ph, [])[:2])
            html.append(f'<tr><td><span class="degen-bar-track"><span class="degen-bar-fill" '
                        f'style="width:{pct}%;"></span></span> {pct}%</td>'
                        f'<td>{hits}/{total}</td>'
                        f'<td>{build_params_badges(hp[ph])}</td>'
                        f'<td style="font-family:monospace;font-size:11px;color:var(--danger);">{examples}</td></tr>')
        html.append('</tbody></table>')
    else:
        html.append('<div class="empty-note">No degeneration detected ✓ — all tested combinations produced varied text.</div>')
    html.append('</div></div>')

    # ── TAB: sensitivity (pooled) ──
    html.append('<div id="tab-sensitivity" class="tab-content">')
    for p_name in ["temperature", "min_p", "top_p", "repetition_penalty"]:
        if p_name not in p_imp:
            continue
        html.append(f'<div class="card" style="margin-bottom:20px;"><h3>Vplyv parametra: {p_name}</h3>'
                    f'<table><tr><th>Value</th><th>Average score</th><th>Samples</th><th>Dimensions</th></tr>')
        for val in sorted(p_imp[p_name].keys()):
            st = calculate_stats(p_imp[p_name][val])
            d_means = {k: sum(v) / len(v) for k, v in p_dim[p_name][val].items() if v}
            html.append(f'<tr><td><span class="badge bg-gray-800 text-gray-300">{val}</span></td>'
                        f'<td><b>{st["mean"]:.4f}</b> <small style="color:var(--text-muted);">±{st["std"]:.3f}</small></td>'
                        f'<td>{st["n"]}</td><td>{build_dims_badges(d_means)}</td></tr>')
        html.append('</table></div>')
    html.append('</div>')

    # ── TAB: prompts (pooled) ──
    html.append('<div id="tab-prompts" class="tab-content"><div class="card"><h3>Test difficulty (hardest first)</h3>'
                '<table><tr><th>Prompt ID</th><th>Average score</th><th>Best score</th><th>Best parameters</th></tr>')
    prompt_list = []
    for pid, ph_scores in pm.items():
        all_sc, best_sc, best_ph = [], -1.0, None
        for ph, sc_list in ph_scores.items():
            all_sc.extend(sc_list)
            avg = sum(sc_list) / len(sc_list)
            if avg > best_sc:
                best_sc, best_ph = avg, ph
        if all_sc:
            prompt_list.append({"pid": pid, "avg": sum(all_sc) / len(all_sc), "best_sc": best_sc, "params": hp.get(best_ph, {})})
    prompt_list.sort(key=lambda x: x["avg"])
    for p in prompt_list:
        html.append(f'<tr><td><code>{p["pid"]}</code></td>'
                    f'<td style="color:var(--danger);"><b>{p["avg"]:.3f}</b></td>'
                    f'<td style="color:var(--success);">{p["best_sc"]:.3f}</td>'
                    f'<td>{build_params_badges(p["params"])}</td></tr>')
    html.append('</table></div></div>')

    # ── TAB: flags (pooled) ──
    html.append('<div id="tab-flags" class="tab-content">')
    for p_name in ["temperature", "repetition_penalty"]:
        if p_name not in p_flags:
            continue
        html.append(f'<div class="card" style="margin-bottom:20px;"><h3>Errors/flags for: {p_name}</h3>'
                    f'<table><tr><th>Value</th><th>Occurrences</th></tr>')
        for val in sorted(p_flags[p_name].keys()):
            flags = p_flags[p_name][val]
            if not flags:
                f_str = '<span style="color:var(--success);">None ✓</span>'
            else:
                f_str = " ".join(f'<span class="badge" style="background:var(--danger);color:white;">{fl}: {cnt}x</span>'
                                 for fl, cnt in sorted(flags.items(), key=lambda x: -x[1]))
            html.append(f'<tr><td><span class="badge bg-gray-800 text-gray-300">{val}</span></td><td>{f_str}</td></tr>')
        html.append('</table></div>')
    html.append('</div>')

    # ── charts JS ──
    degen_by_temp = {}
    for ph, total in degen_total.items():
        t = hp.get(ph, {}).get("temperature")
        if t is None:
            continue
        degen_by_temp.setdefault(t, [0, 0])
        degen_by_temp[t][0] += degen_hits.get(ph, 0)
        degen_by_temp[t][1] += total
    degen_temps = sorted(degen_by_temp.keys())
    degen_rates = [round(100 * degen_by_temp[t][0] / degen_by_temp[t][1], 1) if degen_by_temp[t][1] else 0 for t in degen_temps]

    html.append(f"""</div>
<script>
new Chart(document.getElementById('tempChart').getContext('2d'), {{
    type: 'line',
    data: {{ labels: {json.dumps(temp_vals)}, datasets: [{{
        label: 'Average score', data: {json.dumps(temp_scores)},
        borderColor: '#38bdf8', backgroundColor: 'rgba(56,189,248,0.15)', fill: true, tension: 0.3, borderWidth: 3
    }}] }},
    options: {{ responsive: true, scales: {{ y: {{ grid: {{ color: '#334155' }} }}, x: {{ grid: {{ color: '#334155' }} }} }} }}
}});
new Chart(document.getElementById('degenChart').getContext('2d'), {{
    type: 'bar',
    data: {{ labels: {json.dumps(degen_temps)}, datasets: [{{
        label: '% of records with loops', data: {json.dumps(degen_rates)},
        backgroundColor: '#f87171', borderRadius: 6
    }}] }},
    options: {{ responsive: true, scales: {{ y: {{ grid: {{ color: '#334155' }}, suggestedMax: 100 }}, x: {{ grid: {{ color: '#334155' }} }} }} }}
}});
</script>
</body></html>""")

    with open(html_file, "w", encoding="utf-8") as f:
        f.write("".join(html))
    return html_file


# ═══════════════════════════════════════════════════════════════
#  INDEX / COMPARISON PAGE
# ═══════════════════════════════════════════════════════════════

def generate_index(by_model: dict, dashboard_files: dict) -> Path:
    index_file = DASH_DIR / "index.html"

    # best mean score per (profile, model), pooled across phases
    comparison = defaultdict(dict)   # profile -> model -> best_mean
    profiles_seen = set()
    for model, records in by_model.items():
        analysis = run_deep_analysis(records)
        bphs = analysis["by_phase_prof_hash_scores"]
        for phase in bphs:
            for prof, hashes in bphs[phase].items():
                profiles_seen.add(prof)
                for ph, scores in hashes.items():
                    mean = sum(scores) / len(scores)
                    prev = comparison[prof].get(model, -1)
                    if mean > prev:
                        comparison[prof][model] = round(mean, 4)

    profiles_sorted = sorted(profiles_seen)
    models_sorted = sorted(by_model.keys())

    html = [f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Senerenai-HyperProbe — Model overview</title>
<style>{BASE_CSS}</style><script>{TABLE_JS}</script></head>
<body>
<div class="header"><h1>🔬 Senerenai-HyperProbe — Model overview</h1>
<span class="badge" style="background:var(--primary);color:#000;">{len(models_sorted)} models</span></div>
<div class="container">
<div class="section-title">📋 Benchmark result sets</div>
<table><tr><th>Model and search design</th><th>Samples</th><th>Dashboard</th></tr>"""]
    for model in models_sorted:
        n = len(by_model[model])
        f = dashboard_files[model].name
        html.append(f'<tr><td><b>{model}</b></td><td>{n}</td>'
                    f'<td><a href="{f}" style="color:var(--primary);">open →</a></td></tr>')
    html.append('</table>')

    html.append('<div class="section-title">⚖️ Comparison by profile (best average score)</div>')
    html.append('<div class="empty-note">Click a column header to sort.</div>')
    html.append('<table id="table-compare"><thead><tr>'
                '<th onclick="sortTable(\'table-compare\',0,false)">Profile</th>')
    for i, model in enumerate(models_sorted, 1):
        html.append(f'<th onclick="sortTable(\'table-compare\',{i},true)">{model}</th>')
    html.append('</tr></thead><tbody>')
    for prof in profiles_sorted:
        icon = PROF_ICONS.get(prof, "📋")
        html.append(f'<tr><td>{icon} {prof}</td>')
        row_vals = comparison[prof]
        best_val = max(row_vals.values()) if row_vals else None
        for model in models_sorted:
            v = row_vals.get(model)
            if v is None:
                html.append('<td style="color:var(--text-muted);">—</td>')
            elif best_val is not None and v == best_val:
                html.append(f'<td><b style="color:var(--success);">{v:.4f} 🏆</b></td>')
            else:
                html.append(f'<td>{v:.4f}</td>')
        html.append('</tr>')
    html.append('</tbody></table></div></body></html>')

    with open(index_file, "w", encoding="utf-8") as f:
        f.write("".join(html))
    return index_file


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    print("Loading and analyzing benchmark data...")
    records = load_all_data()
    if not records:
        print("No JSONL benchmark files were found in results/.")
        return

    by_model = group_by_model(records)
    print(f"Found {len(by_model)} model(s): {', '.join(sorted(by_model.keys()))}")

    dashboard_files = {}
    for model, model_records in by_model.items():
        f = generate_model_dashboard(model, model_records)
        dashboard_files[model] = f
        print(f"  {model}: {len(model_records)} records -> {f}")

    index_file = generate_index(by_model, dashboard_files)
    print(f"\nDashboard generated at: {index_file}")
    print("Tip: on a headless server, serve results/dashboards with:")
    print("   python3 -m http.server 8000")


if __name__ == "__main__":
    main()