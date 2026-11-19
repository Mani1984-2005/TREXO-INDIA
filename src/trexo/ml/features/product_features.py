"""Product-level features computed strictly from sales dated <= cutoff.

Leakage control: `build_features(sales, cutoff)` first filters `Date <= cutoff`;
nothing after the cutoff can reach a feature. Verified by
tests/ml/test_features.py (future rows must not change features).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

WINDOWS = (7, 30, 60, 90, 180, 365)

FEATURE_COLUMNS = [
    "history_days", "age_days", "days_since_last_sale", "n_invoices", "n_sale_days",
    "total_qty", "avg_qty_per_invoice", "velocity_per_day",
    *[f"qty_{w}d" for w in WINDOWS], *[f"inv_{w}d" for w in (30, 90)],
    "sale_day_share", "mean_gap_days", "gap_cv", "max_gap_days", "recency_gap_ratio",
    "monthly_cv", "trend_ratio_60", "avg_price", "price_cv", "n_customers",
    "missing_customer_share", "log_total_value",
]


def _daily(sales: pd.DataFrame) -> pd.DataFrame:
    return (sales.groupby(["StockCode", "Date"])
            .agg(qty=("Quantity", "sum"), inv=("InvoiceNo", "nunique")).reset_index())


def build_features(sales: pd.DataFrame, cutoff, data_start=None) -> pd.DataFrame:
    """One row per product with >=1 valid sale on or before `cutoff`."""
    cutoff = pd.Timestamp(cutoff).normalize()
    s = sales.loc[sales["Date"] <= cutoff]
    if s.empty:
        return pd.DataFrame(columns=["StockCode", *FEATURE_COLUMNS])
    data_start = pd.Timestamp(data_start) if data_start is not None else sales["Date"].min()
    daily = _daily(s)
    daily["age"] = (cutoff - daily["Date"]).dt.days  # 0 = cutoff day

    g = daily.groupby("StockCode")
    f = pd.DataFrame({
        "first": g["Date"].min(), "last": g["Date"].max(),
        "n_sale_days": g["Date"].nunique(), "total_qty": g["qty"].sum(),
    })
    f["age_days"] = (cutoff - f["first"]).dt.days
    f["days_since_last_sale"] = (cutoff - f["last"]).dt.days
    f["history_days"] = (cutoff - data_start).days
    inv = s.groupby("StockCode")["InvoiceNo"].nunique()
    f["n_invoices"] = inv
    f["avg_qty_per_invoice"] = f["total_qty"] / f["n_invoices"]
    f["velocity_per_day"] = f["total_qty"] / (f["age_days"] + 1).clip(lower=30)
    for w in WINDOWS:
        m = daily["age"] < w
        f[f"qty_{w}d"] = daily[m].groupby("StockCode")["qty"].sum()
    for w in (30, 90):
        m = s["Date"] > cutoff - pd.Timedelta(days=w)
        f[f"inv_{w}d"] = s[m].groupby("StockCode")["InvoiceNo"].nunique()
    f[[c for c in f.columns if c.startswith(("qty_", "inv_"))]] = \
        f[[c for c in f.columns if c.startswith(("qty_", "inv_"))]].fillna(0)
    f["sale_day_share"] = f["n_sale_days"] / (f["age_days"] + 1)

    # gaps between consecutive sale days
    d2 = daily.sort_values(["StockCode", "Date"])
    d2["gap"] = d2.groupby("StockCode")["Date"].diff().dt.days
    gg = d2.groupby("StockCode")["gap"]
    f["mean_gap_days"] = gg.mean()
    f["gap_cv"] = gg.std() / gg.mean()
    f["max_gap_days"] = gg.max()
    # NaN for single-sale-day products is retained as information, then imputed below
    f["recency_gap_ratio"] = f["days_since_last_sale"] / f["mean_gap_days"].where(f["mean_gap_days"] > 0)

    # monthly demand variability over 30-day bins ending at the cutoff (<=6 bins, only bins that exist after first sale)
    daily["bin"] = (daily["age"] // 30).clip(upper=5)
    bins = daily.groupby(["StockCode", "bin"])["qty"].sum().unstack(fill_value=0)
    for b in range(6):
        if b not in bins.columns:
            bins[b] = 0
    bins = bins[list(range(6))]
    n_bins = ((f["age_days"] // 30) + 1).clip(upper=6)
    mask = np.arange(6)[None, :] < n_bins.reindex(bins.index).to_numpy()[:, None]
    vals = bins.to_numpy(dtype=float)
    mu = np.where(mask, vals, np.nan)
    with np.errstate(all="ignore"):
        cv = np.nanstd(mu, axis=1, ddof=0) / np.nanmean(mu, axis=1)
    f["monthly_cv"] = pd.Series(cv, index=bins.index)
    prev60 = daily[(daily["age"] >= 60) & (daily["age"] < 120)].groupby("StockCode")["qty"].sum()
    f["trend_ratio_60"] = (f["qty_60d"] + 1) / (prev60.reindex(f.index).fillna(0) + 1)

    price = s.groupby("StockCode")["UnitPrice"].agg(["mean", "std"])
    f["avg_price"] = price["mean"]
    f["price_cv"] = (price["std"] / price["mean"]).fillna(0)
    f["n_customers"] = s.groupby("StockCode")["CustomerID"].nunique()
    f["missing_customer_share"] = s.assign(m=s["CustomerID"].isna()).groupby("StockCode")["m"].mean()
    f["log_total_value"] = np.log1p(s.groupby("StockCode")["LineValue"].sum())

    # documented imputation: products with a single sale day have no gap statistics
    f["mean_gap_days"] = f["mean_gap_days"].fillna(f["history_days"])
    f["gap_cv"] = f["gap_cv"].fillna(0.0)
    f["max_gap_days"] = f["max_gap_days"].fillna(f["history_days"])
    f["recency_gap_ratio"] = (f["days_since_last_sale"] / f["mean_gap_days"].clip(lower=1)).fillna(0)
    f["monthly_cv"] = f["monthly_cv"].fillna(0.0)
    f = f.reset_index().rename(columns={"index": "StockCode"})
    f["cutoff"] = cutoff
    return f[["StockCode", "cutoff", "first", "last", *FEATURE_COLUMNS]]
