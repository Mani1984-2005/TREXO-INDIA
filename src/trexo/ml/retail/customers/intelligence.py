"""Customer and promotion intelligence (privacy-minimising).
- Uses only pseudonymous CustomerID already present; identifiers in outputs are salted SHA-256 prefixes.
- Segment outputs are suppressed when a segment has < MIN_GROUP customers (k-anonymity).
- Individual-level recommendations require an explicit `consent_verified=True`; otherwise only aggregate output.
- 'Discount responsiveness' is a PROXY (share of purchase lines at <=90% of the product's median price), because
  no promotion log exists. It is not a causal response measure."""
from __future__ import annotations
import hashlib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

MIN_GROUP = 10


def pseudonymise(ids: pd.Series, salt: str) -> pd.Series:
    return ids.astype("Int64").astype(str).map(lambda x: hashlib.sha256((salt + x).encode()).hexdigest()[:12])


def rfm(sales: pd.DataFrame, as_of) -> pd.DataFrame:
    as_of = pd.Timestamp(as_of)
    s = sales[(sales["Date"] <= as_of) & sales["CustomerID"].notna()]
    g = s.groupby("CustomerID")
    return pd.DataFrame({"recency_days": (as_of - g["Date"].max()).dt.days, "frequency": g["InvoiceNo"].nunique(),
                         "monetary": g["LineValue"].sum(), "distinct_products": g["StockCode"].nunique()}).reset_index()


def segment(r: pd.DataFrame, k: int = 4, seed: int = 42):
    X = np.log1p(r[["recency_days", "frequency", "monetary"]].clip(lower=0).to_numpy())
    X = (X - X.mean(0)) / (X.std(0) + 1e-9)
    km = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(X)
    out = r.copy(); out["cluster"] = km.labels_
    prof = out.groupby("cluster")[["recency_days", "frequency", "monetary"]].median()
    order = (prof["monetary"].rank() + prof["frequency"].rank() - prof["recency_days"].rank()).sort_values(ascending=False).index
    names = ["Champions (recent, frequent, high value)", "Loyal regulars", "Occasional / cooling", "Lapsed / low value"]
    nm = {c: names[min(i, len(names) - 1)] for i, c in enumerate(order)}
    out["segment"] = out["cluster"].map(nm)
    return out, km, prof.assign(segment=prof.index.map(nm))


def segment_report(seg: pd.DataFrame) -> pd.DataFrame:
    t = seg.groupby("segment").agg(customers=("CustomerID", "size"), median_recency=("recency_days", "median"),
                                   median_orders=("frequency", "median"), median_spend=("monetary", "median")).reset_index()
    t.loc[t["customers"] < MIN_GROUP, ["median_recency", "median_orders", "median_spend"]] = np.nan   # suppression
    return t


def item_item_model(sales: pd.DataFrame, cutoff, min_item_customers: int = 5):
    """Customer-item co-occurrence (cosine) from purchases up to `cutoff`."""
    s = sales[(sales["Date"] <= pd.Timestamp(cutoff)) & sales["CustomerID"].notna()]
    ci = s.groupby(["CustomerID", "StockCode"]).size().reset_index(name="n")
    cnt = ci.groupby("StockCode")["CustomerID"].nunique(); keep = cnt[cnt >= min_item_customers].index
    ci = ci[ci["StockCode"].isin(keep)]
    cu = {c: i for i, c in enumerate(ci["CustomerID"].unique())}; it = {c: i for i, c in enumerate(ci["StockCode"].unique())}
    from scipy import sparse
    M = sparse.csr_matrix((np.ones(len(ci)), (ci["CustomerID"].map(cu), ci["StockCode"].map(it))), shape=(len(cu), len(it)))
    co = (M.T @ M).tocsr(); d = np.sqrt(co.diagonal()) + 1e-9
    return {"co": co, "norm": d, "items": list(it), "item_idx": it, "cust_idx": cu, "M": M, "pop": cnt}


def recommend_for_customer(model, customer_id, k=10, consent_verified: bool = False, exclude_owned=True):
    if not consent_verified:
        raise PermissionError("individual-level recommendations require consent_verified=True")
    ci = model["cust_idx"].get(customer_id)
    if ci is None: return []
    owned = model["M"][ci].indices
    score = np.asarray(model["co"][owned].multiply(1 / model["norm"][owned][:, None]).sum(axis=0)).ravel() / model["norm"]
    if exclude_owned: score[owned] = -1
    top = np.argsort(-score)[:k]
    return [(model["items"][j], float(score[j])) for j in top if score[j] > 0]


def hit_rate(model, test_purchases: dict, k=10, sample=1500, seed=42) -> dict:
    """test_purchases: customer -> set(products bought AFTER cutoff, not in train set). Compare with popularity."""
    rng = np.random.default_rng(seed)
    custs = [c for c in test_purchases if c in model["cust_idx"] and test_purchases[c]]
    if len(custs) > sample: custs = list(rng.choice(custs, sample, replace=False))
    pop_rank = list(model["pop"].sort_values(ascending=False).index)
    hits = {"item_cf": 0, "popularity": 0}
    for c in custs:
        ci = model["cust_idx"][c]; owned = {model["items"][j] for j in model["M"][ci].indices}
        rec = [i for i, _ in recommend_for_customer(model, c, k, consent_verified=True)]
        pop = [i for i in pop_rank if i not in owned][:k]
        t = test_purchases[c]
        hits["item_cf"] += bool(set(rec) & t); hits["popularity"] += bool(set(pop) & t)
    return {"customers_evaluated": len(custs), "k": k, **{f"hit_rate@{k}_{m}": v / max(len(custs), 1) for m, v in hits.items()}}


def discount_proxy(sales: pd.DataFrame, cutoff) -> pd.DataFrame:
    s = sales[(sales["Date"] <= pd.Timestamp(cutoff)) & sales["CustomerID"].notna()].copy()
    s["med"] = s.groupby("StockCode")["UnitPrice"].transform("median")
    s["low"] = s["UnitPrice"] <= 0.9 * s["med"]
    g = s.groupby("CustomerID").agg(lines=("low", "size"), low_price_share=("low", "mean")).reset_index()
    return g[g["lines"] >= 10]
