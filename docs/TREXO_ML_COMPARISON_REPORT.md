# TREXO ML Comparison Report

**Scope:** Compare the existing TREXO-INDIA ML repository (`ml-1.1.0`) with the Claude RETAIL implementation (`RETAIL`, `ml-1.0.0` base) and report exactly what was retained, merged, or rejected.
**Date:** 2026-11-20

---

## 1. Provenance

| Aspect | Existing repository | Claude RETAIL |
|---|---|---|
| Source | `TREXO-INDIA` git repo, remote `origin` | `TREXO-INDIA-RETAIL.zip` (staged copy, no git history) |
| Pipeline version | `ml-1.1.0` | `ml-1.0.0` core + retail additions |
| Governance | D01 decision implemented, lineage audits | inherited D01 code, less governance depth |
| Tests at audit | 74 passed, 4 skipped | 98 passed, 4 skipped, 4 subtests |
| Model kinds | dead_stock, forecasting, movement, anomaly | same core + pricing, bundles, customers, forecasting_price |
| Docs | 26 documents | 14 retail documents |

The two codebases share an ancestor. The Claude fork was built from the earlier `1.0.0` core and therefore **lacks** later fixes in the `1.1.0` core. A full replacement was rejected.

---

## 2. Capability comparison

| Capability | Existing 1.1.0 | RETAIL 1.0.0 | Decision |
|---|---|---|---|
| D01 bad-debt exclusion (`A563185`–`A563187`) | Yes, with audit and warnings | Present but older | **Keep 1.1.0** |
| Data quality / lineage audits | Yes | Partial | Keep 1.1.0 |
| Dead-stock classifier + calibration | Yes, calibrated recency rule deployed, challenger rejected | Older version | Keep 1.1.0 |
| Demand forecasting (classical + LightGBM) | Yes | Yes | Keep 1.1.0 |
| Movement / ABC-XYZ | Yes | Yes | Keep 1.1.0 |
| Anomaly detection | Yes | Yes | Keep 1.1.0 |
| Reorder policy | Yes | Yes | Keep 1.1.0 |
| Recommendation queue / five-part explanation | Yes | Partial | Keep 1.1.0 |
| Versioned registry + checksums | Yes | Yes | Keep 1.1.0 |
| Inference service + request validation | Yes | Older | Keep 1.1.0 |
| Inventory ledger / ageing / selling priority | **No** | Yes | **Merge additive** |
| Pricing scenario engine + elasticity | No | Yes | Merge additive |
| Bundle / basket recommendations | No | Yes | Merge additive |
| Customer RFM / promotion intelligence | No | Yes | Merge additive |
| Recovery engine / profit optimiser (MILP) | No | Yes | Merge additive |
| Feedback store / controlled retraining workflow | No | Yes | Merge additive |
| Simulation replay | Basic backtest | Clearance replay | Merge additive |
| Shop-operations API | No | No | **Build new** |
| React UI | No | No | **Integrate new** |

No existing module, test, report, model or governance record was overwritten by the merge.

---

## 3. Retail package evaluation (as delivered, re-verified)

These are the numbers recorded by the retail experiments. They are **associational / synthetic where noted**, and none demonstrate profit benefit on a real shop.

| Component | Evaluation | Result | Use |
|---|---|---|---|
| Pooled price elasticity | cluster bootstrap, split-half, placebo | **−0.7365** (95% CI −0.8044 to −0.7043); halves −0.598 / −0.671; placebo 0.0038; 135,063 observations, 2,956 products | conservative pooled prior only |
| Price-aware weekly forecast | LightGBM + planned price vs SES vs no-price LightGBM, rolling origins | **WAPE 0.6952** (price) vs **0.7112** (SES) vs 0.7273 (no price); MAE 28.20 vs 28.85 vs 29.50 | scenario forecasts only; ~2% gain; SES remains default |
| Bundle rules | temporal split, Sep–Dec 2011 holdout | 82.1% of candidate rules keep lift > 1; train↔test lift Spearman **0.7852**; test confidence / base rate ≈ 3.21 | recommendations, not effect claims |
| Item-item recommender | hit-rate@10 | 46.2% vs popularity 33.8% | aggregate by default, consent-gated |
| Customer segmentation | KMeans / RFM, descriptive | 4 segments; 4,334 customers; 24.9% anonymous lines | descriptive only |
| Discount-proxy persistence | train vs test | Spearman ρ ≈ 0.49 | proxy only |
| MILP optimiser | brute-force equality + constraint tests | exact on test cases | adopted |
| Clearance replay | synthetic stock/cost/response | **no benefit demonstrated** | not a benefit claim |
| Synthetic ledger/ageing/recovery demos | unit tests | pass | logic verified only |

Retail test suite at merge: **98 passed, 4 skipped, 4 subtests passed in 7.10 s**.

---

## 4. Model artifact comparison

| Kind | Existing version | Retail version | Latest after merge |
|---|---|---|---|
| dead_stock | `dead_stock-ml-1.1.0-20261119T091454Z` | older | `dead_stock-ml-1.1.0-20261120T122808Z` (re-run, identical checksums) |
| forecasting | `forecasting-ml-1.1.0-20261119T091542Z` | older | `forecasting-ml-1.1.0-20261120T122830Z` (re-run, identical checksums) |
| movement | `movement-ml-1.1.0-20261119T091800Z` | older | unchanged |
| anomaly | `anomaly-ml-1.1.0-20261119T091800Z` | older | unchanged |
| pricing | — | `pricing-ml-1.0.0-20261119T092053Z` | added |
| bundles | — | `bundles-ml-1.0.0-20261119T092127Z` | added |
| customers | — | `customers-ml-1.0.0-20261119T092127Z` | added |
| forecasting_price | — | `forecasting_price-ml-1.0.0-20261119T092609Z` | added |

Retail models were added under new kind directories. Their own `LATEST` files were not overwritten by anything in the 1.1.0 core. Training re-runs create new timestamped directories and only update that kind's `LATEST`.

---

## 5. Code-level merge notes

- `src/trexo/ml/retail/**` added verbatim; it imports only stable core modules (`config`, `registry`) and its own subpackages.
- The retail `RetailIntelligenceService` is loaded lazily by the backend, so a missing retail artifact degrades only retail endpoints (`MODEL_UNAVAILABLE`, HTTP 503) and does not break store operations or core ML.
- `tests/ml/retail/**` added; the merged suite runs it together with core tests (now 141 passed / 4 skipped including 37 API tests).
- Retail scripts and docs were copied with their original names; no existing doc was replaced.
- The retail package's older duplicated core modules were **not** copied.

---

## 6. Conclusion

The correct integration is **existing 1.1.0 core + additive retail package**, not a fork replacement:

- it preserves the stronger governance, audited inference layer and rejected-challenger history;
- it gains the retail capabilities the core lacked;
- it keeps every model version and report;
- it adds a tested API and a UI that can consume both the store domain and the ML outputs.

The retail models remain decision support with explicit limitations: elasticity is observational, price-aware forecasting has a small (~2%) gain, and no real-shop profit benefit has been demonstrated.
