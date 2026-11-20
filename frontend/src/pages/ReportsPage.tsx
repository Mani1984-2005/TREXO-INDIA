import {
  BookOpen,
  Coins,
  Download,
  IndianRupee,
  Printer,
  Receipt,
  RotateCcw,
  Wallet,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ReceiptModal } from '../components/ReceiptModal';
import {
  EmptyState,
  KpiCell,
  KpiStrip,
  PageHeader,
  SectionCard,
  SectionHeader,
  SegmentedTabs,
} from '../components/ui/DesignSystem';
import { useLedgerStore } from '../store/useLedgerStore';
import type { Sale } from '../types/domain';
import {
  formatINR,
  isDeadStock,
  isLowStock,
  isSameLocalDay,
  isWithinLocalDays,
} from '../utils/money';
import { buildSalesReportCsv } from '../utils/reports';

type ReportRange = 'all' | 'today' | '7d' | '30d';

export function ReportsPage() {
  const [range, setRange] = useState<ReportRange>('all');
  const [selectedSale, setSelectedSale] = useState<Sale | null>(null);
  const [confirmingReset, setConfirmingReset] = useState(false);

  const salesSummary = useLedgerStore((s) => s.salesSummary);
  const sales = useLedgerStore((s) => s.sales);
  const products = useLedgerStore((s) => s.products);
  const customers = useLedgerStore((s) => s.customers);
  const customerPayments = useLedgerStore((s) => s.customerPayments);
  const supplierReturns = useLedgerStore((s) => s.supplierReturns);
  const resetDemoData = useLedgerStore((s) => s.resetDemoData);
  const pushToast = useLedgerStore((s) => s.pushToast);

  const filteredSales = useMemo(() => {
    if (range === 'all') return sales;
    return sales.filter((s) => {
      if (range === 'today') return isSameLocalDay(s.createdAt);
      if (range === '7d') return isWithinLocalDays(s.createdAt, 7);
      return isWithinLocalDays(s.createdAt, 30);
    });
  }, [sales, range]);

  const filteredRepayments = useMemo(() => {
    const confirmed = customerPayments.filter((p) => p.status === 'confirmed');
    if (range === 'all') return confirmed;
    return confirmed.filter((p) => {
      if (range === 'today') return isSameLocalDay(p.createdAt);
      if (range === '7d') return isWithinLocalDays(p.createdAt, 7);
      return isWithinLocalDays(p.createdAt, 30);
    });
  }, [customerPayments, range]);

  const reportMetrics = useMemo(() => {
    let totalRevenuePaise = 0;
    let cashPaise = 0;
    let upiPaise = 0;
    let udhaarPaise = 0;
    let rescuedPaise = 0;
    const productStats = new Map<
      string,
      { productId: string; name: string; qtySold: number; revenuePaise: number }
    >();

    for (const s of filteredSales) {
      totalRevenuePaise += s.totalPaise;
      rescuedPaise += s.rescuedDeadStockPaise;
      if (s.paymentMethod === 'cash') cashPaise += s.totalPaise;
      else if (s.paymentMethod === 'upi') upiPaise += s.totalPaise;
      else udhaarPaise += s.totalPaise;

      for (const item of s.items) {
        const prev = productStats.get(item.productId) ?? {
          productId: item.productId,
          name: item.name,
          qtySold: 0,
          revenuePaise: 0,
        };
        prev.qtySold += item.qty;
        prev.revenuePaise += item.lineTotalPaise;
        productStats.set(item.productId, prev);
      }
    }

    const topProducts = Array.from(productStats.values())
      .sort((a, b) => b.revenuePaise - a.revenuePaise)
      .slice(0, 6);

    const inventoryCostValuePaise = products.reduce(
      (sum, p) => sum + p.costPaise * p.stockQty,
      0
    );
    const deadStockCount = products.filter((p) => isDeadStock(p)).length;
    const lowStockCount = products.filter((p) => isLowStock(p)).length;
    const totalUdhaarDuePaise = customers.reduce((sum, c) => sum + c.duePaise, 0);
    const confirmedRepaymentsPaise = customerPayments
      .filter((p) => p.status === 'confirmed')
      .reduce((sum, p) => sum + p.amountPaise, 0);

    let periodRepaymentCashPaise = 0;
    let periodRepaymentUpiPaise = 0;
    for (const rep of filteredRepayments) {
      if (rep.paymentMethod === 'cash') periodRepaymentCashPaise += rep.amountPaise;
      else periodRepaymentUpiPaise += rep.amountPaise;
    }
    const periodRepaymentsTotalPaise = periodRepaymentCashPaise + periodRepaymentUpiPaise;
    const supplierReturnCreditPaise = supplierReturns.reduce(
      (sum, r) => sum + r.totalCreditPaise,
      0
    );

    return {
      totalRevenuePaise,
      cashPaise,
      upiPaise,
      udhaarPaise,
      rescuedPaise,
      topProducts,
      inventoryCostValuePaise,
      deadStockCount,
      lowStockCount,
      totalUdhaarDuePaise,
      confirmedRepaymentsPaise,
      periodRepaymentCashPaise,
      periodRepaymentUpiPaise,
      periodRepaymentsTotalPaise,
      supplierReturnCreditPaise,
    };
  }, [filteredSales, filteredRepayments, products, customers, customerPayments, supplierReturns]);

  const handleExportCsv = () => {
    if (filteredSales.length === 0) {
      pushToast('Nothing to export', 'No bills recorded in the selected date range.', 'amber');
      return;
    }
    const csv = buildSalesReportCsv(filteredSales);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `trexo-sales-report-${range}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    pushToast('Report exported', `${filteredSales.length} bills saved as CSV.`, 'emerald');
  };

  const handleConfirmReset = async () => {
    await resetDemoData();
    setConfirmingReset(false);
  };

  const totalPaymentBasis = Math.max(1, reportMetrics.totalRevenuePaise);
  const cashPct = Math.round((reportMetrics.cashPaise / totalPaymentBasis) * 100);
  const upiPct = Math.round((reportMetrics.upiPaise / totalPaymentBasis) * 100);
  const udhaarPct = Math.max(0, 100 - cashPct - upiPct);

  return (
    <div className="space-y-6 trexo-fade-in">
      <PageHeader
        title="Store Reports & Exports"
        description="Analyze sales by payment mode, inspect top-selling staples, review inventory and Udhaar health, and export CSV records."
        actions={
          <>
            <SegmentedTabs
              value={range}
              onChange={setRange}
              ariaLabel="Report date range"
              options={[
                { id: 'all', label: 'All Time' },
                { id: 'today', label: 'Today' },
                { id: '7d', label: '7 Days' },
                { id: '30d', label: '30 Days' },
              ]}
            />
            <button
              type="button"
              onClick={handleExportCsv}
              className="min-h-[40px] inline-flex items-center gap-1.5 rounded-lg bg-[#145C3A] px-4 py-2 text-xs sm:text-sm font-semibold text-white hover:bg-[#103D2B] transition-colors whitespace-nowrap shadow-[0_1px_2px_rgba(16,61,43,0.16)]"
            >
              <Download className="h-4 w-4" />
              <span>Export CSV</span>
            </button>
          </>
        }
      />

      {/* Revenue Breakdown Strip */}
      <KpiStrip columns={4} ariaLabel="Sales report summary" className="no-print">
        <KpiCell
          label="Recorded Counter Sales"
          value={formatINR(reportMetrics.totalRevenuePaise)}
          icon={<IndianRupee className="h-3.5 w-3.5" />}
          caption={`${filteredSales.length} completed ${filteredSales.length === 1 ? 'bill' : 'bills'}`}
        />
        <KpiCell
          label="Cash & UPI Collected"
          value={formatINR(reportMetrics.cashPaise + reportMetrics.upiPaise)}
          icon={<Wallet className="h-3.5 w-3.5" />}
          caption={`Cash ${formatINR(reportMetrics.cashPaise)} · UPI ${formatINR(reportMetrics.upiPaise)}`}
          tone="emerald"
        />
        <KpiCell
          label="Udhaar Credit Billed"
          value={formatINR(reportMetrics.udhaarPaise)}
          icon={<BookOpen className="h-3.5 w-3.5" />}
          caption={`Current ledger due: ${formatINR(reportMetrics.totalUdhaarDuePaise)}`}
          tone={reportMetrics.udhaarPaise > 0 ? 'amber' : 'default'}
        />
        <KpiCell
          label="Dead-Stock Cash Unlocked"
          value={formatINR(reportMetrics.rescuedPaise)}
          icon={<Coins className="h-3.5 w-3.5" />}
          caption="Cleared through counter billing"
          tone="emerald"
        />
      </KpiStrip>

      {/* Payment Mode + Inventory & Udhaar Health Row */}
      <div className="no-print grid grid-cols-1 lg:grid-cols-12 gap-6">
        <SectionCard className="lg:col-span-6 p-5 space-y-4">
          <div>
            <h2 className="text-sm font-semibold text-[#172B22]">Payment Mode Breakdown</h2>
            <p className="text-xs text-[#65766D] mt-0.5">
              Share of Cash, UPI, and Udhaar billing for selected range
            </p>
          </div>
          <div className="space-y-3.5">
            {[
              {
                label: 'Cash',
                amount: reportMetrics.cashPaise,
                pct: reportMetrics.totalRevenuePaise > 0 ? cashPct : 0,
                bar: 'bg-[#103D2B]',
              },
              {
                label: 'UPI (GPay / PhonePe / Paytm)',
                amount: reportMetrics.upiPaise,
                pct: reportMetrics.totalRevenuePaise > 0 ? upiPct : 0,
                bar: 'bg-[#145C3A]',
              },
              {
                label: 'Udhaar (Credit)',
                amount: reportMetrics.udhaarPaise,
                pct: reportMetrics.totalRevenuePaise > 0 ? udhaarPct : 0,
                bar: 'bg-[#C6A15B]',
              },
            ].map((row) => (
              <div key={row.label} className="space-y-1.5">
                <div className="flex items-center justify-between gap-2 text-xs">
                  <span className="font-medium text-[#172B22]">{row.label}</span>
                  <span className="font-mono font-semibold text-[#103D2B] tabular-nums">
                    {formatINR(row.amount)} ({row.pct}%)
                  </span>
                </div>
                <div className="h-2 w-full rounded-full bg-[#F3F5F2] overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-200 ${row.bar}`}
                    style={{ width: `${row.pct}%` }}
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="border-t border-[#E5EAE5] pt-3.5 space-y-1.5">
            <div className="flex items-center justify-between gap-2 text-xs">
              <span className="font-semibold text-[#172B22]">
                Udhaar Repayments Collected (Selected Period)
              </span>
              <span className="font-mono font-bold text-[#145C3A] tabular-nums">
                {formatINR(reportMetrics.periodRepaymentsTotalPaise)}
              </span>
            </div>
            <p className="text-[11px] text-[#65766D] font-mono tabular-nums leading-relaxed">
              Cash {formatINR(reportMetrics.periodRepaymentCashPaise)} · UPI{' '}
              {formatINR(reportMetrics.periodRepaymentUpiPaise)} ({filteredRepayments.length}{' '}
              {filteredRepayments.length === 1 ? 'receipt' : 'receipts'}) — tracked separately from
              Counter Sales to prevent double-counting.
            </p>
          </div>
        </SectionCard>

        <SectionCard variant="warm" className="lg:col-span-6 p-5 space-y-3.5">
          <div>
            <h2 className="text-sm font-semibold text-[#103D2B]">
              Inventory &amp; Udhaar Health Summary
            </h2>
            <p className="text-xs text-[#52635B] mt-0.5">
              Current store snapshot across all products and accounts
            </p>
          </div>
          <dl className="divide-y divide-[#E4DCC6] text-xs">
            <div className="py-2.5 flex items-center justify-between gap-3">
              <dt className="text-[#52635B]">Active Shelf Stock Cost Value</dt>
              <dd className="font-mono font-bold text-[#103D2B] tabular-nums">
                {formatINR(reportMetrics.inventoryCostValuePaise)}
              </dd>
            </div>
            <div className="py-2.5 flex items-center justify-between gap-3">
              <dt className="text-[#52635B]">Dead Stock / Low Stock SKUs</dt>
              <dd className="font-mono font-semibold text-[#172B22] tabular-nums">
                {reportMetrics.deadStockCount} dead · {reportMetrics.lowStockCount} low/out
              </dd>
            </div>
            <div className="py-2.5 flex items-center justify-between gap-3">
              <dt className="text-[#52635B]">Outstanding Udhaar Receivable</dt>
              <dd className="font-mono font-bold text-red-700 tabular-nums">
                {formatINR(reportMetrics.totalUdhaarDuePaise)}
              </dd>
            </div>
            <div className="py-2.5 flex items-center justify-between gap-3">
              <dt className="text-[#52635B]">Total Udhaar Repayments (All Time)</dt>
              <dd className="font-mono font-bold text-[#145C3A] tabular-nums">
                {formatINR(reportMetrics.confirmedRepaymentsPaise)}
              </dd>
            </div>
            <div className="py-2.5 flex items-center justify-between gap-3">
              <dt className="text-[#52635B]">Pending Supplier Return Credits</dt>
              <dd className="font-mono font-bold text-[#103D2B] tabular-nums">
                {formatINR(reportMetrics.supplierReturnCreditPaise)}
              </dd>
            </div>
          </dl>
        </SectionCard>
      </div>

      {/* Chart + Top Products Split */}
      <div className="no-print grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <SectionCard className="lg:col-span-7">
          <SectionHeader
            title="7-Day Counter Revenue"
            subtitle="Daily sales and rescued dead-stock revenue (₹)"
          />
          <div className="p-5">
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={salesSummary?.dailySeries ?? []}
                  margin={{ top: 8, right: 8, left: -10, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#E5EAE5" vertical={false} />
                  <XAxis
                    dataKey="label"
                    tick={{ fill: '#65766D', fontSize: 11 }}
                    axisLine={{ stroke: '#E5EAE5' }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: '#65766D', fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) => `₹${v}`}
                  />
                  <Tooltip
                    cursor={{ fill: '#FAF7EF' }}
                    formatter={(value: unknown) => `₹${Number(value).toLocaleString('en-IN')}`}
                    contentStyle={{
                      borderRadius: '10px',
                      border: '1px solid #E5EAE5',
                      boxShadow: '0 6px 20px rgba(16, 61, 43, 0.08)',
                      fontSize: '12px',
                      color: '#172B22',
                    }}
                  />
                  <Bar
                    dataKey="revenueRupees"
                    name="Total Sales (₹)"
                    fill="#103D2B"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={28}
                  />
                  <Bar
                    dataKey="rescuedRupees"
                    name="Rescued Dead Stock (₹)"
                    fill="#C6A15B"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={28}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </SectionCard>

        <SectionCard className="lg:col-span-5">
          <SectionHeader
            title="Top Selling Items"
            subtitle="Ranked by sales value in selected period"
          />
          {reportMetrics.topProducts.length === 0 ? (
            <EmptyState
              icon={<Receipt className="h-5 w-5" />}
              title="No items sold in this period"
              description="Switch the report date range or record counter sales to see top performers."
              className="py-9"
            />
          ) : (
            <div className="divide-y divide-[#E5EAE5]">
              {reportMetrics.topProducts.map((item, idx) => (
                <div
                  key={item.productId}
                  className="px-5 py-3.5 flex items-center justify-between gap-3 hover:bg-[#FAF7EF]/45 transition-colors"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="font-mono text-xs font-semibold text-[#718078] w-4 shrink-0 tabular-nums">
                      {idx + 1}.
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-[#172B22] truncate">{item.name}</p>
                      <p className="text-xs text-[#65766D] font-mono tabular-nums">
                        {item.qtySold} {item.qtySold === 1 ? 'unit' : 'units'} sold
                      </p>
                    </div>
                  </div>
                  <span className="font-mono text-sm font-bold text-[#103D2B] tabular-nums shrink-0">
                    {formatINR(item.revenuePaise)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </SectionCard>
      </div>

      {/* Counter Receipts Table (lg+) & Responsive Card Grid (< lg) */}
      <SectionCard className="no-print">
        <SectionHeader
          title={`Counter Receipts (${filteredSales.length})`}
          subtitle="Saved locally on this device · Click Reprint to view or print any bill"
        />

        {filteredSales.length === 0 ? (
          <EmptyState
            icon={<Receipt className="h-5 w-5" />}
            title="No counter bills in this range"
            description="Complete a bill on the Counter or switch to All Time to view recorded receipts."
            className="py-10"
          />
        ) : (
          <>
            <div className="hidden lg:block overflow-x-auto trexo-scroll">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-[#E5EAE5] bg-[#FAF7EF] text-xs font-semibold text-[#52635B]">
                    <th className="px-5 py-3">Invoice</th>
                    <th className="px-4 py-3">Date &amp; Time</th>
                    <th className="px-4 py-3">Customer</th>
                    <th className="px-4 py-3">Payment</th>
                    <th className="px-4 py-3 text-right">Amount</th>
                    <th className="px-5 py-3 text-right">Receipt</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5EAE5]">
                  {filteredSales.map((sale) => (
                    <tr key={sale.id} className="hover:bg-[#FAF7EF]/50 transition-colors">
                      <td className="px-5 py-3.5 font-mono font-semibold text-[#172B22]">
                        {sale.invoiceNo}
                        {sale.rescuedDeadStockPaise > 0 && (
                          <p className="font-sans text-[11px] font-medium text-[#145C3A]">
                            Includes cash rescue ({formatINR(sale.rescuedDeadStockPaise)})
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3.5 text-xs text-[#65766D] whitespace-nowrap">
                        {new Date(sale.createdAt).toLocaleString('en-IN', {
                          day: '2-digit',
                          month: 'short',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </td>
                      <td className="px-4 py-3.5 text-[#172B22]">
                        {sale.customerName ?? 'Walk-in Customer'}
                      </td>
                      <td className="px-4 py-3.5 text-xs text-[#52635B]">
                        <span className="uppercase font-semibold text-[#172B22]">
                          {sale.paymentMethod}
                        </span>
                        {sale.upiTransactionRef && (
                          <p className="font-mono text-[11px] text-[#65766D] truncate max-w-[160px]">
                            {sale.upiTransactionRef}
                            {sale.isDemoPayment ? ' · DEMO' : ''}
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3.5 text-right font-mono font-bold text-[#103D2B] tabular-nums whitespace-nowrap">
                        {formatINR(sale.totalPaise)}
                      </td>
                      <td className="px-5 py-3.5 text-right whitespace-nowrap">
                        <button
                          type="button"
                          onClick={() => setSelectedSale(sale)}
                          className="inline-flex items-center gap-1 rounded-md border border-[#E5EAE5] bg-white px-2.5 py-1.5 text-xs font-semibold text-[#145C3A] hover:bg-[#FAF7EF] hover:border-[#145C3A] transition-colors whitespace-nowrap"
                        >
                          <Printer className="h-3.5 w-3.5" />
                          <span>Reprint</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="lg:hidden grid grid-cols-1 md:grid-cols-2 gap-px bg-[#E5EAE5]">
              {filteredSales.map((sale) => (
                <div key={sale.id} className="bg-white p-4 space-y-2.5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-mono text-sm font-bold text-[#172B22]">{sale.invoiceNo}</p>
                      <p className="text-xs text-[#65766D] truncate mt-0.5">
                        {sale.customerName ?? 'Walk-in Customer'} ·{' '}
                        {new Date(sale.createdAt).toLocaleString('en-IN', {
                          day: '2-digit',
                          month: 'short',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </p>
                    </div>
                    <span className="font-mono text-sm font-bold text-[#103D2B] tabular-nums shrink-0">
                      {formatINR(sale.totalPaise)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-2 text-xs pt-1 border-t border-[#E5EAE5]/70">
                    <span className="text-[#52635B] truncate">
                      <span className="uppercase font-semibold text-[#172B22]">
                        {sale.paymentMethod}
                      </span>
                      {sale.upiTransactionRef ? ` · ${sale.upiTransactionRef}` : ''}
                    </span>
                    <button
                      type="button"
                      onClick={() => setSelectedSale(sale)}
                      className="min-h-[34px] inline-flex items-center gap-1 rounded-md border border-[#E5EAE5] bg-white px-2.5 py-1 text-xs font-semibold text-[#145C3A] hover:border-[#145C3A] whitespace-nowrap shrink-0"
                    >
                      <Printer className="h-3.5 w-3.5" />
                      <span>Reprint</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </SectionCard>

      {/* Demo Data Reset Utility */}
      <SectionCard className="no-print p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-[#172B22]">Reset Local Demo Data</h3>
          <p className="mt-0.5 text-xs text-[#65766D]">
            Restores all seeded products, dead-stock items, Udhaar balances, and sales history in
            localStorage.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {confirmingReset ? (
            <>
              <button
                type="button"
                onClick={() => setConfirmingReset(false)}
                className="min-h-[38px] rounded-lg border border-[#D4DDD6] bg-white px-3.5 py-2 text-xs font-medium text-[#172B22] hover:bg-[#FAF7EF] transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmReset}
                className="min-h-[38px] rounded-lg bg-red-700 px-3.5 py-2 text-xs font-semibold text-white hover:bg-red-800 transition-colors"
              >
                Confirm Reset
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmingReset(true)}
              className="min-h-[38px] inline-flex items-center gap-1.5 rounded-lg border border-[#D4DDD6] bg-white px-4 py-2 text-xs font-semibold text-[#172B22] hover:bg-[#FAF7EF] transition-colors whitespace-nowrap"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span>Reset Demo Data</span>
            </button>
          )}
        </div>
      </SectionCard>

      <ReceiptModal sale={selectedSale} onClose={() => setSelectedSale(null)} />
    </div>
  );
}
