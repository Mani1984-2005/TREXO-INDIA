import numpy as np, pandas as pd, pytest
from trexo.ml.data_pipeline.pipeline import tag_exclusions, normalise_types, exclusion_log, build_sales, is_non_product_code
from trexo.ml.features.product_features import build_features, FEATURE_COLUMNS
from trexo.ml.features.labels import inactivity_label, build_training_table
from trexo.ml.validation.splits import make_cutoffs, forward_chain_folds
from trexo.ml.config import HorizonConfig, ML_DATA_DIR


def raw(rows):
    return pd.DataFrame(rows, columns=["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"]).assign(SourceRow=lambda d: range(2, len(d) + 2))


def test_exclusion_rules_and_reconciliation():
    r = raw([("536365", "85123A", "X", 6, "2011-01-01", 2.5, 1, "UK"),
             ("C536379", "22423", "X", -1, "2011-01-02", 2.5, 1, "UK"),
             ("536381", "POST", "POSTAGE", 1, "2011-01-02", 18, 1, "UK"),
             ("536382", "gift_0001_10", "voucher", 1, "2011-01-02", 10, 1, "UK"),
             ("536383", "20725", "X", -5, "2011-01-03", 1, 1, "UK"),
             ("536384", "20725", "X", 5, "2011-01-03", 0, 1, "UK"),
             ("536385", "20725", "X", 5, None, 1, 1, "UK"),
             ("536386", "21000", "X", np.nan, "2011-01-03", 1, 1, "UK")])
    t = tag_exclusions(normalise_types(r))
    assert t["ExclusionReason"].tolist() == ["", "CANCELLATION_INVOICE", "NON_PRODUCT_CODE", "NON_PRODUCT_CODE",
                                             "NON_POSITIVE_QUANTITY", "ZERO_PRICE", "MISSING_DATE", "MISSING_QUANTITY_OR_PRICE"]
    assert exclusion_log(t)["Rows"].sum() == len(r)         # no silent loss
    assert len(build_sales(t)) == 1


def test_non_product_code_case_insensitive_prefix_only():
    s = pd.Series(["GIFT_0001_10", "gift_0001_20", "DCGS0003", "85123A", "m", "M", "15056bl"])
    assert is_non_product_code(s).tolist() == [True, True, True, False, True, True, False]


def test_features_no_future_leakage(sales):
    cutoff = pd.Timestamp("2011-04-01")
    f1 = build_features(sales, cutoff)
    future = sales.copy()
    extra = sales[sales["Date"] > cutoff].copy(); extra["Quantity"] *= 1000
    f2 = build_features(pd.concat([sales[sales["Date"] <= cutoff], extra]), cutoff)
    pd.testing.assert_frame_equal(f1.reset_index(drop=True), f2.reset_index(drop=True))


def test_edge_products(sales):
    f = build_features(sales, "2011-07-01").set_index("StockCode")
    assert f.loc["B", "n_invoices"] == 1 and f.loc["B", "gap_cv"] == 0      # single transaction: defined, not NaN
    assert not f[FEATURE_COLUMNS].isna().any().any()
    assert f.loc["C", "days_since_last_sale"] > f.loc["A", "days_since_last_sale"]
    assert f.loc["B", "missing_customer_share"] == 1.0                       # missing customer id handled
    assert "ZZZ" not in f.index                                              # product with no sales gets no features


def test_label_uses_only_future_window(sales):
    lab = inactivity_label(sales, ["A", "C"], "2011-04-01", 60).set_index("StockCode")
    assert lab.loc["A", "y_inactive"] == 0 and lab.loc["C", "y_inactive"] == 1


def test_splits_are_purged():
    c = make_cutoffs("2010-12-01")
    H = pd.Timedelta(days=60)
    assert c["train"][-1] + H <= c["val"] and c["val"] + H <= c["test"]
    for tr, v in forward_chain_folds(c["train"], 60):
        assert all(t + H <= v for t in tr)


def test_unsorted_dates_and_missing_dates_input_order_invariant(sales):
    a = build_features(sales, "2011-06-01").reset_index(drop=True)
    b = build_features(sales.sample(frac=1, random_state=1), "2011-06-01").reset_index(drop=True)
    pd.testing.assert_frame_equal(a.sort_values("StockCode").reset_index(drop=True), b.sort_values("StockCode").reset_index(drop=True))


@pytest.mark.skipif(not (ML_DATA_DIR / "data_manifest_v1.json").exists(), reason="pipeline not run")
def test_real_data_reconciles_to_audited_policy_count():
    import json
    m = json.loads((ML_DATA_DIR / "data_manifest_v1.json").read_text())
    assert m["raw_rows"] == 541909 and m["valid_sale_rows"] == 527725   # == CUSTOMER_SALE in TRANSACTION_CLASSIFICATION_POLICY_V1
    assert sum(m["exclusion_log"].values()) == 541909
