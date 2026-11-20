from __future__ import annotations

from fastapi import APIRouter, Depends

from ..schemas.api import ModelInfo, RollbackInput
from ..security import require_admin, require_auth
from ..services import ml

router = APIRouter(prefix="/models", tags=["model-management"], dependencies=[Depends(require_auth)])


@router.get("", response_model=list[ModelInfo])
def list_models() -> list[dict]:
    return ml.list_models()


@router.get("/{kind}", response_model=ModelInfo)
def get_model(kind: str) -> dict:
    return ml.model(kind)


@router.post("/{kind}/activate", response_model=ModelInfo, dependencies=[Depends(require_admin)])
def activate(kind: str, payload: RollbackInput) -> dict:
    """Promote a previously trained version (rollback / roll-forward)."""
    return ml.activate(kind, payload.version)
