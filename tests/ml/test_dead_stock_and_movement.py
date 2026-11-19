import numpy as np, pandas as pd, pytest
from trexo.ml.config import ClassificationThresholds
from trexo.ml.dead_stock.classifier import classify_score, classify_products, CLASSES, evidence_quality
from trexo.ml.movement.movement import abc_class, xyz_class
from trexo.ml.features.product_features import build_features
from trexo.ml.registry.registry import latest_version

T = ClassificationThresholds()
CURVE = (np.array([0, 30, 60, 120, 400.0]), np.array([0.02, 0.2, 0.5, 0.9, 1.0]), {"train_max_recency_days": 300})


def test_class_boundaries_monotone():
    scores = [0.0, 0.2, 0.3, 0.5, 0.7, 0.9]
    out = [classify_score(s, T) for s in scores]
    assert out == [CLASSES[0], CLASSES[0], CLASSES[1], CLASSES[2], CLASSES[3], CLASSES[4]]


def test_confirmed_dead_stock_requires_stock_data(sales):
    f = build_features(sales, "2011-07-20"); d = pd.DataFrame({"StockCode": f["StockCode"], "Description": "x"})
    c = classify_products(f, sales, d, curve=CURVE, thresholds=T)
    assert (c["classification"] != CLASSES[5]).all()                         # never from sales alone
    assert (c["status_type"] == "DEMAND_INACTIVITY_INDICATOR_ONLY").all()
    crit = c[c["classification"] == CLASSES[4]]["StockCode"].tolist()
    assert crit, "fixture must contain a critical-risk product"
    oh = pd.DataFrame({"StockCode": crit, "on_hand_qty": [10.0] * len(crit)})
    c2 = classify_products(f, sales, d, on_hand=oh, curve=CURVE, thresholds=T)
    assert (c2.set_index("StockCode").loc[[x for x in crit if c2.set_index('StockCode').loc[x, 'evidence_quality'] != 'LOW'], "classification"] == CLASSES[5]).all()
    oh0 = pd.DataFrame({"StockCode": crit, "on_hand_qty": [0.0] * len(crit)})
    assert (classify_products(f, sales, d, on_hand=oh0, curve=CURVE, thresholds=T)["classification"] != CLASSES[5]).all()


def test_insufficient_history_flagged_low_evidence(sales):
    f = build_features(sales, "2011-07-20"); c = classify_products(f, sales, pd.DataFrame({"StockCode": f["StockCode"], "Description": "x"}), curve=CURVE, thresholds=T).set_index("StockCode")
    assert c.loc["B", "evidence_quality"] == "LOW" and c.loc["B", "demand_pattern"] == "INSUFFICIENT_OBSERVATION_HISTORY"
    assert c.loc["A", "demand_pattern"] in ("CONTINUOUS_DEMAND", "INTERMITTENT_DEMAND")


def test_abc_xyz_thresholds():
    rev = pd.Series([700, 200, 50, 30, 20], index=list("abcde"))
    assert abc_class(rev, T).tolist() == ["A", "B", "C", "C", "C"]   # share-before-item: 0, .70, .90, .95, .98 vs cut-offs .70/.90
    assert xyz_class(pd.Series([0.2, 0.7, 1.5]), T).tolist() == ["X", "Y", "Z"]


def test_deployed_model_artifacts_exist_and_verified():
    v = latest_version("dead_stock")
    if v is None: pytest.skip("not trained")
    from trexo.ml.registry.registry import load_model_bundle
    objs, meta = load_model_bundle("dead_stock")
    assert meta["status"] == "TRAINED_AND_VERIFIED" and "rule_calibrator" in objs
