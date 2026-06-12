#!/usr/bin/env python3
"""Produce the README figures from a finished pipeline run.

Usage:
    python scripts/make_figures.py --results results/latest --out docs/figures
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

COLOR_RAW = "#9aa3af"
COLOR_STD = "#1f6feb"
COLOR_ACC = "#d33f49"


def fig_long_tail(df: pd.DataFrame, out: Path) -> None:
    """Rank-frequency (log-log) of raw names vs. standardized labels."""
    raw = df["raw_name"].value_counts().to_numpy()
    std = df.loc[df["pred_label"] != "UNMATCHED", "pred_label"].value_counts().to_numpy()
    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=150)
    ax.loglog(range(1, len(raw) + 1), raw, ".", ms=3, color=COLOR_RAW,
              label=f"raw names ({len(raw):,} unique)")
    ax.loglog(range(1, len(std) + 1), std, ".", ms=5, color=COLOR_STD,
              label=f"standardized labels ({len(std):,} unique)")
    ax.set_xlabel("rank")
    ax.set_ylabel("frequency")
    ax.set_title("Long-tail collapse: raw name variants \u2192 canonical labels")
    ax.legend(frameon=False)
    ax.grid(alpha=0.25, which="both")
    fig.tight_layout()
    fig.savefig(out / "long_tail.png")
    plt.close(fig)


def fig_funnel(metrics: dict, df: pd.DataFrame, out: Path) -> None:
    """Row counts surviving each pipeline stage."""
    stages = [
        ("input rows", metrics["n_rows_input"]),
        ("after target filter", metrics["n_rows_after_filter"]),
        ("matched to canon", int((df["pred_label"] != "UNMATCHED").sum())),
    ]
    names = [s[0] for s in stages]
    vals = [s[1] for s in stages]
    fig, ax = plt.subplots(figsize=(7, 3.6), dpi=150)
    bars = ax.barh(names[::-1], vals[::-1], color=[COLOR_STD, "#5a93f0", COLOR_RAW][::-1])
    for bar, val in zip(bars, vals[::-1]):
        ax.text(bar.get_width() * 1.01, bar.get_y() + bar.get_height() / 2,
                f"{val:,}", va="center", fontsize=9)
    ax.set_xlim(0, max(vals) * 1.15)
    ax.set_title("Pipeline funnel (synthetic benchmark)")
    ax.grid(alpha=0.25, axis="x")
    fig.tight_layout()
    fig.savefig(out / "funnel.png")
    plt.close(fig)


def fig_threshold(sweep: pd.DataFrame, threshold: float, out: Path) -> None:
    """Coverage/accuracy trade-off across abstention thresholds."""
    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=150)
    ax.plot(sweep["threshold"], sweep["coverage"], "-o", ms=3.5,
            color=COLOR_RAW, label="coverage")
    ax.plot(sweep["threshold"], sweep["matched_accuracy"], "-o", ms=3.5,
            color=COLOR_ACC, label="matched accuracy")
    ax.plot(sweep["threshold"], sweep["overall_accuracy"], "-o", ms=3.5,
            color=COLOR_STD, label="overall accuracy")
    ax.axvline(threshold, ls="--", lw=1, color="black", alpha=0.6)
    metric_cols = ["coverage", "matched_accuracy", "overall_accuracy"]
    y_min = max(0.0, float(sweep[metric_cols].min().min()) - 0.02)
    ax.set_ylim(y_min, 1.005)
    ax.text(threshold + 0.01, y_min + 0.005, f"operating point ({threshold})", fontsize=8)
    ax.set_xlabel("abstention threshold")
    ax.set_ylabel("metric value")
    ax.set_title("Threshold sweep: coverage vs. precision")
    ax.legend(frameon=False, loc="lower left")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out / "threshold_sweep.png")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=ROOT / "results/latest")
    parser.add_argument("--out", type=Path, default=ROOT / "docs/figures")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.results / "standardized.csv")
    metrics = json.loads((args.results / "metrics.json").read_text(encoding="utf-8"))
    fig_long_tail(df, args.out)
    fig_funnel(metrics, df, args.out)
    sweep_path = args.results / "threshold_sweep.csv"
    if sweep_path.exists():
        fig_threshold(pd.read_csv(sweep_path), metrics["threshold"], args.out)
    print(f"figures written to {args.out}")


if __name__ == "__main__":
    main()
