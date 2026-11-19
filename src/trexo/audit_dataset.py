import pandas as pd
from pathlib import Path

file_path = Path("data/raw/Online Retail.xlsx")

print("=" * 55)
print("TREXO - DATASET AUDIT V1")
print("=" * 55)

if not file_path.exists():
    raise FileNotFoundError(f"Dataset not found: {file_path}")

df = pd.read_excel(file_path)

print("\n1. DATASET SHAPE")
print(df.shape)

print("\n2. COLUMN NAMES")
print(df.columns.tolist())

print("\n3. FIRST FIVE ROWS")
print(df.head())

print("\n4. DATA TYPES")
print(df.dtypes)

print("\n5. MISSING VALUES")
print(df.isnull().sum())

print("\n6. DUPLICATE ROWS")
print(df.duplicated().sum())

print("\n7. DATE RANGE")
df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
print("Start:", df["InvoiceDate"].min())
print("End:", df["InvoiceDate"].max())

print("\n8. BASIC SALES STATISTICS")
print(df[["Quantity", "UnitPrice"]].describe())

print("\nAUDIT COMPLETED")
