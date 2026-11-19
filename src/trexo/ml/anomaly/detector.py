"""Module G: anomaly detection. Reports only - nothing is deleted or altered.
Two separate families:
  * TRANSACTION-QUALITY: duplicates, extreme quantity, abnormal price vs product median.
  * BUSINESS-DEMAND: product weekly spikes/drops (robust z), product-level Isolation Forest.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

IF_FEATURES = ["velocity_per_day", "avg_qty_per_invoice", "monthly_cv", "trend_ratio_60", "price_cv",
               "recency_gap_ratio", "sale_day_share", "log_total_value"]


def transaction_quality(sales: pd.DataFrame, qty_limit: int = 1000, price_ratio: float = 10.0) -> pd.DataFrame:
    s = sales.copy()
    med = s.groupby("StockCode")["UnitPrice"].transform("median")
    ratio = s["UnitPrice"] / med
    qmed = s.groupby("StockCode")["Quantity"].transform("median")
    flags = pd.DataFrame({
        "EXACT_DUPLICATE_ROW": s["IsExactDuplicate"],
        "EXTREME_QUANTITY": s["Quantity"] >= qty_limit,
        "QUANTITY_100X_PRODUCT_MEDIAN": (s["Quantity"] >= 100 * qmed) & (s["Quantity"] >= 100),
        "PRICE_ABOVE_10X_PRODUCT_MEDIAN": ratio >= price_ratio,
        "PRICE_BELOW_TENTH_OF_PRODUCT_MEDIAN": ratio <= 1 / price_ratio,
    }, index=s.index)
    flagged = flags.any(axis=1)
    out = s.loc[flagged, ["SourceRow", "InvoiceNo", "StockCode", "Description", "Quantity",
                          "UnitPrice", "Date"]].copy()
    sub = flags.loc[flagged]
    out["flags"] = [";".join(sub.columns[row.to_numpy(bool)]) for _, row in sub.iterrows()]
    if out.empty:
        out["what_was_unusual"] = pd.Series(dtype=object)
        out["why_review"] = pd.Series(dtype=object)
        out["requires_review"] = pd.Series(dtype=bool)
        out["family"] = pd.Series(dtype=object)
        out["action"] = pd.Series(dtype=object)
        return out

    def why(row):
        parts, f = [], set(row["flags"].split(";"))
        if "EXACT_DUPLICATE_ROW" in f:
            parts.append("this line is an exact duplicate of an earlier line (possible data-entry repeat)")
        if "EXTREME_QUANTITY" in f:
            parts.append(f"quantity {row['Quantity']:.0f} is at or above the extreme-quantity limit (1000)")
        if "QUANTITY_100X_PRODUCT_MEDIAN" in f:
            parts.append(f"quantity {row['Quantity']:.0f} is at least 100x this product's median line quantity")
        if "PRICE_ABOVE_10X_PRODUCT_MEDIAN" in f:
            parts.append(f"unit price {row['UnitPrice']:.2f} is at least 10x this product's median price")
        if "PRICE_BELOW_TENTH_OF_PRODUCT_MEDIAN" in f:
            parts.append(f"unit price {row['UnitPrice']:.2f} is at most one-tenth of this product's median price")
        return "; ".join(parts)

    out["what_was_unusual"] = out.apply(why, axis=1)
    out["why_review"] = ("A statistical/rule outlier can be a legitimate bulk order, a correction, a pricing "
                         "error or a data-quality problem. It is not evidence of fraud or misconduct.")
    out["requires_review"] = True
    out["family"] = "TRANSACTION_QUALITY"
    out["action"] = "Report only; retained in all datasets. Owner decision required before any exclusion."
    return out


def demand_anomalies(weekly: pd.DataFrame, min_active_weeks=8, z=6.0, min_ratio=5.0) -> pd.DataFrame:
    """weekly: products x weeks matrix (DataFrame). Robust z = (x - median)/ (1.4826*MAD) over the product's own history."""
    rows = []
    arr = weekly.to_numpy(float)
    for i, code in enumerate(weekly.index):
        y = arr[i]
        if (y > 0).sum() < min_active_weeks: continue
        nz = y[y > 0]; med = np.median(nz); mad = np.median(np.abs(nz - med)) * 1.4826
        mad = max(mad, 0.25 * med, 1.0)   # floor: perfectly steady series have MAD=0 and must still flag spikes
        for w in np.flatnonzero(y > 0):
            zz = (y[w] - med) / mad
            if zz >= z and y[w] >= min_ratio * med: rows.append((code, int(w), y[w], med, zz, "SALES_SPIKE"))
        recent = y[-4:]; prior = y[-12:-4]
        if prior.sum() > 0 and (prior > 0).sum() >= 4 and recent.sum() == 0:
            rows.append((code, weekly.shape[1] - 1, 0.0, float(prior.mean()), -np.inf, "SUDDEN_DEMAND_STOP"))
    d = pd.DataFrame(rows, columns=["StockCode", "week_index", "quantity", "product_median_active_week", "robust_z", "type"])
    d["explanation"] = np.where(
        d["type"] == "SALES_SPIKE",
        "Weekly quantity " + d["quantity"].round(0).astype(str) + " vs product median active week "
        + d["product_median_active_week"].round(1).astype(str) + " (robust z " + d["robust_z"].round(1).astype(str) + ").",
        "No sales in the last 4 weeks after at least 4 active weeks in the preceding 8-week window.")
    d["why_review"] = ("Demand spike/stop candidates for review (bulk order, stockout, delisting, campaign or "
                       "data issue). Reported, never treated as fraud or automatically removed.")
    d["requires_review"] = True
    d["family"] = "BUSINESS_DEMAND"
    return d


def fit_isolation_forest(feat: pd.DataFrame, contamination=0.02, seed=42):
    X = np.log1p(np.clip(feat[IF_FEATURES].to_numpy(float), 0, None))
    return IsolationForest(n_estimators=300, contamination=contamination, random_state=seed).fit(X)


def score_isolation_forest(model, feat: pd.DataFrame) -> pd.DataFrame:
    X = np.log1p(np.clip(feat[IF_FEATURES].to_numpy(float), 0, None))
    out = feat[["StockCode"]].copy()
    out["anomaly_score"] = -model.score_samples(X)
    out["is_anomalous_profile"] = model.predict(X) == -1
    ctr = np.median(X, axis=0); mad = np.median(np.abs(X - ctr), axis=0) * 1.4826 + 1e-9
    zs = (X - ctr) / mad
    top = np.argsort(-np.abs(zs), axis=1)[:, :2]
    out["main_drivers"] = [", ".join(f"{IF_FEATURES[j]}({zs[i, j]:+.1f}z)" for j in top[i]) for i in range(len(out))]
    return out
