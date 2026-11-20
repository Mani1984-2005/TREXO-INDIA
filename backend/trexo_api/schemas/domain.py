"""Pydantic contracts mirroring ``frontend/src/types/domain.ts``.

Field names are snake_case internally and serialised as camelCase so the React
client consumes exactly the shapes it already declares.  Validation is
deliberately strict about money (integer paise) and quantities.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

Category = Literal[
    "Grains & Atta",
    "Edible Oils",
    "Dairy & Daily",
    "Snacks & Beverages",
    "Home & Personal",
    "Specialty & Dry Fruits",
]
PaymentMethod = Literal["cash", "upi", "udhaar"]
UpiStatus = Literal["initiated", "awaiting_verification", "confirmed", "failed", "cancelled"]
Horizon = Literal["1W", "1M", "6M", "1Y"]
ReturnReason = Literal[
    "Dead stock (slow moving)", "Near expiry", "Damaged packaging", "Excess supply"
]


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class Product(CamelModel):
    id: str
    sku: str
    name: str
    hindi_name: Optional[str] = None
    kannada_name: Optional[str] = None
    category: Category
    unit: str
    mrp_paise: int = Field(ge=0)
    cost_paise: int = Field(ge=0)
    selling_price_paise: int = Field(ge=0)
    counter_discount_price_paise: Optional[int] = Field(default=None, ge=0)
    stock_qty: int = Field(ge=0)
    reorder_level: int = Field(ge=0)
    avg_daily_sales: float = Field(ge=0)
    last_sold_at: str
    expiry_date: Optional[str] = None
    supplier_id: str
    stop_reordering: bool = False


class ProductCreateInput(CamelModel):
    name: str = Field(min_length=1, max_length=200)
    sku: str = Field(min_length=1, max_length=60)
    category: Category
    unit: str = Field(min_length=1, max_length=60)
    mrp_paise: int = Field(ge=0)
    cost_paise: int = Field(ge=0)
    selling_price_paise: int = Field(ge=0)
    stock_qty: int = Field(ge=0)
    reorder_level: int = Field(ge=0)
    expiry_date: Optional[str] = None
    supplier_id: str


class ProductPatch(CamelModel):
    """Partial product update.  Only mutable operational fields are accepted."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    sku: Optional[str] = Field(default=None, min_length=1, max_length=60)
    category: Optional[Category] = None
    unit: Optional[str] = None
    mrp_paise: Optional[int] = Field(default=None, ge=0)
    cost_paise: Optional[int] = Field(default=None, ge=0)
    selling_price_paise: Optional[int] = Field(default=None, ge=0)
    stock_qty: Optional[int] = Field(default=None, ge=0)
    reorder_level: Optional[int] = Field(default=None, ge=0)
    expiry_date: Optional[str] = None
    supplier_id: Optional[str] = None
    stop_reordering: Optional[bool] = None


class CartItem(CamelModel):
    product_id: str
    qty: int = Field(ge=0)


class SaleLineItem(CamelModel):
    product_id: str
    sku: str
    name: str
    unit: str
    qty: int = Field(ge=0)
    unit_price_paise: int = Field(ge=0)
    original_price_paise: int = Field(ge=0)
    cost_paise: int = Field(ge=0)
    is_dead_stock_rescued: bool
    line_total_paise: int = Field(ge=0)


class Sale(CamelModel):
    id: str
    invoice_no: str
    created_at: str
    items: list[SaleLineItem]
    subtotal_paise: int = Field(ge=0)
    discount_saved_paise: int = Field(ge=0)
    total_paise: int = Field(ge=0)
    payment_method: PaymentMethod
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    rescued_dead_stock_paise: int = Field(ge=0)
    upi_transaction_ref: Optional[str] = None
    upi_utr_number: Optional[str] = None
    upi_id_used: Optional[str] = None
    payment_status: Optional[UpiStatus] = None
    is_demo_payment: Optional[bool] = None


class CompleteSaleInput(CamelModel):
    items: list[CartItem] = Field(min_length=1, max_length=100)
    payment_method: PaymentMethod
    customer_id: Optional[str] = None
    upi_transaction_ref: Optional[str] = None
    upi_utr_number: Optional[str] = None
    upi_id_used: Optional[str] = None
    payment_status: Optional[UpiStatus] = None
    is_demo_payment: Optional[bool] = None


class Customer(CamelModel):
    id: str
    name: str
    phone: str
    address: str
    due_paise: int = Field(ge=0)
    last_transaction_at: str


class CustomerCreateInput(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=3, max_length=20)
    address: str = ""
    opening_due_paise: Optional[int] = Field(default=0, ge=0)


class CustomerPaymentEntry(CamelModel):
    id: str
    customer_id: str
    customer_name: str
    amount_paise: int = Field(ge=0)
    previous_due_paise: int = Field(ge=0)
    remaining_due_paise: int = Field(ge=0)
    payment_method: Literal["cash", "upi"]
    status: UpiStatus
    transaction_ref: str
    utr_number: Optional[str] = None
    upi_id_used: Optional[str] = None
    is_demo: bool = True
    created_at: str


class RecordPaymentMeta(CamelModel):
    payment_method: Literal["cash", "upi"] = "cash"
    transaction_ref: Optional[str] = None
    utr_number: Optional[str] = None
    upi_id_used: Optional[str] = None
    status: Optional[UpiStatus] = None
    is_demo: Optional[bool] = None


class PartialPaymentInput(CamelModel):
    amount_paise: int = Field(gt=0)
    meta: Optional[RecordPaymentMeta] = None


class PaymentAttemptInput(CamelModel):
    amount_paise: int = Field(ge=0)
    meta: RecordPaymentMeta


class Supplier(CamelModel):
    id: str
    name: str
    contact_person: str
    phone: str
    city: str
    lead_time_days: int = Field(ge=0)


class SupplierReturnItem(CamelModel):
    id: str
    product_id: str
    product_name: str
    sku: str
    supplier_id: str
    supplier_name: str
    qty: int = Field(gt=0)
    unit_cost_paise: int = Field(ge=0)
    total_credit_paise: int = Field(ge=0)
    reason: ReturnReason
    created_at: str
    slip_generated_at: Optional[str] = None


class ReturnToSupplierInput(CamelModel):
    product_id: str
    qty: int = Field(gt=0)
    reason: ReturnReason


class SupplierReturnResult(CamelModel):
    product: Product
    return_item: SupplierReturnItem


class MarkReturnsInput(CamelModel):
    return_ids: list[str]


class PurchaseOrderItem(CamelModel):
    product_id: str
    sku: str
    name: str
    supplier_id: str
    supplier_name: str
    qty: int = Field(gt=0)
    unit_cost_paise: int = Field(ge=0)
    line_total_paise: int = Field(ge=0)


class PurchaseOrderCreateItem(CamelModel):
    product_id: str
    sku: str
    name: str
    supplier_id: str
    supplier_name: str
    qty: int = Field(gt=0)
    unit_cost_paise: int = Field(ge=0)


class PurchaseOrder(CamelModel):
    id: str
    po_number: str
    created_at: str
    status: Literal["Ordered", "Received"]
    items: list[PurchaseOrderItem]
    total_paise: int = Field(ge=0)


class ForecastRow(CamelModel):
    product_id: str
    sku: str
    name: str
    category: Category
    supplier_id: str
    supplier_name: str
    current_stock: int = Field(ge=0)
    avg_daily_sales: float = Field(ge=0)
    forecasted_demand: int = Field(ge=0)
    recommended_order_qty: int = Field(ge=0)
    estimated_order_cost_paise: int = Field(ge=0)
    estimated_lost_sales_paise: int = Field(ge=0)
    days_of_cover: float = Field(ge=0)
    status: Literal["Out of Stock", "Low Stock", "Healthy", "Stopped"]
    stop_reordering: bool


class DailySeriesPoint(CamelModel):
    label: str
    revenue_rupees: int
    rescued_rupees: int


class TopProduct(CamelModel):
    product_id: str
    name: str
    qty_sold: int
    revenue_paise: int


class SalesSummary(CamelModel):
    today_revenue_paise: int
    today_bills_count: int
    total_revenue_paise: int
    cash_revenue_paise: int
    upi_revenue_paise: int
    udhaar_revenue_paise: int
    total_rescued_cash_paise: int
    daily_series: list[DailySeriesPoint]
    top_products: list[TopProduct]


class LoginInput(CamelModel):
    password: str = Field(min_length=1, max_length=200)


class LoginResult(CamelModel):
    token: str
    expires_in: int
    token_type: Literal["bearer"] = "bearer"


class AdjustStockInput(CamelModel):
    delta_qty: int

    @field_validator("delta_qty")
    @classmethod
    def _nonzero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("delta_qty must not be zero")
        return v


class PaymentResult(CamelModel):
    customer: Customer
    payment: CustomerPaymentEntry


class Ack(CamelModel):
    status: Literal["OK"] = "OK"
    message: str | None = None


class ResetDemoInput(CamelModel):
    confirmation: str = Field(min_length=1, max_length=100)


class SetDiscountInput(CamelModel):
    price_paise: Optional[int] = Field(default=None, ge=0)


class StopReorderingInput(CamelModel):
    stop: bool
