"""
Results analysis and chart generation.
Run after both run_experiment.py and baseline.py have completed.

Usage:
    cd src
    python analyze_results.py
"""

import os
import csv
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from config import RESULTS_DIR


def load_csv(filename):
    """Load results from CSV file."""
    path = os.path.join(RESULTS_DIR, filename)
    if not os.path.exists(path):
        print(f"Warning: {path} not found")
        return []
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        return list(reader)


def compute_metrics(results, label="System"):
    """Compute all evaluation metrics."""
    total = len(results)
    if total == 0:
        return {}

    success = sum(1 for r in results if r["success"] == "True" or r["success"] is True)
    success_rate = success / total * 100

    pass_at_1 = sum(1 for r in results
                    if (r["success"] == "True" or r["success"] is True)
                    and int(r["attempts"]) == 1)

    fixed = [r for r in results if r["success"] == "True" or r["success"] is True]
    avg_time = sum(float(r["time_seconds"]) for r in fixed) / len(fixed) if fixed else 0
    avg_attempts = sum(int(r["attempts"]) for r in fixed) / len(fixed) if fixed else 0
    total_time = sum(float(r["time_seconds"]) for r in results)

    metrics = {
        "label": label,
        "total": total,
        "success": success,
        "success_rate": round(success_rate, 1),
        "pass_at_1": pass_at_1,
        "pass_at_1_rate": round(pass_at_1 / total * 100, 1),
        "avg_time_fixed": round(avg_time, 1),
        "avg_attempts": round(avg_attempts, 1),
        "total_time": round(total_time, 1),
    }

    print(f"\n--- {label} ---")
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    return metrics


def plot_comparison(multi_metrics, baseline_metrics):
    """Generate comparison bar charts."""
    figures_dir = os.path.join(RESULTS_DIR, "figures")
    os.makedirs(figures_dir, exist_ok=True)

    # Chart 1: Success Rate Comparison
    fig, ax = plt.subplots(figsize=(8, 5))
    labels = ["Multi-Agent\n(Proposed)", "Single-Prompt\n(Baseline)"]
    values = [multi_metrics["success_rate"], baseline_metrics["success_rate"]]
    colors = ["#2196F3", "#FF9800"]
    bars = ax.bar(labels, values, color=colors, width=0.5, edgecolor="black", linewidth=0.8)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f"{val}%", ha="center", va="bottom", fontweight="bold", fontsize=12)
    ax.set_ylabel("Success Rate (%)", fontsize=12)
    ax.set_title("Repair Success Rate Comparison", fontsize=14, fontweight="bold")
    ax.set_ylim(0, 105)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(figures_dir, "success_rate_comparison.png"), dpi=150)
    plt.close()
    print("  Saved: success_rate_comparison.png")

    # Chart 2: Pass@1 Comparison
    fig, ax = plt.subplots(figsize=(8, 5))
    values = [multi_metrics["pass_at_1_rate"], baseline_metrics["pass_at_1_rate"]]
    bars = ax.bar(labels, values, color=colors, width=0.5, edgecolor="black", linewidth=0.8)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f"{val}%", ha="center", va="bottom", fontweight="bold", fontsize=12)
    ax.set_ylabel("Pass@1 Rate (%)", fontsize=12)
    ax.set_title("Pass@1 Comparison (Fixed on First Attempt)", fontsize=14, fontweight="bold")
    ax.set_ylim(0, 105)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(figures_dir, "pass_at_1_comparison.png"), dpi=150)
    plt.close()
    print("  Saved: pass_at_1_comparison.png")

    # Chart 3: Per-program results (multi-agent)
    fig, ax = plt.subplots(figsize=(14, 5))
    multi_results = load_csv("results.csv")
    programs = [r["program"] for r in multi_results]
    successes = [1 if r["success"] == "True" else 0 for r in multi_results]
    color_map = ["#4CAF50" if s else "#F44336" for s in successes]
    ax.bar(range(len(programs)), [1]*len(programs), color=color_map, edgecolor="black", linewidth=0.3)
    ax.set_xticks(range(len(programs)))
    ax.set_xticklabels(programs, rotation=90, fontsize=7)
    ax.set_yticks([])
    ax.set_title("Per-Program Recovery Results (Green=Fixed, Red=Failed)", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(figures_dir, "per_program_results.png"), dpi=150)
    plt.close()
    print("  Saved: per_program_results.png")

    # Chart 4: Metrics Summary Table as figure
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.axis("off")
    table_data = [
        ["Metric", "Multi-Agent (Proposed)", "Single-Prompt (Baseline)"],
        ["Programs Tested", str(multi_metrics["total"]), str(baseline_metrics["total"])],
        ["Bugs Fixed", str(multi_metrics["success"]), str(baseline_metrics["success"])],
        ["Success Rate", f"{multi_metrics['success_rate']}%", f"{baseline_metrics['success_rate']}%"],
        ["Pass@1", f"{multi_metrics['pass_at_1']}/{multi_metrics['total']}", f"{baseline_metrics['pass_at_1']}/{baseline_metrics['total']}"],
        ["Avg Time (fixed)", f"{multi_metrics['avg_time_fixed']}s", f"{baseline_metrics['avg_time_fixed']}s"],
        ["Avg Attempts", str(multi_metrics["avg_attempts"]), "1.0"],
    ]
    table = ax.table(cellText=table_data, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 1.8)
    # Style header row
    for j in range(3):
        table[0, j].set_facecolor("#2196F3")
        table[0, j].set_text_props(color="white", fontweight="bold")
    ax.set_title("Experimental Results Summary", fontsize=14, fontweight="bold", pad=20)
    plt.tight_layout()
    plt.savefig(os.path.join(figures_dir, "results_table.png"), dpi=150)
    plt.close()
    print("  Saved: results_table.png")


def main():
    print("=" * 60)
    print("RESULTS ANALYSIS")
    print("=" * 60)

    multi_results = load_csv("results.csv")
    baseline_results = load_csv("baseline_results.csv")

    if not multi_results:
        print("No multi-agent results found. Run run_experiment.py first.")
        return
    if not baseline_results:
        print("No baseline results found. Run baseline.py first.")
        return

    multi_metrics = compute_metrics(multi_results, "Multi-Agent System")
    baseline_metrics = compute_metrics(baseline_results, "Single-Prompt Baseline")

    print("\nGenerating charts...")
    plot_comparison(multi_metrics, baseline_metrics)

    print("\nDone! Check results/figures/ for all charts.")


if __name__ == "__main__":
    main()
