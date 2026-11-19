"""Module C: product-level weekly demand forecasting.

Series: 7-day bins anchored at the first sale date; only COMPLETE weeks are used.
Methods: zero, naive, MA4, MA8, SES (alpha chosen in-sample), Croston, SBA, and a
global LightGBM (direct multi-horizon, lag/rolling features). ARIMA/SARIMA and
seasonal decomposition are NOT used: 53 weekly points per product (one cycle),
mostly intermittent, cannot support them (documented in docs/DEMAND_FORECASTING.md).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

MAX_H = 8


def weekly_matrix(sales: pd.DataFrame):
    start = sales["Date"].min().normalize()
    end = sales["Date"].max().normalize()
    n_weeks = ((end - start).days + 1) // 7          # complete weeks only
    s = sales.assign(w=(sales["Date"] - start).dt.days // 7)
    s = s[s["w"] < n_weeks]
    m = s.pivot_table(index="StockCode", columns="w", values="Quantity", aggfunc="sum", fill_value=0)
    m = m.reindex(columns=range(n_weeks), fill_value=0)
    return m, start


def _ses(y, alphas=(0.1, 0.2, 0.3, 0.5)):
    best = (np.inf, 0.0, 0.0)
    for a in alphas:
        l = y[0]; err = 0.0
        for v in y[1:]:
            err += (v - l) ** 2; l = a * v + (1 - a) * l
        if err < best[0]: best = (err, a, l)
    return best[2]


def _croston(y, alpha=0.1, sba=False):
    nz = np.flatnonzero(y > 0)
    if len(nz) == 0: return 0.0
    z = y[nz[0]]; p = nz[0] + 1.0; q = 1
    for i in range(nz[0] + 1, len(y)):
        if y[i] > 0:
            z = alpha * y[i] + (1 - alpha) * z
            p = alpha * q + (1 - alpha) * p; q = 1
        else:
            q += 1
    f = z / p
    return f * (1 - alpha / 2) if sba else f


def classical_forecasts(y: np.ndarray) -> dict:
    """Level forecasts (constant over horizon) per method for one series up to the origin."""
    return {"zero": 0.0, "naive": float(y[-1]), "ma4": float(y[-4:].mean()), "ma8": float(y[-8:].mean()),
            "ses": float(_ses(y)), "croston": float(_croston(y)), "sba": float(_croston(y, sba=True))}


def demand_class(y: np.ndarray) -> str:
    """Syntetos-Boylan: ADI cut 1.32, CV^2 cut 0.49 -> smooth/erratic/intermittent/lumpy."""
    nz = y[y > 0]
    if len(nz) < 2: return "insufficient"
    adi = len(y) / len(nz); cv2 = (nz.std() / nz.mean()) ** 2
    return ("smooth" if cv2 < 0.49 else "erratic") if adi < 1.32 else ("intermittent" if cv2 < 0.49 else "lumpy")


def ml_features(mat: np.ndarray, origin: int, h: int) -> np.ndarray:
    """Features at `origin` (last observed week index = origin-1). Columns:
    lags 1..8, mean4/8/13, weeks_since_last_sale, zero_share_13, nz_mean_all, total_active_weeks, h."""
    hist = mat[:, :origin]
    lags = np.stack([hist[:, -k] if origin >= k else np.zeros(len(mat)) for k in range(1, 9)], 1)
    mean = lambda k: hist[:, -k:].mean(1)
    pos = hist > 0
    last = np.where(pos.any(1), origin - 1 - (origin - 1 - np.argmax(pos[:, ::-1], 1)) , origin)
    wsl = np.where(pos.any(1), np.argmax(pos[:, ::-1], 1), origin)
    zero13 = 1 - pos[:, -13:].mean(1)
    nzm = np.where(pos.sum(1) > 0, hist.sum(1) / np.maximum(pos.sum(1), 1), 0)
    return np.column_stack([lags, mean(4), mean(8), mean(13), wsl, zero13, nzm, pos.sum(1), np.full(len(mat), h)])


ML_FEATURE_NAMES = [f"lag{k}" for k in range(1, 9)] + ["mean4", "mean8", "mean13", "weeks_since_sale",
                                                      "zero_share13", "nonzero_mean", "active_weeks", "horizon"]


def ml_train_table(mat: np.ndarray, last_target_week: int, min_origin=12):
    """Rows for all origins o and horizons h with o+h-1 <= last_target_week (targets strictly
    inside the training period -> no leakage into the evaluation window)."""
    X, y = [], []
    for o in range(min_origin, last_target_week + 1):
        for h in range(1, MAX_H + 1):
            t = o + h - 1
            if t > last_target_week: break
            X.append(ml_features(mat, o, h)); y.append(mat[:, t])
    return np.vstack(X), np.concatenate(y)


def fit_lgbm(mat: np.ndarray, last_target_week: int, seed=42):
    import lightgbm as lgb
    X, y = ml_train_table(mat, last_target_week)
    keep = X[:, ML_FEATURE_NAMES.index("active_weeks")] > 0
    m = lgb.LGBMRegressor(objective="tweedie", tweedie_variance_power=1.3, n_estimators=300, learning_rate=0.05,
                          num_leaves=31, min_child_samples=50, subsample=0.8, subsample_freq=1,
                          colsample_bytree=0.8, random_state=seed, verbose=-1, n_jobs=2)
    m.fit(X[keep], y[keep]); return m


def forecast_metrics(actual: np.ndarray, fc: np.ndarray) -> dict:
    a = np.asarray(actual, float); f = np.asarray(fc, float); e = f - a
    den = np.abs(a) + np.abs(f)
    smape = np.where(den == 0, 0.0, 2 * np.abs(e) / np.where(den == 0, 1, den))
    return {"MAE": float(np.abs(e).mean()), "RMSE": float(np.sqrt((e ** 2).mean())),
            "WAPE": float(np.abs(e).sum() / max(a.sum(), 1e-9)), "sMAPE": float(smape.mean()),
            "bias": float(e.sum() / max(a.sum(), 1e-9)), "n": int(a.size), "actual_total": float(a.sum())}
