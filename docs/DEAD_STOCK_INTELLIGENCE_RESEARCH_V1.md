# TREXO — Dead Stock Intelligence Research V1

**Status:** RESEARCH DOCUMENT — no implementation. Awaiting review.
**Purpose:** establish the scientific, mathematical and business foundations of
TREXO's primary product: **detecting, analysing, preventing and reducing dead
stock**.
**Companion documents:** `docs/DEAD_STOCK_DATA_REQUIREMENTS_V1.md`,
`docs/TREXO_INTELLIGENCE_ARCHITECTURE_V1.md`,
`docs/TREXO_APPLICATION_ARCHITECTURE_PROPOSAL_V1.md`.

## Evidence basis and honesty rules for this document

- **Measured facts** (marked *measured*) come from
  `data/raw/Online Retail.xlsx` and the completed Special Transaction Audit V1
  (541,909 rows; 25,900 invoices; 4,070 StockCodes; 2010-12-01 → 2011-12-09;
  135,080 rows without CustomerID; 1,454 without Description; 3,385 rows on
  35 non-product StockCodes).
- **Literature formulas** (marked *standard formula*) are established
  inventory-analytics definitions (FSN, ABC, XYZ, turnover, SLOB). They are
  described, not invented; thresholds cited from literature are explicitly
  labelled as *illustrative* because no threshold is universal.
- **Proposals** (marked *proposal*) are TREXO designs awaiting approval.
- **Limitations** are stated wherever the dataset cannot support a claim.

> **Governance rule 15 (binding on this document):** a historical sales
> dataset alone can never prove that a product *is* dead stock **right now**.
> It can only establish *historical non-moving risk*. Every statement below
> that concerns current stock requires inventory evidence this dataset does
> not contain (see `DEAD_STOCK_DATA_REQUIREMENTS_V1.md`).

**External sources consulted:** UCI Machine Learning Repository dataset page
for *Online Retail* (Chen, D., 2015, DOI 10.24432/C5BW33, CC BY 4.0,
541,909 instances, 01/12/2010–09/12/2011, InvoiceNo starting with `c` =
cancellation); Finale Inventory's FSN (fast–slow–non-moving) guide
(finaleinventory.com) for the FSN average-stay / consumption-rate procedure.
No other external source was consulted; where a method is widely known but
not verified against a source here, it is presented as a standard formula
without attribution.

---

# Investigation 1 — Precise definitions

## 1.1 The ten terms are not interchangeable

They vary along four axes: **(a) does the claim concern stock on hand or
sales history? (b) is it time-based, rate-based, or quantity-based? (c) is it
an absolute state or a relative ranking? (d) does it require cost data?**

| Term | Definition (proposed canonical wording) | Entry condition — enters when… | Primary axis | Needs stock on hand? | Needs cost? | Available from current dataset? |
|---|---|---|---|---|---|---|
| **Dead stock** | Inventory that has *no remaining realistic prospect of sale at full value* while still held | Stock on hand > 0 **and** no sale for a policy period **and** no planned demand (e.g. discontinued/season ended) | Time + demand stop, state of *held* stock | **Yes** | For exposure only | **No** — no stock-on-hand field. Only its historical precursor, *historical non-moving risk*, can be computed |
| **Slow-moving inventory** | Stock selling materially slower than the catalog average or the replenishment cycle | Sell-through rate below a chosen threshold (or inventory days above it) for a sustained window | Relative rate | No (rate from sales) | No | **Partly** — sales rate is computable; the *inventory* framing needs stock |
| **Non-moving inventory** | Items with zero sales in a defined observation window | Sales count = 0 over window W (item still active in the assortment) | Count, window-based | No | No | **Yes, historically** — computable per product for any W inside 2010-12-01…2011-12-09 |
| **Excess inventory** | Stock on hand exceeds expected demand for a coverage horizon | On-hand > demand × coverage factor (e.g. > N months of expected demand) | Quantity vs demand | **Yes** | No | **No** — requires on-hand |
| **Obsolete inventory** | Stock that can no longer be sold at all because the product itself is no longer wanted/sellable (fashion, technology, superseded SKU, regulation) | A discontinuation/obsolescence event exists, or sales stopped while substitutes dominate | Product state change | Yes (to value it) | For write-down | **No** — no discontinuation or lifecycle field; sales stop is only a *signal*, not proof |
| **Aging inventory** | Stock whose time-in-warehouse exceeds an aging policy threshold | Age of the *oldest unsold unit* > threshold (FIFO layers) | Age, not demand | **Yes** + receipt dates | No | **No** — requires receipt dates; *sales-side age proxy* (time since first/last sale) is computable |
| **Overstocking** | A purchasing decision outcome: ordered quantity exceeded what demand absorbed | Purchases > demand over a period (with on-hand rising) | Flow comparison | Purchases **yes** | No | **No** — no purchase receipts |
| **At-risk inventory** | A *leading* classification: on-hand stock with elevated probability of becoming dead (weak recent demand, downward trend, season ending) | Composite risk score crosses a policy band (score defined in Investigation 3) | Predictive, composite | No (score can be built from sales) | For exposure | **Partly** — sales-side risk score computable; final "risk *of held stock*" still needs on-hand |
| **Seasonal inventory** | Stock held intentionally for a seasonal demand peak | Demand has a seasonal pattern and stock was bought against that peak | Intentional, pattern-based | Yes (to distinguish intent) | No | **Partly** — seasonality of *sales* is observable within one year of data (limited); intent is not |
| **Low-demand inventory** | Permanently low but non-zero demand items (long tail) | Demand rate below assortment threshold yet consistently > 0 | Level, not stop | No | No | **Yes, historically** — computable |

**Key distinctions the product must never blur**

1. **Dead vs non-moving:** non-moving is a *measurement* (zero sales in
   window); dead is a *judgment* that the zero will not reverse. A seasonal
   item is non-moving for months every year and never dead.
2. **Excess vs dead:** excess is about *quantity* (too many units of a
   selling item); dead is about *demand extinction* (no units of any quantity
   will move). A product can be dead with 3 units and excessive with 30,000
   units of a fast seller.
3. **Obsolete vs non-moving:** obsolescence is caused by the product leaving
   the market; non-moving can occur while the product is fully current.
4. **Aging vs slow-moving:** aging measures elapsed time on a held unit;
   slow-moving measures the *rate* of consumption. Fast sellers can still
   hold old units if replenishment is erratic.
5. **At-risk is predictive; the others are descriptive.** At-risk is the only
   term in the list that refers to a future state — which is exactly why it
   needs the explicit limitations of Investigation 3.

## 1.2 Entry conditions as testable rules (proposal, thresholds to be set)

```
NON_MOVING(W):        units_sold(product, last W days) == 0
SLOW_MOVING(θv):      units_sold(product, W) / max(units_sold, previous W) < θv   (relative variant)
                       OR units_sold(product, W) < θa                              (absolute variant)
EXCESS(θc):           on_hand(product) > θc × expected_demand(product, H days)
AGING(θt):            oldest_unsold_unit_age(product) > θt
AT_RISK(θs):          composite_score(product) ≥ θs        (score per Investigation 3)
DEAD(product):        on_hand > 0 AND NON_MOVING(W) AND not_seasonal(product)
                      AND status(product) ∈ {active, discontinued} is known
                      AND (repeat confirmation: NON_MOVING also true in prior window)
```

`θ` values are **policy parameters, never universal constants**. The
threshold-selection methods are specified in Investigation 2.9.

## 1.3 Definitions across business models

| Dimension | Retail | Wholesale distribution | E-commerce | Manufacturing | TREXO's current dataset (e-commerce/retail, single seller) |
|---|---|---|---|---|---|
| Unit of analysis | SKU at store/SKU×location | SKU at branch | SKU (pooled network) | Component/WIP/FG | SKU = raw `StockCode` (case variants exist: `15056BL`/`15056bl`, `M`/`m`) |
| Typical dead-stock trigger | Season end / markdown cycle | Minimum order quantity over-buy | Trend collapse on a viral item | Engineering change / BOM replacement | Only *sales stoppage* observable |
| What "movement" means | POS sell-through | Shipments to branches | Order lines shipped | Consumption by production | Invoice lines (V2 sale definition) |
| Extra evidence usually available | Store stock, planograms, markdown history | Warehouse on-hand, MOQ, lead time | Stock across marketplaces, returns rate | BOM, ECN notices, production schedule | **None of these** |
| Seasonality strength | High (holiday/fashion) | Moderate | High (events/viral) | Moderate | One year of data → one seasonal cycle at best |
| Cost visibility | Unit cost, margin | Landed cost | COGS from supplier | Material + routing cost | **Absent** — only selling price |
| Consequence of error | Markdown loss | Dead capital + storage | Paid acquisition wasted on unsellable listing | Line stoppage or write-off | Not measurable yet without cost/stock data |

**Applicable now (dataset alone):** non-moving, slow-moving (sales-rate
variants), low-demand, sales-side ABC/XYZ/FSN rankings, seasonality of sales,
historical non-moving risk.
**Applicable only with added data:** dead stock (needs on-hand + intent),
excess (needs on-hand + forecast), obsolete (needs lifecycle/discontinuation
events), aging (needs receipt dates), overstocking (needs purchase receipts),
true financial exposure (needs acquisition cost).

# Investigation 2 — Dead-stock detection methodologies

Every methodology below is documented with the nine required aspects.
**"Implementable now"** refers to `data/raw/Online Retail.xlsx` + the audit
outputs, under the V2 sale definition and after excluding the 24 non-product
StockCode keys (POST, DOT, M, C2, D, S, B, PADS, BANK CHARGES, AMAZONFEE,
CRUK, GIFT_*, DCGS*, 15056BL, case variants), which carry 2,762 V2 rows and
£412,565.65 of non-merchandise value.

## Measured baseline used in the worked examples

*Measured (product codes only, V2 sale rows):* 527,342 rows · **3,898
products** · £10,254,118.89 line value · window 373.2 days
(2010-12-01 08:26 → 2011-12-09 12:50).

| Recency bucket (days since last sale) | Products | % of products | Line value |
|---|---|---|---|
| 0–30 | 2,925 | 75.04% | £9,770,645.48 |
| 31–90 | 296 | 7.59% | £288,820.99 |
| 91–180 | 217 | 5.57% | £91,524.00 |
| 181–270 | 272 | 6.98% | £76,833.16 |
| >270 | 188 | 4.82% | £26,295.26 |
| **Total** | **3,898** | 100% | **£10,254,118.89** |

- Products with no sale in the final **180 days: 460** (11.80% of products),
  55,623 units, £103,128.42 of *historical* line value (1.01% of product
  revenue). Products with no sale in the final **90 days: 677**.
- Invoice frequency per product: **1 invoice: 154** products (3.95%),
  2–4: 282 (7.23%), 5–19: 632 (16.21%), **20+: 2,830 (72.60%)** carrying
  £9,987,457.75. Single-line products: 153.
- ABC by line value (cumulative 70/20/10): **A = 543 products (13.93%)**,
  B = 791, C = 2,564.
- 3,672 of 3,898 products sold in more than one distinct month.

> These are *sales-side* facts about one historical year. They rank products
> by past behaviour; they do not establish any current stock position.

---

### M1 — Days since last sale (recency)

- **Definition.** Elapsed time between a product's last observed sale and the
  evaluation date.
- **Formula.** `recency(product) = t_eval − max(InvoiceDate where sale)`
- **Required inputs.** Transaction timestamps; product key; evaluation date.
- **Interpretation.** Rising recency with an active assortment = demand
  stall candidate. Direct input to non-moving and at-risk definitions.
- **Advantages.** Trivial, transparent, works on any sales history, no cost
  or stock data needed.
- **Limitations.** Sensitive to product being intentionally paused; censored
  at dataset end ("last sale" may be cut off by extraction); one global
  `t_eval` hides products that stopped selling at different times.
- **Potential false positives.** Seasonal items off-season; long-cycle B2B
  products; new SKUs launched just before `t_eval`; items temporarily
  out of stock (they *can't* sell, but aren't dead).
- **Suitability for TREXO.** Core indicator — it is the single clearest
  "demand stopped" signal and is explainable to non-technical users.
- **Implementable now?** **Yes** (measured above; 460 products >180 days).

### M2 — Sales frequency

- **Definition.** How often a product sells in a window (order lines,
  invoices, or days-with-sale).
- **Formula.** `freq(W) = count(lines in W)` or `count(distinct invoices in W)`
  or `days_with_sale / W`.
- **Required inputs.** Transactions within window W.
- **Interpretation.** Low frequency = weak demand base; frequency trending
  to zero = non-moving risk. FSN class building block.
- **Advantages.** Robust to price errors (counts don't need prices);
  works for zero-price goods.
- **Limitations.** Window-dependent; a product with 1 huge annual order
  looks "infrequent" but is healthy; bulk single-line items (this dataset:
  80,995 units on one line) distort line-counts.
- **Potential false positives.** High-value/low-frequency luxury items;
  wholesale MOQ patterns; new products with short exposure.
- **Suitability for TREXO.** Yes, as a supporting indicator with exposure
  normalisation (frequency per active month).
- **Implementable now?** **Yes** (measured: 154 single-invoice products).

### M3 — Average demand (sales velocity)

- **Definition.** Mean consumption rate per unit of time.
- **Formula.** `avg_demand(W) = units_sold(W) / W` (W in days or months);
  variants: per active month, per selling week, trailing vs whole-window.
- **Required inputs.** Units sold and window length; product key.
- **Interpretation.** The denominator of coverage and safety-stock maths;
  low velocity at given stock = excess/dead risk.
- **Advantages.** Universal input; easy to explain.
- **Limitations.** Mean hides trend and volatility; whole-window means
  include the growth phase of new products (survivorship).
- **Potential false positives.** Products in a growth phase averaged down
  over a long window; discontinued-with-final-bulk-order spikes.
- **Suitability for TREXO.** Yes — as the baseline rate, always paired with
  a trend and a variability measure.
- **Implementable now?** **Yes.** Worked example (measured): 85123A sold
  37,660 units over the 373.2-day window ≈ **3,070 units/month** average.

### M4 — Inventory turnover ratio

- **Definition.** How many times average inventory is sold/used in a period.
- **Formula (standard).**
  `turnover = COGS / Average Inventory value`, with
  `Average Inventory = (opening + closing inventory value) / 2`;
  `days_inventory = 365 / turnover`.
- **Required inputs.** **Cost of goods sold (acquisition cost) and inventory
  balances over time** — neither exists in this dataset.
- **Interpretation.** Falling turnover = capital immobilising; turnover → 0
  over successive periods = dead-stock progression.
- **Advantages.** The canonical finance-facing metric; directly monetises
  inefficiency.
- **Limitations.** A ratio of two unknowns here; revenue-based proxies
  (`Sales / Inventory`) systematically overstate turnover because selling
  price > cost.
- **Potential false positives.** Seasonal peaks (turnover collapses
  off-season); high-margin items where revenue/COGS skew the ratio.
- **Suitability for TREXO.** Essential for the *product* long-term — it is
  the bridge from "not selling" to "money trapped".
- **Implementable now?** **No.** Requires acquisition cost + inventory
  snapshots (see data-requirements doc). Only a labelled *sales-side proxy*
  could be shown today, and it must not be called turnover.

### M5 — Inventory aging

- **Definition.** Age of units held, typically FIFO layers since goods
  receipt.
- **Formula (standard).** `age(layer) = t_eval − receipt_date(layer)`;
  aging buckets = Σ value of layers older than 30/60/90/180 days.
- **Required inputs.** Goods-receipt records with dates and quantities;
  stock ledger for the current position.
- **Interpretation.** Oldest-layer age drives markdown depth and write-off
  risk; aging + no movement = strongest dead-stock evidence.
- **Advantages.** Directly matches accounting write-down practice and
  warehouse reality.
- **Limitations.** Impossible from sales data alone (sales date ≠ receipt
  date); needs lot/layer tracking for FIFO accuracy.
- **Potential false positives.** Old slow-replenished spare parts that are
  contractually required; seasonal goods aged since last season but wanted
  next season.
- **Suitability for TREXO.** Yes, once inventory snapshots/receipts exist;
  it becomes a first-class page in the platform.
- **Implementable now?** **No** (no receipt dates). A sales-age proxy
  (time since last sale) is *not* the same thing and must be labelled as such.

### M6 — Stock coverage (weeks/days of supply)

- **Definition.** How long current stock lasts at current demand.
- **Formula (standard).** `coverage_days = on_hand / avg_daily_demand`;
  comparison `cover_vs_lead_time = coverage_days − supplier_lead_time`.
- **Required inputs.** On-hand quantity; demand rate; (for judgement)
  supplier lead time.
- **Interpretation.** Coverage far beyond lead time + demand horizon =
  excess; coverage ≈ 0 with stock > 0 = stockout (opposite failure).
- **Advantages.** Actionable: directly sets reorder rules and overstock
  flags; combines stock and demand in one number.
- **Limitations.** Undefined when demand = 0 (needs the Poisson treatment
  in M7/thresholds); sensitive to demand-rate choice.
- **Potential false positives.** Erratic-demand items (coverage swings);
  intentional pre-season builds.
- **Suitability for TREXO.** Yes — one of the two core "excess" metrics
  (with turnover) once on-hand exists.
- **Implementable now?** **No** (needs `on_hand`). Demand-rate component is
  computable today.

### M7 — Demand variability (and the zero-demand probability)

- **Definition.** Dispersion of demand around its mean; includes the
  probability that demand in a future window is exactly zero.
- **Formula.** `CV = σ_demand / μ_demand` (σ over periods). For sparse
  demand, model arrivals: Poisson → `P(no sale in W) = e^(−μ·W)`; when
  observed variance ≫ mean (over-dispersion, common in retail) use the
  negative-binomial instead of Poisson.
- **Required inputs.** Period-level demand series (monthly series exist in
  `product_monthly_sales_v2.csv`).
- **Interpretation.** High CV ⇒ noisy demand ⇒ recency alone is weak
  evidence; the calibrated `P(no sale in W)` turns "no recent sale" into a
  *statistically surprising* event, which is exactly the threshold logic
  dead-stock detection needs (see M2.9).
- **Advantages.** Separates "no sale yet, expected for this demand rate"
  from "no sale, statistically abnormal"; directly supports confidence
  statements in recommendations.
  Worked example (illustrative numbers): a product that normally sells about
  once a month (μ = 1/30.4 days) shows no sale for 90 days ⇒
  `P = e^(−90/30.4) ≈ 0.052` — borderline surprising at α = 0.05; the same
  90-day gap for a product selling once a year is completely expected
  (`P ≈ 0.78`). Same observed recency, opposite conclusions.
- **Limitations.** Distribution choice matters (Poisson under-dispersed for
  retail); short windows give unstable CV; one year of data limits seasonal
  variance estimation.
- **Potential false positives.** Over-dispersed products modelled as Poisson
  get flagged too eagerly.
- **Suitability for TREXO.** High — it is what keeps TREXO's flags
  explainable ("90 days without a sale, but this product's normal rate is
  once per year, so the gap is statistically ordinary").
- **Implementable now?** **Partly** — CV and empirical P(0-sale) computable
  from monthly sales; distribution fitting is a future analytics step (not
  ML, but should still be approved).

### M8 — ABC analysis

- **Definition.** Rank products by a value contribution (usually revenue or
  margin) and split into classes.
- **Formula (standard).** Sort by value desc; cumulative share;
  A = items to 70–80% of value, B = next 15–20%, C = final 5–10%
  (this research uses the 70/20/10 variant, clearly labelled *illustrative*).
- **Required inputs.** Value per product (revenue = quantity × price here;
  margin preferred when cost exists).
- **Interpretation.** Prioritisation: dead-stock exposure on A items costs
  the most; C-item dead stock is a handling-cost problem, not a capital one.
- **Advantages.** Cheap, robust, universally understood by management.
- **Limitations.** Pure ranking: every product gets a class even if all are
  healthy; ignores recency, movement and stock; revenue-based ABC uses
  selling price, not cost.
- **Potential false positives.** A high-revenue product with a single
  bulk-line anomaly (this dataset: product 23843 = one line, 80,995 units,
  £168,469.60 — an A-class "product" driven by one audited extreme row).
- **Suitability for TREXO.** Yes, as the *prioritisation* layer that ranks
  risk scores by financial exposure — never as a dead-stock detector alone.
- **Implementable now?** **Yes** (measured: A = 543, B = 791, C = 2,564).

### M9 — XYZ analysis

- **Definition.** Rank products by demand predictability (variability), the
  volatility complement of ABC.
- **Formula (standard).** `CV = σ_monthly / μ_monthly` over ≥ 12 periods;
  class bands on CV (X = stable, Z = erratic). **Band values are policy
  choices** — they must be selected by back-testing or percentiles for the
  dataset at hand, not copied (see M2.9).
- **Required inputs.** ≥ several periods of demand per product (34,069
  product-month records exist).
- **Interpretation.** AX = protect with stock; CZ = never auto-reorder.
  For dead stock: Z/C combined with rising recency is the "stop buying"
  archetype.
- **Advantages.** Pairs naturally with ABC; drives different inventory
  policies per class.
- **Limitations.** Needs full-period demand history (new/short-lived SKUs
  get meaningless CV); seasonal products look erratic without
  de-seasonalisation.
- **Potential false positives.** Erratic but healthy products (event-driven
  demand) marked as risk.
- **Suitability for TREXO.** Yes, as a risk *modifier* (variability raises
  uncertainty), not as a detector.
- **Implementable now?** **Yes** for monthly-demand CV (data exists);
  seasonality-corrected variants need ≥ 2 seasonal cycles (we have 1).

### M10 — FSN analysis (fast / slow / non-moving)

- **Definition.** Classic inventory classification by movement: fast = high
  consumption, slow = moderate, non-moving = none/little.
- **Formula (standard, FSN procedure per Finale Inventory's guide).**
  `average stay = cumulative days of inventory / (opening balance + goods received)`
  (simplified period form: `average stay = Σ balance over periods / units issued`);
  `consumption rate = units issued / period days`;
  `FSN index = (cumulative consumption × 100) / (cumulative average stay × total issues)`
  — products ranked by index → fast (high index), slow, non-moving (index ≈ 0).
  Practical simplified variants used in most tools: class by issues per
  period, or by recency of last movement.
- **Required inputs.** Issues/stock movements (or sales as proxy);
  ideally balances for the true stay formula.
- **Interpretation.** Non-moving class = candidate dead-stock review list;
  slow = reorder-review list.
- **Advantages.** Intuitive to operations staff; directly yields a review
  list; well-established in distribution practice.
- **Limitations.** The published index needs inventory balances (which we
  lack), so today only proxy variants are possible; class boundaries are
  threshold-driven and not universal.
- **Potential false positives.** Seasonal non-movers (every year);
  new products in their first weeks; long-cycle items.
- **Suitability for TREXO.** High — FSN is essentially the *vocabulary*
  users already understand; TREXO's risk score can output FSN-style classes
  with stated thresholds.
- **Implementable now?** **Partly** — proxy FSN yes: issues-based classes
  (measured: ≥20 invoices = 2,830 "fast", 5–19 = 632 "slow", <5 = 436
  "non-moving" under illustrative thresholds), recency-based non-moving
  (measured: 460 products >180 days). The two variants **disagree by 24
  products** — a concrete demonstration that thresholds must be chosen and
  documented, never assumed.

### M11 — Demand decay

- **Definition.** Model the declining tail of demand after a peak or after
  a product stops being promoted.
- **Formula.** Exponential decay `d(t) = d₀·e^(−k·t)` fitted to recent
  periods; half-life `t½ = ln2 / k`; or rolling-window ratios
  `d(t) = units(W_recent) / units(W_prior)` with `d(t) < 1` = decay.
- **Required inputs.** Time series per product, ≥ several periods.
- **Interpretation.** `k` quantifies how fast a product is dying; a fitted
  `k` extrapolates time-until-zero demand — the bridge from "slow" to
  "future dead stock".
- **Advantages.** Early warning: decay starts long before sales hit zero;
  half-life is explainable ("demand halves every 47 days").
- **Limitations.** Fitting requires care with sparse data; confounds
  promotion ends, stockouts and seasonality; extrapolation is a forecast
  (see governance: forecasting is out of scope for V1 — this method may be
  *specified* but not *operated* yet).
- **Potential false positives.** Post-promotion normalisation mistaken for
  decay; supply-constrained products (out of stock ⇒ "decaying" demand).
- **Suitability for TREXO.** Yes for the future risk-scoring component,
  clearly separated from the detection core (Investigation 3, part C).
- **Implementable now?** **Design only** — fitting curves is modelling; it
  must be approved separately from rule-based detection.

### M12 — Excess inventory analysis

- **Definition.** Quantify stock beyond what demand justifies.
- **Formula (standard).**
  `excess_qty = max(0, on_hand − target_stock)`,
  `target_stock = demand_rate × coverage_target (+ safety_stock)`;
  `excess_value = excess_qty × unit_cost`.
- **Required inputs.** On-hand, demand rate, coverage policy, unit cost.
- **Interpretation.** Converts "too much stock" into a currency figure the
  business can act on; distinguishes excess (too many of a *selling* item)
  from dead (of an *unselling* item).
- **Advantages.** The metric that ties detection to money; drives
  reorder-Stop and transfer recommendations.
- **Limitations.** Requires on-hand + cost (both absent); depends on the
  chosen coverage target (policy).
- **Potential false positives.** Intentional safety/pre-season stock counted
  as excess; slow but required service parts.
- **Suitability for TREXO.** Central to the product's financial pages.
- **Implementable now?** **No** (needs on-hand + cost).

### M13 — Seasonal demand adjustment

- **Definition.** Evaluate movement against the product's own seasonal
  expectation instead of a flat window.
- **Formula.** Seasonal index `I(m) = demand(m) / mean(demand)` for month m`
  over prior year(s); seasonally-expected sales in window W =
  `Σ I(m) · base_rate`; flag only when actual ≪ expected.
- **Required inputs.** ≥ 1–2 full seasonal cycles of demand history
  (one year exists here — a single cycle, so indices can be *observed*
  but not *validated*).
- **Interpretation.** Prevents the classic false positive of labelling
  off-season items dead; also reveals *pre-season* risk (bought stock with
  the season already over).
- **Advantages.** Materially reduces false positives in seasonal
  assortments; explainable ("flagged because demand is 80% below this
  month's normal level, not merely because it is a slow month").
- **Limitations.** Needs ≥ 2 cycles to separate trend from season;
  promotion effects contaminate indices; one-cycle data cannot prove
  repeatability.
- **Potential false positives.** One-off events (a hot product one year)
  baked into the index; calendar shifts (Easter/ramadan dates).
- **Suitability for TREXO.** Necessary as a *filter* on risk scores, but
  with an explicit confidence penalty while only one cycle exists.
- **Implementable now?** **Partly** — intra-year seasonality is observable
  (373 days covers all months once); validation of the indices is not.

### M14 — Product lifecycle analysis

- **Definition.** Place each product on introduction → growth → maturity →
  decline → discontinuation, and interpret movement accordingly.
- **Formula.** No single formula; practical proxies:
  `age_since_first_sale`, phase from trend fit (approved modelling), or
  explicit lifecycle events (launch/discontinue dates) when available.
- **Required inputs.** Product master lifecycle events (ideal); fallback =
  first/last sale dates from transaction history.
- **Interpretation.** Death-of-demand is *expected* in decline/discontinued
  phase (then the right action is markdown/liquidation, not reorder-stop
  education); unexpected stall in maturity = real alert.
- **Advantages.** Changes the recommended action, not just the flag —
  prevents wrong interventions on intentionally ending products.
- **Limitations.** First/last-sale proxies confuse "new" with "declining";
  without discontinuation events the phase label is inference, not fact.
- **Potential false positives.** New products flagged as declining; pre-
  launch stock flagged as dead.
- **Suitability for TREXO.** Yes as an action-context field with
  `lifecycle_phase_source ∈ {event, inferred, unknown}` labelling.
- **Implementable now?** **Partly** — age since first sale computable;
  phase inference requires approved modelling or external product-master data.

## 2.9 Threshold selection (no universal thresholds)

| Method | How | When to prefer | Dataset readiness |
|---|---|---|---|
| **1. Business policy** | Contractual/operational rules: shelf life, season end, supplier return windows, MOQ cycles | Lifecycle or regulatory deadlines exist | Needs business input (not yet collected) |
| **2. Percentile / rank** | Flag bottom-k% or above/below a dataset percentile (e.g. recency p90, consumption-share bands 70/20/10) | Distribution unknown, relative ranking is enough | **Ready** (used in the audit: p99 of zero-price quantities) |
| **3. Back-testing / holdout** | Choose thresholds that correctly predicted items later confirmed unsold when a stock snapshot becomes available; report precision/recall of each candidate threshold | Stock snapshots or future outcomes will exist | **Blocked** until inventory data exists — this is the honest reason thresholds cannot be finalised today |
| **4. Statistical surprise** | Under Poisson demand rate μ, `P(no sale in W) = e^(−μW)`; flag when `P < α` (e.g. 0.05), with α documented | Sparse demand, need calibrated confidence | **Partly ready** (μ computable; α is a policy choice) |
| **5. Cost-benefit economics** | Set threshold where expected carrying cost of flagging/acting equals expected recovery — `hold_cost × days > expected_recovery` | Monetised decisions (markdown depth) | Blocked (needs cost data) |
| **6. Expert elicitation + review loop** | Practitioners state expectations; every override logged with reason; thresholds versioned | Domain knowledge is strong but data weak | **Ready** — recommend starting here for V1 thresholds |

**Rules for TREXO (proposal):** every threshold ships with (a) the method
that produced it, (b) its dataset/period of calibration, (c) an expiry/review
date, (d) a sensitivity note ("at ±20% the flagged list changes by N items").
Literature values such as 20+/5–19/<5 invoices (FSN), 70/20/10 (ABC
consumption share) or 30/180-day recency bands are **starting points to
back-test, not answers**.

# Investigation 3 — Dead-stock risk scoring (proposed framework)

## 3.1 Design constraints (from governance)

1. Every score must **expose its supporting indicators and limitations** —
   no opaque number may be shown without the inputs that produced it.
2. A historical sales dataset **cannot establish current stock**; therefore
   the framework separates what is computable today from what is blocked.
3. Scores are **decision support, not verdicts**: the system recommends, a
   human approves. No score may silently rewrite data-quality state.
4. Modularity: each dimension is an independent, individually testable
   component so that dead-stock detection works **before** forecasting/ML
   exists.

## 3.2 The four score families (A–D) — kept strictly separate

| Family | Question it answers | Data it may use | Computable now? | Output wording required |
|---|---|---|---|---|
| **A. Historical non-moving risk** | "Did demand stall in the past year?" | Sales history only | **Yes** | "Historically non-moving (no sale in N days)" |
| **B. Current dead-stock risk** | "Is stock dead *right now*?" | Sales **+ inventory snapshot + lifecycle status** | **No** (blocked) | "Cannot be computed: no stock-on-hand data" — the UI must say this, not invent a value |
| **C. Future dead-stock risk** | "Is this product likely to die?" | Sales trend + seasonality + (approved) forecasting | **Design only** (forecasting not approved) | "Predictive estimate — model not yet approved" |
| **D. Financial exposure** | "How much money is at stake?" | Quantities × **cost** (+ holding/markdown rates) | **No** (blocked) | "Exposure unavailable: no acquisition cost" |

Only **A** may be computed end-to-end today. B, C and D must appear in the
architecture as defined components with explicit `status: blocked` inputs —
never as partially-computed numbers that look real.

## 3.3 Score A — historical non-moving risk (ready to build)

Sub-indicators, each normalised to 0–1 (0 = healthy, 1 = worst), each
carrying its own evidence string:

| # | Indicator | Transform (proposal) | Source | Measured availability |
|---|---|---|---|---|
| A1 | Recency | `min(1, recency_days / R_cap)` where `R_cap` is a calibrated cap | InvoiceDate per product | Ready (0–30d: 2,925 products … >270d: 188) |
| A2 | Sales velocity | inverse of `units/W` vs catalog percentile | Quantity | Ready |
| A3 | Sales frequency | `1 − percentile_rank(invoices)` | InvoiceNo count | Ready (154 products with 1 invoice) |
| A4 | Trend (recent vs prior window) | `max(0, 1 − recent_rate/prior_rate)` | Monthly sales | Ready (seasonality caveat) |
| A5 | Demand variability | CV modifier: raises uncertainty, never lowers risk alone | Monthly sales | Ready (34,069 product-months) |
| A6 | Statistical surprise | `1 − P(no sale in W | demand rate)` (Poisson/neg-binomial) | Monthly sales | Ready (method choice to approve) |
| A7 | Seasonal expectation gap | `1 − actual/seasonal_expected` (only when seasonal) | Monthly sales | Partly (1 cycle only) |
| A8 | Concentration | share of total revenue/units (ABC rank) | Line value | Ready (A=543, B=791, C=2,564) |

**Composition (proposal):**
`score_A = 100 × Σ wᵢ·xᵢ / Σ wᵢ` over available indicators, with:

- **weights `wᵢ` versioned and policy-set** (start equal-weight; adjust only
  via approved back-test);
- **missing-data handling = declare, don't impute**: `available_mask` shown
  with the score ("6 of 8 indicators available"); a score never uses a
  fabricated value to fill a gap;
- **confidence label** derived from coverage + data-quality state of that
  product's rows (duplicates, zero-price ambiguity, non-product code
  contamination from Audit V1);
- **explanations**: top-3 contributing indicators with their raw values,
  e.g. *"recency 368d (cap 365 → 1.00), invoices 1 (rank 4th percentile),
  trend −100% (last 90d = 0 units)"*.

**Anti-patterns explicitly avoided:** single-indicator flags presented as
conclusions; hidden normalisation caps; scores computed over rows the audit
flagged `NEEDS_MANUAL_REVIEW`/`UNKNOWN` without showing that fact.

## 3.4 Score B/C/D composition (design, blocked inputs)

- **B (current dead):** `B = f(on_hand > 0, A-score, lifecycle_status,
  days_since_last_receipt)`. Requires inventory snapshot + lifecycle event.
  Until then TREXO reports "not computable" with the list of missing inputs.
- **C (future risk):** `C = g(A, trend slope, seasonal outlook, forecast
  (when approved))`, output as a probability band with model card. Rule-based
  variant available first: *"A-score high ∧ seasonal index declining ∧
  coverage above target"* — no ML required.
- **D (exposure):** `D = Σ (on_hand_qty × unit_cost)`, plus
  `expected_loss = D × (1 − expected_recovery_rate)`; holding-cost add-on
  `= D × annual_carrying_rate × days/365`.

## 3.5 Worked score example (illustrative inputs, real method)

Product X: recency 240 days (cap 365 → A1 = 0.66), invoices 2 (A3 ≈ 0.96
percentile), trend last 90d vs prior 90d = 0 units (A4 = 1.00), CV 1.4
(A5 contributes its policy weight), P(no sale in 180d) = 0.001 (A6 = 0.999),
revenue rank bottom 40% (A8 = 0.40). Equal weights over 6 available
indicators ⇒ `score_A ≈ 83/100`, displayed with: *"Available 6/8 — no
stock-on-hand, no lifecycle data; historical signal only."* The UI then
states what this does **not** mean: it does not prove the product is dead
today, and no financial value is attached without cost data.

# Investigation 4 — Financial impact methods

## 4.1 Five values that must never be conflated

| Concept | Definition | Source field | Available now? |
|---|---|---|---|
| **Historical revenue** | What sold, at selling price | `Quantity × UnitPrice` | **Yes** (measured: £10,254,118.89 product-line value) |
| **Inventory acquisition cost** | What the held stock cost to buy | Supplier invoice / standard cost | **No** |
| **Current inventory valuation** | Value of stock on hand today (cost, or NRV if lower) | Stock ledger × cost | **No** |
| **Potential liquidation revenue** | What could actually be recovered now (discounted channel) | Price history + channel recovery rates | **No** (needs cost/channel inputs) |
| **Estimated financial loss** | Valuation − recoverable amount | Derived | **No** |

**Hard rule:** historical selling price must **never** be used as inventory
acquisition cost. Using £10.25M of line value as "capital tied up" would be
a category error: that is *turnover*, not *stock value*.

## 4.2 Formulas with required fields (each field listed if missing)

```
Inventory capital tied up   = Σ on_hand_qty × unit_acquisition_cost
                              [on_hand_qty: MISSING | unit_acquisition_cost: MISSING]
Carrying cost (period)      = avg_inventory_value × annual_carrying_rate × days/365
                              [rate = policy; components above MISSING]
  where annual_carrying_rate typically = cost_of_capital
                                   + storage_rate + insurance + shrinkage
                                   + obsolescence_rate   [all policy/finance inputs]
Storage cost                = Σ (units × footprint × days) × storage_rate
                              [footprint, storage_rate: MISSING; days from snapshots: MISSING]
Markdown loss               = Σ (unit_cost − markdown_price) × qty_marked_down
                              [unit_cost MISSING; markdown prices MISSING]
Obsolescence risk provision = holding_value × P(obsolescence | age, lifecycle)
                              [both inputs MISSING; P from approved model only]
Excess inventory value      = Σ max(0, on_hand − target_stock) × unit_cost
                              [on_hand, unit_cost MISSING; target derivable from demand + policy]
Potential recovery value    = Σ on_hand_qty × unit_cost × recovery_rate(channel, age)
                              [recovery_rate needs market data; rest MISSING]
Estimated financial loss    = holding_value − potential_recovery_value − salvage
                              [all MISSING]
```

**Available today (clearly labelled as sales-side, not stock):**
- historical revenue and unit volume per product (measured);
- *value-at-risk proxies*: historical line value of products flagged
  historically non-moving = **£103,128.42 across 460 products** (measured) —
  this is **past revenue**, explicitly not capital at risk;
- audit anomalies (e.g. CRITICAL ANOM-0001: a £11,062.06 bad-debt row inside
  V2 product sales) — data-quality-driven financial distortions are
  measurable now.

**Illustrative carrying-cost example (hypothetical numbers, method only):**
if £100,000 of stock were held with a 22%/yr combined carrying rate, cost =
£100,000 × 0.22 × 90/365 ≈ **£5,425 for a 90-day hold** — shown to
demonstrate the formula; TREXO must not present any such figure until cost
and holding-rate inputs exist.

## 4.3 Data-gap summary for financial impact

Missing fields: `on_hand_qty`, `unit_acquisition_cost`, `average_cost`,
`inventory_value_period_end`, `holding_rate_components`, `footprint/storage
rate`, `markdown_history`, `recovery/liquidation rates`, `open_purchase_orders`.
Full classification in `DEAD_STOCK_DATA_REQUIREMENTS_V1.md`.

# Investigation 5 — Dead-stock prevention interventions

For each intervention: **trigger → required data → expected benefit →
business risk → when NOT to apply**. Every future recommendation must be
rendered as *"We recommend X because indicators Y show Z (confidence C,
limitation L)"*.

| # | Intervention | Trigger conditions (proposal) | Required data | Expected benefit | Business risk | Do NOT apply when |
|---|---|---|---|---|---|---|
| 1 | **Reorder restriction (hold PO)** | Score A high ∧ on-hand > coverage target ∧ no reorder justified | Sales + on-hand + open POs | Stops capital flowing into dead stock | Stockout if demand revives; supplier-relationship strain (MOQ commitments) | Item is seasonal with season approaching; service-level contract requires availability |
| 2 | **Demand-based replenishment** | Reorder point = demand rate × lead time (+ safety stock) | Demand series, lead times, on-hand | Matches purchasing to real demand | Under-buying when demand spikes; needs stable demand estimates | Erratic (Z-class) demand without safety-stock buffer; no lead-time data |
| 3 | **Safety-stock optimisation** | Recompute SS from demand CV + lead-time variability at service target | Demand series, lead-time history, service policy | Fewer stockouts *and* less excess than fixed SS | Wrong service target over-buffers | Service target undefined; lead times unknown |
| 4 | **Min/max stock policy** | Position outside [min, max] for its class (ABC/XYZ) | On-hand, class from demand | Simple, operable rules for staff | Static levels drift with season | Levels never reviewed; seasonal items with fixed levels |
| 5 | **Discount recommendation** | Non-moving ∧ season over ∧ recovery decaying; depth from age band | Sales history + age + price elasticity (or manual bands) | Converts stock to cash before obsolescence | Margin erosion; brand/devaluation; customers learn to wait | Item about to restock in season; MAP/price-parity contracts; brand-positioning constraints |
| 6 | **Product bundling** | Slow item pairs with a fast mover (basket affinity) | Co-purchase data (invoice lines) | Lifts dead stock via popular product's traffic | Dilutes fast-mover margin; operational kitting cost | Bundles with no affinity evidence; components with different shelf lives |
| 7 | **Promotion / campaign** | At-risk before season end; promo expected lift > cost | Sales history, promo calendar, cost of promo | Demand pull while item is still sellable | Promotion pulls forward future demand (cannibalisation); cost may exceed recovery | Item discontinued (promotion only delays write-off) |
| 8 | **Inter-warehouse transfer** | Overstock at A + shortage at B | Location-level on-hand and demand | Zero markdown; balances network | Transfer cost; wrong if network demand is also low | Single-warehouse operation (our current dataset has **no warehouse data at all**) |
| 9 | **Supplier return / buy-back** | Within return window, supplier accepts | Supplier terms, receipt dates, PO | Full or high recovery | Return windows expired; restocking fees; relationship friction | Window passed (typical for fashion/gifts); no contract terms loaded |
| 10 | **Purchase-quantity optimisation** | Next-buy qty from demand + excess position + MOQ | Demand, on-hand, MOQ/lead time | Prevents recurrence (the real cure) | MOQ forces over-buy anyway; forecast error | Demand history too short (new SKU) — then conservative first buys |
| 11 | **Discontinuation** | Persistent non-moving ∧ revival unlikely ∧ carrying cost > expected recovery | Multi-period demand + lifecycle + cost | Permanently stops waste | Killing a product that would recover; stranded customer demand | Item is a slow-but-required spare/service part; seasonal item mid-cycle |

**Shared precondition:** interventions 1, 2, 4, 8, 10 need **inventory and
purchase data we do not have**; 5, 6, 7, 11 can be *piloted* on sales
evidence alone but their benefit metrics still need cost. TREXO V1 may
therefore ship **detection and evidence**, while recommendations carry
`requires: [inventory, cost, …]` badges until those inputs exist.

**Explainability contract (proposal):** `Recommendation { action, product,
trigger_indicators[], evidence_rows[sourceRow, invoice, value], confidence,
limitations[], expected_benefit_range, do_not_apply_when[], approved_by:
null }` — `approved_by: null` until a human signs off; no auto-execution.

# Investigation 6 — Dataset suitability (`data/raw/Online Retail.xlsx`)

## 6.1 What the dataset is (measured)

Transactional sales history of one UK-based non-store online retailer
(UCI: Chen 2015, DOI 10.24432/C5BW33, CC BY 4.0): **541,909 rows · 25,900
invoices · 4,070 StockCodes · 2010-12-01 08:26 → 2011-12-09 12:50
(373.2 days, a single annual cycle)**.

Data-quality state (measured in Audit V1): missing Description 1,454 rows ·
missing CustomerID 135,080 (24.93%) · exact duplicate rows 5,268 ·
2,515 zero-price rows · 1,336 negative non-cancellation rows (all priced
0.00) · 2 negative-price rows (bad-debt pair) · 9,288 cancellation rows ·
3,385 rows on 35 non-product StockCodes (8 of them inside product movement
V2) · 2,166 unusual invoices · StockCode mixed int/str typing (487,036 int +
54,873 str on raw read) · case-variant codes (`15056BL`/`15056bl`, `M`/`m`).

## 6.2 Field-by-field answer to the required list

| Information | Status | Notes |
|---|---|---|
| Historical sales | **Available** | Line-level invoices with dates |
| Product quantities | **Available** | `Quantity` (incl. negative/zero rows — meaning ambiguous per Audit V1) |
| Product descriptions | **Available (imperfect)** | Free text; 1,454 missing; case variants preserved |
| Last observed sale | **Derivable** | Measured: 460 products >180 days |
| Sales frequency | **Derivable** | Measured: invoice counts per product |
| Sales trends | **Derivable** | Monthly series exist (34,069 product-months); one cycle only |
| Current stock on hand | **Missing** | Absolute blocker for "dead stock" claims |
| Purchase receipts | **Missing** | Blocks overstock/aging/receipt-age analysis |
| Supplier information | **Missing** | Blocks return/buy-back recommendations |
| Acquisition costs | **Missing** | Blocks turnover, exposure, markdown-loss, recovery |
| Warehouse/location | **Missing** | Blocks transfers, per-location aging |
| Inventory aging | **Missing** | No receipt dates ⇒ no real unit age |
| Lead times | **Missing** | Blocks reorder-point/safety-stock maths |
| Product lifecycle events | **Missing** | Launch/discontinue dates absent (first/last sale are weak proxies) |
| Customer identity | **Partial** | 24.93% missing — irrelevant for stock, relevant for demand segmentation |
| Country | **Available (weak)** | Invoice country only, not delivery destination |

## 6.3 What dead-stock research is possible now vs blocked

**Possible now (sales-side only):** non-moving / slow-moving / low-demand
measurement; recency, frequency, velocity, trend, variability; ABC/XYZ/FSN
variants; seasonality observation (one cycle); historical non-moving risk
score (Score A); data-quality-informed confidence; *historical* value
proxies (£103,128.42 of past line value on 460 >180-day products);
prevention triggers expressed as rules **pending inventory inputs**.

**Blocked (needs additional data):** any claim of *current* dead stock;
excess/overstock quantification; aging units; turnover and carrying cost;
financial exposure and loss; supplier-return and transfer actions;
reorder-point and safety-stock recommendations; validated seasonality;
ML/forecast-based future risk.

**Condemned shortcuts (explicitly prohibited):** inferring stock from
sales; treating selling price as cost; calling recency "dead stock"; using
ML to paper over the audit's open anomalies (93, all `OPEN`).

## 6.4 Additional datasets for methodology validation (research only — none downloaded)

| Dataset | Origin & licence (as published) | What it would validate | Suitability notes |
|---|---|---|---|
| **UCI Online Retail** (the current file) | UCI ML Repository, Chen D. 2015, DOI 10.24432/C5BW33, CC BY 4.0 | Baseline — all measured figures in this document | Licence permits redistribution/attribution; cite when publishing results |
| **M5 forecasting competition (Walmart)** — `accuracy` + `sales_evaluation` | Kaggle, "M5 Forecasting - Accuracy" (sponsored by Walmart; competition dataset) | Recency/frequency/FSN thresholds, seasonal adjustment, intermittent-demand treatment across ~3,049 hierarchical series with calendar and *supply-side* signals | Strong for threshold back-testing because it has known sell-through outcomes; check Kaggle competition rules before redistribution (competition data is typically for analysis under Kaggle's terms, not blanket open licence) |
| **Corporate stockouts / inventory Kaggle sets** (e.g. store sales, inventory demand) | Kaggle per-dataset licences vary (CC0 / CC BY-SA / research-only) | Turnover & excess-inventory formulas on real on-hand data | **Licence must be read per dataset before any download**; several forbid commercial use, which matters for a commercial product |
| **Retailer ERP exports** (real businesses) | Private, requires customer agreement | True dead-stock ground truth (on-hand + cost + disposition outcome) | The *only* source that can validate Score B; must define retention/PII terms first |

**Download rule (agreed):** no dataset enters the repository without a
`docs/DATA_SOURCE_REGISTER.md` entry recording origin, licence, retrieval
date, row count, intended use, and a fit assessment. *This research phase
downloads nothing.*

## 6.5 Research status and open questions

**Established by this document (verified against the dataset):** canonical
definitions; 14 detection methodologies with formulas, inputs, limits and
false-positive modes; a threshold-selection framework; a modular,
explainable risk-scoring design with the A/B/C/D separation; financial-impact
formulas with explicit missing fields; 11 prevention interventions with
do-not-apply conditions; and a candid dataset capability assessment.

**Open questions requiring review (not answered here):**

1. Which threshold method (of Investigation 2.9) does TREXO adopt for V1
   non-moving/slow-moving boundaries — and who owns the policy values?
2. Are equal starting weights for Score A acceptable pending back-test data?
3. Which validation dataset (6.4) may be downloaded, given its licence?
4. What is the roadmap to inventory/cost ingestion (the single blocker for
   Scores B and D)?
5. Should the 93 open audit anomalies be resolved *before* any scoring
   ships (recommended: yes, for the 8 non-product codes inside V2)?

**Nothing in this research has been implemented.** No scoring job, API,
model, or dataset change exists as a result of this document.

---

**Status: Dead Stock Intelligence Research V1 complete as a research
document; implementation not started, awaiting review.**
