"""SYNTHETIC shop generator - for TESTS and clearly-labelled demos ONLY (never for training or reported performance)."""
from __future__ import annotations
import numpy as np
import pandas as pd

LABEL = "SYNTHETIC_FOR_TESTING_ONLY"


def synthetic_shop(n_products=12, days=180, seed=7, start="2011-01-01"):
    rng = np.random.default_rng(seed); t0 = pd.Timestamp(start)
    ev, n = [], 0
    def add(**k):
        nonlocal n; n += 1; ev.append({"event_id": f"E{n:06d}", "location": "MAIN", "unit_cost": np.nan, "direction": np.nan, "expiry_date": pd.NaT, "unit_price": np.nan, **k})
    prods = {}
    for i in range(n_products):
        pid = f"P{i:03d}"; cost = float(rng.uniform(1, 8)); price = cost * float(rng.uniform(1.3, 1.9))
        rate = float(rng.choice([0.0, 0.2, 1.0, 4.0])) if i >= 3 else 3.0      # first 3 products are fast sellers
        prods[pid] = (cost, price, rate)
        add(product_id=pid, ts=t0, type="OPENING", qty=int(rng.integers(40, 200)), unit_cost=cost)
        for d in range(0, days, 30):
            add(product_id=pid, ts=t0 + pd.Timedelta(days=d + 5), type="RECEIPT", qty=int(rng.integers(20, 100)), unit_cost=cost * float(rng.uniform(0.95, 1.05)))
        for d in range(days):
            q = int(rng.poisson(rate))
            if q: add(product_id=pid, ts=t0 + pd.Timedelta(days=d), type="SALE", qty=q, unit_price=price)
    return pd.DataFrame(ev), prods, LABEL
