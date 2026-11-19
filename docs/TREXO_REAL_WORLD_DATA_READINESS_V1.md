# TREXO — Real-World Data Readiness V1

**Document ID:** `TREXO-DATA-READINESS-V1`
**Version:** V1
**Status:** `READY_FOR_OWNER_REVIEW`
**Scope:** A field-level and capability-level statement of what the TREXO-INDIA Dead Stock Intelligence Platform can and cannot do with real business data, based on the audited transaction dataset and the documented data requirements.
**Prepared by role:** Data Readiness Analyst (design-only)
**Repository:** `E:\TREXO-INDIA`
**Review date:** 2026-11-19
**Companion documents:** `docs/DEAD_STOCK_DATA_REQUIREMENTS_V1.md`, `docs/DEAD_STOCK_INTELLIGENCE_RESEARCH_V1.md`, `docs/TREXO_INTELLIGENCE_ARCHITECTURE_V1.md`, `docs/TREXO_APPROVAL_REVIEW_PACK_V1.md`, `docs/TREXO_DATA_ONBOARDING_SPECIFICATION_V1.md`, `docs/TREXO_DATA_QUALITY_CONTRACT_V1.md`, `docs/TREXO_DATA_SOURCE_AND_LICENCE_REGISTER_V1.md`

> **This document contains no implementation.** It defines requirements, availability and blockers only. No schema, pipeline, script, dataset or integration is created, changed or approved by this document. No item in this document is `APPROVED`.

---

## 1. Purpose

This document answers one question for every capability TREXO intends to offer:

> *With the data we actually hold today, plus the data a real business could realistically supply, what can TREXO truthfully claim — and what is blocked, and by exactly what?*

It exists to prevent three failure modes:

1. **Over-claiming.** Presenting historical sales inactivity as current dead stock.
2. **Under-specifying.** Telling a pilot customer "we need your inventory data" without naming the field, the grain and the reason.
3. **Silent simulation.** Filling a missing stock or cost field with an estimate and presenting the result as measured.

The document is deliberately blunt. Where a capability is blocked, it says so and names the missing field. Where a capability is partially available, it separates the readable part from the unreadable part.

---

## 2. Scope

### 2.1 In scope

- The eight fields present in `data/raw/Online Retail.xlsx` and their measured quality.
- The derived fields documented as reproducible from those eight fields.
- The business data domains A–G required for the full dead-stock capability set.
- A field-level availability matrix and a capability readiness matrix.
- A minimum viable data set and a three-phase data request plan for a real pilot.
- Data-volume, granularity, multi-warehouse and multi-organisation expectations.
- An explicit list of claims that must never be made.

### 2.2 Out of scope

| Item | Position |
|---|---|
| Schema creation or migration | Not started — design only |
| Ingestion code or connectors | Not started — see onboarding specification |
| Any new dataset acquisition or download | Not performed |
| V3 dataset | Not created |
| Rule approval (D01–D07) | `PENDING` owner decision |
| Forecasting / ML | Out of scope until separately approved |
| Backend, API or user interface | Not built |
| Commercial or contractual terms | Not negotiated |

### 2.3 Relationship to existing documents

This document **does not replace** `DEAD_STOCK_DATA_REQUIREMENTS_V1.md`. That document classifies fields and states capability gaps; this document adds:

- a consolidated field-level availability matrix with a fourth class (`External`),
- a capability readiness matrix expressed in the project status vocabulary,
- a phased, pilot-facing data request sequence,
- explicit volume, grain and multi-entity expectations.

Where the two documents overlap, the statements here are consistent with the earlier document and add operational detail. No earlier conclusion is contradicted.

---

## 3. Evidence basis

| Evidence item | Value | Source |
|---|---|---|
| Source dataset | `data/raw/Online Retail.xlsx` | Repository file, unchanged |
| Rows | 541,909 | Audited |
| Distinct invoices | 25,900 | Audited |
| Distinct StockCodes (raw, after `astype(str).strip()`) | 4,070 | Audited |
| Date coverage | 2010-12-01 to 2011-12-09 | Audited |
| Rows without CustomerID | 135,080 | Audited |
| Rows without Description | 1,454 | Audited |
| Original fields | `InvoiceNo`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`, `UnitPrice`, `CustomerID`, `Country` | Source workbook |
| Provenance | UCI Machine Learning Repository, Chen D. 2015, DOI `10.24432/C5BW33`, CC BY 4.0 | Dataset register |
| V2 sale definition | `InvoiceNo` not starting with `C` **AND** `Quantity > 0` **AND** `UnitPrice > 0` | `docs/TRANSACTION_CLASSIFICATION_POLICY_V1.md` |
| Open audit anomalies | 93, all `OPEN`, none resolved | Audit V1 |
| Governance decisions | D01–D07, all `PENDING` | `TREXO_APPROVAL_REVIEW_PACK_V1.md` |

**Measured data issues carried into readiness assessment:**

| Ref | Issue | Scale |
|---|---|---|
| D01 | Bad-debt accounting rows | 3 rows, net −£11,062.06 |
| D02 | Non-standard-code V2 rows | 2,762 rows, £412,565.65 |
| D03 | Cancellations and zero-price negative rows | 9,288 cancellation + 1,336 zero-price negative |
| D04 | Exact duplicate extra rows | 5,268 rows, £21,740.98 |
| D05 | Zero-price rows | 2,515 rows |
| D06 | Mixed-typed and case-variant StockCodes | 487,036 int-typed + 54,873 str-typed; 112 case collisions |
| D07 | Manual-review rows | 3,025 rows |

These are **transaction-quality** facts. They affect the trustworthiness of historical sales metrics. They do **not** supply inventory, cost or supplier truth, which are absent entirely.

---

## 4. Honesty rules

These rules bind every future output, report and conversation with a customer.

1. **Stock is not derivable from sales.** No sequence of invoices, however long, yields a current on-hand quantity. Any such inference is fabrication.
2. **Historical inactivity is not dead stock.** A product with no sale in a window is `HISTORICALLY_NON_MOVING`. It is never `DEAD` without on-hand evidence and an owner-approved definition.
3. **Selling price is not cost.** `UnitPrice` is a revenue fact. It must never populate an inventory valuation, carrying cost or loss figure.
4. **Missing is data.** A blocked field is reported as blocked, never as zero, null-filled or estimated.
5. **UNKNOWN survives.** Unresolved classifications stay unresolved until evidence arrives; they are not collapsed into a convenient category.
6. **Every number carries its window and rule version.** A metric without a stated period and rule version is not reportable.
7. **Evidence labels travel.** Statements are labelled as directly verified, derived, inferred or unresolved, consistent with the approval pack convention.
8. **No silent joins.** Combining two sources requires a documented key, and unmatched rows are reported, not dropped.

---

## 5. Required data domains A–G

Each domain below states the required fields, why they are needed, the capability they unblock, current availability, and target granularity.

### A. Product master

| Attribute | Detail |
|---|---|
| Required fields | `product_key` (canonical), `original_code` (as received), `description`, `product_family`, `brand`, `category`, `unit_of_measure`, `pack_size`, `lifecycle_status` (`ACTIVE` / `DISCONTINUED` / `SEASONAL` / `UNKNOWN`), `lifecycle_effective_date`, `is_physical_good`, `country_of_origin` (optional), `barcode` (optional) |
| Why needed | Separates real products from services, postage, fees and adjustments; merges case and type variants reversibly; distinguishes expected end-of-life from unexpected stall |
| Capability unblocked | Stable product identity; correct product count; defensible ABC/FSN population; `DEAD` vs `DISCONTINUED` distinction |
| Currently available | **NO** — no product master exists. Only `StockCode`, `Description` (free text, 1,454 missing) and inferred code families |
| Target granularity | One row per canonical product; effective-dated lifecycle history; one-to-many alias table mapping raw codes to canonical keys |
| Status | `BLOCKED_BY_EXTERNAL_DATA` |

### B. Inventory snapshots

| Attribute | Detail |
|---|---|
| Required fields | `snapshot_date`, `product_key`, `warehouse_id`, `on_hand_qty`, `reserved_qty` (optional), `in_transit_qty` (optional), `unit_cost` or `average_cost`, `currency`, `source_system` |
| Why needed | The only source of current stock position; the foundation of every current-state claim |
| Capability unblocked | Current non-moving inventory, stock coverage, excess analysis, inventory valuation, dead-stock confirmation |
| Currently available | **NO** — the dataset has no stock-on-hand field of any kind |
| Target granularity | One row per (`snapshot_date`, `product_key`, `warehouse_id`); at least weekly; daily preferred for fast-moving categories |
| Status | `BLOCKED_BY_EXTERNAL_DATA` |

### C. Stock movements

| Attribute | Detail |
|---|---|
| Required fields | `movement_id`, `movement_date`, `movement_type` (receipt, issue, transfer, adjustment, return, write-off), `product_key`, `warehouse_id`, `quantity_signed`, `reference_document`, `reason_code` (for adjustments), `created_by` (optional) |
| Why needed | Explains why on-hand changed between snapshots; identifies unexplained adjustments and orphan movements |
| Capability unblocked | Movement reconciliation, adjustment governance, snapshot continuity, audit-grade stock evidence |
| Currently available | **NO** — no stock ledger, movement record or returns record |
| Target granularity | One row per movement event |
| Status | `BLOCKED_BY_EXTERNAL_DATA` |

### D. Purchase orders and goods receipts

| Attribute | Detail |
|---|---|
| Required fields | **PO:** `po_id`, `po_line_id`, `product_key`, `supplier_id`, `order_date`, `expected_date`, `ordered_qty`, `unit_cost`, `currency`, `status`. **Receipt:** `receipt_id`, `receipt_date`, `po_id` (where applicable), `product_key`, `warehouse_id`, `received_qty`, `unit_cost`, `supplier_id`, `batch` (optional) |
| Why needed | Establishes unit age (FIFO layers); identifies open orders that should be held; enables overstock diagnosis |
| Capability unblocked | Inventory ageing, receipt-driven valuation, reorder hold, overstocking analysis |
| Currently available | **NO** — no purchase orders, no goods receipts, no supplier references |
| Target granularity | One row per PO line and one row per receipt line |
| Status | `BLOCKED_BY_EXTERNAL_DATA` |

### E. Financial valuation

| Attribute | Detail |
|---|---|
| Required fields | `product_key`, `valuation_date`, `valuation_method` (`FIFO` / `WEIGHTED_AVERAGE` / `STANDARD`), `unit_cost`, `inventory_value`, `currency`, `holding_rate_components` (cost of capital, storage, insurance, shrinkage, obsolescence), `markdown_history`, `recovery_rate` by channel and age band |
| Why needed | Converts unit quantities into money; supports carrying cost, exposure and recovery estimates |
| Capability unblocked | Capital tied up, carrying cost, markdown loss, recovery value, financial exposure ranking |
| Currently available | **NO** — only selling price exists, which is a revenue field and explicitly not cost |
| Target granularity | One row per (`valuation_date`, `product_key`, `warehouse_id`); holding rates as an effective-dated policy table |
| Status | `BLOCKED_BY_EXTERNAL_DATA` |

### F. Supplier and procurement

| Attribute | Detail |
|---|---|
| Required fields | `supplier_id`, `supplier_name`, `lead_time_days`, `lead_time_variability_days`, `minimum_order_quantity`, `return_window_days`, `return_terms`, `payment_terms`, `active_flag` |
| Why needed | Makes replenishment realistic; enables supplier return as a recovery action; supports lead-time anomaly detection |
| Capability unblocked | Reorder point, safety stock, supplier return recommendation, purchase-quantity optimisation |
| Currently available | **NO** — no supplier field, no lead times, no MOQ, no return terms |
| Target granularity | One row per supplier; effective-dated terms |
| Status | `BLOCKED_BY_EXTERNAL_DATA` |

### G. Business context

| Attribute | Detail |
|---|---|
| Required fields | `organisation_id`, `warehouse_id` and location attributes, `calendar` (holidays, trading days), `promotion_calendar`, `service_level_policy`, `assortment_status` per product, `currency_policy`, `unit_policy` |
| Why needed | Distinguishes promotional dips from organic decay; separates trading days from calendar days; defines the acceptable service level |
| Capability unblocked | Seasonality adjustment, at-risk scoring, policy-consistent replenishment |
| Currently available | **NO** — only invoice country, which is not a delivery destination and not a warehouse |
| Target granularity | Organisation-level policy; warehouse-level location; calendar at day level per market |
| Status | `BLOCKED_BY_EXTERNAL_DATA` |

---

## 6. Field-level availability matrix

Class definitions: **Available** = present in the source file today. **Derivable** = computable from Available fields by a documented, reproducible transformation. **Missing** = not present and not computable; a business system must supply it. **External** = neither in the source nor in the business's own systems; market, benchmark or calendar data.

| Field | Class | Present today | Blocks if absent |
|---|---|---|---|
| `InvoiceNo` | Available | Yes | Invoice grouping, cancellation marker |
| `StockCode` | Available | Yes (mixed type) | Product key — requires text cast first |
| `Description` | Available | Yes (1,454 missing) | Product naming, write-off evidence |
| `Quantity` | Available | Yes | Demand volume |
| `InvoiceDate` | Available | Yes | All time-based metrics |
| `UnitPrice` | Available | Yes | Line value, revenue ABC |
| `CustomerID` | Available | Yes (135,080 missing) | Customer segmentation only |
| `Country` | Available | Yes | Weak regional signal |
| `SourceRow` | Derivable | Yes | Lineage and traceability |
| `LineValue` | Derivable | Yes | Revenue-side exposure proxies |
| `InvoicePrefix` | Derivable | Yes | Classification |
| `ProductKeyRaw` | Derivable | Yes | Per-product metrics |
| `ProductKeyCanonical` | Derivable (policy `PENDING`, D06) | Conditionally | Stable product identity |
| `RecencyDays` | Derivable | Yes | Historical inactivity |
| `SalesVelocity` | Derivable | Yes | Coverage numerator |
| `SalesFrequency` | Derivable | Yes | FSN class |
| `TrendRatio` | Derivable | Yes | Demand decay |
| `DemandCV` | Derivable | Yes | XYZ class |
| `MonthlySales` | Derivable | Yes | Seasonality, trend |
| `ABCClass` | Derivable | Yes | Prioritisation |
| `XYZClass` | Derivable (thresholds `PENDING`) | Conditionally | Variability ranking |
| `FSNClass` | Derivable | Yes | Movement class |
| `ProductLifecycleStatus` | Missing | No | Dead vs discontinued |
| `OnHandQty` | Missing | No | Every current-state claim |
| `ReservedQty` | Missing | No | Available-to-promise |
| `WarehouseID` | Missing | No | Location analysis, transfers |
| `SnapshotDate` | Missing | No | Stock trend, continuity |
| `UnitAcquisitionCost` | Missing | No | All inventory money figures |
| `AverageCost` | Missing | No | Valuation |
| `Currency` | Missing | No | Cross-currency safety |
| `ReceiptDate` / `ReceiptQty` | Missing | No | Ageing, FIFO layers |
| `MovementType` / `MovementID` | Missing | No | Movement reconciliation |
| `SupplierID` | Missing | No | Return, replenishment |
| `LeadTimeDays` | Missing | No | Reorder point, safety stock |
| `MinimumOrderQuantity` | Missing | No | Purchase optimisation |
| `ReturnWindowDays` | Missing | No | Supplier return |
| `POID` / `OpenPOQty` | Missing | No | Reorder hold |
| `HoldingRateComponents` | Missing | No | Carrying cost |
| `MarkdownHistory` | Missing | No | Markdown loss |
| `RecoveryRate` | Missing | No | Recovery valuation |
| `PromotionCalendar` | Missing | No | Promo vs decay separation |
| `ServiceLevelPolicy` | Missing | No | Safety stock |
| `HolidayCalendar` | External | No | Correct seasonality |
| `MarketDemandIndex` | External | No | Market-wide vs share loss |
| `LiquidationBenchmark` | External | No | Recovery realism |
| `FreightRate` | External | No | Landed cost |
| `IndustryBenchmarkKPI` | External | No | Turnover context |

**Reading the matrix:** only the first eight rows are facts drawn from the source. Rows 9–24 are reproducible mathematics over those facts. Everything from row 25 onwards is absent and must be supplied by a business system or an external provider.

---

## 7. Capability readiness matrix

Status values follow the project vocabulary. No row may be marked `APPROVED`.

| # | Capability | Status | Exact blocker |
|---|---|---|---|
| 1 | Historical sales inactivity (`HISTORICALLY_NON_MOVING`) | `COMPLETED` (analysis) / `READY_FOR_APPROVAL` (policy) | Values are computable; exact figures remain conditional on D02 and D06 owner decisions (`BLOCKED_BY_OWNER`) |
| 2 | Current non-moving inventory | `BLOCKED_BY_EXTERNAL_DATA` | No `on_hand_qty` and no `snapshot_date`; no inventory snapshot of any kind has been supplied |
| 3 | Inventory ageing | `BLOCKED_BY_EXTERNAL_DATA` | No `receipt_date`; no goods-receipt ledger, therefore no FIFO age layers |
| 4 | Actual dead stock | `BLOCKED_BY_EXTERNAL_DATA` **and** `BLOCKED_BY_OWNER` | Requires on-hand evidence **and** an owner-approved definition of dead stock; neither exists |
| 5 | Future dead-stock risk | `NOT_STARTED` | No approved forecasting method; no on-hand input; explicit approval gate not crossed |
| 6 | Financial exposure | `BLOCKED_BY_EXTERNAL_DATA` | No `unit_acquisition_cost`, no `average_cost`, no holding-rate policy; selling price cannot substitute |
| 7 | Prevention (reorder hold, safety stock, min/max) | `BLOCKED_BY_EXTERNAL_DATA` | No on-hand, no lead time, no open purchase orders, no service-level policy |
| 8 | Recovery (markdown, bundle, transfer, return) | `BLOCKED_BY_EXTERNAL_DATA` | Detection is possible from sales; benefit quantification needs cost, stock, supplier terms and recovery rates |

### 7.1 Partial capabilities and what exactly is available

| Capability | Available part | Unavailable part |
|---|---|---|
| Product risk ranking | Historical recency, frequency, velocity, ABC/XYZ/FSN from transactions | Any statement about whether the product is currently held |
| Revenue analysis | Historical line value at selling price | Any inventory valuation |
| Data-quality signalling | 93 open anomalies as confidence modifiers | Resolution of those anomalies — all `PENDING` owner approval |
| Recovery targeting | List of historically inactive products | Whether stock exists to recover, and what it is worth |

---

## 8. Minimum viable data set for a first real pilot

A pilot must be honest, bounded and reviewable. The minimum set below is the smallest collection that permits a **current-state** statement, not merely a historical one.

### 8.1 Tier 1 — indispensable

| Dataset | Minimum fields | Minimum grain | Why indispensable |
|---|---|---|---|
| Product master | `product_key`, `description`, `is_physical_good`, `lifecycle_status` | One row per product | Identity and physical/service separation |
| Inventory snapshot | `snapshot_date`, `product_key`, `warehouse_id`, `on_hand_qty` | One snapshot, one row per product × warehouse | The current stock position |
| Sales transactions | `InvoiceNo`, `StockCode`, `Quantity`, `InvoiceDate`, `UnitPrice` | Existing V2 grain | Demand history for comparison |

Without Tier 1, TREXO can only report historical inactivity. It cannot report current stock, current non-moving inventory or dead stock.

### 8.2 Tier 2 — required for value, not for honesty

| Dataset | Minimum fields | Unlocks |
|---|---|---|
| Cost master | `product_key`, `unit_cost`, `currency`, `valuation_method`, `effective_date` | Financial exposure |
| Goods receipts | `receipt_date`, `product_key`, `received_qty`, `unit_cost` | Ageing, FIFO layers |
| Purchase orders | `po_id`, `product_key`, `ordered_qty`, `expected_date`, `status` | Reorder hold, open-order visibility |

### 8.3 Tier 3 — required for recommendation quality

Supplier terms, lead times, holding-rate policy, markdown history, promotion calendar, recovery rates, service-level policy.

### 8.4 Explicit non-substitutes

| Tempting substitute | Why it is rejected |
|---|---|
| Inferring stock from cumulative sales | Produces a negative or fictional balance; ignores receipts across the dataset boundary |
| Using selling price as cost | Category error between turnover and capital |
| Using a single snapshot as a trend | One point cannot establish direction; continuity needs at least two |
| Using a generic industry benchmark as the business's position | Benchmark is context, not measurement |

---

## 9. Phased data requests

Phases are sequential in *value*, not strictly in *time*; a customer may supply Phase 3 fields early if they exist. Nothing in any phase is approved.

### Phase 1 — Minimal (unblocks current-state honesty)

| # | Request | Format expectation | Acceptance condition |
|---|---|---|---|
| 1 | Product master extract | CSV or Excel, one row per product | Every transaction product key resolves or is quarantined |
| 2 | One inventory snapshot | CSV, one row per product × warehouse | `on_hand_qty` present and non-null; snapshot_date stated |
| 3 | Warehouse list | CSV, one row per location | Every snapshot warehouse resolves |
| 4 | Currency and unit declaration | Written statement | One currency, one unit per field, explicitly stated |

**Outcome if Phase 1 is met:** current non-moving inventory can be stated as a measurement, with confidence qualifiers. Dead stock still requires an owner-approved definition.

### Phase 2 — Valuation and ageing

| # | Request | Format expectation | Acceptance condition |
|---|---|---|---|
| 5 | Cost master or valuation extract | CSV, effective-dated | `unit_cost` present for ≥ 95% of on-hand products, gaps declared |
| 6 | Goods receipts, 12–24 months | CSV, line level | Receipt dates and quantities reconcile to snapshot movement |
| 7 | Open purchase orders | CSV, line level | Status and expected date present |

**Outcome if Phase 2 is met:** ageing, inventory value, carrying-cost inputs and reorder-hold recommendations become computable.

### Phase 3 — Prevention and recovery

| # | Request | Format expectation | Acceptance condition |
|---|---|---|---|
| 8 | Supplier master and terms | CSV, effective-dated | Lead time, MOQ and return window present |
| 9 | Holding-rate policy | Written policy | Components named, not a single blended guess |
| 10 | Markdown and price history | CSV, effective-dated | Markdown dates and prices present |
| 11 | Recovery outcomes | CSV, historical liquidations | Channel, age band and realised price present |
| 12 | Promotion calendar | CSV or ICS | Dates and affected products present |

**Outcome if Phase 3 is met:** prevention and recovery recommendations can carry quantified benefit ranges rather than qualitative advice.

### Phase dependency summary

| Phase | Blocks if incomplete | Cannot be claimed |
|---|---|---|
| 1 | Current non-moving inventory, dead stock | Any current stock statement |
| 2 | Ageing, valuation, exposure | Any money figure about held stock |
| 3 | Prevention value, recovery value | Any quantified saving or recovery estimate |

---

## 10. Data-volume and granularity expectations

| Dataset | Expected volume (order of magnitude) | Grain | Growth |
|---|---|---|---|
| Product master | 10³–10⁵ rows | Product | Slow |
| Inventory snapshot | 10⁴–10⁶ rows per snapshot | Product × warehouse × date | Linear with snapshot frequency |
| Stock movements | 10⁵–10⁷ rows/year | Movement event | Linear with transaction volume |
| Purchase orders | 10⁴–10⁵ lines/year | PO line | Linear with purchasing activity |
| Goods receipts | 10⁴–10⁵ lines/year | Receipt line | Linear with purchasing activity |
| Sales transactions | 10⁵–10⁷ rows/year | Invoice line | Linear with trading volume |
| Supplier master | 10²–10⁴ rows | Supplier | Slow |
| Cost master | 10³–10⁵ rows | Product × effective date | Slow |

**Grain rules:**

1. Never aggregate before validation. Validation operates at the finest supplied grain.
2. Every dataset carries an explicit primary key. If the source has none, a documented composite key is defined and stored.
3. Snapshots are append-only. A corrected snapshot is a new snapshot with a correction reference, not an overwrite.
4. Time zones and date boundaries must be declared by the source system, not assumed.

**Volume implications for the pilot:** the current transaction file is 541,909 rows and processes at batch scale. Inventory snapshots at daily frequency with 10⁴ products and 10 warehouses would produce 10⁵ rows per day — a scale that is manageable in batch but requires a documented partitioning key of (`snapshot_date`, `warehouse_id`).

---

## 11. Multi-warehouse and multi-organisation considerations

### 11.1 Multi-warehouse

| Consideration | Requirement |
|---|---|
| Identity | `warehouse_id` must be a stable, source-assigned key; warehouse names change, keys must not |
| Stock pooling | Product-level stock may only be pooled across warehouses when the business confirms fungibility; otherwise report per location |
| Transfers | A transfer is two movements (out of A, into B) with one reference; both must reconcile |
| Demand attribution | Sales must map to a fulfilling warehouse where the source supports it; otherwise demand is unallocated and declared |
| Ageing | Age layers are per warehouse; a network-level age is a derived summary, not a fact |
| Coverage | Local demand must be used for local coverage; national demand for a national stock position is a different question |

### 11.2 Multi-organisation

| Consideration | Requirement |
|---|---|
| Isolation | `organisation_id` on every row of every dataset; no cross-tenant query path |
| Identity collision | Two organisations may legitimately use the same product code for different products; canonical identity is scoped to organisation |
| Currency | Currency is declared per organisation; no implicit conversion |
| Calendar | Trading calendars are per organisation and per market |
| Benchmarking | Cross-organisation comparison requires explicit consent and de-identification; it is not a default feature |
| Provenance | `import_id`, `source_file_hash` and `mapping_version` are stored per organisation, per import |

**Rule:** multi-organisation support is a design requirement, not a current capability. No multi-tenant storage exists today.

---

## 12. What we must never claim

The following statements are prohibited regardless of how compelling the sales pattern looks.

| # | Prohibited claim | Permitted alternative |
|---|---|---|
| 1 | "This product is dead stock." | "This product had no observed sale in the period [start–end]." |
| 2 | "You are holding £X of dead stock." | "No inventory valuation is available; historical revenue for this product was £X." |
| 3 | "You have N units of this product." | "No stock record was supplied for this product." |
| 4 | "This product has been in the warehouse for 18 months." | "The last observed sale was 18 months before the dataset end date." |
| 5 | "Your dead stock is worth £X." | "Inventory value is `BLOCKED`: cost data has not been supplied." |
| 6 | "This item is obsolete." | "The product had no observed sale in the window; lifecycle status is `UNKNOWN`." |
| 7 | "Our model predicts this will not sell." | "Historical trend is declining; no approved forecast exists." |
| 8 | "Stock is zero because sales stopped." | "Sales stopped; stock position is unknown." |
| 9 | "We have cleaned the data." | "Known anomalies are flagged and carried as confidence modifiers." |
| 10 | "This is the approved definition." | "This is a proposed definition awaiting owner approval." |
| 11 | "Across all your warehouses." | "For the warehouse records supplied, covering [list]." |
| 12 | "This saved you £X." | "The theoretical exposure is X under stated assumptions; realised saving is not measured." |
| 13 | "The dataset is complete." | "The dataset covers [dates] and contains [n] rows; coverage outside these bounds is unknown." |
| 14 | "Duplicates were removed." | "Duplicates were flagged; the deduplicated view differs by [n] rows and £X." |
| 15 | "The product count is 4,070." | "The raw code count is 4,070; the canonical product count is `PENDING` the D02 and D06 decisions." |

**The single sentence that governs all output:** *a product with zero recent sales and no stock record must be labelled "no observed sale in the period", never "dead stock".*

---

## 13. Readiness summary


| Dimension | Position | Status |
|---|---|---|
| Transaction data | Present, audited, 93 anomalies open | `COMPLETED` (analysis) |
| Product identity | Raw codes usable; canonical identity undecided | `BLOCKED_BY_OWNER` (D02, D06) |
| Current stock | Absent | `BLOCKED_BY_EXTERNAL_DATA` |
| Cost and valuation | Absent | `BLOCKED_BY_EXTERNAL_DATA` |
| Procurement | Absent | `BLOCKED_BY_EXTERNAL_DATA` |
| Supplier terms | Absent | `BLOCKED_BY_EXTERNAL_DATA` |
| Business context | Absent | `BLOCKED_BY_EXTERNAL_DATA` |
| Onboarding process | Specified, not implemented | `READY_FOR_APPROVAL` (design) |
| Data-quality contract | Specified, not implemented | `READY_FOR_APPROVAL` (design) |
| Source and licence register | Established for one dataset only | `IN_PROGRESS` |

**Overall readiness:** historical sales intelligence is `READY_FOR_APPROVAL`. Real-world inventory intelligence is `BLOCKED_BY_EXTERNAL_DATA` until Phase 1 is supplied and `BLOCKED_BY_OWNER` until D01–D07 are decided. No capability in this document is `APPROVED`.

---

## 14. Open items and next actions

| # | Item | Owner role | Status |
|---|---|---|---|
| 1 | Decide D01–D07 | Project owner | `BLOCKED_BY_OWNER` |
| 2 | Identify a pilot business with inventory data | Commercial owner | `NOT_STARTED` |
| 3 | Agree data-sharing terms and retention | Legal / commercial | `NOT_STARTED` |
| 4 | Request Phase 1 data set | Data lead | `NOT_STARTED` |
| 5 | Confirm currency and unit declarations | Pilot business | `NOT_STARTED` |
| 6 | Review onboarding specification | Project owner | `READY_FOR_APPROVAL` |
| 7 | Review data-quality contract | Project owner | `READY_FOR_APPROVAL` |
| 8 | Extend source register for any new dataset | Data lead | `IN_PROGRESS` |

---

**Status: Real-World Data Readiness V1 complete as design documentation. No implementation, no schema, no data acquisition, and no approval. Awaiting owner review.**
