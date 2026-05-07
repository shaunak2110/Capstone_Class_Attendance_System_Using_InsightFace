"""
Publication-quality visualization generator for the face recognition benchmark.

Reads: results/final_benchmark/aggregated_summary.json
       results/final_benchmark/metrics_*.json  (for EER sweep data)
       results/final_benchmark/predictions_*.csv (for confusion matrix)

Saves: results/final_benchmark/figures/*.png  (300 DPI)
                                    *.pdf
       results/final_benchmark/figures_summary.md

Run from workspace root:
    python backend/evaluation/generate_figures.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_EVAL_ROOT   = Path(__file__).resolve().parent
_BENCH_DIR   = _EVAL_ROOT / "results" / "final_benchmark"
_FIGURES_DIR = _BENCH_DIR / "figures"
_FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Academic style
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "font.family":       "DejaVu Sans",
    "font.size":         13,
    "axes.titlesize":    15,
    "axes.labelsize":    13,
    "xtick.labelsize":   11,
    "ytick.labelsize":   11,
    "legend.fontsize":   11,
    "figure.dpi":        150,
    "savefig.dpi":       300,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":         True,
    "grid.alpha":        0.3,
    "grid.linestyle":    "--",
})

DPI = 300

# ---------------------------------------------------------------------------
# Colour palette — consistent across all figures
# ---------------------------------------------------------------------------
PALETTE = {
    "haarcascade_lbph":         "#E07B54",   # warm orange
    "haarcascade_insightface":  "#5B8DB8",   # steel blue
    "insightface_lbph":         "#6BAE75",   # sage green
    "insightface_insightface":  "#9B59B6",   # purple  ← best
}
BEST_KEY = "insightface_insightface"

LABELS = {
    "haarcascade_lbph":         "Haar + LBPH",
    "haarcascade_insightface":  "Haar + ArcFace",
    "insightface_lbph":         "InsightFace + LBPH",
    "insightface_insightface":  "InsightFace + ArcFace",
}

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def load_summary() -> list:
    with open(_BENCH_DIR / "aggregated_summary.json") as f:
        return json.load(f)


def combo_key(entry: dict) -> str:
    return f"{entry['detector']}_{entry['recognizer']}"


def save_fig(fig, name: str) -> None:
    for ext in ("png", "pdf"):
        path = _FIGURES_DIR / f"{name}.{ext}"
        fig.savefig(str(path), dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {name}.png / .pdf")


# ---------------------------------------------------------------------------
# Figure 1 — Accuracy comparison bar chart
# ---------------------------------------------------------------------------

def fig_accuracy(data: list) -> None:
    keys   = [combo_key(d) for d in data]
    means  = [d["accuracy_mean"] * 100 for d in data]
    stds   = [d["accuracy_std"]  * 100 for d in data]
    colors = [PALETTE[k] for k in keys]
    labels = [LABELS[k]  for k in keys]

    fig, ax = plt.subplots(figsize=(9, 5.5))
    x = np.arange(len(keys))
    bars = ax.bar(x, means, yerr=stds, capsize=6, color=colors,
                  edgecolor="white", linewidth=0.8, width=0.55,
                  error_kw={"elinewidth": 1.8, "ecolor": "#333"})

    # Highlight best
    best_idx = keys.index(BEST_KEY)
    bars[best_idx].set_edgecolor("#FFD700")
    bars[best_idx].set_linewidth(2.5)

    # Value labels
    for bar, m, s in zip(bars, means, stds):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + s + 1.2,
                f"{m:.1f}%", ha="center", va="bottom",
                fontsize=10, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("Recognition Accuracy (%)")
    ax.set_title("Recognition Accuracy Comparison\n(mean ± std, 3 independent runs, threshold = 0.50)")
    ax.set_ylim(0, 115)
    ax.axhline(100, color="gray", linestyle=":", linewidth=0.8)

    # Best marker
    ax.annotate("★ Best", xy=(best_idx, means[best_idx] + stds[best_idx] + 6),
                ha="center", fontsize=11, color="#9B59B6", fontweight="bold")

    fig.tight_layout()
    save_fig(fig, "fig1_accuracy_comparison")


# ---------------------------------------------------------------------------
# Figure 2 — Detection rate comparison
# ---------------------------------------------------------------------------

def fig_detection_rate(data: list) -> None:
    keys   = [combo_key(d) for d in data]
    means  = [d["detection_rate_mean"] * 100 for d in data]
    stds   = [d["detection_rate_std"]  * 100 for d in data]
    colors = [PALETTE[k] for k in keys]
    labels = [LABELS[k]  for k in keys]

    fig, ax = plt.subplots(figsize=(9, 5.5))
    x = np.arange(len(keys))
    bars = ax.bar(x, means, yerr=stds, capsize=6, color=colors,
                  edgecolor="white", linewidth=0.8, width=0.55,
                  error_kw={"elinewidth": 1.8, "ecolor": "#333"})

    for bar, m, s in zip(bars, means, stds):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + s + 0.8,
                f"{m:.1f}%", ha="center", va="bottom",
                fontsize=10, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("Face Detection Rate (%)")
    ax.set_title("Face Detection Rate by Detector\n(mean ± std, 3 independent runs)")
    ax.set_ylim(0, 115)

    # Detector grouping annotation
    ax.axvline(1.5, color="gray", linestyle="--", linewidth=1, alpha=0.5)
    ax.text(0.75, 108, "Haarcascade\nDetector", ha="center", fontsize=10,
            color="gray", style="italic")
    ax.text(2.75, 108, "InsightFace\nDetector", ha="center", fontsize=10,
            color="gray", style="italic")

    fig.tight_layout()
    save_fig(fig, "fig2_detection_rate")


# ---------------------------------------------------------------------------
# Figure 3 — FAR vs FRR grouped bar chart
# ---------------------------------------------------------------------------

def fig_far_frr(data: list) -> None:
    keys   = [combo_key(d) for d in data]
    labels = [LABELS[k]  for k in keys]
    frr_m  = [d["frr_mean"]  * 100 for d in data]
    frr_s  = [d["frr_std"]   * 100 for d in data]
    eer_m  = [d["eer_mean"]  * 100 for d in data]
    eer_s  = [d["eer_std"]   * 100 for d in data]

    x     = np.arange(len(keys))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 5.5))

    bars_frr = ax.bar(x - width / 2, frr_m, width, yerr=frr_s, capsize=5,
                      label="FRR (%)", color="#E07B54", alpha=0.85,
                      error_kw={"elinewidth": 1.5, "ecolor": "#333"})
    bars_eer = ax.bar(x + width / 2, eer_m, width, yerr=eer_s, capsize=5,
                      label="EER (%)", color="#5B8DB8", alpha=0.85,
                      error_kw={"elinewidth": 1.5, "ecolor": "#333"})

    # Highlight best
    best_idx = keys.index(BEST_KEY)
    for bar in [bars_frr[best_idx], bars_eer[best_idx]]:
        bar.set_edgecolor("#FFD700")
        bar.set_linewidth(2.5)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("Error Rate (%)")
    ax.set_title("False Rejection Rate (FRR) and Equal Error Rate (EER)\n(mean ± std, 3 independent runs)")
    ax.set_ylim(0, 130)
    ax.legend(loc="upper right")

    # Value labels on EER bars (more informative)
    for bar, m, s in zip(bars_eer, eer_m, eer_s):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + s + 1.5,
                f"{m:.1f}%", ha="center", va="bottom",
                fontsize=9, color="#5B8DB8", fontweight="bold")

    fig.tight_layout()
    save_fig(fig, "fig3_far_frr_comparison")


# ---------------------------------------------------------------------------
# Figure 4 — EER comparison (standalone, sorted)
# ---------------------------------------------------------------------------

def fig_eer(data: list) -> None:
    sorted_data = sorted(data, key=lambda d: d["eer_mean"])
    keys   = [combo_key(d) for d in sorted_data]
    means  = [d["eer_mean"] * 100 for d in sorted_data]
    stds   = [d["eer_std"]  * 100 for d in sorted_data]
    colors = [PALETTE[k] for k in keys]
    labels = [LABELS[k]  for k in keys]

    fig, ax = plt.subplots(figsize=(9, 5.5))
    x = np.arange(len(keys))
    bars = ax.bar(x, means, yerr=stds, capsize=6, color=colors,
                  edgecolor="white", linewidth=0.8, width=0.55,
                  error_kw={"elinewidth": 1.8, "ecolor": "#333"})

    best_idx = keys.index(BEST_KEY)
    bars[best_idx].set_edgecolor("#FFD700")
    bars[best_idx].set_linewidth(2.5)

    for bar, m, s in zip(bars, means, stds):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + s + 0.5,
                f"{m:.1f}%", ha="center", va="bottom",
                fontsize=10, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("Equal Error Rate (%)")
    ax.set_title("Equal Error Rate (EER) — Lower is Better\n(mean ± std, sorted ascending, 3 runs)")
    ax.set_ylim(0, max(means) * 1.4 + 5)

    ax.annotate("★ Best", xy=(best_idx, means[best_idx] + stds[best_idx] + 2),
                ha="center", fontsize=11, color="#9B59B6", fontweight="bold")

    fig.tight_layout()
    save_fig(fig, "fig4_eer_comparison")


# ---------------------------------------------------------------------------
# Figure 5 — Latency comparison (stacked: detection + recognition)
# ---------------------------------------------------------------------------

def fig_latency(data: list) -> None:
    keys    = [combo_key(d) for d in data]
    labels  = [LABELS[k]  for k in keys]
    det_ms  = [d["detection_ms_mean"]   for d in data]
    rec_ms  = [d["recognition_ms_mean"] for d in data]
    lat_std = [d["latency_std_ms"]      for d in data]

    x     = np.arange(len(keys))
    width = 0.55

    fig, ax = plt.subplots(figsize=(9, 5.5))

    bars_det = ax.bar(x, det_ms, width, label="Detection (ms)",
                      color="#5B8DB8", alpha=0.85)
    bars_rec = ax.bar(x, rec_ms, width, bottom=det_ms,
                      label="Recognition (ms)", color="#E07B54", alpha=0.85)

    # Error bars on total
    totals = [d + r for d, r in zip(det_ms, rec_ms)]
    ax.errorbar(x, totals, yerr=lat_std, fmt="none",
                ecolor="#333", elinewidth=1.8, capsize=6)

    # Total labels
    for xi, (t, s) in enumerate(zip(totals, lat_std)):
        ax.text(xi, t + s + 3, f"{t:.0f}ms", ha="center", va="bottom",
                fontsize=10, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("Mean Latency per Image (ms)")
    ax.set_title("Pipeline Latency: Detection + Recognition\n(mean ± std, 3 independent runs)")
    ax.legend(loc="upper left")
    ax.set_ylim(0, max(totals) * 1.35)

    fig.tight_layout()
    save_fig(fig, "fig5_latency_comparison")


# ---------------------------------------------------------------------------
# Figure 6 — DET curves (FAR vs FRR sweep) for each combination
# ---------------------------------------------------------------------------

def fig_det_curves(data: list) -> None:
    """
    Load EER sweep data from per-run metrics JSONs and plot DET curves.
    Average sweep across runs per combination.
    """
    fig, ax = plt.subplots(figsize=(7, 6))

    for entry in data:
        key   = combo_key(entry)
        label = LABELS[key]
        color = PALETTE[key]

        # Collect sweep arrays across runs
        all_far: list[list] = []
        all_frr: list[list] = []

        for run in entry["per_run"]:
            exp_id = run["experiment_id"]
            mpath  = _BENCH_DIR / f"metrics_{exp_id}.json"
            if not mpath.exists():
                continue
            with open(mpath) as f:
                m = json.load(f)
            sweep = m.get("eer", {})
            far_arr = sweep.get("sweep_far", [])
            frr_arr = sweep.get("sweep_frr", [])
            if far_arr and frr_arr:
                all_far.append(far_arr)
                all_frr.append(frr_arr)

        if not all_far:
            continue

        # Average across runs (same length guaranteed by our sweep logic)
        min_len = min(len(a) for a in all_far)
        avg_far = np.mean([a[:min_len] for a in all_far], axis=0)
        avg_frr = np.mean([a[:min_len] for a in all_frr], axis=0)

        lw = 2.5 if key == BEST_KEY else 1.5
        ls = "-"  if key == BEST_KEY else "--"
        ax.plot(avg_far * 100, avg_frr * 100,
                color=color, linewidth=lw, linestyle=ls, label=label)

    # Diagonal reference
    ax.plot([0, 100], [0, 100], "k:", linewidth=0.8, alpha=0.4, label="Chance")

    ax.set_xlabel("False Acceptance Rate (%)")
    ax.set_ylabel("False Rejection Rate (%)")
    ax.set_title("Detection Error Tradeoff (DET) Curves\n(averaged across 3 runs)")
    ax.legend(loc="upper right", fontsize=10)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)

    fig.tight_layout()
    save_fig(fig, "fig6_det_curves")


# ---------------------------------------------------------------------------
# Figure 7 — Confusion matrix for best system (insightface + insightface)
# ---------------------------------------------------------------------------

def fig_confusion_matrix(data: list) -> None:
    """
    Build confusion matrix from the best system's predictions CSV (run 0).
    """
    best_entry = next(d for d in data if combo_key(d) == BEST_KEY)
    run0_id    = best_entry["per_run"][0]["experiment_id"]
    csv_path   = _BENCH_DIR / f"predictions_{run0_id}.csv"

    if not csv_path.exists():
        print(f"  Skipping confusion matrix — {csv_path.name} not found")
        return

    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))

    # Collect labels
    true_labels = sorted({r["true_label"] for r in rows if r["true_label"]})
    pred_labels = sorted({r["predicted_label"]
                          for r in rows
                          if r["predicted_label"] and r["predicted_label"] != ""})
    all_labels  = sorted(set(true_labels) | set(pred_labels))

    # Short display names
    short = {lbl: lbl.replace("person_", "P").replace("_", "\n")
             for lbl in all_labels}

    n = len(all_labels)
    idx = {lbl: i for i, lbl in enumerate(all_labels)}
    matrix = np.zeros((n, n), dtype=int)

    for r in rows:
        tl = r["true_label"]
        pl = r["predicted_label"]
        if tl in idx and pl in idx:
            matrix[idx[tl], idx[pl]] += 1

    # Normalise by row (true label)
    row_sums = matrix.sum(axis=1, keepdims=True)
    norm_matrix = np.where(row_sums > 0, matrix / row_sums, 0)

    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(norm_matrix, cmap="Blues", vmin=0, vmax=1)

    tick_labels = [short[lbl] for lbl in all_labels]
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(tick_labels, fontsize=10)
    ax.set_yticklabels(tick_labels, fontsize=10)
    ax.set_xlabel("Predicted Identity")
    ax.set_ylabel("True Identity")
    ax.set_title(f"Confusion Matrix — InsightFace + ArcFace\n(Run 0, seed=42, normalised by row)")

    # Cell annotations
    for i in range(n):
        for j in range(n):
            val = norm_matrix[i, j]
            text_color = "white" if val > 0.6 else "black"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                    fontsize=11, color=text_color, fontweight="bold")

    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Fraction")
    fig.tight_layout()
    save_fig(fig, "fig7_confusion_matrix_best")


# ---------------------------------------------------------------------------
# Figure 8 — Summary radar / spider chart
# ---------------------------------------------------------------------------

def fig_radar(data: list) -> None:
    """
    Radar chart comparing 4 metrics across all combinations.
    Metrics: Accuracy, Detection Rate, 1-EER (higher=better), 1-FRR (higher=better)
    """
    categories = ["Accuracy", "Detection\nRate", "1 − EER\n(higher=better)",
                  "1 − FRR\n(higher=better)"]
    N = len(categories)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]  # close the polygon

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw={"polar": True})

    for entry in data:
        key   = combo_key(entry)
        label = LABELS[key]
        color = PALETTE[key]
        lw    = 2.5 if key == BEST_KEY else 1.5

        acc     = entry["accuracy_mean"]
        det     = entry["detection_rate_mean"]
        one_eer = 1.0 - entry["eer_mean"]
        frr     = entry["frr_mean"]
        one_frr = 1.0 - frr if frr is not None else 0.0

        values = [acc, det, one_eer, one_frr]
        values += values[:1]

        ax.plot(angles, values, color=color, linewidth=lw, label=label)
        ax.fill(angles, values, color=color, alpha=0.08)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=11)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0.25", "0.50", "0.75", "1.00"], fontsize=8)
    ax.set_title("Multi-Metric Radar Comparison\n(all metrics normalised to [0,1], higher=better)",
                 pad=20, fontsize=13)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.15), fontsize=10)

    fig.tight_layout()
    save_fig(fig, "fig8_radar_comparison")


# ---------------------------------------------------------------------------
# figures_summary.md
# ---------------------------------------------------------------------------

def write_summary(data: list) -> None:
    best = next(d for d in data if combo_key(d) == BEST_KEY)
    lines = [
        "# Benchmark Figures Summary",
        "",
        "All figures are saved as both PNG (300 DPI) and PDF in `results/final_benchmark/figures/`.",
        "",
        "## Dataset",
        "- 4 identities: person_1_sudhanshu, person_2_shaunak, person_3_srishti, person_4_ashlesha",
        "- 335 total images (50–106 per identity)",
        "- 70% gallery / 30% probe split, 3 independent runs per combination",
        "- Similarity threshold: 0.50",
        "",
        "## Figures",
        "",
        "### Figure 1 — `fig1_accuracy_comparison`",
        "Bar chart comparing recognition accuracy (mean ± std) across all 4 detector × recognizer",
        "combinations. The best-performing system (InsightFace + ArcFace) is highlighted with a",
        "gold border. Error bars represent standard deviation across 3 runs.",
        "",
        "### Figure 2 — `fig2_detection_rate`",
        "Bar chart showing face detection rate per combination. Haarcascade detects ~68% of probe",
        "images; InsightFace detects ~98%. A vertical divider separates the two detector groups.",
        "",
        "### Figure 3 — `fig3_far_frr_comparison`",
        "Grouped bar chart comparing FRR and EER side by side for each combination.",
        "LBPH-based systems show FRR = 100% (all genuine probes rejected at threshold 0.50),",
        "while ArcFace-based systems achieve FRR < 40%.",
        "",
        "### Figure 4 — `fig4_eer_comparison`",
        "Bar chart of Equal Error Rate (EER) sorted ascending (lower = better).",
        f"Best: InsightFace + ArcFace — EER = {best['eer_mean']*100:.1f}% ± {best['eer_std']*100:.1f}%.",
        "",
        "### Figure 5 — `fig5_latency_comparison`",
        "Stacked bar chart showing mean detection and recognition latency per image.",
        "Haarcascade + LBPH is fastest (~77 ms); InsightFace + ArcFace takes ~163 ms.",
        "",
        "### Figure 6 — `fig6_det_curves`",
        "Detection Error Tradeoff (DET) curves plotting FAR vs FRR across the full threshold sweep.",
        "Curves averaged across 3 runs. The best system (InsightFace + ArcFace) is shown with a",
        "solid line; others are dashed.",
        "",
        "### Figure 7 — `fig7_confusion_matrix_best`",
        "Row-normalised confusion matrix for the best system (InsightFace + ArcFace, run 0).",
        "Diagonal values show per-identity recall. Off-diagonal values reveal which identities",
        "are most frequently confused.",
        "",
        "### Figure 8 — `fig8_radar_comparison`",
        "Radar (spider) chart comparing 4 metrics simultaneously: Accuracy, Detection Rate,",
        "1−EER, and 1−FRR (all normalised to [0,1], higher = better). Provides a holistic",
        "view of each system's strengths and weaknesses.",
        "",
        "## Key Results",
        "",
        "| Detector | Recognizer | Accuracy | EER | Det. Rate | Latency |",
        "|---|---|---|---|---|---|",
    ]

    for d in sorted(data, key=lambda x: x["accuracy_mean"], reverse=True):
        det = d["detector"].capitalize()
        rec = "ArcFace" if d["recognizer"] == "insightface" else d["recognizer"].upper()
        acc = f"{d['accuracy_mean']*100:.1f}±{d['accuracy_std']*100:.1f}%"
        eer = f"{d['eer_mean']*100:.1f}±{d['eer_std']*100:.1f}%"
        dr  = f"{d['detection_rate_mean']*100:.1f}%"
        lat = f"{d['latency_mean_ms']:.0f}ms"
        lines.append(f"| {det} | {rec} | {acc} | {eer} | {dr} | {lat} |")

    lines += [
        "",
        "## Conclusion",
        "",
        f"The **InsightFace detector + ArcFace recognizer** combination achieves the highest",
        f"recognition accuracy ({best['accuracy_mean']*100:.1f}% ± {best['accuracy_std']*100:.1f}%)",
        f"and the lowest EER ({best['eer_mean']*100:.1f}% ± {best['eer_std']*100:.1f}%),",
        f"with a face detection rate of {best['detection_rate_mean']*100:.1f}%.",
        f"The trade-off is higher latency (~{best['latency_mean_ms']:.0f} ms/image vs ~77 ms for",
        f"Haarcascade + LBPH). For attendance systems where accuracy is paramount, InsightFace + ArcFace",
        f"is the recommended configuration.",
    ]

    summary_path = _BENCH_DIR / "figures_summary.md"
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Saved: figures_summary.md")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("  Generating publication-quality figures")
    print("=" * 60)
    print(f"  Input:  {_BENCH_DIR}")
    print(f"  Output: {_FIGURES_DIR}")
    print()

    data = load_summary()
    print(f"  Loaded {len(data)} combinations × {data[0]['n_runs']} runs each")
    print()

    print("[1/8] Accuracy comparison bar chart...")
    fig_accuracy(data)

    print("[2/8] Detection rate chart...")
    fig_detection_rate(data)

    print("[3/8] FAR vs FRR grouped chart...")
    fig_far_frr(data)

    print("[4/8] EER comparison chart...")
    fig_eer(data)

    print("[5/8] Latency comparison chart...")
    fig_latency(data)

    print("[6/8] DET curves...")
    fig_det_curves(data)

    print("[7/8] Confusion matrix (best system)...")
    fig_confusion_matrix(data)

    print("[8/8] Radar comparison chart...")
    fig_radar(data)

    print()
    print("Writing figures_summary.md...")
    write_summary(data)

    print()
    print("=" * 60)
    print(f"  Done. {len(list(_FIGURES_DIR.glob('*.png')))} PNG files saved.")
    print(f"  Output: {_FIGURES_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
