import type {
  CompleteSaleInput,
  Customer,
  CustomerCreateInput,
  CustomerPaymentEntry,
  ForecastHorizon,
  ForecastRow,
  Product,
  ProductCreateInput,
  PurchaseOrder,
  PurchaseOrderItem,
  RecordPaymentMeta,
  Sale,
  SalesSummary,
  Supplier,
  SupplierReturnItem,
} from '../types/domain';
import { api } from './apiClient';
import type { TrexoServices } from './interfaces';

/**
 * REST adapter implementing the same contract as ``mockServices``.
 *
 * Business rules (stock clamping, duplicate-UPI rejection, invoice sequencing)
 * live on the server; this layer only maps arguments and results.
 */

/** Only mutable product fields are accepted by the backend's ProductPatch. */
const PATCHABLE = [
  'name',
  'sku',
  'category',
  'unit',
  'mrpPaise',
  'costPaise',
  'sellingPricePaise',
  'stockQty',
  'reorderLevel',
  'expiryDate',
  'supplierId',
  'stopReordering',
] as const;

function toProductPatch(patch: Partial<Product>): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  for (const key of PATCHABLE) {
    if (key in patch && patch[key] !== undefined) {
      body[key] = patch[key];
    }
  }
  return body;
}

function toCompleteSaleBody(input: CompleteSaleInput): Record<string, unknown> {
  // Explicit mapping keeps the backend's strict (extra="forbid") schema happy
  // while the frontend's input type can carry optional UI-only fields.
  return {
    items: input.items.map((item) => ({ productId: item.productId, qty: item.qty })),
    paymentMethod: input.paymentMethod,
    customerId: input.customerId ?? null,
    upiTransactionRef: input.upiTransactionRef,
    upiUtrNumber: input.upiUtrNumber,
    upiIdUsed: input.upiIdUsed,
    paymentStatus: input.paymentStatus,
    isDemoPayment: input.isDemoPayment,
  };
}

function toPaymentMeta(meta?: RecordPaymentMeta): Record<string, unknown> | undefined {
  if (!meta) return undefined;
  return {
    paymentMethod: meta.paymentMethod,
    transactionRef: meta.transactionRef,
    utrNumber: meta.utrNumber,
    upiIdUsed: meta.upiIdUsed,
    status: meta.status,
    isDemo: meta.isDemo,
  };
}

export function createApiServices(): TrexoServices {
  return {
    products: {
      getAll: () => api.get<Product[]>('/store/products'),
      create: (input: ProductCreateInput) => api.post<Product>('/store/products', input),
      update: (id: string, patch: Partial<Product>) =>
        api.patch<Product>(`/store/products/${encodeURIComponent(id)}`, toProductPatch(patch)),
      setCounterDiscount: (id: string, pricePaise: number | null) =>
        api.post<Product>(`/store/products/${encodeURIComponent(id)}/counter-discount`, {
          pricePaise,
        }),
      setStopReordering: (id: string, stop: boolean) =>
        api.post<Product>(`/store/products/${encodeURIComponent(id)}/stop-reordering`, { stop }),
    },

    billing: {
      getSales: () => api.get<Sale[]>('/store/sales'),
      completeSale: (input: CompleteSaleInput) => api.post<Sale>('/store/sales', toCompleteSaleBody(input)),
    },

    inventory: {
      adjustStock: (id: string, deltaQty: number) =>
        api.post<Product>(`/store/products/${encodeURIComponent(id)}/stock`, { deltaQty }),
      returnToSupplier: (input) =>
        api.post<{ product: Product; returnItem: SupplierReturnItem }>('/store/supplier-returns', input),
    },

    suppliers: {
      getAll: () => api.get<Supplier[]>('/store/suppliers'),
      getReturnList: () => api.get<SupplierReturnItem[]>('/store/supplier-returns'),
      markReturnSlipGenerated: (returnIds: string[]) =>
        api.post<SupplierReturnItem[]>('/store/supplier-returns/mark-slips', { returnIds }),
      clearReturnedItem: (returnId: string) =>
        api.del<void>(`/store/supplier-returns/${encodeURIComponent(returnId)}`),
    },

    customers: {
      getAll: () => api.get<Customer[]>('/store/customers'),
      getPayments: () => api.get<CustomerPaymentEntry[]>('/store/customer-payments'),
      create: (input: CustomerCreateInput) => api.post<Customer>('/store/customers', input),
      recordPartialPayment: (customerId: string, amountPaise: number, meta?: RecordPaymentMeta) =>
        api.post<{ customer: Customer; payment: CustomerPaymentEntry }>(
          `/store/customers/${encodeURIComponent(customerId)}/payments`,
          { amountPaise, meta: toPaymentMeta(meta) }
        ),
      recordPaymentAttempt: (customerId: string, amountPaise: number, meta: RecordPaymentMeta) =>
        api.post<CustomerPaymentEntry>(
          `/store/customers/${encodeURIComponent(customerId)}/payment-attempts`,
          { amountPaise, meta: toPaymentMeta(meta) }
        ),
    },

    forecast: {
      getForecast: (horizon: ForecastHorizon) =>
        api.get<ForecastRow[]>(`/store/forecast?horizon=${encodeURIComponent(horizon)}`),
      getPurchaseOrders: () => api.get<PurchaseOrder[]>('/store/purchase-orders'),
      createPurchaseOrder: (items: Omit<PurchaseOrderItem, 'lineTotalPaise'>[]) =>
        api.post<PurchaseOrder>('/store/purchase-orders', items),
    },

    reports: {
      getSalesSummary: () => api.get<SalesSummary>('/store/reports/sales-summary'),
      resetDemoData: async () => {
        await api.post('/store/reports/reset-demo', { confirmation: 'RESET-DEMO' });
      },
    },
  };
}
