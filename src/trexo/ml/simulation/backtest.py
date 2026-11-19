"""Module: chronological decision backtest (UNIT-LEVEL SCENARIO, not a financial result).

MEASURED: actual demand in the 60 days after each cutoff, risk scores computed with
a calibration fitted on data BEFORE that cutoff only.
HYPOTHETICAL: the purchase quantities (no procurement data exist). Two stylised policies
place one replenishment per product at each cutoff to cover the next H days:
  BASELINE : buy what the product sold in the trailing H days (naive repeat-purchase).
  TREXO    : buy forecast demand (SES level x H/7), but NOTHING if the calibrated
             risk score >= pause_threshold (At-Risk or worse).
Reported in units only. No money, no margin, no stock carry-over (every cycle starts at 0
on-hand), so 'excess' = units bought but not sold within H days.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from ..features.product_features import build_features
from ..features.labels import inactivity_label
from ..forecasting.engine import _ses


def _weekly_before(sales, cutoff):
    start = sales["Date"].min().normalize()
    n = ((pd.Timestamp(cutoff) - start).days + 1) // 7
    s = sales[(sales["Date"] <= pd.Timestamp(cutoff))]
    s = s.assign(w=(s["Date"] - start).dt.days // 7)
    s = s[s["w"] < n]
    return s.pivot_table(index="StockCode", columns="w", values="Quantity", aggfunc="sum", fill_value=0) \
            .reindex(columns=range(n), fill_value=0)


def simulate(sales: pd.DataFrame, calibration_table: pd.DataFrame, cutoffs, horizon_days=60,
             pause_threshold=0.6) -> pd.DataFrame:
    """calibration_table: rows (days_since_last_sale, y_inactive) from cutoffs STRICTLY earlier
    than every simulated cutoff (caller guarantees; asserted via the 'cutoff' column)."""
    rows = []
    for c in cutoffs:
        c = pd.Timestamp(c)
        cal = calibration_table[calibration_table["cutoff"] + pd.Timedelta(days=horizon_days) <= c]
        if cal.empty: raise ValueError(f"no label-complete calibration data before {c.date()}")
        iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(
            cal["days_since_last_sale"], cal["y_inactive"])
        f = build_features(sales, c)
        lab = inactivity_label(sales, f["StockCode"], c, horizon_days)
        f = f.merge(lab, on="StockCode")
        f["score"] = iso.predict(f["days_since_last_sale"])
        wk = _weekly_before(sales, c)
        level = wk.apply(lambda r: _ses(r.to_numpy(float)), axis=1) if len(wk.columns) else pd.Series(0.0, index=wk.index)
        f["forecast_h"] = f["StockCode"].map(level).fillna(0) * horizon_days / 7
        d60 = sales[(sales["Date"] <= c) & (sales["Date"] > c - pd.Timedelta(days=horizon_days))] \
            .groupby("StockCode")["Quantity"].sum()
        f["buy_baseline"] = f["StockCode"].map(d60).fillna(0)
        f["buy_trexo"] = np.where(f["score"] >= pause_threshold, 0.0, f["forecast_h"])
        for name in ("baseline", "trexo"):
            b = f[f"buy_{name}"]; dem = f["future_qty"]
            sold = np.minimum(b, dem)
            rows.append({"cutoff": str(c.date()), "strategy": name, "products": len(f),
                         "units_bought": float(b.sum()), "units_sold_of_bought": float(sold.sum()),
                         "excess_units": float((b - sold).sum()), "unmet_demand_units": float((dem - sold).sum()),
                         "fill_rate_proxy": float(sold.sum() / max(dem.sum(), 1e-9)),
                         "turnover_proxy": float(sold.sum() / max(b.sum(), 1e-9)),
                         "purchase_lines_on_zero_demand_products": int(((b > 0) & (dem == 0)).sum()),
                         "units_bought_on_zero_demand_products": float(b[(dem == 0)].sum()),
                         "actual_demand_units": float(dem.sum())})
    return pd.DataFrame(rows)
