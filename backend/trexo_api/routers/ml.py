from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends

from ..config import REPO_ROOT
from ..dependencies import get_store
from ..schemas.api import (
    BundleRequest,
    ForecastRequest,
    LedgerRequest,
    MLRequest,
    PortfolioRequest,
    PricingRequest,
    RecoveryRequest,
    StockPriorityRequest,
)
from ..security import require_auth
from ..services import ml
from ..store.service import StoreService

router = APIRouter(prefix="/ml", tags=["machine-learning"], dependencies=[Depends(require_auth)])
retail_router = APIRouter(prefix="/retail", tags=["retail-intelligence"], dependencies=[Depends(require_auth)])


@router.post("/dead-stock")
def dead_stock(payload: MLRequest) -> dict:
    return ml.dead_stock(payload.model_dump(exclude_none=True))


@router.post("/dead-stock/risk")
def dead_stock_risk(payload: MLRequest) -> dict:
    return ml.dead_stock(payload.model_dump(exclude_none=True))


@router.post("/forecast")
def forecast(payload: ForecastRequest) -> dict:
    body = payload.model_dump(exclude_none=True)
    horizon = body.pop("horizon_weeks", 4)
    return ml.forecast(body, horizon)


@router.post("/movement")
def movement(payload: MLRequest) -> dict:
    return ml.movement(payload.model_dump(exclude_none=True))


@router.post("/anomalies")
def anomalies(payload: MLRequest) -> dict:
    return ml.anomalies(payload.model_dump(exclude_none=True))


@router.post("/reorder")
def reorder(payload: MLRequest) -> dict:
    return ml.reorder(payload.model_dump(exclude_none=True))


@router.post("/reduction-actions")
def reduction_actions(payload: MLRequest) -> dict:
    return ml.reduction_actions(payload.model_dump(exclude_none=True))


@router.get("/summary")
def summary() -> dict:
    return ml.summary()


@router.post("/portfolio")
def portfolio(payload: PortfolioRequest, store: StoreService = Depends(get_store)) -> dict:
    """Run the audited inference pipeline over the shop catalogue.

    Every product is evaluated independently.  A product with insufficient
    history returns ``NO_VALID_SALES`` rather than a fabricated prediction.
    """
    catalog = store.ml_product_catalog()
    if payload.product_ids:
        wanted = {p.strip().upper() for p in payload.product_ids}
        catalog = [p for p in catalog if p["product_id"].upper() in wanted]
    results: list[dict] = []
    failures = 0
    for item in catalog:
        request = {
            "product_id": item["product_id"],
            "sales_history": item["sales_history"],
            "as_of": payload.as_of or item["as_of"],
            "description": item["product_name"],
        }
        if item.get("on_hand_qty") is not None:
            request["on_hand_qty"] = item["on_hand_qty"]
        if item.get("unit_cost") is not None:
            request["unit_cost"] = item["unit_cost"]
        if item.get("lead_time_days") is not None:
            request["lead_time_days"] = item["lead_time_days"]
        try:
            dead = ml.dead_stock(request)
            fc = ml.forecast(
                {**request, "on_hand_qty": item.get("on_hand_qty")}, payload.horizon_weeks
            )
        except ml.ApiError as exc:
            if exc.code == "MODEL_UNAVAILABLE":
                raise
            failures += 1
            results.append(
                {
                    "productId": item["product_id"],
                    "name": item["product_name"],
                    "status": "ERROR",
                    "error": {"code": exc.code, "message": exc.message},
                }
            )
            continue
        results.append(
            {
                "productId": item["product_id"],
                "name": item["product_name"],
                "status": "OK",
                "deadStock": dead,
                "forecast": fc,
            }
        )
    return {
        "status": "OK",
        "evaluated": len(results),
        "failures": failures,
        "syntheticHistoryNote": (
            "The demo catalogue's sales history is synthetic seed data; it must not be read as "
            "real-world performance evidence."
        ),
        "results": results,
    }


@retail_router.post("/inventory/balances")
def inventory_balances(payload: LedgerRequest) -> dict:
    return ml.inventory_balances(payload.model_dump(exclude_none=True))


@retail_router.post("/stock-priority")
def stock_priority(payload: StockPriorityRequest) -> dict:
    return ml.stock_priority(payload.model_dump(exclude_none=True))


@retail_router.post("/pricing/scenarios")
def pricing_scenarios(payload: PricingRequest) -> dict:
    return ml.pricing_scenarios(payload.model_dump(exclude_none=True))


@retail_router.post("/bundles/recommendations")
def bundles(payload: BundleRequest) -> dict:
    return ml.bundle_recommendations(payload.model_dump(exclude_none=True))


@retail_router.post("/recovery/plan")
def recovery(payload: RecoveryRequest) -> dict:
    return ml.recovery_plan(payload.model_dump(exclude_none=True))


@retail_router.get("/insights")
def insights() -> dict:
    """Read-only published experiment outputs (no live customer data)."""
    base = REPO_ROOT / "reports" / "ml" / "retail"
    out: dict[str, Any] = {"status": "OK", "sources": []}
    files = {
        "bundlesAndCustomers": base / "bundles_customers_results.json",
        "pricingElasticity": base / "pricing_elasticity_results.json",
        "priceAwareForecast": base / "forecast_price_aware_results.json",
        "customerSegments": base / "customer_segments_aggregate.csv",
    }
    for key, path in files.items():
        if not path.exists():
            out[key] = None
            continue
        out["sources"].append(str(path.relative_to(REPO_ROOT)))
        if path.suffix == ".json":
            try:
                out[key] = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                out[key] = None
        else:
            rows = path.read_text(encoding="utf-8").strip().splitlines()
            header = rows[0].split(",") if rows else []
            out[key] = [dict(zip(header, row.split(","))) for row in rows[1:]] if len(rows) > 1 else []
    return out
