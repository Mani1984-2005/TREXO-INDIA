"""Module A: transparent dead-stock classification (demand-inactivity based).

Classes (policy): Healthy / Normal / Slow / At-Risk / Critical Dead-Stock Risk /
Confirmed Dead Stock. 'Confirmed Dead Stock' is ONLY assignable when the caller
supplies on_hand_qty > 0 AND the demand evidence is at Critical level; this
dataset has no stock balances, so it is never assigned from sales data alone.
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
from ..config import ML_DATA_DIR, ClassificationThresholds, load_calibrated_thresholds

CLASSES = ["Healthy Moving Stock", "Normal Moving Stock", "Slow Moving Stock", "At-Risk Stock",
           "Critical Dead-Stock Risk", "Confirmed Dead Stock"]


def _load_rule_curve(path=None):
    p = path or ML_DATA_DIR / "calibration.json"
    d = json.loads(p.read_text())
    return np.array(d["recency_grid_days"], float), np.array(d["recency_probability"], float), d


def rule_score(days_since_last_sale, curve=None) -> np.ndarray:
    grid, prob, _ = curve or _load_rule_curve()
    return np.interp(np.asarray(days_since_last_sale, float), grid, prob)  # clipped at ends


def classify_score(score: float, t: ClassificationThresholds) -> str:
    if score <= t.healthy_max_score: return CLASSES[0]
    if score <= t.normal_max_score: return CLASSES[1]
    if score <= t.slow_max_score: return CLASSES[2]
    if score <= t.at_risk_max_score: return CLASSES[3]
    return CLASSES[4]


def evidence_quality(row, t: ClassificationThresholds, train_max_recency: float) -> tuple[str, list[str]]:
    flags = []
    if row["n_invoices"] < t.min_invoices_for_evidence:
        flags.append("FEW_INVOICES")
    if row["age_days"] < t.min_age_days_for_evidence:
        flags.append("SHORT_PRODUCT_HISTORY")
    if row["days_since_last_sale"] > train_max_recency:
        flags.append("RECENCY_BEYOND_CALIBRATED_RANGE")
    if row["history_days"] < 365:
        flags.append("SINGLE_SEASONAL_CYCLE_OBSERVED")  # seasonality cannot be verified
    if row.get("missing_customer_share", 0) > 0.5:
        flags.append("MOSTLY_ANONYMOUS_SALES")
    serious = {"FEW_INVOICES", "SHORT_PRODUCT_HISTORY"}
    q = "LOW" if serious & set(flags) else ("MEDIUM" if flags else "HIGH")
    return q, flags


def demand_pattern(row, monthly_best2_share: float, t: ClassificationThresholds) -> str:
    """Context labels that distinguish inactivity from other explanations."""
    if row["n_invoices"] < t.min_invoices_for_evidence or row["age_days"] < t.min_age_days_for_evidence:
        return "INSUFFICIENT_OBSERVATION_HISTORY"
    if monthly_best2_share >= t.seasonal_concentration_share and row["n_sale_days"] >= 3:
        return "SEASONAL_OR_CAMPAIGN_CONCENTRATED"
    if row["gap_cv"] > 1.0 or row["mean_gap_days"] > 21:
        return "INTERMITTENT_DEMAND"
    return "CONTINUOUS_DEMAND"


def best2_month_share(sales: pd.DataFrame, cutoff) -> pd.Series:
    s = sales[sales["Date"] <= pd.Timestamp(cutoff)]
    m = s.groupby(["StockCode", s["Date"].dt.to_period("M")])["Quantity"].sum().reset_index()
    def share(x):
        v = np.sort(x.to_numpy())[::-1]
        return v[:2].sum() / max(v.sum(), 1e-9)
    return m.groupby("StockCode")["Quantity"].apply(share)


def classify_products(feat: pd.DataFrame, sales: pd.DataFrame, descriptions: pd.DataFrame,
                      on_hand: pd.DataFrame | None = None, curve=None,
                      thresholds: ClassificationThresholds | None = None) -> pd.DataFrame:
    t = thresholds or load_calibrated_thresholds()
    curve = curve or _load_rule_curve()
    train_max = curve[2].get("train_max_recency_days", np.inf)
    cutoff = feat["cutoff"].iloc[0]
    out = feat.copy()
    out["dead_stock_risk_score"] = rule_score(out["days_since_last_sale"], curve)
    out["classification"] = out["dead_stock_risk_score"].apply(lambda s: classify_score(s, t))
    b2 = best2_month_share(sales, cutoff)
    out["best2_month_share"] = out["StockCode"].map(b2).fillna(1.0)
    ev = out.apply(lambda r: evidence_quality(r, t, train_max), axis=1)
    out["evidence_quality"] = [e[0] for e in ev]
    out["evidence_flags"] = [";".join(e[1]) for e in ev]
    out["demand_pattern"] = out.apply(lambda r: demand_pattern(r, r["best2_month_share"], t), axis=1)
    out["stock_data_available"] = False
    if on_hand is not None and len(on_hand):
        oh = on_hand.set_index("StockCode")["on_hand_qty"]
        out["on_hand_qty"] = out["StockCode"].map(oh)
        out["stock_data_available"] = out["on_hand_qty"].notna()
        conf = (out["on_hand_qty"] > 0) & (out["classification"] == CLASSES[4]) & (out["evidence_quality"] != "LOW")
        out.loc[conf, "classification"] = CLASSES[5]
    out["status_type"] = np.where(out["stock_data_available"], "STOCK_AND_DEMAND_EVIDENCE",
                                  "DEMAND_INACTIVITY_INDICATOR_ONLY")
    out["evidence_basis"] = np.where(out["stock_data_available"],
                                     "SALES_HISTORY_PLUS_PHYSICAL_STOCK",
                                     "SALES_HISTORY_ONLY")
    out["inventory_value_available"] = False
    risky = out["classification"].isin([CLASSES[2], CLASSES[3], CLASSES[4], CLASSES[5]])
    out["stock_verification_required"] = risky & ~out["stock_data_available"]
    out["human_review_required"] = risky
    out = out.merge(descriptions, on="StockCode", how="left")
    out["risk_explanation"] = out.apply(_explain, axis=1)
    out["recommended_intervention"] = out["classification"].map(INTERVENTION_HINT)
    return out


INTERVENTION_HINT = {
    CLASSES[0]: "No dead-stock action; monitor.", CLASSES[1]: "No action; monitor.",
    CLASSES[2]: "Review purchasing cadence; do not increase orders.",
    CLASSES[3]: "Pause new purchasing pending review; check stock on hand.",
    CLASSES[4]: "Stop replenishment; verify physical stock; plan clearance after seasonal check.",
    CLASSES[5]: "Escalate: confirmed stock with critical demand inactivity.",
}


def _explain(r) -> str:
    base = (f"{int(r['days_since_last_sale'])} days since last valid sale; "
            f"{int(r['n_invoices'])} invoices, {int(r['total_qty'])} units sold historically; "
            f"estimated {r['dead_stock_risk_score']:.0%} of products with this recency had no sale in the next 60 days.")
    if r["demand_pattern"] != "CONTINUOUS_DEMAND":
        base += f" Pattern: {r['demand_pattern'].replace('_', ' ').lower()}."
    if not r["stock_data_available"]:
        base += (" Stock on hand and unit cost unknown: this is a demand-inactivity indicator, "
                 "not confirmed physical dead stock, and capital tied up cannot be calculated.")
    return base
