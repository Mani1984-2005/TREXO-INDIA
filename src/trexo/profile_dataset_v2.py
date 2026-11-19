import pandas as pd
from pathlib import Path

RAW = Path("data/raw/Online Retail.xlsx")
OUTPUT = Path("data/processed")

print("=" * 65)
print("TREXO - PRODUCT MOVEMENT PROFILING V2")
print("=" * 65)

df = pd.read_excel(RAW)

df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
df["InvoiceNo"] = df["InvoiceNo"].astype(str)

# Keep valid positive sales transactions
sales = df[
    (~df["InvoiceNo"].str.startswith("C")) &
    (df["Quantity"] > 0) &
    (df["UnitPrice"] > 0)
].copy()

sales["SaleDate"] = sales["InvoiceDate"].dt.normalize()
sales["SaleMonth"] = sales["InvoiceDate"].dt.to_period("M")
sales["Revenue"] = sales["Quantity"] * sales["UnitPrice"]

# Dataset observation window
start_date = sales["InvoiceDate"].min()
end_date = sales["InvoiceDate"].max()

total_months = len(pd.period_range(
    start=start_date.to_period("M"),
    end=end_date.to_period("M"),
    freq="M"
))

# Product-level profiling
products = sales.groupby("StockCode").agg(
    ProductDescription=("Description", "first"),
    TotalQuantitySold=("Quantity", "sum"),
    InvoiceCount=("InvoiceNo", "nunique"),
    ActualSaleDays=("SaleDate", "nunique"),
    ActiveMonths=("SaleMonth", "nunique"),
    FirstSale=("InvoiceDate", "min"),
    LastSale=("InvoiceDate", "max"),
    TotalSalesValue=("Revenue", "sum")
)

products["DaysSinceLastSale"] = (
    end_date.normalize() -
    products["LastSale"].dt.normalize()
).dt.days

products["AverageUnitsPerInvoice"] = (
    products["TotalQuantitySold"] /
    products["InvoiceCount"]
)

products["AverageUnitsPerActiveMonth"] = (
    products["TotalQuantitySold"] /
    products["ActiveMonths"]
)

products["MonthlyActivityRate"] = (
    products["ActiveMonths"] / total_months * 100
)

products = products.sort_values(
    "DaysSinceLastSale",
    ascending=False
)

print("\n1. DATASET OBSERVATION WINDOW")
print("Start:", start_date)
print("End:", end_date)
print("Observed months:", total_months)

print("\n2. PRODUCT MOVEMENT SUMMARY")
print("Total products:", len(products))
print("Products with one invoice:",
      (products["InvoiceCount"] == 1).sum())
print("Products sold on one actual day:",
      (products["ActualSaleDays"] == 1).sum())

print("\n3. PRODUCTS WITH LONGEST SALES INACTIVITY")
print(products.head(20).to_string())

print("\n4. PRODUCTS WITH LOWEST TOTAL SALES")
print(products.nsmallest(
    20, "TotalQuantitySold"
).to_string())

print("\n5. PRODUCTS WITH NO SALES IN LAST 90 OBSERVED DAYS")
inactive_90 = products[
    products["DaysSinceLastSale"] >= 90
]

print("Count:", len(inactive_90))
print(inactive_90.head(20).to_string())

print("\n6. MONTHLY PRODUCT SALES")

monthly = sales.groupby(
    ["StockCode", "SaleMonth"]
).agg(
    MonthlyQuantity=("Quantity", "sum"),
    MonthlyInvoices=("InvoiceNo", "nunique"),
    MonthlyRevenue=("Revenue", "sum")
).reset_index()

# Export results
OUTPUT.mkdir(parents=True, exist_ok=True)

products.to_csv(
    OUTPUT / "product_movement_v2.csv"
)

monthly.to_csv(
    OUTPUT / "product_monthly_sales_v2.csv",
    index=False
)

print("\n7. GENERATED FILES")
print("data/processed/product_movement_v2.csv")
print("data/processed/product_monthly_sales_v2.csv")

print("\nPRODUCT MOVEMENT PROFILING V2 COMPLETED")
