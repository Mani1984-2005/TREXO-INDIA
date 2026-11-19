
import pandas as pd
import numpy as np

RAW_FILE = "data/raw/Online Retail.xlsx"

print("=" * 78)
print("TREXO - UNRESOLVED TRANSACTION INVESTIGATION V1")
print("=" * 78)

df = pd.read_excel(RAW_FILE, engine="openpyxl")

df["InvoiceNo"] = df["InvoiceNo"].astype(str).str.strip()
df["StockCode"] = df["StockCode"].astype(str).str.strip()
df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce")
df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")

is_cancel = df["InvoiceNo"].str.startswith("C")
is_negative = df["Quantity"] < 0
is_positive = df["Quantity"] > 0

# --------------------------------------------------
# 1. THE TWO OTHER / INVALID ROWS
# --------------------------------------------------

print("\n1. OTHER OR INVALID TRANSACTIONS")

invalid = df[
    ~(is_cancel & is_negative)
    & ~(is_cancel & is_positive)
    & ~(~is_cancel & is_negative)
    & ~(~is_cancel & is_positive & (df["UnitPrice"] == 0))
    & ~(~is_cancel & is_positive & (df["UnitPrice"] > 0))
].copy()

print("Rows:", len(invalid))

print(
    invalid[
        ["InvoiceNo", "StockCode", "Description", "Quantity",
         "UnitPrice", "InvoiceDate", "CustomerID", "Country"]
    ].to_string(index=False)
)

# --------------------------------------------------
# 2. POSITIVE ZERO-PRICE TRANSACTIONS
# --------------------------------------------------

print("\n2. ZERO-PRICE POSITIVE TRANSACTIONS")

zero = df[
    (~is_cancel)
    & is_positive
    & (df["UnitPrice"] == 0)
].copy()

zero["DescriptionGroup"] = (
    zero["Description"]
    .fillna("[MISSING]")
    .astype(str)
    .str.strip()
    .str.lower()
)

print("\nSummary:")
print("Rows:", len(zero))
print("Total quantity:", zero["Quantity"].sum())
print("Unique products:", zero["StockCode"].nunique())
print("Unique invoices:", zero["InvoiceNo"].nunique())
print("Unique customers:", zero["CustomerID"].nunique())
print("Missing descriptions:", zero["Description"].isna().sum())
print("Missing customers:", zero["CustomerID"].isna().sum())

print("\nTop 30 description groups:")

print(
    zero.groupby("DescriptionGroup").agg(
        Rows=("Quantity", "size"),
        TotalQuantity=("Quantity", "sum"),
        Products=("StockCode", "nunique"),
        Invoices=("InvoiceNo", "nunique"),
        Customers=("CustomerID", "nunique")
    ).sort_values("Rows", ascending=False).head(30).to_string()
)

print("\nZero-price transactions with meaningful descriptions:")

meaningful = zero[
    zero["Description"].notna()
    & ~zero["DescriptionGroup"].isin(["", "?", "??"])
]

print(
    meaningful[
        ["InvoiceNo", "StockCode", "Description", "Quantity",
         "InvoiceDate", "CustomerID", "Country"]
    ].head(50).to_string(index=False)
)

print("\nLargest zero-price quantities:")

print(
    zero.sort_values("Quantity", ascending=False)[
        ["InvoiceNo", "StockCode", "Description", "Quantity",
         "InvoiceDate", "CustomerID", "Country"]
    ].head(30).to_string(index=False)
)

# --------------------------------------------------
# 3. NEGATIVE TRANSACTIONS WITH MISSING DESCRIPTIONS
# --------------------------------------------------

print("\n3. NEGATIVE NON-C TRANSACTIONS WITH MISSING DESCRIPTIONS")

missing_negative = df[
    (~is_cancel)
    & is_negative
    & (
        df["Description"].isna()
        | df["Description"].astype(str).str.strip().eq("")
    )
].copy()

print("Rows:", len(missing_negative))
print("Total negative quantity:", missing_negative["Quantity"].sum())
print("Unique products:", missing_negative["StockCode"].nunique())
print("Unique invoices:", missing_negative["InvoiceNo"].nunique())
print("Unique customers:", missing_negative["CustomerID"].nunique())

print("\nFirst 60 rows in date order:")

print(
    missing_negative.sort_values("InvoiceDate")[
        ["InvoiceNo", "StockCode", "Quantity", "UnitPrice",
         "InvoiceDate", "CustomerID", "Country"]
    ].head(60).to_string(index=False)
)

print("\nProducts with the largest missing-description adjustments:")

print(
    missing_negative.groupby("StockCode").agg(
        Rows=("Quantity", "size"),
        TotalQuantity=("Quantity", "sum"),
        FirstDate=("InvoiceDate", "min"),
        LastDate=("InvoiceDate", "max")
    ).sort_values("TotalQuantity").head(25).to_string()
)

# --------------------------------------------------
# 4. ZERO-PRICE INVOICE PATTERNS
# --------------------------------------------------

print("\n4. ZERO-PRICE INVOICE PATTERNS")

zero_invoice = zero.groupby("InvoiceNo").agg(
    Rows=("Quantity", "size"),
    TotalQuantity=("Quantity", "sum"),
    Products=("StockCode", "nunique"),
    Customers=("CustomerID", "nunique"),
    InvoiceDate=("InvoiceDate", "min")
).reset_index()

print("\nInvoice count:", len(zero_invoice))
print("Invoices with multiple rows:", (zero_invoice["Rows"] > 1).sum())
print("Largest zero-price invoices:")

print(
    zero_invoice.sort_values("TotalQuantity", ascending=False)
    .head(20).to_string(index=False)
)

print("\n" + "=" * 78)
print("UNRESOLVED TRANSACTION INVESTIGATION V1 COMPLETED")
print("No source or processed data was modified.")
print("=" * 78)
