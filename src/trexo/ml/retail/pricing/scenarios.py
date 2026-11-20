"""Offer scenario analysis with hard constraints. Never invents cost; never recommends below the floor.

Demand response (ASSUMPTION-DRIVEN unless validated): q(p) = q0 * min((p/p0)^e, uplift_cap), e < 0.
`elasticity_source` is carried into every output row: 'estimated_pooled' (observational, associational),
'assumed' (user/config), or 'none' (e = 0, i.e. no demand response: discounts then only cost margin).

Objective for choosing an offer (explicit):
  J = gross_profit(horizon) - carrying_cost(remaining units) - obsolescence_loss(remaining units)
  carrying_cost = holding_rate_annual * horizon/365 * unit_cost * remaining
  obsolescence_loss = obsolescence_rate * unit_cost * remaining           (0 unless supplied)
Requires unit_cost. Without cost the table is returned as ANALYSIS_ONLY (revenue, units) and nothing is selected.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
import pandas as pd

LEVELS = (0.0, 0.05, 0.10, 0.15, 0.20)


@dataclass
class PricingRules:
    max_discount: float = 0.30           # business-approved ceiling (config; must be approved by the owner)
    min_margin: float | None = None      # minimum margin on price, e.g. 0.10; None = only price >= cost
    price_floor: float | None = None     # absolute approved floor per unit
    uplift_cap: float = 3.0              # demand multiplier cannot exceed this (guard against extrapolation)
    min_gain_to_discount: float = 0.0    # J must beat no-discount by more than this to recommend a discount


def effective_floor(cost: float | None, rules: PricingRules) -> float | None:
    f = [x for x in (rules.price_floor,) if x is not None]
    if cost is not None:
        f.append(cost if rules.min_margin is None else cost / (1 - rules.min_margin))
    return max(f) if f else None


def scenario_table(price: float, stock: float, daily_demand: float, horizon_days: int, elasticity: float,
                   elasticity_source: str, cost: float | None = None, rules: PricingRules = PricingRules(),
                   levels=LEVELS, holding_rate_annual: float | None = None, obsolescence_rate: float = 0.0) -> pd.DataFrame:
    if price <= 0 or stock < 0 or daily_demand < 0 or horizon_days <= 0: raise ValueError("invalid pricing inputs")
    if elasticity > 0: raise ValueError("elasticity must be <= 0")
    floor = effective_floor(cost, rules)
    rows = []
    for d in levels:
        p = price * (1 - d)
        mult = min((p / price) ** elasticity, rules.uplift_cap) if d > 0 else 1.0
        demand = daily_demand * horizon_days * mult
        sold = min(stock, demand); remaining = stock - sold
        feasible, why = True, []
        if d > rules.max_discount + 1e-12: feasible = False; why.append("above approved maximum discount")
        if floor is not None and p < floor - 1e-9: feasible = False; why.append("below price floor/margin")
        if floor is None and d > 0: why.append("no cost or floor supplied: analysis only")
        r = {"discount": d, "offer_price": p, "expected_demand_units": demand, "expected_units_sold": sold,
             "remaining_stock": remaining, "revenue": sold * p, "discount_cost_vs_list": sold * price * d,
             "units_vs_no_discount": None, "feasible": feasible, "infeasible_reason": "; ".join(why),
             "elasticity": elasticity, "elasticity_source": elasticity_source, "demand_multiplier": mult}
        if cost is not None:
            gp = sold * (p - cost)
            carry = (holding_rate_annual or 0.0) * horizon_days / 365 * cost * remaining
            obs = obsolescence_rate * cost * remaining
            r.update(gross_profit=gp, carrying_cost=carry, obsolescence_loss=obs, objective_J=gp - carry - obs,
                     capital_remaining=cost * remaining, profit_status="COMPUTED_FROM_SUPPLIED_COST")
        else:
            r.update(gross_profit=None, carrying_cost=None, obsolescence_loss=None, objective_J=None,
                     capital_remaining=None, profit_status="NOT_COMPUTED_COST_MISSING")
        rows.append(r)
    t = pd.DataFrame(rows)
    base_sold = t.loc[t["discount"] == 0, "expected_units_sold"].iloc[0]
    t["units_vs_no_discount"] = t["expected_units_sold"] - base_sold
    return t


def choose_offer(t: pd.DataFrame, rules: PricingRules = PricingRules()) -> dict:
    if t["objective_J"].isna().any():
        return {"selected_discount": None, "status": "ANALYSIS_ONLY_COST_MISSING",
                "reason": "Unit cost not supplied: profit cannot be verified, so no offer is selected."}
    feas = t[t["feasible"]]
    if feas.empty:
        return {"selected_discount": None, "status": "NO_FEASIBLE_OFFER", "reason": "all levels violate floor/limits"}
    base = feas[feas["discount"] == 0]
    best = feas.loc[feas["objective_J"].idxmax()]
    if len(base) and best["discount"] > 0 and best["objective_J"] - base["objective_J"].iloc[0] <= rules.min_gain_to_discount:
        best = base.iloc[0]
    return {"selected_discount": float(best["discount"]), "offer_price": float(best["offer_price"]),
            "status": "RECOMMENDATION_REQUIRES_APPROVAL", "objective_J": float(best["objective_J"]),
            "expected_units_sold": float(best["expected_units_sold"]), "elasticity_source": best["elasticity_source"],
            "reason": "maximises J among feasible levels" if best["discount"] > 0 else "no discount beats full price on the objective"}


def choose_discount_vectorised(price, stock, daily_demand, horizon_days, elasticity, cost, rules: PricingRules = PricingRules(),
                               levels=LEVELS, holding_rate_annual: float = 0.0, obsolescence_rate: float = 0.0):
    """Numpy equivalent of scenario_table + choose_offer for many products at once (used by the replay for speed;
    equivalence to the reference implementation is unit-tested). Arrays in, array of chosen discounts out."""
    price, stock, dd, cost = (np.asarray(x, float) for x in (price, stock, daily_demand, cost))
    floor = cost if rules.min_margin is None else cost / (1 - rules.min_margin)
    if rules.price_floor is not None: floor = np.maximum(floor, rules.price_floor)
    J, feas = [], []
    for d in levels:
        p = price * (1 - d)
        mult = np.minimum((p / price) ** elasticity, rules.uplift_cap) if d > 0 else np.ones_like(price)
        sold = np.minimum(stock, dd * horizon_days * mult); rem = stock - sold
        J.append(sold * (p - cost) - holding_rate_annual * horizon_days / 365 * cost * rem - obsolescence_rate * cost * rem)
        feas.append((d <= rules.max_discount + 1e-12) & (p >= floor - 1e-9))
    J = np.vstack(J); feas = np.vstack(feas)
    Jm = np.where(feas, J, -np.inf); best = Jm.argmax(axis=0)
    chosen = np.asarray(levels)[best].astype(float)
    base_ok = feas[0]
    with np.errstate(invalid="ignore"):
        gain = Jm[best, np.arange(J.shape[1])] - np.where(base_ok, J[0], -np.inf)
    chosen = np.where((chosen > 0) & base_ok & (gain <= rules.min_gain_to_discount), 0.0, chosen)
    chosen = np.where(~feas.any(axis=0), 0.0, chosen)          # no feasible level: no offer
    return chosen
