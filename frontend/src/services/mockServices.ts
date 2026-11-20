import { STORAGE_KEYS } from '../config';
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
  SaleLineItem,
  SalesSummary,
  Supplier,
  SupplierReturnItem,
} from '../types/domain';
import {
  calculateLineTotalPaise,
  getEffectivePricePaise,
  isDeadStock,
  isNearExpiry,
  isStockoutFastMover,
} from '../utils/money';
import { generateUpiTransactionRef } from '../utils/upi';
import type { ReturnToSupplierInput, TrexoServices } from './interfaces';

interface PersistedState {
  products: Product[];
  sales: Sale[];
  customers: Customer[];
  customerPayments: CustomerPaymentEntry[];
  confirmedRefs: string[];
  suppliers: Supplier[];
  supplierReturns: SupplierReturnItem[];
  purchaseOrders: PurchaseOrder[];
  invoiceSeq: number;
  poSeq: number;
}

function daysOffsetISO(daysDelta: number): string {
  const d = new Date();
  d.setDate(d.getDate() + daysDelta);
  return d.toISOString();
}

function buildSeedState(): PersistedState {
  const suppliers: Supplier[] = [
    {
      id: 'sup-1',
      name: 'Sri Venkateswara Agencies',
      contactPerson: 'Raghavendra Rao',
      phone: '919845011223',
      city: 'Hubballi APMC Yard',
      leadTimeDays: 2,
    },
    {
      id: 'sup-2',
      name: 'Mahavir Wholesale Distributors',
      contactPerson: 'Suresh Jain',
      phone: '919845044556',
      city: 'Dharwad Main Road',
      leadTimeDays: 3,
    },
    {
      id: 'sup-3',
      name: 'Kaveri FMCG Traders',
      contactPerson: 'Pradeep Deshpande',
      phone: '919845077889',
      city: 'Belagavi Bypass',
      leadTimeDays: 2,
    },
    {
      id: 'sup-4',
      name: 'National Grain & Oil Depot',
      contactPerson: 'Imran Shaikh',
      phone: '919845099001',
      city: 'Gadag Road Market',
      leadTimeDays: 1,
    },
  ];

  const products: Product[] = [
    // Fast-moving core essentials (in stock)
    {
      id: 'prod-1',
      sku: 'GRN-001',
      name: 'Aashirvaad Shudh Chakki Atta 5kg',
      hindiName: 'आशीर्वाद चक्की आटा 5kg',
      kannadaName: 'ಆಶೀರ್ವಾದ್ ಗೋಧಿ ಹಿಟ್ಟು 5kg',
      category: 'Grains & Atta',
      unit: '5 kg bag',
      mrpPaise: 26500,
      costPaise: 21800,
      sellingPricePaise: 25500,
      counterDiscountPricePaise: null,
      stockQty: 18,
      reorderLevel: 10,
      avgDailySales: 4.5,
      lastSoldAt: daysOffsetISO(0),
      expiryDate: daysOffsetISO(95),
      supplierId: 'sup-4',
      stopReordering: false,
    },
    {
      id: 'prod-2',
      sku: 'OIL-002',
      name: 'Fortune Sunlite Sunflower Oil 1L',
      hindiName: 'फॉर्च्यून सनफ्लावर तेल 1L',
      kannadaName: 'ಫಾರ್ಚ್ಯೂನ್ ಸೂರ್ಯಕಾಂತಿ ಎಣ್ಣೆ 1L',
      category: 'Edible Oils',
      unit: '1 L pouch',
      mrpPaise: 15500,
      costPaise: 12600,
      sellingPricePaise: 14500,
      counterDiscountPricePaise: null,
      stockQty: 24,
      reorderLevel: 12,
      avgDailySales: 6.2,
      lastSoldAt: daysOffsetISO(0),
      expiryDate: daysOffsetISO(140),
      supplierId: 'sup-4',
      stopReordering: false,
    },
    {
      id: 'prod-3',
      sku: 'GRN-003',
      name: 'Tata Salt Vacuum Evaporated 1kg',
      hindiName: 'टाटा नमक 1kg',
      kannadaName: 'ಟಾಟಾ ಉಪ್ಪು 1kg',
      category: 'Grains & Atta',
      unit: '1 kg pack',
      mrpPaise: 2800,
      costPaise: 2250,
      sellingPricePaise: 2800,
      counterDiscountPricePaise: null,
      stockQty: 42,
      reorderLevel: 18,
      avgDailySales: 8.0,
      lastSoldAt: daysOffsetISO(0),
      expiryDate: daysOffsetISO(320),
      supplierId: 'sup-1',
      stopReordering: false,
    },
    {
      id: 'prod-4',
      sku: 'SNK-004',
      name: 'Parle-G Gold Biscuits 1kg Value',
      hindiName: 'पारले-जी गोल्ड बिस्कुट 1kg',
      kannadaName: 'ಪಾರ್ಲೆ-ಜಿ ಗೋಲ್ಡ್ ಬಿಸ್ಕೆಟ್ 1kg',
      category: 'Snacks & Beverages',
      unit: '1 kg pack',
      mrpPaise: 12000,
      costPaise: 9600,
      sellingPricePaise: 11500,
      counterDiscountPricePaise: null,
      stockQty: 14,
      reorderLevel: 8,
      avgDailySales: 3.4,
      lastSoldAt: daysOffsetISO(-1),
      expiryDate: daysOffsetISO(110),
      supplierId: 'sup-3',
      stopReordering: false,
    },
    {
      id: 'prod-5',
      sku: 'SNK-005',
      name: 'Brooke Bond Red Label Tea 500g',
      hindiName: 'रेड लेबल चाय 500g',
      kannadaName: 'ರೆಡ್ ಲೇಬಲ್ ಚಹಾ ಪುಡಿ 500g',
      category: 'Snacks & Beverages',
      unit: '500 g box',
      mrpPaise: 28500,
      costPaise: 23800,
      sellingPricePaise: 27500,
      counterDiscountPricePaise: null,
      stockQty: 9,
      reorderLevel: 10,
      avgDailySales: 2.8,
      lastSoldAt: daysOffsetISO(0),
      expiryDate: daysOffsetISO(190),
      supplierId: 'sup-3',
      stopReordering: false,
    },
    {
      id: 'prod-6',
      sku: 'GRN-006',
      name: 'Unpolished Toor Dal Loose 1kg',
      hindiName: 'तूर दाल 1kg',
      kannadaName: 'ತೊಗರಿ ಬೇಳೆ 1kg',
      category: 'Grains & Atta',
      unit: '1 kg',
      mrpPaise: 16800,
      costPaise: 13800,
      sellingPricePaise: 16200,
      counterDiscountPricePaise: null,
      stockQty: 28,
      reorderLevel: 15,
      avgDailySales: 5.5,
      lastSoldAt: daysOffsetISO(0),
      expiryDate: daysOffsetISO(150),
      supplierId: 'sup-4',
      stopReordering: false,
    },
    {
      id: 'prod-7',
      sku: 'HMP-007',
      name: 'Surf Excel Easy Wash 1kg',
      hindiName: 'सर्फ एक्सेल ईज़ी वॉश 1kg',
      kannadaName: 'ಸರ್ಫ್ ಎಕ್ಸೆಲ್ 1kg',
      category: 'Home & Personal',
      unit: '1 kg pack',
      mrpPaise: 14800,
      costPaise: 11800,
      sellingPricePaise: 14200,
      counterDiscountPricePaise: null,
      stockQty: 16,
      reorderLevel: 8,
      avgDailySales: 3.1,
      lastSoldAt: daysOffsetISO(-1),
      expiryDate: daysOffsetISO(280),
      supplierId: 'sup-3',
      stopReordering: false,
    },
    // Out-of-stock fast movers (driving Estimated sales lost to stockouts)
    {
      id: 'prod-8',
      sku: 'DRY-008',
      name: 'Nandini GoodLife Toned Milk 500ml',
      hindiName: 'नंदिनी टोंड दूध 500ml',
      kannadaName: 'ನಂದಿನಿ ಗುಡ್‌ಲೈಫ್ ಹಾಲು 500ml',
      category: 'Dairy & Daily',
      unit: '500 ml pack',
      mrpPaise: 3200,
      costPaise: 2700,
      sellingPricePaise: 3200,
      counterDiscountPricePaise: null,
      stockQty: 0,
      reorderLevel: 24,
      avgDailySales: 14.0,
      lastSoldAt: daysOffsetISO(-2),
      expiryDate: daysOffsetISO(45),
      supplierId: 'sup-1',
      stopReordering: false,
    },
    {
      id: 'prod-9',
      sku: 'SNK-009',
      name: 'Maggi 2-Minute Masala Noodles 12-Pack',
      hindiName: 'मैगी मसाला नूडल्स 12-पैक',
      kannadaName: 'ಮ್ಯಾಗಿ ಮಸಾಲಾ ನೂಡಲ್ಸ್ 12-ಪ್ಯಾಕ್',
      category: 'Snacks & Beverages',
      unit: '840 g pack',
      mrpPaise: 16800,
      costPaise: 13900,
      sellingPricePaise: 16500,
      counterDiscountPricePaise: null,
      stockQty: 0,
      reorderLevel: 12,
      avgDailySales: 4.2,
      lastSoldAt: daysOffsetISO(-3),
      expiryDate: daysOffsetISO(120),
      supplierId: 'sup-3',
      stopReordering: false,
    },
    {
      id: 'prod-10',
      sku: 'OIL-010',
      name: 'Gold Winner Refined Groundnut Oil 1L',
      hindiName: 'गोल्ड विनर मूंगफली तेल 1L',
      kannadaName: 'ಗೋಲ್ಡ್ ವಿನ್ನರ್ ಶೇಂಗಾ ಎಣ್ಣೆ 1L',
      category: 'Edible Oils',
      unit: '1 L bottle',
      mrpPaise: 21000,
      costPaise: 17600,
      sellingPricePaise: 20200,
      counterDiscountPricePaise: null,
      stockQty: 0,
      reorderLevel: 10,
      avgDailySales: 3.5,
      lastSoldAt: daysOffsetISO(-2),
      expiryDate: daysOffsetISO(160),
      supplierId: 'sup-4',
      stopReordering: false,
    },
    // DEAD STOCK & NEAR-EXPIRY items trapping significant working capital
    {
      id: 'prod-11',
      sku: 'SPC-011',
      name: 'Figaro Pomace Olive Oil Tin 1L',
      hindiName: 'फिगारो ऑलिव ऑयल टिन 1L',
      kannadaName: 'ಫಿಗಾರೊ ಆಲಿವ್ ಎಣ್ಣೆ 1L',
      category: 'Edible Oils',
      unit: '1 L tin',
      mrpPaise: 118000,
      costPaise: 89000,
      sellingPricePaise: 112000,
      counterDiscountPricePaise: null,
      stockQty: 11,
      reorderLevel: 3,
      avgDailySales: 0.1,
      lastSoldAt: daysOffsetISO(-64),
      expiryDate: daysOffsetISO(48),
      supplierId: 'sup-2',
      stopReordering: false,
    },
    {
      id: 'prod-12',
      sku: 'SPC-012',
      name: 'Organic White Quinoa Grain 500g',
      hindiName: 'ऑर्गेनिक क्विनोआ 500g',
      kannadaName: 'ಆರ್ಗ್ಯಾನಿಕ್ ಕ್ವಿನೋವಾ 500g',
      category: 'Specialty & Dry Fruits',
      unit: '500 g pouch',
      mrpPaise: 34000,
      costPaise: 24500,
      sellingPricePaise: 32500,
      counterDiscountPricePaise: null,
      stockQty: 16,
      reorderLevel: 4,
      avgDailySales: 0.1,
      lastSoldAt: daysOffsetISO(-52),
      expiryDate: daysOffsetISO(11),
      supplierId: 'sup-2',
      stopReordering: false,
    },
    {
      id: 'prod-13',
      sku: 'SPC-013',
      name: 'Kashmiri Saffron Basmati Gold 5kg',
      hindiName: 'केसर बासमती चावल 5kg',
      kannadaName: 'ಕೇಸರಿ ಬಾಸ್ಮತಿ ಅಕ್ಕಿ 5kg',
      category: 'Grains & Atta',
      unit: '5 kg bag',
      mrpPaise: 92000,
      costPaise: 71000,
      sellingPricePaise: 88000,
      counterDiscountPricePaise: null,
      stockQty: 8,
      reorderLevel: 3,
      avgDailySales: 0.2,
      lastSoldAt: daysOffsetISO(-46),
      expiryDate: daysOffsetISO(72),
      supplierId: 'sup-1',
      stopReordering: false,
    },
    {
      id: 'prod-14',
      sku: 'SNK-014',
      name: 'Tulsi Chamomile Herbal Tea Tin 100g',
      hindiName: 'तुलसी हर्बल ग्रीन टी टिन',
      kannadaName: 'ತುಳಸಿ ಹರ್ಬಲ್ ಟೀ ಟಿನ್ 100g',
      category: 'Snacks & Beverages',
      unit: '100 g tin',
      mrpPaise: 42000,
      costPaise: 31000,
      sellingPricePaise: 39500,
      counterDiscountPricePaise: null,
      stockQty: 14,
      reorderLevel: 4,
      avgDailySales: 0.1,
      lastSoldAt: daysOffsetISO(-41),
      expiryDate: daysOffsetISO(9),
      supplierId: 'sup-2',
      stopReordering: false,
    },
    {
      id: 'prod-15',
      sku: 'HMP-015',
      name: 'Botanical Argan Hair Serum 200ml',
      hindiName: 'आर्गन हेयर सीरम 200ml',
      kannadaName: 'ಆರ್ಗನ್ ಹೇರ್ ಸೀರಮ್ 200ml',
      category: 'Home & Personal',
      unit: '200 ml bottle',
      mrpPaise: 49500,
      costPaise: 34500,
      sellingPricePaise: 46000,
      counterDiscountPricePaise: null,
      stockQty: 9,
      reorderLevel: 2,
      avgDailySales: 0.1,
      lastSoldAt: daysOffsetISO(-58),
      expiryDate: daysOffsetISO(105),
      supplierId: 'sup-3',
      stopReordering: false,
    },
    {
      id: 'prod-16',
      sku: 'DRY-016',
      name: 'Crunchy Honey Almond Butter 340g',
      hindiName: 'हनी बादाम बटर 340g',
      kannadaName: 'ಜೇನು ಬಾದಾಮಿ ಬಟರ್ 340g',
      category: 'Specialty & Dry Fruits',
      unit: '340 g jar',
      mrpPaise: 54000,
      costPaise: 41000,
      sellingPricePaise: 51000,
      counterDiscountPricePaise: 42000, // One item pre-discounted to show counter discount badge in action
      stockQty: 7,
      reorderLevel: 2,
      avgDailySales: 0.2,
      lastSoldAt: daysOffsetISO(-35),
      expiryDate: daysOffsetISO(7),
      supplierId: 'sup-2',
      stopReordering: false,
    },
  ];

  const customers: Customer[] = [
    {
      id: 'cust-1',
      name: 'Ramesh Sharma',
      phone: '+91 98451 33412',
      address: 'Vidyanagar 2nd Cross',
      duePaise: 145000,
      lastTransactionAt: daysOffsetISO(-2),
    },
    {
      id: 'cust-2',
      name: 'Sunita Devi Patil',
      phone: '+91 99002 78123',
      address: 'Keshwapur Main Road',
      duePaise: 82000,
      lastTransactionAt: daysOffsetISO(-1),
    },
    {
      id: 'cust-3',
      name: 'Manjunath Gowda',
      phone: '+91 97400 56219',
      address: 'Deshpande Nagar Block B',
      duePaise: 234000,
      lastTransactionAt: daysOffsetISO(-4),
    },
    {
      id: 'cust-4',
      name: 'Fatima Begum',
      phone: '+91 98861 44019',
      address: 'Old Hubballi Circle',
      duePaise: 46500,
      lastTransactionAt: daysOffsetISO(-3),
    },
    {
      id: 'cust-5',
      name: 'Prakash Kulkarni',
      phone: '+91 94481 91022',
      address: 'Gokul Road Extension',
      duePaise: 0,
      lastTransactionAt: daysOffsetISO(-5),
    },
  ];

  const sales: Sale[] = [
    {
      id: 'sale-1',
      invoiceNo: 'TRX-1041',
      createdAt: daysOffsetISO(0),
      items: [
        {
          productId: 'prod-1',
          sku: 'GRN-001',
          name: 'Aashirvaad Shudh Chakki Atta 5kg',
          unit: '5 kg bag',
          qty: 2,
          unitPricePaise: 25500,
          originalPricePaise: 25500,
          costPaise: 21800,
          isDeadStockRescued: false,
          lineTotalPaise: 51000,
        },
        {
          productId: 'prod-2',
          sku: 'OIL-002',
          name: 'Fortune Sunlite Sunflower Oil 1L',
          unit: '1 L pouch',
          qty: 3,
          unitPricePaise: 14500,
          originalPricePaise: 14500,
          costPaise: 12600,
          isDeadStockRescued: false,
          lineTotalPaise: 43500,
        },
      ],
      subtotalPaise: 94500,
      discountSavedPaise: 0,
      totalPaise: 94500,
      paymentMethod: 'upi',
      customerId: null,
      customerName: 'Walk-in Customer',
      rescuedDeadStockPaise: 0,
    },
    {
      id: 'sale-2',
      invoiceNo: 'TRX-1040',
      createdAt: daysOffsetISO(0),
      items: [
        {
          productId: 'prod-6',
          sku: 'GRN-006',
          name: 'Unpolished Toor Dal Loose 1kg',
          unit: '1 kg',
          qty: 2,
          unitPricePaise: 16200,
          originalPricePaise: 16200,
          costPaise: 13800,
          isDeadStockRescued: false,
          lineTotalPaise: 32400,
        },
        {
          productId: 'prod-16',
          sku: 'DRY-016',
          name: 'Crunchy Honey Almond Butter 340g',
          unit: '340 g jar',
          qty: 1,
          unitPricePaise: 42000,
          originalPricePaise: 51000,
          costPaise: 41000,
          isDeadStockRescued: true,
          lineTotalPaise: 42000,
        },
      ],
      subtotalPaise: 83400,
      discountSavedPaise: 9000,
      totalPaise: 74400,
      paymentMethod: 'cash',
      customerId: null,
      customerName: 'Walk-in Customer',
      rescuedDeadStockPaise: 42000,
    },
    {
      id: 'sale-3',
      invoiceNo: 'TRX-1039',
      createdAt: daysOffsetISO(-1),
      items: [
        {
          productId: 'prod-5',
          sku: 'SNK-005',
          name: 'Brooke Bond Red Label Tea 500g',
          unit: '500 g box',
          qty: 2,
          unitPricePaise: 27500,
          originalPricePaise: 27500,
          costPaise: 23800,
          isDeadStockRescued: false,
          lineTotalPaise: 55000,
        },
        {
          productId: 'prod-7',
          sku: 'HMP-007',
          name: 'Surf Excel Easy Wash 1kg',
          unit: '1 kg pack',
          qty: 2,
          unitPricePaise: 14200,
          originalPricePaise: 14200,
          costPaise: 11800,
          isDeadStockRescued: false,
          lineTotalPaise: 28400,
        },
      ],
      subtotalPaise: 83400,
      discountSavedPaise: 0,
      totalPaise: 83400,
      paymentMethod: 'udhaar',
      customerId: 'cust-2',
      customerName: 'Sunita Devi Patil',
      rescuedDeadStockPaise: 0,
    },
    {
      id: 'sale-4',
      invoiceNo: 'TRX-1038',
      createdAt: daysOffsetISO(-2),
      items: [
        {
          productId: 'prod-3',
          sku: 'GRN-003',
          name: 'Tata Salt Vacuum Evaporated 1kg',
          unit: '1 kg pack',
          qty: 6,
          unitPricePaise: 2800,
          originalPricePaise: 2800,
          costPaise: 2250,
          isDeadStockRescued: false,
          lineTotalPaise: 16800,
        },
        {
          productId: 'prod-1',
          sku: 'GRN-001',
          name: 'Aashirvaad Shudh Chakki Atta 5kg',
          unit: '5 kg bag',
          qty: 3,
          unitPricePaise: 25500,
          originalPricePaise: 25500,
          costPaise: 21800,
          isDeadStockRescued: false,
          lineTotalPaise: 76500,
        },
      ],
      subtotalPaise: 93300,
      discountSavedPaise: 0,
      totalPaise: 93300,
      paymentMethod: 'cash',
      customerId: null,
      customerName: 'Walk-in Customer',
      rescuedDeadStockPaise: 0,
    },
    {
      id: 'sale-5',
      invoiceNo: 'TRX-1037',
      createdAt: daysOffsetISO(-3),
      items: [
        {
          productId: 'prod-2',
          sku: 'OIL-002',
          name: 'Fortune Sunlite Sunflower Oil 1L',
          unit: '1 L pouch',
          qty: 5,
          unitPricePaise: 14500,
          originalPricePaise: 14500,
          costPaise: 12600,
          isDeadStockRescued: false,
          lineTotalPaise: 72500,
        },
        {
          productId: 'prod-4',
          sku: 'SNK-004',
          name: 'Parle-G Gold Biscuits 1kg Value',
          unit: '1 kg pack',
          qty: 3,
          unitPricePaise: 11500,
          originalPricePaise: 11500,
          costPaise: 9600,
          isDeadStockRescued: false,
          lineTotalPaise: 34500,
        },
      ],
      subtotalPaise: 107000,
      discountSavedPaise: 0,
      totalPaise: 107000,
      paymentMethod: 'upi',
      customerId: null,
      customerName: 'Walk-in Customer',
      rescuedDeadStockPaise: 0,
    },
    {
      id: 'sale-6',
      invoiceNo: 'TRX-1036',
      createdAt: daysOffsetISO(-4),
      items: [
        {
          productId: 'prod-6',
          sku: 'GRN-006',
          name: 'Unpolished Toor Dal Loose 1kg',
          unit: '1 kg',
          qty: 4,
          unitPricePaise: 16200,
          originalPricePaise: 16200,
          costPaise: 13800,
          isDeadStockRescued: false,
          lineTotalPaise: 64800,
        },
      ],
      subtotalPaise: 64800,
      discountSavedPaise: 0,
      totalPaise: 64800,
      paymentMethod: 'cash',
      customerId: null,
      customerName: 'Walk-in Customer',
      rescuedDeadStockPaise: 0,
    },
  ];

  const supplierReturns: SupplierReturnItem[] = [
    {
      id: 'ret-1',
      productId: 'prod-12',
      productName: 'Organic White Quinoa Grain 500g',
      sku: 'SPC-012',
      supplierId: 'sup-2',
      supplierName: 'Mahavir Wholesale Distributors',
      qty: 4,
      unitCostPaise: 24500,
      totalCreditPaise: 98000,
      reason: 'Near expiry',
      createdAt: daysOffsetISO(-1),
      slipGeneratedAt: null,
    },
  ];

  const purchaseOrders: PurchaseOrder[] = [
    {
      id: 'po-1',
      poNumber: 'PO-2026-084',
      createdAt: daysOffsetISO(-5),
      status: 'Received',
      items: [
        {
          productId: 'prod-1',
          sku: 'GRN-001',
          name: 'Aashirvaad Shudh Chakki Atta 5kg',
          supplierId: 'sup-4',
          supplierName: 'National Grain & Oil Depot',
          qty: 20,
          unitCostPaise: 21800,
          lineTotalPaise: 436000,
        },
      ],
      totalPaise: 436000,
    },
  ];

  const customerPayments: CustomerPaymentEntry[] = [
    {
      id: 'pay-seed-1',
      customerId: 'cust-1',
      customerName: 'Ramesh Sharma',
      amountPaise: 50000,
      previousDuePaise: 195000,
      remainingDuePaise: 145000,
      paymentMethod: 'upi',
      status: 'confirmed',
      transactionRef: 'TRX-UDHAAR-SEED-1001',
      isDemo: true,
      createdAt: daysOffsetISO(-2),
    },
    {
      id: 'pay-seed-2',
      customerId: 'cust-2',
      customerName: 'Sunita Devi Patil',
      amountPaise: 40000,
      previousDuePaise: 122000,
      remainingDuePaise: 82000,
      paymentMethod: 'cash',
      status: 'confirmed',
      transactionRef: 'TRX-CASH-SEED-1002',
      isDemo: true,
      createdAt: daysOffsetISO(-3),
    },
    {
      id: 'pay-seed-3',
      customerId: 'cust-5',
      customerName: 'Prakash Kulkarni',
      amountPaise: 118000,
      previousDuePaise: 118000,
      remainingDuePaise: 0,
      paymentMethod: 'upi',
      status: 'confirmed',
      transactionRef: 'TRX-UDHAAR-SEED-1003',
      isDemo: true,
      createdAt: daysOffsetISO(-5),
    },
  ];

  return {
    products,
    sales,
    customers,
    customerPayments,
    confirmedRefs: ['TRX-UDHAAR-SEED-1001', 'TRX-CASH-SEED-1002', 'TRX-UDHAAR-SEED-1003'],
    suppliers,
    supplierReturns,
    purchaseOrders,
    invoiceSeq: 1042,
    poSeq: 85,
  };
}

function isValidRecord(item: unknown, requiredKeys: string[]): item is Record<string, unknown> {
  if (!item || typeof item !== 'object') return false;
  const obj = item as Record<string, unknown>;
  return requiredKeys.every((key) => obj[key] !== undefined && obj[key] !== null);
}

function loadState(): PersistedState {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.STATE_V1);
    if (!raw) {
      const seeded = buildSeedState();
      saveState(seeded);
      return seeded;
    }
    const parsed = JSON.parse(raw) as Partial<PersistedState>;
    if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.products) || !Array.isArray(parsed.suppliers)) {
      const seeded = buildSeedState();
      saveState(seeded);
      return seeded;
    }

    const validProducts = parsed.products.filter(
      (p) =>
        isValidRecord(p, ['id', 'sku', 'name', 'sellingPricePaise', 'costPaise', 'stockQty']) &&
        typeof p.sellingPricePaise === 'number' &&
        Number.isFinite(p.sellingPricePaise) &&
        typeof p.costPaise === 'number' &&
        Number.isFinite(p.costPaise) &&
        typeof p.stockQty === 'number' &&
        Number.isFinite(p.stockQty)
    ) as Product[];

    const validSuppliers = parsed.suppliers.filter((s) =>
      isValidRecord(s, ['id', 'name'])
    ) as Supplier[];

    // If persisted arrays had non-empty entries that were all corrupted, repair cleanly
    if (
      (parsed.products.length > 0 && validProducts.length === 0) ||
      (parsed.suppliers.length > 0 && validSuppliers.length === 0)
    ) {
      const seeded = buildSeedState();
      saveState(seeded);
      return seeded;
    }

    const seededDefaults = buildSeedState();
    const validSales = Array.isArray(parsed.sales)
      ? (parsed.sales.filter(
          (s) =>
            isValidRecord(s, ['id', 'invoiceNo', 'createdAt', 'totalPaise', 'paymentMethod']) &&
            Array.isArray((s as { items?: unknown }).items)
        ) as Sale[])
      : seededDefaults.sales;

    const validCustomers = Array.isArray(parsed.customers)
      ? (parsed.customers.filter(
          (c) =>
            isValidRecord(c, ['id', 'name', 'duePaise']) &&
            typeof c.duePaise === 'number' &&
            Number.isFinite(c.duePaise)
        ) as Customer[])
      : seededDefaults.customers;

    const validCustomerPayments = Array.isArray(parsed.customerPayments)
      ? (parsed.customerPayments.filter((p) =>
          isValidRecord(p, ['id', 'customerId', 'amountPaise', 'paymentMethod', 'status'])
        ) as CustomerPaymentEntry[])
      : seededDefaults.customerPayments;

    const validConfirmedRefs = Array.isArray(parsed.confirmedRefs)
      ? parsed.confirmedRefs.filter((r): r is string => typeof r === 'string')
      : seededDefaults.confirmedRefs;

    return {
      products: validProducts,
      sales: validSales,
      customers: validCustomers,
      customerPayments: validCustomerPayments,
      confirmedRefs: validConfirmedRefs,
      suppliers: validSuppliers,
      supplierReturns: Array.isArray(parsed.supplierReturns)
        ? (parsed.supplierReturns.filter((r) =>
            isValidRecord(r, ['id', 'productId', 'qty'])
          ) as SupplierReturnItem[])
        : [],
      purchaseOrders: Array.isArray(parsed.purchaseOrders)
        ? (parsed.purchaseOrders.filter((po) =>
            isValidRecord(po, ['id', 'poNumber', 'items'])
          ) as PurchaseOrder[])
        : [],
      invoiceSeq:
        typeof parsed.invoiceSeq === 'number' && Number.isFinite(parsed.invoiceSeq)
          ? parsed.invoiceSeq
          : seededDefaults.invoiceSeq,
      poSeq:
        typeof parsed.poSeq === 'number' && Number.isFinite(parsed.poSeq)
          ? parsed.poSeq
          : seededDefaults.poSeq,
    };
  } catch {
    const seeded = buildSeedState();
    saveState(seeded);
    return seeded;
  }
}

function saveState(state: PersistedState): void {
  try {
    localStorage.setItem(STORAGE_KEYS.STATE_V1, JSON.stringify(state));
  } catch {
    // Storage quota or restricted mode fallback
  }
}

const HORIZON_MULTIPLIERS: Record<ForecastHorizon, { days: number; seasonalFactor: number }> = {
  '1W': { days: 7, seasonalFactor: 1.05 },
  '1M': { days: 30, seasonalFactor: 1.12 },
  '6M': { days: 180, seasonalFactor: 1.18 },
  '1Y': { days: 365, seasonalFactor: 1.24 },
};

export function createMockServices(): TrexoServices {
  return {
    products: {
      async getAll() {
        return loadState().products;
      },
      async create(input: ProductCreateInput) {
        const state = loadState();
        const product: Product = {
          id: `prod-${Date.now()}`,
          sku: input.sku.trim().toUpperCase() || `SKU-${Math.floor(1000 + Math.random() * 9000)}`,
          name: input.name.trim(),
          category: input.category,
          unit: input.unit.trim() || '1 unit',
          mrpPaise: input.mrpPaise,
          costPaise: input.costPaise,
          sellingPricePaise: input.sellingPricePaise,
          counterDiscountPricePaise: null,
          stockQty: Math.max(0, Math.round(input.stockQty)),
          reorderLevel: Math.max(0, Math.round(input.reorderLevel)),
          avgDailySales: 0,
          lastSoldAt: new Date().toISOString(),
          expiryDate: input.expiryDate,
          supplierId: input.supplierId,
          stopReordering: false,
        };
        state.products.unshift(product);
        saveState(state);
        return product;
      },
      async update(id: string, patch: Partial<Product>) {
        const state = loadState();
        const idx = state.products.findIndex((p) => p.id === id);
        if (idx === -1) throw new Error('Product not found');
        state.products[idx] = { ...state.products[idx], ...patch };
        saveState(state);
        return state.products[idx];
      },
      async setCounterDiscount(id: string, pricePaise: number | null) {
        const state = loadState();
        const idx = state.products.findIndex((p) => p.id === id);
        if (idx === -1) throw new Error('Product not found');
        const product = state.products[idx];
        const sanitized =
          pricePaise !== null && pricePaise > 0 && pricePaise < product.sellingPricePaise
            ? Math.round(pricePaise)
            : null;
        state.products[idx] = { ...product, counterDiscountPricePaise: sanitized };
        saveState(state);
        return state.products[idx];
      },
      async setStopReordering(id: string, stop: boolean) {
        const state = loadState();
        const idx = state.products.findIndex((p) => p.id === id);
        if (idx === -1) throw new Error('Product not found');
        state.products[idx] = { ...state.products[idx], stopReordering: stop };
        saveState(state);
        return state.products[idx];
      },
    },

    billing: {
      async getSales() {
        return loadState().sales;
      },
      async completeSale(input: CompleteSaleInput) {
        const state = loadState();
        const now = new Date();
        const nowIso = now.toISOString();

        const saleItems: SaleLineItem[] = [];
        let subtotalPaise = 0;
        let totalPaise = 0;
        let rescuedDeadStockPaise = 0;

        for (const cartLine of input.items) {
          const prodIdx = state.products.findIndex((p) => p.id === cartLine.productId);
          if (prodIdx === -1) continue;
          const prod = state.products[prodIdx];
          if (prod.stockQty <= 0) {
            throw new Error(`${prod.name} is out of stock.`);
          }
          const qty = Math.min(Math.max(1, Math.round(cartLine.qty)), prod.stockQty);
          const effPrice = getEffectivePricePaise(prod);
          const origPrice = prod.sellingPricePaise;
          const lineTotal = calculateLineTotalPaise(effPrice, qty);
          const origTotal = calculateLineTotalPaise(origPrice, qty);
          const wasDeadOrNearExpiry = isDeadStock(prod, now) || isNearExpiry(prod, now);

          subtotalPaise += origTotal;
          totalPaise += lineTotal;
          if (wasDeadOrNearExpiry) {
            rescuedDeadStockPaise += lineTotal;
          }

          saleItems.push({
            productId: prod.id,
            sku: prod.sku,
            name: prod.name,
            unit: prod.unit,
            qty,
            unitPricePaise: effPrice,
            originalPricePaise: origPrice,
            costPaise: prod.costPaise,
            isDeadStockRescued: wasDeadOrNearExpiry,
            lineTotalPaise: lineTotal,
          });

          const remainingStock = Math.max(0, prod.stockQty - qty);
          state.products[prodIdx] = {
            ...prod,
            stockQty: remainingStock,
            avgDailySales:
              prod.avgDailySales > 0 ? prod.avgDailySales : Number(Math.max(0.2, qty / 7).toFixed(2)),
            lastSoldAt: nowIso,
            // Clear counter discount once stock sells out
            counterDiscountPricePaise: remainingStock === 0 ? null : prod.counterDiscountPricePaise,
          };
        }

        if (saleItems.length === 0) {
          throw new Error('Cannot complete empty sale');
        }

        let customerName: string | null = 'Walk-in Customer';
        let customerId: string | null = null;
        if (input.paymentMethod === 'udhaar') {
          const custIdx = input.customerId
            ? state.customers.findIndex((c) => c.id === input.customerId)
            : -1;
          if (custIdx === -1) {
            throw new Error('Select a valid customer account for Udhaar billing.');
          }
          customerId = state.customers[custIdx].id;
          customerName = state.customers[custIdx].name;
          state.customers[custIdx] = {
            ...state.customers[custIdx],
            duePaise: state.customers[custIdx].duePaise + totalPaise,
            lastTransactionAt: nowIso,
          };
        } else if (input.customerId) {
          const found = state.customers.find((c) => c.id === input.customerId);
          if (found) {
            customerId = found.id;
            customerName = found.name;
          }
        }

        // Prevent accidental duplicate confirmation of the same UPI transaction reference
        if (input.upiTransactionRef && state.confirmedRefs.includes(input.upiTransactionRef)) {
          throw new Error('This UPI transaction reference has already been confirmed.');
        }

        const sale: Sale = {
          id: `sale-${Date.now()}`,
          invoiceNo: `TRX-${state.invoiceSeq}`,
          createdAt: nowIso,
          items: saleItems,
          subtotalPaise,
          discountSavedPaise: Math.max(0, subtotalPaise - totalPaise),
          totalPaise,
          paymentMethod: input.paymentMethod,
          customerId,
          customerName,
          rescuedDeadStockPaise,
          upiTransactionRef: input.upiTransactionRef,
          upiUtrNumber: input.upiUtrNumber?.trim() || undefined,
          upiIdUsed: input.upiIdUsed?.trim() || undefined,
          paymentStatus: input.paymentStatus ?? 'confirmed',
          isDemoPayment: input.isDemoPayment ?? (input.paymentMethod === 'upi'),
        };

        if (input.upiTransactionRef) {
          state.confirmedRefs.push(input.upiTransactionRef);
        }

        state.invoiceSeq += 1;
        state.sales.unshift(sale);
        saveState(state);
        return sale;
      },
    },

    inventory: {
      async adjustStock(id: string, deltaQty: number) {
        const state = loadState();
        const idx = state.products.findIndex((p) => p.id === id);
        if (idx === -1) throw new Error('Product not found');
        const nextQty = Math.max(0, state.products[idx].stockQty + Math.round(deltaQty));
        state.products[idx] = { ...state.products[idx], stockQty: nextQty };
        saveState(state);
        return state.products[idx];
      },
      async returnToSupplier(input: ReturnToSupplierInput) {
        const state = loadState();
        const idx = state.products.findIndex((p) => p.id === input.productId);
        if (idx === -1) throw new Error('Product not found');
        const prod = state.products[idx];
        const qty = Math.min(Math.max(1, Math.round(input.qty)), prod.stockQty);
        if (qty <= 0) throw new Error('No stock available to return');

        const supplier = state.suppliers.find((s) => s.id === prod.supplierId);
        const returnItem: SupplierReturnItem = {
          id: `ret-${Date.now()}`,
          productId: prod.id,
          productName: prod.name,
          sku: prod.sku,
          supplierId: prod.supplierId,
          supplierName: supplier?.name ?? 'Assigned Distributor',
          qty,
          unitCostPaise: prod.costPaise,
          totalCreditPaise: qty * prod.costPaise,
          reason: input.reason,
          createdAt: new Date().toISOString(),
          slipGeneratedAt: null,
        };

        state.products[idx] = {
          ...prod,
          stockQty: Math.max(0, prod.stockQty - qty),
        };
        state.supplierReturns.unshift(returnItem);
        saveState(state);
        return { product: state.products[idx], returnItem };
      },
    },

    suppliers: {
      async getAll() {
        return loadState().suppliers;
      },
      async getReturnList() {
        return loadState().supplierReturns;
      },
      async markReturnSlipGenerated(returnIds: string[]) {
        const state = loadState();
        const nowIso = new Date().toISOString();
        const idSet = new Set(returnIds);
        state.supplierReturns = state.supplierReturns.map((item) =>
          idSet.has(item.id) ? { ...item, slipGeneratedAt: nowIso } : item
        );
        saveState(state);
        return state.supplierReturns;
      },
      async clearReturnedItem(returnId: string) {
        const state = loadState();
        state.supplierReturns = state.supplierReturns.filter((r) => r.id !== returnId);
        saveState(state);
      },
    },

    customers: {
      async getAll() {
        return loadState().customers;
      },
      async getPayments() {
        return loadState().customerPayments;
      },
      async create(input: CustomerCreateInput) {
        const state = loadState();
        const customer: Customer = {
          id: `cust-${Date.now()}`,
          name: input.name.trim(),
          phone: input.phone.trim(),
          address: input.address.trim() || 'Local Area',
          duePaise: Math.max(0, Math.round(input.openingDuePaise ?? 0)),
          lastTransactionAt: new Date().toISOString(),
        };
        state.customers.unshift(customer);
        saveState(state);
        return customer;
      },
      async recordPartialPayment(
        customerId: string,
        amountPaise: number,
        meta?: RecordPaymentMeta
      ) {
        const state = loadState();
        const idx = state.customers.findIndex((c) => c.id === customerId);
        if (idx === -1) throw new Error('Customer not found');

        const customer = state.customers[idx];
        const paid = Math.round(amountPaise);
        if (!Number.isFinite(paid) || paid <= 0) {
          throw new Error('Repayment amount must be greater than ₹0.');
        }
        if (paid > customer.duePaise) {
          throw new Error('Repayment amount cannot exceed the outstanding Udhaar balance.');
        }

        const method = meta?.paymentMethod ?? 'cash';
        const txRef =
          meta?.transactionRef?.trim() ||
          generateUpiTransactionRef(method === 'upi' ? 'UDHAAR' : 'CASH');

        // Duplicate confirmation guard
        if (state.confirmedRefs.includes(txRef)) {
          throw new Error('This payment reference has already been confirmed.');
        }

        const nowIso = new Date().toISOString();
        const previousDuePaise = customer.duePaise;
        const remainingDuePaise = Math.max(0, previousDuePaise - paid);

        const updatedCustomer: Customer = {
          ...customer,
          duePaise: remainingDuePaise,
          lastTransactionAt: nowIso,
        };
        state.customers[idx] = updatedCustomer;

        const payment: CustomerPaymentEntry = {
          id: `pay-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          customerId: customer.id,
          customerName: customer.name,
          amountPaise: paid,
          previousDuePaise,
          remainingDuePaise,
          paymentMethod: method,
          status: 'confirmed',
          transactionRef: txRef,
          utrNumber: meta?.utrNumber?.trim() || undefined,
          upiIdUsed: meta?.upiIdUsed?.trim() || undefined,
          isDemo: meta?.isDemo ?? true,
          createdAt: nowIso,
        };

        state.confirmedRefs.push(txRef);
        state.customerPayments.unshift(payment);
        saveState(state);
        return { customer: updatedCustomer, payment };
      },
      async recordPaymentAttempt(
        customerId: string,
        amountPaise: number,
        meta: RecordPaymentMeta
      ) {
        const state = loadState();
        const customer = state.customers.find((c) => c.id === customerId);
        if (!customer) throw new Error('Customer not found');

        const status = meta.status === 'failed' || meta.status === 'cancelled' ? meta.status : 'cancelled';
        const payment: CustomerPaymentEntry = {
          id: `pay-att-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          customerId: customer.id,
          customerName: customer.name,
          amountPaise: Math.max(0, Math.round(amountPaise)),
          previousDuePaise: customer.duePaise,
          remainingDuePaise: customer.duePaise, // Balance strictly unchanged for failed/cancelled attempts
          paymentMethod: meta.paymentMethod,
          status,
          transactionRef:
            meta.transactionRef?.trim() || generateUpiTransactionRef('UDHAAR'),
          upiIdUsed: meta.upiIdUsed?.trim() || undefined,
          isDemo: meta.isDemo ?? true,
          createdAt: new Date().toISOString(),
        };

        state.customerPayments.unshift(payment);
        saveState(state);
        return payment;
      },
    },

    forecast: {
      async getForecast(horizon: ForecastHorizon) {
        const state = loadState();
        const { days, seasonalFactor } = HORIZON_MULTIPLIERS[horizon];
        const supplierMap = new Map(state.suppliers.map((s) => [s.id, s]));

        const rows: ForecastRow[] = state.products.map((p) => {
          const supplier = supplierMap.get(p.supplierId);
          const hasSalesHistory = p.avgDailySales > 0;
          const forecastedDemand = hasSalesHistory
            ? Math.max(0, Math.round(p.avgDailySales * days * seasonalFactor))
            : 0;
          const safetyBuffer = hasSalesHistory
            ? Math.ceil(p.avgDailySales * (supplier?.leadTimeDays ?? 2))
            : 0;
          const recommendedOrderQty = p.stopReordering
            ? 0
            : hasSalesHistory
              ? Math.max(0, forecastedDemand + safetyBuffer - p.stockQty)
              : p.stockQty <= p.reorderLevel
                ? Math.max(0, Math.max(p.reorderLevel * 2, 10) - p.stockQty)
                : 0;
          const estimatedOrderCostPaise = recommendedOrderQty * p.costPaise;
          const estimatedLostSalesPaise = isStockoutFastMover(p)
            ? Math.round(p.avgDailySales * Math.min(days, 14)) * p.sellingPricePaise
            : 0;
          const daysOfCover =
            p.stockQty === 0
              ? 0
              : hasSalesHistory
                ? Math.round((p.stockQty / p.avgDailySales) * 10) / 10
                : 999;

          let status: ForecastRow['status'] = 'Healthy';
          if (p.stopReordering) status = 'Stopped';
          else if (p.stockQty === 0) status = 'Out of Stock';
          else if (p.stockQty <= p.reorderLevel) status = 'Low Stock';

          return {
            productId: p.id,
            sku: p.sku,
            name: p.name,
            category: p.category,
            supplierId: p.supplierId,
            supplierName: supplier?.name ?? 'Assigned Distributor',
            currentStock: p.stockQty,
            avgDailySales: p.avgDailySales,
            forecastedDemand,
            recommendedOrderQty,
            estimatedOrderCostPaise,
            estimatedLostSalesPaise,
            daysOfCover,
            status,
            stopReordering: p.stopReordering,
          };
        });

        // Sort Out of Stock & Low Stock fast movers to the top
        return rows.sort((a, b) => {
          const priority = { 'Out of Stock': 0, 'Low Stock': 1, Healthy: 2, Stopped: 3 };
          if (priority[a.status] !== priority[b.status]) {
            return priority[a.status] - priority[b.status];
          }
          return b.recommendedOrderQty - a.recommendedOrderQty;
        });
      },
      async getPurchaseOrders() {
        return loadState().purchaseOrders;
      },
      async createPurchaseOrder(items: Omit<PurchaseOrderItem, 'lineTotalPaise'>[]) {
        const state = loadState();
        const poItems: PurchaseOrderItem[] = items
          .filter((i) => i.qty > 0)
          .map((i) => ({
            ...i,
            qty: Math.round(i.qty),
            lineTotalPaise: Math.round(i.qty) * i.unitCostPaise,
          }));
        if (poItems.length === 0) throw new Error('PO cannot be empty');

        const totalPaise = poItems.reduce((sum, i) => sum + i.lineTotalPaise, 0);
        const po: PurchaseOrder = {
          id: `po-${Date.now()}`,
          poNumber: `PO-${new Date().getFullYear()}-${String(state.poSeq).padStart(3, '0')}`,
          createdAt: new Date().toISOString(),
          status: 'Ordered',
          items: poItems,
          totalPaise,
        };

        state.poSeq += 1;
        state.purchaseOrders.unshift(po);
        saveState(state);
        return po;
      },
    },

    reports: {
      async getSalesSummary() {
        const state = loadState();
        const todayStr = new Date().toDateString();

        let todayRevenuePaise = 0;
        let todayBillsCount = 0;
        let totalRevenuePaise = 0;
        let cashRevenuePaise = 0;
        let upiRevenuePaise = 0;
        let udhaarRevenuePaise = 0;
        let totalRescuedCashPaise = 0;

        const productAgg = new Map<string, { name: string; qtySold: number; revenuePaise: number }>();

        for (const sale of state.sales) {
          totalRevenuePaise += sale.totalPaise;
          totalRescuedCashPaise += sale.rescuedDeadStockPaise;
          if (sale.paymentMethod === 'cash') cashRevenuePaise += sale.totalPaise;
          if (sale.paymentMethod === 'upi') upiRevenuePaise += sale.totalPaise;
          if (sale.paymentMethod === 'udhaar') udhaarRevenuePaise += sale.totalPaise;

          if (new Date(sale.createdAt).toDateString() === todayStr) {
            todayRevenuePaise += sale.totalPaise;
            todayBillsCount += 1;
          }

          for (const line of sale.items) {
            const existing = productAgg.get(line.productId) ?? {
              name: line.name,
              qtySold: 0,
              revenuePaise: 0,
            };
            existing.qtySold += line.qty;
            existing.revenuePaise += line.lineTotalPaise;
            productAgg.set(line.productId, existing);
          }
        }

        // Build 7-day rolling series
        const dailySeries: SalesSummary['dailySeries'] = [];
        for (let i = 6; i >= 0; i--) {
          const d = new Date();
          d.setDate(d.getDate() - i);
          const dayStr = d.toDateString();
          const label = d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
          let rev = 0;
          let rescued = 0;
          for (const sale of state.sales) {
            if (new Date(sale.createdAt).toDateString() === dayStr) {
              rev += sale.totalPaise;
              rescued += sale.rescuedDeadStockPaise;
            }
          }
          dailySeries.push({
            label,
            revenueRupees: Math.round(rev / 100),
            rescuedRupees: Math.round(rescued / 100),
          });
        }

        const topProducts = Array.from(productAgg.entries())
          .map(([productId, data]) => ({ productId, ...data }))
          .sort((a, b) => b.revenuePaise - a.revenuePaise)
          .slice(0, 6);

        return {
          todayRevenuePaise,
          todayBillsCount,
          totalRevenuePaise,
          cashRevenuePaise,
          upiRevenuePaise,
          udhaarRevenuePaise,
          totalRescuedCashPaise,
          dailySeries,
          topProducts,
        };
      },

      async resetDemoData() {
        const seeded = buildSeedState();
        saveState(seeded);
      },
    },
  };
}
