"""Reproducible data pipeline: raw Excel -> validated product-demand tables.

Raw data is read-only. Excluded rows are logged by reason, never deleted from
the source and never silently dropped (exclusion log is written to reports/ml).
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
from ..config import (RAW_FILE, ML_DATA_DIR, REPORT_DIR, NON_PRODUCT_CODES,
                      NON_PRODUCT_PREFIXES, PIPELINE_VERSION, D01_EXCLUSION_REASON,
                      D01_BAD_DEBT_INVOICES, D01_EVENT_GROUP, D01_DECISION, D01_REASON)

RAW_COLUMNS = ["InvoiceNo", "StockCode", "Description", "Quantity",
               "InvoiceDate", "UnitPrice", "CustomerID", "Country"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_raw(path: Path = RAW_FILE) -> pd.DataFrame:
    df = pd.read_excel(path, dtype={"InvoiceNo": str, "StockCode": str})
    missing = set(RAW_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"raw file missing columns: {sorted(missing)}")
    df = df[RAW_COLUMNS].copy()
    df["SourceRow"] = np.arange(2, len(df) + 2)  # Excel row (header = row 1)
    return df


def normalise_types(df: pd.DataFrame) -> pd.DataFrame:
    """Project convention: StockCode/InvoiceNo cast to str + strip. No case folding
    (case-folding is a proposal that has not been approved)."""
    out = df.copy()
    out["InvoiceNo"] = out["InvoiceNo"].astype(str).str.strip()
    out["StockCode"] = out["StockCode"].astype(str).str.strip()
    out["Quantity"] = pd.to_numeric(out["Quantity"], errors="coerce")
    out["UnitPrice"] = pd.to_numeric(out["UnitPrice"], errors="coerce")
    out["InvoiceDate"] = pd.to_datetime(out["InvoiceDate"], errors="coerce")
    return out


def is_non_product_code(code: pd.Series) -> pd.Series:
    # prefix match is case-insensitive (lower-case gift_0001_* rows exist; policy rule 10);
    # this is exclusion matching only - product keys are NOT case-folded.
    return code.isin(NON_PRODUCT_CODES) | code.str.upper().str.startswith(NON_PRODUCT_PREFIXES)


def d01_mask(df: pd.DataFrame) -> pd.Series:
    """True for the approved D01 bad-debt invoice group (invoice-level match)."""
    return df["InvoiceNo"].astype(str).str.strip().isin(D01_BAD_DEBT_INVOICES)


def tag_exclusions(df: pd.DataFrame) -> pd.DataFrame:
    """Add ExclusionReason (first-match, '' when the row is a valid product sale).

    D01_BAD_DEBT_GROUP is deliberately the FIRST rule: the approved governance
    decision is about the whole invoice group, not about StockCode B, and must
    override every generic transaction rule for those source rows.

    Valid sale = V2 definition (non-C invoice, Quantity>0, UnitPrice>0) AND an
    ordinary product code (policy category CUSTOMER_SALE)."""
    out = df.copy()
    reason = pd.Series("", index=out.index, dtype=object)
    rules = [
        (D01_EXCLUSION_REASON, d01_mask(out)),
        ("MISSING_DATE", out["InvoiceDate"].isna()),
        ("MISSING_QUANTITY_OR_PRICE", out["Quantity"].isna() | out["UnitPrice"].isna()),
        ("NON_PRODUCT_CODE", is_non_product_code(out["StockCode"])),
        ("CANCELLATION_INVOICE", out["InvoiceNo"].str.startswith("C")),
        ("NON_POSITIVE_QUANTITY", out["Quantity"] <= 0),
        ("NEGATIVE_PRICE", out["UnitPrice"] < 0),
        ("ZERO_PRICE", out["UnitPrice"] == 0),
    ]
    for name, mask in rules:
        reason = reason.mask((reason == "") & mask.fillna(False), name)
    out["ExclusionReason"] = reason
    out["IsValidSale"] = reason == ""
    out["IsExactDuplicate"] = out.duplicated(
        subset=["InvoiceNo", "StockCode", "Description", "Quantity",
                "InvoiceDate", "UnitPrice", "CustomerID", "Country"], keep="first")
    return out


def excluded_financial_events(tagged: pd.DataFrame) -> pd.DataFrame:
    """Auditable record of the D01 group. Original values are copied verbatim;
    this is a quarantine record, never a replacement for the raw workbook."""
    e = tagged.loc[tagged["ExclusionReason"] == D01_EXCLUSION_REASON].copy()
    e["LineValue"] = e["Quantity"] * e["UnitPrice"]
    e["GovernanceDecision"] = D01_DECISION
    e["EventGroup"] = D01_EVENT_GROUP
    e["ExclusionReason"] = D01_EXCLUSION_REASON
    e["ExclusionRationale"] = D01_REASON
    e["SourcePreserved"] = True
    cols = ["SourceRow", "InvoiceNo", "StockCode", "Description", "Quantity",
            "InvoiceDate", "UnitPrice", "LineValue", "CustomerID", "Country",
            "GovernanceDecision", "EventGroup", "ExclusionReason",
            "ExclusionRationale", "SourcePreserved"]
    return e[cols].sort_values("SourceRow").reset_index(drop=True)


def reconcile_d01(tagged: pd.DataFrame) -> dict:
    """Reconcile the D01 group against the original source rows (no assumptions)."""
    e = excluded_financial_events(tagged)
    per_invoice = []
    for inv in D01_BAD_DEBT_INVOICES:
        rows = e[e["InvoiceNo"] == inv]
        per_invoice.append({
            "invoice": inv,
            "found": bool(len(rows)),
            "source_rows": [int(x) for x in rows["SourceRow"]],
            "row_count": int(len(rows)),
            "quantity_sum": float(rows["Quantity"].sum()),
            "line_value_sum": float(rows["LineValue"].sum()),
            "stock_codes": sorted(set(rows["StockCode"].astype(str))),
            "descriptions": sorted(set(rows["Description"].dropna().astype(str))),
        })
    return {
        "decision": D01_DECISION,
        "reason_code": D01_EXCLUSION_REASON,
        "event_group": D01_EVENT_GROUP,
        "rationale": D01_REASON,
        "invoices": list(D01_BAD_DEBT_INVOICES),
        "row_count": int(len(e)),
        "source_rows": [int(x) for x in e["SourceRow"]],
        "quantity_sum": float(e["Quantity"].sum()),
        "gross_positive_line_value": float(e.loc[e["LineValue"] > 0, "LineValue"].sum()),
        "gross_negative_line_value": float(e.loc[e["LineValue"] < 0, "LineValue"].sum()),
        "net_line_value": float(e["LineValue"].sum()),
        "stock_codes": sorted(set(e["StockCode"].astype(str))),
        "excluded_from_valid_sales": bool(not e.empty),
        "preserved_file": "data/ml/excluded_financial_events_v1.csv",
        "per_invoice": per_invoice,
    }


def build_sales(tagged: pd.DataFrame) -> pd.DataFrame:
    s = tagged.loc[tagged["IsValidSale"]].copy()
    s["Date"] = s["InvoiceDate"].dt.normalize()
    s["LineValue"] = s["Quantity"] * s["UnitPrice"]
    return s[["SourceRow", "InvoiceNo", "StockCode", "Description", "Quantity", "UnitPrice",
              "LineValue", "InvoiceDate", "Date", "CustomerID", "Country", "IsExactDuplicate"]]


def exclusion_log(tagged: pd.DataFrame) -> pd.DataFrame:
    g = tagged.assign(Reason=tagged["ExclusionReason"].replace("", "VALID_SALE")).groupby("Reason")
    log = g.agg(Rows=("SourceRow", "count"), QuantitySum=("Quantity", "sum")).reset_index()
    assert log["Rows"].sum() == len(tagged), "exclusion log must reconcile to source rows"
    return log.sort_values("Rows", ascending=False)


def product_descriptions(tagged: pd.DataFrame) -> pd.DataFrame:
    """Most frequent non-null description per StockCode (valid-sale rows first)."""
    d = tagged.dropna(subset=["Description"])
    d = d.assign(Description=d["Description"].astype(str).str.strip())
    pick = lambda x: x.value_counts().index[0]
    mode = d[d["IsValidSale"]].groupby("StockCode")["Description"].agg(pick)
    fallback = d.groupby("StockCode")["Description"].agg(pick)
    return mode.combine_first(fallback).rename("Description").reset_index()


def run_pipeline(raw_path: Path = RAW_FILE, out_dir: Path = ML_DATA_DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    raw = load_raw(raw_path)
    tagged = tag_exclusions(normalise_types(raw))
    sales = build_sales(tagged)
    log = exclusion_log(tagged)
    desc = product_descriptions(tagged)
    d01 = reconcile_d01(tagged)
    events = excluded_financial_events(tagged)
    sales.to_csv(out_dir / "valid_sales_v1.csv.gz", index=False)
    desc.to_csv(out_dir / "product_descriptions_v1.csv", index=False)
    log.to_csv(REPORT_DIR / "ml_exclusion_log.csv", index=False)
    events.to_csv(out_dir / "excluded_financial_events_v1.csv", index=False)
    pd.DataFrame(d01["per_invoice"]).to_csv(REPORT_DIR / "d01_lineage_reconciliation.csv", index=False)
    no_sale = sorted(set(tagged["StockCode"]) - set(sales["StockCode"]))
    pd.DataFrame({"StockCode": no_sale}).to_csv(out_dir / "codes_without_valid_sales_v1.csv", index=False)
    manifest = {
        "pipeline_version": PIPELINE_VERSION,
        "raw_file": raw_path.name, "raw_sha256": sha256_file(raw_path),
        "raw_rows": int(len(raw)), "valid_sale_rows": int(len(sales)),
        "distinct_stock_codes_raw": int(tagged["StockCode"].nunique()),
        "distinct_products_with_valid_sales": int(sales["StockCode"].nunique()),
        "codes_without_valid_sales": len(no_sale),
        "date_min": str(sales["Date"].min().date()), "date_max": str(sales["Date"].max().date()),
        "exact_duplicate_valid_rows_kept": int(sales["IsExactDuplicate"].sum()),
        "exclusion_log": {k: int(v) for k, v in log.set_index("Reason")["Rows"].items()},
        "exclusion_rule_order": ["D01_BAD_DEBT_GROUP", "MISSING_DATE", "MISSING_QUANTITY_OR_PRICE",
                                 "NON_PRODUCT_CODE", "CANCELLATION_INVOICE",
                                 "NON_POSITIVE_QUANTITY", "NEGATIVE_PRICE", "ZERO_PRICE"],
        "governance_exclusions": {"D01_BAD_DEBT_GROUP": d01},
        "source_row_lineage": "Every valid-sale and D01-quarantine row keeps its Excel SourceRow.",
        "excluded_financial_events_file": "data/ml/excluded_financial_events_v1.csv",
        "excluded_financial_events_sha256": sha256_file(out_dir / "excluded_financial_events_v1.csv"),
    }
    (out_dir / "data_manifest_v1.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def load_sales(out_dir: Path = ML_DATA_DIR) -> pd.DataFrame:
    p = out_dir / "valid_sales_v1.csv.gz"
    if not p.exists():
        raise FileNotFoundError(f"{p} missing - run scripts/ml_prepare_data.py first")
    return pd.read_csv(p, dtype={"InvoiceNo": str, "StockCode": str},
                       parse_dates=["InvoiceDate", "Date"])


def load_excluded_financial_events(out_dir: Path = ML_DATA_DIR) -> pd.DataFrame:
    p = out_dir / "excluded_financial_events_v1.csv"
    if not p.exists():
        raise FileNotFoundError(f"{p} missing - run scripts/ml_prepare_data.py first")
    return pd.read_csv(p, dtype={"InvoiceNo": str, "StockCode": str}, parse_dates=["InvoiceDate"])
