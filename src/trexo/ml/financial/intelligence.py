"""Module H: financial inventory intelligence.
Values are labelled MEASURED (computed from supplied cost/stock), ESTIMATED (needs a stated
assumption) or SCENARIO. With the current dataset no inventory/cost data exist, so only the
data-readiness report is produced; the calculators are exercised by unit tests and are ready
for pilot data."""
from __future__ import annotations
import pandas as pd

REQUIRED_FIELDS = {
    "on_hand_qty": "units physically in stock (product x location x snapshot date)",
    "unit_cost": "acquisition/average cost per unit (to value stock)",
    "holding_rate_annual": "carrying-cost rate (capital, storage, insurance, shrink) for carrying-cost savings",
    "recovery_rate": "expected recoverable share of cost when clearing (SCENARIO assumption, never measured)",
    "selling_price_and_margin": "to test whether a discount destroys margin",
}


def data_readiness(columns_available) -> pd.DataFrame:
    have = set(columns_available)
    return pd.DataFrame([{"field": k, "needed_for": v, "available": k in have} for k, v in REQUIRED_FIELDS.items()])


def inventory_financials(stock: pd.DataFrame, classification: pd.DataFrame, forecast_daily: pd.Series | None = None,
                         excess_cover_days: float = 180, holding_rate_annual: float | None = None,
                         recovery_rate: float | None = None) -> dict:
    """stock: StockCode, on_hand_qty, unit_cost. classification: StockCode, classification."""
    need = {"StockCode", "on_hand_qty", "unit_cost"}
    if not need <= set(stock.columns):
        raise ValueError(f"stock table missing columns: {sorted(need - set(stock.columns))}")
    d = stock.merge(classification[["StockCode", "classification"]], on="StockCode", how="left")
    d["value"] = d["on_hand_qty"] * d["unit_cost"]
    out = {"MEASURED": {"inventory_value": float(d["value"].sum()),
                        "slow_moving_value": float(d.loc[d["classification"] == "Slow Moving Stock", "value"].sum()),
                        "dead_stock_value": float(d.loc[d["classification"] == "Confirmed Dead Stock", "value"].sum()),
                        "at_risk_and_critical_value": float(d.loc[d["classification"].isin(
                            ["At-Risk Stock", "Critical Dead-Stock Risk"]), "value"].sum()),
                        "unclassified_value": float(d.loc[d["classification"].isna(), "value"].sum())},
           "ESTIMATED": {}, "SCENARIO": {}}
    if forecast_daily is not None:
        d["cover_days"] = d["on_hand_qty"] / d["StockCode"].map(forecast_daily).replace(0, float("nan"))
        excess = d["cover_days"] > excess_cover_days
        ex_units = (d["on_hand_qty"] - excess_cover_days * d["StockCode"].map(forecast_daily)).clip(lower=0)
        out["ESTIMATED"]["excess_inventory_value_over_cover_threshold"] = float((ex_units[excess] * d.loc[excess, "unit_cost"]).sum())
        out["ESTIMATED"]["assumption"] = f"excess = stock above {excess_cover_days} days of forecast demand"
    if holding_rate_annual is not None:
        out["ESTIMATED"]["annual_carrying_cost_of_at_risk_stock"] = out["MEASURED"]["at_risk_and_critical_value"] * holding_rate_annual
    if recovery_rate is not None:
        out["SCENARIO"]["recoverable_value_if_cleared"] = (out["MEASURED"]["dead_stock_value"]
            + out["MEASURED"]["at_risk_and_critical_value"]) * recovery_rate
        out["SCENARIO"]["note"] = "hypothetical, depends on the assumed recovery_rate; not a realised saving"
    return out
