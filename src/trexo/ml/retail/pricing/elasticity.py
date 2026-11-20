"""Price-response estimation from OBSERVATIONAL data (UCI Online Retail).

Model: Poisson regression, response = number of distinct invoices containing the product in a week
(purchase events; not quantity, because wholesale quantity tiers make average price and quantity
mechanically correlated), regressors = product fixed effects + week fixed effects +
log(weekly median unit price / product mean log price). The price coefficient is an
elasticity of purchase frequency. It is ASSOCIATIONAL: prices were set by the business, not randomised.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.linear_model import PoissonRegressor


def weekly_price_panel(sales: pd.DataFrame, min_weeks: int = 10) -> pd.DataFrame:
    start = sales["Date"].min().normalize()
    s = sales.assign(w=(sales["Date"] - start).dt.days // 7)
    n_w = ((sales["Date"].max() - start).days + 1) // 7
    s = s[s["w"] < n_w]
    g = s.groupby(["StockCode", "w"]).agg(invoices=("InvoiceNo", "nunique"), qty=("Quantity", "sum"), price=("UnitPrice", "median")).reset_index()
    first = g.groupby("StockCode")["w"].transform("min"); last = g.groupby("StockCode")["w"].transform("max")
    n = g.groupby("StockCode")["w"].transform("size")
    g = g[n >= min_weeks]
    # complete the grid between first and last sale week so zero-sale weeks are observations (price carried forward)
    rows = []
    for code, d in g.groupby("StockCode"):
        full = pd.DataFrame({"w": range(int(d["w"].min()), int(d["w"].max()) + 1)})
        m = full.merge(d, on="w", how="left"); m["StockCode"] = code
        m["invoices"] = m["invoices"].fillna(0); m["qty"] = m["qty"].fillna(0)
        m["price"] = m["price"].ffill().bfill()
        rows.append(m)
    p = pd.concat(rows, ignore_index=True)
    p["lp"] = np.log(p["price"]); p["rel_lp"] = p["lp"] - p.groupby("StockCode")["lp"].transform("mean")
    return p


def fit_price_coefficient(panel: pd.DataFrame, alpha: float = 1e-6, seed: int = 0) -> float:
    prods = {c: i for i, c in enumerate(panel["StockCode"].unique())}
    wks = {w: i for i, w in enumerate(sorted(panel["w"].unique()))}
    n = len(panel); pi = panel["StockCode"].map(prods).to_numpy(); wi = panel["w"].map(wks).to_numpy()
    X = sparse.hstack([sparse.csr_matrix((np.ones(n), (np.arange(n), pi)), shape=(n, len(prods))),
                       sparse.csr_matrix((np.ones(n), (np.arange(n), wi)), shape=(n, len(wks))),
                       sparse.csr_matrix(panel[["rel_lp"]].to_numpy())]).tocsr()
    m = PoissonRegressor(alpha=alpha, max_iter=300, fit_intercept=False).fit(X, panel["invoices"].to_numpy())
    return float(m.coef_[-1])


def estimate_with_validation(panel: pd.DataFrame, n_boot: int = 40, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    full = fit_price_coefficient(panel)
    codes = panel["StockCode"].unique()
    boots = []
    for _ in range(n_boot):                       # cluster (product) bootstrap
        pick = rng.choice(codes, len(codes), replace=True)
        parts = [g for _, g in panel[panel["StockCode"].isin(pick)].groupby("StockCode")]
        cnt = pd.Series(pick).value_counts()
        b = pd.concat([parts_i.assign(StockCode=f"{parts_i['StockCode'].iloc[0]}#{k}") for parts_i in parts for k in range(int(cnt[parts_i['StockCode'].iloc[0]]))], ignore_index=True)
        b["rel_lp"] = b["lp"] - b.groupby("StockCode")["lp"].transform("mean")
        boots.append(fit_price_coefficient(b))
    mid = panel["w"].median()
    halves = {}
    for name, d in (("first_half", panel[panel["w"] <= mid]), ("second_half", panel[panel["w"] > mid])):
        d = d.copy(); d["rel_lp"] = d["lp"] - d.groupby("StockCode")["lp"].transform("mean")
        n = d.groupby("StockCode")["w"].transform("size"); d = d[n >= 6]
        halves[name] = fit_price_coefficient(d)
    pl = panel.copy(); pl["rel_lp"] = pl.groupby("StockCode")["rel_lp"].transform(lambda x: rng.permutation(x.to_numpy()))
    placebo = fit_price_coefficient(pl)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    stable = (np.sign(halves["first_half"]) == np.sign(halves["second_half"]) == np.sign(full))
    usable = bool(hi < 0 and stable and abs(placebo) < abs(full) / 3)
    return {"coefficient": full, "ci95": [float(lo), float(hi)], "bootstrap_sd": float(np.std(boots)),
            "split_half": halves, "placebo_permuted_price": float(placebo), "n_obs": int(len(panel)),
            "n_products": int(len(codes)), "usable_as_pooled_prior": usable,
            "identification_caveat": "observational; prices chosen by the business; associational not causal"}
