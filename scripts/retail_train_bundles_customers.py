import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
from trexo.ml.config import REPORT_DIR, SEED
from trexo.ml.data_pipeline.pipeline import load_sales
from trexo.ml.retail.bundles.basket import mine_pairs, directed, recommend_bundles
from trexo.ml.retail.customers import intelligence as ci
from trexo.ml.registry.registry import save_model_bundle
R = REPORT_DIR / "retail"; R.mkdir(parents=True, exist_ok=True)
sales = load_sales(); SPLIT = pd.Timestamp("2011-09-01")   # train: before; test: on/after (>=3 months)
tr = sales[sales["Date"] < SPLIT]; te = sales[sales["Date"] >= SPLIT]
res = {"train_period": [str(tr.Date.min().date()), str(tr.Date.max().date())], "test_period": [str(te.Date.min().date()), str(te.Date.max().date())]}

# ---------------- bundles: temporal validation of pair rules
rules_tr, info_tr = mine_pairs(tr); rules_te, info_te = mine_pairs(te, min_pair_baskets=1)
d_tr = directed(rules_tr); d_te = directed(rules_te)
top = d_tr[(d_tr["lift"] >= 1.5) & (d_tr["confidence"] >= 0.05)].sort_values("lift", ascending=False)
m = top.merge(d_te[["antecedent", "consequent", "lift", "confidence", "pair_baskets"]], on=["antecedent", "consequent"], how="left", suffixes=("_train", "_test"))
tb = te.groupby("InvoiceNo")["StockCode"].apply(lambda x: set(x)); tb = tb[tb.apply(len) >= 2]
item_te = pd.Series([i for s in tb for i in s]).value_counts() / len(tb)
base_rate = m["consequent"].map(item_te).fillna(0)
# did the antecedent->consequent co-occur at all in test baskets, and is conf above the consequent's base rate?
seen = m["pair_baskets_test"].fillna(0) > 0
res["bundles"] = {"train_info": info_tr, "n_rules_train_directed": int(len(d_tr)), "n_candidate_rules(lift>=1.5,conf>=0.05)": int(len(m)),
    "share_candidates_cooccurring_in_test": float(seen.mean()),
    "median_test_lift_of_candidates_that_cooccur": float(m.loc[seen, "lift_test"].median()),
    "share_with_test_lift_gt_1": float((m["lift_test"].fillna(0) > 1).mean()),
    "train_lift_vs_test_lift_spearman": float(m[["lift_train", "lift_test"]].dropna().corr(method="spearman").iloc[0, 1]),
    "mean_test_confidence_of_candidates": float(m["confidence_test"].fillna(0).mean()),
    "mean_test_base_rate_of_consequent": float(base_rate.mean()),
    "test_conf_over_base_rate": float(m["confidence_test"].fillna(0).mean() / max(base_rate.mean(), 1e-9))}
# ---------------- bundle recommendations for real slow products (sales-only capability; no stock claims)
cls = pd.read_csv(REPORT_DIR / "dead_stock_classification.csv", dtype={"StockCode": str})
mov = pd.read_csv(REPORT_DIR / "product_movement_classification.csv", dtype={"StockCode": str})
rules_all, info_all = mine_pairs(sales); d_all = directed(rules_all)
prices = sales.groupby("StockCode")["UnitPrice"].median()
fast = set(mov.loc[mov["speed_class"].isin(["Fast-moving", "Medium-moving"]) & (mov["days_since_last_sale"] < 30), "StockCode"])
risky = cls.loc[cls["classification"].isin(["Slow Moving Stock", "At-Risk Stock", "Critical Dead-Stock Risk"]) & (cls["evidence_quality"] != "LOW") &
                (cls["demand_pattern"] != "SEASONAL_OR_CAMPAIGN_CONCENTRATED"), "StockCode"].tolist()
rec = recommend_bundles(risky, d_all, fast, prices, min_lift=1.5, min_conf=0.05, top_k=2, bundle_discount=0.10)
desc = pd.read_csv("data/ml/product_descriptions_v1.csv", dtype=str).set_index("StockCode")["Description"]
rec["slow_name"] = rec["slow_product"].map(desc); rec["anchor_name"] = rec["anchor_product"].map(desc)
rec["status"] = "RECOMMENDATION_ONLY: bundle profit unverified (cost missing); requires owner approval; sales-based (no stock data)"
rec.to_csv(R / "bundle_recommendations_sales_based.csv", index=False)
res["bundles"]["slow_products_considered"] = len(risky); res["bundles"]["slow_products_with_bundle_candidate"] = int(rec["slow_product"].nunique())
res["bundles"]["pairs_used_all_data"] = info_all

# ---------------- customers
res["customers"] = {"anonymous_share_of_valid_lines": float(sales["CustomerID"].isna().mean()), "customers_total": int(sales["CustomerID"].nunique())}
r = ci.rfm(sales, sales["Date"].max()); seg, km, prof = ci.segment(r, k=4, seed=SEED)
rep = ci.segment_report(seg); rep.to_csv(R / "customer_segments_aggregate.csv", index=False)
res["customers"]["segments"] = rep.to_dict("records")
model = ci.item_item_model(tr, SPLIT - pd.Timedelta(days=1))
test_buys = te.dropna(subset=["CustomerID"]).groupby("CustomerID")["StockCode"].apply(set).to_dict()
train_buys = tr.dropna(subset=["CustomerID"]).groupby("CustomerID")["StockCode"].apply(set).to_dict()
new_only = {c: (s - train_buys.get(c, set())) for c, s in test_buys.items()}        # evaluate on products NOT bought before
res["customers"]["recommender_eval"] = ci.hit_rate(model, new_only, k=10)
# discount-proxy persistence (train vs test)
dp_tr = ci.discount_proxy(tr, SPLIT - pd.Timedelta(days=1)); dp_te = ci.discount_proxy(te, te["Date"].max()).rename(columns={"low_price_share": "te"})
j = dp_tr.merge(dp_te[["CustomerID", "te"]], on="CustomerID")
res["customers"]["discount_proxy_persistence"] = {"customers": int(len(j)), "spearman_train_vs_test": float(j[["low_price_share", "te"]].corr(method="spearman").iloc[0, 1]),
    "mean_low_price_share": float(dp_tr["low_price_share"].mean()),
    "note": "PROXY (purchase lines at <=90% of product median price); no promotion log exists, so this is not measured promotion response"}
meta_b = save_model_bundle("bundles", {"rules_directed": d_all[d_all["lift"] >= 1.2]}, {"validation": res["bundles"], "min_pair_baskets": 15, "max_basket": 60, "random_seed": SEED,
                           "contains_customer_data": False})
meta_c = save_model_bundle("customers", {"kmeans": km, "segment_profile": prof}, {"validation": res["customers"], "contains_customer_level_data": False, "k": 4, "random_seed": SEED})
res["artifacts"] = {"bundles": meta_b["model_version"], "customers": meta_c["model_version"]}
(R / "bundles_customers_results.json").write_text(json.dumps(res, indent=2, default=str))
print(json.dumps({k: res[k] for k in ("bundles", "customers")}, indent=1, default=str)[:3500])
