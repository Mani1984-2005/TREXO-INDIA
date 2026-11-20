import { beforeEach, describe, expect, it } from 'vitest';
import { STORAGE_KEYS } from '../config';
import { createMockServices } from './mockServices';

class MemoryStorage implements Storage {
  private map = new Map<string, string>();
  get length() {
    return this.map.size;
  }
  clear() {
    this.map.clear();
  }
  getItem(key: string) {
    return this.map.has(key) ? this.map.get(key)! : null;
  }
  key(index: number) {
    return Array.from(this.map.keys())[index] ?? null;
  }
  removeItem(key: string) {
    this.map.delete(key);
  }
  setItem(key: string, value: string) {
    this.map.set(key, value);
  }
}

describe('Mock Services — Counter UPI & Udhaar Repayment Safeguards', () => {
  beforeEach(() => {
    Object.defineProperty(globalThis, 'localStorage', {
      value: new MemoryStorage(),
      configurable: true,
    });
  });

  it('completes cash and UPI counter bills and blocks duplicate UPI transaction references', async () => {
    const svc = createMockServices();
    const productsBefore = await svc.products.getAll();
    const atta = productsBefore.find((p) => p.id === 'prod-1')!;
    const startStock = atta.stockQty;

    // 1. Cash bill still works
    const cashSale = await svc.billing.completeSale({
      items: [{ productId: atta.id, qty: 1 }],
      paymentMethod: 'cash',
    });
    expect(cashSale.paymentMethod).toBe('cash');
    expect(cashSale.totalPaise).toBe(atta.sellingPricePaise);

    // 2. UPI bill persists UPI metadata
    const upiRef = 'TRX-BILL-20261119-TEST01';
    const upiSale = await svc.billing.completeSale({
      items: [{ productId: atta.id, qty: 1 }],
      paymentMethod: 'upi',
      upiTransactionRef: upiRef,
      upiUtrNumber: '432198765432',
      upiIdUsed: 'owner@okaxis',
      paymentStatus: 'confirmed',
      isDemoPayment: true,
    });
    expect(upiSale.paymentMethod).toBe('upi');
    expect(upiSale.upiTransactionRef).toBe(upiRef);
    expect(upiSale.upiUtrNumber).toBe('432198765432');
    expect(upiSale.isDemoPayment).toBe(true);

    // 3. Duplicate confirmation with same UPI reference must fail
    await expect(
      svc.billing.completeSale({
        items: [{ productId: atta.id, qty: 1 }],
        paymentMethod: 'upi',
        upiTransactionRef: upiRef,
      })
    ).rejects.toThrow(/already been confirmed/i);

    const productsAfter = await svc.products.getAll();
    const attaAfter = productsAfter.find((p) => p.id === 'prod-1')!;
    expect(attaAfter.stockQty).toBe(startStock - 2);
  });

  it('records Udhaar UPI repayment accurately, preserves history, blocks overpayment and duplicate confirmation', async () => {
    const svc = createMockServices();
    const customersBefore = await svc.customers.getAll();
    const ramesh = customersBefore.find((c) => c.id === 'cust-1')!;
    const initialDue = ramesh.duePaise; // 145000 (₹1,450)
    const initialHistory = (await svc.customers.getPayments()).filter(
      (p) => p.customerId === ramesh.id
    );

    // Reject overpayment greater than outstanding balance
    await expect(
      svc.customers.recordPartialPayment(ramesh.id, initialDue + 100, {
        paymentMethod: 'upi',
        transactionRef: 'TRX-UDHAAR-OVERPAY',
      })
    ).rejects.toThrow(/cannot exceed/i);

    // Failed/cancelled attempt must NOT deduct balance
    await svc.customers.recordPaymentAttempt(ramesh.id, 50000, {
      paymentMethod: 'upi',
      status: 'failed',
      transactionRef: 'TRX-UDHAAR-FAILED-1',
      upiIdUsed: 'owner@oksbi',
      isDemo: true,
    });
    const afterFailed = (await svc.customers.getAll()).find((c) => c.id === ramesh.id)!;
    expect(afterFailed.duePaise).toBe(initialDue);

    // Confirmed UPI repayment deducts balance and preserves prior history
    const ref = 'TRX-UDHAAR-CONFIRMED-1';
    const { customer, payment } = await svc.customers.recordPartialPayment(ramesh.id, 45000, {
      paymentMethod: 'upi',
      transactionRef: ref,
      upiIdUsed: 'owner@oksbi',
      utrNumber: '112233445566',
      isDemo: true,
    });

    expect(customer.duePaise).toBe(initialDue - 45000);
    expect(payment.paymentMethod).toBe('upi');
    expect(payment.transactionRef).toBe(ref);
    expect(payment.remainingDuePaise).toBe(initialDue - 45000);

    // Duplicate confirmation with the same reference must be blocked
    await expect(
      svc.customers.recordPartialPayment(ramesh.id, 45000, {
        paymentMethod: 'upi',
        transactionRef: ref,
      })
    ).rejects.toThrow(/already been confirmed/i);

    const historyAfter = (await svc.customers.getPayments()).filter(
      (p) => p.customerId === ramesh.id
    );
    expect(historyAfter.length).toBe(initialHistory.length + 2);
  });

  it('rejects out-of-stock billing, clamps over-stock quantities, and enforces Udhaar customer account', async () => {
    const svc = createMockServices();
    const products = await svc.products.getAll();
    const outOfStockProd = products.find((p) => p.stockQty === 0)!;
    expect(outOfStockProd).toBeDefined();

    // Out-of-stock item must be rejected
    await expect(
      svc.billing.completeSale({
        items: [{ productId: outOfStockProd.id, qty: 1 }],
        paymentMethod: 'cash',
      })
    ).rejects.toThrow(/out of stock/i);

    // Udhaar sale without valid customer must be rejected
    const inStock = products.find((p) => p.stockQty >= 2)!;
    await expect(
      svc.billing.completeSale({
        items: [{ productId: inStock.id, qty: 1 }],
        paymentMethod: 'udhaar',
        customerId: null,
      })
    ).rejects.toThrow(/valid customer account/i);

    // Quantity exceeding available stock is clamped to exact stockQty
    const initialQty = inStock.stockQty;
    const clampedSale = await svc.billing.completeSale({
      items: [{ productId: inStock.id, qty: initialQty + 50 }],
      paymentMethod: 'cash',
    });
    expect(clampedSale.items[0].qty).toBe(initialQty);
    const updated = (await svc.products.getAll()).find((p) => p.id === inStock.id)!;
    expect(updated.stockQty).toBe(0);
  });

  it('rejects zero/negative repayments and payments on settled ₹0 customer accounts', async () => {
    const svc = createMockServices();
    const settled = await svc.customers.create({
      name: 'Settled Customer',
      phone: '+91 98450 11111',
      address: 'Hubballi',
      openingDuePaise: 0,
    });

    await expect(
      svc.customers.recordPartialPayment(settled.id, 0, { paymentMethod: 'cash' })
    ).rejects.toThrow(/greater than/i);

    await expect(
      svc.customers.recordPartialPayment(settled.id, -500, { paymentMethod: 'cash' })
    ).rejects.toThrow(/greater than/i);

    await expect(
      svc.customers.recordPartialPayment(settled.id, 100, { paymentMethod: 'upi' })
    ).rejects.toThrow(/cannot exceed/i);
  });

  it('recovers cleanly from corrupted localStorage JSON and malformed array snapshots', async () => {
    // 1. Completely broken JSON
    localStorage.setItem(STORAGE_KEYS.STATE_V1, '{not-valid-json');
    const svc = createMockServices();
    const recoveredProducts = await svc.products.getAll();
    expect(recoveredProducts.length).toBeGreaterThan(0);
    // Persisted storage should now be valid JSON
    expect(() => JSON.parse(localStorage.getItem(STORAGE_KEYS.STATE_V1)!)).not.toThrow();

    // 2. Malformed objects inside products array
    localStorage.setItem(
      STORAGE_KEYS.STATE_V1,
      JSON.stringify({ products: [null, { broken: true }], suppliers: [] })
    );
    const recoveredAgain = await svc.products.getAll();
    expect(recoveredAgain.length).toBeGreaterThan(0);

    // 3. Valid empty store inventory & customers still work cleanly in forecast and reports
    localStorage.setItem(
      STORAGE_KEYS.STATE_V1,
      JSON.stringify({
        products: [],
        sales: [],
        customers: [],
        customerPayments: [],
        confirmedRefs: [],
        suppliers: [],
        supplierReturns: [],
        purchaseOrders: [],
        invoiceSeq: 1001,
        poSeq: 1,
      })
    );
    const emptyForecast = await svc.forecast.getForecast('1M');
    const emptySummary = await svc.reports.getSalesSummary();
    expect(emptyForecast).toEqual([]);
    expect(emptySummary.totalRevenuePaise).toBe(0);
    expect(emptySummary.todayBillsCount).toBe(0);
  });

  it('edits product details and prevents misleading demand forecasts on new products without sales history', async () => {
    const svc = createMockServices();
    const created = await svc.products.create({
      name: 'Mysore Sandal Soap Pack',
      sku: 'HPC-901',
      category: 'Home & Personal',
      unit: '3x125g',
      mrpPaise: 24000,
      costPaise: 19000,
      sellingPricePaise: 23000,
      stockQty: 20,
      reorderLevel: 5,
      expiryDate: null,
      supplierId: 'sup-1',
    });

    expect(created.avgDailySales).toBe(0);

    const forecastBefore = await svc.forecast.getForecast('1M');
    const rowHealthy = forecastBefore.find((r) => r.productId === created.id)!;
    expect(rowHealthy.forecastedDemand).toBe(0);
    expect(rowHealthy.recommendedOrderQty).toBe(0);
    expect(rowHealthy.estimatedLostSalesPaise).toBe(0);
    expect(rowHealthy.status).toBe('Healthy');

    const updated = await svc.products.update(created.id, {
      name: 'Mysore Sandal Soap Family Pack',
      sellingPricePaise: 22500,
      stockQty: 3,
      reorderLevel: 6,
    });
    expect(updated.name).toBe('Mysore Sandal Soap Family Pack');
    expect(updated.sellingPricePaise).toBe(22500);
    expect(updated.stockQty).toBe(3);

    const forecastLow = await svc.forecast.getForecast('1M');
    const rowLow = forecastLow.find((r) => r.productId === created.id)!;
    expect(rowLow.forecastedDemand).toBe(0);
    expect(rowLow.status).toBe('Low Stock');
    expect(rowLow.recommendedOrderQty).toBeGreaterThan(0);
  });

  it('keeps counter revenue split exact and never double-counts Udhaar repayments into counter sales', async () => {
    const svc = createMockServices();
    const summaryBefore = await svc.reports.getSalesSummary();
    const products = await svc.products.getAll();
    const item = products.find((p) => p.stockQty >= 2)!;
    const customers = await svc.customers.getAll();
    const customer = customers[0];

    const udhaarSale = await svc.billing.completeSale({
      items: [{ productId: item.id, qty: 1 }],
      paymentMethod: 'udhaar',
      customerId: customer.id,
    });

    await svc.customers.recordPartialPayment(customer.id, udhaarSale.totalPaise, {
      paymentMethod: 'cash',
      transactionRef: 'TRX-UDHAAR-CASH-CHECK',
    });

    const summaryAfter = await svc.reports.getSalesSummary();
    expect(summaryAfter.totalRevenuePaise).toBe(
      summaryBefore.totalRevenuePaise + udhaarSale.totalPaise
    );
    expect(summaryAfter.udhaarRevenuePaise).toBe(
      summaryBefore.udhaarRevenuePaise + udhaarSale.totalPaise
    );
    expect(summaryAfter.cashRevenuePaise).toBe(summaryBefore.cashRevenuePaise);
    expect(
      summaryAfter.cashRevenuePaise +
        summaryAfter.upiRevenuePaise +
        summaryAfter.udhaarRevenuePaise
    ).toBe(summaryAfter.totalRevenuePaise);
  });
});

