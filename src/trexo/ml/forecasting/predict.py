from __future__ import annotations
import numpy as np
import pandas as pd
from .engine import (MAX_H, classical_forecasts, demand_class, ml_features)


def forecast_products(mat_df: pd.DataFrame, choice: dict, lgbm=None, fallback="ma8", min_active=4) -> pd.DataFrame:
    """Forecast weeks 1..MAX_H after the last observed week. Method per product:
    selected method for its demand class if >= min_active active weeks, else fallback (MA8)."""
    mat = mat_df.to_numpy(float); n = mat.shape[1]
    X = {h: ml_features(mat, n, h) for h in range(1, MAX_H + 1)} if lgbm is not None else {}
    rows = []
    for i, code in enumerate(mat_df.index):
        y = mat[i]; active = int((y > 0).sum())
        if active < min_active:
            cls, method = "insufficient_history", fallback
        else:
            cls = demand_class(y); method = choice.get(cls, fallback)
        if method == "lightgbm" and lgbm is None: method = fallback
        for h in range(1, MAX_H + 1):
            if method == "lightgbm":
                f = float(max(lgbm.predict(X[h][i:i + 1])[0], 0))
            else:
                key = "croston" if method == "croston" else method
                f = classical_forecasts(y)[key]
            rows.append((code, h, f, method, cls))
    return pd.DataFrame(rows, columns=["StockCode", "horizon_week", "forecast_units", "method", "demand_class"])
