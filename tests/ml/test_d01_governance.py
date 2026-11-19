"""D01 governance regression tests: source lineage, exclusion, preservation, downstream absence."""
import hashlib, json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from trexo.ml.config import (D01_BAD_DEBT_INVOICES, D01_EXCLUSION_REASON, ML_DATA_DIR,
                             RAW_FILE, REPORT_DIR)
from trexo.ml.data_pipeline.pipeline import (build_sales, exclusion_log,
                                             excluded_financial_events, load_raw,
                                             load_sales, normalise_types,
                                             reconcile_d01, tag_exclusions)
from trexo.ml.governance.d01 import build_corrected_movement


def raw(rows):
    return pd.DataFrame(rows, columns=["InvoiceNo", "StockCode", "Description", "Quantity",
                                       "InvoiceDate", "UnitPrice", "CustomerID", "Country"]
                        ).assign(SourceRow=lambda d: range(2, len(d) + 2))


def test_d01_is_first_match_and_preserved():
    r = raw([
        ("A563185", "B", "Adjust bad debt", 1, "2011-08-12", 11062.06, None, "UK"),
        ("A563186", "B", "Adjust bad debt", 1, "2011-08-12", -11062.06, None, "UK"),
        ("A563187", "B", "Adjust bad debt", 1, None, -11062.06, None, "UK"),  # D01 wins over MISSING_DATE
        ("536365", "B", "some other B row", 1, "2011-01-01", 10.0, 1, "UK"),  # defensive fallback, not D01
        ("536366", "85123A", "real product", 2, "2011-01-01", 2.5, 1, "UK"),
    ])
    t = tag_exclusions(normalise_types(r))
    assert t.loc[t.InvoiceNo.isin(D01_BAD_DEBT_INVOICES), "ExclusionReason"].tolist() == [D01_EXCLUSION_REASON] * 3
    assert t.loc[t.InvoiceNo == "536365", "ExclusionReason"].tolist() == ["NON_PRODUCT_CODE"]
    assert t.loc[t.InvoiceNo == "536366", "ExclusionReason"].tolist() == [""]
    assert len(build_sales(t)) == 1
    assert exclusion_log(t)["Rows"].sum() == len(r)

    e = excluded_financial_events(t)
    assert e["SourceRow"].tolist() == [2, 3, 4]
    assert e["LineValue"].sum() == -11062.06
    assert (e["SourcePreserved"]).all()
    rec = reconcile_d01(t)
    assert rec["row_count"] == 3 and rec["net_line_value"] == -11062.06


@pytest.fixture(scope="module")
def real():
    if not (ML_DATA_DIR / "valid_sales_v1.csv.gz").exists():
        pytest.skip("pipeline not run")
    return {
        "raw": load_raw(RAW_FILE),
        "sales": load_sales(),
        "manifest": json.loads((ML_DATA_DIR / "data_manifest_v1.json").read_text()),
    }


def test_real_source_rows_and_reconciliation(real):
    raw = real["raw"]
    m = raw[raw["InvoiceNo"].isin(D01_BAD_DEBT_INVOICES)]
    assert len(m) == 3
    assert m["SourceRow"].tolist() == [299984, 299985, 299986]
    assert m["Quantity"].tolist() == [1, 1, 1]
    assert m["UnitPrice"].tolist() == [11062.06, -11062.06, -11062.06]
    assert float((m["Quantity"] * m["UnitPrice"]).sum()) == -11062.06
    b = raw[raw["StockCode"] == "B"]
    assert len(b) == 3 and set(b["InvoiceNo"]) == set(D01_BAD_DEBT_INVOICES)


def test_real_d01_absent_from_all_ml_training_inputs(real):
    s = real["sales"]
    assert int(s["InvoiceNo"].isin(D01_BAD_DEBT_INVOICES).sum()) == 0
    assert int((s["StockCode"] == "B").sum()) == 0
    m = real["manifest"]
    d01 = m["governance_exclusions"][D01_EXCLUSION_REASON]
    assert d01["row_count"] == 3
    assert d01["source_rows"] == [299984, 299985, 299986]
    assert d01["net_line_value"] == -11062.06
    assert m["exclusion_log"][D01_EXCLUSION_REASON] == 3
    assert m["exclusion_log"]["NON_PRODUCT_CODE"] == 2992   # 2995 - 3 D01 rows
    assert sum(m["exclusion_log"].values()) == m["raw_rows"] == 541909
    assert m["valid_sale_rows"] == 527725
    assert m["pipeline_version"] == "ml-1.1.0"
    assert m["raw_sha256"] == hashlib.sha256(RAW_FILE.read_bytes()).hexdigest()

    events = pd.read_csv(ML_DATA_DIR / "excluded_financial_events_v1.csv", dtype={"InvoiceNo": str})
    assert events["InvoiceNo"].tolist() == list(D01_BAD_DEBT_INVOICES)
    assert events["LineValue"].sum() == -11062.06
    assert events["SourceRow"].tolist() == [299984, 299985, 299986]


def test_real_d01_absent_from_downstream_reports(real):
    for name, col in (("product_movement_classification.csv", "StockCode"),
                      ("dead_stock_classification.csv", "StockCode"),
                      ("dead_stock_intervention_queue.csv", "StockCode"),
                      ("forecast_next_8_weeks.csv", "StockCode")):
        p = REPORT_DIR / name
        if not p.exists():
            continue
        d = pd.read_csv(p, usecols=[col], dtype=str)
        assert not d[col].eq("B").any(), f"{name} contains D01 StockCode B"
    bt = ML_DATA_DIR / "forecast_backtest_rows.csv.gz"
    if bt.exists():
        d = pd.read_csv(bt, usecols=["StockCode"], dtype={"StockCode": str})
        assert not d["StockCode"].eq("B").any()


def test_corrected_movement_is_clean_and_reconciles(real):
    v1, v2, monthly = build_corrected_movement(real["sales"])
    assert "B" not in set(v1["StockCode"]) and "B" not in set(v2["StockCode"])
    assert "B" not in set(monthly["StockCode"])
    assert len(v1) == len(v2) == real["sales"]["StockCode"].nunique() == 3900
    assert abs(v1["TotalQuantitySold"].sum() - real["sales"]["Quantity"].sum()) < 1e-6
    assert abs(v1["TotalSalesValue"].sum() - real["sales"]["LineValue"].sum()) < 1e-6
    assert abs(monthly["MonthlyQuantity"].sum() - real["sales"]["Quantity"].sum()) < 1e-6


def test_processed_stage_artifacts_are_flagged_not_consumed(real):
    audit = json.loads((REPORT_DIR / "d01_lineage_audit.json").read_text())
    assert audit["source_verification"]["source_reconciliation_ok"] is True
    assert audit["source_verification"]["stockcode_B_exclusively_d01"] is True
    assert audit["ml_dataset_presence"]["d01_rows_in_valid_sales"] == 0
    assert audit["corrected_movement_clean"] is True
    statuses = {p["artifact"]: p for p in audit["processed_stage_artifacts"]}
    for f in ("data/processed/product_movement_v1.csv",
              "data/processed/product_movement_v2.csv",
              "data/processed/product_monthly_sales_v2.csv"):
        assert statuses[f]["contains_stockcode_B"] is True
        assert statuses[f]["status"] == "PROTECTED_HISTORICAL_ARTIFACT_NOT_CONSUMED_BY_ML"
