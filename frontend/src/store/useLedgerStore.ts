import { create } from 'zustand';
import { services } from '../services';
import { type AuthResult, authService } from '../services/authService';
import type {
  CartItem,
  Customer,
  CustomerCreateInput,
  CustomerPaymentEntry,
  ForecastHorizon,
  ForecastRow,
  LanguageCode,
  PaymentMethod,
  Product,
  ProductCreateInput,
  PurchaseOrder,
  PurchaseOrderItem,
  RecordPaymentMeta,
  ReturnReason,
  Sale,
  SalesSummary,
  Supplier,
  SupplierReturnItem,
  UpiMerchantConfig,
  UpiPaymentStatus,
} from '../types/domain';
import { loadUpiMerchantConfig, saveUpiMerchantConfig } from '../utils/upi';

export interface CompleteSaleUpiMeta {
  upiTransactionRef?: string;
  upiUtrNumber?: string;
  upiIdUsed?: string;
  paymentStatus?: UpiPaymentStatus;
  isDemoPayment?: boolean;
}

export interface ToastNotice {
  id: string;
  title: string;
  detail?: string;
  tone: 'emerald' | 'amber' | 'slate';
}

interface LedgerState {
  initialized: boolean;
  loading: boolean;
  isAuthenticated: boolean;
  isSaving: boolean;
  lastSavedAt: string | null;
  language: LanguageCode;
  products: Product[];
  sales: Sale[];
  customers: Customer[];
  customerPayments: CustomerPaymentEntry[];
  upiConfig: UpiMerchantConfig;
  suppliers: Supplier[];
  supplierReturns: SupplierReturnItem[];
  purchaseOrders: PurchaseOrder[];
  forecastHorizon: ForecastHorizon;
  forecastRows: ForecastRow[];
  salesSummary: SalesSummary | null;
  cart: CartItem[];
  lastCompletedSale: Sale | null;
  toasts: ToastNotice[];

  init: () => Promise<void>;
  loginOwner: (password: string) => Promise<AuthResult>;
  logoutOwner: () => void;
  markSavedNow: () => void;
  setLanguage: (lang: LanguageCode) => void;
  setUpiConfig: (upiId: string, merchantName?: string) => void;
  pushToast: (title: string, detail?: string, tone?: ToastNotice['tone']) => void;
  dismissToast: (id: string) => void;

  // Cart & Counter Billing
  addToCart: (productId: string, qty?: number) => void;
  updateCartQty: (productId: string, qty: number) => void;
  removeFromCart: (productId: string) => void;
  clearCart: () => void;
  completeSale: (
    paymentMethod: PaymentMethod,
    customerId?: string | null,
    upiMeta?: CompleteSaleUpiMeta
  ) => Promise<Sale | null>;
  clearLastCompletedSale: () => void;

  // Products & Inventory
  createProduct: (input: ProductCreateInput) => Promise<void>;
  updateProduct: (productId: string, patch: Partial<Product>) => Promise<void>;
  adjustStock: (productId: string, deltaQty: number) => Promise<void>;
  setCounterDiscount: (productId: string, pricePaise: number | null) => Promise<void>;
  setStopReordering: (productId: string, stop: boolean) => Promise<void>;

  // Dead-stock supplier returns
  returnToSupplier: (productId: string, qty: number, reason: ReturnReason) => Promise<void>;
  markReturnSlipGenerated: (returnIds: string[]) => Promise<void>;
  clearReturnedItem: (returnId: string) => Promise<void>;

  // Udhaar Customers
  createCustomer: (input: CustomerCreateInput) => Promise<void>;
  recordPartialPayment: (
    customerId: string,
    amountPaise: number,
    meta?: RecordPaymentMeta
  ) => Promise<CustomerPaymentEntry>;
  recordPaymentAttempt: (
    customerId: string,
    amountPaise: number,
    meta: RecordPaymentMeta
  ) => Promise<CustomerPaymentEntry>;

  // Restock & Forecast
  setForecastHorizon: (horizon: ForecastHorizon) => Promise<void>;
  createPurchaseOrder: (items: Omit<PurchaseOrderItem, 'lineTotalPaise'>[]) => Promise<PurchaseOrder>;

  // Reports & Demo Reset
  resetDemoData: () => Promise<void>;
}

function reconcileCartWithProducts(cart: CartItem[], products: Product[]): CartItem[] {
  const byId = new Map(products.map((p) => [p.id, p]));
  return cart
    .map((line) => {
      const prod = byId.get(line.productId);
      if (!prod || prod.stockQty <= 0) return null;
      return {
        productId: line.productId,
        qty: Math.min(line.qty, prod.stockQty),
      };
    })
    .filter((line): line is CartItem => line !== null);
}

export const useLedgerStore = create<LedgerState>((set, get) => ({
  initialized: false,
  loading: false,
  isAuthenticated: authService.isAuthenticated(),
  isSaving: false,
  lastSavedAt: null,
  language: 'en',
  products: [],
  sales: [],
  customers: [],
  customerPayments: [],
  upiConfig: loadUpiMerchantConfig(),
  suppliers: [],
  supplierReturns: [],
  purchaseOrders: [],
  forecastHorizon: '1M',
  forecastRows: [],
  salesSummary: null,
  cart: [],
  lastCompletedSale: null,
  toasts: [],

  init: async () => {
    set({ loading: true });
    const horizon = get().forecastHorizon;
    const [
      products,
      sales,
      customers,
      customerPayments,
      suppliers,
      supplierReturns,
      purchaseOrders,
      forecastRows,
      salesSummary,
    ] = await Promise.all([
      services.products.getAll(),
      services.billing.getSales(),
      services.customers.getAll(),
      services.customers.getPayments(),
      services.suppliers.getAll(),
      services.suppliers.getReturnList(),
      services.forecast.getPurchaseOrders(),
      services.forecast.getForecast(horizon),
      services.reports.getSalesSummary(),
    ]);

    set({
      initialized: true,
      loading: false,
      lastSavedAt: new Date().toISOString(),
      upiConfig: loadUpiMerchantConfig(),
      products,
      sales,
      customers,
      customerPayments,
      suppliers,
      supplierReturns,
      purchaseOrders,
      forecastRows,
      salesSummary,
    });
  },

  loginOwner: async (password) => {
    const result = await authService.verifyOwnerPassword(password);
    if (result.ok) {
      set({ isAuthenticated: true });
      if (!get().initialized) {
        await get().init();
      }
    }
    return result;
  },

  logoutOwner: () => {
    authService.logout();
    set({ isAuthenticated: false, lastCompletedSale: null, toasts: [] });
  },

  markSavedNow: () => set({ lastSavedAt: new Date().toISOString() }),

  setLanguage: (lang) => set({ language: lang }),

  setUpiConfig: (upiId, merchantName) => {
    const current = get().upiConfig;
    const saved = saveUpiMerchantConfig({
      upiId: upiId.trim(),
      merchantName: merchantName?.trim() || current.merchantName,
      updatedAt: new Date().toISOString(),
    });
    set({ upiConfig: saved, lastSavedAt: saved.updatedAt });
    get().pushToast(
      saved.upiId ? 'Store UPI ID saved' : 'Store UPI ID cleared',
      saved.upiId
        ? `QR codes will use ${saved.upiId}`
        : 'Configure a UPI ID before accepting UPI payments.',
      saved.upiId ? 'emerald' : 'slate'
    );
  },

  pushToast: (title, detail, tone = 'emerald') => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    set((s) => ({ toasts: [...s.toasts.slice(-2), { id, title, detail, tone }] }));
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
    }, 4200);
  },

  dismissToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),

  addToCart: (productId, qty = 1) => {
    const product = get().products.find((p) => p.id === productId);
    if (!product) return;
    if (product.stockQty <= 0) {
      get().pushToast('Out of stock', `${product.name} has 0 units on shelf.`, 'amber');
      return;
    }
    set((state) => {
      const existing = state.cart.find((c) => c.productId === productId);
      if (existing) {
        const nextQty = Math.min(product.stockQty, existing.qty + qty);
        return {
          cart: state.cart.map((c) => (c.productId === productId ? { ...c, qty: nextQty } : c)),
        };
      }
      return {
        cart: [...state.cart, { productId, qty: Math.min(product.stockQty, qty) }],
      };
    });
  },

  updateCartQty: (productId, qty) => {
    const product = get().products.find((p) => p.id === productId);
    if (!product) return;
    if (qty <= 0) {
      set((s) => ({ cart: s.cart.filter((c) => c.productId !== productId) }));
      return;
    }
    const clamped = Math.min(product.stockQty, Math.round(qty));
    set((s) => ({
      cart: s.cart.map((c) => (c.productId === productId ? { ...c, qty: clamped } : c)),
    }));
  },

  removeFromCart: (productId) =>
    set((s) => ({ cart: s.cart.filter((c) => c.productId !== productId) })),

  clearCart: () => set({ cart: [] }),

  completeSale: async (paymentMethod, customerId = null, upiMeta) => {
    const { cart, forecastHorizon, isSaving } = get();
    if (cart.length === 0 || isSaving) return null;
    set({ isSaving: true });
    try {
      const sale = await services.billing.completeSale({
        items: cart,
        paymentMethod,
        customerId,
        upiTransactionRef: upiMeta?.upiTransactionRef,
        upiUtrNumber: upiMeta?.upiUtrNumber,
        upiIdUsed: upiMeta?.upiIdUsed,
        paymentStatus: upiMeta?.paymentStatus,
        isDemoPayment: upiMeta?.isDemoPayment,
      });
      const [products, sales, customers, forecastRows, salesSummary] = await Promise.all([
        services.products.getAll(),
        services.billing.getSales(),
        services.customers.getAll(),
        services.forecast.getForecast(forecastHorizon),
        services.reports.getSalesSummary(),
      ]);
      set({
        products,
        sales,
        customers,
        forecastRows,
        salesSummary,
        cart: [],
        lastCompletedSale: sale,
        isSaving: false,
        lastSavedAt: new Date().toISOString(),
      });
      if (sale.rescuedDeadStockPaise > 0) {
        get().pushToast(
          `Bill ${sale.invoiceNo} completed`,
          `Unlocked ₹${Math.round(sale.rescuedDeadStockPaise / 100).toLocaleString('en-IN')} from dead/near-expiry stock.`,
          'emerald'
        );
      } else {
        get().pushToast(`Bill ${sale.invoiceNo} completed`, 'Stock & ledger updated on this device.', 'emerald');
      }
      return sale;
    } catch (err) {
      set({ isSaving: false });
      throw err;
    }
  },

  clearLastCompletedSale: () => set({ lastCompletedSale: null }),

  createProduct: async (input) => {
    set({ isSaving: true });
    try {
      const created = await services.products.create(input);
      const [products, forecastRows] = await Promise.all([
        services.products.getAll(),
        services.forecast.getForecast(get().forecastHorizon),
      ]);
      set({ products, forecastRows, isSaving: false, lastSavedAt: new Date().toISOString() });
      get().pushToast('Item added to inventory', `${created.name} (${created.stockQty} units)`);
    } catch (err) {
      set({ isSaving: false });
      throw err;
    }
  },

  updateProduct: async (productId, patch) => {
    set({ isSaving: true });
    try {
      const updated = await services.products.update(productId, patch);
      const [products, forecastRows] = await Promise.all([
        services.products.getAll(),
        services.forecast.getForecast(get().forecastHorizon),
      ]);
      set((s) => ({
        products,
        forecastRows,
        cart: reconcileCartWithProducts(s.cart, products),
        isSaving: false,
        lastSavedAt: new Date().toISOString(),
      }));
      get().pushToast('Product updated', `${updated.name} changes saved.`);
    } catch (err) {
      set({ isSaving: false });
      throw err;
    }
  },

  adjustStock: async (productId, deltaQty) => {
    set({ isSaving: true });
    try {
      await services.inventory.adjustStock(productId, deltaQty);
      const [products, forecastRows] = await Promise.all([
        services.products.getAll(),
        services.forecast.getForecast(get().forecastHorizon),
      ]);
      set((s) => ({
        products,
        forecastRows,
        cart: reconcileCartWithProducts(s.cart, products),
        isSaving: false,
        lastSavedAt: new Date().toISOString(),
      }));
    } catch (err) {
      set({ isSaving: false });
      throw err;
    }
  },

  setCounterDiscount: async (productId, pricePaise) => {
    set({ isSaving: true });
    try {
      const updated = await services.products.setCounterDiscount(productId, pricePaise);
      const products = await services.products.getAll();
      set({ products, isSaving: false, lastSavedAt: new Date().toISOString() });
      if (updated.counterDiscountPricePaise) {
        get().pushToast(
          'Counter discount live',
          `${updated.name} updated to ₹${(updated.counterDiscountPricePaise / 100).toFixed(0)} on Counter.`
        );
      } else {
        get().pushToast('Counter discount removed', `${updated.name} restored to regular price.`, 'slate');
      }
    } catch (err) {
      set({ isSaving: false });
      throw err;
    }
  },

  setStopReordering: async (productId, stop) => {
    const updated = await services.products.setStopReordering(productId, stop);
    const [products, forecastRows] = await Promise.all([
      services.products.getAll(),
      services.forecast.getForecast(get().forecastHorizon),
    ]);
    set({ products, forecastRows, lastSavedAt: new Date().toISOString() });
    get().pushToast(
      stop ? 'Reordering paused' : 'Reordering resumed',
      updated.name,
      stop ? 'amber' : 'emerald'
    );
  },

  returnToSupplier: async (productId, qty, reason) => {
    const { returnItem } = await services.inventory.returnToSupplier({ productId, qty, reason });
    const [products, supplierReturns, forecastRows] = await Promise.all([
      services.products.getAll(),
      services.suppliers.getReturnList(),
      services.forecast.getForecast(get().forecastHorizon),
    ]);
    set((s) => ({
      products,
      supplierReturns,
      forecastRows,
      cart: reconcileCartWithProducts(s.cart, products),
      lastSavedAt: new Date().toISOString(),
    }));
    get().pushToast(
      'Added to Supplier Return List',
      `${returnItem.qty} × ${returnItem.productName} queued for ${returnItem.supplierName}.`
    );
  },

  markReturnSlipGenerated: async (returnIds) => {
    const supplierReturns = await services.suppliers.markReturnSlipGenerated(returnIds);
    set({ supplierReturns, lastSavedAt: new Date().toISOString() });
  },

  clearReturnedItem: async (returnId) => {
    await services.suppliers.clearReturnedItem(returnId);
    const supplierReturns = await services.suppliers.getReturnList();
    set({ supplierReturns, lastSavedAt: new Date().toISOString() });
    get().pushToast('Return settled', 'Removed from pending supplier return list.', 'slate');
  },

  createCustomer: async (input) => {
    const created = await services.customers.create(input);
    const customers = await services.customers.getAll();
    set({ customers, lastSavedAt: new Date().toISOString() });
    get().pushToast('Customer added', `${created.name} saved to Udhaar ledger.`);
  },

  recordPartialPayment: async (customerId, amountPaise, meta) => {
    set({ isSaving: true });
    try {
      const { customer: updated, payment } = await services.customers.recordPartialPayment(
        customerId,
        amountPaise,
        meta
      );
      const [customers, customerPayments] = await Promise.all([
        services.customers.getAll(),
        services.customers.getPayments(),
      ]);
      set({
        customers,
        customerPayments,
        isSaving: false,
        lastSavedAt: new Date().toISOString(),
      });
      get().pushToast(
        `${payment.paymentMethod === 'upi' ? 'UPI' : 'Cash'} repayment confirmed`,
        `${updated.name} remaining balance: ₹${Math.round(updated.duePaise / 100).toLocaleString('en-IN')}`
      );
      return payment;
    } catch (err) {
      set({ isSaving: false });
      throw err;
    }
  },

  recordPaymentAttempt: async (customerId, amountPaise, meta) => {
    set({ isSaving: true });
    try {
      const attempt = await services.customers.recordPaymentAttempt(customerId, amountPaise, meta);
      const customerPayments = await services.customers.getPayments();
      set({
        customerPayments,
        isSaving: false,
        lastSavedAt: new Date().toISOString(),
      });
      get().pushToast(
        attempt.status === 'failed' ? 'UPI payment marked failed' : 'UPI payment cancelled',
        `No balance was deducted for ${attempt.customerName}.`,
        'amber'
      );
      return attempt;
    } catch (err) {
      set({ isSaving: false });
      throw err;
    }
  },

  setForecastHorizon: async (horizon) => {
    const forecastRows = await services.forecast.getForecast(horizon);
    set({ forecastHorizon: horizon, forecastRows });
  },

  createPurchaseOrder: async (items) => {
    set({ isSaving: true });
    try {
      const po = await services.forecast.createPurchaseOrder(items);
      const purchaseOrders = await services.forecast.getPurchaseOrders();
      set({ purchaseOrders, isSaving: false, lastSavedAt: new Date().toISOString() });
      get().pushToast(`Purchase Order ${po.poNumber} created`, `${po.items.length} line items saved.`);
      return po;
    } catch (err) {
      set({ isSaving: false });
      throw err;
    }
  },

  resetDemoData: async () => {
    await services.reports.resetDemoData();
    set({ cart: [], lastCompletedSale: null });
    await get().init();
    get().pushToast('Demo data restored', 'All inventory, bills, and forecasts reset.', 'slate');
  },
}));
