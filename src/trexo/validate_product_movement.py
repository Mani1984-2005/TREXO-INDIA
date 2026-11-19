
import pandas as pd
import numpy as np

MOVEMENT_FILE = "data/processed/product_movement_v2.csv"
MONTHLY_FILE = "data/processed/product_monthly_sales_v2.csv"

movement = pd.read_csv(MOVEMENT_FILE)
monthly = pd.read_csv(MONTHLY_FILE)

print("=" * 75)
print("TREXO - PRODUCT MOVEMENT VALIDATION V1")
print("=" * 75)

# --------------------------------------------------
# 1. KEY UNIQUENESS
# --------------------------------------------------

print("\n1. KEY UNIQUENESS")

print("Duplicate product codes:",
      movement["StockCode"].duplicated().sum())

print("Duplicate product-month keys:",
      monthly.duplicated(["StockCode", "SaleMonth"]).sum())

# --------------------------------------------------
# 2. NUMERIC VALIDATION
# --------------------------------------------------

print("\n2. NUMERIC VALIDATION")

numeric_movement = [
    "TotalQuantitySold", "InvoiceCount",
    "ActualSaleDays", "ActiveMonths",
    "TotalSalesValue", "DaysSinceLastSale",
    "AverageUnitsPerInvoice",
    "AverageUnitsPerActiveMonth",
    "MonthlyActivityRate"
]

numeric_monthly = [
    "MonthlyQuantity", "MonthlyInvoices", "MonthlyRevenue"
]

for col in numeric_movement:
    print(
        col,
        "| Negative:", (movement[col] < 0).sum(),
        "| Zero:", (movement[col] == 0).sum()
    )

for col in numeric_monthly:
    print(
        col,
        "| Negative:", (monthly[col] < 0).sum(),
        "| Zero:", (monthly[col] == 0).sum()
    )

# --------------------------------------------------
# 3. PRODUCT-LEVEL RECONCILIATION
# --------------------------------------------------

print("\n3. PRODUCT-LEVEL RECONCILIATION")

monthly_summary = monthly.groupby("StockCode").agg(
    RecalculatedQuantity=("MonthlyQuantity", "sum"),
    RecalculatedInvoices=("MonthlyInvoices", "sum"),
    RecalculatedRevenue=("MonthlyRevenue", "sum"),
    RecalculatedActiveMonths=("SaleMonth", "nunique"),
    MonthlyRecordCount=("SaleMonth", "count")
).reset_index()

comparison = movement.merge(
    monthly_summary,
    on="StockCode",
    how="outer",
    indicator=True
)

print("\nProduct merge status:")
print(comparison["_merge"].value_counts())

checks = {
    "Quantity": (
        "TotalQuantitySold", "RecalculatedQuantity"
    ),
    "Invoice count": (
        "InvoiceCount", "RecalculatedInvoices"
    ),
    "Revenue": (
        "TotalSalesValue", "RecalculatedRevenue"
    ),
    "Active months": (
        "ActiveMonths", "RecalculatedActiveMonths"
    )
}

for name, (original, recalculated) in checks.items():
    difference = (
        comparison[original] - comparison[recalculated]
    ).abs()

    mismatches = difference.gt(0.01).sum()

    print(f"{name} mismatches: {mismatches}")

    if mismatches:
        print(
            comparison.loc[
                difference.gt(0.01),
                ["StockCode", original, recalculated]
            ].head(10).to_string(index=False)
        )

# --------------------------------------------------
# 4. DATE VALIDATION
# --------------------------------------------------

print("\n4. DATE VALIDATION")

movement["FirstSale"] = pd.to_datetime(
    movement["FirstSale"], errors="coerce"
)

movement["LastSale"] = pd.to_datetime(
    movement["LastSale"], errors="coerce"
)

monthly["SaleMonth"] = pd.to_datetime(
    monthly["SaleMonth"], errors="coerce"
)

print("Invalid first sale dates:",
      movement["FirstSale"].isna().sum())

print("Invalid last sale dates:",
      movement["LastSale"].isna().sum())

print("Invalid monthly dates:",
      monthly["SaleMonth"].isna().sum())

print("First transaction:",
      movement["FirstSale"].min())

print("Last transaction:",
      movement["LastSale"].max())

print("Products with FirstSale > LastSale:",
      (movement["FirstSale"] > movement["LastSale"]).sum())

# --------------------------------------------------
# 5. OUTLIER INVESTIGATION
# --------------------------------------------------

print("\n5. TOP 15 PRODUCTS BY QUANTITY")

print(
    movement.nlargest(15, "TotalQuantitySold")[
        ["StockCode", "ProductDescription",
         "TotalQuantitySold", "InvoiceCount",
         "AverageUnitsPerInvoice", "TotalSalesValue"]
    ].to_string(index=False)
)

# --------------------------------------------------
# 6. MONTHLY DATA CHECKS
# --------------------------------------------------

print("\n6. MONTHLY DATA CHECKS")

print("Monthly quantity distribution:")
print(monthly["MonthlyQuantity"].describe())

print("\nProducts with only one active month:",
      (movement["ActiveMonths"] == 1).sum())

print("Products with all 13 active months:",
      (movement["ActiveMonths"] == 13).sum())

print("\nMonthly records per product:")
print(monthly.groupby("StockCode").size().describe())

# --------------------------------------------------
# 7. FINAL REPORT
# --------------------------------------------------

print("\n" + "=" * 75)
print("TREXO VALIDATION V1 COMPLETED")
print("=" * 75)
print("Review all mismatches and anomalies before model development.")
