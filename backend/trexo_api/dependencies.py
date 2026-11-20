"""Shared FastAPI dependencies."""
from __future__ import annotations

from fastapi import Request

from .store.service import StoreService


def get_store(request: Request) -> StoreService:
    return request.app.state.store
