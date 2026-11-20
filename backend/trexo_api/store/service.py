"""Store-operations business logic.

This module is a server-side implementation of the contract previously
implemented in ``frontend/src/services/mockServices.ts``.  Behaviour is kept
intentionally equivalent (same invoice sequence, same clamping, same duplicate
UPI guard) so switching the frontend between mock and API does not change
business semantics.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import random
import uuid
from pathlib import Path
from typing import Any

from .db import StoreDB

SEED_PATH = Path(__file__).with_name("seed_data.json")
HORIZON = {
    "1W": (7, 1.05),
    "1M": (30, 1.12),
    "6M": (180, 1.18),
    "1Y": (365, 1.24),
}
DEADSTOCK_DAYS = 30
NEAR_EXPIRY_DAYS = 14


class StoreError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(value: dt.datetime | None = None) -> str:
    return (value or _now()).isoformat().replace("+00:00", "Z")


def _parse(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return _now()
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def _days_since(iso_date: str, now: dt.datetime | None = None) -> int:
    then = _parse(iso_date)
    delta = (now or _now()) - then
    return max(0, delta.days)


def _days_until(iso_date: str | None, now: dt.datetime | None = None) -> int | None:
    if not iso_date:
        return None
    target = _parse(iso_date)
    delta = target - (now or _now())
    return math.ceil(delta.total_seconds() / 86400)


def effective_price(product: dict) -> int:
    disc = product.get("counterDiscountPricePaise")
    selling = int(product["sellingPricePaise"])
    if disc is not None and 0 <= disc < selling:
        return int(disc)
    return selling


def is_dead_stock(product: dict, now: dt.datetime | None = None) -> bool:
    return product["stockQty"] > 0 and _days_since(product["lastSoldAt"], now) >= DEADSTOCK_DAYS


def is_near_expiry(product: dict, now: dt.datetime | None = None) -> bool:
    if product["stockQty"] <= 0:
        return False
    left = _days_until(product.get("expiryDate"), now)
    return left is not None and left <= NEAR_EXPIRY_DAYS


def is_stockout_fast_mover(product: dict) -> bool:
    return (
        not product["stopReordering"]
        and product["stockQty"] == 0
        and float(product["avgDailySales"]) >= 2
    )


class StoreService:
    def __init__(self, db: StoreDB):
        self.db = db
        self.ensure_seed()

    # ------------------------------------------------------------------ seed
    def ensure_seed(self) -> None:
        if self.db.count("products") == 0:
            seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
            # Re-base relative timestamps so a fresh database is always current.
            now = _now()
            dump_time = dt.datetime.fromtimestamp(SEED_PATH.stat().st_mtime, dt.timezone.utc)
            shift = now - dump_time
            for table, key in (
                ("products", "products"),
                ("customers", "customers"),
                ("sales", "sales"),
                ("suppliers", "suppliers"),
                ("supplier_returns", "supplierReturns"),
                ("purchase_orders", "purchaseOrders"),
            ):
                for row in seed.get(key, []):
                    self._shift_dates(row, shift)
                    created = row.get("createdAt") or _iso()
                    self.db.put(table, row["id"], row, created)
            for row in seed.get("customerPayments", []):
                self._shift_dates(row, shift)
                self.db.put("customer_payments", row["id"], row, row.get("createdAt", _iso()))
            self.db.set_meta("invoice_seq", str(seed.get("invoiceSeq", 1000)))
            self.db.set_meta("po_seq", str(seed.get("poSeq", 1)))
            self.db.set_meta("confirmed_refs", json.dumps(seed.get("confirmedRefs", [])))
        if not self.db.has_history():
            self._seed_history()

    @staticmethod
    def _shift_dates(row: dict, shift: dt.timedelta) -> None:
        for field in ("lastSoldAt", "createdAt", "lastTransactionAt", "slipGeneratedAt", "expiryDate"):
            value = row.get(field)
            if not isinstance(value, str) or len(value) < 10:
                continue
            try:
                parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            row[field] = _iso(parsed + shift)

    def _seed_history(self) -> None:
        """Synthetic 180-day sales history for ML demos.

        Explicitly synthetic: it is derived from each product's configured
        average daily sales and never presented as real-world performance.
        """
        rng = random.Random(20261120)
        rows: list[tuple[str, str, float, float, str]] = []
        today = _now().date()
        for product in self.db.all("products"):
            rate = float(product["avgDailySales"])
            if rate <= 0:
                continue
            last_sale = _parse(product["lastSoldAt"]).date()
            # Products whose last sale is old intentionally behave as at-risk.
            end = min(today, last_sale)
            price = product["sellingPricePaise"] / 100.0
            for age in range(180, 0, -1):
                day = today - dt.timedelta(days=age)
                if day > end:
                    continue
                weekday = 1.25 if day.weekday() >= 5 else 1.0
                lam = rate * weekday
                # Knuth Poisson draw without a numpy dependency.
                limit, p, qty = math.exp(-lam), rng.random(), 0
                while p > limit and qty < 60:
                    qty += 1
                    p *= rng.random()
                if qty <= 0:
                    continue
                jitter = 1.0 + rng.uniform(-0.06, 0.06)
                rows.append(
                    (
                        product["id"],
                        day.isoformat(),
                        float(qty),
                        round(price * jitter, 2),
                        f"ML-{day.strftime('%Y%m%d')}-{product['sku']}",
                    )
                )
        if rows:
            self.db.add_history_rows(rows)

    # -------------------------------------------------------------- products
    def list_products(self) -> list[dict]:
        return self.db.all("products")

    def _product(self, product_id: str) -> dict:
        product = self.db.get("products", product_id)
        if product is None:
            raise StoreError("PRODUCT_NOT_FOUND", "Product not found", 404)
        return product

    def create_product(self, payload: dict) -> dict:
        now_iso = _iso()
        sku = (payload.get("sku") or "").strip().upper() or f"SKU-{uuid.uuid4().hex[:4].upper()}"
        product = {
            "id": f"prod-{uuid.uuid4().hex[:12]}",
            "sku": sku,
            "name": payload["name"].strip(),
            "category": payload["category"],
            "unit": payload.get("unit") or "1 unit",
            "mrpPaise": int(payload.get("mrpPaise", 0)),
            "costPaise": int(payload.get("costPaise", 0)),
            "sellingPricePaise": int(payload.get("sellingPricePaise", 0)),
            "counterDiscountPricePaise": None,
            "stockQty": max(0, int(payload.get("stockQty", 0))),
            "reorderLevel": max(0, int(payload.get("reorderLevel", 0))),
            "avgDailySales": 0,
            "lastSoldAt": now_iso,
            "expiryDate": payload.get("expiryDate"),
            "supplierId": payload["supplierId"],
            "stopReordering": False,
        }
        self.db.put("products", product["id"], product, now_iso)
        return product

    def update_product(self, product_id: str, patch: dict) -> dict:
        product = self._product(product_id)
        cleaned = dict(patch)
        if cleaned.get("sku"):
            cleaned["sku"] = str(cleaned["sku"]).strip().upper()
        product.update(cleaned)
        for key in ("mrpPaise", "costPaise", "sellingPricePaise", "stockQty", "reorderLevel"):
            if key in cleaned:
                product[key] = max(0, int(cleaned[key]))
        self.db.put("products", product_id, product, product.get("lastSoldAt") or _iso())
        return product

    def set_counter_discount(self, product_id: str, price_paise: int | None) -> dict:
        product = self._product(product_id)
        selling = int(product["sellingPricePaise"])
        product["counterDiscountPricePaise"] = (
            int(round(price_paise)) if price_paise is not None and 0 < price_paise < selling else None
        )
        self.db.put("products", product_id, product, product.get("lastSoldAt") or _iso())
        return product

    def set_stop_reordering(self, product_id: str, stop: bool) -> dict:
        product = self._product(product_id)
        product["stopReordering"] = bool(stop)
        self.db.put("products", product_id, product, product.get("lastSoldAt") or _iso())
        return product

    # --------------------------------------------------------------- billing
    def list_sales(self) -> list[dict]:
        return self.db.all("sales")

    def complete_sale(self, payload: dict) -> dict:
        products = {p["id"]: p for p in self.db.all("products")}
        now = _now()
        now_iso = _iso(now)
        items: list[dict] = []
        pending_updates: list[dict] = []
        subtotal = total = rescued = 0
        for line in payload["items"]:
            product = products.get(line["productId"])
            if product is None:
                raise StoreError("PRODUCT_NOT_FOUND", f"Product {line['productId']} not found", 404)
            if product["stockQty"] <= 0:
                raise StoreError("OUT_OF_STOCK", f"{product['name']} is out of stock.")
            qty = max(1, int(round(line["qty"])))
            qty = min(qty, int(product["stockQty"]))
            eff = effective_price(product)
            orig = int(product["sellingPricePaise"])
            line_total = eff * qty
            subtotal += orig * qty
            total += line_total
            dead = is_dead_stock(product, now) or is_near_expiry(product, now)
            if dead:
                rescued += line_total
            items.append(
                {
                    "productId": product["id"],
                    "sku": product["sku"],
                    "name": product["name"],
                    "unit": product["unit"],
                    "qty": qty,
                    "unitPricePaise": eff,
                    "originalPricePaise": orig,
                    "costPaise": int(product["costPaise"]),
                    "isDeadStockRescued": dead,
                    "lineTotalPaise": line_total,
                }
            )
            remaining = max(0, int(product["stockQty"]) - qty)
            pending_updates.append(
                {
                    "product": product,
                    "remaining": remaining,
                    "qty": qty,
                    "price": eff,
                    "clear_discount": remaining == 0,
                }
            )

        if not items:
            raise StoreError("EMPTY_SALE", "Cannot complete empty sale")

        customer_id = payload.get("customerId")
        customer_name = "Walk-in Customer"
        customer_update: dict | None = None
        if payload["paymentMethod"] == "udhaar":
            if not customer_id:
                raise StoreError("CUSTOMER_REQUIRED", "Select a valid customer account for Udhaar billing.")
            customer = self.db.get("customers", customer_id)
            if customer is None:
                raise StoreError("CUSTOMER_NOT_FOUND", "Select a valid customer account for Udhaar billing.", 404)
            customer["duePaise"] = int(customer["duePaise"]) + total
            customer["lastTransactionAt"] = now_iso
            customer_update = customer
            customer_name = customer["name"]
        elif customer_id:
            customer = self.db.get("customers", customer_id)
            if customer:
                customer_name = customer["name"]
            else:
                customer_id = None

        upi_ref = payload.get("upiTransactionRef")
        confirmed = self._confirmed_refs()
        if upi_ref and upi_ref in confirmed:
            raise StoreError("DUPLICATE_UPI_REF", "This UPI transaction reference has already been confirmed.", 409)

        # ---- all validation passed: apply mutations atomically -----------
        for update in pending_updates:
            product = update["product"]
            product["stockQty"] = update["remaining"]
            if float(product["avgDailySales"]) <= 0:
                product["avgDailySales"] = round(max(0.2, update["qty"] / 7), 2)
            product["lastSoldAt"] = now_iso
            if update["clear_discount"]:
                product["counterDiscountPricePaise"] = None
            self.db.put("products", product["id"], product, now_iso)
            self._add_history(product, update["qty"], update["price"] / 100.0, now)
        if customer_update is not None:
            self.db.put("customers", customer_id, customer_update, now_iso)
        if upi_ref:
            confirmed.append(upi_ref)
            self.db.set_meta("confirmed_refs", json.dumps(confirmed))

        seq = int(self.db.get_meta("invoice_seq", "1000"))
        sale = {
            "id": f"sale-{uuid.uuid4().hex[:12]}",
            "invoiceNo": f"TRX-{seq}",
            "createdAt": now_iso,
            "items": items,
            "subtotalPaise": subtotal,
            "discountSavedPaise": max(0, subtotal - total),
            "totalPaise": total,
            "paymentMethod": payload["paymentMethod"],
            "customerId": customer_id,
            "customerName": customer_name,
            "rescuedDeadStockPaise": rescued,
            "upiTransactionRef": upi_ref,
            "upiUtrNumber": (payload.get("upiUtrNumber") or "").strip() or None,
            "upiIdUsed": (payload.get("upiIdUsed") or "").strip() or None,
            "paymentStatus": payload.get("paymentStatus") or "confirmed",
            "isDemoPayment": payload.get("isDemoPayment", payload["paymentMethod"] == "upi"),
        }
        self.db.put("sales", sale["id"], sale, now_iso)
        self.db.set_meta("invoice_seq", str(seq + 1))
        return sale

    def _add_history(self, product: dict, qty: int, price: float, when: dt.datetime) -> None:
        self.db.add_history_rows(
            [(product["id"], when.date().isoformat(), float(qty), price, f"TRX-{uuid.uuid4().hex[:8]}")]
        )

    def _confirmed_refs(self) -> list[str]:
        raw = self.db.get_meta("confirmed_refs", "[]") or "[]"
        try:
            value = json.loads(raw)
            return [str(v) for v in value] if isinstance(value, list) else []
        except json.JSONDecodeError:
            return []

    # ------------------------------------------------------------- inventory
    def adjust_stock(self, product_id: str, delta: int) -> dict:
        product = self._product(product_id)
        product["stockQty"] = max(0, int(product["stockQty"]) + int(round(delta)))
        self.db.put("products", product_id, product, product.get("lastSoldAt") or _iso())
        return product

    def return_to_supplier(self, product_id: str, qty: int, reason: str) -> dict:
        product = self._product(product_id)
        qty = min(max(1, int(round(qty))), int(product["stockQty"]))
        if qty <= 0:
            raise StoreError("NO_STOCK", "No stock available to return")
        supplier = self.db.get("suppliers", product["supplierId"])
        now_iso = _iso()
        item = {
            "id": f"ret-{uuid.uuid4().hex[:12]}",
            "productId": product["id"],
            "productName": product["name"],
            "sku": product["sku"],
            "supplierId": product["supplierId"],
            "supplierName": supplier["name"] if supplier else "Assigned Distributor",
            "qty": qty,
            "unitCostPaise": int(product["costPaise"]),
            "totalCreditPaise": qty * int(product["costPaise"]),
            "reason": reason,
            "createdAt": now_iso,
            "slipGeneratedAt": None,
        }
        product["stockQty"] = max(0, int(product["stockQty"]) - qty)
        self.db.put("products", product_id, product, product.get("lastSoldAt") or _iso())
        self.db.put("supplier_returns", item["id"], item, now_iso)
        return {"product": product, "returnItem": item}

    # ------------------------------------------------------------- suppliers
    def list_suppliers(self) -> list[dict]:
        return self.db.all("suppliers")

    def list_returns(self) -> list[dict]:
        return self.db.all("supplier_returns")

    def mark_return_slips(self, return_ids: list[str]) -> list[dict]:
        now_iso = _iso()
        wanted = set(return_ids)
        for item in self.db.all("supplier_returns"):
            if item["id"] in wanted:
                item["slipGeneratedAt"] = now_iso
                self.db.put("supplier_returns", item["id"], item, item.get("createdAt", now_iso))
        return self.list_returns()

    def clear_returned_item(self, return_id: str) -> None:
        if not self.db.delete("supplier_returns", return_id):
            raise StoreError("RETURN_NOT_FOUND", "Supplier return not found", 404)

    # ------------------------------------------------------------- customers
    def list_customers(self) -> list[dict]:
        return self.db.all("customers")

    def list_payments(self) -> list[dict]:
        return self.db.all("customer_payments")

    def create_customer(self, payload: dict) -> dict:
        now_iso = _iso()
        customer = {
            "id": f"cust-{uuid.uuid4().hex[:12]}",
            "name": payload["name"].strip(),
            "phone": payload["phone"].strip(),
            "address": (payload.get("address") or "").strip() or "Local Area",
            "duePaise": max(0, int(payload.get("openingDuePaise") or 0)),
            "lastTransactionAt": now_iso,
        }
        self.db.put("customers", customer["id"], customer, now_iso)
        return customer

    def record_partial_payment(self, customer_id: str, amount_paise: int, meta: dict | None) -> dict:
        customer = self.db.get("customers", customer_id)
        if customer is None:
            raise StoreError("CUSTOMER_NOT_FOUND", "Customer not found", 404)
        paid = int(amount_paise)
        if paid <= 0:
            raise StoreError("INVALID_AMOUNT", "Repayment amount must be greater than ₹0.")
        if paid > int(customer["duePaise"]):
            raise StoreError("AMOUNT_EXCEEDS_DUE", "Repayment amount cannot exceed the outstanding Udhaar balance.")
        meta = meta or {}
        method = meta.get("paymentMethod") or "cash"
        tx_ref = (meta.get("transactionRef") or "").strip() or f"UDHAAR-{uuid.uuid4().hex[:10].upper()}"
        confirmed = self._confirmed_refs()
        if tx_ref in confirmed:
            raise StoreError("DUPLICATE_PAYMENT_REF", "This payment reference has already been confirmed.", 409)
        now_iso = _iso()
        previous = int(customer["duePaise"])
        remaining = max(0, previous - paid)
        customer["duePaise"] = remaining
        customer["lastTransactionAt"] = now_iso
        self.db.put("customers", customer_id, customer, now_iso)
        payment = {
            "id": f"pay-{uuid.uuid4().hex[:12]}",
            "customerId": customer["id"],
            "customerName": customer["name"],
            "amountPaise": paid,
            "previousDuePaise": previous,
            "remainingDuePaise": remaining,
            "paymentMethod": method,
            "status": "confirmed",
            "transactionRef": tx_ref,
            "utrNumber": (meta.get("utrNumber") or "").strip() or None,
            "upiIdUsed": (meta.get("upiIdUsed") or "").strip() or None,
            "isDemo": meta.get("isDemo", True),
            "createdAt": now_iso,
        }
        confirmed.append(tx_ref)
        self.db.set_meta("confirmed_refs", json.dumps(confirmed))
        self.db.put("customer_payments", payment["id"], payment, now_iso)
        return {"customer": customer, "payment": payment}

    def record_payment_attempt(self, customer_id: str, amount_paise: int, meta: dict) -> dict:
        customer = self.db.get("customers", customer_id)
        if customer is None:
            raise StoreError("CUSTOMER_NOT_FOUND", "Customer not found", 404)
        status = meta.get("status") if meta.get("status") in ("failed", "cancelled") else "cancelled"
        payment = {
            "id": f"pay-att-{uuid.uuid4().hex[:12]}",
            "customerId": customer["id"],
            "customerName": customer["name"],
            "amountPaise": max(0, int(amount_paise)),
            "previousDuePaise": int(customer["duePaise"]),
            "remainingDuePaise": int(customer["duePaise"]),
            "paymentMethod": meta.get("paymentMethod") or "cash",
            "status": status,
            "transactionRef": (meta.get("transactionRef") or "").strip() or f"UDHAAR-{uuid.uuid4().hex[:10].upper()}",
            "upiIdUsed": (meta.get("upiIdUsed") or "").strip() or None,
            "isDemo": meta.get("isDemo", True),
            "createdAt": _iso(),
        }
        self.db.put("customer_payments", payment["id"], payment, payment["createdAt"])
        return payment

    # -------------------------------------------------------------- forecast
    def forecast(self, horizon: str) -> list[dict]:
        if horizon not in HORIZON:
            raise StoreError("INVALID_HORIZON", f"horizon must be one of {sorted(HORIZON)}")
        days, seasonal = HORIZON[horizon]
        suppliers = {s["id"]: s for s in self.db.all("suppliers")}
        rows = []
        for p in self.db.all("products"):
            supplier = suppliers.get(p["supplierId"])
            has_history = float(p["avgDailySales"]) > 0
            demand = max(0, round(float(p["avgDailySales"]) * days * seasonal)) if has_history else 0
            buffer = math.ceil(float(p["avgDailySales"]) * int((supplier or {}).get("leadTimeDays", 2))) if has_history else 0
            if p["stopReordering"]:
                order_qty = 0
            elif has_history:
                order_qty = max(0, demand + buffer - int(p["stockQty"]))
            elif int(p["stockQty"]) <= int(p["reorderLevel"]):
                order_qty = max(0, max(int(p["reorderLevel"]) * 2, 10) - int(p["stockQty"]))
            else:
                order_qty = 0
            lost = (
                round(float(p["avgDailySales"]) * min(days, 14)) * int(p["sellingPricePaise"])
                if is_stockout_fast_mover(p)
                else 0
            )
            cover = (
                0.0
                if int(p["stockQty"]) == 0
                else round(int(p["stockQty"]) / float(p["avgDailySales"]), 1)
                if has_history
                else 999.0
            )
            if p["stopReordering"]:
                status = "Stopped"
            elif int(p["stockQty"]) == 0:
                status = "Out of Stock"
            elif int(p["stockQty"]) <= int(p["reorderLevel"]):
                status = "Low Stock"
            else:
                status = "Healthy"
            rows.append(
                {
                    "productId": p["id"],
                    "sku": p["sku"],
                    "name": p["name"],
                    "category": p["category"],
                    "supplierId": p["supplierId"],
                    "supplierName": supplier["name"] if supplier else "Assigned Distributor",
                    "currentStock": int(p["stockQty"]),
                    "avgDailySales": float(p["avgDailySales"]),
                    "forecastedDemand": demand,
                    "recommendedOrderQty": order_qty,
                    "estimatedOrderCostPaise": order_qty * int(p["costPaise"]),
                    "estimatedLostSalesPaise": lost,
                    "daysOfCover": cover,
                    "status": status,
                    "stopReordering": bool(p["stopReordering"]),
                }
            )
        priority = {"Out of Stock": 0, "Low Stock": 1, "Healthy": 2, "Stopped": 3}
        rows.sort(key=lambda r: (priority[r["status"]], -r["recommendedOrderQty"]))
        return rows

    def list_purchase_orders(self) -> list[dict]:
        return self.db.all("purchase_orders")

    def create_purchase_order(self, items: list[dict]) -> dict:
        cleaned = [
            {
                **i,
                "qty": int(round(i["qty"])),
                "lineTotalPaise": int(round(i["qty"])) * int(i["unitCostPaise"]),
            }
            for i in items
            if int(round(i["qty"])) > 0
        ]
        if not cleaned:
            raise StoreError("EMPTY_PO", "PO cannot be empty")
        now = _now()
        seq = int(self.db.get_meta("po_seq", "1"))
        po = {
            "id": f"po-{uuid.uuid4().hex[:12]}",
            "poNumber": f"PO-{now.year}-{seq:03d}",
            "createdAt": _iso(now),
            "status": "Ordered",
            "items": cleaned,
            "totalPaise": sum(i["lineTotalPaise"] for i in cleaned),
        }
        self.db.put("purchase_orders", po["id"], po, po["createdAt"])
        self.db.set_meta("po_seq", str(seq + 1))
        return po

    # --------------------------------------------------------------- reports
    def sales_summary(self) -> dict:
        sales = self.db.all("sales")
        today = _now().astimezone().date()
        cash = upi = udhaar = total = rescued = today_rev = 0
        today_bills = 0
        agg: dict[str, dict] = {}
        daily: dict[str, dict] = {
            (today - dt.timedelta(days=i)).isoformat(): {"revenue": 0, "rescued": 0} for i in range(7)
        }
        for sale in sales:
            amount = int(sale["totalPaise"])
            total += amount
            rescued += int(sale["rescuedDeadStockPaise"])
            if sale["paymentMethod"] == "cash":
                cash += amount
            elif sale["paymentMethod"] == "upi":
                upi += amount
            elif sale["paymentMethod"] == "udhaar":
                udhaar += amount
            created = _parse(sale["createdAt"]).astimezone()
            if created.date() == today:
                today_rev += amount
                today_bills += 1
            key = created.date().isoformat()
            if key in daily:
                daily[key]["revenue"] += amount
                daily[key]["rescued"] += int(sale["rescuedDeadStockPaise"])
            for line in sale["items"]:
                item = agg.setdefault(
                    line["productId"], {"name": line["name"], "qtySold": 0, "revenuePaise": 0}
                )
                item["qtySold"] += int(line["qty"])
                item["revenuePaise"] += int(line["lineTotalPaise"])
        series = []
        for offset in range(6, -1, -1):
            day = today - dt.timedelta(days=offset)
            data = daily[day.isoformat()]
            series.append(
                {
                    "label": day.strftime("%d %b"),
                    "revenueRupees": round(data["revenue"] / 100),
                    "rescuedRupees": round(data["rescued"] / 100),
                }
            )
        top = sorted(
            ({"productId": pid, **data} for pid, data in agg.items()),
            key=lambda x: -x["revenuePaise"],
        )[:6]
        return {
            "todayRevenuePaise": today_rev,
            "todayBillsCount": today_bills,
            "totalRevenuePaise": total,
            "cashRevenuePaise": cash,
            "upiRevenuePaise": upi,
            "udhaarRevenuePaise": udhaar,
            "totalRescuedCashPaise": rescued,
            "dailySeries": series,
            "topProducts": top,
        }

    def reset_demo_data(self) -> None:
        self.db.reset_domain()
        self.ensure_seed()

    # ------------------------------------------------------------------- ML
    def ml_product_catalog(self) -> list[dict]:
        """Products enriched with the sales history required by the ML layer."""
        history = self.db.history_for()
        today = _now().date().isoformat()
        out = []
        for p in self.db.all("products"):
            out.append(
                {
                    "product_id": p["sku"],
                    "product_name": p["name"],
                    "sales_history": history.get(p["id"], []),
                    "as_of": today,
                    "description": p["name"],
                    "on_hand_qty": p["stockQty"],
                    "unit_cost": p["costPaise"] / 100.0,
                    "lead_time_days": 2,
                }
            )
        return out
