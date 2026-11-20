"""Market-basket pair mining (support / confidence / lift) + bundle economics.
Pairs only (a 2-product bundle is the commercially executable unit); a full Apriori/FP-Growth
over ~4k items adds little for pair offers and mlxtend is not installed. Pair counting is exact."""
from __future__ import annotations
from itertools import combinations
from collections import Counter
import numpy as np
import pandas as pd

MAX_BASKET = 60   # larger wholesale baskets create combinatorial spurious pairs; reported, not deleted


def mine_pairs(sales: pd.DataFrame, min_pair_baskets: int = 15, max_basket: int = MAX_BASKET) -> tuple[pd.DataFrame, dict]:
    b = sales.groupby("InvoiceNo")["StockCode"].apply(lambda x: sorted(set(x)))
    n_all = len(b); b = b[b.apply(len).between(2, max_basket)]
    item = Counter(); pair = Counter()
    for items in b:
        item.update(items); pair.update(combinations(items, 2))
    N = len(b)
    rows = [(a, c, k, item[a], item[c]) for (a, c), k in pair.items() if k >= min_pair_baskets]
    r = pd.DataFrame(rows, columns=["item_a", "item_b", "pair_baskets", "baskets_a", "baskets_b"])
    r["support"] = r["pair_baskets"] / N
    r["lift"] = r["pair_baskets"] * N / (r["baskets_a"] * r["baskets_b"])
    r["conf_a_to_b"] = r["pair_baskets"] / r["baskets_a"]; r["conf_b_to_a"] = r["pair_baskets"] / r["baskets_b"]
    info = {"baskets_total": int(n_all), "baskets_used": int(N), "max_basket": max_basket}
    return r, info


def directed(rules: pd.DataFrame) -> pd.DataFrame:
    """Both directions: antecedent -> consequent."""
    ab = rules.rename(columns={"item_a": "antecedent", "item_b": "consequent", "conf_a_to_b": "confidence"})[["antecedent", "consequent", "pair_baskets", "support", "lift", "confidence", "baskets_a", "baskets_b"]]
    ba = rules.rename(columns={"item_b": "antecedent", "item_a": "consequent", "conf_b_to_a": "confidence", "baskets_b": "baskets_a", "baskets_a": "baskets_b"})[["antecedent", "consequent", "pair_baskets", "support", "lift", "confidence", "baskets_a", "baskets_b"]]
    return pd.concat([ab, ba], ignore_index=True)


def bundle_economics(price_anchor: float, price_target: float, bundle_discount: float, cost_anchor: float | None = None,
                     cost_target: float | None = None, min_margin: float | None = None, price_floor: float | None = None) -> dict:
    if min(price_anchor, price_target) <= 0 or not 0 <= bundle_discount < 1: raise ValueError("invalid bundle inputs")
    list_total = price_anchor + price_target
    bp = list_total * (1 - bundle_discount)
    out = {"list_total": list_total, "bundle_price": bp, "discount_cost_per_bundle": list_total - bp, "feasible": True, "notes": []}
    if price_floor is not None and bp < price_floor: out["feasible"] = False; out["notes"].append("below approved price floor")
    if cost_anchor is not None and cost_target is not None:
        cost = cost_anchor + cost_target; margin = (bp - cost) / bp
        out.update(unit_cost=cost, gross_profit_per_bundle=bp - cost, margin=margin, profit_status="COMPUTED_FROM_SUPPLIED_COST")
        if bp < cost or (min_margin is not None and margin < min_margin): out["feasible"] = False; out["notes"].append("below cost or minimum margin")
    else:
        out.update(unit_cost=None, gross_profit_per_bundle=None, margin=None, profit_status="NOT_COMPUTED_COST_MISSING")
        out["notes"].append("bundle profit unverified: costs missing")
    return out


def recommend_bundles(target_items: list[str], rules_directed: pd.DataFrame, fast_items: set[str], prices: pd.Series,
                      min_lift: float = 1.5, min_conf: float = 0.05, top_k: int = 3, bundle_discount: float = 0.10) -> pd.DataFrame:
    """For each slow target B find anchors A (fast-moving) with co-purchase evidence A -> B.
    Never bundles without evidence of co-purchase (no 'incompatible clearing')."""
    d = rules_directed[(rules_directed["consequent"].isin(target_items)) & (rules_directed["antecedent"].isin(fast_items))
                       & (rules_directed["lift"] >= min_lift) & (rules_directed["confidence"] >= min_conf)].copy()
    d["rank_score"] = d["lift"] * d["confidence"] * np.log1p(d["pair_baskets"])
    d = d.sort_values("rank_score", ascending=False).groupby("consequent").head(top_k)
    rows = []
    for r in d.itertuples():
        pa, pb = prices.get(r.antecedent), prices.get(r.consequent)
        if pd.isna(pa) or pd.isna(pb): continue
        e = bundle_economics(float(pa), float(pb), bundle_discount)
        rows.append({"slow_product": r.consequent, "anchor_product": r.antecedent, "pair_baskets": int(r.pair_baskets),
                     "lift": float(r.lift), "confidence_anchor_to_slow": float(r.confidence), "rank_score": float(r.rank_score),
                     "list_total": e["list_total"], "bundle_price": e["bundle_price"], "profit_status": e["profit_status"],
                     "evidence": f"{int(r.pair_baskets)} baskets contained both; buyers of the anchor were {r.lift:.1f}x more likely than average to also buy the slow item"})
    return pd.DataFrame(rows)
