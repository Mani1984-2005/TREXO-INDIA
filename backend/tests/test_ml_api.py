from __future__ import annotations


def _body(history, **overrides):
    payload = {
        "product_id": "TEST-SKU",
        "as_of": "2011-06-01",
        "description": "Test product",
        "sales_history": history,
        "on_hand_qty": 12,
        "unit_cost": 3.5,
        "lead_time_days": 3,
        "service_level": 0.95,
    }
    payload.update(overrides)
    return payload


def test_dead_stock_prediction(client, auth, ml_history):
    resp = client.post("/api/v1/ml/dead-stock", json=_body(ml_history), headers=auth)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "OK"
    assert 0.0 <= body["dead_stock_risk_score"] <= 1.0
    assert body["model_version"].startswith("dead_stock-")
    assert body["predictor"] == "baseline_recency_rule"
    assert body["status_type"] in {"DEMAND_INACTIVITY_INDICATOR_ONLY", "STOCK_AND_DEMAND_EVIDENCE"}
    assert isinstance(body["human_review_required"], bool)


def test_dead_stock_no_valid_sales(client, auth):
    resp = client.post("/api/v1/ml/dead-stock", json=_body([]), headers=auth)
    assert resp.status_code == 200
    assert resp.json()["status"] == "NO_VALID_SALES"
    assert resp.json()["prediction"] is None


def test_dead_stock_rejects_non_product_code(client, auth, ml_history):
    resp = client.post(
        "/api/v1/ml/dead-stock", json=_body(ml_history, product_id="POST"), headers=auth
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"


def test_d01_records_excluded_with_warning(client, auth, ml_history):
    history = list(ml_history) + [
        {"date": "2011-03-01", "quantity": 5, "unit_price": 2.0, "invoice_no": "A563185"}
    ]
    resp = client.post("/api/v1/ml/dead-stock", json=_body(history), headers=auth)
    assert resp.status_code == 200
    warnings = " ".join(resp.json()["warnings"])
    assert "governance" in warnings.lower() or "D01" in warnings


def test_forecast_horizon_validation(client, auth, ml_history):
    assert (
        client.post(
            "/api/v1/ml/forecast", json={**_body(ml_history), "horizon_weeks": 0}, headers=auth
        ).status_code
        == 422
    )
    resp = client.post(
        "/api/v1/ml/forecast", json={**_body(ml_history), "horizon_weeks": 4}, headers=auth
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "OK"
    assert len(body["forecast_weekly_units"]) == 4
    assert body["forecast_total_units"] == body["forecast_weekly_units"][0] * 4


def test_reorder_requires_inventory_inputs(client, auth, ml_history):
    body = _body(ml_history)
    body.pop("on_hand_qty")
    resp = client.post("/api/v1/ml/reorder", json=body, headers=auth)
    assert resp.status_code == 200
    reorder = resp.json()["reorder"]
    assert reorder["status"] == "INSUFFICIENT_INPUTS"
    assert "on_hand_qty" in reorder["inputs_missing"]


def test_anomaly_and_movement(client, auth, ml_history):
    anomalies = client.post("/api/v1/ml/anomalies", json=_body(ml_history), headers=auth)
    assert anomalies.status_code == 200
    assert anomalies.json()["status"] == "OK"
    movement = client.post("/api/v1/ml/movement", json=_body(ml_history), headers=auth)
    assert movement.status_code == 200
    assert movement.json()["abc_xyz"] in {a + b for a in "ABC" for b in "XYZ"}


def test_invalid_date_rejected(client, auth, ml_history):
    resp = client.post("/api/v1/ml/dead-stock", json=_body(ml_history, as_of="not-a-date"), headers=auth)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"


def test_portfolio_runs_full_catalogue(client, auth):
    resp = client.post("/api/v1/ml/portfolio", json={"horizon_weeks": 2}, headers=auth)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["evaluated"] > 0
    assert body["failures"] == 0
    assert all(r["status"] == "OK" for r in body["results"])
    assert "synthetic" in body["syntheticHistoryNote"].lower()


def test_portfolio_filters_product_ids(client, auth):
    resp = client.post(
        "/api/v1/ml/portfolio", json={"horizon_weeks": 1, "product_ids": ["GRN-001"]}, headers=auth
    )
    assert resp.status_code == 200
    assert [r["productId"] for r in resp.json()["results"]] == ["GRN-001"]


def test_management_summary(client, auth):
    resp = client.get("/api/v1/ml/summary", headers=auth)
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


def test_retail_pricing(client, auth):
    resp = client.post(
        "/api/v1/retail/pricing/scenarios",
        json={"price": 10, "stock": 100, "daily_demand": 1, "cost": 6, "elasticity": -2},
        headers=auth,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "OK"
    assert "requires" in body["disclaimer"].lower() or "Recommendation" in body["disclaimer"]
    bad = client.post(
        "/api/v1/retail/pricing/scenarios",
        json={"price": 10, "stock": 1, "daily_demand": 1, "elasticity": 0.5},
        headers=auth,
    )
    assert bad.status_code == 422


def test_retail_bundles_and_insights(client, auth):
    missing = client.post("/api/v1/retail/bundles/recommendations", json={}, headers=auth)
    assert missing.status_code == 422
    bundle = client.post(
        "/api/v1/retail/bundles/recommendations",
        json={"product_id": "does-not-exist"},
        headers=auth,
    )
    assert bundle.status_code == 200
    assert bundle.json()["candidates"] == []
    insights = client.get("/api/v1/retail/insights", headers=auth)
    assert insights.status_code == 200
    assert insights.json()["status"] == "OK"


def test_retail_ledger_requires_events(client, auth):
    assert client.post("/api/v1/retail/inventory/balances", json={"events": []}, headers=auth).status_code == 422
    event = {
        "event_id": "e1",
        "product_id": "P1",
        "location": "MAIN",
        "ts": "2011-01-01",
        "type": "OPENING",
        "qty": 10,
        "unit_cost": 5,
    }
    resp = client.post("/api/v1/retail/inventory/balances", json={"events": [event]}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["balances"][0]["on_hand"] == 10
