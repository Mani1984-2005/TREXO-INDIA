"""Business explanations. Rule-based (the deployed predictor is a calibrated one-feature rule,
so the explanation IS the model) plus permutation importance for the rejected ML challenger."""
from __future__ import annotations
import pandas as pd


def five_part_explanation(row: dict, missing: list[str]) -> dict:
    return {
        "what_was_detected": f"{row['classification']} ({row['status_type'].replace('_', ' ').lower()}).",
        "supporting_evidence": row["risk_explanation"],
        "why_it_matters": ("A product with a high chance of no sales keeps tying up purchasing budget and "
                           "storage if replenished; the cost of acting wrongly is higher for top-revenue items."
                           if row["classification"] in ("At-Risk Stock", "Critical Dead-Stock Risk", "Confirmed Dead Stock")
                           else "No dead-stock concern detected from demand evidence."),
        "what_to_do": row.get("recommended_actions") or row.get("recommended_intervention"),
        "information_still_required": missing,
    }


def load_importance(path) -> pd.DataFrame:
    return pd.read_csv(path)
