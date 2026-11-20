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
  ReturnReason,
  Sale,
  SalesSummary,
  Supplier,
  SupplierReturnItem,
} from '../types/domain';

export interface IProductService {
  getAll(): Promise<Product[]>;
  create(input: ProductCreateInput): Promise<Product>;
  update(id: string, patch: Partial<Product>): Promise<Product>;
  setCounterDiscount(id: string, pricePaise: number | null): Promise<Product>;
  setStopReordering(id: string, stop: boolean): Promise<Product>;
}

export interface IBillingService {
  getSales(): Promise<Sale[]>;
  completeSale(input: CompleteSaleInput): Promise<Sale>;
}

export interface ReturnToSupplierInput {
  productId: string;
  qty: number;
  reason: ReturnReason;
}

export interface IInventoryService {
  adjustStock(id: string, deltaQty: number): Promise<Product>;
  returnToSupplier(input: ReturnToSupplierInput): Promise<{
    product: Product;
    returnItem: SupplierReturnItem;
  }>;
}

export interface ISupplierService {
  getAll(): Promise<Supplier[]>;
  getReturnList(): Promise<SupplierReturnItem[]>;
  markReturnSlipGenerated(returnIds: string[]): Promise<SupplierReturnItem[]>;
  clearReturnedItem(returnId: string): Promise<void>;
}

export interface ICustomerService {
  getAll(): Promise<Customer[]>;
  getPayments(): Promise<CustomerPaymentEntry[]>;
  create(input: CustomerCreateInput): Promise<Customer>;
  recordPartialPayment(
    customerId: string,
    amountPaise: number,
    meta?: RecordPaymentMeta
  ): Promise<{ customer: Customer; payment: CustomerPaymentEntry }>;
  recordPaymentAttempt(
    customerId: string,
    amountPaise: number,
    meta: RecordPaymentMeta
  ): Promise<CustomerPaymentEntry>;
}

export interface IForecastService {
  getForecast(horizon: ForecastHorizon): Promise<ForecastRow[]>;
  getPurchaseOrders(): Promise<PurchaseOrder[]>;
  createPurchaseOrder(items: Omit<PurchaseOrderItem, 'lineTotalPaise'>[]): Promise<PurchaseOrder>;
}

export interface IReportsService {
  getSalesSummary(): Promise<SalesSummary>;
  resetDemoData(): Promise<void>;
}

export interface TrexoServices {
  products: IProductService;
  billing: IBillingService;
  inventory: IInventoryService;
  suppliers: ISupplierService;
  customers: ICustomerService;
  forecast: IForecastService;
  reports: IReportsService;
}
