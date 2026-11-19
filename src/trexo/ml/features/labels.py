"""Time-based labels. Label for (product, cutoff T) = no valid sale in (T, T+H].
Computed from the SAME sales table but only from dates > T; it never enters features."""
from __future__ import annotations
import pandas as pd


def inactivity_label(sales: pd.DataFrame, products, cutoff, horizon_days: int) -> pd.DataFrame:
    cutoff = pd.Timestamp(cutoff).normalize()
    end = cutoff + pd.Timedelta(days=horizon_days)
    fut = sales[(sales["Date"] > cutoff) & (sales["Date"] <= end)]
    q = fut.groupby("StockCode")["Quantity"].sum()
    out = pd.DataFrame({"StockCode": list(products)})
    out["future_qty"] = out["StockCode"].map(q).fillna(0.0)
    out["y_inactive"] = (out["future_qty"] <= 0).astype(int)
    return out


def build_training_table(sales: pd.DataFrame, cutoffs, horizon_days: int) -> pd.DataFrame:
    from .product_features import build_features
    parts = []
    data_start = sales["Date"].min()
    for c in cutoffs:
        feat = build_features(sales, c, data_start)
        lab = inactivity_label(sales, feat["StockCode"], c, horizon_days)
        parts.append(feat.merge(lab, on="StockCode"))
    return pd.concat(parts, ignore_index=True)
