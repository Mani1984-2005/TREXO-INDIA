# TREXO — Dead Stock Data Requirements V1

**Status:** RESEARCH/REQUIREMENTS DOCUMENT — no data collected, no schema
migrated, awaiting review.
**Companions:** `docs/DEAD_STOCK_INTELLIGENCE_RESEARCH_V1.md`,
`docs/TREXO_INTELLIGENCE_ARCHITECTURE_V1.md`,
`docs/TREXO_APPLICATION_ARCHITECTURE_PROPOSAL_V1.md`,
`docs/DATA_SOURCE_REGISTER.md` (existing register of sources).

## How fields are classified

| Class | Meaning |
|---|---|
| **Available** | Present as a column in `data/raw/Online Retail.xlsx` today |
| **Derivable** | Computable from Available fields by a documented, reproducible transformation (no new source needed) |
| **Missing** | Not present and not computable — must be supplied by a business system (ERP/POS/WMS/spreadsheets) |
| **Requires external data** | Belongs to neither the raw file nor the business's own transactional systems — market, benchmark, calendar or channel data |

Every derivation below names its source columns; every missing field names
the capability it blocks (methodology IDs from the research document,
score letters A–D).

---

## A. Available (raw file, 8 columns — audited facts)

| Column | Type reality | Quality facts (measured) | Role in dead-stock intelligence |
|---|---|---|---|
| `InvoiceNo` | string; 6-digit numeric or `C`/`A` prefix | 25,900 invoices; prefixes NUMERIC 22,061 / C 3,836 / A 3 | Order grouping, cancellation marker (project convention) |
| `StockCode` | **mixed int/str on read** (487,036 int + 54,873 str) | 4,070 distinct after `astype(str).strip()`; case variants exist (`15056BL`/`15056bl`, `M`/`m`); 35 non-product codes | Product key (raw, per project convention); normalisation policy still unapproved |
| `Description` | string | 1,454 missing (0.27%); free text; case variants preserved | Product name; admin/write-off/correction evidence (Audit V1 buckets) |
| `Quantity` | integer | 10,624 negative, 0 zero, rest positive; extreme values audited (80,995 / 74,215 / ±9,600) | Demand volume (subject to classification rules) |
| `InvoiceDate` | datetime | 2010-12-01 08:26 → 2011-12-09 12:50 = **373.2 days** | All time-based indicators (recency/frequency/trend/seasonality) |
| `UnitPrice` | float | 2,515 rows at 0.00; 2 negative (bad debt); no missing | Line value, revenue-side ABC |
| `CustomerID` | float64 | 135,080 missing (24.93%) | Demand segmentation only (not needed for stock) |
| `Country` | string | Invoice country, **not** delivery destination (Audit V1 limitation) | Weak regional signal |

**Not in the file (confirmed by audit reconnaissance):** stock balances,
warehouse, receipts, purchases, suppliers, costs, lead times, lifecycle
events, returns linkage, stock ledger of any kind.

## B. Derivable (documented transformations)

| Derived field | Formula / rule | Source columns | Blocks nothing (used by) |
|---|---|---|---|
| `SourceRow` | Excel row index (header = row 1) | row position | Traceability/lineage for every score |
| `LineValue` | `Quantity × UnitPrice` (float64, unrounded) | Quantity, UnitPrice | Revenue-side exposure proxies |
| `InvoicePrefix`, `IsCancellationInvoice` | `^([A-Za-z]+)` / startswith `C` | InvoiceNo | Classification (done in Audit V1) |
| `AuditPartition`, `ProposedCategory`, `ConfidenceLevel`, `PhysicalInventoryImpact` | Ordered evidence rules (25 rules) | all columns | Cleaning inputs before any metric |
| `DescriptionBucket` | Pattern buckets (negative/zero evidence) | Description | Confidence of metric inputs |
| Product key (raw) | `StockCode.astype(str).str.strip()` — **mandatory first step** | StockCode | All per-product metrics (the int/str pitfall silently drops 487k rows if skipped) |
| Product key (normalised) | `str.upper()` case-fold — **proposed, not approved** | StockCode | Merging `M`/`m` and `15056BL`/`15056bl` |
| `recency_days` | `t_eval − max(InvoiceDate)` per product | InvoiceDate | Score A1 (measured: 460 products >180d) |
| `sales_velocity` | `units_sold / W` per product | Quantity, InvoiceDate | A2, coverage numerator (M3) |
| `sales_frequency` | `nunique(InvoiceNo)`, line counts, days-with-sale | InvoiceNo | A3, FSN (M2; measured 154 single-invoice products) |
| `trend_ratio` | `rate(recent W) / rate(prior W)` | Quantity, InvoiceDate | A4 |
| `demand_cv` | `σ_monthly / μ_monthly` | monthly aggregates | A5, XYZ (M9) |
| `p_zero_sale` | `e^(−μ·W)` (Poisson) or neg-binomial variant | monthly aggregates | A6 (M7) |
| Monthly product sales | groupby product × month (`product_monthly_sales_v2.csv` already exists, 34,069 records) | Quantity, InvoiceDate | A4–A7, seasonality (M13) |
| ABC classes | cumulative revenue share 70/20/10 (illustrative bands) | LineValue | A8 prioritisation (measured A=543) |
| XYZ / FSN classes | CV bands / issue-count or recency bands (**thresholds to be approved**) | monthly or invoice counts | M9, M10 |
| Seasonal index | `demand(month) / mean(demand)` over available cycle | monthly sales | A7 (confidence-limited: 1 cycle) |
| `days_since_first_sale`, product age | first-sale date difference | InvoiceDate | Lifecycle proxy (M14) |
| Unusual-invoice flags (S1–S6) | Audit V1 selection rules | all columns | Excluding anomalies from metric inputs |
| Duplicate flag | exact-row duplicate detection (5,268 rows) | all raw columns | Data-quality modifier on scores |

## C. Missing (business systems must supply)

| Missing field | Needed for (IDs) | If absent, this capability is blocked |
|---|---|---|
| `on_hand_qty` (product × warehouse × date) | M4, M6, M12; Score **B**, exposure **D** | **All current dead-stock claims**, excess/coverage analysis, reorder rules |
| `inventory_snapshot_date` / snapshot history | M5, M12; B, D | Trend of stock vs trend of sales |
| `receipt_date`, `receipt_qty` (goods-in ledger) | M5 (aging), supplier returns | Unit age, FIFO layers, return-window checks |
| `unit_acquisition_cost` / `average_cost` | M4, M12; D | Turnover, capital tied up, markdown-loss, recovery, every currency figure except historical revenue |
| `supplier_id`, supplier terms (MOQ, return window, lead time) | M6, interventions 9/10 | Buy-back and purchase-optimisation actions; realistic reorder |
| `lead_time_days` (+ variability) | M6, interventions 2/3 | Reorder point, safety stock, coverage judgement |
| `warehouse/location` | intervention 8, M5 | Transfers, per-location aging (single- vs multi-site) |
| `lifecycle_status` (active/discontinued) + dates | M14, Score B | Separating expected end-of-life from unexpected stall |
| `holding_rate_components` (capital, storage, insurance, shrink, obsolescence) | Investigation 4 | Carrying cost, economic thresholds (method 5) |
| `storage_footprint_rate` | Investigation 4 | Storage cost component |
| `price/markdown history` | Investigation 4 | Markdown loss and realised recovery |
| `recovery_rate` per channel/age band | Investigation 4; intervention 5 | Liquidation value, discount depth advice |
| `open_purchase_orders` | intervention 1 | Stopping an order already in flight (a top prevention action) |
| `service_level_policy`, safety-stock policy | interventions 2/3/4 | Optimised replenishment |
| `promotion_calendar` | intervention 7, M13 | Distinguishing promo dip/spike from organic decay |
| `footprint/pack dims` (optional) | storage cost | Fine-grained storage costing |

**Minimum viable inventory snapshot (proposal, to request from a business):**

```
inventory_snapshot (
  snapshot_date      DATE      -- daily or weekly cadence
  product_key        TEXT      -- same key rules as transactions
  warehouse_id       TEXT
  on_hand_qty        NUMERIC   -- >= 0, negatives rejected at validation
  average_cost       NUMERIC   -- currency, >= 0
  reserved_qty       NUMERIC   -- optional
  source_system      TEXT      -- lineage
)
grain: one row per (snapshot_date, product_key, warehouse_id)
```

plus `goods_receipts(receipt_date, product_key, warehouse_id, qty, unit_cost,
supplier_id, po_id)` and `purchase_orders(po_id, product_key, qty,
lead_time_days, supplier_id, status)` as the two highest-value follow-ups.

**Cost sourcing options (proposal):** (1) weighted-average cost computed
from receipts; (2) standard-cost master maintained by finance; (3) invoice
import. Selling price must never be substituted (governance rule).

## D. Requires external data

| External field | Source type | Purpose | Availability note |
|---|---|---|---|
| Competitor/market demand index | Market data providers | Distinguishing "market died" from "we lost share" | Paid APIs; not required for V1 |
| Liquidation-channel recovery rates | Auction/liquidator benchmarks or internal history | Realistic recovery value | Derivable only *after* internal liquidations are recorded |
| Economic/seasonal calendars (holidays, events) | Public calendars / commercial | Correct seasonality (M13) | Public sources exist; must be registered in `DATA_SOURCE_REGISTER.md` before use |
| Freight/shipping cost rates | Carrier tariffs | True landed cost | Business contract data |
| Benchmarked inventory KPIs | Industry benchmarks | Context for turnover/aging bands | Vendor/association reports; licence varies |
| Validation datasets (M5 Walmart etc.) | Kaggle/UCI — see §E | Threshold back-testing | Licence check mandatory before download |

## E. External dataset candidates (research only — nothing downloaded)

| Dataset | Origin | Licence (as published) | Best use for TREXO | Suitability / risk |
|---|---|---|---|---|
| **M5 Forecasting (Walmart)** | Kaggle competition ("M5 Forecasting - Accuracy", Walmart-sponsored) | Kaggle competition rules (analysis use; redistribution typically restricted) | Back-test recency/FSN/seasonal thresholds against known sell-through outcomes; intermittent-demand patterns | Excellent analytical fit (hierarchical retail, calendar events, 3,049 series); **must confirm competition terms before any download or redistribution** |
| **UCI Online Retail** (current source) | UCI ML Repository, Chen D. 2015, DOI 10.24432/C5BW33 | **CC BY 4.0** | Baseline reproduction of every figure in these docs | Already in `data/raw/` with provenance; cite DOI when publishing |
| Retail inventory/sales Kaggle datasets (generic) | Kaggle, per-dataset pages | Varies: CC0 / CC BY-SA / "research only" / custom | Practice turnover & excess formulas on data that has on-hand | **Licence varies dataset-by-dataset — read each page; many forbid commercial use** |
| Open government / statistical retail sales | e.g. national statistics offices | Usually open government licences | Seasonality validation at market level | Aggregate only — no product-level dead-stock ground truth |
| Partner/ERP extracts (real business) | Direct from a pilot customer | Contractual | **The only true ground truth for Score B (current dead stock)** | Requires data-sharing agreement, retention and PII terms first |

**Download policy (governance):** register first (`docs/DATA_SOURCE_REGISTER.md`
entry with origin, licence, retrieval date, row count, intended use), store
under `data/external/` with a recorded SHA-256, never overwrite
`data/raw/Online Retail.xlsx` or V1/V2 processed files. **As of this
document: zero external datasets have been downloaded.**

## F. Capability → data gap matrix

| Capability | Fields required | Status |
|---|---|---|
| Historical non-moving / slow-moving detection (Score A) | transactions | **Ready now** |
| Explainable risk ranking (Score A, ABC/XYZ/FSN) | transactions (+ monthly aggregates) | **Ready now** |
| Data-quality-aware confidence | Audit V1 outputs | **Ready now** (93 anomalies open) |
| Current dead-stock confirmation (Score B) | + `on_hand_qty`, `lifecycle_status` | **Blocked** |
| Aging analysis | + receipts with dates | **Blocked** |
| Turnover / carrying cost / financial exposure (Score D) | + `unit_acquisition_cost`, holding rates | **Blocked** |
| Excess inventory & coverage (M6, M12) | + `on_hand_qty`, `lead_time_days` | **Blocked** |
| Reorder stop / safety stock / min-max (interventions 1–4) | + on-hand, lead time, POs, policy | **Blocked** |
| Supplier return / transfer (interventions 8–9) | + supplier terms, warehouses, receipts | **Blocked** |
| Discount/bundle/promo recommendations (5–7) | sales (present) + cost (absent) | **Partial — detection yes, benefit quantification blocked** |
| Future dead-stock risk (Score C) | + approved forecasting | **Not started (forecasting out of scope until approved)** |

## G. Data contracts to enforce at ingestion (proposal)

1. **Key typing:** `StockCode` must be cast to text *before* any pattern or
   group operation (measured failure mode: 487,036 int rows silently fail
   `str.fullmatch`).
2. **No silent drops:** rejected rows go to an error table with reason codes
   and `SourceRow` lineage; counts must reconcile to the source total.
3. **Never rewrite history:** source files immutable (SHA-256 verified);
   derived tables versioned (`v1`, `v2`…), never overwritten.
4. **Missing is data:** nulls preserved and surfaced (`[MISSING]`), never
   imputed silently.
5. **Type/date/units validation** at every ingest (rows failing coercion
   reported — currently 0 for Quantity/UnitPrice/InvoiceDate).
6. **Currency and unit declarations** carried in metadata (all figures here
   are the dataset's native currency, unlabelled in source).
7. **UNKNOWN survives:** classification/ingestion never collapses unknown
   states into known ones.

---

**Status: Dead Stock Data Requirements V1 complete; no data was collected,
no schema was created, awaiting review.**
