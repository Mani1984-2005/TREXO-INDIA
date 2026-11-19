import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import numpy as np, pandas as pd, pytest


def make_sales(spec: dict, start="2011-01-01") -> pd.DataFrame:
    """spec: {stockcode: [(day_offset, qty, price, customer_or_None), ...]} -> valid-sales frame (synthetic, tests only)."""
    rows = []; n = 0
    for code, recs in spec.items():
        for off, q, p, c in recs:
            d = pd.Timestamp(start) + pd.Timedelta(days=off); n += 1
            rows.append({"SourceRow": n, "InvoiceNo": f"5{n:05d}", "StockCode": code, "Description": f"ITEM {code}",
                         "Quantity": float(q), "UnitPrice": float(p), "LineValue": float(q * p), "InvoiceDate": d, "Date": d,
                         "CustomerID": np.nan if c is None else float(c), "Country": "UK", "IsExactDuplicate": False})
    return pd.DataFrame(rows)


@pytest.fixture
def sales():
    spec = {
        "A": [(i, 5, 2.0, 1) for i in range(0, 200, 3)],                 # steady seller
        "B": [(10, 4, 1.5, None)],                                        # single transaction
        "C": [(i, 3, 3.0, 2) for i in range(0, 60, 2)],                  # sold early, then silent
        "D": [(i, 1, 1.0, 3) for i in (5, 60, 120, 190)],                # intermittent
        "E": [(i, 200 if i == 100 else 4, 2.0, 4) for i in range(0, 200, 7)],  # spike
    }
    s = make_sales(spec)
    return s
