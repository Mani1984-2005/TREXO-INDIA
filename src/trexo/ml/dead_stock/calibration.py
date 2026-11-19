"""Empirical calibration of the transparent dead-stock rule score.

rule_score(days_since_last_sale) = isotonic estimate of
    P(no valid sale in next H days | days since last sale)
fitted ONLY on training cutoffs. Classification bands are then defined on this
interpretable probability and validated on later cutoffs.
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from ..config import ML_DATA_DIR


def fit_rule_score(train: pd.DataFrame) -> IsotonicRegression:
    iso = IsotonicRegression(y_min=0.0, y_max=1.0, increasing=True, out_of_bounds="clip")
    iso.fit(train["days_since_last_sale"].to_numpy(float), train["y_inactive"].to_numpy(float))
    return iso


def recency_for_probability(iso: IsotonicRegression, p: float, max_days=400) -> int | None:
    grid = np.arange(0, max_days)
    pr = iso.predict(grid)
    ok = np.where(pr >= p)[0]
    return int(grid[ok[0]]) if len(ok) else None


def band_table(df: pd.DataFrame, score_col: str, edges) -> pd.DataFrame:
    b = pd.cut(df[score_col], [-np.inf, *edges, np.inf])
    t = df.groupby(b, observed=False).agg(n=("y_inactive", "size"),
                                          observed_inactive_rate=("y_inactive", "mean"),
                                          mean_score=(score_col, "mean")).reset_index()
    t["band"] = t[score_col].astype(str)
    return t.drop(columns=[score_col])


def save_calibration(iso, edges, extra: dict, path=None):
    path = path or ML_DATA_DIR / "calibration.json"
    grid = np.arange(0, 400)
    payload = {
        "method": "isotonic regression of 60-day inactivity on days_since_last_sale, train cutoffs only",
        "recency_grid_days": grid.tolist()[::5],
        "recency_probability": [float(x) for x in iso.predict(grid)[::5]],
        "classification_thresholds": {
            "healthy_max_score": edges[0], "normal_max_score": edges[1],
            "slow_max_score": edges[2], "at_risk_max_score": edges[3]},
        **extra,
    }
    path.write_text(json.dumps(payload, indent=2))
    return payload
