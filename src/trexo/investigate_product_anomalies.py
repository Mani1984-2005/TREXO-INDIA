
import pandas as pd

RAW_FILE = "data/raw/Online Retail.xlsx"
TARGET_CODE = "23843"

print("=" * 75)
print("TREXO - SOURCE LEVEL PRODUCT ANOMALY INVESTIGATION V1")
print("=" * 75)

# Load original dataset without modifying it
df = pd.read_excel(RAW_FILE, engine="openpyxl")

df["StockCode_Normalized"] = (
    df["StockCode"].astype(str).str.strip()
)

# --------------------------------------------------
# 1. INVESTIGATE TARGET PRODUCT
# --------------------------------------------------

product = df[
    df["StockCode_Normalized"] == TARGET_CODE
].copy()

print("\n1. TARGET PRODUCT")
print("StockCode:", TARGET_CODE)
print("Original transaction rows:", len(product))

print("\nProduct descriptions:")
print(product["Description"].value_counts(dropna=False))

# --------------------------------------------------
# 2. ORIGINAL TRANSACTION DETAILS
# --------------------------------------------------

print("\n2. ALL ORIGINAL TRANSACTIONS")

columns = [
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country"
]

print(
    product[columns].sort_values(
        "InvoiceDate"
    ).to_string(index=False)
)

# --------------------------------------------------
# 3. TRANSACTION SUMMARY
# --------------------------------------------------

print("\n3. TRANSACTION SUMMARY")

print("Total quantity:", product["Quantity"].sum())
print("Positive quantity:", product.loc[
    product["Quantity"] > 0, "Quantity"
].sum())

print("Negative quantity:", product.loc[
    product["Quantity"] < 0, "Quantity"
].sum())

print("Distinct invoices:", product["InvoiceNo"].nunique())
print("Distinct customers:", product["CustomerID"].nunique())

print("Total positive transaction value:",
      (product.loc[product["Quantity"] > 0, "Quantity"] *
       product.loc[product["Quantity"] > 0, "UnitPrice"]).sum())

# --------------------------------------------------
# 4. INVOICE-LEVEL INVESTIGATION
# --------------------------------------------------

print("\n4. INVOICE LEVEL DETAILS")

invoice_summary = product.groupby("InvoiceNo").agg(
    TotalQuantity=("Quantity", "sum"),
    TransactionRows=("Quantity", "count"),
    InvoiceDate=("InvoiceDate", "min"),
    UnitPriceMin=("UnitPrice", "min"),
    UnitPriceMax=("UnitPrice", "max"),
    CustomerID=("CustomerID", "first")
).reset_index()

print(invoice_summary.to_string(index=False))

# --------------------------------------------------
# 5. EXTREME TRANSACTION INVESTIGATION
# --------------------------------------------------

print("\n5. TOP 20 LARGEST POSITIVE TRANSACTION LINES")

positive = df[df["Quantity"] > 0].copy()

print(
    positive.nlargest(20, "Quantity")[
        columns
    ].to_string(index=False)
)

# --------------------------------------------------
# 6. DATA QUALITY INDICATORS
# --------------------------------------------------

print("\n6. DATA QUALITY INDICATORS")

print("Rows with zero quantity:",
      (product["Quantity"] == 0).sum())

print("Rows with negative unit price:",
      (product["UnitPrice"] < 0).sum())

print("Rows with zero unit price:",
      (product["UnitPrice"] == 0).sum())

print("Rows with missing CustomerID:",
      product["CustomerID"].isna().sum())

print("Cancellation-style invoice rows:",
      product["InvoiceNo"].astype(str).str.startswith("C").sum())

print("\nSOURCE LEVEL INVESTIGATION COMPLETED")
print("=" * 75)

