"""Dead-stock recovery engine: turns stock category + demand + cost + bundle evidence into ranked,
approval-gated recommendations. Every output is a RECOMMENDATION; nothing is executed.
Rank = urgency x feasibility x benefit_pct  (all documented below)
  feasibility: 1.0 offer computable with cost+floor; 0.7 analysis-only offer / bundle with evidence; 0.5 non-price action only
  benefit_pct: percentile rank of capital exposure (if cost known) else of remaining units x list price (revenue at risk)"""
from __future__ import annotations
import numpy as np
import pandas as pd
from ..pricing.scenarios import scenario_table, choose_offer, PricingRules, effective_floor

UNAVAILABLE = {"inter_location_transfer": "needs per-location demand and stock in >=2 locations",
               "supplier_return_review": "needs supplier terms (return window/eligibility)",
               "customer_targeting": "needs consent-verified customer data"}


def recovery_plan(stock: pd.DataFrame, prices: pd.Series, costs: pd.Series | None = None, bundle_recs: pd.DataFrame | None = None,
                  patterns: pd.Series | None = None, elasticity: float = -1.0, elasticity_source: str = "assumed",
                  rules: PricingRules = PricingRules(), horizon_days: int = 28, holding_rate_annual: float | None = None,
                  supplier_return_eligible: set | None = None, names: pd.Series | None = None) -> pd.DataFrame:
    """stock: classify_stock() output (needs category, units_on_hand, weighted_age_days, forecast_daily, coverage_days, urgency, risk_score)."""
    rows = []
    bund = bundle_recs.groupby("slow_product").first() if bundle_recs is not None and len(bundle_recs) else pd.DataFrame()
    for r in stock.itertuples():
        cat = r.category
        if cat in ("Fresh Stock", "Normal Stock"): continue
        pid = r.product_id
        selling_ok = np.isfinite(r.coverage_days) and r.coverage_days <= 60 and cat in ("Ageing Stock", "Slow-Moving Stock")
        if selling_ok:
            continue            # selling sufficiently well: no discount, no intervention
        price = prices.get(pid); cost = costs.get(pid) if costs is not None else None
        cost = None if cost is None or pd.isna(cost) else float(cost)
        pattern = patterns.get(pid) if patterns is not None else None
        acts, why, offer, outcome = [], [], None, "NOT_COMPUTED"
        floor = effective_floor(cost, rules) if price is not None else None
        seasonal = pattern == "SEASONAL_OR_CAMPAIGN_CONCENTRATED"
        if cat in ("At-Risk Stock", "Critical Dead-Stock Risk", "Confirmed Dead Stock"):
            acts += ["Stop or pause replenishment"]; why.append("demand-inactivity risk is high")
        if seasonal:
            acts += ["Review seasonal timing before any discount"]; why.append("sales were concentrated in a short window")
        else:
            if pid in bund.index:
                b = bund.loc[pid]; acts += [f"Offer a bundle with {b['anchor_product']} (co-purchase evidence)"]; why.append(b["evidence"])
            if cat in ("Critical Dead-Stock Risk", "Confirmed Dead Stock", "Slow-Moving Stock", "Ageing Stock", "At-Risk Stock") and price is not None:
                daily = r.forecast_daily if pd.notna(r.forecast_daily) else 0.0
                t = scenario_table(float(price), float(r.units_on_hand), float(daily), horizon_days, elasticity, elasticity_source, cost, rules,
                                   holding_rate_annual=holding_rate_annual)
                sel = choose_offer(t, rules)
                if sel["status"] == "RECOMMENDATION_REQUIRES_APPROVAL" and sel["selected_discount"] > 0:
                    offer = {"discount": sel["selected_discount"], "offer_price": sel["offer_price"], "elasticity_source": elasticity_source}
                    acts += [f"Controlled clearance offer ({sel['selected_discount']:.0%})"]
                    best = t[t["discount"] == sel["selected_discount"]].iloc[0]
                    outcome = {"expected_gross_profit": best["gross_profit"], "expected_units_sold": best["expected_units_sold"],
                               "status": "MODEL_ESTIMATE_ASSUMED_RESPONSE" if elasticity_source == "assumed" else "MODEL_ESTIMATE_ASSOCIATIONAL"}
                elif sel["status"] == "ANALYSIS_ONLY_COST_MISSING":
                    acts += ["Price scenarios available (analysis only: cost missing, no offer selected)"]
                    outcome = {"status": "NOT_COMPUTED_COST_MISSING"}
                else:
                    acts += ["Do not discount: no feasible offer improves the objective"]
            if "Offer a bundle" not in " ".join(acts): acts += ["Improve product visibility / cross-sell at point of sale"]
        if pid in (supplier_return_eligible or set()): acts += ["Supplier return review"]
        if cat == "Confirmed Dead Stock": acts += ["Assortment review and management intervention"]
        # HIGH requires an experimentally validated price response; observational/assumed elasticities cap confidence at MEDIUM
        conf = "LOW" if (pd.isna(r.risk_score) or cost is None) else ("HIGH" if elasticity_source == "experimentally_validated" else "MEDIUM")
        feas = 1.0 if offer is not None and cost is not None else (0.7 if (pid in bund.index or price is not None) else 0.5)
        expo = (r.capital_exposure if pd.notna(r.capital_exposure) else r.units_on_hand * (price if price is not None else 0.0))
        rows.append({"product_id": pid, "name": names.get(pid) if names is not None else None, "remaining_quantity": r.units_on_hand,
                     "stock_age_days": r.weighted_age_days, "risk_classification": cat, "urgency": r.urgency,
                     "evidence": f"{r.units_on_hand:.0f} units, age {r.weighted_age_days:.0f}d, cover {'n/a' if not np.isfinite(r.coverage_days) else round(r.coverage_days)}d, risk {r.risk_score if pd.notna(r.risk_score) else 'n/a'}",
                     "recommended_actions": " | ".join(acts), "why": " ".join(why), "suggested_offer": offer, "price_floor": floor,
                     "expected_quantity_movement": (outcome.get("expected_units_sold") if isinstance(outcome, dict) else None),
                     "estimated_financial_outcome": outcome, "confidence": conf, "requires_management_approval": True,
                     "outcome_measurement": "A/B or matched-control comparison of units, price and gross profit over the offer window; record in feedback store",
                     "feasibility": feas, "exposure_basis": "capital_at_cost" if pd.notna(r.capital_exposure) else "revenue_at_list_price",
                     "exposure": expo, "data_unavailable_actions": "; ".join(UNAVAILABLE)})
    out = pd.DataFrame(rows)
    if out.empty: return out
    out["benefit_pct"] = out["exposure"].rank(pct=True)
    out["rank_score"] = out["urgency"] * out["feasibility"] * out["benefit_pct"]
    out = out.sort_values("rank_score", ascending=False).reset_index(drop=True)
    out.insert(0, "rank", range(1, len(out) + 1))
    return out
