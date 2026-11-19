# ML Inference API Contract (service level)

> Status: stable Python service contract for backend integration. No HTTP server is included; a backend must wrap `trexo.ml.inference.service.InferenceService`. Examples in this document are real responses from `reports/ml/inference_contract_examples.json`.

## 1. Service

```python
from trexo.ml.inference.service import InferenceService, InvalidRequestError, ModelUnavailableError
svc = InferenceService()
```

Constructor loads the versioned artifacts and verifies their SHA-256 checksums. It raises `ModelUnavailableError` if calibrators/models are missing or corrupt; it never returns a fabricated prediction.

## 2. Common request envelope

```json
{
  "request_id": "optional-caller-id",
  "product_id": "22783",
  "description": "optional product description",
  "as_of": "2011-12-09",
  "sales_history": [
    {"invoice_no": "5001", "date": "2011-06-01", "quantity": 5, "unit_price": 2.1,
     "customer_id": 12345, "country": "United Kingdom"}
  ],
  "on_hand_qty": 40,
  "unit_cost": null,
  "lead_time_days": 14,
  "lead_time_sd_days": 3,
  "on_order_qty": 0,
  "moq": 10,
  "service_level": 0.95,
  "review_period_days": 7
}
```

Validation rules:
- `product_id` must be a non-empty string and must not be a non-product StockCode (`POST`, `DOT`, `B`, etc.).
- `sales_history` must be a list. Invalid dates, non-numeric/negative/zero quantity or price are excluded and reported in `warnings`; they are never silently treated as sales.
- Records carrying a D01 invoice (`A563185/A563186/A563187`) are excluded with an explicit governance warning.
- Records after `as_of` are ignored for all features and reported.
- Optional inventory fields must be finite and non-negative; `moq > 0`; `service_level` in `[0.5, 1)`.
- If no valid sales remain, the response is `status = "NO_VALID_SALES"` with `prediction = null` (no demand-based prediction).

## 3. Methods and response shape

| Method | Purpose |
|---|---|
| `health()` | artifact versions and readiness (no prediction) |
| `dead_stock_detection(req)` | demand-inactivity risk classification |
| `dead_stock_risk_prediction(req)` | alias of the deployed predictor |
| `demand_forecast(req, horizon_weeks=4)` | weekly level forecast, 1-8 weeks |
| `movement_classification(req)` | speed / ABC / XYZ / trend |
| `reorder_recommendation(req)` | demand guidance + optional reorder calculation |
| `anomaly_detection(req)` | transaction-quality alerts with explanations |
| `reduction_actions(req)` | prioritised, explainable intervention |
| `management_summary()` | latest aggregate management summary |

Every successful response includes:
- `schema_version` (`"1.0"`), `product_id`, `request_id`, `prediction_timestamp`, `as_of`
- `status` (`"OK"` or `"NO_VALID_SALES"`)
- `model_version`, `model_trained_at_utc`, `pipeline_version` where a model applies
- `warnings` and `missing_input_warnings`
- prediction-specific evidence, explanation, confidence and recommended action

### 3.1 Dead-stock detection

Adds: `classification` (Healthy / Normal / Slow / At-Risk / Critical / Confirmed), `dead_stock_risk_score` = calibrated probability of no sale in the next 60 days, `demand_pattern`, `evidence_quality`, `evidence_flags`, `evidence_basis`, `stock_verification_required`, `human_review_required`, `inventory_value_available`, `supporting_metrics`, `explanation`, `recommended_action`, `status_type`.

`Confirmed Dead Stock` is impossible unless the caller supplies `on_hand_qty > 0` and the demand evidence is Critical with non-LOW quality.

### 3.2 Demand forecast

Adds: `method`, `demand_class`, `forecast_weekly_units`, `forecast_total_units`, `prediction.expected_units_total`, `confidence` (including backtest WAPE reference). Horizon > 8 weeks raises `InvalidRequestError`.

### 3.3 Reorder

`reorder.status` is one of:
- `INSUFFICIENT_INPUTS` — missing `on_hand_qty` / `lead_time_days`; `recommended_order_qty = null`.
- `CALCULATED` — formula output with safety stock, reorder point, cover days and order quantity.
- `BLOCKED_BY_DEAD_STOCK_RISK` — order suppressed at risk >= 0.6.

`guidance.purchase_guidance` is one of `DO_NOT_REORDER`, `PAUSE_REORDER_PENDING_REVIEW`, `REDUCE_FUTURE_PURCHASES`, `DEMAND_SUPPORTS_REPLENISHMENT`. No purchase order is executed.

### 3.4 Anomaly

Returns `transaction_quality_flags` with `flags`, `what_was_unusual`, `why_review`. Report-only; rows are never removed; anomalies are not fraud findings.

### 3.5 Reduction actions

Returns `priority`, `intervention`, `recommended_action`, `risk_classification`, `expected_impact_direction`, `inventory_value_impact`, `required_information`, `requires_human_approval`, and a five-part explanation.

## 4. Errors

| Error | When |
|---|---|
| `InvalidRequestError` | malformed request, non-product id, invalid date, invalid numeric inventory input, horizon out of range |
| `ModelUnavailableError` | artifacts/calibrator missing or checksum verification fails |

Errors are raised, not converted into optimistic predictions.

## 5. Backend integration notes

1. The service is stateless per call; it does not mutate source datasets.
2. Call `health()` at deployment and after every artifact promotion.
3. Persist `model_version`, `pipeline_version`, `prediction_timestamp` and input warnings with every prediction for audit.
4. Do not expose `management_summary()` as a real-time endpoint without caching; it reads a generated report.
5. Authentication, rate limiting, TLS, logging and PII controls are backend responsibilities and are not implemented here.
6. Do not auto-execute reorder/reduction recommendations. `requires_human_approval` is always true for business actions.
