# ML Data Quality and Feature Audit

> Generated from the actual raw workbook and delivered ML datasets on 2026-11-19T09:07:19.613460+00:00.
> Pipeline `ml-1.1.0`; raw SHA-256 `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`.

## 1. Dataset shape
| Metric | Value |
|---|---|
| raw | 541909 |
| valid_sales | 527725 |
| distinct_valid_products | 3900 |
| date_min | 2010-12-01 |
| date_max | 2011-12-09 |

## 2. Missing values (raw)
| Column | Missing | % |
|---|---|---|
| InvoiceNo | 0 | 0.00% |
| StockCode | 0 | 0.00% |
| Description | 1,454 | 0.27% |
| Quantity | 0 | 0.00% |
| InvoiceDate | 0 | 0.00% |
| UnitPrice | 0 | 0.00% |
| CustomerID | 135,080 | 24.93% |
| Country | 0 | 0.00% |

## 3. Duplicates
- Raw exact duplicates: **5,268**.
- Exact duplicates inside valid sales, retained and flagged: **5,221**.
- They contribute **15716 units** and **24213.74** line value.
- No duplicate row is silently deleted. Invoice counts use distinct invoices, so they are not inflated by exact duplicates.

## 4. Product identifiers and descriptions
- Raw StockCodes: **4,070**; with valid sales: **3,900**.
- StockCodes needing whitespace strip: **0**; case-variant groups: **112** (case-folding NOT applied).
- Missing Description: **1,454**; blank: **0**; products with multiple descriptions: **650**.

## 5. Transaction quality and exclusions
| Reason | Rows |
|---|---|
| VALID_SALE | 527,725 |
| CANCELLATION_INVOICE | 8,704 |
| NON_PRODUCT_CODE | 2,992 |
| NON_POSITIVE_QUANTITY | 1,324 |
| ZERO_PRICE | 1,161 |
| D01_BAD_DEBT_GROUP | 3 |

- Negative quantity rows: **10,624**; zero price: **2,515**; negative price: **2**; C-invoices: **9,288**.
- Invalid dates: **0**; non-numeric quantity: **0**; non-numeric price: **0**.
- D01 rows in valid sales: **0**; StockCode B rows in raw: **3**, exclusively D01: **True**.

## 6. Time series and product history
- 374 calendar days, 305 valid-sale days, 69 days with no valid sale; max gap 12 days.
- Complete weeks usable by the forecaster: **53**.
- Products assessed at 2011-12-09: **3,900**; age days median 369; single-invoice products 154; single-sale-day products 157.

## 7. Leakage and consistency
- Chronological cutoffs purged: **True**; CV folds purged: **True**.
- Products with any NaN in the feature vector: **0**.
- Feature schema stable: **True**.
- Product aggregation reconciles to valid-sale totals: **True**.
- D01 absent from features: **True**.
- Training and inference both use `build_features`; no separate feature implementation exists.

## 8. Findings
- **INFO** — D01 group is excluded by an explicit first-match rule and absent from valid sales.
- **WARN** — 5,221 exact duplicate valid rows retained; they add 15716 units and 24213.74 line value.
- **WARN** — 1,454 raw rows lack Description; descriptions are not a reliable product key.
- **WARN** — 135,080 raw rows lack CustomerID (24.9%).
- **WARN** — Only 53 complete weeks exist; seasonality cannot be validated.
- **INFO** — 154 products have a single invoice; evidence quality is LOW for them.
- **WARN** — 112 case-variant StockCode groups exist; no case-folding is applied (not approved).

## 9. Decisions still required
1. Duplicate treatment (currently retain + flag; no approved deletion).
2. Product-key case policy (currently no case-folding).
3. Customer-data use (24.9% missing; currently limited to counts and missing-share features).
4. Seasonality needs a second year of data.
