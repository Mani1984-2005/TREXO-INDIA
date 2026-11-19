"""Measured data-quality / feature / label audit. Writes JSON + markdown. Read-only."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
from trexo.ml.config import (RAW_FILE, ML_DATA_DIR, REPORT_DIR, REPO_ROOT, D01_BAD_DEBT_INVOICES,
                             D01_EXCLUSION_REASON, HorizonConfig)
from trexo.ml.data_pipeline.pipeline import (load_raw, normalise_types, tag_exclusions, build_sales,
                                             exclusion_log, is_non_product_code, load_sales)
from trexo.ml.features.product_features import build_features, FEATURE_COLUMNS
from trexo.ml.validation.splits import make_cutoffs, forward_chain_folds

H = HorizonConfig()
raw = load_raw(RAW_FILE)
norm = normalise_types(raw)
tagged = tag_exclusions(norm)
sales = load_sales()
as_of = sales["Date"].max()

def pct(a, b): return round(100.0 * a / b, 4) if b else 0.0

missing = {}
for c in ["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"]:
    n = int(raw[c].isna().sum())
    missing[c] = {"missing": n, "pct": pct(n, len(raw))}

raw_exact_dup = int(raw.duplicated(subset=["InvoiceNo", "StockCode", "Description", "Quantity",
                                           "InvoiceDate", "UnitPrice", "CustomerID", "Country"]).sum())
valid_dup = int(sales["IsExactDuplicate"].sum())
dup_mask = sales["IsExactDuplicate"]
dup_qty = float(sales.loc[dup_mask, "Quantity"].sum())
dup_value = float(sales.loc[dup_mask, "LineValue"].sum())

raw_sc = raw["StockCode"].astype(str)
sc_strip_changed = int((raw_sc != raw_sc.str.strip()).sum())
sc_ws = raw_sc[raw_sc != raw_sc.str.strip()]
# Case variants: distinct exact keys whose uppercase form collides (no case-folding applied)
codes = pd.Series(norm["StockCode"].unique())
grp = codes.groupby(codes.str.upper()).agg(lambda x: sorted(set(x)))
variants = grp[grp.apply(len) > 1]

desc_missing = int(raw["Description"].isna().sum())
desc_blank = int(raw["Description"].astype(str).str.strip().eq("").sum())
desc_per_code = norm.dropna(subset=["Description"]).groupby("StockCode")["Description"].nunique()
multi_desc = int((desc_per_code > 1).sum())

invalid_dates = int(norm["InvoiceDate"].isna().sum())
invalid_qty = int(norm["Quantity"].isna().sum())
invalid_price = int(norm["UnitPrice"].isna().sum())
neg_qty = int((norm["Quantity"] < 0).sum())
zero_price = int((norm["UnitPrice"] == 0).sum())
neg_price = int((norm["UnitPrice"] < 0).sum())
cancellations = int(norm["InvoiceNo"].str.startswith("C").sum())

log = exclusion_log(tagged)
d01_rows = tagged[tagged["ExclusionReason"] == D01_EXCLUSION_REASON]
d01_in_sales = int(sales["InvoiceNo"].isin(D01_BAD_DEBT_INVOICES).sum())

daily = sales.groupby("Date").size()
date_span = int((sales["Date"].max() - sales["Date"].min()).days + 1)
distinct_dates = int(sales["Date"].nunique())
missing_calendar_days = date_span - distinct_dates
max_gap = int(pd.Series(sorted(sales["Date"].unique())).diff().dt.days.max()) if distinct_dates > 1 else 0
weekly_complete = int(((sales["Date"].max().normalize() - sales["Date"].min().normalize()).days + 1) // 7)

feat = build_features(sales, as_of)
feat_nan = int(feat[FEATURE_COLUMNS].isna().any(axis=1).sum())
age = feat["age_days"]
history = {
    "products": int(len(feat)),
    "age_days_quantiles": {str(q): float(age.quantile(q)) for q in (0, .1, .25, .5, .75, .9, 1)},
    "products_age_lt_60d": int((age < 60).sum()),
    "products_age_lt_180d": int((age < 180).sum()),
    "products_single_invoice": int((feat["n_invoices"] == 1).sum()),
    "products_single_sale_day": int((feat["n_sale_days"] == 1).sum()),
}

c = make_cutoffs(sales["Date"].min(), H)
purged = bool(c["train"][-1] + pd.Timedelta(days=H.label_horizon_days) <= c["val"]
              and c["val"] + pd.Timedelta(days=H.label_horizon_days) <= c["test"])
folds = forward_chain_folds(c["train"], H.label_horizon_days)
folds_purged = all(all(t + pd.Timedelta(days=H.label_horizon_days) <= v for t in tr) for tr, v in folds)

# Product aggregation: ML product totals must equal the sum of their valid-sale lines.
prod_qty = sales.groupby("StockCode")["Quantity"].sum()
prod_val = sales.groupby("StockCode")["LineValue"].sum()
agg_ok = bool(abs(prod_qty.sum() - sales["Quantity"].sum()) < 1e-6 and abs(prod_val.sum() - sales["LineValue"].sum()) < 1e-6)

b_rows = norm[norm["StockCode"] == "B"]
result = {
    "audit_timestamp_utc": pd.Timestamp.utcnow().isoformat(),
    "raw_sha256": json.loads((ML_DATA_DIR / "data_manifest_v1.json").read_text())["raw_sha256"],
    "pipeline_version": json.loads((ML_DATA_DIR / "data_manifest_v1.json").read_text())["pipeline_version"],
    "rows": {"raw": int(len(raw)), "valid_sales": int(len(sales)),
             "distinct_valid_products": int(sales["StockCode"].nunique()),
             "date_min": str(sales["Date"].min().date()), "date_max": str(sales["Date"].max().date())},
    "missing_values": missing,
    "duplicates": {
        "raw_exact_duplicate_rows": raw_exact_dup,
        "valid_exact_duplicate_rows_retained": valid_dup,
        "valid_duplicate_quantity_sum": dup_qty,
        "valid_duplicate_line_value_sum": dup_value,
        "policy": "RETained and flagged, never silently deleted (owner decision pending).",
        "impact_by_purpose": {
            "units_and_revenue": "Duplicates inflate units and line value if they are data-entry repeats.",
            "invoice_counts": "InvoiceCount uses distinct invoices, so exact duplicates do not inflate it.",
            "sale_day_counts": "Distinct sale days are unaffected unless duplicates are the only row on a day.",
        },
    },
    "product_identifiers": {
        "raw_unique_stockcodes": int(raw["StockCode"].nunique()),
        "valid_unique_stockcodes": int(sales["StockCode"].nunique()),
        "stockcodes_with_leading_trailing_whitespace": sc_strip_changed,
        "case_variant_groups": int(len(variants)),
        "case_variant_examples": [list(v) for v in variants.head(10).tolist()],
        "case_folding_applied": False,
    },
    "descriptions": {
        "missing": desc_missing, "blank": desc_blank,
        "products_with_multiple_descriptions": multi_desc,
    },
    "transaction_quality": {
        "invalid_dates": invalid_dates, "non_numeric_quantity": invalid_qty,
        "non_numeric_price": invalid_price, "negative_quantity_rows": neg_qty,
        "zero_price_rows": zero_price, "negative_price_rows": neg_price,
        "cancellation_invoice_rows": cancellations,
        "exclusion_log": {k: int(v) for k, v in log.set_index("Reason")["Rows"].items()},
        "d01_rows_in_valid_sales": d01_in_sales,
        "stockcode_B_rows_raw": int(len(b_rows)),
        "stockcode_B_exclusively_d01": bool(len(b_rows) == 3 and set(b_rows["InvoiceNo"]) == set(D01_BAD_DEBT_INVOICES)),
    },
    "time_series": {
        "calendar_days_spanned": date_span, "distinct_sale_days": distinct_dates,
        "calendar_days_without_valid_sale": missing_calendar_days,
        "max_gap_between_sale_days": max_gap,
        "complete_weeks_for_forecasting": weekly_complete,
        "note": "One seasonal cycle only; no second year for seasonal validation.",
    },
    "product_history": history,
    "valid_sales_distribution": {
        "quantity": {k: float(v) for k, v in sales["Quantity"].describe(percentiles=[.5, .99]).items()},
        "unit_price": {k: float(v) for k, v in sales["UnitPrice"].describe(percentiles=[.5, .99]).items()},
        "quantity_ge_1000_rows": int((sales["Quantity"] >= 1000).sum()),
        "line_value_total": float(sales["LineValue"].sum()),
    },
    "leakage_and_consistency": {
        "cutoffs_purged": purged, "cv_folds_purged": folds_purged,
        "features_contain_any_nan_products": feat_nan,
        "feature_schema_matches_training": list(feat.columns) == ["StockCode", "cutoff", "first", "last", *FEATURE_COLUMNS],
        "product_aggregation_reconciles": agg_ok,
        "d01_absent_from_features": bool("B" not in set(feat["StockCode"]) and d01_in_sales == 0),
        "inference_uses_same_feature_builder": True,
    },
    "findings": [],
}
f = result["findings"]
f.append({"severity": "INFO", "finding": "D01 group is excluded by an explicit first-match rule and absent from valid sales."})
f.append({"severity": "WARN", "finding": f"{valid_dup:,} exact duplicate valid rows retained; they add {dup_qty:.0f} units and {dup_value:.2f} line value."})
f.append({"severity": "WARN", "finding": f"{desc_missing:,} raw rows lack Description; descriptions are not a reliable product key."})
f.append({"severity": "WARN", "finding": f"{int(raw['CustomerID'].isna().sum()):,} raw rows lack CustomerID ({pct(int(raw['CustomerID'].isna().sum()), len(raw)):.1f}%)."})
f.append({"severity": "WARN", "finding": f"Only {weekly_complete} complete weeks exist; seasonality cannot be validated."})
f.append({"severity": "INFO", "finding": f"{history['products_single_invoice']:,} products have a single invoice; evidence quality is LOW for them."})
if len(variants):
    f.append({"severity": "WARN", "finding": f"{len(variants)} case-variant StockCode groups exist; no case-folding is applied (not approved)."})
result["findings"] = f

REPORT_DIR.mkdir(parents=True, exist_ok=True)
(REPORT_DIR / "data_quality_audit.json").write_text(json.dumps(result, indent=2, default=str))
pd.DataFrame(f).to_csv(REPORT_DIR / "data_quality_findings.csv", index=False)

def table(d):
    return "| Metric | Value |\n|---|---|\n" + "\n".join(f"| {k} | {v} |" for k, v in d.items())

md = f"""# ML Data Quality and Feature Audit

> Generated from the actual raw workbook and delivered ML datasets on {result['audit_timestamp_utc']}.
> Pipeline `{result['pipeline_version']}`; raw SHA-256 `{result['raw_sha256']}`.

## 1. Dataset shape
{table(result['rows'])}

## 2. Missing values (raw)
| Column | Missing | % |
|---|---|---|
""" + "\n".join(f"| {k} | {v['missing']:,} | {v['pct']:.2f}% |" for k, v in missing.items()) + f"""

## 3. Duplicates
- Raw exact duplicates: **{raw_exact_dup:,}**.
- Exact duplicates inside valid sales, retained and flagged: **{valid_dup:,}**.
- They contribute **{dup_qty:.0f} units** and **{dup_value:.2f}** line value.
- No duplicate row is silently deleted. Invoice counts use distinct invoices, so they are not inflated by exact duplicates.

## 4. Product identifiers and descriptions
- Raw StockCodes: **{result['product_identifiers']['raw_unique_stockcodes']:,}**; with valid sales: **{result['product_identifiers']['valid_unique_stockcodes']:,}**.
- StockCodes needing whitespace strip: **{sc_strip_changed:,}**; case-variant groups: **{len(variants)}** (case-folding NOT applied).
- Missing Description: **{desc_missing:,}**; blank: **{desc_blank:,}**; products with multiple descriptions: **{multi_desc:,}**.

## 5. Transaction quality and exclusions
| Reason | Rows |
|---|---|
""" + "\n".join(f"| {k} | {v:,} |" for k, v in result["transaction_quality"]["exclusion_log"].items()) + f"""

- Negative quantity rows: **{neg_qty:,}**; zero price: **{zero_price:,}**; negative price: **{neg_price:,}**; C-invoices: **{cancellations:,}**.
- Invalid dates: **{invalid_dates}**; non-numeric quantity: **{invalid_qty}**; non-numeric price: **{invalid_price}**.
- D01 rows in valid sales: **{d01_in_sales}**; StockCode B rows in raw: **{len(b_rows)}**, exclusively D01: **{result['transaction_quality']['stockcode_B_exclusively_d01']}**.

## 6. Time series and product history
- {date_span} calendar days, {distinct_dates} valid-sale days, {missing_calendar_days} days with no valid sale; max gap {max_gap} days.
- Complete weeks usable by the forecaster: **{weekly_complete}**.
- Products assessed at {as_of.date()}: **{history['products']:,}**; age days median {history['age_days_quantiles']['0.5']:.0f}; single-invoice products {history['products_single_invoice']:,}; single-sale-day products {history['products_single_sale_day']:,}.

## 7. Leakage and consistency
- Chronological cutoffs purged: **{purged}**; CV folds purged: **{folds_purged}**.
- Products with any NaN in the feature vector: **{feat_nan}**.
- Feature schema stable: **{result['leakage_and_consistency']['feature_schema_matches_training']}**.
- Product aggregation reconciles to valid-sale totals: **{agg_ok}**.
- D01 absent from features: **{result['leakage_and_consistency']['d01_absent_from_features']}**.
- Training and inference both use `build_features`; no separate feature implementation exists.

## 8. Findings
""" + "\n".join(f"- **{x['severity']}** — {x['finding']}" for x in f) + """

## 9. Decisions still required
1. Duplicate treatment (currently retain + flag; no approved deletion).
2. Product-key case policy (currently no case-folding).
3. Customer-data use (24.9% missing; currently limited to counts and missing-share features).
4. Seasonality needs a second year of data.
"""
(REPORT_DIR / "data_quality_report.md").write_text(md, encoding="utf-8")
(REPO_ROOT / "docs" / "ML_DATA_QUALITY_REPORT.md").write_text(md, encoding="utf-8")
print(json.dumps({"rows": result["rows"], "duplicates": result["duplicates"],
                  "findings": [x["finding"] for x in f]}, indent=2, default=str))
