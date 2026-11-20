"""Constrained offer assignment via mixed-integer linear programming (scipy.optimize.milp).
x[i,k] in {0,1}: product i takes scenario k (from scenario_table, infeasible levels removed).
Strategies (explicit objectives; conflicts are shown, not hidden):
  profit_max       : maximise sum J
  balanced         : maximise sum J + lam * capital_released   (capital_released = cost*(units_sold - units_sold_no_discount))
  clearance_max    : maximise units sold subject to sum J >= (1 - tolerance) * best-profit J   (profit protection)
Shared constraints: one level per product; optional total discount-cost budget."""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.optimize import milp, LinearConstraint, Bounds


def _stack(tables: dict) -> pd.DataFrame:
    out = []
    for pid, t in tables.items():
        if t["objective_J"].isna().any(): continue      # cost missing -> excluded from optimisation, reported by caller
        f = t[t["feasible"]].copy()
        if f.empty: continue
        f["product_id"] = pid
        base_units = t.loc[t["discount"] == 0, "expected_units_sold"].iloc[0]
        f["units_extra"] = f["expected_units_sold"] - base_units
        out.append(f)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def _solve(S: pd.DataFrame, c: np.ndarray, budget=None, min_J=None):
    n = len(S); prods = S["product_id"].unique()
    A = np.zeros((len(prods), n)); idx = {p: i for i, p in enumerate(prods)}
    for j, p in enumerate(S["product_id"]): A[idx[p], j] = 1
    cons = [LinearConstraint(A, 1, 1)]
    if budget is not None: cons.append(LinearConstraint(S["discount_cost_vs_list"].to_numpy()[None, :], -np.inf, budget))
    if min_J is not None: cons.append(LinearConstraint(S["objective_J"].to_numpy()[None, :], min_J, np.inf))
    r = milp(c=-c, constraints=cons, integrality=np.ones(n), bounds=Bounds(0, 1))
    if not r.success: return None
    return S[np.round(r.x) == 1].reset_index(drop=True)


def optimise(tables: dict, strategy: str = "profit_max", discount_budget: float | None = None,
             lam: float = 0.5, tolerance: float = 0.05) -> dict:
    S = _stack(tables)
    if S.empty: return {"status": "NO_OPTIMISABLE_PRODUCTS", "assignment": pd.DataFrame()}
    cap = S["capital_remaining"].to_numpy()
    released = (S["units_extra"] * (S["capital_remaining"] / S["remaining_stock"].replace(0, np.nan))).fillna(0).to_numpy()
    if strategy == "profit_max":
        sol = _solve(S, S["objective_J"].to_numpy(), discount_budget)
    elif strategy == "balanced":
        sol = _solve(S, S["objective_J"].to_numpy() + lam * released, discount_budget)
    elif strategy == "clearance_max":
        best = _solve(S, S["objective_J"].to_numpy(), discount_budget)
        if best is None: return {"status": "INFEASIBLE", "assignment": pd.DataFrame()}
        sol = _solve(S, S["expected_units_sold"].to_numpy(), discount_budget,
                     min_J=best["objective_J"].sum() - tolerance * abs(best["objective_J"].sum()))
    else:
        raise ValueError("unknown strategy")
    if sol is None: return {"status": "INFEASIBLE", "assignment": pd.DataFrame()}
    summ = {"strategy": strategy, "products": int(len(sol)), "total_objective_J": float(sol["objective_J"].sum()),
            "total_gross_profit": float(sol["gross_profit"].sum()), "total_units_sold": float(sol["expected_units_sold"].sum()),
            "total_discount_cost": float(sol["discount_cost_vs_list"].sum()), "units_with_discount": int((sol["discount"] > 0).sum()),
            "total_remaining_capital": float(sol["capital_remaining"].sum())}
    return {"status": "OPTIMAL", "summary": summ, "assignment": sol[["product_id", "discount", "offer_price", "expected_units_sold",
            "objective_J", "gross_profit", "discount_cost_vs_list", "remaining_stock", "elasticity_source"]]}


def compare_strategies(tables: dict, discount_budget: float | None = None) -> pd.DataFrame:
    rows = []
    for s in ("profit_max", "balanced", "clearance_max"):
        r = optimise(tables, s, discount_budget)
        if r["status"] == "OPTIMAL": rows.append(r["summary"])
    return pd.DataFrame(rows)
