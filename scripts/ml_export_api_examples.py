"""Call the real InferenceService and export request/response contract examples."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pandas as pd
from trexo.ml.config import REPORT_DIR
from trexo.ml.inference.service import InferenceService

svc = InferenceService()
d0 = pd.Timestamp("2011-01-15")
healthy = {"request_id": "demo-healthy", "product_id": "TREXO-DEMO-001", "description": "Demo steady seller",
           "as_of": "2011-12-09",
           "sales_history": [{"invoice_no": f"9{i:05d}", "date": str((d0 + pd.Timedelta(days=7 * i)).date()),
                              "quantity": 12, "unit_price": 4.5, "customer_id": 100 + i % 7} for i in range(44)]}
stale = {"request_id": "demo-stale", "product_id": "TREXO-DEMO-002", "description": "Demo stalled item",
         "as_of": "2011-12-09",
         "sales_history": [{"invoice_no": f"8{i:05d}", "date": str((d0 + pd.Timedelta(days=3 * i)).date()),
                            "quantity": 5, "unit_price": 8.0, "customer_id": 200 + i % 5} for i in range(40)]}
stale["sales_history"] = stale["sales_history"][:55]  # stops around mid-year
examples = {
    "service": "trexo.ml.inference.service.InferenceService",
    "health": svc.health(),
    "requests": {"healthy": healthy, "stale": stale},
    "responses": {
        "dead_stock_detection_healthy": svc.dead_stock_detection(healthy),
        "dead_stock_detection_stale": svc.dead_stock_detection(stale),
        "demand_forecast_stale": svc.demand_forecast(stale, horizon_weeks=4),
        "movement_classification_healthy": svc.movement_classification(healthy),
        "reorder_without_inventory": svc.reorder_recommendation(stale),
        "reorder_with_inventory": svc.reorder_recommendation({**healthy, "on_hand_qty": 40, "lead_time_days": 14,
                                                             "moq": 10, "service_level": 0.95}),
        "anomaly_detection_healthy": svc.anomaly_detection(healthy),
        "reduction_actions_stale": svc.reduction_actions(stale),
    },
}
REPORT_DIR.mkdir(parents=True, exist_ok=True)
(REPORT_DIR / "inference_contract_examples.json").write_text(json.dumps(examples, indent=2, default=str))
print(json.dumps({
    "health": examples["health"],
    "stale_classification": examples["responses"]["dead_stock_detection_stale"].get("classification"),
    "reorder_without_inputs_status": examples["responses"]["reorder_without_inventory"]["reorder"]["status"],
    "reorder_with_inputs_status": examples["responses"]["reorder_with_inventory"]["reorder"]["status"],
    "reduction_priority": examples["responses"]["reduction_actions_stale"].get("prediction"),
}, indent=2, default=str))
