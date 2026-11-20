from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query, status

from ..dependencies import get_store
from ..schemas.domain import (
    Ack,
    AdjustStockInput,
    CompleteSaleInput,
    Customer,
    CustomerCreateInput,
    CustomerPaymentEntry,
    ForecastRow,
    MarkReturnsInput,
    PartialPaymentInput,
    PaymentAttemptInput,
    PaymentResult,
    Product,
    ProductCreateInput,
    ProductPatch,
    PurchaseOrder,
    PurchaseOrderCreateItem,
    ResetDemoInput,
    ReturnToSupplierInput,
    Sale,
    SalesSummary,
    SetDiscountInput,
    StopReorderingInput,
    Supplier,
    SupplierReturnItem,
    SupplierReturnResult,
)
from ..security import require_admin, require_auth
from ..store.service import StoreError, StoreService

router = APIRouter(prefix="/store", tags=["store"], dependencies=[Depends(require_auth)])

logger = logging.getLogger("trexo.api.reset")


# ---------------------------------------------------------------- products
@router.get("/products", response_model=list[Product])
def list_products(store: StoreService = Depends(get_store)):
    return store.list_products()


@router.post("/products", response_model=Product, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreateInput, store: StoreService = Depends(get_store)):
    return store.create_product(payload.model_dump(by_alias=True, exclude_unset=True))


@router.patch("/products/{product_id}", response_model=Product)
def update_product(product_id: str, payload: ProductPatch, store: StoreService = Depends(get_store)):
    return store.update_product(product_id, payload.model_dump(by_alias=True, exclude_unset=True))


@router.post("/products/{product_id}/counter-discount", response_model=Product)
def set_counter_discount(
    product_id: str, payload: SetDiscountInput, store: StoreService = Depends(get_store)
):
    return store.set_counter_discount(product_id, payload.price_paise)


@router.post("/products/{product_id}/stop-reordering", response_model=Product)
def set_stop_reordering(
    product_id: str, payload: StopReorderingInput, store: StoreService = Depends(get_store)
):
    return store.set_stop_reordering(product_id, payload.stop)


# ----------------------------------------------------------------- billing
@router.get("/sales", response_model=list[Sale])
def list_sales(store: StoreService = Depends(get_store)):
    return store.list_sales()


@router.post("/sales", response_model=Sale, status_code=status.HTTP_201_CREATED)
def complete_sale(payload: CompleteSaleInput, store: StoreService = Depends(get_store)):
    return store.complete_sale(payload.model_dump(by_alias=True, exclude_unset=True))


# --------------------------------------------------------------- inventory
@router.post("/products/{product_id}/stock", response_model=Product)
def adjust_stock(
    product_id: str, payload: AdjustStockInput, store: StoreService = Depends(get_store)
):
    return store.adjust_stock(product_id, payload.delta_qty)


@router.post("/supplier-returns", response_model=SupplierReturnResult, status_code=201)
def return_to_supplier(payload: ReturnToSupplierInput, store: StoreService = Depends(get_store)):
    result = store.return_to_supplier(payload.product_id, payload.qty, payload.reason)
    return {"product": result["product"], "returnItem": result["returnItem"]}


@router.get("/supplier-returns", response_model=list[SupplierReturnItem])
def list_supplier_returns(store: StoreService = Depends(get_store)):
    return store.list_returns()


@router.post("/supplier-returns/mark-slips", response_model=list[SupplierReturnItem])
def mark_slips(payload: MarkReturnsInput, store: StoreService = Depends(get_store)):
    return store.mark_return_slips(payload.return_ids)


@router.delete("/supplier-returns/{return_id}", status_code=status.HTTP_204_NO_CONTENT)
def clear_supplier_return(return_id: str, store: StoreService = Depends(get_store)):
    store.clear_returned_item(return_id)
    return None


# --------------------------------------------------------------- suppliers
@router.get("/suppliers", response_model=list[Supplier])
def list_suppliers(store: StoreService = Depends(get_store)):
    return store.list_suppliers()


# --------------------------------------------------------------- customers
@router.get("/customers", response_model=list[Customer])
def list_customers(store: StoreService = Depends(get_store)):
    return store.list_customers()


@router.post("/customers", response_model=Customer, status_code=201)
def create_customer(payload: CustomerCreateInput, store: StoreService = Depends(get_store)):
    return store.create_customer(payload.model_dump(by_alias=True, exclude_unset=True))


@router.get("/customer-payments", response_model=list[CustomerPaymentEntry])
def list_payments(store: StoreService = Depends(get_store)):
    return store.list_payments()


@router.post("/customers/{customer_id}/payments", response_model=PaymentResult)
def record_payment(
    customer_id: str, payload: PartialPaymentInput, store: StoreService = Depends(get_store)
):
    meta = payload.meta.model_dump(by_alias=True, exclude_unset=True) if payload.meta else None
    return store.record_partial_payment(customer_id, payload.amount_paise, meta)


@router.post("/customers/{customer_id}/payment-attempts", response_model=CustomerPaymentEntry)
def record_payment_attempt(
    customer_id: str, payload: PaymentAttemptInput, store: StoreService = Depends(get_store)
):
    return store.record_payment_attempt(
        customer_id, payload.amount_paise, payload.meta.model_dump(by_alias=True, exclude_unset=True)
    )


# ---------------------------------------------------------------- forecast
@router.get("/forecast", response_model=list[ForecastRow])
def get_forecast(
    horizon: str = Query(default="1M", pattern="^(1W|1M|6M|1Y)$"),
    store: StoreService = Depends(get_store),
):
    return store.forecast(horizon)


@router.get("/purchase-orders", response_model=list[PurchaseOrder])
def list_purchase_orders(store: StoreService = Depends(get_store)):
    return store.list_purchase_orders()


@router.post("/purchase-orders", response_model=PurchaseOrder, status_code=201)
def create_purchase_order(
    items: list[PurchaseOrderCreateItem], store: StoreService = Depends(get_store)
):
    return store.create_purchase_order([i.model_dump(by_alias=True) for i in items])


# ----------------------------------------------------------------- reports
@router.get("/reports/sales-summary", response_model=SalesSummary)
def sales_summary(store: StoreService = Depends(get_store)):
    return store.sales_summary()


@router.post(
    "/reports/reset-demo",
    response_model=Ack,
    dependencies=[Depends(require_admin)],
)
def reset_demo(
    payload: ResetDemoInput,
    store: StoreService = Depends(get_store),
):
    if payload.confirmation != "RESET-DEMO":
        logger.warning("Demo reset rejected: invalid confirmation")
        raise StoreError("RESET_CONFIRMATION_REQUIRED", "Explicit RESET-DEMO confirmation is required.", 400)
    store.reset_demo_data()
    logger.warning("Demo reset completed")
    return {"status": "OK", "message": "Demo data reset"}


# --------------------------------------------------------------------- ML
@router.get("/ml/catalog")
def ml_catalog(store: StoreService = Depends(get_store)) -> dict[str, Any]:
    """Products prepared for the ML layer (sales history is server-derived)."""
    catalog = store.ml_product_catalog()
    return {"status": "OK", "count": len(catalog), "products": catalog}
