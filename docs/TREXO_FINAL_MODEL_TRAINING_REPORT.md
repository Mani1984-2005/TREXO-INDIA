# TREXO Final Model Training Report

**Date:** 2026-11-20
**Environment:** Python 3.11.9 (`.venv`), Windows, CPU
**Data:** UCI Online Retail (`data/raw/Online Retail.xlsx`) → `data/ml/valid_sales_v1.csv.gz` with D01 governance exclusions applied.

All numbers below were produced by the commands shown, in this environment, on this date. Nothing is estimated or copied from an earlier run unless explicitly labelled as a comparison.

---

## 1. Commands executed

```powershell
.venv\Scripts\python.exe scripts\ml_train_dead_stock.py
.venv\Scripts\python.exe scripts\ml_train_forecasting.py
.venv\Scripts\python.exe scripts\ml_independent_evaluation.py
```

The training scripts take no CLI flags; they read the prepared data and write:
`reports/ml/*.json`, `reports/ml/*.csv`, `data/ml/calibration.json`, and a new checksum-verified bundle under `models/<kind>/<version>/`.

No existing model version directory was modified or deleted. New versions were created and each kind's `LATEST` was repointed only after the registry round-trip and checksum verification succeeded.

---

## 2. Dead-stock risk model

### 2.1 Setup

| Item | Value |
|---|---|
| Target | no valid sale in the next **60 days** (demand inactivity; **not** physical dead stock) |
| Rows (train / validation / test) | 12,992 / 3,583 / 3,765 |
| Train cutoffs | 2011-03-10, 2011-04-09, 2011-05-09, 2011-06-08 |
| Validation cutoff | 2011-08-10 |
| Test cutoff | 2011-10-10 |
| Features | 27 (recency, quantity windows, invoice/sale-day frequency, gaps, trend, price, customer coverage) |
| Random seed | 42 |
| Tuning | purged forward-chaining CV inside the training period, PR-AUC objective |

### 2.2 Candidate comparison

| Candidate | Validation PR-AUC | Test PR-AUC |
|---|---:|---:|
| **Baseline: calibrated recency rule** | **0.7611** | **0.8020** |
| Histogram gradient boosting (selected challenger) | 0.788 | 0.793 |
| LightGBM | 0.786 | 0.780 |
| Random forest | 0.779 | 0.779 |
| Logistic regression | 0.775 | 0.793 |
| Prevalence prior | — | 0.2048 |

Acceptance rule: PR-AUC ≥ baseline + 0.02 on **both** validation and test, and Brier score better than the prevalence prior.

**Result: challenger REJECTED.** The selected gradient-boosting model did not clear the required margin over the calibrated recency rule. The retained artifacts are stored for audit and comparison only; inference deploys the calibrated recency rule.

### 2.3 Deployed predictor (train-only, out-of-time)

Test metrics at the validation-selected threshold (0.2318):

| Metric | Value |
|---|---:|
| ROC-AUC | 0.9469 |
| PR-AUC | 0.8020 |
| Brier | 0.0704 |
| Brier (prevalence prior) | 0.1628 |
| Precision | 0.6355 |
| Recall | 0.9092 |
| F1 / F2 | 0.7481 / 0.8371 |
| Confusion (TN/FP/FN/TP) | 2592 / 402 / 70 / 701 |

### 2.4 Rejected challenger (recorded for audit)

`hist_gradient_boosting`, refit on all labelled cutoffs:

| Metric | Raw | Isotonic-calibrated |
|---|---:|---:|
| Test PR-AUC | 0.7926 | 0.7838 |
| Test ROC-AUC | 0.9491 | 0.9484 |
| Test Brier | 0.0753 | 0.0712 |
| ECE | 0.0474 | 0.0183 |
| Stability (PR-AUC over seeds 1–5) | mean 0.7926, std 0.0000 | — |

Top permutation-importance features: `days_since_last_sale`, `recency_gap_ratio`, `qty_7d`, `log_total_value`, `missing_customer_share`, `age_days`, `mean_gap_days`, `inv_30d`.

### 2.5 Artifact

```
models/dead_stock/dead_stock-ml-1.1.0-20261120T122808Z/
```

| File | SHA-256 |
|---|---|
| `estimator.joblib` | `5b01ac0b991fbb79bfc80dd5a0b4729d78d580bfeef1ee43fc352b5d29b60c69` |
| `calibrator.joblib` | `3d5b2caff23e0b48da054beea7fe74e52143e8017e7dc30bb4555be8f051f2e2` |
| `rule_calibrator.joblib` | `741cea92510b3e95b0378e65851328345e77fc108bf2be9d45ae9f4f124b374b` |

These checksums are **identical** to the previous `20261119T091454Z` bundle, confirming the pipeline is deterministic on the same data and seed.

---

## 3. Demand forecasting model

### 3.1 Setup

| Item | Value |
|---|---|
| Products | 3,898 complete weekly series |
| Complete weeks | 53, ending 2011-12-06 |
| Backtest origins | weeks 36, 40, 44 |
| Minimum active weeks | 4 |
| Backtest rows | 75,704 |
| Actual total (units) | 3,070,561 |

### 3.2 Overall backtest

| Method | MAE | RMSE | WAPE | sMAPE | Bias |
|---|---:|---:|---:|---:|---:|
| zero | 40.56 | 130.93 | 1.000 | 1.248 | −1.000 |
| naive | 33.03 | 115.79 | 0.814 | 0.852 | −0.125 |
| ma4 | 29.75 | 101.49 | 0.734 | 0.939 | −0.153 |
| ma8 | 29.29 | 100.74 | 0.722 | 1.025 | −0.207 |
| **ses** | **28.85** | **99.74** | **0.711** | 1.252 | −0.160 |
| croston | 33.96 | 142.78 | 0.837 | 1.297 | −0.285 |
| sba | 33.66 | 139.86 | 0.830 | 1.300 | −0.321 |
| lightgbm | 29.50 | 102.49 | 0.727 | 1.226 | −0.142 |

**Selected overall by MAE: `ses`.**

Selected method by demand class:

| Demand class | Method |
|---|---|
| smooth | ses |
| intermittent | ma8 |
| erratic | sba |
| lumpy | ses |

### 3.3 Artifact

```
models/forecasting/forecasting-ml-1.1.0-20261120T122830Z/
```

The artifact checksums match the previous `20261119T091542Z` bundle exactly, again confirming deterministic reproducibility.

### 3.4 Price-aware variant (retail, separate artifact)

A separate `forecasting_price` artifact (not the default) was trained by the retail scripts: LightGBM using planned target-week price, WAPE **0.6952** vs SES **0.7112**, MAE 28.20 vs 28.85. The gain is small (~2%) and it is used **only** for price-conditional scenarios.

---

## 4. Other registry artifacts

| Kind | Version | Status |
|---|---|---|
| movement | `movement-ml-1.1.0-20261119T091800Z` | unchanged |
| anomaly | `anomaly-ml-1.1.0-20261119T091800Z` | unchanged |
| pricing | `pricing-ml-1.0.0-20261119T092053Z` | added by merge, unchanged |
| bundles | `bundles-ml-1.0.0-20261119T092127Z` | added by merge, unchanged |
| customers | `customers-ml-1.0.0-20261119T092127Z` | added by merge, unchanged |
| forecasting_price | `forecasting_price-ml-1.0.0-20261119T092609Z` | added by merge, unchanged |

---

## 5. Reproducibility evidence

- Both training scripts completed with the same row counts, cutoffs, selected models and metrics as the registered 2026-11-19 runs.
- All three dead-stock artifact checksums and the forecasting artifact checksums are byte-identical to the previous versions.
- The independent evaluation script (which does not import the repository's evaluation module) reproduced the deployed rule's validation and test metrics exactly:
  - validation PR-AUC `0.7611267027053554`
  - test PR-AUC `0.801978787703206`
  - test ROC-AUC `0.946921296115794`

Runtime: dead-stock training 21.2 s; forecasting 44.6 s.

---

## 6. Governance notes

- D01 invoices `A563185`, `A563186`, `A563187` are excluded from product-demand training and inference. They remain in the source records. The independent evaluation confirms **zero** occurrences in `valid_sales_v1.csv.gz`.
- Rejected challengers are retained with full metadata and are never deleted.
- `LATEST` is only repointed after registry checksum verification and a successful reload.
- No model is described as production-ready; the dead-stock target measures demand inactivity, not physical stock.
