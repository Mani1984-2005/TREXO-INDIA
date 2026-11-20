import type { Sale } from '../types/domain';

/**
 * Generates a RFC-4180 compliant CSV string for counter sales reports.
 * Always matches the exact filtered sales array shown in ReportsPage.
 */
export function buildSalesReportCsv(sales: Sale[]): string {
  const header = [
    'Invoice No',
    'Date',
    'Customer',
    'Payment Mode',
    'UPI Ref',
    'Items Count',
    'Total (INR)',
    'Rescued Cash (INR)',
  ];

  const rows = sales.map((s) => [
    s.invoiceNo,
    new Date(s.createdAt).toISOString(),
    `"${(s.customerName ?? 'Walk-in Customer').replace(/"/g, '""')}"`,
    s.paymentMethod.toUpperCase(),
    s.upiTransactionRef ?? '',
    String(s.items.reduce((acc, i) => acc + i.qty, 0)),
    (s.totalPaise / 100).toFixed(2),
    (s.rescuedDeadStockPaise / 100).toFixed(2),
  ]);

  return [header.join(','), ...rows.map((r) => r.join(','))].join('\n');
}
