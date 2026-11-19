# D01 Bad-Debt Group — Lineage Audit

> Generated from the raw workbook and actual ML artefacts on 2026-11-19T09:17:20.215452+00:00.
> Pipeline version `ml-1.1.0`. Raw SHA-256 `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`.

## 1. Decision

**D01_APPROVED** — `D01_BAD_DEBT_GROUP` (`BAD_DEBT_A563185_A563187`).

Approved D01 governance decision: complete bad-debt invoice group is a financial adjustment event, excluded from product demand/movement/forecasting/dead-stock features, labels, evaluation and recommendations.

## 2. Source rows (verified)

| Invoice | Source row | Quantity | Unit price | Line value | Stock code | Description |
|---|---|---|---|---|---|---|
| A563185 | 299984 | 1 | — | 11062.06 | B | Adjust bad debt |
| A563186 | 299985 | 1 | — | -11062.06 | B | Adjust bad debt |
| A563187 | 299986 | 1 | — | -11062.06 | B | Adjust bad debt |

- Rows: **3**; source rows **299984, 299985, 299986**.
- Gross positive line value: **11062.06**; gross negative: **-22124.12**; net financial effect: **-11062.06**.
- StockCode `B` rows in raw: **3**; exclusively the D01 group: **True**.
- Source reconciliation OK: **True**.

## 3. Presence in ML data

| Check | Result |
|---|---|
| D01 rows in `valid_sales_v1.csv.gz` | 0 (must be 0) |
| StockCode B rows in `valid_sales_v1.csv.gz` | 0 (must be 0) |
| D01 rows in forecast backtest rows | 0 (must be 0) |
| Quarantined financial rows | 3 |
| Quarantine net line value | -11062.06 |

Training labels/features are constructed only from `valid_sales_v1`, so the absence above covers dead-stock features, labels, calibration, evaluation, forecasting, recommendations and reports.

## 4. Stage-processed artefacts

| Artifact | Exists | Contains B | B rows | Status |
|---|---|---|---|---|
| `data/processed/product_movement_v1.csv` | True | True | 1 | PROTECTED_HISTORICAL_ARTIFACT_NOT_CONSUMED_BY_ML |
| `data/processed/product_movement_v2.csv` | True | True | 1 | PROTECTED_HISTORICAL_ARTIFACT_NOT_CONSUMED_BY_ML |
| `data/processed/product_monthly_sales_v2.csv` | True | True | 1 | PROTECTED_HISTORICAL_ARTIFACT_NOT_CONSUMED_BY_ML |

The Stage-processed files are protected historical artifacts (their own regression suite pins their SHA-256 and row counts). They are **not read by the ML layer**. D01-corrected copies are written for governance-clean consumers:

- `data/ml/product_movement_v1_d01corrected.csv` — 3900 rows.
- `data/ml/product_movement_v2_d01corrected.csv` — 3900 rows.
- `data/ml/product_monthly_sales_v2_d01corrected.csv` — 33955 rows.

Corrected movement contains no StockCode B: **True**.

## 5. Required remediation (status)

- [x] D01 is excluded by invoice before every generic rule (implemented).
- [x] Original source workbook is read-only and unchanged (verified by SHA-256).
- [x] The three rows are preserved in data/ml/excluded_financial_events_v1.csv with SourceRow lineage.
- [x] Stage-processed movement V1/V2 remain protected historical files; ML consumes only valid_sales_v1, which is D01-clean.
- [x] D01-corrected movement exports are written under data/ml/ for governance-clean consumers.

## 6. Affected downstream artifacts

- data/ml/valid_sales_v1.csv.gz: D01 absent (verified).
- ML features/labels/training/backtesting/forecasting/recommendations: derived from valid_sales only; D01 absent.
- reports/ml/dead_stock_classification.csv, dead_stock_intervention_queue.csv, product_movement_classification.csv, forecast_next_8_weeks.csv: derived from valid_sales only.
- data/processed/product_movement_v1/v2.csv: contain the B row as a protected Stage artifact; NOT consumed by ML. Corrected copies in data/ml/.

## 7. Reconciliation result

The approved group reconciles to **3** source rows and a net **-11062.06**. The original source workbook is unchanged (SHA-256 `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`). The raw rows remain in place; only the ML analytic dataset and quarantine record are governed.
