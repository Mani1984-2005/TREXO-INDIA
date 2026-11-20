"""Chronological clearance replay on REAL product demand with ASSUMED inventory/cost/response inputs.
Everything stock/cost/response related is SIMULATED (labelled). Real = weekly demand quantities and prices.
Both arms: no replenishment (a clearance comparison, not a full operations simulation)."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from ..pricing.scenarios import PricingRules, choose_discount_vectorised


@dataclass
class ReplayAssumptions:
    stock_multiple: float = 1.5      # A1: initial stock = multiple x units sold in prior 90 days  (ASSUMED)
    cost_ratio: float = 0.60         # A2: unit cost = ratio x product median price               (ASSUMED)
    min_margin: float = 0.10         # business rule used as floor (config; needs owner approval)
    max_discount: float = 0.20
    decision_elasticity: float = -1.0   # elasticity the DECISION engine believes
    true_elasticity: float = -1.0       # elasticity the SIMULATED customers actually have
    uplift_cap: float = 3.0
    risk_threshold: float = 0.6
    cover_threshold_days: float = 120
    decision_horizon_days: int = 28
    holding_rate_annual: float = 0.20
    loss_given_dead: float = 0.5        # A3: share of cost lost if leftover stock turns out dead (ASSUMED); decision uses risk x this


def run_replay(sales: pd.DataFrame, iso: IsotonicRegression, start, n_weeks: int, a: ReplayAssumptions, min_invoices: int = 3, seed: int = 42) -> dict:
    start = pd.Timestamp(start)
    pre = sales[sales["Date"] <= start]
    inv = pre.groupby("StockCode")["InvoiceNo"].nunique(); prods = inv[inv >= min_invoices].index
    s = sales[sales["StockCode"].isin(prods)]
    price = s.groupby("StockCode")["UnitPrice"].median()
    q90 = s[(s["Date"] <= start) & (s["Date"] > start - pd.Timedelta(days=90))].groupby("StockCode")["Quantity"].sum().reindex(prods).fillna(0)
    ok = q90 > 0; prods = prods[ok.to_numpy()]; q90 = q90[prods]
    stock0 = np.ceil(a.stock_multiple * q90).astype(float); stock = stock0.copy()
    cost = a.cost_ratio * price.reindex(prods)
    rules = PricingRules(max_discount=a.max_discount, min_margin=a.min_margin, uplift_cap=a.uplift_cap)
    wk_edges = [start + pd.Timedelta(days=7 * i) for i in range(n_weeks + 1)]
    out = {}
    for arm in ("baseline", "trexo"):
        st = stock.copy(); gp = rev = disc = units = 0.0; offers = 0
        for w in range(n_weeks):
            lo, hi = wk_edges[w], wk_edges[w + 1]
            actual = s[(s["Date"] > lo) & (s["Date"] <= hi)].groupby("StockCode")["Quantity"].sum().reindex(prods).fillna(0)
            d = pd.Series(0.0, index=prods)
            if arm == "trexo":
                hist = s[s["Date"] <= lo]
                last = hist.groupby("StockCode")["Date"].max().reindex(prods)
                rec = (lo - last).dt.days.fillna(999)
                risk = pd.Series(iso.predict(rec.to_numpy(float)), index=prods)
                daily = hist[hist["Date"] > lo - pd.Timedelta(days=56)].groupby("StockCode")["Quantity"].sum().reindex(prods).fillna(0) / 56
                cov = st / daily.replace(0, np.nan)
                flag = (st > 0) & ((risk >= a.risk_threshold) | (cov.fillna(np.inf) > a.cover_threshold_days))
                idx = prods[flag.to_numpy()]
                if len(idx):
                    ch = choose_discount_vectorised(price[idx], st[idx], daily[idx], a.decision_horizon_days, a.decision_elasticity, cost[idx], rules,
                                                    holding_rate_annual=a.holding_rate_annual,
                                                    obsolescence_rate=a.loss_given_dead * risk[idx].to_numpy())
                    d.loc[idx] = ch; offers += int((ch > 0).sum())
            mult = np.where(d > 0, np.minimum((1 - d) ** a.true_elasticity, a.uplift_cap), 1.0)
            demand = actual * mult
            sold = np.minimum(st, demand); p = price.reindex(prods) * (1 - d)
            st = st - sold; units += sold.sum(); rev += (sold * p).sum(); gp += (sold * (p - cost)).sum(); disc += (sold * price.reindex(prods) * d).sum()
        # dead-stock proxy: leftover units of products with ZERO real demand in the last 8 weeks of the window
        last8 = s[(s["Date"] > wk_edges[max(0, n_weeks - 8)]) & (s["Date"] <= wk_edges[n_weeks])].groupby("StockCode")["Quantity"].sum().reindex(prods).fillna(0)
        dead_left = st[last8 == 0].sum()
        writeoff = a.loss_given_dead * float((st[last8 == 0] * cost[last8 == 0]).sum())
        out[arm] = {"initial_units": float(stock0.sum()), "units_sold": float(units), "sell_through": float(units / stock0.sum()),
                    "ending_units": float(st.sum()), "ending_stock_cost_value": float((st * cost).sum()),
                    "gross_profit": float(gp), "assumed_writeoff_of_dead_leftover": float(writeoff), "profit_after_assumed_writeoff": float(gp - writeoff), "revenue": float(rev), "discount_expense_vs_list": float(disc),
                    "leftover_units_zero_recent_demand": float(dead_left), "offers_applied_product_weeks": int(offers),
                    "products": int(len(prods)),
                    "initial_stock_cost_value": float((stock0 * cost).sum())}
    return out
