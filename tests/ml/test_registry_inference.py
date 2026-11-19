import json, numpy as np, pytest
from trexo.ml.registry.registry import save_model_bundle, load_model_bundle
from trexo.ml.inference.service import InferenceService, InvalidRequestError, validate_request, ModelUnavailableError
from trexo.ml.config import MODEL_DIR


def test_registry_roundtrip_and_tamper_detection(tmp_path):
    from sklearn.linear_model import LogisticRegression
    m = LogisticRegression().fit(np.array([[0], [1], [2], [3]]), [0, 0, 1, 1])
    info = save_model_bundle("toy", {"estimator": m}, {"note": "t"}, root=tmp_path)
    objs, meta = load_model_bundle("toy", root=tmp_path)
    assert meta["status"] == "TRAINED_AND_VERIFIED" and objs["estimator"].predict([[3]])[0] == 1
    (tmp_path / "toy" / info["model_version"] / "estimator.joblib").write_bytes(b"tampered")
    with pytest.raises(RuntimeError): load_model_bundle("toy", root=tmp_path)
    with pytest.raises(FileNotFoundError): load_model_bundle("absent", root=tmp_path)


def test_validate_request_edge_cases():
    with pytest.raises(InvalidRequestError): validate_request({"product_id": "", "sales_history": []})
    with pytest.raises(InvalidRequestError): validate_request({"product_id": "A", "sales_history": "x"})
    s, w, _ = validate_request({"product_id": "A", "sales_history": [
        {"date": "2011-01-01", "quantity": 5, "unit_price": 2}, {"date": None, "quantity": 1, "unit_price": 1},
        {"date": "2011-01-02", "quantity": -3, "unit_price": 1}, {"date": "2011-01-03", "quantity": "x", "unit_price": 1},
        {"date": "2011-01-04", "quantity": 2, "unit_price": 0}, {"date": "2011-01-05", "quantity": 1, "unit_price": 1}], "as_of": "2011-01-04"})
    assert len(s) == 1 and len(w) >= 4          # exclusions are reported, future-dated record ignored


@pytest.fixture(scope="module")
def svc():
    try: return InferenceService()
    except ModelUnavailableError: pytest.skip("models not trained")


def _req(n=30, gap=4, qty=5, as_of="2011-06-01"):
    import pandas as pd
    d0 = pd.Timestamp(as_of) - pd.Timedelta(days=n * gap)
    return {"product_id": "T1", "as_of": as_of, "sales_history": [
        {"date": str((d0 + pd.Timedelta(days=i * gap)).date()), "quantity": qty, "unit_price": 2.0} for i in range(n)]}


def test_inference_fields_and_no_fabrication(svc):
    r = svc.dead_stock_detection(_req())
    for k in ("product_id", "model_version", "prediction_timestamp", "classification", "explanation", "recommended_action",
              "confidence", "missing_input_warnings", "supporting_metrics"): assert k in r
    assert r["classification"] in ("Healthy Moving Stock", "Normal Moving Stock") and 0 <= r["dead_stock_risk_score"] <= 1
    assert r["status_type"] == "DEMAND_INACTIVITY_INDICATOR_ONLY" and any("on_hand_qty" in w for w in r["missing_input_warnings"])
    none = svc.dead_stock_detection({"product_id": "Z", "sales_history": []})
    assert none["status"] == "NO_VALID_SALES" and none["prediction"] is None


def test_inference_confirmed_needs_stock_and_critical(svc):
    stale = _req(n=10, gap=5, as_of="2011-12-01")
    stale["as_of"] = "2011-12-09"
    r = svc.dead_stock_detection({**stale, "on_hand_qty": 40}); assert r["status_type"] == "STOCK_AND_DEMAND_EVIDENCE"
    with pytest.raises(InvalidRequestError): svc.dead_stock_detection({**stale, "on_hand_qty": -1})


def test_reorder_and_forecast_inference(svc):
    r = svc.reorder_recommendation(_req())
    assert r["reorder"]["status"] == "INSUFFICIENT_INPUTS" and r["reorder"]["recommended_order_qty"] is None
    r2 = svc.reorder_recommendation({**_req(), "on_hand_qty": 5, "lead_time_days": 7})
    assert r2["reorder"]["status"] == "CALCULATED" and r2["reorder"]["recommended_order_qty"] >= 0
    with pytest.raises(InvalidRequestError): svc.demand_forecast(_req(), horizon_weeks=20)


def test_movement_and_anomaly_inference(svc):
    m = svc.movement_classification(_req()); assert m["abc_xyz"][0] in "ABC" and m["speed_class"]
    a = svc.anomaly_detection({**_req(), "sales_history": _req()["sales_history"] + [{"date": "2011-05-30", "quantity": 5000, "unit_price": 2.0}]})
    assert a["prediction"]["n_flagged"] >= 1
