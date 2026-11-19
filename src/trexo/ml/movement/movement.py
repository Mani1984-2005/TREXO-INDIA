"""Module D: movement classification (FSN-style speed, ABC value, XYZ variability, trend).
Value (ABC) uses historical SALES REVENUE (Quantity x UnitPrice), the only value in the
data; it is not inventory value or margin. Thresholds come from ClassificationThresholds."""
from __future__ import annotations
import numpy as np
import pandas as pd
from ..config import ClassificationThresholds, load_calibrated_thresholds


def abc_class(revenue: pd.Series, t: ClassificationThresholds) -> pd.Series:
    r = revenue.sort_values(ascending=False)
    share = r.cumsum() / r.sum()
    cls = pd.Series(np.where(share.shift(fill_value=0) < t.abc_a_share, "A",
                    np.where(share.shift(fill_value=0) < t.abc_b_share, "B", "C")), index=r.index)
    return cls.reindex(revenue.index)


def xyz_class(cv: pd.Series, t: ClassificationThresholds) -> pd.Series:
    return pd.Series(np.where(cv <= t.xyz_x_max_cv, "X", np.where(cv <= t.xyz_y_max_cv, "Y", "Z")), index=cv.index)


def speed_class(f: pd.DataFrame, dead_recency_days: float, t: ClassificationThresholds) -> pd.Series:
    """Fast / Medium / Slow by sales velocity (units/day) percentiles among ACTIVE products;
    Non-moving = no sale within dead_recency_days (calibrated: P(inactive next 60d) >= 0.6)."""
    active = f["days_since_last_sale"] <= dead_recency_days
    q_fast = f.loc[active, "velocity_per_day"].quantile(t.fast_velocity_pctl)
    q_slow = f.loc[active, "velocity_per_day"].quantile(1 - t.fast_velocity_pctl)
    s = np.where(~active, "Non-moving", np.where(f["velocity_per_day"] >= q_fast, "Fast-moving",
                 np.where(f["velocity_per_day"] <= q_slow, "Slow-moving", "Medium-moving")))
    return pd.Series(s, index=f.index)


def classify_movement(feat: pd.DataFrame, sales: pd.DataFrame, dead_recency_days: float,
                      t: ClassificationThresholds | None = None) -> pd.DataFrame:
    t = t or load_calibrated_thresholds()
    cutoff = feat["cutoff"].iloc[0]
    s = sales[sales["Date"] <= cutoff]
    rev = s.groupby("StockCode")["LineValue"].sum().reindex(feat["StockCode"]).fillna(0)
    out = feat[["StockCode", "cutoff", "days_since_last_sale", "velocity_per_day", "total_qty",
                "monthly_cv", "trend_ratio_60", "mean_gap_days", "gap_cv", "n_invoices"]].copy()
    out["revenue_to_date"] = rev.to_numpy()
    out = out.set_index("StockCode")
    out["speed_class"] = speed_class(out, dead_recency_days, t)
    out["abc_class"] = abc_class(out["revenue_to_date"], t)
    out["xyz_class"] = xyz_class(out["monthly_cv"], t)
    out["abc_xyz"] = out["abc_class"] + out["xyz_class"]
    tr = out["trend_ratio_60"]
    out["trend_class"] = np.where(tr <= t.trend_decline_ratio, "Declining",
                          np.where(tr >= t.trend_growth_ratio, "Growing", "Stable"))
    out["intermittent"] = (out["mean_gap_days"] > 21) | (out["gap_cv"] > 1.0)
    out["high_value_declining"] = (out["abc_class"] == "A") & (out["trend_class"] == "Declining")
    out["unstable_demand"] = out["xyz_class"] == "Z"
    return out.reset_index()
