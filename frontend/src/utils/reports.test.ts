import { describe, expect, it } from 'vitest';
import type { Sale } from '../types/domain';
import { buildSalesReportCsv } from './reports';

describe('buildSalesReportCsv', () => {
  it('formats headers, INR currency values, UPI refs, and escapes quoted customer names', () => {
    const sampleSales: Sale[] = [
      {
        id: 'sale-1',
        invoiceNo: 'TRX-1001',
        createdAt: '2026-11-19T06:30:00.000Z',
        items: [
          {
            productId: 'prod-1',
            sku: 'GRN-001',
            name: 'Aashirvaad Atta 5kg',
            unit: '5 kg',
            qty: 2,
            unitPricePaise: 25500,
            originalPricePaise: 25500,
            costPaise: 22000,
            isDeadStockRescued: false,
            lineTotalPaise: 51000,
          },
        ],
        subtotalPaise: 51000,
        discountSavedPaise: 0,
        totalPaise: 51000,
        paymentMethod: 'upi',
        customerId: null,
        customerName: 'Ramesh "Raju" Kulkarni',
        rescuedDeadStockPaise: 0,
        upiTransactionRef: 'TRX-BILL-20261119-AB12',
      },
      {
        id: 'sale-2',
        invoiceNo: 'TRX-1002',
        createdAt: '2026-11-19T07:15:00.000Z',
        items: [
          {
            productId: 'prod-9',
            sku: 'DRY-009',
            name: 'Organic Quinoa 500g',
            unit: '500 g',
            qty: 1,
            unitPricePaise: 24950,
            originalPricePaise: 32000,
            costPaise: 21000,
            isDeadStockRescued: true,
            lineTotalPaise: 24950,
          },
        ],
        subtotalPaise: 32000,
        discountSavedPaise: 7050,
        totalPaise: 24950,
        paymentMethod: 'cash',
        customerId: null,
        customerName: null,
        rescuedDeadStockPaise: 24950,
      },
    ];

    const csv = buildSalesReportCsv(sampleSales);
    const lines = csv.split('\n');

    expect(lines).toHaveLength(3);
    expect(lines[0]).toBe(
      'Invoice No,Date,Customer,Payment Mode,UPI Ref,Items Count,Total (INR),Rescued Cash (INR)'
    );
    expect(lines[1]).toBe(
      'TRX-1001,2026-11-19T06:30:00.000Z,"Ramesh ""Raju"" Kulkarni",UPI,TRX-BILL-20261119-AB12,2,510.00,0.00'
    );
    expect(lines[2]).toBe(
      'TRX-1002,2026-11-19T07:15:00.000Z,"Walk-in Customer",CASH,,1,249.50,249.50'
    );
  });
});
