from __future__ import annotations

import uuid


def test_products_shape(products):
    assert len(products) == 16
    first = products[0]
    for key in (
        "id",
        "sku",
        "name",
        "category",
        "mrpPaise",
        "costPaise",
        "sellingPricePaise",
        "stockQty",
        "avgDailySales",
        "supplierId",
        "stopReordering",
    ):
        assert key in first


def test_forecast_contract(client, auth):
    resp = client.get("/api/v1/store/forecast?horizon=1M", headers=auth)
    assert resp.status_code == 200
    rows = resp.json()
    assert rows
    for key in ("recommendedOrderQty", "forecastedDemand", "daysOfCover", "status"):
        assert key in rows[0]
    statuses = {r["status"] for r in rows}
    assert statuses <= {"Out of Stock", "Low Stock", "Healthy", "Stopped"}
    assert client.get("/api/v1/store/forecast?horizon=9Y", headers=auth).status_code == 422


def test_sales_summary_totals(client, auth):
    sales = client.get("/api/v1/store/sales", headers=auth).json()
    summary = client.get("/api/v1/store/reports/sales-summary", headers=auth).json()
    assert summary["totalRevenuePaise"] == sum(s["totalPaise"] for s in sales)
    assert len(summary["dailySeries"]) == 7


def test_sale_flow_updates_stock_and_customer(client, auth, products):
    product = products[0]
    token = uuid.uuid4().hex
    payload = {
        "items": [{"productId": product["id"], "qty": 2}],
        "paymentMethod": "upi",
        "upiTransactionRef": f"TEST-{token}",
        "paymentStatus": "confirmed",
    }
    resp = client.post("/api/v1/store/sales", json=payload, headers=auth)
    assert resp.status_code == 201, resp.text
    sale = resp.json()
    assert sale["invoiceNo"].startswith("TRX-")
    assert sale["totalPaise"] == sale["items"][0]["unitPricePaise"] * 2
    assert sale["discountSavedPaise"] >= 0

    updated = next(p for p in client.get("/api/v1/store/products", headers=auth).json() if p["id"] == product["id"])
    assert updated["stockQty"] == product["stockQty"] - 2

    dup = client.post(
        "/api/v1/store/sales",
        json={**payload, "items": [{"productId": product["id"], "qty": 1}]},
        headers=auth,
    )
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "DUPLICATE_UPI_REF"


def test_sale_clamps_to_available_stock(client, auth):
    product = next(p for p in client.get("/api/v1/store/products", headers=auth).json() if p["stockQty"] > 0)
    resp = client.post(
        "/api/v1/store/sales",
        json={"items": [{"productId": product["id"], "qty": 999}], "paymentMethod": "cash"},
        headers=auth,
    )
    assert resp.status_code == 201
    assert resp.json()["items"][0]["qty"] == product["stockQty"]


def test_sale_validation_errors(client, auth):
    bad_method = client.post(
        "/api/v1/store/sales",
        json={"items": [{"productId": "prod-x", "qty": 1}], "paymentMethod": "bitcoin"},
        headers=auth,
    )
    assert bad_method.status_code == 422
    empty = client.post(
        "/api/v1/store/sales", json={"items": [], "paymentMethod": "cash"}, headers=auth
    )
    assert empty.status_code == 422
    unknown = client.post(
        "/api/v1/store/sales",
        json={"items": [{"productId": "does-not-exist", "qty": 1}], "paymentMethod": "cash"},
        headers=auth,
    )
    assert unknown.status_code == 404
    udhaar = client.post(
        "/api/v1/store/sales",
        json={"items": [{"productId": "prod-1", "qty": 1}], "paymentMethod": "udhaar"},
        headers=auth,
    )
    assert udhaar.status_code == 400
    assert udhaar.json()["error"]["code"] == "CUSTOMER_REQUIRED"


def test_udhaar_requires_existing_customer(client, auth, products):
    created = client.post(
        "/api/v1/store/products",
        json={
            "name": "Udhaar Test Item",
            "sku": "UDH-1",
            "category": "Snacks & Beverages",
            "unit": "1 unit",
            "mrpPaise": 5000,
            "costPaise": 3000,
            "sellingPricePaise": 4500,
            "stockQty": 5,
            "reorderLevel": 1,
            "expiryDate": None,
            "supplierId": products[0]["supplierId"],
        },
        headers=auth,
    )
    product = created.json()
    resp = client.post(
        "/api/v1/store/sales",
        json={
            "items": [{"productId": product["id"], "qty": 1}],
            "paymentMethod": "udhaar",
            "customerId": "cust-does-not-exist",
        },
        headers=auth,
    )
    assert resp.status_code == 404
    # Failed sale must not have mutated stock (atomicity).
    unchanged = next(
        p for p in client.get("/api/v1/store/products", headers=auth).json() if p["id"] == product["id"]
    )
    assert unchanged["stockQty"] == 5


def test_stock_adjustment(client, auth):
    product = client.get("/api/v1/store/products", headers=auth).json()[0]
    before = product["stockQty"]
    resp = client.post(
        f"/api/v1/store/products/{product['id']}/stock", json={"deltaQty": 5}, headers=auth
    )
    assert resp.status_code == 200 and resp.json()["stockQty"] == before + 5
    zero = client.post(
        f"/api/v1/store/products/{product['id']}/stock", json={"deltaQty": 0}, headers=auth
    )
    assert zero.status_code == 422
    missing = client.post("/api/v1/store/products/nope/stock", json={"deltaQty": 1}, headers=auth)
    assert missing.status_code == 404


def test_product_create_update_and_discount(client, auth, products):
    supplier_id = products[0]["supplierId"]
    created = client.post(
        "/api/v1/store/products",
        json={
            "name": "Test Rice 1kg",
            "sku": "tst-1",
            "category": "Grains & Atta",
            "unit": "1 kg",
            "mrpPaise": 10000,
            "costPaise": 8000,
            "sellingPricePaise": 9500,
            "stockQty": 10,
            "reorderLevel": 3,
            "expiryDate": None,
            "supplierId": supplier_id,
        },
        headers=auth,
    )
    assert created.status_code == 201, created.text
    product = created.json()
    assert product["sku"] == "TST-1"

    patched = client.patch(
        f"/api/v1/store/products/{product['id']}", json={"stockQty": 4}, headers=auth
    )
    assert patched.status_code == 200 and patched.json()["stockQty"] == 4

    discount = client.post(
        f"/api/v1/store/products/{product['id']}/counter-discount",
        json={"pricePaise": 9000},
        headers=auth,
    )
    assert discount.status_code == 200 and discount.json()["counterDiscountPricePaise"] == 9000

    invalid_discount = client.post(
        f"/api/v1/store/products/{product['id']}/counter-discount",
        json={"pricePaise": 99999},
        headers=auth,
    )
    assert invalid_discount.status_code == 200
    assert invalid_discount.json()["counterDiscountPricePaise"] is None

    stopped = client.post(
        f"/api/v1/store/products/{product['id']}/stop-reordering",
        json={"stop": True},
        headers=auth,
    )
    assert stopped.json()["stopReordering"] is True


def test_supplier_return_and_clear(client, auth):
    product = next(p for p in client.get("/api/v1/store/products", headers=auth).json() if p["stockQty"] > 1)
    resp = client.post(
        "/api/v1/store/supplier-returns",
        json={"productId": product["id"], "qty": 1, "reason": "Near expiry"},
        headers=auth,
    )
    assert resp.status_code == 201, resp.text
    item = resp.json()["returnItem"]
    assert item["totalCreditPaise"] == product["costPaise"]

    marked = client.post(
        "/api/v1/store/supplier-returns/mark-slips",
        json={"returnIds": [item["id"]]},
        headers=auth,
    )
    assert marked.status_code == 200
    assert next(r for r in marked.json() if r["id"] == item["id"])["slipGeneratedAt"]

    assert client.delete(f"/api/v1/store/supplier-returns/{item['id']}", headers=auth).status_code == 204
    assert client.delete("/api/v1/store/supplier-returns/nope", headers=auth).status_code == 404


def test_customer_payments(client, auth):
    created = client.post(
        "/api/v1/store/customers",
        json={"name": "Test Customer", "phone": "9000000000", "address": "Test", "openingDuePaise": 5000},
        headers=auth,
    )
    assert created.status_code == 201
    customer = created.json()

    over = client.post(
        f"/api/v1/store/customers/{customer['id']}/payments",
        json={"amountPaise": 6000},
        headers=auth,
    )
    assert over.status_code == 400 and over.json()["error"]["code"] == "AMOUNT_EXCEEDS_DUE"

    paid = client.post(
        f"/api/v1/store/customers/{customer['id']}/payments",
        json={"amountPaise": 2000, "meta": {"paymentMethod": "cash"}},
        headers=auth,
    )
    assert paid.status_code == 200, paid.text
    body = paid.json()
    assert body["payment"]["remainingDuePaise"] == 3000
    assert body["customer"]["duePaise"] == 3000

    attempt = client.post(
        f"/api/v1/store/customers/{customer['id']}/payment-attempts",
        json={"amountPaise": 1000, "meta": {"paymentMethod": "upi", "status": "failed"}},
        headers=auth,
    )
    assert attempt.status_code == 200
    assert attempt.json()["remainingDuePaise"] == 3000


def test_purchase_order_flow(client, auth):
    bad = client.post("/api/v1/store/purchase-orders", json=[], headers=auth)
    assert bad.status_code == 400
    po = client.post(
        "/api/v1/store/purchase-orders",
        json=[
            {
                "productId": "prod-1",
                "sku": "GRN-001",
                "name": "Atta",
                "supplierId": "sup-4",
                "supplierName": "National Grain & Oil Depot",
                "qty": 2,
                "unitCostPaise": 21800,
            }
        ],
        headers=auth,
    )
    assert po.status_code == 201, po.text
    assert po.json()["totalPaise"] == 43600
    assert po.json()["poNumber"].startswith("PO-")


def test_ml_catalog(client, auth):
    resp = client.get("/api/v1/store/ml/catalog", headers=auth)
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 10
    assert all("sales_history" in p for p in body["products"])
