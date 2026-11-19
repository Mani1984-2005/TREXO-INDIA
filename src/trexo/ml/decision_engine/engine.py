"""Module I: management decision intelligence. Pure aggregation of documented module outputs;
no additional hidden scoring. Every figure traces to a module table."""
from __future__ import annotations
import pandas as pd


def management_summary(cls: pd.DataFrame, mov: pd.DataFrame, queue: pd.DataFrame, fc4w: pd.Series,
                       as_of: str, top_n: int = 10) -> dict:
    d = cls.merge(mov[["StockCode", "abc_class", "trend_class", "revenue_to_date", "high_value_declining"]],
                  on="StockCode", how="left")
    d["fc4w"] = d["StockCode"].map(fc4w)
    counts = d["classification"].value_counts().to_dict()
    risky = d[d["classification"].isin(["At-Risk Stock", "Critical Dead-Stock Risk"])]
    tot_rev = d["revenue_to_date"].sum()
    do_not_reorder = risky[risky["evidence_quality"] != "LOW"]
    growing = d[(d["trend_class"] == "Growing") & d["classification"].isin(
        ["Healthy Moving Stock", "Normal Moving Stock"])].nlargest(top_n, "qty_60d")
    declining = d[d["trend_class"] == "Declining"].nlargest(top_n, "revenue_to_date")
    summary = {
        "as_of": as_of, "products_assessed": int(len(d)),
        "status_type": "DEMAND_INACTIVITY_INDICATORS (no stock-on-hand data supplied)",
        "classification_counts": counts,
        "biggest_problem": (
            f"{counts.get('Critical Dead-Stock Risk', 0)} products are at Critical dead-stock risk and "
            f"{counts.get('At-Risk Stock', 0)} At-Risk by demand inactivity; physical stock and its value "
            "cannot be measured because stock, cost and receipts are absent from the dataset."),
        "historical_revenue_share_of_critical_and_atrisk_products": float(risky["revenue_to_date"].sum() / tot_rev),
        "historical_revenue_note": "MEASURED historical sales revenue to date; not inventory value, not capital tied up.",
        "capital_trapped": "NOT COMPUTABLE: requires on_hand_qty and unit_cost (see financial data-readiness report).",
        "priority_counts": queue["priority"].value_counts().to_dict(),
        "do_not_reorder_count_evidence_not_low": int(len(do_not_reorder)),
        "immediate_attention_top": queue.head(top_n)[["queue_rank", "StockCode", "Description", "priority",
                                                      "classification", "dead_stock_risk_score", "recommended_actions"]].to_dict("records"),
        "increasing_demand_top": growing[["StockCode", "Description", "qty_60d", "trend_ratio_60"]].to_dict("records"),
        "declining_demand_top_by_revenue": declining[["StockCode", "Description", "trend_ratio_60", "revenue_to_date"]].to_dict("records"),
        "caveat": ("Trend flags are computed over a period containing the pre-Christmas ramp and only one "
                   "seasonal cycle; 'Growing' is partly seasonal."),
    }
    return summary
