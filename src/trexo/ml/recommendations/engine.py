"""Module F: dead-stock reduction recommendations + prioritised intervention queue.

Priority points (documented, no hidden score):
    priority_points = risk_score x value_weight x evidence_weight
    value_weight    : ABC class A=1.0, B=0.6, C=0.3  (historical SALES revenue rank, not inventory value)
    evidence_weight : HIGH=1.0, MEDIUM=0.7, LOW=0.4
Priority tier: points >= 0.60 -> P1 (immediate), >= 0.30 -> P2, >= 0.10 -> P3, else P4 (monitor).
No monetary benefit is estimated: cost/margin/stock data are absent.
"""
from __future__ import annotations
import pandas as pd

VALUE_W = {"A": 1.0, "B": 0.6, "C": 0.3}
EVID_W = {"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.4}
RISKY = ("Slow Moving Stock", "At-Risk Stock", "Critical Dead-Stock Risk", "Confirmed Dead Stock")
UNAVAILABLE_ACTIONS = [
    "Transfer inventory between locations (needs warehouse/location stock data)",
    "Return to supplier (needs supplier, contract and return-window data)",
    "Alternative customer segments (needs reliable customer data; 25% of rows have no CustomerID)"]


def tier(points: float) -> str:
    return "P1" if points >= 0.60 else "P2" if points >= 0.30 else "P3" if points >= 0.10 else "P4"


def _actions(r) -> tuple[list[str], str]:
    c, pat = r["classification"], r["demand_pattern"]
    acts, why = [], []
    if pat == "INSUFFICIENT_OBSERVATION_HISTORY":
        return ["Monitor; collect more sales history before intervening"], \
               "Too few invoices or too short a history to separate dead demand from a new/slow launch."
    if c in ("Critical Dead-Stock Risk", "Confirmed Dead Stock"):
        acts += ["Stop or pause replenishment", "Verify physical stock on hand"]
        why.append("Calibrated probability of no sale in the next 60 days is high.")
        if pat == "SEASONAL_OR_CAMPAIGN_CONCENTRATED":
            acts += ["Review seasonal timing before discounting"]
            why.append("Sales were concentrated in a short window; a discount now may be premature (one seasonal cycle only observed).")
        else:
            acts += ["Prioritise selling existing inventory", "Review product discontinuation"]
            if r["abc_class"] in ("A", "B"):
                acts += ["Escalate high-value item for management review"]
                why.append("Item ranks in the top revenue classes, so the cost of being wrong is larger.")
            if r.get("price_cv", 0) > 0.5:
                acts += ["Investigate pricing or product-description issues"]
                why.append("Selling price varied widely, which can mask a pricing problem.")
        acts += ["Consider controlled promotion or bundling only after margin is known"]
    elif c == "At-Risk Stock":
        acts += ["Pause new purchasing pending review", "Reduce future purchase quantities"]
        if pat == "SEASONAL_OR_CAMPAIGN_CONCENTRATED":
            acts += ["Review seasonal timing before discounting"]
        else:
            acts += ["Bundle with popular products or run a targeted promotion (validate margin first)"]
        why.append("Sales are slowing relative to this product's own history.")
    elif c == "Slow Moving Stock":
        acts += ["Reduce future purchase quantities", "Do not increase order sizes"]
        why.append("Recency is above the typical range for continuously selling products.")
    if r.get("high_value_declining") and "Escalate high-value item for management review" not in acts:
        acts += ["Escalate high-value item for management review"]
        why.append("Class-A revenue product with declining demand.")
    return acts, " ".join(why)


def build_queue(cls: pd.DataFrame, mov: pd.DataFrame, fc4w: pd.Series | None = None) -> pd.DataFrame:
    d = cls.merge(mov[["StockCode", "abc_class", "xyz_class", "abc_xyz", "trend_class", "speed_class",
                       "high_value_declining", "revenue_to_date"]], on="StockCode", how="left")
    d["value_weight"] = d["abc_class"].map(VALUE_W)
    d["evidence_weight"] = d["evidence_quality"].map(EVID_W)
    d["priority_points"] = d["dead_stock_risk_score"] * d["value_weight"] * d["evidence_weight"]
    d["priority"] = d["priority_points"].apply(tier)
    d = d[d["classification"].isin(RISKY) | d["high_value_declining"]].copy()
    recs = d.apply(_actions, axis=1)
    d["recommended_actions"] = [" | ".join(a) for a, _ in recs]
    d["why_appropriate"] = [w for _, w in recs]
    d["detected_problem"] = d["classification"] + " (" + d["status_type"].str.replace("_", " ").str.lower() + ")"
    d["supporting_evidence"] = d["risk_explanation"]
    d["risk_level"] = d["classification"]
    d["expected_business_benefit"] = ("Avoids further purchasing of a product with an estimated "
        + (d["dead_stock_risk_score"] * 100).round(0).astype(int).astype(str)
        + "% chance of no sale in 60 days. Monetary benefit NOT estimated (no cost/stock/margin data).")
    d["required_information"] = ("on-hand quantity; unit cost and margin; supplier terms; lifecycle status"
                                 + d["demand_pattern"].map({"SEASONAL_OR_CAMPAIGN_CONCENTRATED": "; prior-year seasonality",
                                                            "INSUFFICIENT_OBSERVATION_HISTORY": "; longer history"}).fillna(""))
    d["confidence"] = d["evidence_quality"]
    d["intervention"] = d.get("recommended_intervention", pd.Series(index=d.index, dtype=object))
    d.loc[d["intervention"].isna(), "intervention"] = (
        d.loc[d["intervention"].isna(), "recommended_actions"].str.split(" | ").str[0])
    d["reason_for_recommendation"] = d["why_appropriate"]
    d["expected_impact_direction"] = d["classification"].map({
        "Critical Dead-Stock Risk": "Reduce/stop replenishment and work down existing stock; "
                                    "stockout trade-off must be reviewed before clearance.",
        "Confirmed Dead Stock": "Reduce/stop replenishment; physical stock confirmed and should be cleared/reviewed.",
        "At-Risk Stock": "Prevent further inventory accumulation while protecting availability of a still-selling item.",
        "Slow Moving Stock": "Gradually reduce purchase quantities; monitor for recovery before clearance.",
    }).fillna("Management review before any change; direction depends on missing stock/cost data.")
    d["inventory_value_impact"] = "NOT_QUANTIFIABLE_WITHOUT_ON_HAND_AND_UNIT_COST"
    d["requires_human_approval"] = True
    d["approval_note"] = ("Human approval required: no purchase order, transfer, discount or clearance is executed "
                          "by the ML layer. Verify stock, margin, supplier terms and seasonal timing first.")
    d["evaluation_method"] = ("Compare units sold in the 60 days after the action with the calibrated "
                              "expectation and with untreated look-alike products (same class/ABC).")
    if fc4w is not None:
        d["forecast_next_4w_units"] = d["StockCode"].map(fc4w)
    d = d.sort_values(["priority_points", "revenue_to_date"], ascending=False).reset_index(drop=True)
    d.insert(0, "queue_rank", range(1, len(d) + 1))
    cols = ["queue_rank", "StockCode", "Description", "priority", "priority_points", "detected_problem",
            "classification", "risk_level", "dead_stock_risk_score", "days_since_last_sale", "total_qty", "abc_xyz",
            "trend_class", "demand_pattern", "supporting_evidence", "intervention", "recommended_actions",
            "why_appropriate", "reason_for_recommendation", "expected_business_benefit",
            "expected_impact_direction", "inventory_value_impact", "required_information", "confidence",
            "requires_human_approval", "approval_note", "evaluation_method",
            "evidence_flags", "forecast_next_4w_units"]
    return d[[c for c in cols if c in d.columns]]
