import numpy as np, pandas as pd, pytest
from trexo.ml.retail.pricing.scenarios import scenario_table, choose_offer, PricingRules, effective_floor
from trexo.ml.retail.optimization.profit_optimizer import optimise, compare_strategies
from trexo.ml.retail.bundles.basket import mine_pairs, bundle_economics, recommend_bundles, directed
from trexo.ml.retail.recovery.engine import recovery_plan
from trexo.ml.retail.ageing.engine import classify_stock


def T(**k):
    a = dict(price=10.0, stock=100.0, daily_demand=1.0, horizon_days=28, elasticity=-2.0, elasticity_source="assumed", cost=6.0)
    a.update(k); return scenario_table(**a)


def test_floor_never_violated():
    t = T(cost=8.5, rules=PricingRules(min_margin=0.1))           # floor = 8.5/0.9 = 9.44 -> only 0% and 5% (9.5) feasible
    f = t[t["feasible"]]; assert f["offer_price"].min() >= 8.5 / 0.9 - 1e-9 and set(f["discount"]) == {0.0, 0.05}
    sel = choose_offer(t, PricingRules(min_margin=0.1)); assert sel["offer_price"] >= 8.5 / 0.9 - 1e-9
    assert effective_floor(None, PricingRules()) is None and effective_floor(6.0, PricingRules(price_floor=9.0)) == 9.0


def test_max_discount_limit():
    t = T(rules=PricingRules(max_discount=0.10)); assert t[t["feasible"]]["discount"].max() == 0.10


def test_no_cost_means_analysis_only():
    t = T(cost=None); assert t["gross_profit"].isna().all() and (t["profit_status"] == "NOT_COMPUTED_COST_MISSING").all()
    s = choose_offer(t); assert s["selected_discount"] is None and s["status"] == "ANALYSIS_ONLY_COST_MISSING"


def test_math_of_one_scenario():
    t = T(elasticity=-1.0, daily_demand=1.0, stock=100).set_index("discount")
    r = t.loc[0.10]; assert r["demand_multiplier"] == pytest.approx(0.9 ** -1.0)
    assert r["expected_units_sold"] == pytest.approx(28 / 0.9) and r["gross_profit"] == pytest.approx(28 / 0.9 * (9 - 6))
    assert r["remaining_stock"] == pytest.approx(100 - 28 / 0.9)
    s = T(stock=10, daily_demand=5).set_index("discount"); assert (s["expected_units_sold"] <= 10).all()   # cannot sell more than stock


def test_no_discount_when_it_does_not_pay():
    t = T(elasticity=0.0); assert choose_offer(t)["selected_discount"] == 0.0              # no demand response -> discounting only loses margin
    t2 = T(elasticity=-3.0, stock=1000, daily_demand=10, holding_rate_annual=0.0); assert choose_offer(t2)["selected_discount"] in (0.0, 0.05, 0.10, 0.15, 0.20)
    with pytest.raises(ValueError): T(elasticity=0.5)
    with pytest.raises(ValueError): T(price=-1)


def test_uplift_cap():
    t = T(elasticity=-10.0, rules=PricingRules(uplift_cap=2.0)); assert t["demand_multiplier"].max() <= 2.0 + 1e-12


def tables():
    return {"A": T(elasticity=-3, stock=500, daily_demand=5, holding_rate_annual=0.3, obsolescence_rate=0.2),
            "B": T(elasticity=-0.2, stock=50, daily_demand=3, cost=7.0, holding_rate_annual=0.3),
            "C": T(elasticity=-2, stock=300, daily_demand=0.5, cost=5.0, holding_rate_annual=0.3, obsolescence_rate=0.3),
            "N": T(cost=None)}


def test_optimizer_constraints_and_objective_ordering():
    tb = tables(); res = optimise(tb, "profit_max"); a = res["assignment"]
    assert res["status"] == "OPTIMAL" and set(a["product_id"]) == {"A", "B", "C"} and "N" not in set(a["product_id"])
    assert a["product_id"].is_unique
    for pid, g in a.groupby("product_id"):
        assert tb[pid].set_index("discount").loc[g["discount"].iloc[0], "feasible"]
    # profit_max has the highest objective; clearance_max sells the most; budget respected
    cmp = compare_strategies(tb).set_index("strategy")
    assert cmp.loc["profit_max", "total_objective_J"] >= cmp.loc["balanced", "total_objective_J"] - 1e-9
    assert cmp.loc["clearance_max", "total_units_sold"] >= cmp.loc["profit_max", "total_units_sold"] - 1e-9
    assert cmp.loc["clearance_max", "total_objective_J"] >= 0.95 * cmp.loc["profit_max", "total_objective_J"] - 1e-9
    b = optimise(tb, "profit_max", discount_budget=1.0)["assignment"]; assert b["discount_cost_vs_list"].sum() <= 1.0 + 1e-9


def test_optimizer_is_global_optimum_vs_bruteforce():
    tb = {k: v for k, v in tables().items() if k != "N"}
    best = max(sum(tb[p][tb[p]["feasible"]].iloc[i]["objective_J"] for p, i in zip(tb, idx))
               for idx in __import__("itertools").product(*[range(int(tb[p]["feasible"].sum())) for p in tb]))
    assert optimise(tb, "profit_max")["summary"]["total_objective_J"] == pytest.approx(best)


def test_bundle_mining_and_economics():
    rows = []
    for i in range(60): rows += [(f"I{i}", "A"), (f"I{i}", "B")]
    for i in range(60, 160): rows += [(f"I{i}", "A")]
    for i in range(160, 260): rows += [(f"I{i}", "C"), (f"I{i}", "D")]
    s = pd.DataFrame(rows, columns=["InvoiceNo", "StockCode"])
    r, info = mine_pairs(s, min_pair_baskets=15); d = directed(r)
    ab = r[(r.item_a == "A") & (r.item_b == "B")].iloc[0]
    assert ab["pair_baskets"] == 60 and ab["lift"] == pytest.approx(60 * 160 / (60 * 60))   # statistics are over multi-item baskets only (160 here) and ab["conf_b_to_a"] == 1.0
    rec = recommend_bundles(["B"], d, {"A"}, pd.Series({"A": 3.0, "B": 2.0}), min_lift=1.2)
    assert len(rec) == 1 and rec["anchor_product"].iloc[0] == "A" and rec["bundle_price"].iloc[0] == pytest.approx(4.5)
    assert recommend_bundles(["D"], d, {"A"}, pd.Series({"A": 3.0, "D": 2.0})).empty          # no evidence -> no bundle
    assert bundle_economics(3, 2, 0.1, 2.0, 2.0, min_margin=0.10)["feasible"]                     # 4.5 vs cost 4.0 -> margin 11.1%
    assert not bundle_economics(3, 2, 0.1, 2.0, 2.0, min_margin=0.12)["feasible"]
    assert not bundle_economics(3, 2, 0.5, 2.0, 2.0)["feasible"]                                  # below cost
    assert bundle_economics(3, 2, 0.1)["profit_status"] == "NOT_COMPUTED_COST_MISSING"


def test_vectorised_chooser_equals_reference():
    from trexo.ml.retail.pricing.scenarios import choose_discount_vectorised
    rng = np.random.default_rng(5); n = 300
    price = rng.uniform(2, 20, n); cost = price * rng.uniform(0.3, 0.95, n); stock = rng.uniform(1, 500, n); dd = rng.uniform(0, 8, n)
    for e, rules in ((-0.7, PricingRules(min_margin=0.1, max_discount=0.2)), (-2.5, PricingRules(max_discount=0.15)), (0.0, PricingRules())):
        v = choose_discount_vectorised(price, stock, dd, 28, e, cost, rules, holding_rate_annual=0.2)
        ref = []
        for i in range(n):
            t = scenario_table(price[i], stock[i], dd[i], 28, e, "assumed", cost[i], rules, holding_rate_annual=0.2)
            s = choose_offer(t, rules); ref.append(s["selected_discount"] or 0.0)
        assert np.allclose(v, ref)
