from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..config import SERVICE_NAME
from ..dependencies import get_store
from ..schemas.api import HealthResponse
from ..services import ml
from ..store.service import StoreService

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request, store: StoreService = Depends(get_store)) -> dict:
    """Readiness probe: database reachable and model artifacts inspectable."""
    try:
        store.db.count("products")
        database = "ok"
    except Exception as exc:  # noqa: BLE001 - health must never raise
        database = f"error: {type(exc).__name__}"

    models: dict = {"status": "unavailable"}
    try:
        models = {"status": "ok", **ml.health()}
    except ml.ApiError as exc:  # noqa: SIM105 - explicit is clearer here
        models = {"status": "unavailable", "code": exc.code, "detail": exc.message}
    except Exception as exc:  # noqa: BLE001
        models = {"status": "unavailable", "detail": str(exc)}

    overall = "ok" if database == "ok" and str(models.get("status", "")).lower() == "ok" else "degraded"
    return {
        "status": overall,
        "service": SERVICE_NAME,
        "version": getattr(request.app, "version", "1.0.0"),
        "database": database,
        "models": models,
    }
