
import pandas as pd
import numpy as np

RAW_FILE = "data/raw/Online Retail.xlsx"
MOVEMENT_FILE = "data/processed/product_movement_v2.csv"

print("=" * 75)
print("TREXO - CANCELLATION AND RETURN AUDIT V1")
print("=" * 75)

# Load original source data
df = pd.read_excel(RAW_FILE, engine="openpyxl")

df["StockCode"] = df["StockCode"].astype(str).str.strip()
df["InvoiceNo"] = df["InvoiceNo"].astype(str).str.strip()

df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce")

df["InvoiceDate"] = pd.to_datetime(
    df["InvoiceDate"], errors="coerce"
)

# --------------------------------------------------
# 1. TRANSACTION OVERVIEW
# --------------------------------------------------

print("\n1. TRANSACTION OVERVIEW")

print("Total source rows:", len(df))
print("Positive quantity rows:", (df["Quantity"] > 0).sum())
print("Negative quantity rows:", (df["Quantity"] < 0).sum())
print("Zero quantity rows:", (df["Quantity"] == 0).sum())

print("Positive quantity total:",
      df.loc[df["Quantity"] > 0, "Quantity"].sum())

print("Negative quantity total:",
      df.loc[df["Quantity"] < 0, "Quantity"].sum())

print("Net quantity:",
      df["Quantity"].sum())

# --------------------------------------------------
# 2. CANCELLATION INVOICES
# --------------------------------------------------

print("\n2. CANCELLATION INVOICES")

df["IsCancellationInvoice"] = (
    df["InvoiceNo"].str.startswith("C")
)

print("Cancellation invoice rows:",
      df["IsCancellationInvoice"].sum())

print("Unique cancellation invoices:",
      df.loc[df["IsCancellationInvoice"], "InvoiceNo"].nunique())

print("Negative rows in non-cancellation invoices:",
      ((df["Quantity"] < 0) &
       (~df["IsCancellationInvoice"])).sum())

print("Positive rows in cancellation invoices:",
      ((df["Quantity"] > 0) &
       (df["IsCancellationInvoice"])).sum())

# --------------------------------------------------
# 3. EXACT REVERSAL GROUP ANALYSIS
# --------------------------------------------------

print("\n3. EXACT REVERSAL GROUP ANALYSIS")

# Compare positive and negative quantities using
# product, customer and unit price.

valid = df.dropna(
    subset=["StockCode", "CustomerID", "UnitPrice", "Quantity"]
).copy()

keys = ["StockCode", "CustomerID", "UnitPrice"]

positive = (
    valid[valid["Quantity"] > 0]
    .groupby(keys)["Quantity"]
    .sum()
    .rename("PositiveQuantity")
    .reset_index()
)

negative = (
    valid[valid["Quantity"] < 0]
    .assign(Quantity=lambda x: x["Quantity"].abs())
    .groupby(keys)["Quantity"]
    .sum()
    .rename("NegativeQuantityMagnitude")
    .reset_index()
)

reversals = positive.merge(negative, on=keys, how="inner")

reversals["MatchedQuantity"] = reversals[
    ["PositiveQuantity", "NegativeQuantityMagnitude"]
].min(axis=1)

reversals["FullyReversedGroup"] = np.isclose(
    reversals["PositiveQuantity"],
    reversals["NegativeQuantityMagnitude"]
)

print("Matching product/customer/price groups:",
      len(reversals))

print("Fully reversed groups:",
      reversals["FullyReversedGroup"].sum())

print("Potential reversal quantity:",
      reversals["MatchedQuantity"].sum())

print("\nLargest matched reversal groups:")

print(
    reversals.nlargest(15, "MatchedQuantity").to_string(index=False)
)

# Note: These are candidate reversals, not proof that
# individual invoices belong to the same original order.

# --------------------------------------------------
# 4. PRODUCT LEVEL GROSS VS NET MOVEMENT
# --------------------------------------------------

print("\n4. PRODUCT LEVEL GROSS VS NET MOVEMENT")

product_sales = df.groupby("StockCode").agg(
    GrossPositiveQuantity=(
        "Quantity",
        lambda x: x[x > 0].sum()
    ),
    NegativeQuantity=(
        "Quantity",
        lambda x: x[x < 0].sum()
    ),
    NetQuantity=("Quantity", "sum"),
    TransactionRows=("Quantity", "count")
).reset_index()

product_sales["AbsoluteNetReduction"] = (
    product_sales["GrossPositiveQuantity"] -
    product_sales["NetQuantity"]
)

print("Products with negative transactions:",
      (product_sales["NegativeQuantity"] < 0).sum())

print("Products with net quantity below gross sales:",
      (product_sales["AbsoluteNetReduction"] > 0).sum())

print("\nLargest gross-to-net differences:")

print(
    product_sales.nlargest(
        15, "AbsoluteNetReduction"
    ).to_string(index=False)
)

# --------------------------------------------------
# 5. COMPARE WITH TREXO V2
# --------------------------------------------------

print("\n5. COMPARE WITH TREXO MOVEMENT V2")

movement = pd.read_csv(MOVEMENT_FILE)

comparison = movement.merge(
    product_sales,
    on="StockCode",
    how="left"
)

comparison["GrossSalesDifference"] = (
    comparison["TotalQuantitySold"] -
    comparison["GrossPositiveQuantity"]
)

print("Products compared:", len(comparison))

print("V2 vs gross sales mismatches:",
      (comparison["GrossSalesDifference"].abs() > 0.01).sum())

comparison["NetMovementDifference"] = (
    comparison["TotalQuantitySold"] -
    comparison["NetQuantity"]
)

print("V2 vs net movement mismatches:",
      (comparison["NetMovementDifference"].abs() > 0.01).sum())

print("\nLargest V2 versus net movement differences:")

print(
    comparison.nlargest(
        15, "NetMovementDifference"
    )[
        ["StockCode", "ProductDescription",
         "TotalQuantitySold", "GrossPositiveQuantity",
         "NegativeQuantity", "NetQuantity",
         "NetMovementDifference"]
    ].to_string(index=False)
)

# --------------------------------------------------
# 6. INVESTIGATE KNOWN PRODUCT
# --------------------------------------------------

print("\n6. PRODUCT 23843 INVESTIGATION")

print(
    df[df["StockCode"] == "23843"][
        ["InvoiceNo", "Quantity", "InvoiceDate",
         "UnitPrice", "CustomerID"]
    ].to_string(index=False)
)

print("\nPRODUCT 23843 AGGREGATE:")

print(
    product_sales[
        product_sales["StockCode"] == "23843"
    ].to_string(index=False)
)

# --------------------------------------------------
# 7. FINAL SUMMARY
# --------------------------------------------------

print("\n" + "=" * 75)
print("TREXO CANCELLATION AND RETURN AUDIT V1 COMPLETED")
print("=" * 75)
print("No source data has been modified.")

