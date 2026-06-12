"""Evaluation harness for the standardization pipeline.

The original project reported a single hand-checked accuracy figure. This
module makes evaluation systematic and re-runnable against gold labels:

* coverage - share of rows the matcher committed to (did not abstain on)
* matched accuracy - precision of committed assignments
* overall accuracy - correct / all rows (abstentions count as errors)
* label reduction - unique raw variants vs. unique predicted labels
* threshold sweep - the coverage/precision trade-off curve, computed from a
  single scoring pass
"""

from __future__ import annotations

import pandas as pd

from menunorm.canonicalize import UNMATCHED


def compute_metrics(
    gold: pd.Series,
    pred: pd.Series,
    raw_names: pd.Series | None = None,
) -> dict[str, float | int]:
    """Compute standardization quality metrics.

    Args:
        gold: Gold canonical labels, aligned with ``pred``.
        pred: Predicted labels (``UNMATCHED`` marks abstentions).
        raw_names: Optional raw input names, used for the label-reduction
            statistic.

    Returns:
        Dict of scalar metrics.
    """
    if len(gold) != len(pred):
        raise ValueError("gold and pred must be aligned")
    total = len(gold)
    matched_mask = pred != UNMATCHED
    n_matched = int(matched_mask.sum())
    correct = int((pred[matched_mask] == gold[matched_mask]).sum())

    metrics: dict[str, float | int] = {
        "n_rows": total,
        "coverage": n_matched / total if total else 0.0,
        "matched_accuracy": correct / n_matched if n_matched else 0.0,
        "overall_accuracy": correct / total if total else 0.0,
        "n_unique_pred_labels": int(pred[matched_mask].nunique()),
    }
    if raw_names is not None:
        n_raw = int(raw_names.nunique())
        metrics["n_unique_raw_names"] = n_raw
        if n_raw:
            metrics["label_reduction_ratio"] = metrics["n_unique_pred_labels"] / n_raw
    return metrics


def threshold_sweep(frame: pd.DataFrame, thresholds: list[float]) -> pd.DataFrame:
    """Trace the coverage/accuracy trade-off across abstention thresholds.

    Operates on the row-level scores already produced by the pipeline, so the
    sweep costs no additional similarity computation.

    Args:
        frame: One row per data row with columns ``best_label``, ``score``,
            ``method`` and ``gold``.
        thresholds: Threshold values to evaluate.

    Returns:
        DataFrame with columns ``threshold``, ``coverage``,
        ``matched_accuracy``, ``overall_accuracy``.
    """
    total = len(frame)
    scorable = frame[frame["method"] != "empty"]
    rows = []
    for thr in thresholds:
        committed = scorable[scorable["score"] >= thr]
        n_matched = len(committed)
        correct = int((committed["best_label"] == committed["gold"]).sum())
        rows.append(
            {
                "threshold": thr,
                "coverage": n_matched / total if total else 0.0,
                "matched_accuracy": correct / n_matched if n_matched else 0.0,
                "overall_accuracy": correct / total if total else 0.0,
            }
        )
    return pd.DataFrame(rows)
