
import pandas as pd
import numpy as np

RAW_FILE = "data/raw/Online Retail.xlsx"

print("=" * 75)
print("TREXO - TRANSACTION CLASSIFICATION AUDIT V1")
print("=" * 75)

df = pd.read_excel(RAW_FILE, engine="openpyxl")

df["InvoiceNo"] = df["InvoiceNo"].astype(str).str.strip()
df["StockCode"] = df["StockCode"].astype(str).str.strip()
df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce")

description = (
    df["Description"]
    .fillna("")
    .astype(str)
    .str.lower()
)

# --------------------------------------------------
# 1. TRANSACTION TYPE
# --------------------------------------------------

is_cancel = df["InvoiceNo"].str.startswith("C")
is_negative = df["Quantity"] < 0
is_positive = df["Quantity"] > 0
is_zero_price = df["UnitPrice"] == 0

df["TransactionType"] = np.select(
    [
        is_cancel & is_negative,
        is_cancel & is_positive,
        ~is_cancel & is_negative,
        ~is_cancel & is_positive & is_zero_price,
        ~is_cancel & is_positive & (df["UnitPrice"] > 0),
    ],
    [
        "CANCELLATION_NEGATIVE",
        "CANCELLATION_POSITIVE",
        "NON_CANCELLATION_NEGATIVE",
        "POSITIVE_ZERO_PRICE",
        "POSITIVE_PAID_SALE",
    ],
    default="OTHER_OR_INVALID"
)

print("\n1. TRANSACTION TYPE SUMMARY")

summary = df.groupby("TransactionType").agg(
    Rows=("Quantity", "size"),
    Quantity=("Quantity", "sum"),
    UniqueInvoices=("InvoiceNo", "nunique"),
    UniqueProducts=("StockCode", "nunique"),
    Revenue=("Quantity", lambda x: 0)
).reset_index()

print(summary.to_string(index=False))

# --------------------------------------------------
# 2. CLASSIFY NEGATIVE NON-CANCELLATION ROWS
# --------------------------------------------------

print("\n2. NEGATIVE NON-CANCELLATION CLASSIFICATION")

negative = df[
    df["TransactionType"] == "NON_CANCELLATION_NEGATIVE"
].copy()

desc = (
    negative["Description"]
    .fillna("")
    .astype(str)
    .str.lower()
)

rules = [
    (
        "DAMAGE_OR_DEFECT",
        r"damag|broken|faulty|mouldy|moldy|rusty|smudg"
    ),
    (
        "DISPOSAL_OR_DESTROYED",
        r"throw away|thrown away|destroyed|unsaleable|unsalable"
    ),
    (
        "STOCK_OR_ENTRY_CORRECTION",
        r"incorrect stock|wrongly marked|wrongly coded|came coded|check"
    ),
    (
        "CREDIT_OR_SUPPLIER_ADJUSTMENT",
        r"credit|asos|supplier"
    ),
    (
        "OTHER_EXPLICIT_NOTE",
        r".+"
    ),
]

conditions = [
    desc.str.contains(pattern, regex=True, na=False)
    for _, pattern in rules
]

negative["DescriptionCategory"] = np.select(
    conditions,
    [name for name, _ in rules],
    default="MISSING_OR_UNCLASSIFIED"
)

print("\nCategory summary:")

print(
    negative.groupby("DescriptionCategory").agg(
        Rows=("Quantity", "size"),
        Quantity=("Quantity", "sum"),
        Products=("StockCode", "nunique")
    ).sort_values("Rows", ascending=False).to_string()
)

print("\nMost common descriptions:")

print(
    negative["Description"]
    .fillna("[MISSING]")
    .value_counts()
    .head(30).to_string()
)

print("\nUnclassified or missing descriptions:")

print(
    negative[
        negative["DescriptionCategory"].isin(
            ["OTHER_EXPLICIT_NOTE", "MISSING_OR_UNCLASSIFIED"]
        )
    ][
        ["InvoiceNo", "StockCode", "Description",
         "Quantity", "InvoiceDate", "UnitPrice"]
    ].head(40).to_string(index=False)
)

# --------------------------------------------------
# 3. ZERO-PRICE POSITIVE TRANSACTIONS
# --------------------------------------------------

print("\n3. POSITIVE ZERO-PRICE TRANSACTIONS")

zero_price = df[
    df["TransactionType"] == "POSITIVE_ZERO_PRICE"
].copy()

print("Rows:", len(zero_price))
print("Total quantity:", zero_price["Quantity"].sum())
print("Unique products:", zero_price["StockCode"].nunique())
print("Missing descriptions:", zero_price["Description"].isna().sum())
print("Missing customers:", zero_price["CustomerID"].isna().sum())

print("\nMost common zero-price descriptions:")

print(
    zero_price["Description"]
    .fillna("[MISSING]")
    .value_counts()
    .head(30).to_string()
)

# --------------------------------------------------
# 4. FINAL CATEGORY COUNTS
# --------------------------------------------------

print("\n4. TRANSACTION QUALITY SUMMARY")

print("Negative non-C rows:", len(negative))
print("Positive zero-price rows:", len(zero_price))
print("Cancellation rows:", is_cancel.sum())
print("Positive paid sales rows:", (
    df["TransactionType"] == "POSITIVE_PAID_SALE"
).sum())

print("\nOriginal dataset rows:", len(df))

print("\n" + "=" * 75)
print("TRANSACTION CLASSIFICATION AUDIT V1 COMPLETED")
print("No source or processed data was modified.")
print("=" * 75)
