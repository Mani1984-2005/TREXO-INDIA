"""Shared API envelopes and ML request schemas."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    database: str
    models: dict[str, Any]


class SalesRecord(BaseModel):
    """One historical sale line used as ML input."""

    model_config = ConfigDict(extra="allow")

    invoice_no: Optional[str] = None
    date: str
    quantity: float
    unit_price: float
    customer_id: Optional[str] = None
    country: Optional[str] = None


class MLRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_id: str = Field(min_length=1, max_length=120)
    sales_history: list[SalesRecord] = Field(default_factory=list)
    as_of: Optional[str] = None
    description: Optional[str] = None
    on_hand_qty: Optional[float] = Field(default=None, ge=0)
    on_order_qty: Optional[float] = Field(default=None, ge=0)
    unit_cost: Optional[float] = Field(default=None, ge=0)
    lead_time_days: Optional[float] = Field(default=None, ge=0)
    lead_time_sd_days: Optional[float] = Field(default=None, ge=0)
    service_level: Optional[float] = Field(default=None, ge=0.5, lt=1)
    moq: Optional[float] = Field(default=None, gt=0)
    review_period_days: Optional[float] = Field(default=None, gt=0)
    supplier_terms: Optional[str] = None
    lifecycle_status: Optional[str] = None
    request_id: Optional[str] = None

    @field_validator("sales_history")
    @classmethod
    def _limit(cls, v: list[SalesRecord]) -> list[SalesRecord]:
        if len(v) > 20000:
            raise ValueError("sales_history exceeds the 20,000 record limit")
        return v


class ForecastRequest(MLRequest):
    horizon_weeks: int = Field(default=4, ge=1, le=8)


class PortfolioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    horizon_weeks: int = Field(default=4, ge=1, le=8)
    product_ids: Optional[list[str]] = None
    as_of: Optional[str] = None


class EventRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    event_id: str
    product_id: str
    location: str = "MAIN"
    ts: str
    type: str
    qty: float
    unit_cost: Optional[float] = None
    direction: Optional[int] = None
    expiry_date: Optional[str] = None
    unit_price: Optional[float] = None


class LedgerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[dict[str, Any]] = Field(min_length=1, max_length=20000)
    as_of: Optional[str] = None
    reported_counts: Optional[list[dict[str, Any]]] = None


class StockPriorityRequest(LedgerRequest):
    velocity_window_days: int = Field(default=56, ge=7, le=365)
    ageing_config: dict[str, Any] = Field(default_factory=dict)


class PricingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price: float = Field(gt=0)
    stock: float = Field(ge=0)
    daily_demand: float = Field(ge=0)
    cost: Optional[float] = Field(default=None, ge=0)
    horizon_days: int = Field(default=28, ge=1, le=180)
    elasticity: Optional[float] = None
    conservative: bool = True
    rules: dict[str, Any] = Field(default_factory=dict)
    holding_rate_annual: Optional[float] = None
    obsolescence_rate: float = Field(default=0.0, ge=0, le=1)


class BundleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(min_length=1)
    min_lift: float = Field(default=1.5, ge=1.0)
    min_conf: float = Field(default=0.05, ge=0, le=1)
    top_k: int = Field(default=3, ge=1, le=20)


class RecoveryRequest(StockPriorityRequest):
    prices: dict[str, float] = Field(default_factory=dict)
    costs: dict[str, float] = Field(default_factory=dict)
    elasticity: Optional[float] = None
    conservative: bool = True
    rules: dict[str, Any] = Field(default_factory=dict)
    holding_rate_annual: Optional[float] = None


class ModelInfo(BaseModel):
    kind: str
    latest: Optional[str]
    versions: list[str]
    metadata: dict[str, Any]


class RollbackInput(BaseModel):
    version: str = Field(min_length=1)


class StatusLiteral(BaseModel):
    status: Literal["OK", "NO_VALID_SALES", "DEGRADED"]
