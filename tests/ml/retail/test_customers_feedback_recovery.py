import numpy as np, pandas as pd, pytest
from trexo.ml.retail.customers.intelligence import (pseudonymise, rfm, segment, segment_report, item_item_model, recommend_for_customer, MIN_GROUP, discount_proxy)
from trexo.ml.retail.feedback.store import FeedbackStore, assign_arm, analyse_experiment, retraining_gate
from trexo.ml.retail.recovery.engine import recovery_plan
from trexo.ml.retail.pricing.scenarios import PricingRules
from trexo.ml.retail.retail_simulation.replay import run_replay, ReplayAssumptions
from sklearn.isotonic import IsotonicRegression


def cust_sales():
    rng = np.random.default_rng(0); rows = []; n = 0
    for c in range(80):
        for k in range(rng.integers(1, 8)):
            for p in rng.choice(30, 4, replace=False):
                n += 1; d = pd.Timestamp("2011-01-01") + pd.Timedelta(days=int(rng.integers(0, 300)))
                rows.append({"InvoiceNo": f"{c}-{k}", "StockCode": f"S{p}", "Quantity": 2.0, "UnitPrice": 1.0 + (p % 3) * (0.8 if rng.random() < .1 else 1), "LineValue": 2.0, "Date": d, "CustomerID": float(c)})
    rows += [{"InvoiceNo": "anon", "StockCode": "S1", "Quantity": 1.0, "UnitPrice": 1.0, "LineValue": 1.0, "Date": pd.Timestamp("2011-02-01"), "CustomerID": np.nan}]
    return pd.DataFrame(rows)


def test_privacy_controls():
    s = cust_sales(); r = rfm(s, "2011-12-01"); assert r["CustomerID"].notna().all() and len(r) == 80       # anonymous rows excluded
    p = pseudonymise(r["CustomerID"], "salt"); assert p.nunique() == 80 and not p.str.contains(r"^\d+$").any() and (pseudonymise(r["CustomerID"], "other") != p).all()
    seg, km, prof = segment(r); rep = segment_report(seg)
    tiny = seg.copy(); tiny.loc[tiny.index[:3], "segment"] = "tiny"; rt = segment_report(tiny)
    assert rt.loc[rt["segment"] == "tiny", "median_spend"].isna().all()                                     # k-anonymity suppression
    m = item_item_model(s, "2011-12-01", min_item_customers=2)
    with pytest.raises(PermissionError): recommend_for_customer(m, 1.0)
    assert len(recommend_for_customer(m, 1.0, 5, consent_verified=True)) <= 5
    assert recommend_for_customer(m, 99999.0, 5, consent_verified=True) == []


def test_feedback_workflow_and_gating():
    f = FeedbackStore()
    rid = f.log_recommendation({"product_id": "A", "suggested_discount": 0.1, "predicted_units": 20, "predicted_gross_profit": 50.0, "risk_score": .8})
    with pytest.raises(PermissionError): f.record_execution(rid, "2011-01-01", "2011-01-15", 0.1, 9.0)       # no approval yet
    with pytest.raises(ValueError): f.record_approval(rid, "", "APPROVED")
    f.record_approval(rid, "owner", "APPROVED", 0.1, 9.0); f.record_execution(rid, "2011-01-01", "2011-01-15", 0.1, 9.0)
    with pytest.raises(ValueError): f.record_outcome(rid, -1, 9, 1, 0)
    f.record_outcome(rid, 25, 9.0, 60.0, 5)
    pv = f.prediction_vs_actual(); assert pv["n"] == 1 and pv["units_MAE"] == 5 and pv["gross_profit_MAE"] == 10
    rid2 = f.log_recommendation({"product_id": "B"}); f.record_approval(rid2, "owner", "REJECTED")
    with pytest.raises(PermissionError): f.record_execution(rid2, "a", "b", 0, 1)


def test_experiment_assignment_and_analysis():
    arms = [assign_arm(f"u{i}", "exp1") for i in range(2000)]
    assert abs(arms.count("treatment") / 2000 - 0.5) < 0.05 and assign_arm("u1", "exp1") == assign_arm("u1", "exp1")
    rng = np.random.default_rng(1)
    df = pd.DataFrame({"arm": ["treatment"] * 100 + ["control"] * 100, "units_sold": np.r_[rng.normal(12, 2, 100), rng.normal(10, 2, 100)]})
    r = analyse_experiment(df); assert r["status"] == "OK" and r["significant_at_95"] and 1.0 < r["effect"] < 3.0
    assert analyse_experiment(df.iloc[:30])["status"] == "INSUFFICIENT_DATA"


def test_retraining_gate_never_auto_promotes():
    assert not retraining_gate(10, .9, .8, True, human_approval=True)["promote"]
    assert not retraining_gate(500, .9, .8, True, human_approval=False)["promote"]
    assert not retraining_gate(500, .81, .8, True, human_approval=True)["promote"]
    assert retraining_gate(500, .9, .8, True, human_approval=True)["promote"]


def stock_frame():
    return pd.DataFrame({"product_id": ["A", "B", "C", "D"], "category": ["Critical Dead-Stock Risk", "Slow-Moving Stock", "Ageing Stock", "Fresh Stock"],
                         "units_on_hand": [200.0, 80, 30, 10], "weighted_age_days": [200.0, 120, 100, 5], "forecast_daily": [0.2, 0.3, 1.0, 1.0],
                         "coverage_days": [1000.0, 266, 30, 10], "urgency": [0.9, 0.6, 0.4, 0.0], "risk_score": [0.9, 0.5, 0.3, 0.0],
                         "capital_exposure": [400.0, 160, 60, 20]})


def test_recovery_plan_rules():
    prices = pd.Series({"A": 4.0, "B": 3.0, "C": 5.0, "D": 2.0}); costs = pd.Series({"A": 2.0, "B": 2.0, "C": 3.0, "D": 1.0})
    p = recovery_plan(stock_frame(), prices, costs, patterns=pd.Series({"B": "SEASONAL_OR_CAMPAIGN_CONCENTRATED"}), elasticity=-2.0, rules=PricingRules(min_margin=0.1))
    ids = set(p["product_id"]); assert "D" not in ids and "C" not in ids          # fresh, and C sells out within 60 days -> no intervention
    assert p["requires_management_approval"].all() and (p["rank"].tolist() == list(range(1, len(p) + 1)))
    b = p[p["product_id"] == "B"].iloc[0]; assert "seasonal" in b["recommended_actions"].lower() and b["suggested_offer"] is None
    a = p[p["product_id"] == "A"].iloc[0]
    assert "Stop or pause replenishment" in a["recommended_actions"]
    if a["suggested_offer"]: assert a["suggested_offer"]["offer_price"] >= a["price_floor"] - 1e-9
    nocost = recovery_plan(stock_frame(), prices, None, elasticity=-2.0).set_index("product_id")
    assert nocost.loc["A", "suggested_offer"] is None and nocost.loc["A", "confidence"] != "HIGH"


def test_replay_runs_and_is_labelled_scenario():
    rng = np.random.default_rng(3); rows = []
    for p in range(20):
        for d in range(0, 260, 3):
            q = rng.poisson(5 if p < 10 or d < 150 else 0)
            if q: rows.append({"InvoiceNo": f"{p}-{d}", "StockCode": f"S{p}", "Quantity": float(q), "UnitPrice": 5.0, "LineValue": 5.0 * q, "Date": pd.Timestamp("2011-01-01") + pd.Timedelta(days=d), "CustomerID": 1.0})
    s = pd.DataFrame(rows); iso = IsotonicRegression(out_of_bounds="clip").fit([0, 30, 60, 120], [0.0, 0.2, 0.7, 0.95])
    r0 = run_replay(s, iso, "2011-06-01", 12, ReplayAssumptions(true_elasticity=0.0))
    r2 = run_replay(s, iso, "2011-06-01", 12, ReplayAssumptions(true_elasticity=-2.0))
    for r in (r0, r2):
        assert r["baseline"]["initial_units"] == r["trexo"]["initial_units"]
        assert r["trexo"]["units_sold"] <= r["trexo"]["initial_units"] + 1e-9
    assert r0["baseline"]["gross_profit"] >= r0["trexo"]["gross_profit"] - 1e-9       # with zero response a discount can only lose margin
    assert r2["trexo"]["units_sold"] >= r2["baseline"]["units_sold"] - 1e-9
