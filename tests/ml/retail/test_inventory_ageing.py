import numpy as np, pandas as pd, pytest
from trexo.ml.retail.inventory.ledger import process_ledger, reconcile, validate_events, incoming_po_by_product
from trexo.ml.retail.inventory.synthetic import synthetic_shop, LABEL
from trexo.ml.retail.ageing.engine import stock_age_table, classify_stock, selling_queue, AgeingConfig, ageing_distribution


def ev(rows):
    return pd.DataFrame(rows, columns=["event_id", "product_id", "location", "ts", "type", "qty", "unit_cost", "direction", "expiry_date"])


def base():
    return [("1", "A", "M", "2011-01-01", "OPENING", 10, 2.0, np.nan, None),
            ("2", "A", "M", "2011-02-01", "RECEIPT", 20, 3.0, np.nan, None),
            ("3", "A", "M", "2011-02-05", "SALE", 12, np.nan, np.nan, None)]


def test_balance_and_fifo_cost_layers():
    r = process_ledger(ev(base()))
    assert r.balances.iloc[0]["on_hand"] == 18
    lay = r.layers.sort_values("received_ts")
    assert lay["qty_remaining"].tolist() == [18] and lay["unit_cost"].tolist() == [3.0]   # sale consumed opening 10 + 2 of receipt
    c = r.consumption; assert c["qty"].sum() == 12 and set(c["unit_cost"]) == {2.0, 3.0}


def test_inventory_balance_identity():
    rows = base() + [("4", "A", "M", "2011-02-06", "DAMAGE", 3, np.nan, np.nan, None), ("5", "A", "M", "2011-02-07", "RETURN", 2, 3.0, np.nan, None),
                     ("6", "A", "M", "2011-02-08", "ADJUSTMENT", 1, np.nan, -1, None), ("7", "A", "M", "2011-02-09", "ADJUSTMENT", 4, np.nan, 1, None)]
    r = process_ledger(ev(rows)); a = r.accepted
    ins = a[a["type"].isin(["OPENING", "RECEIPT", "RETURN"])]["qty"].sum() + a[(a["type"] == "ADJUSTMENT") & (a["direction"] == 1)]["qty"].sum()
    outs = a[a["type"].isin(["SALE", "DAMAGE"])]["qty"].sum() + a[(a["type"] == "ADJUSTMENT") & (a["direction"] == -1)]["qty"].sum()
    assert r.balances["on_hand"].iloc[0] == ins - outs == r.layers["qty_remaining"].sum()


def test_negative_balance_rejected_not_silently_fixed():
    rows = base() + [("9", "A", "M", "2011-03-01", "SALE", 100, np.nan, np.nan, None)]
    r = process_ledger(ev(rows))
    assert r.balances["on_hand"].iloc[0] == 18 and r.rejected["reject_reason"].str.startswith("NEGATIVE_BALANCE").any()
    assert process_ledger(ev(rows), allow_negative=True).balances["on_hand"].iloc[0] == 0


def test_validation_rejections():
    rows = [("1", "A", "M", "2011-01-01", "OPENING", 5, 1.0, np.nan, None), ("1", "A", "M", "2011-01-01", "OPENING", 5, 1.0, np.nan, None),
            ("2", "A", "M", None, "RECEIPT", 5, 1.0, np.nan, None), ("3", "A", "M", "2011-01-01", "SALE", -2, np.nan, np.nan, None),
            ("4", "A", "M", "2011-01-01", "BOGUS", 2, np.nan, np.nan, None), ("5", "A", "M", "2011-01-01", "ADJUSTMENT", 2, np.nan, np.nan, None)]
    ok, bad = validate_events(ev(rows))
    assert len(ok) == 1 and set(bad["reject_reason"]) == {"DUPLICATE_EVENT_ID", "MISSING_OR_INVALID_DATE", "NON_POSITIVE_OR_MISSING_QTY", "UNKNOWN_EVENT_TYPE", "ADJUSTMENT_NEEDS_DIRECTION"}


def test_reservation_available_and_reconcile():
    rows = base() + [("r1", "A", "M", "2011-02-10", "RESERVE", 5, np.nan, np.nan, None), ("r2", "A", "M", "2011-02-11", "RESERVE", 50, np.nan, np.nan, None)]
    r = process_ledger(ev(rows)); b = r.balances.iloc[0]
    assert b["reserved"] == 5 and b["available"] == 13 and (r.rejected["reject_reason"] == "RESERVATION_EXCEEDS_STOCK").any()
    rec = reconcile(r.balances, pd.DataFrame({"product_id": ["A"], "location": ["M"], "reported_on_hand": [16.0]}))
    assert rec.iloc[0]["status"] == "DISCREPANCY" and rec.iloc[0]["difference"] == -2


def test_missing_cost_is_unknown_not_zero():
    rows = [("1", "A", "M", "2011-01-01", "OPENING", 10, np.nan, np.nan, None)]
    r = process_ledger(ev(rows)); t = stock_age_table(r.layers, "2011-03-01")
    assert pd.isna(t["capital_exposure"].iloc[0]) and t["cost_known_share"].iloc[0] == 0


def test_po_incoming():
    po = pd.DataFrame({"po_id": [1, 2, 3], "product_id": ["A", "A", "B"], "qty": [10, 5, 7], "expected_date": ["2011-03-01"] * 3, "status": ["OPEN", "RECEIVED", "OPEN"]})
    assert incoming_po_by_product(po, "2011-02-01").to_dict() == {"A": 10, "B": 7}


def test_synthetic_pipeline_end_to_end_and_label():
    e, prods, label = synthetic_shop(); assert label == "SYNTHETIC_FOR_TESTING_ONLY"
    r = process_ledger(e); assert r.rejected.empty or (r.rejected["reject_reason"].str.startswith("NEGATIVE")).all()
    as_of = pd.Timestamp("2011-06-30"); age = stock_age_table(r.layers, as_of)
    last = r.accepted[r.accepted["type"] == "SALE"].groupby("product_id")["ts"].max()
    vel = r.accepted[(r.accepted["type"] == "SALE") & (r.accepted["ts"] > as_of - pd.Timedelta(days=56))].groupby("product_id")["qty"].sum() / 56
    dem = pd.DataFrame({"product_id": age["product_id"], "forecast_daily": age["product_id"].map(vel).fillna(0), "risk_score": np.nan,
                        "days_since_last_sale": (as_of - age["product_id"].map(last)).dt.days})
    c = classify_stock(age, dem)
    assert "Confirmed Dead Stock" not in set(c["category"])            # needs demand-risk evidence
    q = selling_queue(c); assert (q["priority_points"].diff().dropna() <= 1e-12).all()
    fast = c.set_index("product_id").reindex(["P000", "P001", "P002"]).dropna(subset=["category"])   # sold-out products hold no stock -> absent
    assert fast["category"].isin(["Fresh Stock", "Normal Stock", "Ageing Stock"]).all()


def test_classification_rules():
    age = pd.DataFrame({"product_id": list("ABCDE"), "units_on_hand": [10, 500, 50, 80, 30], "weighted_age_days": [10, 40, 200, 70, 400],
                        "oldest_layer_age_days": [10, 40, 220, 80, 400], "capital_exposure": [20.0, 100, 200, 160, 60], "cost_known_share": [1.0] * 5,
                        "units_expiring_soon": [0, 0, 0, 0, 0], "min_days_to_expiry": [np.nan] * 5, "capital_exposure_known_part": [20.0, 100, 200, 160, 60]})
    dem = pd.DataFrame({"product_id": list("ABCDE"), "forecast_daily": [1.0, 1.0, 1.0, 1.0, 0.1], "risk_score": [0.05, 0.1, 0.1, 0.7, 0.9],
                        "days_since_last_sale": [1, 2, 3, 100, 150]})
    c = classify_stock(age, dem).set_index("product_id")["category"]
    assert c.to_dict() == {"A": "Fresh Stock", "B": "Slow-Moving Stock", "C": "Ageing Stock", "D": "At-Risk Stock", "E": "Confirmed Dead Stock"}
    assert set(ageing_distribution(pd.DataFrame({"received_ts": pd.to_datetime(["2011-01-01"]), "qty_remaining": [5.0]}), "2011-06-01")["units"]) <= {0.0, 5.0}
