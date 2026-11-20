export type LanguageCode = 'en' | 'hi' | 'kn';

export type ProductCategory =
  | 'Grains & Atta'
  | 'Edible Oils'
  | 'Dairy & Daily'
  | 'Snacks & Beverages'
  | 'Home & Personal'
  | 'Specialty & Dry Fruits';

export type PaymentMethod = 'cash' | 'upi' | 'udhaar';

export type UpiPaymentStatus =
  | 'initiated'
  | 'awaiting_verification'
  | 'confirmed'
  | 'failed'
  | 'cancelled';

export interface UpiMerchantConfig {
  /**
   * Owner-configured UPI ID (VPA). Intentionally empty until entered by the store owner.
   */
  upiId: string;
  merchantName: string;
  updatedAt: string | null;
}

export type ForecastHorizon = '1W' | '1M' | '6M' | '1Y';

export type ReturnReason = 'Dead stock (slow moving)' | 'Near expiry' | 'Damaged packaging' | 'Excess supply';

export interface Product {
  id: string;
  sku: string;
  name: string;
  hindiName?: string;
  kannadaName?: string;
  category: ProductCategory;
  unit: string;
  mrpPaise: number;
  costPaise: number;
  sellingPricePaise: number;
  counterDiscountPricePaise: number | null;
  stockQty: number;
  reorderLevel: number;
  avgDailySales: number;
  lastSoldAt: string; // ISO date string
  expiryDate: string | null; // ISO date string
  supplierId: string;
  stopReordering: boolean;
}

export interface ProductCreateInput {
  name: string;
  sku: string;
  category: ProductCategory;
  unit: string;
  mrpPaise: number;
  costPaise: number;
  sellingPricePaise: number;
  stockQty: number;
  reorderLevel: number;
  expiryDate: string | null;
  supplierId: string;
}

export interface CartItem {
  productId: string;
  qty: number;
}

export interface SaleLineItem {
  productId: string;
  sku: string;
  name: string;
  unit: string;
  qty: number;
  unitPricePaise: number;
  originalPricePaise: number;
  costPaise: number;
  isDeadStockRescued: boolean;
  lineTotalPaise: number;
}

export interface Sale {
  id: string;
  invoiceNo: string;
  createdAt: string;
  items: SaleLineItem[];
  subtotalPaise: number;
  discountSavedPaise: number;
  totalPaise: number;
  paymentMethod: PaymentMethod;
  customerId: string | null;
  customerName: string | null;
  rescuedDeadStockPaise: number;
  upiTransactionRef?: string;
  upiUtrNumber?: string;
  upiIdUsed?: string;
  paymentStatus?: UpiPaymentStatus;
  isDemoPayment?: boolean;
}

export interface CompleteSaleInput {
  items: CartItem[];
  paymentMethod: PaymentMethod;
  customerId?: string | null;
  upiTransactionRef?: string;
  upiUtrNumber?: string;
  upiIdUsed?: string;
  paymentStatus?: UpiPaymentStatus;
  isDemoPayment?: boolean;
}

export interface Customer {
  id: string;
  name: string;
  phone: string;
  address: string;
  duePaise: number;
  lastTransactionAt: string;
}

export interface CustomerPaymentEntry {
  id: string;
  customerId: string;
  customerName: string;
  amountPaise: number;
  previousDuePaise: number;
  remainingDuePaise: number;
  paymentMethod: 'cash' | 'upi';
  status: UpiPaymentStatus;
  transactionRef: string;
  utrNumber?: string;
  upiIdUsed?: string;
  isDemo: boolean;
  createdAt: string;
}

export interface RecordPaymentMeta {
  paymentMethod: 'cash' | 'upi';
  transactionRef?: string;
  utrNumber?: string;
  upiIdUsed?: string;
  status?: UpiPaymentStatus;
  isDemo?: boolean;
}

export interface CustomerCreateInput {
  name: string;
  phone: string;
  address: string;
  openingDuePaise?: number;
}

export interface Supplier {
  id: string;
  name: string;
  contactPerson: string;
  phone: string;
  city: string;
  leadTimeDays: number;
}

export interface SupplierReturnItem {
  id: string;
  productId: string;
  productName: string;
  sku: string;
  supplierId: string;
  supplierName: string;
  qty: number;
  unitCostPaise: number;
  totalCreditPaise: number;
  reason: ReturnReason;
  createdAt: string;
  slipGeneratedAt: string | null;
}

export interface PurchaseOrderItem {
  productId: string;
  sku: string;
  name: string;
  supplierId: string;
  supplierName: string;
  qty: number;
  unitCostPaise: number;
  lineTotalPaise: number;
}

export interface PurchaseOrder {
  id: string;
  poNumber: string;
  createdAt: string;
  status: 'Ordered' | 'Received';
  items: PurchaseOrderItem[];
  totalPaise: number;
}

export interface ForecastRow {
  productId: string;
  sku: string;
  name: string;
  category: ProductCategory;
  supplierId: string;
  supplierName: string;
  currentStock: number;
  avgDailySales: number;
  forecastedDemand: number;
  recommendedOrderQty: number;
  estimatedOrderCostPaise: number;
  estimatedLostSalesPaise: number;
  daysOfCover: number;
  status: 'Out of Stock' | 'Low Stock' | 'Healthy' | 'Stopped';
  stopReordering: boolean;
}

export interface SalesSummary {
  todayRevenuePaise: number;
  todayBillsCount: number;
  totalRevenuePaise: number;
  cashRevenuePaise: number;
  upiRevenuePaise: number;
  udhaarRevenuePaise: number;
  totalRescuedCashPaise: number;
  dailySeries: { label: string; revenueRupees: number; rescuedRupees: number }[];
  topProducts: { productId: string; name: string; qtySold: number; revenuePaise: number }[];
}
