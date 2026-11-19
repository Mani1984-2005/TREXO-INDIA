import numpy as np, pandas as pd, pytest
from trexo.ml.forecasting.engine import (_croston, _ses, demand_class, forecast_metrics, ml_features, classical_forecasts, weekly_matrix)
from trexo.ml.reorder.policy import reorder_calc, demand_based_guidance
from trexo.ml.recommendations.engine import _actions, tier, build_queue
from trexo.ml.financial.intelligence import inventory_financials, data_readiness
from trexo.ml.anomaly.detector import transaction_quality, demand_anomalies
from trexo.ml.simulation.backtest import simulate


def test_croston_and_sba_known_values():
    y = np.array([0, 4, 0, 0, 4, 0.0])
    f = _croston(y, alpha=0.1); assert f == pytest.approx(4 / ((1 - 0.1) * 2 + 0.1 * 3) * 1.0, rel=1e-9)
    assert _croston(y, 0.1, sba=True) == pytest.approx(f * 0.95)
    assert _croston(np.zeros(5)) == 0.0


def test_ses_constant_series():
    assert _ses(np.full(10, 7.0)) == pytest.approx(7.0)


def test_metrics_zero_safe():
    m = forecast_metrics(np.zeros(5), np.zeros(5))
    assert m["sMAPE"] == 0 and m["MAE"] == 0 and np.isfinite(m["WAPE"])
    m2 = forecast_metrics([10, 0], [12, 0]); assert m2["bias"] == pytest.approx(0.2)


def test_demand_classes():
    assert demand_class(np.array([5, 6, 5, 6, 5, 6.0])) == "smooth"
    assert demand_class(np.array([0, 0, 0, 5, 0, 0, 0, 6.0])) == "intermittent"
    assert demand_class(np.array([0, 0, 0, 5.0])) == "insufficient"


def test_ml_features_ignore_future_weeks():
    m = np.random.default_rng(0).poisson(3, (4, 30)).astype(float)
    a = ml_features(m, 20, 3); m2 = m.copy(); m2[:, 20:] *= 100
    assert np.array_equal(a, ml_features(m2, 20, 3))


def test_weekly_matrix_uses_complete_weeks_only(sales):
    m, start = weekly_matrix(sales)
    assert m.shape[1] == ((sales["Date"].max() - sales["Date"].min()).days + 1) // 7


def test_reorder_numbers():
    r = reorder_calc(10, 3, on_hand_qty=50, lead_time_days=9, service_level=0.95, review_period_days=7)
    z = 1.6448536; safety = z * 3 * 3
    assert r["safety_stock"] == pytest.approx(safety, rel=1e-4) and r["reorder_point"] == pytest.approx(90 + safety, rel=1e-4)
    assert r["recommended_order_qty"] == pytest.approx(10 * 16 + safety - 50, rel=1e-4)
    assert reorder_calc(10, 3, 50, 9, moq=25)["recommended_order_qty"] % 25 == 0


def test_reorder_never_invents_quantity():
    r = reorder_calc(10, 3)
    assert r["status"] == "INSUFFICIENT_INPUTS" and r["recommended_order_qty"] is None
    assert set(r["inputs_missing"]) == {"on_hand_qty", "lead_time_days"}
    assert reorder_calc(10, 3, 50, 9, dead_stock_risk_score=0.9)["recommended_order_qty"] == 0.0
    with pytest.raises(ValueError): reorder_calc(-1, 1, 1, 1)
    assert demand_based_guidance(12, 0.9, "Critical Dead-Stock Risk")["recommended_order_qty"] is None


def _row(**k):
    base = dict(classification="Critical Dead-Stock Risk", demand_pattern="CONTINUOUS_DEMAND", abc_class="C", price_cv=0.1, high_value_declining=False)
    base.update(k); return base


def test_recommendations_logic():
    seasonal, _ = _actions(_row(demand_pattern="SEASONAL_OR_CAMPAIGN_CONCENTRATED"))
    assert any("seasonal timing" in a for a in seasonal) and not any("Prioritise selling" in a for a in seasonal)
    new, _ = _actions(_row(demand_pattern="INSUFFICIENT_OBSERVATION_HISTORY"))
    assert new == ["Monitor; collect more sales history before intervening"]
    a, _ = _actions(_row(abc_class="A")); assert any("Escalate" in x for x in a)
    assert not any("discount" in x.lower() and "margin" not in x.lower() for x in a)   # no blind discount
    assert tier(0.7) == "P1" and tier(0.35) == "P2" and tier(0.05) == "P4"


def test_financial_separation_and_validation():
    stock = pd.DataFrame({"StockCode": ["A", "B"], "on_hand_qty": [10, 20], "unit_cost": [2.0, 5.0]})
    cls = pd.DataFrame({"StockCode": ["A", "B"], "classification": ["Confirmed Dead Stock", "Slow Moving Stock"]})
    r = inventory_financials(stock, cls, holding_rate_annual=0.2, recovery_rate=0.3)
    assert r["MEASURED"]["dead_stock_value"] == 20 and r["MEASURED"]["slow_moving_value"] == 100
    assert "recoverable_value_if_cleared" in r["SCENARIO"] and "recoverable_value_if_cleared" not in r["MEASURED"]
    assert "recoverable_value_if_cleared" not in inventory_financials(stock, cls)["SCENARIO"]
    with pytest.raises(ValueError): inventory_financials(stock.drop(columns="unit_cost"), cls)
    assert not data_readiness(["InvoiceNo", "Quantity"])["available"].any()


def test_anomalies_reported_not_removed(sales):
    s = sales.copy(); s.loc[s.index[0], "IsExactDuplicate"] = True
    n_before = len(s); tq = transaction_quality(s)
    assert len(s) == n_before and "EXACT_DUPLICATE_ROW" in tq["flags"].iloc[0]
    assert (tq["family"] == "TRANSACTION_QUALITY").all()
    wk = pd.DataFrame([[4.0] * 20 + [400.0] + [4.0] * 20], index=["S"]); wk.iloc[0, 3] = 5
    d = demand_anomalies(wk); assert (d["type"] == "SALES_SPIKE").any() and (d["family"] == "BUSINESS_DEMAND").all()


def test_simulation_rejects_calibration_without_complete_labels(sales):
    cal = pd.DataFrame({"cutoff": [pd.Timestamp("2011-04-01")], "days_since_last_sale": [3], "y_inactive": [0]})
    with pytest.raises(ValueError): simulate(sales, cal, ["2011-04-20"], 60)     # label window not closed before cutoff
