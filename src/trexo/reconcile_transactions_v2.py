
import pandas as pd
import numpy as np

RAW_FILE = "data/raw/Online Retail.xlsx"
MOVEMENT_FILE = "data/processed/product_movement_v2.csv"

print("=" * 75)
print("TREXO - TRANSACTION RECONCILIATION V2")
print("=" * 75)

# Load original data
df = pd.read_excel(RAW_FILE, engine="openpyxl")

df["InvoiceNo"] = df["InvoiceNo"].astype(str).str.strip()
df["StockCode"] = df["StockCode"].astype(str).str.strip()
df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce")
df["InvoiceDate"] = pd.to_datetime(
    df["InvoiceDate"], errors="coerce"
)

# --------------------------------------------------
# 1. RECREATE V2 FILTERING
# --------------------------------------------------

print("\n1. RECREATE ORIGINAL V2 FILTERS")

not_cancelled = ~df["InvoiceNo"].str.startswith("C")
positive_quantity = df["Quantity"] > 0
positive_price = df["UnitPrice"] > 0

eligible = df[
    not_cancelled &
    positive_quantity &
    positive_price
].copy()

print("Original rows:", len(df))
print("Rows after V2 filters:", len(eligible))
print("Excluded rows:", len(df) - len(eligible))

print("Excluded cancellation rows:",
      (~not_cancelled).sum())

print("Excluded non-positive quantity rows:",
      (not_cancelled & ~positive_quantity).sum())

print("Excluded non-positive price rows:",
      (not_cancelled & positive_quantity & ~positive_price).sum())

# --------------------------------------------------
# 2. REBUILD PRODUCT QUANTITY
# --------------------------------------------------

print("\n2. PRODUCT QUANTITY RECONCILIATION")

expected = eligible.groupby("StockCode").agg(
    ExpectedQuantity=("Quantity", "sum"),
    ExpectedInvoices=("InvoiceNo", "nunique"),
    ExpectedRevenue=("UnitPrice", lambda x: 0)
).reset_index()

# Calculate revenue independently
eligible["Revenue"] = eligible["Quantity"] * eligible["UnitPrice"]

revenue = eligible.groupby("StockCode")["Revenue"].sum()
expected["ExpectedRevenue"] = expected["StockCode"].map(revenue)

movement = pd.read_csv(MOVEMENT_FILE)
movement["StockCode"] = movement["StockCode"].astype(str).str.strip()

comparison = movement.merge(
    expected,
    on="StockCode",
    how="outer",
    indicator=True
)

print("\nProduct matching:")
print(comparison["_merge"].value_counts())

for actual, rebuilt, label in [
    ("TotalQuantitySold", "ExpectedQuantity", "Quantity"),
    ("InvoiceCount", "ExpectedInvoices", "Invoice count"),
    ("TotalSalesValue", "ExpectedRevenue", "Revenue")
]:
    difference = (
        comparison[actual] - comparison[rebuilt]
    ).abs()

    mismatches = difference.gt(0.01)

    print(f"\n{label} mismatches:", mismatches.sum())

    if mismatches.any():
        print(
            comparison.loc[
                mismatches,
                ["StockCode", actual, rebuilt]
            ].head(15).to_string(index=False)
        )

# --------------------------------------------------
# 3. INVESTIGATE NEGATIVE NON-CANCELLATION ROWS
# --------------------------------------------------

print("\n3. NEGATIVE TRANSACTIONS OUTSIDE C INVOICES")

negative_non_c = df[
    (df["Quantity"] < 0) &
    (~df["InvoiceNo"].str.startswith("C"))
].copy()

print("Rows:", len(negative_non_c))
print("Unique invoices:",
      negative_non_c["InvoiceNo"].nunique())

print("Unique products:",
      negative_non_c["StockCode"].nunique())

print("Total negative quantity:",
      negative_non_c["Quantity"].sum())

print("\nTop 30 negative transactions:")

print(
    negative_non_c.assign(
        AbsoluteQuantity=negative_non_c["Quantity"].abs()
    ).nlargest(30, "AbsoluteQuantity")[
        ["InvoiceNo", "StockCode", "Description",
         "Quantity", "InvoiceDate", "UnitPrice",
         "CustomerID", "Country"]
    ].to_string(index=False)
)

# --------------------------------------------------
# 4. NEGATIVE TRANSACTION INVOICE ANALYSIS
# --------------------------------------------------

print("\n4. NEGATIVE TRANSACTION INVOICE PATTERNS")

invoice_analysis = negative_non_c.groupby("InvoiceNo").agg(
    Rows=("Quantity", "count"),
    TotalQuantity=("Quantity", "sum"),
    UniqueProducts=("StockCode", "nunique"),
    FirstDate=("InvoiceDate", "min"),
    LastDate=("InvoiceDate", "max"),
    Customers=("CustomerID", "nunique")
).reset_index()

print("\nInvoice summary:")
print(invoice_analysis.describe(include="all").to_string())

print("\nLargest negative invoices:")

print(
    invoice_analysis.assign(
        AbsoluteQuantity=invoice_analysis["TotalQuantity"].abs()
    ).nlargest(20, "AbsoluteQuantity").to_string(index=False)
)

# --------------------------------------------------
# 5. PRODUCT 23843 CONTROL CHECK
# --------------------------------------------------

print("\n5. PRODUCT 23843 CONTROL CHECK")

print(
    comparison[
        comparison["StockCode"] == "23843"
    ].to_string(index=False)
)

print("\n" + "=" * 75)
print("TRANSACTION RECONCILIATION V2 COMPLETED")
print("Original data and V2 processed data were not modified.")
print("=" * 75)
