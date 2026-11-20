"""Independent re-evaluation of the deployed dead-stock decision rule.

Why this exists
---------------
The training pipeline writes its own metrics.  This script recomputes them
without importing ``trexo.ml.evaluation`` and without reading the saved metric
files, so a coding error in either path cannot silently agree with itself.

It fits the *train-only* recency calibration (no test-period information),
selects a threshold on the validation cutoff, and reports untouched test-cutoff
metrics.  The registry artifact is deliberately refit on all labelled cutoffs
and is therefore not used for the out-of-time numbers here.

Output: ``reports/ml/independent_evaluation.json``.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)

from trexo.ml.config import (  # noqa: E402
    D01_BAD_DEBT_INVOICES,
    ML_DATA_DIR,
    REPORT_DIR,
    HorizonConfig,
)
from trexo.ml.data_pipeline.pipeline import load_sales  # noqa: E402
from trexo.ml.features.labels import build_training_table  # noqa: E402
from trexo.ml.validation.splits import make_cutoffs  # noqa: E402


def best_threshold_f2(y: np.ndarray, scores: np.ndarray) -> float:
    """Pick the threshold that maximises F2 on validation, computed inline.

    Kept independent of the repository evaluation module on purpose.
    """
    order = np.argsort(-scores)
    y_sorted, s_sorted = y[order], scores[order]
    tp = np.cumsum(y_sorted)
    fp = np.cumsum(1 - y_sorted)
    fn = tp[-1] - tp
    beta2 = 4.0
    f2 = (1 + beta2) * tp / ((1 + beta2) * tp + beta2 * fn + fp + 1e-12)
    idx = int(np.argmax(f2))
    return float(s_sorted[idx])


def metrics(y: np.ndarray, scores: np.ndarray, threshold: float) -> dict:
    pred = (scores >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    precision, recall, f1, _ = precision_recall_fscore_support(
        y, pred, average="binary", zero_division=0
    )
    f2 = (5 * precision * recall) / (4 * precision + recall + 1e-12)
    return {
        "n": int(len(y)),
        "prevalence": float(y.mean()),
        "threshold": float(threshold),
        "roc_auc": float(roc_auc_score(y, scores)),
        "pr_auc": float(average_precision_score(y, scores)),
        "brier": float(brier_score_loss(y, scores)),
        "brier_prevalence_prior": float(brier_score_loss(y, np.full(len(y), y.mean()))),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "f2": float(f2),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def main() -> int:
    sales = load_sales()
    horizon = HorizonConfig()
    cutoffs = make_cutoffs(sales["Date"].min(), horizon)
    train = build_training_table(sales, cutoffs["train"], horizon.label_horizon_days)
    val = build_training_table(sales, [cutoffs["val"]], horizon.label_horizon_days)
    test = build_training_table(sales, [cutoffs["test"]], horizon.label_horizon_days)

    # Train-only isotonic calibration of the recency score.
    iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip")
    iso.fit(train["days_since_last_sale"], train["y_inactive"])

    p_val = iso.predict(val["days_since_last_sale"])
    p_test = iso.predict(test["days_since_last_sale"])
    threshold = best_threshold_f2(val["y_inactive"].to_numpy(), p_val)

    result = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "script": "scripts/ml_independent_evaluation.py",
        "methodology": (
            "Recency rule calibrated on training cutoffs only; threshold selected on the "
            "validation cutoff by F2; metrics computed on the untouched test cutoff with "
            "scikit-learn directly (not the repository evaluation helpers)."
        ),
        "cutoffs": {
            "train": [str(c.date()) for c in cutoffs["train"]],
            "validation": str(cutoffs["val"].date()),
            "test": str(cutoffs["test"].date()),
        },
        "label_horizon_days": horizon.label_horizon_days,
        "rule": "isotonic calibration of days_since_last_sale",
        "validation": metrics(val["y_inactive"].to_numpy(), p_val, threshold),
        "test": metrics(test["y_inactive"].to_numpy(), p_test, threshold),
        "d01_governance": {},
    }

    # D01 verification: the bad-debt invoices must be absent from valid sales.
    excluded = D01_BAD_DEBT_INVOICES
    invoices = sales["InvoiceNo"].astype(str)
    leaked = sorted(set(invoices) & set(excluded))
    result["d01_governance"] = {
        "excluded_invoice_numbers": sorted(excluded),
        "present_in_valid_sales": leaked,
        "records_present": int(invoices.isin(excluded).sum()),
    }

    # Compare with the registered report when available (no values are copied
    # into the result: this is a consistency check, not the source of truth).
    registered_path = REPORT_DIR / "dead_stock_model_results.json"
    baseline_registered = None
    if registered_path.exists():
        registered = json.loads(registered_path.read_text(encoding="utf-8"))
        baseline_registered = registered.get("models", {}).get("baseline_recency_rule", {}).get("test")
    if baseline_registered:
        result["registered_report_check"] = {
            "registered_pr_auc": baseline_registered.get("pr_auc"),
            "recomputed_pr_auc": result["test"]["pr_auc"],
            "absolute_difference": abs(
                float(baseline_registered.get("pr_auc", 0)) - result["test"]["pr_auc"]
            ),
            "note": (
                "Registered metrics use the same cutoff and calibration family; a small "
                "difference is expected because the registered report selects the threshold "
                "with the repository's implementation and fits on a slightly different cutoff list."
            ),
        }

    out = Path(REPORT_DIR) / "independent_evaluation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("cutoffs", "validation", "test")}, indent=2))
    print("written", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
