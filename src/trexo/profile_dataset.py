import pandas as pd
from pathlib import Path

file_path = Path("data/raw/Online Retail.xlsx")

df = pd.read_excel(file_path)

print("=" * 65)
print("TREXO - PRODUCT MOVEMENT PROFILING V1")
print("=" * 65)

# Prepare transaction data
df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
df["InvoiceNo"] = df["InvoiceNo"].astype(str)

# Identify cancelled invoices
df["IsCancelled"] = df["InvoiceNo"].str.startswith("C")

# Basic dataset information
print("\n1. UNIQUE PRODUCTS")
print(df["StockCode"].nunique())

# Product-level sales movement
sales = df[
    (~df["IsCancelled"]) &
    (df["Quantity"] > 0) &
    (df["UnitPrice"] > 0)
].copy()

product_movement = sales.groupby("StockCode").agg(
    ProductDescription=("Description", "first"),
    TotalQuantitySold=("Quantity", "sum"),
    InvoiceCount=("InvoiceNo", "nunique"),
    FirstSale=("InvoiceDate", "min"),
    LastSale=("InvoiceDate", "max"),
    TotalSalesValue=("Quantity", lambda x: 0)
)

# Calculate revenue separately
revenue = sales.assign(
    Revenue=sales["Quantity"] * sales["UnitPrice"]
).groupby("StockCode")["Revenue"].sum()

product_movement["TotalSalesValue"] = revenue

product_movement["ActiveDays"] = (
    product_movement["LastSale"] -
    product_movement["FirstSale"]
).dt.days + 1

product_movement = product_movement.sort_values(
    "TotalQuantitySold",
    ascending=False
)

print("\n2. TOTAL PRODUCTS WITH VALID SALES")
print(len(product_movement))

print("\n3. TOP 15 PRODUCTS BY QUANTITY SOLD")
print(product_movement.head(15).to_string())

print("\n4. BOTTOM 15 PRODUCTS BY QUANTITY SOLD")
print(product_movement.tail(15).to_string())

print("\n5. PRODUCTS WITH ONLY ONE RECORDED INVOICE")
print((product_movement["InvoiceCount"] == 1).sum())

print("\n6. PRODUCTS WITH SALES RECORDED OVER ONLY ONE DAY")
print((product_movement["ActiveDays"] == 1).sum())

print("\n7. PRODUCTS WITH LOW HISTORICAL MOVEMENT")
print(product_movement[
    product_movement["TotalQuantitySold"] <= 5
].head(20).to_string())

# Save results without modifying raw data
output_path = Path("data/processed")
output_path.mkdir(parents=True, exist_ok=True)

product_movement.to_csv(
    output_path / "product_movement_v1.csv"
)

print("\n8. OUTPUT FILE")
print(output_path / "product_movement_v1.csv")

print("\nPRODUCT MOVEMENT PROFILING COMPLETED")
