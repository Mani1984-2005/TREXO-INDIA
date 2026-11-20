import numpy as np, pandas as pd, pytest
from trexo.ml.retail.service import RetailIntelligenceService, DISCLAIMER
from trexo.ml.inference.service import InvalidRequestError, ModelUnavailableError
from trexo.ml.retail.inventory.synthetic import synthetic_shop


@pytest.fixture(scope="module")
def svc():
    try: return RetailIntelligenceService()
    except ModelUnavailableError: pytest.skip("retail models not trained")


@pytest.fixture(scope="module")
def events():
    e, prods, _ = synthetic_shop(n_products=10, days=120, seed=3)
    return e.assign(ts=e["ts"].astype(str), expiry_date=None).to_dict("records"), prods


def test_balances_reject_and_reconcile(svc, events):
    ev, _ = events
    r = svc.inventory_balances({"events": ev + [{"event_id": "BAD", "product_id": "P000", "location": "MAIN", "ts": "2011-02-01", "type": "SALE", "qty": 10 ** 6}],
                                "reported_counts": [{"product_id": "P000", "location": "MAIN", "reported_on_hand": 1.0}]})
    assert any(x["event_id"] == "BAD" and x["reject_reason"].startswith("NEGATIVE_BALANCE") for x in r["rejected_events"])
    assert DISCLAIMER in r["disclaimer"] and r["reconciliation"][0]["status"] in ("DISCREPANCY", "MATCH")
    with pytest.raises(InvalidRequestError): svc.inventory_balances({"events": []})


def test_priority_and_recovery_are_recommendations_only(svc, events):
    ev, prods = events
    p = svc.stock_priority({"events": ev, "as_of": "2011-04-25"})
    assert p["status"] == "OK" and all("Fresh" not in q["category"] for q in p["queue"]) and any("not calibrated" in w for w in p["warnings"])
    rec = svc.recovery_recommendations({"events": ev, "as_of": "2011-04-25", "prices": {k: v[1] for k, v in prods.items()}, "costs": {k: v[0] for k, v in prods.items()},
                                        "rules": {"min_margin": 0.1, "max_discount": 0.2}})
    for x in rec["plan"]:
        assert x["requires_management_approval"] is True and x["confidence"] != "HIGH"
        if x["suggested_offer"]: assert x["suggested_offer"]["offer_price"] >= x["price_floor"] - 1e-9
    assert DISCLAIMER in rec["disclaimer"]


def test_pricing_endpoint_rules(svc):
    r = svc.pricing_scenarios({"price": 10, "stock": 100, "daily_demand": 1, "cost": 6, "rules": {"min_margin": 0.1, "max_discount": 0.15}, "elasticity": -2})
    assert r["selection"]["status"] in ("RECOMMENDATION_REQUIRES_APPROVAL", "NO_FEASIBLE_OFFER") and "assumed" in r["elasticity_source"]
    assert max(s["discount"] for s in r["scenarios"] if s["feasible"]) <= 0.15
    nc = svc.pricing_scenarios({"price": 10, "stock": 100, "daily_demand": 1}); assert nc["selection"]["selected_discount"] is None
    assert "estimated_pooled" in nc["elasticity_source"] or "assumed" in nc["elasticity_source"]
    with pytest.raises(InvalidRequestError): svc.pricing_scenarios({"price": 10})
    with pytest.raises(InvalidRequestError): svc.pricing_scenarios({"price": 10, "stock": 5, "daily_demand": 1, "elasticity": 0.4})


def test_bundle_endpoint(svc):
    r = svc.bundle_recommendations({"product_id": "does-not-exist"})
    assert r["candidates"] == [] and any("no co-purchase evidence" in w for w in r["warnings"])
    with pytest.raises(InvalidRequestError): svc.bundle_recommendations({})


def test_existing_ml_layer_unchanged_regression():
    from trexo.ml.inference.service import InferenceService
    s = InferenceService(); r = s.dead_stock_detection({"product_id": "T", "as_of": "2011-06-01", "sales_history": [{"date": "2011-05-30", "quantity": 3, "unit_price": 2.0}] * 3})
    assert r["status"] == "OK" and r["status_type"] == "DEMAND_INACTIVITY_INDICATOR_ONLY"
