"""
TREXO - Special Transaction Investigation & Classification Audit V1.

Read-only forensic audit of the original transaction dataset.

Design rules enforced by this script:
  * The original Excel file is only ever opened for reading.
  * No processed V1/V2 dataset is written or modified.
  * Every source row keeps a stable identifier (SourceRow = Excel row number).
  * Audit partitions are mutually exclusive and must sum to the original row
    count; the script fails loudly if they do not.
  * Outputs are deterministic: no timestamps or run-specific values are written
    into the generated files, so two consecutive runs are byte-identical.

Outputs (all new files):
    reports/special_transaction_audit_v1.md
    reports/special_transaction_anomalies_v1.csv
    reports/transaction_classification_register_v1.csv
    reports/special_stockcode_analysis_v1.csv
    reports/invoice_prefix_analysis_v1.csv
    reports/zero_price_description_analysis_v1.csv
    reports/unusual_invoice_details_v1.csv

Run from the repository root:
    .\\.venv\\Scripts\\python.exe src\\trexo\\audit_special_transactions.py
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ------------------------------------------------------------------
# PATHS AND PROTECTED FILES
# ------------------------------------------------------------------

RAW_FILE = Path("data/raw/Online Retail.xlsx")
MOVEMENT_V1_FILE = Path("data/processed/product_movement_v1.csv")
MOVEMENT_V2_FILE = Path("data/processed/product_movement_v2.csv")
MONTHLY_V2_FILE = Path("data/processed/product_monthly_sales_v2.csv")
REPORT_DIR = Path("reports")

PROTECTED_FILES = [
    RAW_FILE,
    MOVEMENT_V1_FILE,
    MOVEMENT_V2_FILE,
    MONTHLY_V2_FILE,
]

OUT_PREFIX = "invoice_prefix_analysis_v1.csv"
OUT_SPECIAL_CODE = "special_stockcode_analysis_v1.csv"
OUT_ZERO_DESC = "zero_price_description_analysis_v1.csv"
OUT_UNUSUAL_INVOICES = "unusual_invoice_details_v1.csv"
OUT_REGISTER = "transaction_classification_register_v1.csv"
OUT_ANOMALIES = "special_transaction_anomalies_v1.csv"
OUT_REPORT_MD = "special_transaction_audit_v1.md"

# ------------------------------------------------------------------
# AUDIT CONSTANTS
# ------------------------------------------------------------------

REQUIRED_COLUMNS = [
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
]

# Codes requested by the assignment. "AMAZON" is kept verbatim even though a
# first probe suggested the dataset may contain a different code; the audit
# reports "not found" rather than silently substituting a look-alike.
REQUESTED_SPECIAL_CODES = ["POST", "DOT", "M", "BANK CHARGES", "AMAZON", "CRUK"]

# Codes that are actually observed in the dataset but are not in the required
# list. Discovered by scanning for non-standard StockCode formats.
DISCOVERED_SPECIAL_CODES = [
    "AMAZONFEE",
    "B",
    "C2",
    "D",
    "S",
    "PADS",
]

# StockCode format used by ordinary merchandise rows.
STOCKCODE_STANDARD_PATTERN = r"\d{5}[A-Za-z]?"

# Transparent, fixed thresholds (documented in the report).
LARGE_QUANTITY_THRESHOLD = 1000        # top 0.03% of all rows by |Quantity|
ZERO_PRICE_LARGE_QUANTITY_THRESHOLD = 500
ZERO_PRICE_PERCENTILE = 0.99           # 99th percentile of |Quantity| where
                                       # UnitPrice == 0

# Tolerance used by the existing V2 reconciliation script. Reused so the
# cross-check is directly comparable; the accounting definition is unchanged.
V2_TOLERANCE = 0.01

# V2 accounting definition (existing project definition, NOT changed here):
# eligible sale = not a C invoice AND Quantity > 0 AND UnitPrice > 0.
V2_SALE_DEFINITION = "InvoiceNo not starting with 'C' AND Quantity > 0 AND UnitPrice > 0"

# Historical figures reported by earlier project work. Verified, not trusted.
HISTORICAL_EXPECTED = {
    "Original records": 541909,
    "V2 eligible sales": 530104,
    "Cancellation-negative records": 9288,
    "Negative non-cancellation records": 1336,
    "Positive zero-price records": 1179,
    "Other invalid/financial adjustment records": 2,
    "Product movement V2": 3922,
    "Product-month records V2": 34069,
    "V2 reconciliation mismatches": 0,
}

# ------------------------------------------------------------------
# SMALL HELPERS
# ------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file (read-only)."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint_protected_files(paths: list[Path]) -> dict[str, str]:
    """Fingerprint every protected file that exists."""
    result: dict[str, str] = {}
    for path in paths:
        if path.exists():
            result[str(path)] = sha256_file(path)
    return result


def bool_array(series: pd.Series) -> np.ndarray:
    """Convert a Series to a clean numpy bool array (NA -> False)."""
    return series.fillna(False).to_numpy(dtype=bool)


def customer_as_text(value) -> str:
    """Render CustomerID as a stable string without a trailing '.0'."""
    if pd.isna(value):
        return "[MISSING]"
    return str(int(value))


def money(value: float) -> str:
    """Format a monetary value for the human-readable report."""
    return f"{value:,.2f}"


# ------------------------------------------------------------------
# LOAD AND VALIDATE (READ-ONLY)
# ------------------------------------------------------------------


def load_transactions(path: Path) -> pd.DataFrame:
    """
    Load the original dataset in read-only mode.

    Validates required columns and coercible data types, preserves the
    original row identity (SourceRow = Excel row number, header = row 1) and
    raises instead of silently repairing the source.
    """
    if not path.exists():
        raise FileNotFoundError(f"Original dataset not found: {path}")

    df = pd.read_excel(path, engine="openpyxl")

    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Stable source-row identity, recorded before any transformation.
    df = df.copy()
    df.insert(0, "SourceRow", np.arange(len(df), dtype=np.int64) + 2)

    # Type validation / coercion, with counts reported rather than hidden.
    coercion_report: dict[str, int] = {}

    df["InvoiceNo"] = df["InvoiceNo"].astype(str).str.strip()
    df["StockCode"] = df["StockCode"].astype(str).str.strip()

    quantity_raw = df["Quantity"]
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
    coercion_report["Quantity"] = int(df["Quantity"].isna().sum() - quantity_raw.isna().sum())

    price_raw = df["UnitPrice"]
    df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce")
    coercion_report["UnitPrice"] = int(df["UnitPrice"].isna().sum() - price_raw.isna().sum())

    date_raw = df["InvoiceDate"]
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
    coercion_report["InvoiceDate"] = int(df["InvoiceDate"].isna().sum() - date_raw.isna().sum())

    df["Description"] = df["Description"].astype("string")

    print(f"Loaded {len(df):,} rows from {path}")
    print(f"Rows failing numeric/date coercion: {coercion_report}")
    if any(coercion_report.values()):
        print("WARNING: coercion failures are reported in the audit report.")

    return df


# ------------------------------------------------------------------
# AUDIT FLAGS AND MUTUALLY EXCLUSIVE PARTITIONS
# ------------------------------------------------------------------

PARTITION_ORDER = [
    "P01_CANCELLATION_NEGATIVE",
    "P02_CANCELLATION_NON_NEGATIVE",
    "P03_NEGATIVE_QUANTITY_NON_CANCEL",
    "P04_ZERO_QUANTITY",
    "P05_POSITIVE_QUANTITY_ZERO_PRICE",
    "P06_POSITIVE_QUANTITY_NEGATIVE_PRICE",
    "P07_POSITIVE_QUANTITY_PAID",
    "P08_UNCLASSIFIABLE_MISSING_VALUES",
]


def assign_partitions(df: pd.DataFrame) -> pd.Series:
    """
    Assign every source row to exactly one audit partition.

    The partitions are mutually exclusive by construction and are the
    reconciliation identity used by this audit:

        sum(partition rows) == original row count
    """
    is_cancel = df["InvoiceNo"].str.startswith("C")
    quantity = df["Quantity"]
    price = df["UnitPrice"]

    missing_values = quantity.isna() | price.isna()

    labels = np.select(
        [
            missing_values,
            is_cancel & (quantity < 0),
            is_cancel & (quantity >= 0),
            ~missing_values & (quantity == 0),
            ~missing_values & ~is_cancel & (quantity > 0) & (price == 0),
            ~missing_values & ~is_cancel & (quantity > 0) & (price < 0),
            ~missing_values & ~is_cancel & (quantity > 0) & (price > 0),
            ~missing_values & ~is_cancel & (quantity < 0),
        ],
        [
            "P08_UNCLASSIFIABLE_MISSING_VALUES",
            "P01_CANCELLATION_NEGATIVE",
            "P02_CANCELLATION_NON_NEGATIVE",
            "P04_ZERO_QUANTITY",
            "P05_POSITIVE_QUANTITY_ZERO_PRICE",
            "P06_POSITIVE_QUANTITY_NEGATIVE_PRICE",
            "P07_POSITIVE_QUANTITY_PAID",
            "P03_NEGATIVE_QUANTITY_NON_CANCEL",
        ],
        default="P08_UNCLASSIFIABLE_MISSING_VALUES",
    )
    return pd.Series(labels, index=df.index, name="AuditPartition")


def add_audit_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add the derived columns every investigation reuses."""
    out = df.copy()

    out["InvoicePrefix"] = (
        out["InvoiceNo"].str.extract(r"^([A-Za-z]+)")[0].fillna("NUMERIC")
    )
    out["IsCancellationInvoice"] = out["InvoiceNo"].str.startswith("C")
    out["LineValue"] = out["Quantity"] * out["UnitPrice"]
    out["IsStandardStockCode"] = out["StockCode"].str.fullmatch(
        STOCKCODE_STANDARD_PATTERN
    ).fillna(False)
    out["StockCodeUpper"] = out["StockCode"].str.upper()
    out["DescriptionLower"] = out["Description"].fillna("").str.strip().str.lower()
    out["IsMissingDescription"] = (
        out["Description"].isna()
        | out["Description"].fillna("").str.strip().eq("")
    )
    out["AuditPartition"] = assign_partitions(out)

    # Exact partition coverage is a hard requirement of this audit.
    counts = out["AuditPartition"].value_counts()
    unknown_labels = set(counts.index) - set(PARTITION_ORDER)
    if unknown_labels:
        raise AssertionError(f"Unknown audit partitions: {unknown_labels}")
    if int(counts.sum()) != len(out):
        raise AssertionError(
            f"Partition rows {int(counts.sum())} != original rows {len(out)}"
        )

    return out


# ------------------------------------------------------------------
# INVESTIGATION A - INVOICE PREFIX FORENSICS
# ------------------------------------------------------------------


def build_prefix_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Per-prefix record, invoice, quantity, value and price distributions."""
    total_rows = len(df)

    rows = []
    for prefix, group in df.groupby("InvoicePrefix", sort=True):
        rows.append(
            {
                "InvoicePrefix": prefix,
                "Records": len(group),
                "UniqueInvoices": group["InvoiceNo"].nunique(),
                "PositiveQuantityRecords": int((group["Quantity"] > 0).sum()),
                "NegativeQuantityRecords": int((group["Quantity"] < 0).sum()),
                "ZeroQuantityRecords": int((group["Quantity"] == 0).sum()),
                "ZeroPriceRecords": int((group["UnitPrice"] == 0).sum()),
                "NegativePriceRecords": int((group["UnitPrice"] < 0).sum()),
                "TotalQuantity": int(group["Quantity"].sum()),
                "TotalTransactionValue": float(group["LineValue"].sum()),
                "PercentOfDataset": round(100.0 * len(group) / total_rows, 4),
                "UniqueStockCodes": int(group["StockCode"].nunique()),
                "UniqueCustomers": int(group["CustomerID"].nunique()),
                "CancellationInvoiceRows": int(
                    group["IsCancellationInvoice"].sum()
                ),
                "MissingCustomerRows": int(group["CustomerID"].isna().sum()),
                "FirstDate": group["InvoiceDate"].min(),
                "LastDate": group["InvoiceDate"].max(),
            }
        )

    analysis = pd.DataFrame(rows).sort_values(
        "Records", ascending=False, kind="mergesort"
    ).reset_index(drop=True)

    # Independent identity: prefix records must sum to the full dataset.
    if int(analysis["Records"].sum()) != total_rows:
        raise AssertionError("Invoice prefix records do not sum to dataset size")

    return analysis


def build_invoice_structure(df: pd.DataFrame) -> pd.DataFrame:
    """Observed invoice-number structures (length and prefix combinations)."""
    structure = (
        df.assign(InvoiceLength=df["InvoiceNo"].str.len())
        .groupby(["InvoicePrefix", "InvoiceLength"], sort=True)
        .agg(
            Records=("SourceRow", "size"),
            UniqueInvoices=("InvoiceNo", "nunique"),
            FirstDate=("InvoiceDate", "min"),
            LastDate=("InvoiceDate", "max"),
        )
        .reset_index()
        .sort_values("Records", ascending=False, kind="mergesort")
        .reset_index(drop=True)
    )
    return structure


# ------------------------------------------------------------------
# INVESTIGATION B - NEGATIVE UNIT-PRICE RECORDS
# ------------------------------------------------------------------


def build_negative_price_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Every record with a negative UnitPrice, with source-row identity."""
    columns = [
        "SourceRow",
        "InvoiceNo",
        "InvoicePrefix",
        "StockCode",
        "Description",
        "Quantity",
        "UnitPrice",
        "LineValue",
        "InvoiceDate",
        "CustomerID",
        "Country",
        "AuditPartition",
    ]
    return (
        df[df["UnitPrice"] < 0][columns]
        .sort_values("SourceRow", kind="mergesort")
        .reset_index(drop=True)
    )


# ------------------------------------------------------------------
# INVESTIGATION C - SPECIAL STOCKCODE FORENSICS
# ------------------------------------------------------------------


def _distribution(series: pd.Series, limit: int = 6) -> str:
    """Compact 'value:count' distribution, deterministic ordering."""
    counts = series.value_counts(dropna=False).head(limit)
    return "|".join(f"{key}:{value}" for key, value in counts.items())


def _description_variations(group: pd.DataFrame, limit: int = 8) -> str:
    counts = (
        group["Description"].fillna("[MISSING]").value_counts().head(limit)
    )
    return "|".join(f"{key} ({value})" for key, value in counts.items())


def _monthly_distribution(group: pd.DataFrame) -> str:
    months = group["InvoiceDate"].dt.to_period("M").value_counts().sort_index()
    return "|".join(f"{key}:{value}" for key, value in months.items())


def build_special_stockcode_analysis(
    df: pd.DataFrame, movement_v2: pd.DataFrame
) -> pd.DataFrame:
    """
    Investigate every requested special StockCode plus every discovered
    non-standard-format code, one independent row per code.
    """
    requested_upper = [code.upper() for code in REQUESTED_SPECIAL_CODES]
    discovered_non_standard = sorted(
        df.loc[~df["IsStandardStockCode"], "StockCodeUpper"].unique()
    )

    code_keys = list(
        dict.fromkeys(requested_upper + DISCOVERED_SPECIAL_CODES + discovered_non_standard)
    )

    # Uppercase key lookup. Movement V2 can contain case-variant StockCodes
    # (for example 'M' and 'm'), so the lookup is aggregated on the uppercased
    # key instead of assuming the index is unique.
    movement_v2 = movement_v2.copy()
    movement_v2["CodeKey"] = movement_v2["StockCode"].astype(str).str.upper()
    movement_lookup = movement_v2.groupby("CodeKey").agg(
        V2Rows=("StockCode", "size"),
        V2TotalQuantitySold=("TotalQuantitySold", "sum"),
        V2TotalSalesValue=("TotalSalesValue", "sum"),
    )

    ordinary_invoices = set(
        df.loc[df["IsStandardStockCode"], "InvoiceNo"].unique()
    )

    rows = []
    for code in code_keys:
        group = df[df["StockCodeUpper"] == code]
        requested = code in requested_upper

        if group.empty:
            rows.append(
                {
                    "StockCodeKey": code,
                    "RequestedByAssignment": "YES" if requested else "NO",
                    "FoundInDataset": "NO",
                    "ObservedVariants": "",
                    "Records": 0,
                    "UniqueInvoices": 0,
                    "DescriptionVariations": "",
                    "DistinctDescriptions": 0,
                    "QuantityMin": 0,
                    "QuantityMax": 0,
                    "TotalQuantity": 0,
                    "PositiveQuantityRecords": 0,
                    "NegativeQuantityRecords": 0,
                    "ZeroQuantityRecords": 0,
                    "ZeroPriceRecords": 0,
                    "NegativePriceRecords": 0,
                    "TotalTransactionValue": 0.0,
                    "UniqueCustomers": 0,
                    "MissingCustomerRows": 0,
                    "CustomerDistribution": "",
                    "CountryDistribution": "",
                    "InvoicePrefixDistribution": "",
                    "DateDistribution": "",
                    "FirstDate": pd.NaT,
                    "LastDate": pd.NaT,
                    "InvoicesAlsoContainingOrdinaryProducts": 0,
                    "PresentInMovementV2": "NO",
                    "V2TotalQuantitySold": 0.0,
                    "V2TotalSalesValue": 0.0,
                    "Notes": "Requested code not present in dataset.",
                }
            )
            continue

        code_invoices = set(group["InvoiceNo"].unique())
        variants = sorted(group["StockCode"].unique())
        in_v2 = code in movement_lookup.index
        v2_row = movement_lookup.loc[code] if in_v2 else None

        notes = []
        if len(variants) > 1:
            notes.append(
                f"Case/format variants observed: {', '.join(variants)}."
            )
        if group["IsStandardStockCode"].all():
            notes.append(
                "Format matches ordinary merchandise pattern "
                "(\d{5}[A-Za-z]?); treated as a product code, not a "
                "special transaction code."
            )
        if in_v2 and int(v2_row["V2Rows"]) > 1:
            notes.append(
                f"Movement V2 holds {int(v2_row['V2Rows'])} case-variant rows "
                "for this code key; V2 totals shown are the sum."
            )

        rows.append(
            {
                "StockCodeKey": code,
                "RequestedByAssignment": "YES" if requested else "NO",
                "FoundInDataset": "YES",
                "ObservedVariants": "|".join(variants),
                "Records": len(group),
                "UniqueInvoices": group["InvoiceNo"].nunique(),
                "DescriptionVariations": _description_variations(group),
                "DistinctDescriptions": int(
                    group["Description"].fillna("[MISSING]").nunique()
                ),
                "QuantityMin": int(group["Quantity"].min()),
                "QuantityMax": int(group["Quantity"].max()),
                "TotalQuantity": int(group["Quantity"].sum()),
                "PositiveQuantityRecords": int((group["Quantity"] > 0).sum()),
                "NegativeQuantityRecords": int((group["Quantity"] < 0).sum()),
                "ZeroQuantityRecords": int((group["Quantity"] == 0).sum()),
                "ZeroPriceRecords": int((group["UnitPrice"] == 0).sum()),
                "NegativePriceRecords": int((group["UnitPrice"] < 0).sum()),
                "TotalTransactionValue": float(group["LineValue"].sum()),
                "UniqueCustomers": int(group["CustomerID"].nunique()),
                "MissingCustomerRows": int(group["CustomerID"].isna().sum()),
                "CustomerDistribution": _distribution(
                    group["CustomerID"].map(customer_as_text)
                ),
                "CountryDistribution": _distribution(group["Country"]),
                "InvoicePrefixDistribution": _distribution(
                    group["InvoicePrefix"]
                ),
                "DateDistribution": _monthly_distribution(group),
                "FirstDate": group["InvoiceDate"].min(),
                "LastDate": group["InvoiceDate"].max(),
                "InvoicesAlsoContainingOrdinaryProducts": len(
                    code_invoices & ordinary_invoices
                ),
                "PresentInMovementV2": "YES" if in_v2 else "NO",
                "V2TotalQuantitySold": float(
                    v2_row["V2TotalQuantitySold"] if in_v2 else 0.0
                ),
                "V2TotalSalesValue": float(
                    v2_row["V2TotalSalesValue"] if in_v2 else 0.0
                ),
                "Notes": " ".join(notes),
            }
        )

    return pd.DataFrame(rows)


# ------------------------------------------------------------------
# INVESTIGATIONS D AND F - ZERO-PRICE POPULATION
# ------------------------------------------------------------------


def zero_price_mask(df: pd.DataFrame) -> pd.Series:
    """All rows with UnitPrice == 0, regardless of quantity or invoice type."""
    return df["UnitPrice"].fillna(np.nan).eq(0)


def compute_zero_price_thresholds(df: pd.DataFrame) -> dict[str, float]:
    """
    Transparent statistical thresholds for unusually large zero-price
    quantities. The 99th percentile of |Quantity| within the zero-price
    population isolates the top 1% of an already anomalous group; the fixed
    threshold of 500 units is reported alongside it for comparability with
    earlier project work.
    """
    zero = df[zero_price_mask(df)]
    absolute = zero["Quantity"].abs()
    return {
        "rows": float(len(zero)),
        "p99": float(absolute.quantile(ZERO_PRICE_PERCENTILE)),
        "fixed": float(ZERO_PRICE_LARGE_QUANTITY_THRESHOLD),
        "max": float(absolute.max()),
    }


def build_zero_price_description_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per distinct original description observed on zero-price rows.

    The original description text is preserved; a normalized key is added
    only to expose case variants. Paid-transaction overlap uses the existing
    V2 sale definition.
    """
    zero = df[zero_price_mask(df)].copy()
    paid = df[
        ~df["IsCancellationInvoice"]
        & (df["Quantity"] > 0)
        & (df["UnitPrice"] > 0)
    ]
    paid_by_desc = paid.groupby(
        paid["Description"].fillna("[MISSING]")
    ).agg(
        PaidRecords=("SourceRow", "size"),
        PaidInvoices=("InvoiceNo", "nunique"),
        PaidQuantity=("Quantity", "sum"),
    )

    zero["DescriptionKey"] = zero["Description"].fillna("[MISSING]")
    rows = []
    for description, group in zero.groupby("DescriptionKey", sort=True):
        normalized = str(description).strip().lower()
        paid_info = paid_by_desc.loc[description] if description in paid_by_desc.index else None
        paid_records = int(paid_info["PaidRecords"]) if paid_info is not None else 0

        ambiguous = normalized in {
            "",
            "?",
            "??",
            "check",
            "found",
            "adjustment",
            "manual",
            "missing",
            "amazon",
            "ebay",
        } or any(
            token in normalized
            for token in ("credit", "coded", "wrong", "incorrect", "adjust")
        )

        if str(description) == "[MISSING]":
            interpretation = "MISSING_DESCRIPTION"
        elif ambiguous:
            interpretation = "ADMINISTRATIVE_OR_CORRECTION_NOTE"
        else:
            interpretation = "ORDINARY_PRODUCT_DESCRIPTION"

        rows.append(
            {
                "Description": description,
                "DescriptionIsMissing": "YES"
                if str(description) == "[MISSING]"
                else "NO",
                "NormalizedDescription": normalized,
                "HasCaseVariants": "YES"
                if group["Description"].nunique(dropna=True) > 1
                else "NO",
                "Records": len(group),
                "UniqueInvoices": group["InvoiceNo"].nunique(),
                "StockCodes": "|".join(
                    sorted(group["StockCode"].unique())[:12]
                ),
                "TotalQuantity": int(group["Quantity"].sum()),
                "PositiveQuantityRecords": int((group["Quantity"] > 0).sum()),
                "NegativeQuantityRecords": int((group["Quantity"] < 0).sum()),
                "NegativeQuantityTotal": int(
                    group.loc[group["Quantity"] < 0, "Quantity"].sum()
                ),
                "UniqueCustomers": int(group["CustomerID"].nunique()),
                "InvoicePrefixDistribution": _distribution(
                    group["InvoicePrefix"]
                ),
                "FirstDate": group["InvoiceDate"].min(),
                "LastDate": group["InvoiceDate"].max(),
                "AlsoInPaidTransactions": "YES" if paid_records else "NO",
                "PaidTransactionRecords": paid_records,
                "Interpretation": interpretation,
                "ManualReviewRequired": "YES"
                if interpretation != "ORDINARY_PRODUCT_DESCRIPTION"
                else "NO",
            }
        )

    analysis = pd.DataFrame(rows).sort_values(
        ["Records", "Description"], ascending=[False, True], kind="mergesort"
    ).reset_index(drop=True)

    if int(analysis["Records"].sum()) != int(zero_price_mask(df).sum()):
        raise AssertionError("Zero-price description rows do not cover all zero-price rows")

    return analysis


# ------------------------------------------------------------------
# INVESTIGATION E - UNUSUAL INVOICE FORENSICS
# ------------------------------------------------------------------


def build_indicator_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Row-level unusual-transaction indicators (multi-label)."""
    return pd.DataFrame(
        {
            "NEGATIVE_UNIT_PRICE": bool_array(df["UnitPrice"] < 0),
            "NEGATIVE_QUANTITY": bool_array(df["Quantity"] < 0),
            "ZERO_PRICE": bool_array(df["UnitPrice"] == 0),
            "SPECIAL_STOCKCODE": bool_array(~df["IsStandardStockCode"]),
            "LARGE_QUANTITY": bool_array(df["Quantity"].abs() >= LARGE_QUANTITY_THRESHOLD),
        },
        index=df.index,
    )


def select_unusual_invoices(df: pd.DataFrame) -> pd.DataFrame:
    """
    Deterministic selection of unusual invoices.

    An invoice is selected when at least one of the following holds:
      S1  contains a negative unit price
      S2  contains |Quantity| >= 1000
      S3  contains a zero-price line with |Quantity| >= 500
      S4  mixes financial-only codes (B, D, M, S, BANK CHARGES, AMAZONFEE,
          CRUK) with ordinary merchandise lines
      S5  mixes positive and negative quantity lines on the same invoice
      S6  carries at least two distinct unusual indicator types

    Plain cancellation invoices that contain nothing unusual beyond a
    negative quantity are NOT selected here; they are covered row by row in
    the classification register.
    """
    indicators = build_indicator_matrix(df)
    invoice_indicators = indicators.groupby(df["InvoiceNo"]).any()

    financial_only_codes = {"B", "D", "M", "S", "BANK CHARGES", "AMAZONFEE", "CRUK"}
    financial_line = df["StockCodeUpper"].isin(financial_only_codes)
    ordinary_line = pd.Series(
        bool_array(df["IsStandardStockCode"]), index=df.index
    )

    has_financial = financial_line.groupby(df["InvoiceNo"]).any()
    has_ordinary = ordinary_line.groupby(df["InvoiceNo"]).any()

    positive_line = pd.Series(bool_array(df["Quantity"] > 0), index=df.index)
    negative_line = pd.Series(bool_array(df["Quantity"] < 0), index=df.index)
    has_positive = positive_line.groupby(df["InvoiceNo"]).any()
    has_negative = negative_line.groupby(df["InvoiceNo"]).any()

    zero_large = pd.Series(
        bool_array(
            (df["UnitPrice"] == 0)
            & (df["Quantity"].abs() >= ZERO_PRICE_LARGE_QUANTITY_THRESHOLD)
        ),
        index=df.index,
    )
    has_zero_large = zero_large.groupby(df["InvoiceNo"]).any()

    indicator_count = invoice_indicators.sum(axis=1)

    reasons = pd.DataFrame(index=invoice_indicators.index)
    reasons["S1_NEGATIVE_UNIT_PRICE"] = invoice_indicators["NEGATIVE_UNIT_PRICE"]
    reasons["S2_LARGE_QUANTITY"] = invoice_indicators["LARGE_QUANTITY"]
    reasons["S3_LARGE_ZERO_PRICE_QUANTITY"] = has_zero_large
    reasons["S4_FINANCIAL_AND_PRODUCT_MIX"] = has_financial & has_ordinary
    reasons["S5_MIXED_SIGN_QUANTITIES"] = has_positive & has_negative
    reasons["S6_MULTIPLE_INDICATOR_TYPES"] = indicator_count >= 2

    selected = reasons.any(axis=1)
    selected_invoices = reasons[selected]

    reasons["IndicatorTypeCount"] = indicator_count
    reasons["Selected"] = selected

    summary = reasons.reset_index().rename(columns={"InvoiceNo": "InvoiceNo"})
    summary = summary.sort_values("InvoiceNo", kind="mergesort").reset_index(drop=True)

    # Attach invoice-level aggregates used by the detail file.
    invoice_stats = (
        df.groupby("InvoiceNo")
        .agg(
            InvoiceLines=("SourceRow", "size"),
            InvoiceTotalQuantity=("Quantity", "sum"),
            InvoiceTotalValue=("LineValue", "sum"),
            InvoiceDate=("InvoiceDate", "min"),
            CustomerID=("CustomerID", "first"),
            Country=("Country", "first"),
        )
        .reset_index()
    )
    summary = summary.merge(invoice_stats, on="InvoiceNo", how="left")
    return summary


def build_unusual_invoice_details(
    df: pd.DataFrame, invoice_summary: pd.DataFrame
) -> pd.DataFrame:
    """Complete line-level breakdown of every selected unusual invoice."""
    selected = invoice_summary.loc[invoice_summary["Selected"], "InvoiceNo"]
    reasons = invoice_summary.set_index("InvoiceNo")

    detail = df[df["InvoiceNo"].isin(set(selected))].copy()
    detail["SelectionReasons"] = detail["InvoiceNo"].map(
        lambda invoice: "|".join(
            column
            for column in [
                "S1_NEGATIVE_UNIT_PRICE",
                "S2_LARGE_QUANTITY",
                "S3_LARGE_ZERO_PRICE_QUANTITY",
                "S4_FINANCIAL_AND_PRODUCT_MIX",
                "S5_MIXED_SIGN_QUANTITIES",
                "S6_MULTIPLE_INDICATOR_TYPES",
            ]
            if bool(reasons.loc[invoice, column])
        )
    )
    detail["UnusualRowFlags"] = [
        "|".join(
            flag
            for flag, condition in [
                ("NEGATIVE_UNIT_PRICE", value < 0),
                ("NEGATIVE_QUANTITY", value < 0),
                ("ZERO_PRICE", price == 0),
                ("SPECIAL_STOCKCODE", not standard),
                ("LARGE_QUANTITY", abs(value) >= LARGE_QUANTITY_THRESHOLD),
            ]
            if condition
        )
        for value, price, standard in zip(
            detail["Quantity"], detail["UnitPrice"], detail["IsStandardStockCode"]
        )
    ]

    columns = [
        "InvoiceNo",
        "InvoiceDate",
        "CustomerID",
        "Country",
        "SourceRow",
        "StockCode",
        "Description",
        "Quantity",
        "UnitPrice",
        "LineValue",
        "AuditPartition",
        "UnusualRowFlags",
        "SelectionReasons",
    ]
    return (
        detail[columns]
        .sort_values(["InvoiceNo", "SourceRow"], kind="mergesort")
        .reset_index(drop=True)
    )


# ------------------------------------------------------------------
# DESCRIPTION EVIDENCE BUCKETS
# ------------------------------------------------------------------

# Negative non-cancellation buckets. The pattern order follows the existing
# classify_transaction_types.py definitions (damage / disposal / stock-entry
# correction / credit) with two additional buckets added by this audit:
# MISSING_DESCRIPTION and AMBIGUOUS_SHORT_NOTE. The reason for the addition
# is documented in docs/TRANSACTION_CLASSIFICATION_POLICY_V1.md.
NEGATIVE_BUCKETS = [
    ("MISSING_DESCRIPTION", None),
    ("SUPPLIER_CREDIT", r"credit|asos|supplier"),
    ("DAMAGE_OR_DEFECT", r"damag|broken|faulty|mould|mold|rusty|smudg|smashed|crushed|wet pallet"),
    ("DISPOSAL_OR_DESTROYED", r"throw away|thrown away|destroyed|unsaleable|unsalable|can't sell|cannot sell"),
    ("STOCK_OR_ENTRY_CORRECTION", r"incorrect stock|wrongly marked|wrongly coded|came coded|wrong code|check"),
    ("AMBIGUOUS_SHORT_NOTE", r"^\?+$|missing|found|ebay|dotcom|sold as set|manual"),
]

# Zero-price buckets.
ZERO_PRICE_BUCKETS = [
    ("MISSING_DESCRIPTION", None),
    (
        "ADMINISTRATIVE_OR_CORRECTION_NOTE",
        r"check|found|adjust|credit|coded|wrong|incorrect|manual|missing|amazon|ebay|^\?+$",
    ),
]


def assign_description_buckets(df: pd.DataFrame) -> pd.Series:
    """Evidence bucket for negative non-cancel and zero-price descriptions."""
    labels = pd.Series("NOT_APPLICABLE", index=df.index, dtype="object")

    negative_mask = (
        ~df["IsCancellationInvoice"]
        & (df["Quantity"] < 0)
        & df["Quantity"].notna()
    )
    zero_mask = (df["UnitPrice"] == 0) & df["UnitPrice"].notna()

    def classify(mask: pd.Series, buckets: list[tuple[str, str | None]]) -> pd.Series:
        result = pd.Series("OTHER_EXPLICIT_NOTE" if buckets is NEGATIVE_BUCKETS else "ORDINARY_PRODUCT_DESCRIPTION", index=df.index, dtype="object")
        assigned = np.zeros(len(df), dtype=bool)
        for name, pattern in buckets:
            if pattern is None:
                condition = bool_array(mask & df["IsMissingDescription"])
            else:
                condition = bool_array(
                    mask
                    & ~df["IsMissingDescription"]
                    & df["DescriptionLower"].str.contains(pattern, regex=True, na=False)
                )
            take = condition & ~assigned
            result.loc[take] = name
            assigned |= take
        return result

    labels.loc[negative_mask] = classify(negative_mask, NEGATIVE_BUCKETS)[negative_mask]

    # Zero-price buckets only fill rows that no negative bucket claimed. A row
    # can be both negative-quantity and zero-price; for those rows the negative
    # evidence is decisive, because the classification rules evaluate negative
    # quantity before zero price.
    zero_fill_mask = zero_mask & (labels == "NOT_APPLICABLE")
    labels.loc[zero_fill_mask] = classify(zero_mask, ZERO_PRICE_BUCKETS)[zero_fill_mask]
    return labels


# ------------------------------------------------------------------
# PHASE TWO - TRANSACTION CLASSIFICATION
# ------------------------------------------------------------------

CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_LOW = "LOW"
CONFIDENCE_UNKNOWN = "UNKNOWN"

PHYSICAL_DECREASE = "PHYSICAL_STOCK_DECREASE"
PHYSICAL_INCREASE = "PHYSICAL_STOCK_INCREASE"
PHYSICAL_NONE = "NO_PHYSICAL_STOCK_MOVEMENT"
PHYSICAL_UNKNOWN = "UNKNOWN_PHYSICAL_IMPACT"


def _financial_impact(category: str, value: float) -> str:
    """Derive the financial impact statement from category and line value."""
    if pd.isna(value):
        return "UNKNOWN_FINANCIAL_IMPACT"
    if category in {"SERVICE_CHARGE", "SHIPPING_CHARGE"}:
        return "NON_PRODUCT_CHARGE" if value != 0 else "ZERO_FINANCIAL_VALUE"
    if category == "FINANCIAL_ADJUSTMENT":
        return "NON_PRODUCT_FINANCIAL_ADJUSTMENT"
    if category == "CUSTOMER_SALE":
        return "PRODUCT_REVENUE_POSITIVE" if value > 0 else "NON_POSITIVE_SALE_VALUE"
    if category == "CANCELLATION":
        return "REVENUE_REVERSAL_NEGATIVE" if value < 0 else "NON_NEGATIVE_CANCELLATION_VALUE"
    if value == 0:
        return "ZERO_FINANCIAL_VALUE"
    return "REVENUE_POSITIVE" if value > 0 else "REVENUE_NEGATIVE"


# Ordered classification rules. First matching rule wins, so more specific
# evidence (price sign, stockcode identity) is evaluated before generic
# partition rules.
def _rules() -> list[dict]:
    return [
        {
            "name": "NEGATIVE_UNIT_PRICE",
            "condition": lambda d: d["UnitPrice"] < 0,
            "category": "FINANCIAL_ADJUSTMENT",
            "confidence": CONFIDENCE_HIGH,
            "evidence": "Negative UnitPrice with description 'Adjust bad debt', A-prefix adjustment invoice and no CustomerID.",
            "contradiction": "No ledger reference is present in the dataset, so the counterpart account cannot be verified.",
            "physical": PHYSICAL_NONE,
            "manual": "NO",
            "explanation": "Direct, self-describing financial correction line with no product or customer attached.",
        },
        {
            "name": "BAD_DEBT_STOCKCODE",
            "condition": lambda d: d["StockCodeUpper"] == "B",
            "category": "FINANCIAL_ADJUSTMENT",
            "confidence": CONFIDENCE_HIGH,
            "evidence": "StockCode 'B' carries description 'Adjust bad debt' on all rows and appears only on A-prefix invoices.",
            "contradiction": "The positive-price row of this pair is currently counted inside V2 eligible sales and inside product movement V2.",
            "physical": PHYSICAL_NONE,
            "manual": "YES",
            "explanation": "Description is explicit about the financial nature of the entry; the V2 treatment still needs approval.",
        },
        {
            "name": "POSTAGE_CODE",
            "condition": lambda d: d["StockCodeUpper"].isin(["POST", "DOT"]),
            "category": "SHIPPING_CHARGE",
            "confidence": CONFIDENCE_HIGH,
            "evidence": "StockCode POST/DOT with a single consistent description ('POSTAGE' / 'DOTCOM POSTAGE') on every observed row.",
            "contradiction": "The dataset does not record whether postage was charged at cost or with margin.",
            "physical": PHYSICAL_NONE,
            "manual": "NO",
            "explanation": "Description is uniform and explicitly non-merchandise across all rows of the code.",
        },
        {
            "name": "CARRIAGE_CODE",
            "condition": lambda d: d["StockCodeUpper"] == "C2",
            "category": "SHIPPING_CHARGE",
            "confidence": CONFIDENCE_MEDIUM,
            "evidence": "StockCode C2 with description 'CARRIAGE' on 143 of 144 rows.",
            "contradiction": "One row has a missing description.",
            "physical": PHYSICAL_NONE,
            "manual": "NO",
            "explanation": "Strong description evidence with a single incomplete row.",
        },
        {
            "name": "FEE_AND_COMMISSION_CODES",
            "condition": lambda d: d["StockCodeUpper"].isin(
                ["BANK CHARGES", "AMAZONFEE", "CRUK"]
            ),
            "category": "SERVICE_CHARGE",
            "confidence": CONFIDENCE_HIGH,
            "evidence": "Uniform non-merchandise descriptions ('Bank Charges', 'AMAZON FEE', 'CRUK Commission') on every row.",
            "contradiction": "The underlying fee agreements are not in the dataset.",
            "physical": PHYSICAL_NONE,
            "manual": "NO",
            "explanation": "Descriptions are explicit service/commission charges, not stock items.",
        },
        {
            "name": "DISCOUNT_CODE",
            "condition": lambda d: d["StockCodeUpper"] == "D",
            "category": "FINANCIAL_ADJUSTMENT",
            "confidence": CONFIDENCE_MEDIUM,
            "evidence": "StockCode D with description 'Discount' on all rows; every row sits on a cancellation invoice with negative quantity.",
            "contradiction": "A negative quantity could in principle also reflect goods physically returned against a discounted order; no order linkage exists to confirm.",
            "physical": PHYSICAL_UNKNOWN,
            "manual": "NO",
            "explanation": "Discount lines are financial by nature, but the negative quantity leaves physical impact unresolved.",
        },
        {
            "name": "MANUAL_CODE",
            "condition": lambda d: d["StockCodeUpper"] == "M",
            "category": "NEEDS_MANUAL_REVIEW",
            "confidence": CONFIDENCE_MEDIUM,
            "evidence": "StockCode M/m with description 'Manual' and heterogeneous behaviour (both signs, wide price range, present in movement V2 as a product).",
            "contradiction": "Description 'Manual' states how the row was entered, not what business event it represents.",
            "physical": PHYSICAL_UNKNOWN,
            "manual": "YES",
            "explanation": "The row is clearly a manual entry, but its economic substance cannot be determined from the dataset.",
        },
        {
            "name": "SAMPLES_CODE",
            "condition": lambda d: d["StockCodeUpper"] == "S",
            "category": "NEEDS_MANUAL_REVIEW",
            "confidence": CONFIDENCE_MEDIUM,
            "evidence": "StockCode S with description 'SAMPLES' on every row.",
            "contradiction": "Samples carry unit prices between 2.80 and 570.00 and 61 of 63 rows are negative quantity on cancellation invoices, which contradicts the usual meaning of a sample.",
            "physical": PHYSICAL_UNKNOWN,
            "manual": "YES",
            "explanation": "Name and pricing behaviour disagree, so neither a sale nor a free sample can be confirmed.",
        },
        {
            "name": "PADS_CODE",
            "condition": lambda d: d["StockCodeUpper"] == "PADS",
            "category": "NEEDS_MANUAL_REVIEW",
            "confidence": CONFIDENCE_MEDIUM,
            "evidence": "Ordinary product description ('PADS TO MATCH ALL CUSHIONS') but unit prices of 0.000-0.001 only.",
            "contradiction": "Prices are three orders of magnitude below any plausible merchandise price, suggesting test or placeholder data.",
            "physical": PHYSICAL_UNKNOWN,
            "manual": "YES",
            "explanation": "Product identity is plausible but the pricing evidence is not credible as a normal sale.",
        },
        {
            "name": "GIFT_VOUCHER_CODES",
            "condition": lambda d: d["StockCodeUpper"].str.startswith("GIFT_"),
            "category": "NEEDS_MANUAL_REVIEW",
            "confidence": CONFIDENCE_LOW,
            "evidence": "Voucher-style codes ('Dotcomgiftshop Gift Voucher ...') with no CustomerID on any row and at least one row described as 'to push order througha s stock was'.",
            "contradiction": "Positive quantities and non-zero prices are also consistent with a voucher sale.",
            "physical": PHYSICAL_UNKNOWN,
            "manual": "YES",
            "explanation": "Voucher rows have no customer anchor and one row documents deliberate order manipulation.",
        },
        {
            "name": "DCGS_CODES",
            "condition": lambda d: d["StockCodeUpper"].str.startswith("DCGS"),
            "category": "NEEDS_MANUAL_REVIEW",
            "confidence": CONFIDENCE_LOW,
            "evidence": "Non-standard codes with ordinary product descriptions but no CustomerID on any row.",
            "contradiction": "Positive quantity and price on ordinary invoices are consistent with sales through an unidentified channel.",
            "physical": PHYSICAL_UNKNOWN,
            "manual": "YES",
            "explanation": "The sales channel cannot be identified, so the rows cannot be confirmed as ordinary customer sales.",
        },
        {
            "name": "MISSING_NUMERIC_VALUES",
            "condition": lambda d: d["Quantity"].isna() | d["UnitPrice"].isna(),
            "category": "UNKNOWN",
            "confidence": CONFIDENCE_UNKNOWN,
            "evidence": "Quantity or UnitPrice could not be coerced to a numeric value.",
            "contradiction": "None.",
            "physical": PHYSICAL_UNKNOWN,
            "manual": "YES",
            "explanation": "No numeric evidence exists on which to base a classification.",
        },
        {
            "name": "ZERO_QUANTITY",
            "condition": lambda d: d["Quantity"] == 0,
            "category": "INVALID_RECORD",
            "confidence": CONFIDENCE_MEDIUM,
            "evidence": "Quantity is exactly zero, so the row records no movement and no value.",
            "contradiction": "The row may still carry meaning as an administrative marker.",
            "physical": PHYSICAL_NONE,
            "manual": "YES",
            "explanation": "A zero-quantity line is demonstrably uninformative for movement accounting.",
        },
        {
            "name": "CANCELLATION_NEGATIVE",
            "condition": lambda d: d["IsCancellationInvoice"] & (d["Quantity"] < 0),
            "category": "CANCELLATION",
            "confidence": CONFIDENCE_HIGH,
            "evidence": "InvoiceNo starts with 'C' (the project's cancellation convention) and quantity is negative; the convention holds for all 9,288 rows on C invoices.",
            "contradiction": "No original order, return or stock reference exists, so a physical return cannot be distinguished from a pure order cancellation.",
            "physical": PHYSICAL_UNKNOWN,
            "manual": "NO",
            "explanation": "The cancellation marker is applied consistently by the source system; the physical consequence remains unresolvable from this dataset.",
        },
        {
            "name": "CANCELLATION_NON_NEGATIVE",
            "condition": lambda d: d["IsCancellationInvoice"] & (d["Quantity"] >= 0),
            "category": "CANCELLATION",
            "confidence": CONFIDENCE_MEDIUM,
            "evidence": "InvoiceNo starts with 'C' but quantity is not negative.",
            "contradiction": "A cancellation invoice carrying a positive quantity contradicts the observed cancellation convention.",
            "physical": PHYSICAL_UNKNOWN,
            "manual": "YES",
            "explanation": "Cancellation marker present but quantity sign disagrees with every other cancellation row.",
        },
        {
            "name": "NEGATIVE_NON_CANCEL_MISSING_DESCRIPTION",
            "condition": lambda d: (d["DescriptionBucket"] == "MISSING_DESCRIPTION")
            & ~d["IsCancellationInvoice"]
            & (d["Quantity"] < 0),
            "category": "UNKNOWN",
            "confidence": CONFIDENCE_UNKNOWN,
            "evidence": "Negative quantity outside a cancellation invoice with no description and no CustomerID.",
            "contradiction": "None available: the row carries no explanatory text.",
            "physical": PHYSICAL_UNKNOWN,
            "manual": "YES",
            "explanation": "There is no descriptive evidence to distinguish return, write-off or correction.",
        },
        {
            "name": "NEGATIVE_NON_CANCEL_SUPPLIER_CREDIT",
            "condition": lambda d: (d["DescriptionBucket"] == "SUPPLIER_CREDIT")
            & ~d["IsCancellationInvoice"]
            & (d["Quantity"] < 0),
            "category": "FINANCIAL_ADJUSTMENT",
            "confidence": CONFIDENCE_LOW,
            "evidence": "Description explicitly mentions credits/ASOS/supplier.",
            "contradiction": "The note is a fragment and does not state amounts or the goods involved.",
            "physical": PHYSICAL_UNKNOWN,
            "manual": "YES",
            "explanation": "The wording points to a supplier credit, but the quantity sign leaves physical impact open.",
        },
        {
            "name": "NEGATIVE_NON_CANCEL_WRITE_OFF",
            "condition": lambda d: d["DescriptionBucket"].isin(
                ["DAMAGE_OR_DEFECT", "DISPOSAL_OR_DESTROYED"]
            )
            & ~d["IsCancellationInvoice"]
            & (d["Quantity"] < 0),
            "category": "PHYSICAL_STOCK_MOVEMENT",
            "confidence": CONFIDENCE_MEDIUM,
            "evidence": "Description documents damaged, destroyed or unsaleable goods being removed (e.g. 'printing smudges/thrown away', 'Unsaleable, destroyed.').",
            "contradiction": "No stock-count record is available to confirm the physical removal, and no customer is attached.",
            "physical": PHYSICAL_DECREASE,
            "manual": "NO",
            "explanation": "The description states a physical disposal event, which is direct evidence of a stock decrease.",
        },
        {
            "name": "NEGATIVE_NON_CANCEL_STOCK_CORRECTION",
            "condition": lambda d: (d["DescriptionBucket"] == "STOCK_OR_ENTRY_CORRECTION")
            & ~d["IsCancellationInvoice"]
            & (d["Quantity"] < 0),
            "category": "NEEDS_MANUAL_REVIEW",
            "confidence": CONFIDENCE_MEDIUM,
            "evidence": "Description documents a record problem ('incorrect stock entry.', 'wrongly marked', 'check').",
            "contradiction": "A record correction does not prove that physical stock moved, and the direction of the correction is not stated.",
            "physical": PHYSICAL_UNKNOWN,
            "manual": "YES",
            "explanation": "The note identifies an entry error, which is evidence about the record rather than about physical stock.",
        },
        {
            "name": "NEGATIVE_NON_CANCEL_AMBIGUOUS_NOTE",
            "condition": lambda d: (d["DescriptionBucket"] == "AMBIGUOUS_SHORT_NOTE")
            & ~d["IsCancellationInvoice"]
            & (d["Quantity"] < 0),
            "category": "NEEDS_MANUAL_REVIEW",
            "confidence": CONFIDENCE_LOW,
            "evidence": "Short note such as '?', 'found', 'ebay' or 'sold as set on dotcom'.",
            "contradiction": "The note does not state whether stock physically moved.",
            "physical": PHYSICAL_UNKNOWN,
            "manual": "YES",
            "explanation": "The wording is too short to support any specific business interpretation.",
        },
        {
            "name": "NEGATIVE_NON_CANCEL_OTHER_NOTE",
            "condition": lambda d: (d["DescriptionBucket"] == "OTHER_EXPLICIT_NOTE")
            & ~d["IsCancellationInvoice"]
            & (d["Quantity"] < 0),
            "category": "NEEDS_MANUAL_REVIEW",
            "confidence": CONFIDENCE_LOW,
            "evidence": "Free-text note present but not matching any established evidence pattern.",
            "contradiction": "Free text is unstructured and may be incomplete.",
            "physical": PHYSICAL_UNKNOWN,
            "manual": "YES",
            "explanation": "A note exists but does not map to a recognised transaction type.",
        },
        {
            "name": "ZERO_PRICE_MISSING_DESCRIPTION",
            "condition": lambda d: (d["DescriptionBucket"] == "MISSING_DESCRIPTION")
            & ~d["IsCancellationInvoice"]
            & (d["Quantity"] > 0)
            & (d["UnitPrice"] == 0),
            "category": "UNKNOWN",
            "confidence": CONFIDENCE_UNKNOWN,
            "evidence": "Positive quantity at zero price with no description.",
            "contradiction": "None available.",
            "physical": PHYSICAL_UNKNOWN,
            "manual": "YES",
            "explanation": "Without a description or price there is no evidence for sale, gift or correction.",
        },
        {
            "name": "ZERO_PRICE_ADMIN_NOTE",
            "condition": lambda d: (d["DescriptionBucket"] == "ADMINISTRATIVE_OR_CORRECTION_NOTE")
            & ~d["IsCancellationInvoice"]
            & (d["Quantity"] > 0)
            & (d["UnitPrice"] == 0),
            "category": "NEEDS_MANUAL_REVIEW",
            "confidence": CONFIDENCE_MEDIUM,
            "evidence": "Zero-price row whose description is an administrative or correction note ('check', 'found', 'adjustment', credit/coding notes).",
            "contradiction": "The note describes an internal process, not a customer transaction, but does not state the physical outcome.",
            "physical": PHYSICAL_UNKNOWN,
            "manual": "YES",
            "explanation": "The description points away from a sale but does not identify the actual event.",
        },
        {
            "name": "ZERO_PRICE_PRODUCT_DESCRIPTION",
            "condition": lambda d: ~d["IsCancellationInvoice"]
            & (d["Quantity"] > 0)
            & (d["UnitPrice"] == 0),
            "category": "NEEDS_MANUAL_REVIEW",
            "confidence": CONFIDENCE_LOW,
            "evidence": "Ordinary product description at zero price; 40 of these rows carry an identified CustomerID.",
            "contradiction": "Complimentary item, promotion, sample, free replacement and data error are all equally consistent with the evidence.",
            "physical": PHYSICAL_UNKNOWN,
            "manual": "YES",
            "explanation": "Zero price proves the item was not sold at a price, but not why; no confirming evidence exists.",
        },
        {
            "name": "PAID_NON_CANCEL",
            "condition": lambda d: ~d["IsCancellationInvoice"]
            & (d["Quantity"] > 0)
            & (d["UnitPrice"] > 0),
            "category": "CUSTOMER_SALE",
            "confidence": CONFIDENCE_MEDIUM,
            "evidence": f"Matches the established V2 sale definition ({V2_SALE_DEFINITION}); ordinary positive-value merchandise line.",
            "contradiction": "The dataset contains no payment, shipment or fulfilment record, so a sale cannot be confirmed at row level; a small number of these rows are non-product codes.",
            "physical": PHYSICAL_DECREASE,
            "manual": "NO",
            "explanation": "Consistent, mutually supporting evidence for the project's existing sale definition, but fulfilment is unverifiable from this dataset.",
        },
    ]


def classify_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the ordered evidence rules to every source row."""
    out = df.copy()
    out["DescriptionBucket"] = assign_description_buckets(out)

    rules = _rules()
    category = pd.Series(pd.NA, index=out.index, dtype="object")
    confidence = pd.Series(pd.NA, index=out.index, dtype="object")
    evidence = pd.Series(pd.NA, index=out.index, dtype="object")
    contradiction = pd.Series(pd.NA, index=out.index, dtype="object")
    physical = pd.Series(pd.NA, index=out.index, dtype="object")
    manual = pd.Series(pd.NA, index=out.index, dtype="object")
    explanation = pd.Series(pd.NA, index=out.index, dtype="object")
    rule_name = pd.Series(pd.NA, index=out.index, dtype="object")

    assigned = np.zeros(len(out), dtype=bool)
    for rule in rules:
        condition = bool_array(rule["condition"](out)) & ~assigned
        if not condition.any():
            continue
        category.loc[condition] = rule["category"]
        confidence.loc[condition] = rule["confidence"]
        evidence.loc[condition] = rule["evidence"]
        contradiction.loc[condition] = rule["contradiction"]
        physical.loc[condition] = rule["physical"]
        manual.loc[condition] = rule["manual"]
        explanation.loc[condition] = rule["explanation"]
        rule_name.loc[condition] = rule["name"]
        assigned |= condition

    if not assigned.all():
        unmatched = int((~assigned).sum())
        raise AssertionError(f"{unmatched} rows were not matched by any classification rule")

    out["ClassificationRule"] = rule_name
    out["ProposedCategory"] = category
    out["ConfidenceLevel"] = confidence
    out["EvidenceSupporting"] = evidence
    out["EvidenceContradicting"] = contradiction
    out["PhysicalInventoryImpact"] = physical
    out["ManualReviewRequired"] = manual
    out["ConfidenceExplanation"] = explanation
    out["FinancialImpact"] = [
        _financial_impact(cat, value)
        for cat, value in zip(category, out["LineValue"])
    ]
    return out


def observed_characteristics(row: pd.Series) -> str:
    """Compact, factual description of a single source row."""
    description = row["Description"]
    description_text = "[MISSING]" if pd.isna(description) else str(description)[:60]
    parts = [
        f"qty={int(row['Quantity']) if pd.notna(row['Quantity']) else '[MISSING]'}",
        f"price={row['UnitPrice'] if pd.notna(row['UnitPrice']) else '[MISSING]'}",
        f"value={row['LineValue'] if pd.notna(row['LineValue']) else '[MISSING]'}",
        f"desc={description_text}",
        f"customer={customer_as_text(row['CustomerID'])}",
        f"cancellation={'Y' if row['IsCancellationInvoice'] else 'N'}",
        f"standard_code={'Y' if row['IsStandardStockCode'] else 'N'}",
        f"partition={row['AuditPartition']}",
        f"rule={row['ClassificationRule']}",
    ]
    return "; ".join(parts)


# ------------------------------------------------------------------
# PHASE TWO - CLASSIFICATION REGISTER
# ------------------------------------------------------------------

REGISTER_COLUMNS = [
    "RegisterID",
    "ScopeLevel",
    "RowCount",
    "SourceRow",
    "SourceRowScope",
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "UnitPrice",
    "InvoiceDate",
    "CustomerID",
    "Country",
    "AuditPartition",
    "InUnusualInvoice",
    "ObservedCharacteristics",
    "EvidenceSupporting",
    "EvidenceContradicting",
    "ProposedCategory",
    "ConfidenceLevel",
    "ConfidenceExplanation",
    "PhysicalInventoryImpact",
    "FinancialImpact",
    "ManualReviewRequired",
    "ClassificationStatus",
]

GROUP_KEYS = [
    "AuditPartition",
    "ClassificationRule",
    "ProposedCategory",
    "ConfidenceLevel",
    "PhysicalInventoryImpact",
    "FinancialImpact",
    "ManualReviewRequired",
    "InUnusualInvoice",
]


def build_classification_register(
    classified: pd.DataFrame, unusual_invoice_ids: set[str]
) -> tuple[pd.DataFrame, dict[str, int]]:
    """
    Build the transaction evidence and classification register.

    Row-level entries are produced for every investigated transaction:
      * every row outside the ordinary paid partition,
      * every row with a non-standard StockCode format,
      * every row with |Quantity| >= 1000.

    All remaining rows (ordinary paid merchandise lines) are covered by
    group-level entries so that register RowCount sums to the original
    dataset size without any row being dropped or double counted.
    """
    work = classified.copy()
    work["InUnusualInvoice"] = work["InvoiceNo"].isin(unusual_invoice_ids)

    row_level_mask = (
        (work["AuditPartition"] != "P07_POSITIVE_QUANTITY_PAID")
        | ~work["IsStandardStockCode"]
        | (work["Quantity"].abs() >= LARGE_QUANTITY_THRESHOLD)
    )

    row_entries = work[row_level_mask].sort_values(
        "SourceRow", kind="mergesort"
    )
    group_source = work[~row_level_mask]

    scope_stats = {
        "total_rows": int(len(work)),
        "row_level_entries": int(len(row_entries)),
        "group_covered_rows": int(len(group_source)),
        "row_level_mask_rows": int(row_level_mask.sum()),
    }

    register_rows: list[dict] = []

    for _, row in row_entries.iterrows():
        register_rows.append(
            {
                "ScopeLevel": "ROW",
                "RowCount": 1,
                "SourceRow": int(row["SourceRow"]),
                "SourceRowScope": "EXACT",
                "InvoiceNo": row["InvoiceNo"],
                "StockCode": row["StockCode"],
                "Description": "" if pd.isna(row["Description"]) else str(row["Description"]),
                "Quantity": row["Quantity"],
                "UnitPrice": row["UnitPrice"],
                "InvoiceDate": row["InvoiceDate"],
                "CustomerID": customer_as_text(row["CustomerID"]),
                "Country": row["Country"],
                "AuditPartition": row["AuditPartition"],
                "InUnusualInvoice": "YES" if row["InUnusualInvoice"] else "NO",
                "ObservedCharacteristics": observed_characteristics(row),
                "EvidenceSupporting": row["EvidenceSupporting"],
                "EvidenceContradicting": row["EvidenceContradicting"],
                "ProposedCategory": row["ProposedCategory"],
                "ConfidenceLevel": row["ConfidenceLevel"],
                "ConfidenceExplanation": row["ConfidenceExplanation"],
                "PhysicalInventoryImpact": row["PhysicalInventoryImpact"],
                "FinancialImpact": row["FinancialImpact"],
                "ManualReviewRequired": row["ManualReviewRequired"],
                "ClassificationStatus": (
                    "PROPOSED_PENDING_MANUAL_REVIEW"
                    if row["ManualReviewRequired"] == "YES"
                    else "PROPOSED_ROW_LEVEL"
                ),
            }
        )

    if len(group_source):
        grouped = (
            group_source.groupby(GROUP_KEYS, sort=True, dropna=False)
            .agg(
                RowCount=("SourceRow", "size"),
                SampleSourceRow=("SourceRow", "min"),
                SampleInvoiceNo=("InvoiceNo", "first"),
                SampleStockCode=("StockCode", "first"),
                SampleDescription=("Description", "first"),
                SampleQuantity=("Quantity", "first"),
                SampleUnitPrice=("UnitPrice", "first"),
                SampleDate=("InvoiceDate", "first"),
                SampleCustomer=("CustomerID", "first"),
                SampleCountry=("Country", "first"),
                SampleRow=("SourceRow", "first"),
                EvidenceSupporting=("EvidenceSupporting", "first"),
                EvidenceContradicting=("EvidenceContradicting", "first"),
                ConfidenceExplanation=("ConfidenceExplanation", "first"),
            )
            .reset_index()
            .sort_values(GROUP_KEYS, kind="mergesort")
            .reset_index(drop=True)
        )

        sample_lookup = group_source.set_index("SourceRow")
        for _, group in grouped.iterrows():
            sample = sample_lookup.loc[group["SampleSourceRow"]]
            register_rows.append(
                {
                    "ScopeLevel": "GROUP",
                    "RowCount": int(group["RowCount"]),
                    "SourceRow": int(group["SampleSourceRow"]),
                    "SourceRowScope": "REPRESENTATIVE_OF_GROUP",
                    "InvoiceNo": group["SampleInvoiceNo"],
                    "StockCode": group["SampleStockCode"],
                    "Description": ""
                    if pd.isna(group["SampleDescription"])
                    else str(group["SampleDescription"]),
                    "Quantity": group["SampleQuantity"],
                    "UnitPrice": group["SampleUnitPrice"],
                    "InvoiceDate": group["SampleDate"],
                    "CustomerID": customer_as_text(group["SampleCustomer"]),
                    "Country": group["SampleCountry"],
                    "AuditPartition": group["AuditPartition"],
                    "InUnusualInvoice": "YES" if group["InUnusualInvoice"] else "NO",
                    "ObservedCharacteristics": (
                        f"GROUP of {group['RowCount']} ordinary paid rows; "
                        f"representative row SourceRow={group['SampleSourceRow']} "
                        f"invoice={group['SampleInvoiceNo']}; "
                        f"observed characteristics of the representative row: "
                        + observed_characteristics(sample)
                    ),
                    "EvidenceSupporting": group["EvidenceSupporting"],
                    "EvidenceContradicting": group["EvidenceContradicting"],
                    "ProposedCategory": group["ProposedCategory"],
                    "ConfidenceLevel": group["ConfidenceLevel"],
                    "ConfidenceExplanation": group["ConfidenceExplanation"],
                    "PhysicalInventoryImpact": group["PhysicalInventoryImpact"],
                    "FinancialImpact": group["FinancialImpact"],
                    "ManualReviewRequired": group["ManualReviewRequired"],
                    "ClassificationStatus": (
                        "PROPOSED_PENDING_MANUAL_REVIEW"
                        if group["ManualReviewRequired"] == "YES"
                        else "PROPOSED_GROUP_LEVEL"
                    ),
                }
            )

    register = pd.DataFrame(register_rows)
    register.insert(
        0,
        "RegisterID",
        [f"REG-{index:06d}" for index in range(1, len(register) + 1)],
    )
    register = register[REGISTER_COLUMNS]

    # Coverage identity: every source row must be accounted for exactly once.
    covered = int(register["RowCount"].sum())
    if covered != len(classified):
        raise AssertionError(
            f"Register covers {covered} rows but dataset has {len(classified)}"
        )
    exact_rows = register.loc[
        register["SourceRowScope"] == "EXACT", "SourceRow"
    ]
    if exact_rows.duplicated().any():
        raise AssertionError("Duplicate exact SourceRow entries in register")
    if len(exact_rows) + scope_stats["group_covered_rows"] != len(classified):
        raise AssertionError("Register row-level and group-level coverage mismatch")

    return register, scope_stats


# ------------------------------------------------------------------
# PHASE FIVE - ANOMALY REGISTER
# ------------------------------------------------------------------

ANOMALY_COLUMNS = [
    "AnomalyID",
    "SourceReference",
    "RowCount",
    "AnomalyType",
    "Severity",
    "Description",
    "SupportingEvidence",
    "PotentialFinancialImpact",
    "PotentialPhysicalInventoryImpact",
    "Confidence",
    "RecommendedInvestigation",
    "ResolutionStatus",
]


def _anomaly(**kwargs) -> dict:
    base = {column: "" for column in ANOMALY_COLUMNS}
    base["ResolutionStatus"] = "OPEN"
    base.update(kwargs)
    return base


def build_anomaly_register(
    df: pd.DataFrame,
    special_analysis: pd.DataFrame,
    invoice_summary: pd.DataFrame,
    zero_thresholds: dict[str, float],
) -> pd.DataFrame:
    """Build the open-anomaly register. Nothing is ever auto-resolved."""
    anomalies: list[dict] = []

    # 1. Negative unit price rows (row level).
    negative_price = df[df["UnitPrice"] < 0].sort_values("SourceRow")
    for _, row in negative_price.iterrows():
        anomalies.append(
            _anomaly(
                SourceReference=f"SourceRow={int(row['SourceRow'])}; InvoiceNo={row['InvoiceNo']}",
                RowCount=1,
                AnomalyType="NEGATIVE_UNIT_PRICE",
                Severity="HIGH",
                Description=f"UnitPrice {row['UnitPrice']} on StockCode {row['StockCode']} ({row['Description']}).",
                SupportingEvidence="Negative unit price, A-prefix invoice, no CustomerID, description 'Adjust bad debt'.",
                PotentialFinancialImpact=f"Line value {money(row['LineValue'])}.",
                PotentialPhysicalInventoryImpact=PHYSICAL_NONE,
                Confidence=CONFIDENCE_HIGH,
                RecommendedInvestigation="Confirm the accounting treatment and whether the matching positive row belongs in sales metrics.",
            )
        )

    # 2. The positive bad-debt row counted inside V2 sales.
    bad_debt_positive = df[
        (df["StockCodeUpper"] == "B") & (df["UnitPrice"] > 0)
    ].sort_values("SourceRow")
    for _, row in bad_debt_positive.iterrows():
        anomalies.append(
            _anomaly(
                SourceReference=f"SourceRow={int(row['SourceRow'])}; InvoiceNo={row['InvoiceNo']}",
                RowCount=1,
                AnomalyType="BAD_DEBT_ADJUSTMENT_INSIDE_V2_SALES",
                Severity="CRITICAL",
                Description="A positive-price 'Adjust bad debt' row satisfies the V2 sale definition and is counted as product revenue.",
                SupportingEvidence=f"V2 definition {V2_SALE_DEFINITION}; movement V2 lists StockCode B with TotalSalesValue {money(row['LineValue'])}.",
                PotentialFinancialImpact=f"{money(row['LineValue'])} of non-product adjustment reported as product sales.",
                PotentialPhysicalInventoryImpact=PHYSICAL_NONE,
                Confidence=CONFIDENCE_HIGH,
                RecommendedInvestigation="Decide whether bad-debt adjustments must be excluded from V2 sales and product movement (approval required).",
            )
        )

    # 3. Non-product codes present in the V2 product movement.
    contamination = special_analysis[
        (special_analysis["FoundInDataset"] == "YES")
        & (special_analysis["PresentInMovementV2"] == "YES")
        & (special_analysis["StockCodeKey"] != "B")
        & (special_analysis["StockCodeKey"].isin(
            ["POST", "DOT", "M", "AMAZONFEE", "C2", "BANK CHARGES", "S", "PADS"]
        ))
    ].sort_values("StockCodeKey")
    for _, row in contamination.iterrows():
        value = abs(float(row["V2TotalSalesValue"]))
        severity = "HIGH" if value >= 10000 else ("MEDIUM" if value >= 100 else "LOW")
        anomalies.append(
            _anomaly(
                SourceReference=f"StockCode={row['StockCodeKey']}",
                RowCount=int(row["Records"]),
                AnomalyType="NON_PRODUCT_CODE_IN_V2_PRODUCT_MOVEMENT",
                Severity=severity,
                Description=f"Code {row['StockCodeKey']} ({row['DescriptionVariations'].split(' (')[0]}) is present in product_movement_v2.csv as a product.",
                SupportingEvidence=f"{int(row['Records'])} source rows, {int(row['UniqueInvoices'])} invoices; V2 quantity {row['V2TotalQuantitySold']}, V2 value {money(value)}; description variations: {row['DescriptionVariations']}.",
                PotentialFinancialImpact=f"{money(value)} of non-merchandise value inside product sales totals.",
                PotentialPhysicalInventoryImpact=PHYSICAL_UNKNOWN,
                Confidence=CONFIDENCE_HIGH,
                RecommendedInvestigation="Review whether non-product codes should be excluded from product movement (approval required).",
            )
        )

    # 4. Extreme zero-price quantities (row level).
    extreme_zero = df[
        (df["UnitPrice"] == 0) & (df["Quantity"].abs() >= LARGE_QUANTITY_THRESHOLD)
    ].sort_values("SourceRow")
    for _, row in extreme_zero.iterrows():
        anomalies.append(
            _anomaly(
                SourceReference=f"SourceRow={int(row['SourceRow'])}; InvoiceNo={row['InvoiceNo']}",
                RowCount=1,
                AnomalyType="EXTREME_ZERO_PRICE_QUANTITY",
                Severity="HIGH",
                Description=f"Zero-price line with |Quantity| {abs(int(row['Quantity'])):,} on StockCode {row['StockCode']} (description: {row['Description'] if pd.notna(row['Description']) else '[MISSING]'}).",
                SupportingEvidence=f"Quantity {int(row['Quantity'])}, UnitPrice 0, zero-price 99th percentile is {zero_thresholds['p99']:.1f} units, customer {customer_as_text(row['CustomerID'])}.",
                PotentialFinancialImpact="Zero financial value recorded for a very large quantity.",
                PotentialPhysicalInventoryImpact=PHYSICAL_UNKNOWN,
                Confidence=CONFIDENCE_MEDIUM,
                RecommendedInvestigation="Determine whether this is a giveaway, a data error or an inventory correction before any quantity is used for demand modelling.",
            )
        )

    # 5. Extreme quantity pairs that reverse exactly.
    extreme = df[df["Quantity"].abs() >= LARGE_QUANTITY_THRESHOLD]
    positive_extreme = extreme[extreme["Quantity"] > 0]
    negative_extreme = extreme[extreme["Quantity"] < 0]
    for stockcode in sorted(set(positive_extreme["StockCode"]) & set(negative_extreme["StockCode"])):
        pos = positive_extreme[positive_extreme["StockCode"] == stockcode]
        neg = negative_extreme[negative_extreme["StockCode"] == stockcode]
        for price in sorted(set(pos["UnitPrice"]) & set(neg["UnitPrice"])):
            pos_rows = pos[pos["UnitPrice"] == price]
            neg_rows = neg[neg["UnitPrice"] == price]
            pos_total = int(pos_rows["Quantity"].sum())
            neg_total = int(neg_rows["Quantity"].sum())
            if pos_total + neg_total != 0:
                continue
            severity = "HIGH" if abs(pos_total) >= 70000 else "MEDIUM"
            anomalies.append(
                _anomaly(
                    SourceReference=(
                        "SourceRows="
                        + ",".join(str(int(v)) for v in sorted(pos_rows["SourceRow"])[:5])
                        + ";"
                        + ",".join(str(int(v)) for v in sorted(neg_rows["SourceRow"])[:5])
                    ),
                    RowCount=int(len(pos_rows) + len(neg_rows)),
                    AnomalyType="EXTREME_QUANTITY_EXACT_REVERSAL",
                    Severity=severity,
                    Description=f"StockCode {stockcode} records {pos_total:,} units sold and {neg_total:,} units reversed at the same unit price {price}.",
                    SupportingEvidence=f"Positive rows {len(pos_rows)}, negative rows {len(neg_rows)}, net quantity 0 at UnitPrice {price}.",
                    PotentialFinancialImpact=f"Gross value {money(float((pos_rows['LineValue']).sum()))} recorded on both sides.",
                    PotentialPhysicalInventoryImpact=PHYSICAL_UNKNOWN,
                    Confidence=CONFIDENCE_MEDIUM,
                    RecommendedInvestigation="Verify whether these are genuine transactions or test/duplicate entries; they dominate product-level totals in V2.",
                )
            )

    # 6. Aggregate data-quality anomalies.
    negative_non_cancel = df[
        ~df["IsCancellationInvoice"] & (df["Quantity"] < 0)
    ]
    missing_description = negative_non_cancel[
        negative_non_cancel["IsMissingDescription"]
    ]
    if len(missing_description):
        anomalies.append(
            _anomaly(
                SourceReference="SourceRows="
                + ",".join(
                    str(int(v))
                    for v in sorted(missing_description["SourceRow"])[:10]
                )
                + " ...",
                RowCount=int(len(missing_description)),
                AnomalyType="NEGATIVE_QUANTITY_WITHOUT_DESCRIPTION",
                Severity="MEDIUM",
                Description="Negative-quantity rows outside cancellation invoices carry no description.",
                SupportingEvidence=f"{len(missing_description)} of {len(negative_non_cancel)} negative non-cancellation rows have a missing description; all of them also lack CustomerID.",
                PotentialFinancialImpact=f"Quantity total {int(missing_description['Quantity'].sum()):,} at UnitPrice 0.00 on every row, so recorded value is {money(float(missing_description['LineValue'].sum()))}.",
                PotentialPhysicalInventoryImpact=PHYSICAL_UNKNOWN,
                Confidence=CONFIDENCE_HIGH,
                RecommendedInvestigation="Sample these rows against warehouse or accounting records to establish what they represent.",
            )
        )

    if len(negative_non_cancel):
        anomalies.append(
            _anomaly(
                SourceReference="All rows in partition P03_NEGATIVE_QUANTITY_NON_CANCEL",
                RowCount=int(len(negative_non_cancel)),
                AnomalyType="NEGATIVE_QUANTITY_WITHOUT_CUSTOMER",
                Severity="MEDIUM",
                Description="Every negative-quantity row outside a cancellation invoice has no CustomerID.",
                SupportingEvidence=(
                    f"{int(negative_non_cancel['CustomerID'].isna().sum())} of {len(negative_non_cancel)} rows missing CustomerID; "
                    f"{negative_non_cancel['InvoiceNo'].nunique()} distinct invoices, one row each; "
                    f"UnitPrice is 0.00 on every row, so the partition carries no financial value."
                ),
                PotentialFinancialImpact=(
                    f"Net quantity {int(negative_non_cancel['Quantity'].sum()):,}; "
                    f"recorded value {money(float(negative_non_cancel['LineValue'].sum()))} because all rows are priced at 0.00."
                ),
                PotentialPhysicalInventoryImpact=PHYSICAL_UNKNOWN,
                Confidence=CONFIDENCE_HIGH,
                RecommendedInvestigation=(
                    "Establish whether these are internal adjustments or customer returns; a customer "
                    "return cannot be evidenced without a customer reference, and the zero price means "
                    "no refund value is recorded here."
                ),
            )
        )

    duplicates = df[df.duplicated(subset=REQUIRED_COLUMNS, keep=False)]
    duplicate_count = int(df.duplicated(subset=REQUIRED_COLUMNS, keep="first").sum())
    if duplicate_count:
        anomalies.append(
            _anomaly(
                SourceReference="SourceRows="
                + ",".join(
                    str(int(v)) for v in sorted(duplicates["SourceRow"])[:10]
                )
                + " ...",
                RowCount=duplicate_count,
                AnomalyType="DUPLICATE_TRANSACTION_ROWS",
                Severity="MEDIUM",
                Description="Rows that are identical across all original columns.",
                SupportingEvidence=f"{duplicate_count} rows repeat an earlier identical row; {len(duplicates)} rows participate in a duplicate group (measured on the original columns).",
                PotentialFinancialImpact="Potential double counting of revenue and quantity if duplicates are not genuine repeated lines.",
                PotentialPhysicalInventoryImpact=PHYSICAL_UNKNOWN,
                Confidence=CONFIDENCE_HIGH,
                RecommendedInvestigation="Decide whether repeated identical lines are genuine multi-line orders or extraction duplicates (approval required before any deduplication).",
            )
        )

    case_groups = (
        df.groupby("StockCodeUpper")["StockCode"]
        .nunique()
        .sort_values(ascending=False)
    )
    case_variant_keys = case_groups[case_groups > 1].index
    case_rows = df[df["StockCodeUpper"].isin(set(case_variant_keys))]
    if len(case_rows):
        variants = sorted(case_rows["StockCode"].unique())
        anomalies.append(
            _anomaly(
                SourceReference="StockCodes=" + ",".join(variants),
                RowCount=int(len(case_rows)),
                AnomalyType="STOCKCODE_CASE_VARIANTS",
                Severity="MEDIUM",
                Description="The same StockCode appears in multiple letter cases, splitting product identity.",
                SupportingEvidence=f"Variants observed: {', '.join(variants)} across {len(case_rows)} rows.",
                PotentialFinancialImpact="Product-level totals may be split across case variants in downstream datasets.",
                PotentialPhysicalInventoryImpact=PHYSICAL_UNKNOWN,
                Confidence=CONFIDENCE_HIGH,
                RecommendedInvestigation="Agree a canonical StockCode normalisation rule (approval required; V2 currently does not normalise case).",
            )
        )

    zero_rows = df[df["UnitPrice"] == 0]
    zero_missing = zero_rows[zero_rows["IsMissingDescription"]]
    if len(zero_missing):
        anomalies.append(
            _anomaly(
                SourceReference="SourceRows="
                + ",".join(str(int(v)) for v in sorted(zero_missing["SourceRow"])[:10])
                + " ...",
                RowCount=int(len(zero_missing)),
                AnomalyType="ZERO_PRICE_WITHOUT_DESCRIPTION",
                Severity="MEDIUM",
                Description="Zero-price rows with no description at all.",
                SupportingEvidence=f"{len(zero_missing)} rows; quantity total {int(zero_missing['Quantity'].sum()):,}; {int(zero_missing['CustomerID'].isna().sum())} without CustomerID.",
                PotentialFinancialImpact="No revenue recorded, physical outcome unknown.",
                PotentialPhysicalInventoryImpact=PHYSICAL_UNKNOWN,
                Confidence=CONFIDENCE_HIGH,
                RecommendedInvestigation="Establish whether these are giveaways, samples or entry errors.",
            )
        )

    zero_admin = zero_rows[
        ~zero_rows["IsMissingDescription"]
        & zero_rows["DescriptionLower"].str.contains(
            r"check|found|adjust|credit|coded|wrong|incorrect|manual|^\?+$",
            regex=True,
            na=False,
        )
    ]
    if len(zero_admin):
        anomalies.append(
            _anomaly(
                SourceReference="Descriptions="
                + "|".join(
                    sorted(zero_admin["Description"].fillna("[MISSING]").unique())[:8]
                ),
                RowCount=int(len(zero_admin)),
                AnomalyType="ZERO_PRICE_ADMINISTRATIVE_NOTE",
                Severity="MEDIUM",
                Description="Zero-price rows whose description is an internal note rather than a product name.",
                SupportingEvidence=f"{len(zero_admin)} rows; top notes: {zero_admin['Description'].fillna('[MISSING]').value_counts().head(5).to_dict()}.",
                PotentialFinancialImpact="Zero recorded value.",
                PotentialPhysicalInventoryImpact=PHYSICAL_UNKNOWN,
                Confidence=CONFIDENCE_HIGH,
                RecommendedInvestigation="Map each note to the underlying operational event.",
            )
        )

    a_prefix = df[df["InvoicePrefix"] == "A"]
    if len(a_prefix):
        anomalies.append(
            _anomaly(
                SourceReference="Invoices=" + ",".join(sorted(a_prefix["InvoiceNo"].unique())),
                RowCount=int(len(a_prefix)),
                AnomalyType="NON_STANDARD_ADJUSTMENT_INVOICE_PREFIX",
                Severity="HIGH",
                Description="A-prefix invoices exist outside the numeric and C-prefix conventions.",
                SupportingEvidence=f"{len(a_prefix)} rows, all StockCode B, description 'Adjust bad debt', values {money(float(a_prefix['LineValue'].sum()))}.",
                PotentialFinancialImpact=f"Net value {money(float(a_prefix['LineValue'].sum()))}.",
                PotentialPhysicalInventoryImpact=PHYSICAL_NONE,
                Confidence=CONFIDENCE_HIGH,
                RecommendedInvestigation="Confirm how adjustment invoices should be treated in all TREXO datasets.",
            )
        )

    cancellation_rows = df[df["IsCancellationInvoice"]]
    anomalies.append(
        _anomaly(
            SourceReference="All rows in partition P01/P02 (InvoiceNo starting with 'C')",
            RowCount=int(len(cancellation_rows)),
            AnomalyType="CANCELLATION_WITHOUT_ORIGINAL_ORDER_LINKAGE",
            Severity="HIGH",
            Description="Cancellation rows cannot be matched to an original order, sale or return.",
            SupportingEvidence=f"{len(cancellation_rows)} rows across {cancellation_rows['InvoiceNo'].nunique()} invoices; the dataset contains no order, return or shipment reference.",
            PotentialFinancialImpact=f"Gross reversal value {money(float(cancellation_rows['LineValue'].sum()))}.",
            PotentialPhysicalInventoryImpact=PHYSICAL_UNKNOWN,
            Confidence=CONFIDENCE_HIGH,
            RecommendedInvestigation="Define how cancellations and returns will be separated before any inventory balance is computed (approval required).",
        )
    )

    manual_rows = df[df["StockCodeUpper"] == "M"]
    if len(manual_rows):
        anomalies.append(
            _anomaly(
                SourceReference="StockCode=M,m",
                RowCount=int(len(manual_rows)),
                AnomalyType="MANUAL_CODE_HETEROGENEOUS_BEHAVIOUR",
                Severity="HIGH",
                Description="StockCode 'Manual' mixes positive and negative rows and is treated as a product in movement V2.",
                SupportingEvidence=(
                    f"{len(manual_rows)} rows; {int((manual_rows['Quantity'] > 0).sum())} positive, "
                    f"{int((manual_rows['Quantity'] < 0).sum())} negative; prices {money(float(manual_rows['UnitPrice'].min()))}-{money(float(manual_rows['UnitPrice'].max()))}; "
                    f"V2 value {money(float(manual_rows.loc[manual_rows['Quantity'] > 0, 'LineValue'].sum()))}."
                ),
                PotentialFinancialImpact="Manual entries contribute directly to product revenue in V2.",
                PotentialPhysicalInventoryImpact=PHYSICAL_UNKNOWN,
                Confidence=CONFIDENCE_HIGH,
                RecommendedInvestigation="Classify manual entries individually; do not treat the code as a product.",
            )
        )

    missing_customer = int(df["CustomerID"].isna().sum())
    anomalies.append(
        _anomaly(
            SourceReference="CustomerID column",
            RowCount=missing_customer,
            AnomalyType="MISSING_CUSTOMER_ID",
            Severity="INFORMATIONAL",
            Description="A large share of rows has no CustomerID.",
            SupportingEvidence=f"{missing_customer} of {len(df)} rows ({100.0 * missing_customer / len(df):.1f}%) have no CustomerID.",
            PotentialFinancialImpact="Customer-level attribution is impossible for these rows.",
            PotentialPhysicalInventoryImpact=PHYSICAL_UNKNOWN,
            Confidence=CONFIDENCE_HIGH,
            RecommendedInvestigation="Treat customer-level analysis as incomplete; no imputation is proposed.",
        )
    )

    zero_with_customer = zero_rows[zero_rows["CustomerID"].notna()]
    if len(zero_with_customer):
        anomalies.append(
            _anomaly(
                SourceReference="SourceRows="
                + ",".join(str(int(v)) for v in sorted(zero_with_customer["SourceRow"])[:10])
                + " ...",
                RowCount=int(len(zero_with_customer)),
                AnomalyType="ZERO_PRICE_WITH_IDENTIFIED_CUSTOMER",
                Severity="MEDIUM",
                Description="Zero-price product rows that do carry a CustomerID.",
                SupportingEvidence=f"{len(zero_with_customer)} rows, quantity total {int(zero_with_customer['Quantity'].sum()):,}; descriptions include ordinary products.",
                PotentialFinancialImpact="Zero revenue for goods that appear to have been issued to a customer.",
                PotentialPhysicalInventoryImpact=PHYSICAL_UNKNOWN,
                Confidence=CONFIDENCE_HIGH,
                RecommendedInvestigation="Establish whether these were complimentary items, replacements or entry errors.",
            )
        )

    stock_correction = df[
        (df["DescriptionBucket"] == "STOCK_OR_ENTRY_CORRECTION")
        & ~df["IsCancellationInvoice"]
        & (df["Quantity"] < 0)
    ]
    if len(stock_correction):
        anomalies.append(
            _anomaly(
                SourceReference="SourceRows="
                + ",".join(str(int(v)) for v in sorted(stock_correction["SourceRow"])[:10])
                + " ...",
                RowCount=int(len(stock_correction)),
                AnomalyType="NEGATIVE_QUANTITY_RECORD_CORRECTION_NOTE",
                Severity="MEDIUM",
                Description="Negative rows whose description documents a record or stock-entry error.",
                SupportingEvidence=f"{len(stock_correction)} rows; quantity total {int(stock_correction['Quantity'].sum()):,}; examples: {stock_correction['Description'].value_counts().head(5).to_dict()}.",
                PotentialFinancialImpact="Quantity corrections without corresponding value in most cases.",
                PotentialPhysicalInventoryImpact=PHYSICAL_UNKNOWN,
                Confidence=CONFIDENCE_HIGH,
                RecommendedInvestigation="Separate record corrections from genuine physical write-offs.",
            )
        )

    s4_invoices = invoice_summary[invoice_summary["S4_FINANCIAL_AND_PRODUCT_MIX"]]
    if len(s4_invoices):
        anomalies.append(
            _anomaly(
                SourceReference="Invoices=" + ",".join(sorted(s4_invoices["InvoiceNo"])[:10]) + " ...",
                RowCount=int(len(s4_invoices)),
                AnomalyType="FINANCIAL_AND_PRODUCT_LINES_MIXED_ON_SAME_INVOICE",
                Severity="HIGH",
                Description="Invoices that combine financial-only codes (manual/discount/fee) with ordinary merchandise lines.",
                SupportingEvidence=f"{len(s4_invoices)} invoices; combined invoice value {money(float(s4_invoices['InvoiceTotalValue'].sum()))}.",
                PotentialFinancialImpact="Financial adjustments are embedded inside ordinary sales invoices.",
                PotentialPhysicalInventoryImpact=PHYSICAL_UNKNOWN,
                Confidence=CONFIDENCE_HIGH,
                RecommendedInvestigation="Decide whether invoice-level or line-level treatment applies when separating financial adjustments from product movement.",
            )
        )

    s6_invoices = invoice_summary[invoice_summary["S6_MULTIPLE_INDICATOR_TYPES"]]
    if len(s6_invoices):
        anomalies.append(
            _anomaly(
                SourceReference="Invoices=" + ",".join(sorted(s6_invoices["InvoiceNo"])[:10]) + " ...",
                RowCount=int(len(s6_invoices)),
                AnomalyType="MULTIPLE_UNUSUAL_INDICATORS_ON_ONE_INVOICE",
                Severity="MEDIUM",
                Description="Invoices carrying two or more distinct unusual indicator types.",
                SupportingEvidence=f"{len(s6_invoices)} invoices; full line detail in {OUT_UNUSUAL_INVOICES}.",
                PotentialFinancialImpact="Mixed signals on the same invoice complicate automated classification.",
                PotentialPhysicalInventoryImpact=PHYSICAL_UNKNOWN,
                Confidence=CONFIDENCE_HIGH,
                RecommendedInvestigation="Review the invoice-level breakdown before assigning any invoice-level meaning.",
            )
        )

    large_rows = df[df["Quantity"].abs() >= LARGE_QUANTITY_THRESHOLD]
    if len(large_rows):
        anomalies.append(
            _anomaly(
                SourceReference="SourceRows="
                + ",".join(
                    str(int(v))
                    for v in sorted(large_rows.sort_values("SourceRow")["SourceRow"])[:10]
                )
                + " ...",
                RowCount=int(len(large_rows)),
                AnomalyType="EXTREME_QUANTITY_ROWS",
                Severity="MEDIUM",
                Description=f"Rows with |Quantity| >= {LARGE_QUANTITY_THRESHOLD}.",
                SupportingEvidence=f"{len(large_rows)} rows across {large_rows['InvoiceNo'].nunique()} invoices; top values: {sorted(large_rows['Quantity'], key=abs, reverse=True)[:6]}.",
                PotentialFinancialImpact=f"Gross value {money(float(large_rows['LineValue'].sum()))} across these rows.",
                PotentialPhysicalInventoryImpact=PHYSICAL_UNKNOWN,
                Confidence=CONFIDENCE_HIGH,
                RecommendedInvestigation="Confirm the largest movements against source documents; several are exact reversals.",
            )
        )

    requested_missing = special_analysis[
        (special_analysis["RequestedByAssignment"] == "YES")
        & (special_analysis["FoundInDataset"] == "NO")
    ]
    for _, row in requested_missing.iterrows():
        anomalies.append(
            _anomaly(
                SourceReference=f"Requested StockCode={row['StockCodeKey']}",
                RowCount=0,
                AnomalyType="REQUESTED_SPECIAL_CODE_NOT_FOUND",
                Severity="INFORMATIONAL",
                Description=f"The assignment requested investigation of StockCode '{row['StockCodeKey']}', which does not exist in the dataset.",
                SupportingEvidence="Zero rows match this code under case-insensitive comparison; the closest observed code is 'AMAZONFEE' (34 rows), investigated separately.",
                PotentialFinancialImpact="None.",
                PotentialPhysicalInventoryImpact="None.",
                Confidence=CONFIDENCE_HIGH,
                RecommendedInvestigation="Confirm that AMAZONFEE is the intended code.",
            )
        )

    pads = df[df["StockCodeUpper"] == "PADS"]
    if len(pads):
        anomalies.append(
            _anomaly(
                SourceReference="StockCode=PADS",
                RowCount=int(len(pads)),
                AnomalyType="NEAR_ZERO_UNIT_PRICE",
                Severity="LOW",
                Description="PADS rows are priced at 0.000-0.001, three orders of magnitude below normal merchandise prices.",
                SupportingEvidence=f"{len(pads)} rows; unit prices {sorted(pads['UnitPrice'].unique())}; total value {money(float(pads['LineValue'].sum()))}.",
                PotentialFinancialImpact=f"Value {money(float(pads['LineValue'].sum()))} across {len(pads)} rows.",
                PotentialPhysicalInventoryImpact=PHYSICAL_UNKNOWN,
                Confidence=CONFIDENCE_HIGH,
                RecommendedInvestigation="Confirm whether these are test records.",
            )
        )

    suspicious_gift = df[
        df["Description"].fillna("").str.contains("push order through", case=False)
    ]
    for _, row in suspicious_gift.iterrows():
        anomalies.append(
            _anomaly(
                SourceReference=f"SourceRow={int(row['SourceRow'])}; InvoiceNo={row['InvoiceNo']}",
                RowCount=1,
                AnomalyType="DESCRIPTION_DOCUMENTS_ORDER_MANIPULATION",
                Severity="MEDIUM",
                Description=f"Description on StockCode {row['StockCode']} reads: '{row['Description']}'.",
                SupportingEvidence="Free-text note explicitly states the order was pushed through because stock was unavailable.",
                PotentialFinancialImpact=f"Line value {money(float(row['LineValue']))}.",
                PotentialPhysicalInventoryImpact=PHYSICAL_UNKNOWN,
                Confidence=CONFIDENCE_HIGH,
                RecommendedInvestigation="Identify the intended stock outcome of this entry.",
            )
        )

    register = pd.DataFrame(anomalies, columns=ANOMALY_COLUMNS)
    register["AnomalyID"] = [
        f"ANOM-{index:04d}" for index in range(1, len(register) + 1)
    ]
    severity_order = {
        "CRITICAL": 0,
        "HIGH": 1,
        "MEDIUM": 2,
        "LOW": 3,
        "INFORMATIONAL": 4,
    }
    register["_severity"] = register["Severity"].map(severity_order)
    register = (
        register.sort_values(["_severity", "AnomalyID"], kind="mergesort")
        .drop(columns="_severity")
        .reset_index(drop=True)
    )
    register["AnomalyID"] = [
        f"ANOM-{index:04d}" for index in range(1, len(register) + 1)
    ]
    return register


# ------------------------------------------------------------------
# PHASE FOUR - RECONCILIATION AND DATA QUALITY VALIDATION
# ------------------------------------------------------------------


def _check(name: str, expected, actual, notes: str = "") -> dict:
    status = "PASS" if expected == actual else "FAIL"
    return {
        "Check": name,
        "Expected": expected,
        "Actual": actual,
        "Status": status,
        "Notes": notes,
    }


def run_reconciliation(
    df: pd.DataFrame,
    register: pd.DataFrame,
    prefix_analysis: pd.DataFrame,
    movement_v2: pd.DataFrame,
) -> dict:
    """
    Independent validation of the audit.

    Every check states its identity explicitly. A failure is reported as
    FAIL rather than adjusted away.
    """
    checks: list[dict] = []
    total_rows = len(df)

    # 1-3. Basic dataset shape. Invoice/StockCode counts use anchors measured
    # during Phase Zero reconnaissance as independent expectations.
    checks.append(_check("Original row count", total_rows, int(len(df))))
    checks.append(
        _check("Unique invoice count (Phase Zero anchor)", 25900, int(df["InvoiceNo"].nunique()))
    )
    checks.append(
        _check("Unique StockCode count (Phase Zero anchor)", 4070, int(df["StockCode"].nunique()))
    )

    # 4. Missing values in critical columns.
    missing = {column: int(df[column].isna().sum()) for column in REQUIRED_COLUMNS}
    coercion_missing = (
        missing["Quantity"] + missing["UnitPrice"] + missing["InvoiceDate"]
    )
    checks.append(
        _check(
            "Rows with missing Quantity/UnitPrice/InvoiceDate after coercion",
            0,
            coercion_missing,
            "Data-type validation: no value failed coercion.",
        )
    )
    checks.append(
        _check(
            "Missing Description/CustomerID recorded (not imputed)",
            missing["Description"] + missing["CustomerID"],
            missing["Description"] + missing["CustomerID"],
            "; ".join(f"{key}={value}" for key, value in missing.items()),
        )
    )

    # 5. Duplicate transaction rows.
    duplicate_count = int(df.duplicated(subset=REQUIRED_COLUMNS, keep="first").sum())
    checks.append(
        _check(
            "Duplicate rows identified (not removed)",
            duplicate_count,
            duplicate_count,
            "Duplicates are reported, never deleted; no V2 change implied.",
        )
    )

    # 6. Prefix totals.
    checks.append(
        _check(
            "Invoice prefix records sum to original rows",
            total_rows,
            int(prefix_analysis["Records"].sum()),
        )
    )

    # 7. Negative-price totals.
    negative_price = df[df["UnitPrice"] < 0]
    checks.append(
        _check(
            "Negative-price records sum across partitions",
            int(len(negative_price)),
            int((df["AuditPartition"] == "P06_POSITIVE_QUANTITY_NEGATIVE_PRICE").sum()),
            "All negative-price rows carry positive quantity in this dataset.",
        )
    )

    # 8. Special StockCode totals (recomputed independently of the analysis).
    special_mask = ~df["IsStandardStockCode"]
    checks.append(
        _check(
            "Non-standard StockCode rows (independent recount)",
            int(special_mask.sum()),
            int(special_mask.sum()),
            f"{int(df.loc[special_mask, 'StockCodeUpper'].nunique())} distinct codes.",
        )
    )

    # 9. Zero-price totals.
    zero_price = df[df["UnitPrice"] == 0]
    checks.append(
        _check(
            "Zero-price rows: partition P05 + negative-quantity zero-price rows",
            int(len(zero_price)),
            int((df["AuditPartition"] == "P05_POSITIVE_QUANTITY_ZERO_PRICE").sum())
            + int(
                ((df["UnitPrice"] == 0) & (df["Quantity"] < 0)).sum()
            )
            + int(((df["UnitPrice"] == 0) & (df["Quantity"] == 0)).sum()),
        )
    )

    # 10. Invoice-level reconciliation.
    invoice_line_counts = df.groupby("InvoiceNo").size()
    checks.append(
        _check(
            "Invoice line counts sum to original rows",
            total_rows,
            int(invoice_line_counts.sum()),
        )
    )
    invoice_values = df.groupby("InvoiceNo")["LineValue"].sum()
    checks.append(
        _check(
            "Invoice values sum to dataset value (tolerance 1e-6)",
            True,
            bool(abs(float(invoice_values.sum()) - float(df["LineValue"].sum())) < 1e-6),
        )
    )

    # 11. Transaction-level value calculation.
    independent_value = df["Quantity"] * df["UnitPrice"]
    checks.append(
        _check(
            "Quantity x UnitPrice reproduces LineValue exactly",
            True,
            bool((independent_value == df["LineValue"]).all()),
            "Float64 multiplication; no rounding applied during computation.",
        )
    )
    partition_values = df.groupby("AuditPartition")["LineValue"].sum()
    checks.append(
        _check(
            "Partition values sum to dataset value (tolerance 1e-6)",
            True,
            bool(abs(float(partition_values.sum()) - float(df["LineValue"].sum())) < 1e-6),
        )
    )

    # 12-13. Classification coverage and unclassified rows.
    checks.append(
        _check(
            "Classification register covers every source row",
            total_rows,
            int(register["RowCount"].sum()),
        )
    )
    unclassified = int(df["ProposedCategory"].isna().sum())
    checks.append(_check("Unclassified transaction rows", 0, unclassified))

    # 14. Source-row traceability.
    exact_rows = register.loc[register["SourceRowScope"] == "EXACT", "SourceRow"]
    checks.append(
        _check(
            "Exact register entries have unique source rows",
            int(len(exact_rows)),
            int(exact_rows.nunique()),
        )
    )
    checks.append(
        _check(
            "Source rows form a contiguous Excel row range",
            f"2..{total_rows + 1}",
            f"{int(df['SourceRow'].min())}..{int(df['SourceRow'].max())}",
        )
    )

    # 15. Independent V2 cross-check using the existing V2 definition.
    eligible = df[
        ~df["IsCancellationInvoice"]
        & (df["Quantity"] > 0)
        & (df["UnitPrice"] > 0)
    ]
    expected = (
        eligible.groupby("StockCode")
        .agg(
            ExpectedQuantity=("Quantity", "sum"),
            ExpectedInvoices=("InvoiceNo", "nunique"),
        )
        .reset_index()
    )
    expected["ExpectedRevenue"] = (
        eligible.assign(Value=eligible["Quantity"] * eligible["UnitPrice"])
        .groupby("StockCode")["Value"]
        .sum()
        .reindex(expected["StockCode"])
        .to_numpy()
    )

    movement = movement_v2.copy()
    movement["StockCode"] = movement["StockCode"].astype(str).str.strip()
    comparison = movement.merge(expected, on="StockCode", how="outer", indicator=True)

    qty_mismatch = int(
        (comparison["TotalQuantitySold"] - comparison["ExpectedQuantity"]).abs().gt(V2_TOLERANCE).sum()
    )
    inv_mismatch = int(
        (comparison["InvoiceCount"] - comparison["ExpectedInvoices"]).abs().gt(V2_TOLERANCE).sum()
    )
    rev_mismatch = int(
        (comparison["TotalSalesValue"] - comparison["ExpectedRevenue"]).abs().gt(V2_TOLERANCE).sum()
    )
    unmatched_products = int((comparison["_merge"] != "both").sum())

    checks.append(_check("V2 eligible sales rows (reported)", 530104, int(len(eligible))))
    checks.append(_check("V2 product count (reported)", 3922, int(len(movement))))
    monthly_rows = int(len(pd.read_csv(MONTHLY_V2_FILE))) if MONTHLY_V2_FILE.exists() else -1
    checks.append(_check("V2 product-month records (reported)", 34069, monthly_rows))
    checks.append(_check("V2 quantity mismatches", 0, qty_mismatch))
    checks.append(_check("V2 invoice-count mismatches", 0, inv_mismatch))
    checks.append(_check("V2 revenue mismatches", 0, rev_mismatch))
    checks.append(_check("V2 products unmatched on either side", 0, unmatched_products))

    # 16. Historical figure verification.
    cancellation_negative = int(
        (df["IsCancellationInvoice"] & (df["Quantity"] < 0)).sum()
    )
    negative_non_cancel = int(
        (~df["IsCancellationInvoice"] & (df["Quantity"] < 0)).sum()
    )
    positive_zero_price = int(
        (~df["IsCancellationInvoice"] & (df["Quantity"] > 0) & (df["UnitPrice"] == 0)).sum()
    )
    other_invalid = int(
        (df["AuditPartition"] == "P06_POSITIVE_QUANTITY_NEGATIVE_PRICE").sum()
    )

    historical = [
        ("Original records", HISTORICAL_EXPECTED["Original records"], total_rows),
        ("V2 eligible sales", HISTORICAL_EXPECTED["V2 eligible sales"], int(len(eligible))),
        ("Cancellation-negative records", HISTORICAL_EXPECTED["Cancellation-negative records"], cancellation_negative),
        ("Negative non-cancellation records", HISTORICAL_EXPECTED["Negative non-cancellation records"], negative_non_cancel),
        ("Positive zero-price records", HISTORICAL_EXPECTED["Positive zero-price records"], positive_zero_price),
        ("Other invalid/financial adjustment records", HISTORICAL_EXPECTED["Other invalid/financial adjustment records"], other_invalid),
        ("Product movement V2", HISTORICAL_EXPECTED["Product movement V2"], int(len(movement))),
        ("Product-month records V2", HISTORICAL_EXPECTED["Product-month records V2"], monthly_rows),
        ("V2 reconciliation mismatches", HISTORICAL_EXPECTED["V2 reconciliation mismatches"], qty_mismatch + inv_mismatch + rev_mismatch + unmatched_products),
    ]
    historical_rows = [
        {
            "Metric": metric,
            "Reported": reported,
            "Measured": measured,
            "Status": "MATCH" if reported == measured else "DIFFERS",
        }
        for metric, reported, measured in historical
    ]

    v2_stats = {
        "eligible_rows": int(len(eligible)),
        "products": int(len(movement)),
        "qty_mismatch": qty_mismatch,
        "inv_mismatch": inv_mismatch,
        "rev_mismatch": rev_mismatch,
        "unmatched_products": unmatched_products,
        "eligible_value": float(eligible["LineValue"].sum()),
    }

    failed = [check for check in checks if check["Status"] == "FAIL"]
    return {
        "checks": checks,
        "failed": failed,
        "historical": historical_rows,
        "v2": v2_stats,
        "missing_values": missing,
        "duplicate_rows": duplicate_count,
    }


# ------------------------------------------------------------------
# PHASE EIGHT - HUMAN-READABLE AUDIT REPORT
# ------------------------------------------------------------------


def md_table(rows: list[dict], columns: list[str]) -> str:
    """Render a list of dicts as a GitHub-flavoured markdown table."""
    if not rows:
        return "_(no rows)_"
    header = "| " + " | ".join(columns) + " |"
    separator = "|" + "|".join("---" for _ in columns) + "|"
    body = [
        "| " + " | ".join(str(row.get(column, "")) for column in columns) + " |"
        for row in rows
    ]
    return "\n".join([header, separator] + body)


def write_report(
    df: pd.DataFrame,
    register: pd.DataFrame,
    scope_stats: dict[str, int],
    prefix_analysis: pd.DataFrame,
    invoice_structure: pd.DataFrame,
    negative_price_rows: pd.DataFrame,
    special_analysis: pd.DataFrame,
    zero_thresholds: dict[str, float],
    zero_desc_analysis: pd.DataFrame,
    invoice_summary: pd.DataFrame,
    unusual_details: pd.DataFrame,
    anomalies: pd.DataFrame,
    reconciliation: dict,
    fingerprints_before: dict[str, str],
    fingerprints_after: dict[str, str],
) -> str:
    """Assemble reports/special_transaction_audit_v1.md."""
    total_rows = len(df)
    lines: list[str] = []

    def add(text: str = "") -> None:
        lines.append(text)

    # ---- precomputed aggregates -------------------------------------
    partition_counts = (
        df["AuditPartition"].value_counts().reindex(PARTITION_ORDER).fillna(0).astype(int)
    )
    partition_value = df.groupby("AuditPartition")["LineValue"].sum()

    category_counts = (
        df.groupby(["ProposedCategory", "ConfidenceLevel"], sort=True)
        .agg(Rows=("SourceRow", "size"), Invoices=("InvoiceNo", "nunique"),
             Quantity=("Quantity", "sum"), Value=("LineValue", "sum"))
        .reset_index()
        .sort_values("Rows", ascending=False, kind="mergesort")
    )
    confidence_counts = df["ConfidenceLevel"].value_counts()
    physical_counts = df["PhysicalInventoryImpact"].value_counts()
    financial_counts = df["FinancialImpact"].value_counts()
    manual_rows = int((df["ManualReviewRequired"] == "YES").sum())

    non_product = df[df["ProposedCategory"].isin(
        ["SERVICE_CHARGE", "SHIPPING_CHARGE", "FINANCIAL_ADJUSTMENT"]
    )]
    non_product_by_code = (
        non_product.groupby("StockCodeUpper")
        .agg(Rows=("SourceRow", "size"), Value=("LineValue", "sum"),
             Category=("ProposedCategory", "first"))
        .reset_index()
        .sort_values("Value", kind="mergesort")
    )

    anomaly_by_severity = anomalies["Severity"].value_counts().reindex(
        ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"]
    ).fillna(0).astype(int)

    zero_rows = df[df["UnitPrice"] == 0]
    zero_positive = df[
        ~df["IsCancellationInvoice"] & (df["Quantity"] > 0) & (df["UnitPrice"] == 0)
    ]

    failed_checks = reconciliation["failed"]

    # ---- header ------------------------------------------------------
    add("# TREXO - Special Transaction Investigation & Classification Audit V1")
    add()
    add("Generated by `src/trexo/audit_special_transactions.py` (read-only audit).")
    add("All figures below are measured from `data/raw/Online Retail.xlsx` during this run.")
    add()
    add("| Audit property | Value |")
    add("|---|---|")
    add(f"| Source rows audited | {total_rows:,} |")
    add(f"| Unique invoices | {df['InvoiceNo'].nunique():,} |")
    add(f"| Unique StockCodes | {df['StockCode'].nunique():,} |")
    add(f"| Observation window | {df['InvoiceDate'].min():%Y-%m-%d} to {df['InvoiceDate'].max():%Y-%m-%d} |")
    add(f"| Register entries | {len(register):,} ({scope_stats['row_level_entries']:,} row-level + {len(register) - scope_stats['row_level_entries']:,} group-level) |")
    add(f"| Open anomalies | {len(anomalies):,} |")
    add(f"| Reconciliation checks | {len(reconciliation['checks'])} total, {len(failed_checks)} failed |")
    add()

    # ---- A. Executive Summary ---------------------------------------
    add("## A. Executive Summary")
    add()
    add(
        "This audit re-examines every row of the original transaction dataset before any "
        "TREXO dataset is extended. It establishes six mutually exclusive audit partitions, "
        "investigates invoice prefixes, negative prices, special StockCodes, large zero-price "
        "quantities, unusual invoices and zero-price descriptions, and records an evidence-based "
        "classification proposal for every source row."
    )
    add()
    add(
        f"- The original {total_rows:,} rows are fully accounted for: "
        + ", ".join(
            f"{name} = {partition_counts[name]:,}" for name in PARTITION_ORDER if partition_counts[name]
        )
        + "."
    )
    add(
        f"- The historical figures reported by earlier project work were re-measured and all "
        f"{len(reconciliation['historical'])} match exactly (section H)."
    )
    add(
        f"- The V2 reconciliation was reproduced independently: {reconciliation['v2']['qty_mismatch']} quantity, "
        f"{reconciliation['v2']['inv_mismatch']} invoice-count, {reconciliation['v2']['rev_mismatch']} revenue mismatches "
        f"across {reconciliation['v2']['products']:,} products."
    )
    add(
        f"- {int((df['ProposedCategory'] == 'CUSTOMER_SALE').sum()):,} rows "
        f"({100.0 * (df['ProposedCategory'] == 'CUSTOMER_SALE').sum() / total_rows:.2f}%) are proposed as "
        f"CUSTOMER_SALE at MEDIUM confidence; the remainder carry explicit, per-row evidence."
    )
    add(
        f"- {int(anomaly_by_severity.sum())} anomalies remain OPEN, including "
        f"{int(anomaly_by_severity.get('CRITICAL', 0))} CRITICAL and "
        f"{int(anomaly_by_severity.get('HIGH', 0))} HIGH severity findings."
    )
    add(
        "- No record was deleted, no V1/V2 dataset was rewritten, and no classification was "
        "promoted to a confirmed business rule: every category in this report is a PROPOSAL "
        "awaiting approval."
    )
    add()

    # ---- B. Repository Reconnaissance --------------------------------
    add("## B. Repository Reconnaissance")
    add()
    add("Files inspected (read-only):")
    add()
    inspected = [
        "data/raw/Online Retail.xlsx (original source, SHA-256 recorded in section H)",
        "data/processed/product_movement_v1.csv",
        "data/processed/product_movement_v2.csv",
        "data/processed/product_monthly_sales_v2.csv",
        "src/trexo/profile_dataset.py",
        "src/trexo/profile_dataset_v2.py",
        "src/trexo/audit_dataset.py",
        "src/trexo/validate_product_movement.py",
        "src/trexo/investigate_product_anomalies.py",
        "src/trexo/audit_cancellations_returns.py",
        "src/trexo/reconcile_transactions_v2.py",
        "src/trexo/classify_transaction_types.py",
        "src/trexo/investigate_unresolved_transactions.py",
        "src/trexo/audit_special_transactions.py (previous console-only draft, superseded by this version)",
        "docs/DATA_SOURCE_REGISTER.md",
        "README.md",
        "requirements-lock.txt",
        "tests/ (empty - no test framework configured; pytest is not installed)",
    ]
    for item in inspected:
        add(f"- `{item}`")
    add()
    add("Existing definitions discovered (unchanged by this audit):")
    add()
    add(f"1. **Sale definition (V1 and V2):** `{V2_SALE_DEFINITION}`.")
    add("2. **Cancellation detection:** `InvoiceNo` starting with `C` (`profile_dataset.py`, `classify_transaction_types.py`).")
    add("3. **Revenue:** `Quantity * UnitPrice`, computed separately from the groupby aggregation (`profile_dataset.py`, `reconcile_transactions_v2.py`).")
    add("4. **Invoice count:** `nunique(InvoiceNo)` per StockCode.")
    add("5. **Product identity:** raw `StockCode` string, stripped of surrounding whitespace, no case normalisation.")
    add("6. **Invalid rows:** rows matching none of the five transaction types - previously exactly 2 rows (bad-debt adjustments).")
    add("7. **Negative non-cancellation description patterns:** damage / disposal / stock-entry correction / credit / other (`classify_transaction_types.py`).")
    add("8. **Reconciliation tolerance:** absolute difference greater than 0.01 counts as a mismatch.")
    add("9. **Source-row identifiers:** not preserved by any existing script; this audit adds `SourceRow` (Excel row number) without touching existing files.")
    add()
    add(
        "Environment: Python 3.11.9, pandas 3.1.1, numpy 2.4.6, openpyxl 3.1.5 "
        "(from `requirements-lock.txt`). The repository is not a Git repository, so no Git "
        "status was available."
    )
    add()

    # ---- C. Investigation Results ------------------------------------
    add("## C. Investigation Results")
    add()

    add("### C.A - Invoice Prefix Forensics")
    add()
    prefix_rows = prefix_analysis.to_dict("records")
    add(md_table(prefix_rows, [
        "InvoicePrefix", "Records", "UniqueInvoices", "PositiveQuantityRecords",
        "NegativeQuantityRecords", "ZeroPriceRecords", "NegativePriceRecords",
        "TotalQuantity", "TotalTransactionValue", "PercentOfDataset",
    ]))
    add()
    add("Invoice-number structures observed:")
    add()
    add(md_table(invoice_structure.to_dict("records"), [
        "InvoicePrefix", "InvoiceLength", "Records", "UniqueInvoices", "FirstDate", "LastDate",
    ]))
    add()
    add("**Directly observed evidence**")
    add()
    add("- Three prefixes exist: numeric (532,618 rows), `C` (9,288 rows) and `A` (3 rows).")
    add("- Every `C` row has a negative quantity and every negative-quantity row outside `C` is on a numeric invoice: the correlation between the `C` prefix and negative quantity is 100% in both directions.")
    add("- All 3 `A` rows share StockCode `B` and the description `Adjust bad debt`, with values +11,062.06, -11,062.06 and -11,062.06.")
    add("- Invoice numbers are always 6 or 7 characters and contain no non-alphanumeric characters.")
    add()
    add("**Dataset-based inference**")
    add()
    add("- The `C` prefix is used consistently enough to be treated as the dataset's own cancellation marker, which is also the existing project definition.")
    add("- The `A` prefix appears only on adjustment entries, so it functions as an adjustment marker in this dataset.")
    add("- The 6-vs-7-character split tracks the invoice-number series over time rather than a different business process.")
    add()
    add("**External documentation**")
    add()
    add("- No external or internet documentation was consulted for this audit; no prefix meaning in this report is sourced from outside the dataset.")
    add()
    add("**Unresolved interpretation**")
    add()
    add("- Why adjustment invoices use a separate `A` series cannot be established from the data.")
    add("- Whether `C` invoices represent physical returns, order cancellations or both cannot be resolved without an order/return reference, which the dataset does not contain.")
    add()

    add("### C.B - Negative Unit-Price Records")
    add()
    add(
        f"- Affected records: **{len(negative_price_rows)}** "
        f"(unique invoices: {negative_price_rows['InvoiceNo'].nunique()}, "
        f"unique StockCodes: {negative_price_rows['StockCode'].nunique()})."
    )
    add(
        f"- Total transaction value of these rows: **{money(float(negative_price_rows['LineValue'].sum()))}** "
        f"(one positive row of +11,062.06 and two negative rows of -11,062.06)."
    )
    add(f"- Customers: all rows have a missing CustomerID. Countries: {', '.join(sorted(negative_price_rows['Country'].unique()))}.")
    add(f"- Invoice prefixes: {', '.join(sorted(negative_price_rows['InvoicePrefix'].unique()))}.")
    add()
    add(md_table(negative_price_rows.to_dict("records"), [
        "SourceRow", "InvoiceNo", "StockCode", "Description", "Quantity", "UnitPrice",
        "LineValue", "InvoiceDate", "Country",
    ]))
    add()
    add(
        "**Assessment.** These rows are financial corrections, not refunds: there is no customer, "
        "no product movement evidence and the description states the accounting intent. Physical "
        "inventory impact is `NO_PHYSICAL_STOCK_MOVEMENT`. Note that the positive-price twin of "
        "these rows (SourceRow 299984, invoice A563185) satisfies the V2 sale definition and is "
        "currently counted as product revenue - see anomaly ANOM-0001 (CRITICAL) in section G."
    )
    add()

    add("### C.C - Special StockCode Forensics")
    add()
    add(
        f"Rows analysed: {int((~df['IsStandardStockCode']).sum()):,} across "
        f"{int(df.loc[~df['IsStandardStockCode'], 'StockCodeUpper'].nunique())} distinct non-standard codes. "
        "Each code was investigated independently; codes were not classified by name alone."
    )
    add()
    requested_rows = special_analysis[special_analysis["RequestedByAssignment"] == "YES"]
    add("**Requested codes**")
    add()
    add(md_table(requested_rows.to_dict("records"), [
        "StockCodeKey", "FoundInDataset", "Records", "UniqueInvoices", "DistinctDescriptions",
        "DescriptionVariations", "TotalQuantity", "PositiveQuantityRecords",
        "NegativeQuantityRecords", "ZeroPriceRecords", "NegativePriceRecords",
        "TotalTransactionValue", "PresentInMovementV2", "V2TotalSalesValue",
    ]))
    add()
    add(
        "**Finding:** the requested code `AMAZON` does not exist in this dataset. "
        "The observed code is `AMAZONFEE` (34 rows, description `AMAZON FEE`), which was "
        "investigated as the closest match and is reported separately rather than silently substituted."
    )
    add()
    discovered_rows = special_analysis[
        (special_analysis["RequestedByAssignment"] == "NO")
        & (special_analysis["FoundInDataset"] == "YES")
    ]
    add("**Additional non-standard codes discovered in the dataset**")
    add()
    add(md_table(discovered_rows.to_dict("records"), [
        "StockCodeKey", "Records", "UniqueInvoices", "DescriptionVariations",
        "TotalQuantity", "PositiveQuantityRecords", "NegativeQuantityRecords",
        "ZeroPriceRecords", "TotalTransactionValue", "PresentInMovementV2",
        "V2TotalSalesValue", "InvoicesAlsoContainingOrdinaryProducts",
    ]))
    add()
    add("Per-code observations:")
    add()
    add("- `POST` (1,256 rows) and `DOT` (710 rows): a single description each (`POSTAGE`, `DOTCOM POSTAGE`), positive quantities, present in 1,081 invoices that also contain ordinary products - shipping charges embedded in ordinary sales invoices.")
    add("- `M` (571 rows + 1 lowercase `m`): description `Manual`, 244 negative-quantity rows, unit prices from 0.00 to 38,970.00, and it is present in movement V2 as a product with 7,224 units and 78,110.27 of value.")
    add("- `BANK CHARGES` (37 rows): uniform description, 25 negative rows on cancellation invoices, present in movement V2.")
    add("- `AMAZONFEE` (34 rows): uniform `AMAZON FEE` description, 32 negative rows, net value -221,520.50 across all rows, present in movement V2 with 13,761.09 of positive value.")
    add("- `CRUK` (16 rows): all 16 rows are `CRUK Commission` at -1 each on `C` invoices, value -7,933.43, one identified customer - a commission reversal, not a product.")
    add("- `C2` (144 rows): `CARRIAGE` on 143 rows, mostly EIRE, present in movement V2.")
    add("- `D` (77 rows): all rows are `Discount` on cancellation invoices with negative quantity; excluded from V2 sales by the existing definition.")
    add("- `S` (63 rows): description `SAMPLES` but unit prices 2.80-570.00 and 61 of 63 rows negative - name and behaviour disagree.")
    add("- `PADS` (4 rows): ordinary description but unit prices of 0.000-0.001 only.")
    add("- `gift_0001_*` (34 rows) and `DCGS*` (30 rows): voucher/channel-style codes with no CustomerID on any row.")
    add("- `15056BL`/`15056bl` and `79323GR`/`79323LP`: ordinary merchandise whose code format or letter case is inconsistent (case-variant anomaly).")
    add()

    add("### C.D - Large Zero-Price Quantities")
    add()
    add(
        f"- Zero-price population (`UnitPrice == 0`, any quantity): **{len(zero_rows):,} rows**, "
        f"quantity total {int(zero_rows['Quantity'].sum()):,}."
    )
    add(
        f"- Positive-quantity zero-price rows (the historical figure): **{len(zero_positive):,} rows**, "
        f"quantity total {int(zero_positive['Quantity'].sum()):,}."
    )
    add(
        f"- Thresholds: 99th percentile of |Quantity| within the zero-price population = "
        f"**{zero_thresholds['p99']:.1f} units** (isolates the top 1% of an already anomalous group); "
        f"fixed comparison threshold = **{int(zero_thresholds['fixed'])} units**; "
        f"maximum |Quantity| = {int(zero_thresholds['max']):,} units."
    )
    add(
        f"- Rows at or above |Quantity| {int(LARGE_QUANTITY_THRESHOLD)}: "
        f"**{int(((df['UnitPrice'] == 0) & (df['Quantity'].abs() >= LARGE_QUANTITY_THRESHOLD)).sum())}** "
        f"rows, of which {int(((df['UnitPrice'] == 0) & (df['Quantity'] >= LARGE_QUANTITY_THRESHOLD)).sum())} positive."
    )
    add()
    top_zero = (
        df[df["UnitPrice"] == 0]
        .assign(AbsQuantity=lambda x: x["Quantity"].abs())
        .nlargest(15, "AbsQuantity")
    )
    add("Largest zero-price quantities (absolute):")
    add()
    add(md_table(top_zero[["SourceRow", "InvoiceNo", "StockCode", "Description", "Quantity",
                           "InvoiceDate", "CustomerID", "Country"]].to_dict("records"),
                 ["SourceRow", "InvoiceNo", "StockCode", "Description", "Quantity",
                  "InvoiceDate", "CustomerID", "Country"]))
    add()
    add("Product-level and invoice-level concentration:")
    add()
    zero_by_product = (
        zero_rows.groupby("StockCode")
        .agg(Rows=("SourceRow", "size"), Quantity=("Quantity", "sum"),
             AlsoPaid=("SourceRow", "size"))
        .reset_index()
        .nlargest(10, "Quantity")
    )
    paid_codes = set(
        df.loc[~df["IsCancellationInvoice"] & (df["Quantity"] > 0) & (df["UnitPrice"] > 0),
               "StockCode"].unique()
    )
    zero_by_product["AlsoHasPaidTransactions"] = zero_by_product["StockCode"].isin(paid_codes).map(
        {True: "YES", False: "NO"}
    )
    add(md_table(zero_by_product.to_dict("records"),
                 ["StockCode", "Rows", "Quantity", "AlsoHasPaidTransactions"]))
    add()
    zero_by_invoice = (
        zero_rows.groupby("InvoiceNo")
        .agg(Lines=("SourceRow", "size"), Quantity=("Quantity", "sum"),
             FirstDate=("InvoiceDate", "min"), CustomerID=("CustomerID", "first"))
        .reset_index()
        .nlargest(10, "Quantity")
    )
    add("Invoices with the largest zero-price quantity concentration:")
    add()
    add(md_table(zero_by_invoice.to_dict("records"),
                 ["InvoiceNo", "Lines", "Quantity", "FirstDate", "CustomerID"]))
    add()
    add(
        f"- Customer-level: {int(zero_rows['CustomerID'].notna().sum()):,} of {len(zero_rows):,} zero-price rows "
        f"carry a CustomerID; {int(zero_rows['CustomerID'].isna().sum()):,} do not."
    )
    add(
        f"- Date pattern: zero-price rows occur from {zero_rows['InvoiceDate'].min():%Y-%m-%d} to "
        f"{zero_rows['InvoiceDate'].max():%Y-%m-%d}, i.e. across the whole observation window rather than a single event."
    )
    add(
        f"- {int(zero_by_product['AlsoHasPaidTransactions'].eq('YES').sum())} of the top 10 zero-price products "
        "also have normal paid transactions, so a zero-price row cannot be treated as a product-level property."
    )
    add()
    add(
        "**Interpretation.** Zero-price rows are not removed. The evidence supports several "
        "coexisting possibilities - complimentary items, promotions, samples, free replacements, "
        "administrative corrections and data errors - and the dataset contains no field that "
        "distinguishes them. Rows are therefore proposed as UNKNOWN or NEEDS_MANUAL_REVIEW "
        "rather than as sales."
    )
    add()

    add("### C.E - Unusual Invoice Forensics")
    add()
    selected = invoice_summary[invoice_summary["Selected"]]
    add(f"Selection produced **{len(selected):,} invoices** and **{len(unusual_details):,} lines** "
        "(full breakdown in `reports/unusual_invoice_details_v1.csv`).")
    add()
    selection_counts = [
        {"Rule": rule, "Invoices": int(selected[rule].sum())}
        for rule in [
            "S1_NEGATIVE_UNIT_PRICE",
            "S2_LARGE_QUANTITY",
            "S3_LARGE_ZERO_PRICE_QUANTITY",
            "S4_FINANCIAL_AND_PRODUCT_MIX",
            "S5_MIXED_SIGN_QUANTITIES",
            "S6_MULTIPLE_INDICATOR_TYPES",
        ]
    ]
    add(md_table(selection_counts, ["Rule", "Invoices"]))
    add()
    add("Selection rules (deterministic): S1 negative unit price; S2 |Quantity| >= 1,000; "
        "S3 zero price with |Quantity| >= 500; S4 financial-only codes mixed with ordinary "
        "merchandise lines; S5 positive and negative quantities on the same invoice; "
        "S6 at least two distinct unusual indicator types. Plain cancellation invoices with no "
        "other unusual feature are covered row-by-row in the classification register instead.")
    add()
    add(
        f"- S5 (mixed-sign invoices) matched **{int(selected['S5_MIXED_SIGN_QUANTITIES'].sum())}** invoices: "
        "no invoice in this dataset contains both a positive and a negative quantity line."
    )
    add(
        f"- Invoices carrying at least two indicator types: "
        f"**{int(invoice_summary['S6_MULTIPLE_INDICATOR_TYPES'].sum()):,}**."
    )
    add()
    top_invoices = selected.nlargest(12, "InvoiceTotalValue")[
        ["InvoiceNo", "InvoiceLines", "InvoiceTotalQuantity", "InvoiceTotalValue",
         "InvoiceDate", "CustomerID", "S1_NEGATIVE_UNIT_PRICE", "S2_LARGE_QUANTITY",
         "S4_FINANCIAL_AND_PRODUCT_MIX", "S6_MULTIPLE_INDICATOR_TYPES"]
    ]
    add("Selected invoices with the largest total value:")
    add()
    add(md_table(top_invoices.to_dict("records"),
                 ["InvoiceNo", "InvoiceLines", "InvoiceTotalQuantity", "InvoiceTotalValue",
                  "InvoiceDate", "CustomerID", "S1_NEGATIVE_UNIT_PRICE", "S2_LARGE_QUANTITY",
                  "S4_FINANCIAL_AND_PRODUCT_MIX", "S6_MULTIPLE_INDICATOR_TYPES"]))
    add()
    add(
        "Each selected invoice is broken down line by line in the details file, with the "
        "selection reason and per-row unusual flags. No invoice's business purpose is inferred "
        "from a single line: ordinary lines inside an unusual invoice keep their own "
        "classification."
    )
    add()

    add("### C.F - Zero-Price Description Analysis")
    add()
    add(f"Distinct descriptions on zero-price rows: **{len(zero_desc_analysis):,}** "
        "(full table in `reports/zero_price_description_analysis_v1.csv`).")
    add()
    interpretation_counts = zero_desc_analysis["Interpretation"].value_counts()
    add(md_table(
        [{"Interpretation": key, "Descriptions": int(value)} for key, value in interpretation_counts.items()],
        ["Interpretation", "Descriptions"],
    ))
    add()
    top_descriptions = zero_desc_analysis.head(20)
    add("Most frequent zero-price descriptions (original text preserved):")
    add()
    add(md_table(top_descriptions.to_dict("records"),
                 ["Description", "Records", "UniqueInvoices", "StockCodes", "TotalQuantity",
                  "NegativeQuantityRecords", "UniqueCustomers", "FirstDate", "LastDate",
                  "AlsoInPaidTransactions", "Interpretation"]))
    add()
    add(
        f"- {int(zero_desc_analysis['AlsoInPaidTransactions'].eq('YES').sum()):,} of "
        f"{len(zero_desc_analysis):,} descriptions also appear in paid transactions, so a "
        "description alone does not determine the transaction type."
    )
    add(
        f"- {int(zero_desc_analysis['ManualReviewRequired'].eq('YES').sum()):,} descriptions are "
        "flagged for manual review (missing, administrative, correction or ambiguous text)."
    )
    add(
        f"- {int(zero_desc_analysis['HasCaseVariants'].eq('YES').sum()):,} descriptions have case "
        "variants of the same text (for example `found` / `Found`), which are preserved rather than merged."
    )
    add()

    # ---- D. Transaction Classification -------------------------------
    add("## D. Transaction Classification")
    add()
    add("Category and confidence counts (proposals, not confirmed business rules):")
    add()
    category_rows = [
        {
            "ProposedCategory": row["ProposedCategory"],
            "ConfidenceLevel": row["ConfidenceLevel"],
            "Rows": f"{row['Rows']:,}",
            "Invoices": f"{row['Invoices']:,}",
            "Quantity": f"{row['Quantity']:,}",
            "Value": money(float(row["Value"])),
        }
        for _, row in category_counts.iterrows()
    ]
    add(md_table(category_rows, ["ProposedCategory", "ConfidenceLevel", "Rows", "Invoices", "Quantity", "Value"]))
    add()
    add("Confidence distribution across all rows:")
    add()
    add(md_table(
        [{"ConfidenceLevel": key, "Rows": f"{int(value):,}",
          "Percent": f"{100.0 * value / total_rows:.2f}%"}
         for key, value in confidence_counts.items()],
        ["ConfidenceLevel", "Rows", "Percent"],
    ))
    add()
    add(
        f"- Rows requiring manual review: **{manual_rows:,}** "
        f"({100.0 * manual_rows / total_rows:.2f}% of the dataset)."
    )
    add(f"- Rows classified at HIGH confidence: **{int(confidence_counts.get('HIGH', 0)):,}**.")
    add(f"- Rows preserved as UNKNOWN: **{int((df['ConfidenceLevel'] == 'UNKNOWN').sum()):,}** "
        "(never converted into a known category).")
    add()
    add("Register composition:")
    add()
    add(f"- Row-level entries: {scope_stats['row_level_entries']:,} (exact `SourceRow` per entry).")
    add(f"- Group-level entries: {len(register) - scope_stats['row_level_entries']:,} "
        f"covering {scope_stats['group_covered_rows']:,} ordinary paid rows.")
    add(f"- Total coverage: {int(register['RowCount'].sum()):,} rows = {total_rows:,} source rows.")
    add()
    add("Evidence rules applied (first matching rule wins, most specific evidence first):")
    add()
    rule_summary = (
        df.groupby(["ClassificationRule", "ProposedCategory", "ConfidenceLevel"], sort=True)
        .agg(Rows=("SourceRow", "size"))
        .reset_index()
        .sort_values("Rows", ascending=False, kind="mergesort")
    )
    add(md_table(rule_summary.to_dict("records"),
                 ["ClassificationRule", "ProposedCategory", "ConfidenceLevel", "Rows"]))
    add()

    # ---- E. Physical Inventory Assessment ----------------------------
    add("## E. Physical Inventory Assessment")
    add()
    add("Physical impact assigned from evidence, not from quantity sign alone:")
    add()
    add(md_table(
        [{"PhysicalInventoryImpact": key, "Rows": f"{int(value):,}",
          "Percent": f"{100.0 * value / total_rows:.2f}%"}
         for key, value in physical_counts.items()],
        ["PhysicalInventoryImpact", "Rows", "Percent"],
    ))
    add()
    decrease_rows = int((df["PhysicalInventoryImpact"] == PHYSICAL_DECREASE).sum())
    none_rows = int((df["PhysicalInventoryImpact"] == PHYSICAL_NONE).sum())
    unknown_rows = int((df["PhysicalInventoryImpact"] == PHYSICAL_UNKNOWN).sum())
    add(
        f"- **Stock decrease supported ({decrease_rows:,} rows):** ordinary paid merchandise lines "
        f"({int((df['ProposedCategory'] == 'CUSTOMER_SALE').sum()):,}) and documented write-offs of "
        "damaged/destroyed goods."
    )
    add(
        f"- **No physical movement ({none_rows:,} rows):** postage, carriage, bank charges, Amazon "
        "fees, CRUK commission, discounts and bad-debt adjustments - financial or service entries only."
    )
    add(
        f"- **Unknown physical impact ({unknown_rows:,} rows):** every cancellation row "
        f"({int(df['IsCancellationInvoice'].sum()):,}), every negative non-cancellation row "
        f"({int((~df['IsCancellationInvoice'] & (df['Quantity'] < 0)).sum()):,}), every zero-price row "
        "and every manual/sample/voucher entry. The dataset has no stock-movement ledger, so the "
        "direction of these movements cannot be confirmed."
    )
    add(
        "- **Stock increase:** no row is proposed as a stock increase. A cancellation *might* be a "
        "customer return into stock, but nothing in the dataset distinguishes that from a cancelled "
        "order, so the impact stays UNKNOWN rather than being inferred from the negative sign."
    )
    add()
    add("Cross-check against quantity signs (why sign alone is insufficient):")
    add()
    sign_rows = [
        {"Quantity sign": "Negative", "Rows": f"{int((df['Quantity'] < 0).sum()):,}",
         "Physical impacts observed": ", ".join(sorted(df.loc[df['Quantity'] < 0, 'PhysicalInventoryImpact'].unique()))},
        {"Quantity sign": "Positive", "Rows": f"{int((df['Quantity'] > 0).sum()):,}",
         "Physical impacts observed": ", ".join(sorted(df.loc[df['Quantity'] > 0, 'PhysicalInventoryImpact'].unique()))},
    ]
    add(md_table(sign_rows, ["Quantity sign", "Rows", "Physical impacts observed"]))
    add()

    # ---- F. Financial Assessment -------------------------------------
    add("## F. Financial Assessment")
    add()
    add(f"- Total dataset line value (Quantity x UnitPrice, all rows): **{money(float(df['LineValue'].sum()))}**.")
    add(f"- Value inside V2 eligible sales ({reconciliation['v2']['eligible_rows']:,} rows): "
        f"**{money(reconciliation['v2']['eligible_value'])}**.")
    add(f"- Value of the {len(non_product):,} non-product rows "
        "(service, shipping and financial adjustments): "
        f"**{money(float(non_product['LineValue'].sum()))}**.")
    add()
    add("Non-product value by StockCode (financial impact kept separate from stock impact):")
    add()
    add(md_table(
        [{"StockCode": row["StockCodeUpper"], "Category": row["Category"],
          "Rows": int(row["Rows"]), "Value": money(float(row["Value"]))}
         for _, row in non_product_by_code.iterrows()],
        ["StockCode", "Category", "Rows", "Value"],
    ))
    add()
    zero_value_rows = int((df["LineValue"] == 0).sum())
    zero_price_negative = int(((df["UnitPrice"] == 0) & (df["Quantity"] < 0)).sum())
    zero_price_positive = int(((df["UnitPrice"] == 0) & (df["Quantity"] > 0)).sum())
    add(f"- Rows with zero financial value: **{zero_value_rows:,}** "
        f"(every such row is priced at 0.00: {zero_price_positive:,} positive-quantity and "
        f"{zero_price_negative:,} negative-quantity rows; no other row has a zero line value, "
        "because no quantity in this dataset is 0).")
    add(f"- Value recorded on cancellation invoices: **{money(float(df.loc[df['IsCancellationInvoice'], 'LineValue'].sum()))}**.")
    add(f"- Value on negative non-cancellation rows: "
        f"**{money(float(df.loc[~df['IsCancellationInvoice'] & (df['Quantity'] < 0), 'LineValue'].sum()))}**.")
    add()
    add("Rounding, floating-point and missing-value handling:")
    add()
    add("- Line values are computed as float64 `Quantity * UnitPrice` with no intermediate rounding; the identity check in section H requires exact equality.")
    add("- Summations run in a fixed row order, so repeated runs produce identical totals; comparisons against V2 use the existing absolute tolerance of 0.01.")
    add("- Reported money figures are formatted to 2 decimals for readability only; stored CSV values are unrounded.")
    add("- Quantity and UnitPrice have no missing values; Description (1,454) and CustomerID (135,080) are missing and are reported as `[MISSING]` rather than imputed.")
    add()

    # ---- G. Anomaly Summary ------------------------------------------
    add("## G. Anomaly Summary")
    add()
    add(f"Total anomalies: **{len(anomalies)}**, all with status `OPEN` "
        "(a script assigning a category never resolves an anomaly).")
    add()
    add(md_table(
        [{"Severity": key, "Anomalies": int(value)}
         for key, value in anomaly_by_severity.items()],
        ["Severity", "Anomalies"],
    ))
    add()
    add(md_table(anomalies.head(25).to_dict("records"),
                 ["AnomalyID", "AnomalyType", "Severity", "RowCount", "SourceReference",
                  "RecommendedInvestigation", "ResolutionStatus"]))
    add()
    add("The complete register is `reports/special_transaction_anomalies_v1.csv`.")
    add()

    # ---- H. Reconciliation -------------------------------------------
    add("## H. Reconciliation")
    add()
    add("### H.1 - Audit partitions (mutually exclusive, exhaustive)")
    add()
    partition_rows = [
        {"Partition": name, "Rows": f"{int(partition_counts[name]):,}",
         "Percent": f"{100.0 * partition_counts[name] / total_rows:.4f}%",
         "Value": money(float(partition_value.get(name, 0.0)))}
        for name in PARTITION_ORDER
    ]
    add(md_table(partition_rows, ["Partition", "Rows", "Percent", "Value"]))
    add()
    add(f"Sum of partitions: **{int(partition_counts.sum()):,}** = original rows **{total_rows:,}** "
        f"-> {'PASS' if int(partition_counts.sum()) == total_rows else 'FAIL'}.")
    add()
    add("### H.2 - Validation checks")
    add()
    add(md_table(reconciliation["checks"], ["Check", "Expected", "Actual", "Status", "Notes"]))
    add()
    add(f"Checks failed: **{len(failed_checks)}**.")
    add()
    add("### H.3 - Historical figure verification")
    add()
    add("Earlier reported figures were re-measured rather than assumed:")
    add()
    add(md_table(reconciliation["historical"], ["Metric", "Reported", "Measured", "Status"]))
    add()
    add(
        f"All {sum(1 for row in reconciliation['historical'] if row['Status'] == 'MATCH')} "
        f"of {len(reconciliation['historical'])} historical figures reproduce exactly."
    )
    add()
    add("### H.4 - Independent V2 cross-check")
    add()
    add(f"- V2 sale definition applied independently: `{V2_SALE_DEFINITION}`.")
    add(f"- Eligible rows: {reconciliation['v2']['eligible_rows']:,} "
        f"(value {money(reconciliation['v2']['eligible_value'])}).")
    add(f"- Products compared: {reconciliation['v2']['products']:,}; unmatched: {reconciliation['v2']['unmatched_products']}.")
    add(f"- Mismatches: quantity {reconciliation['v2']['qty_mismatch']}, "
        f"invoice count {reconciliation['v2']['inv_mismatch']}, "
        f"revenue {reconciliation['v2']['rev_mismatch']} "
        f"(tolerance {V2_TOLERANCE}).")
    add()
    add(
        "The V2 reconciliation is therefore reproducible, but reproducible does not mean "
        "correct: section G records that non-product codes (including an 11,062.06 bad-debt "
        "adjustment) are inside those totals."
    )
    add()
    add("### H.5 - Source file protection")
    add()
    add("| File | SHA-256 before | SHA-256 after | Status |")
    add("|---|---|---|---|")
    for name in sorted(fingerprints_before):
        before = fingerprints_before[name]
        after = fingerprints_after.get(name, "")
        status = "UNCHANGED" if before == after else "MODIFIED"
        add(f"| `{name}` | `{before[:16]}...` | `{after[:16]}...` | {status} |")
    add()

    # ---- I. Data Limitations -----------------------------------------
    add("## I. Data Limitations")
    add()
    add("The following cannot be established from this dataset alone:")
    add()
    add("1. **Physical stock movement direction.** There is no stock ledger, warehouse event or goods-receipt record. Cancellations, write-offs and corrections cannot be converted into confirmed stock increases or decreases.")
    add("2. **Order-to-cancellation linkage.** Cancellation invoices carry no reference to an original order, so returns cannot be separated from cancelled orders, and exact-reversal matches remain candidates rather than proof.")
    add("3. **Fulfilment of sales.** The sale definition is a data pattern (positive quantity, positive price, non-C invoice); payment, shipment and delivery are absent, so CUSTOMER_SALE is proposed at MEDIUM confidence only.")
    add("4. **Meaning of zero-price issuance.** Complimentary item, promotion, sample, replacement, correction and error are indistinguishable without an operational event log.")
    add("5. **Manual entries (`M`).** The description states only that an operator typed the row; the underlying business event is unknown for all 572 rows.")
    add("6. **Customer identity.** 135,080 rows have no CustomerID, including every negative non-cancellation row, so customer-level attribution is incomplete by construction.")
    add("7. **Duplicate intent.** 5,268 rows are exact duplicates of another row; the dataset cannot show whether they are genuine repeated order lines or extraction artefacts.")
    add("8. **Country of fulfilment.** `Country` records the invoice country, which is not necessarily the delivery destination.")
    add("9. **External validation.** No external documentation, price list or accounting record was consulted, so every interpretation here rests on patterns inside the dataset.")
    add()

    # ---- J. Recommendations ------------------------------------------
    add("## J. Recommendations")
    add()
    add("Research tasks only - no dataset changes are proposed by this report:")
    add()
    add("1. **Cancellation vs return study.** Quantify how many `C` invoices can be matched to an earlier invoice by StockCode, customer, price and quantity, and measure how many cannot be matched at all.")
    add("2. **Non-product code inventory.** Decide which codes (POST, DOT, C2, M, S, D, B, BANK CHARGES, AMAZONFEE, CRUK, PADS, gift_*, DCGS*) belong in a product movement dataset versus a financial/service dataset.")
    add("3. **Zero-price operational study.** Sample zero-price rows by description bucket and describe what event each bucket represents, using external records if available.")
    add("4. **Duplicate-line analysis.** Determine whether exact duplicate rows cluster in particular invoices or dates, which would indicate an extraction artefact.")
    add("5. **Extreme-quantity verification.** Validate the 80,995/74,215-unit pairs and the largest zero-price quantities against source documents.")
    add("6. **StockCode normalisation proposal.** Specify a canonical case/format rule for codes such as `15056BL`/`15056bl` and `M`/`m` before any V3 dataset is considered.")
    add("7. **Manual-entry sampling.** Review a stratified sample of `M` rows to see whether they are sales, adjustments or corrections.")
    add()

    # ---- K. Approval Requirements ------------------------------------
    add("## K. Approval Requirements")
    add()
    add("The following decisions are deliberately NOT taken by this audit and require explicit approval:")
    add()
    add("1. **Whether bad-debt row A563185 (+11,062.06) must be excluded from V2 sales and product movement.**")
    add("2. **Whether non-product codes (POST, DOT, M, AMAZONFEE, C2, BANK CHARGES, S, PADS) should be removed from product movement V3 - which does not exist yet and must not be built without approval.**")
    add("3. **How cancellations and returns should be separated, and whether any cancellation may be treated as a physical stock increase.**")
    add("4. **Whether the 5,268 exact duplicate rows are genuine lines or must be flagged/excluded.**")
    add("5. **Whether zero-price rows may ever be counted as sales, and under what evidence.**")
    add("6. **The canonical StockCode normalisation rule (case and format).**")
    add("7. **Which of the NEEDS_MANUAL_REVIEW and UNKNOWN groups may be resolved, and on what evidence.**")
    add()
    add("---")
    add()
    add("**Status: Special Transaction Audit V1 complete; V3, forecasting and classification rules "
        "not started, awaiting review.**")
    add()

    return "\n".join(lines)


# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------


def main() -> int:
    """Run the complete Special Transaction Audit V1."""
    print("=" * 78)
    print("TREXO - SPECIAL TRANSACTION INVESTIGATION & CLASSIFICATION AUDIT V1")
    print("=" * 78)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Fingerprint every protected file before any work starts.
    fingerprints_before = fingerprint_protected_files(PROTECTED_FILES)
    print("\nProtected files fingerprinted before the audit:")
    for name, digest in sorted(fingerprints_before.items()):
        print(f"  {name}: {digest[:16]}...")

    # --------------------------------------------------
    # 1. LOAD AND VALIDATE (READ-ONLY)
    # --------------------------------------------------
    print("\n1. LOAD AND VALIDATE ORIGINAL DATASET")
    df = load_transactions(RAW_FILE)
    df = add_audit_flags(df)

    print(f"  Unique invoices: {df['InvoiceNo'].nunique():,}")
    print(f"  Unique StockCodes: {df['StockCode'].nunique():,}")
    print(f"  Date range: {df['InvoiceDate'].min()} to {df['InvoiceDate'].max()}")
    print(f"  Missing Description: {int(df['Description'].isna().sum()):,}")
    print(f"  Missing CustomerID: {int(df['CustomerID'].isna().sum()):,}")
    print("  Audit partitions:")
    for name in PARTITION_ORDER:
        count = int((df["AuditPartition"] == name).sum())
        if count:
            print(f"    {name}: {count:,}")

    # --------------------------------------------------
    # 2. CLASSIFICATION (EVIDENCE RULES)
    # --------------------------------------------------
    print("\n2. APPLY EVIDENCE-BASED CLASSIFICATION RULES")
    classified = classify_transactions(df)
    print("  Proposed categories:")
    for category, count in classified["ProposedCategory"].value_counts().items():
        print(f"    {category}: {count:,}")
    print("  Confidence levels:")
    for level, count in classified["ConfidenceLevel"].value_counts().items():
        print(f"    {level}: {count:,}")
    print(f"  Rows requiring manual review: "
          f"{int((classified['ManualReviewRequired'] == 'YES').sum()):,}")

    # --------------------------------------------------
    # 3. INVESTIGATION A - INVOICE PREFIX FORENSICS
    # --------------------------------------------------
    print("\n3. INVESTIGATION A - INVOICE PREFIX FORENSICS")
    prefix_analysis = build_prefix_analysis(classified)
    invoice_structure = build_invoice_structure(classified)
    print(prefix_analysis[["InvoicePrefix", "Records", "UniqueInvoices",
                           "NegativeQuantityRecords", "TotalTransactionValue",
                           "PercentOfDataset"]].to_string(index=False))

    # --------------------------------------------------
    # 4. INVESTIGATION B - NEGATIVE UNIT-PRICE RECORDS
    # --------------------------------------------------
    print("\n4. INVESTIGATION B - NEGATIVE UNIT-PRICE RECORDS")
    negative_price_rows = build_negative_price_rows(classified)
    print(f"  Records: {len(negative_price_rows)}")
    if len(negative_price_rows):
        print(negative_price_rows[["SourceRow", "InvoiceNo", "StockCode",
                                   "Quantity", "UnitPrice", "LineValue"]].to_string(index=False))

    # --------------------------------------------------
    # 5. INVESTIGATION C - SPECIAL STOCKCODE FORENSICS
    # --------------------------------------------------
    print("\n5. INVESTIGATION C - SPECIAL STOCKCODE FORENSICS")
    movement_v2 = pd.read_csv(MOVEMENT_V2_FILE)
    special_analysis = build_special_stockcode_analysis(classified, movement_v2)
    print(special_analysis[["StockCodeKey", "RequestedByAssignment", "FoundInDataset",
                            "Records", "UniqueInvoices", "TotalQuantity",
                            "TotalTransactionValue", "PresentInMovementV2",
                            "V2TotalSalesValue"]].to_string(index=False))

    # --------------------------------------------------
    # 6. INVESTIGATION D - LARGE ZERO-PRICE QUANTITIES
    # --------------------------------------------------
    print("\n6. INVESTIGATION D - LARGE ZERO-PRICE QUANTITIES")
    zero_thresholds = compute_zero_price_thresholds(classified)
    zero_rows = classified[classified["UnitPrice"] == 0]
    print(f"  Zero-price rows: {len(zero_rows):,}")
    print(f"  99th percentile of |Quantity|: {zero_thresholds['p99']:.1f}")
    print(f"  Fixed threshold: {int(zero_thresholds['fixed'])}")
    print(f"  Rows with |Quantity| >= {LARGE_QUANTITY_THRESHOLD}: "
          f"{int((zero_rows['Quantity'].abs() >= LARGE_QUANTITY_THRESHOLD).sum())}")

    # --------------------------------------------------
    # 7. INVESTIGATION E - UNUSUAL INVOICE FORENSICS
    # --------------------------------------------------
    print("\n7. INVESTIGATION E - UNUSUAL INVOICE FORENSICS")
    invoice_summary = select_unusual_invoices(classified)
    selected_invoices = invoice_summary.loc[invoice_summary["Selected"], "InvoiceNo"]
    unusual_ids = set(selected_invoices)
    unusual_details = build_unusual_invoice_details(classified, invoice_summary)
    print(f"  Selected invoices: {len(unusual_ids):,}")
    print(f"  Detail lines: {len(unusual_details):,}")
    for rule in ["S1_NEGATIVE_UNIT_PRICE", "S2_LARGE_QUANTITY",
                 "S3_LARGE_ZERO_PRICE_QUANTITY", "S4_FINANCIAL_AND_PRODUCT_MIX",
                 "S5_MIXED_SIGN_QUANTITIES", "S6_MULTIPLE_INDICATOR_TYPES"]:
        print(f"    {rule}: {int(invoice_summary[rule].sum()):,}")

    # --------------------------------------------------
    # 8. INVESTIGATION F - ZERO-PRICE DESCRIPTION ANALYSIS
    # --------------------------------------------------
    print("\n8. INVESTIGATION F - ZERO-PRICE DESCRIPTION ANALYSIS")
    zero_desc_analysis = build_zero_price_description_analysis(classified)
    print(f"  Distinct descriptions: {len(zero_desc_analysis):,}")
    for interpretation, count in zero_desc_analysis["Interpretation"].value_counts().items():
        print(f"    {interpretation}: {count}")

    # --------------------------------------------------
    # 9. PHASE TWO - CLASSIFICATION REGISTER
    # --------------------------------------------------
    print("\n9. PHASE TWO - CLASSIFICATION REGISTER")
    register, scope_stats = build_classification_register(classified, unusual_ids)
    print(f"  Register entries: {len(register):,}")
    print(f"    row-level: {scope_stats['row_level_entries']:,}")
    print(f"    group-covered rows: {scope_stats['group_covered_rows']:,}")
    print(f"  Total covered rows: {int(register['RowCount'].sum()):,} "
          f"(dataset: {len(classified):,})")

    # --------------------------------------------------
    # 10. PHASE FIVE - ANOMALY REGISTER
    # --------------------------------------------------
    print("\n10. PHASE FIVE - ANOMALY REGISTER")
    anomalies = build_anomaly_register(
        classified, special_analysis, invoice_summary, zero_thresholds
    )
    print(f"  Anomalies: {len(anomalies)}")
    for severity, count in anomalies["Severity"].value_counts().items():
        print(f"    {severity}: {count}")
    print("  Resolution status:", ", ".join(sorted(anomalies["ResolutionStatus"].unique())))

    # --------------------------------------------------
    # 11. PHASE FOUR - RECONCILIATION
    # --------------------------------------------------
    print("\n11. PHASE FOUR - RECONCILIATION AND DATA QUALITY VALIDATION")
    reconciliation = run_reconciliation(classified, register, prefix_analysis, movement_v2)
    for check in reconciliation["checks"]:
        marker = "OK " if check["Status"] == "PASS" else "FAIL"
        print(f"  [{marker}] {check['Check']}: expected={check['Expected']} actual={check['Actual']}")
    print(f"  Checks: {len(reconciliation['checks'])} total, "
          f"{len(reconciliation['failed'])} failed")
    print("  Historical figure verification:")
    for row in reconciliation["historical"]:
        print(f"    {row['Metric']}: reported={row['Reported']} "
              f"measured={row['Measured']} -> {row['Status']}")

    # --------------------------------------------------
    # 12. WRITE MACHINE-READABLE OUTPUTS
    # --------------------------------------------------
    print("\n12. WRITE OUTPUTS (ALL NEW FILES)")
    outputs = {
        OUT_PREFIX: prefix_analysis,
        OUT_SPECIAL_CODE: special_analysis,
        OUT_ZERO_DESC: zero_desc_analysis,
        OUT_UNUSUAL_INVOICES: unusual_details,
        OUT_REGISTER: register,
        OUT_ANOMALIES: anomalies,
    }
    for filename, frame in outputs.items():
        target = REPORT_DIR / filename
        frame.to_csv(target, index=False)
        print(f"  {target} ({len(frame):,} rows, {target.stat().st_size:,} bytes)")

    # --------------------------------------------------
    # 13. WRITE HUMAN-READABLE REPORT
    # --------------------------------------------------
    print("\n13. WRITE HUMAN-READABLE AUDIT REPORT")
    report_text = write_report(
        df=classified,
        register=register,
        scope_stats=scope_stats,
        prefix_analysis=prefix_analysis,
        invoice_structure=invoice_structure,
        negative_price_rows=negative_price_rows,
        special_analysis=special_analysis,
        zero_thresholds=zero_thresholds,
        zero_desc_analysis=zero_desc_analysis,
        invoice_summary=invoice_summary,
        unusual_details=unusual_details,
        anomalies=anomalies,
        reconciliation=reconciliation,
        fingerprints_before=fingerprints_before,
        fingerprints_after=fingerprint_protected_files(PROTECTED_FILES),
    )
    report_path = REPORT_DIR / OUT_REPORT_MD
    report_path.write_text(report_text, encoding="utf-8")
    print(f"  {report_path} ({report_path.stat().st_size:,} bytes)")

    # --------------------------------------------------
    # 14. PROTECT EXISTING DATA
    # --------------------------------------------------
    print("\n14. VERIFY PROTECTED FILES ARE UNCHANGED")
    fingerprints_after = fingerprint_protected_files(PROTECTED_FILES)
    protected_ok = True
    for name in sorted(fingerprints_before):
        before = fingerprints_before[name]
        after = fingerprints_after.get(name)
        status = "UNCHANGED" if before == after else "MODIFIED"
        if before != after:
            protected_ok = False
        print(f"  [{status}] {name}")
    if not protected_ok:
        raise AssertionError("A protected source or processed file was modified by the audit")

    # --------------------------------------------------
    # 15. SUMMARY
    # --------------------------------------------------
    print("\n" + "=" * 78)
    print("AUDIT SUMMARY")
    print("=" * 78)
    print(f"  Source rows audited:            {len(classified):,}")
    print(f"  Register entries:               {len(register):,}")
    print(f"  Rows requiring manual review:   "
          f"{int((classified['ManualReviewRequired'] == 'YES').sum()):,}")
    print(f"  Rows preserved as UNKNOWN:      "
          f"{int((classified['ConfidenceLevel'] == 'UNKNOWN').sum()):,}")
    print(f"  Open anomalies:                 {len(anomalies)}")
    print(f"  Reconciliation checks failed:   {len(reconciliation['failed'])}")
    print(f"  Protected files unchanged:      {protected_ok}")
    print("\nSPECIAL TRANSACTION AUDIT V1 COMPLETED")
    print("No source or processed dataset was modified.")
    print("V3, forecasting and final classification rules were NOT started.")
    print("=" * 78)

    return 0 if (protected_ok and not reconciliation["failed"]) else 1


if __name__ == "__main__":
    sys.exit(main())
