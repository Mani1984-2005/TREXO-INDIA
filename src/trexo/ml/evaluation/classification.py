from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score, roc_auc_score, precision_score, recall_score,
                             f1_score, confusion_matrix, brier_score_loss, fbeta_score)


def best_threshold_fbeta(y, p, beta=2.0, grid=None):
    """Threshold maximising F-beta (recall-weighted: missing a dead-stock risk costs more
    than a false alarm). Chosen on validation data only."""
    grid = np.unique(np.quantile(p, np.linspace(0.02, 0.98, 97))) if grid is None else grid
    scores = [fbeta_score(y, p >= t, beta=beta, zero_division=0) for t in grid]
    return float(grid[int(np.argmax(scores))])


def calibration_table(y, p, bins=10):
    df = pd.DataFrame({"y": y, "p": p})
    df["bin"] = pd.qcut(df["p"], bins, duplicates="drop")
    t = df.groupby("bin", observed=True).agg(n=("y", "size"), mean_pred=("p", "mean"),
                                             observed=("y", "mean")).reset_index(drop=True)
    return t


def expected_calibration_error(y, p, bins=10) -> float:
    t = calibration_table(y, p, bins)
    return float((t["n"] * (t["mean_pred"] - t["observed"]).abs()).sum() / t["n"].sum())


def evaluate_binary(y, p, threshold: float) -> dict:
    y = np.asarray(y); p = np.asarray(p, float); pred = (p >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {
        "n": int(len(y)), "prevalence": float(y.mean()), "threshold": float(threshold),
        "roc_auc": float(roc_auc_score(y, p)), "pr_auc": float(average_precision_score(y, p)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "f2": float(fbeta_score(y, pred, beta=2, zero_division=0)),
        "false_positive_rate": float(fp / max(fp + tn, 1)),
        "false_negative_rate": float(fn / max(fn + tp, 1)),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "brier": float(brier_score_loss(y, p)),
        "brier_prevalence_baseline": float(brier_score_loss(y, np.full(len(y), y.mean()))),
        "ece": expected_calibration_error(y, p),
    }
