import {
  AlertTriangle,
  ArrowUpRight,
  Banknote,
  BookOpen,
  CheckCircle2,
  Coins,
  IndianRupee,
  Package,
  QrCode,
  Receipt,
  RefreshCw,
  ShoppingCart,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { PaymentReceipt } from '../components/payments/PaymentReceipt';
import { ReceiptModal } from '../components/ReceiptModal';
import {
  EmptyState,
  KpiCell,
  KpiStrip,
  PageHeader,
  SectionCard,
  SectionHeader,
} from '../components/ui/DesignSystem';
import { STORE_INFO } from '../config';
import { TRANSLATIONS } from '../i18n/translations';
import { useLedgerStore } from '../store/useLedgerStore';
import type { CustomerPaymentEntry, Sale } from '../types/domain';
import {
  daysSince,
  daysUntil,
  formatINR,
  isDeadStock,
  isNearExpiry,
  isSameLocalDay,
  isStockoutFastMover,
} from '../utils/money';

type ActivityItem =
  | {
      id: string;
      kind: 'sale';
      createdAt: string;
      title: string;
      subtitle: string;
      methodLabel: string;
      amountPaise: number;
      sale: Sale;
    }
  | {
      id: string;
      kind: 'repayment';
      createdAt: string;
      title: string;
      subtitle: string;
      methodLabel: string;
      amountPaise: number;
      payment: CustomerPaymentEntry;
    };

function getTimeGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

export function DashboardPage() {
  const navigate = useNavigate();
  const language = useLedgerStore((s) => s.language);
  const products = useLedgerStore((s) => s.products);
  const sales = useLedgerStore((s) => s.sales);
  const salesSummary = useLedgerStore((s) => s.salesSummary);
  const customers = useLedgerStore((s) => s.customers);
  const customerPayments = useLedgerStore((s) => s.customerPayments);
  const supplierReturns = useLedgerStore((s) => s.supplierReturns);

  const [previewSale, setPreviewSale] = useState<Sale | null>(null);
  const [previewPayment, setPreviewPayment] = useState<CustomerPaymentEntry | null>(null);

  const t = TRANSLATIONS[language];

  const metrics = useMemo(() => {
    const todaySales = sales.filter((s) => isSameLocalDay(s.createdAt));
    const todaySalesPaise =
      salesSummary?.todayRevenuePaise ?? todaySales.reduce((acc, s) => acc + s.totalPaise, 0);
    const todayBillsCount = salesSummary?.todayBillsCount ?? todaySales.length;

    const outOfStock = products.filter((p) => p.stockQty <= 0);
    const lowStock = products.filter((p) => p.stockQty > 0 && p.stockQty <= p.reorderLevel);
    const deadStock = products.filter((p) => isDeadStock(p));
    const nearExpiry = products.filter((p) => isNearExpiry(p));
    const stockoutFastMovers = products.filter((p) => isStockoutFastMover(p));

    const deadStockValuePaise = deadStock.reduce(
      (acc, p) => acc + p.costPaise * p.stockQty,
      0
    );

    const totalUdhaarPaise = customers.reduce((acc, c) => acc + c.duePaise, 0);
    const activeUdhaarCount = customers.filter((c) => c.duePaise > 0).length;

    const confirmedRepayments = customerPayments.filter((p) => p.status === 'confirmed');
    const cashSalesPaise = sales
      .filter((s) => s.paymentMethod === 'cash')
      .reduce((acc, s) => acc + s.totalPaise, 0);
    const upiSalesPaise = sales
      .filter((s) => s.paymentMethod === 'upi')
      .reduce((acc, s) => acc + s.totalPaise, 0);
    const cashRepaymentsPaise = confirmedRepayments
      .filter((p) => p.paymentMethod === 'cash')
      .reduce((acc, p) => acc + p.amountPaise, 0);
    const upiRepaymentsPaise = confirmedRepayments
      .filter((p) => p.paymentMethod === 'upi')
      .reduce((acc, p) => acc + p.amountPaise, 0);

    const totalCashInflowPaise = cashSalesPaise + cashRepaymentsPaise;
    const totalUpiInflowPaise = upiSalesPaise + upiRepaymentsPaise;
    const totalCollectedPaise = totalCashInflowPaise + totalUpiInflowPaise;
    const cashSharePct =
      totalCollectedPaise > 0
        ? Math.round((totalCashInflowPaise / totalCollectedPaise) * 100)
        : 0;
    const upiSharePct = totalCollectedPaise > 0 ? 100 - cashSharePct : 0;

    const returnCreditPaise = supplierReturns.reduce((acc, r) => acc + r.totalCreditPaise, 0);

    return {
      todaySalesPaise,
      todayBillsCount,
      totalProducts: products.length,
      inStockProducts: products.length - outOfStock.length,
      lowAndOutCount: outOfStock.length + lowStock.length,
      outOfStockCount: outOfStock.length,
      lowStockCount: lowStock.length,
      deadStockCount: deadStock.length,
      nearExpiryCount: nearExpiry.length,
      deadStockValuePaise,
      stockoutFastMovers,
      deadOrExpiryItems: [...deadStock, ...nearExpiry.filter((p) => !isDeadStock(p))].slice(0, 4),
      totalUdhaarPaise,
      activeUdhaarCount,
      totalCashInflowPaise,
      totalUpiInflowPaise,
      totalCollectedPaise,
      cashSharePct,
      upiSharePct,
      returnCreditPaise,
    };
  }, [products, sales, salesSummary, customers, customerPayments, supplierReturns]);

  const dailyChartData = useMemo(() => {
    return (salesSummary?.dailySeries ?? []).map((row) => ({
      day: row.label,
      sales: Math.round(row.revenueRupees),
      rescued: Math.round(row.rescuedRupees),
    }));
  }, [salesSummary]);

  const recentActivity = useMemo<ActivityItem[]>(() => {
    const saleItems: ActivityItem[] = sales.slice(0, 8).map((s) => ({
      id: `sale-${s.id}`,
      kind: 'sale',
      createdAt: s.createdAt,
      title: `Bill ${s.invoiceNo}`,
      subtitle: `${s.customerName ?? 'Walk-in Customer'} · ${s.items.reduce((a, i) => a + i.qty, 0)} items`,
      methodLabel:
        s.paymentMethod === 'upi'
          ? s.isDemoPayment
            ? 'UPI · Demo'
            : 'UPI'
          : s.paymentMethod === 'udhaar'
            ? 'Udhaar'
            : 'Cash',
      amountPaise: s.totalPaise,
      sale: s,
    }));

    const paymentItems: ActivityItem[] = customerPayments
      .filter((p) => p.status === 'confirmed')
      .slice(0, 8)
      .map((p) => ({
        id: `pay-${p.id}`,
        kind: 'repayment',
        createdAt: p.createdAt,
        title: `Udhaar Repayment · ${p.customerName}`,
        subtitle: `Ref ${p.transactionRef}${p.utrNumber ? ` · UTR ${p.utrNumber}` : ''}`,
        methodLabel:
          p.paymentMethod === 'upi' ? (p.isDemo ? 'UPI · Demo' : 'UPI') : 'Cash',
        amountPaise: p.amountPaise,
        payment: p,
      }));

    return [...saleItems, ...paymentItems]
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      .slice(0, 8);
  }, [sales, customerPayments]);

  const todayFormatted = new Date().toLocaleDateString('en-IN', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });

  const greeting = getTimeGreeting();

  return (
    <div className="space-y-6 trexo-fade-in">
      <PageHeader
        eyebrow={`${greeting} · ${todayFormatted}`}
        title={STORE_INFO.shopName}
        description={`${STORE_INFO.location} · ${metrics.todayBillsCount} ${
          metrics.todayBillsCount === 1 ? 'bill' : 'bills'
        } today · ${metrics.lowAndOutCount} stock ${
          metrics.lowAndOutCount === 1 ? 'alert' : 'alerts'
        } · ${metrics.activeUdhaarCount} active Udhaar ${
          metrics.activeUdhaarCount === 1 ? 'account' : 'accounts'
        }.`}
        actions={
          <>
            <button
              type="button"
              onClick={() => navigate('/customers')}
              className="min-h-[42px] inline-flex items-center gap-2 rounded-lg border border-[#E5EAE5] bg-white px-4 py-2 text-sm font-medium text-[#172B22] hover:bg-[#FAF7EF] hover:border-[#C6A15B]/60 transition-colors whitespace-nowrap"
            >
              <BookOpen className="h-4 w-4 text-[#145C3A]" />
              <span>Udhaar Ledger</span>
            </button>
            <button
              type="button"
              onClick={() => navigate('/counter')}
              className="min-h-[42px] inline-flex items-center gap-2 rounded-lg bg-[#145C3A] px-4 py-2 text-sm font-semibold text-white hover:bg-[#103D2B] transition-colors whitespace-nowrap shadow-[0_1px_2px_rgba(16,61,43,0.16)]"
            >
              <ShoppingCart className="h-4 w-4" />
              <span>New Counter Bill</span>
            </button>
          </>
        }
      />

      {/* 6-KPI Executive Financial Strip (3x2 balanced grid on desktop) */}
      <KpiStrip columns={6} ariaLabel="Store Key Performance Indicators">
        <KpiCell
          label={t.todaySalesLabel}
          value={formatINR(metrics.todaySalesPaise)}
          icon={<IndianRupee className="h-3.5 w-3.5" />}
          caption={`${metrics.todayBillsCount} ${
            metrics.todayBillsCount === 1 ? 'bill' : 'bills'
          } recorded today`}
          tone="emerald"
        />
        <KpiCell
          label="Cash Collected"
          value={formatINR(metrics.totalCashInflowPaise)}
          icon={<Banknote className="h-3.5 w-3.5" />}
          caption="Counter cash bills & Udhaar repayments"
        />
        <KpiCell
          label="UPI Collected"
          value={formatINR(metrics.totalUpiInflowPaise)}
          icon={<QrCode className="h-3.5 w-3.5" />}
          caption="Counter UPI bills & Udhaar repayments"
          tone="emerald"
        />
        <KpiCell
          label="Total Udhaar Due"
          value={formatINR(metrics.totalUdhaarPaise)}
          icon={<BookOpen className="h-3.5 w-3.5" />}
          caption={`${metrics.activeUdhaarCount} ${
            metrics.activeUdhaarCount === 1 ? 'account' : 'accounts'
          } with balance`}
          tone={metrics.totalUdhaarPaise > 0 ? 'crimson' : 'emerald'}
          action={
            <button
              type="button"
              onClick={() => navigate('/customers')}
              className="inline-flex items-center gap-0.5 font-semibold text-[#145C3A] hover:text-[#103D2B] whitespace-nowrap"
            >
              <span>Collect</span>
              <ArrowUpRight className="h-3.5 w-3.5" />
            </button>
          }
        />
        <KpiCell
          label="Low Stock Alerts"
          value={String(metrics.lowAndOutCount)}
          icon={<AlertTriangle className="h-3.5 w-3.5" />}
          caption={`${metrics.outOfStockCount} out of stock · ${metrics.lowStockCount} low`}
          tone={metrics.lowAndOutCount > 0 ? 'amber' : 'emerald'}
          action={
            <button
              type="button"
              onClick={() => navigate('/restock')}
              className="inline-flex items-center gap-0.5 font-semibold text-amber-700 hover:text-amber-900 whitespace-nowrap"
            >
              <span>Restock</span>
              <ArrowUpRight className="h-3.5 w-3.5" />
            </button>
          }
        />
        <KpiCell
          label="Total Products"
          value={String(metrics.totalProducts)}
          icon={<Package className="h-3.5 w-3.5" />}
          caption={`${metrics.inStockProducts} active in stock`}
          action={
            <button
              type="button"
              onClick={() => navigate('/inventory')}
              className="inline-flex items-center gap-0.5 font-semibold text-[#145C3A] hover:text-[#103D2B] whitespace-nowrap"
            >
              <span>Manage</span>
              <ArrowUpRight className="h-3.5 w-3.5" />
            </button>
          }
        />
      </KpiStrip>

      {/* Main Analytics + Financial Snapshot Split */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left 7 Cols: 7-Day Revenue Chart + Quick Operations */}
        <div className="lg:col-span-7 space-y-6">
          <SectionCard>
            <SectionHeader
              title="7-Day Sales & Cash Rescued"
              subtitle="Daily counter billing alongside cash unlocked from slow-moving shelf stock"
              action={
                <button
                  type="button"
                  onClick={() => navigate('/reports')}
                  className="inline-flex items-center gap-1 text-xs font-semibold text-[#145C3A] hover:text-[#103D2B] whitespace-nowrap"
                >
                  <span>Full Reports</span>
                  <ArrowUpRight className="h-3.5 w-3.5" />
                </button>
              }
            />
            <div className="p-5">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                <div className="flex flex-wrap items-center gap-5 text-xs text-[#65766D]">
                  <span className="inline-flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-xs bg-[#145C3A]" aria-hidden="true" />
                    <span>Counter Sales (₹)</span>
                  </span>
                  <span className="inline-flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-xs bg-[#C6A15B]" aria-hidden="true" />
                    <span>Dead-Stock Rescued (₹)</span>
                  </span>
                </div>
                <span className="font-mono text-xs text-[#65766D] tabular-nums">
                  Total collected: <strong className="text-[#103D2B]">{formatINR(metrics.totalCollectedPaise)}</strong>
                </span>
              </div>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={dailyChartData}
                    margin={{ top: 6, right: 8, left: -12, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#E5EAE5" vertical={false} />
                    <XAxis
                      dataKey="day"
                      tick={{ fontSize: 11, fill: '#65766D' }}
                      axisLine={{ stroke: '#E5EAE5' }}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: '#65766D' }}
                      axisLine={false}
                      tickLine={false}
                      tickFormatter={(v) => `₹${v}`}
                    />
                    <Tooltip
                      cursor={{ fill: '#FAF7EF' }}
                      contentStyle={{
                        backgroundColor: '#FFFFFF',
                        borderColor: '#E5EAE5',
                        borderRadius: '10px',
                        boxShadow: '0 6px 20px rgba(16, 61, 43, 0.08)',
                        fontSize: '12px',
                        color: '#172B22',
                      }}
                      formatter={(val: unknown, name: unknown) => [
                        `₹${Number(val ?? 0).toLocaleString('en-IN')}`,
                        name === 'sales' ? 'Counter Sales' : 'Cash Rescued',
                      ]}
                    />
                    <Bar dataKey="sales" fill="#145C3A" radius={[4, 4, 0, 0]} maxBarSize={30} />
                    <Bar dataKey="rescued" fill="#C6A15B" radius={[4, 4, 0, 0]} maxBarSize={30} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </SectionCard>

          {/* Direct Store Operations */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            <button
              type="button"
              onClick={() => navigate('/counter')}
              className="group flex items-start justify-between gap-3 rounded-xl border border-[#E5EAE5] bg-white p-4 text-left shadow-[0_1px_2px_rgba(16,61,43,0.04)] hover:border-[#145C3A]/60 hover:bg-[#FAF7EF]/35 transition-all duration-150"
            >
              <div className="flex items-start gap-3 min-w-0">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#FAF7EF] border border-[#E4DCC6] text-[#145C3A]">
                  <ShoppingCart className="h-4.5 w-4.5" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-[#172B22]">Counter POS Billing</p>
                  <p className="mt-0.5 text-xs text-[#65766D] leading-relaxed">
                    Fast Cash, UPI QR, and customer Udhaar checkout
                  </p>
                </div>
              </div>
              <ArrowUpRight className="h-4 w-4 text-[#718078] group-hover:text-[#145C3A] shrink-0 mt-0.5 transition-colors" />
            </button>

            <button
              type="button"
              onClick={() => navigate('/rescue')}
              className="group flex items-start justify-between gap-3 rounded-xl border border-[#E5EAE5] bg-white p-4 text-left shadow-[0_1px_2px_rgba(16,61,43,0.04)] hover:border-[#145C3A]/60 hover:bg-[#FAF7EF]/35 transition-all duration-150"
            >
              <div className="flex items-start gap-3 min-w-0">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#FAF7EF] border border-[#E4DCC6] text-[#145C3A]">
                  <Coins className="h-4.5 w-4.5" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-[#172B22]">Rescue Stuck Cash</p>
                  <p className="mt-0.5 text-xs text-[#65766D] leading-relaxed">
                    {formatINR(metrics.deadStockValuePaise)} tied up in {metrics.deadStockCount} slow items
                  </p>
                </div>
              </div>
              <ArrowUpRight className="h-4 w-4 text-[#718078] group-hover:text-[#145C3A] shrink-0 mt-0.5 transition-colors" />
            </button>

            <button
              type="button"
              onClick={() => navigate('/restock')}
              className="group flex items-start justify-between gap-3 rounded-xl border border-[#E5EAE5] bg-white p-4 text-left shadow-[0_1px_2px_rgba(16,61,43,0.04)] hover:border-[#145C3A]/60 hover:bg-[#FAF7EF]/35 transition-all duration-150"
            >
              <div className="flex items-start gap-3 min-w-0">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#FAF7EF] border border-[#E4DCC6] text-[#145C3A]">
                  <RefreshCw className="h-4.5 w-4.5" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-[#172B22]">Restock Planner</p>
                  <p className="mt-0.5 text-xs text-[#65766D] leading-relaxed">
                    {metrics.stockoutFastMovers.length} urgent fast-movers need supplier POs
                  </p>
                </div>
              </div>
              <ArrowUpRight className="h-4 w-4 text-[#718078] group-hover:text-[#145C3A] shrink-0 mt-0.5 transition-colors" />
            </button>

            <button
              type="button"
              onClick={() => navigate('/customers')}
              className="group flex items-start justify-between gap-3 rounded-xl border border-[#E5EAE5] bg-white p-4 text-left shadow-[0_1px_2px_rgba(16,61,43,0.04)] hover:border-[#145C3A]/60 hover:bg-[#FAF7EF]/35 transition-all duration-150"
            >
              <div className="flex items-start gap-3 min-w-0">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#FAF7EF] border border-[#E4DCC6] text-[#145C3A]">
                  <QrCode className="h-4.5 w-4.5" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-[#172B22]">Collect Udhaar via UPI</p>
                  <p className="mt-0.5 text-xs text-[#65766D] leading-relaxed">
                    {formatINR(metrics.totalUdhaarPaise)} due across {metrics.activeUdhaarCount} customers
                  </p>
                </div>
              </div>
              <ArrowUpRight className="h-4 w-4 text-[#718078] group-hover:text-[#145C3A] shrink-0 mt-0.5 transition-colors" />
            </button>
          </div>
        </div>

        {/* Right 5 Cols: Cash & Credit Position + Operational Alerts */}
        <div className="lg:col-span-5 space-y-6">
          {/* Warm Cream Financial Position Card */}
          <SectionCard variant="warm" className="p-5 space-y-4">
            <div className="flex items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold text-[#103D2B]">Cash &amp; Credit Position</h3>
                <p className="text-xs text-[#65766D] mt-0.5">
                  Real store inflows, trapped inventory capital, and supplier returns
                </p>
              </div>
              <span className="font-mono text-[11px] font-medium text-[#718078]">INR (₹)</span>
            </div>

            {/* Cash vs UPI Share Bar */}
            {metrics.totalCollectedPaise > 0 && (
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-[11px] font-medium text-[#52635B]">
                  <span>Cash {metrics.cashSharePct}%</span>
                  <span>UPI {metrics.upiSharePct}%</span>
                </div>
                <div className="h-2 w-full rounded-full bg-[#E4DCC6] overflow-hidden flex">
                  <div
                    className="h-full bg-[#103D2B] transition-all duration-200"
                    style={{ width: `${metrics.cashSharePct}%` }}
                  />
                  <div
                    className="h-full bg-[#237A50] transition-all duration-200"
                    style={{ width: `${metrics.upiSharePct}%` }}
                  />
                </div>
              </div>
            )}

            <dl className="divide-y divide-[#E4DCC6] text-xs">
              <div className="py-2.5 flex items-center justify-between gap-3">
                <dt className="text-[#52635B]">Cash Collected (Bills + Udhaar)</dt>
                <dd className="font-mono font-semibold text-[#172B22] tabular-nums">
                  {formatINR(metrics.totalCashInflowPaise)}
                </dd>
              </div>
              <div className="py-2.5 flex items-center justify-between gap-3">
                <dt className="text-[#52635B]">UPI Collected (Bills + Udhaar)</dt>
                <dd className="font-mono font-semibold text-[#145C3A] tabular-nums">
                  {formatINR(metrics.totalUpiInflowPaise)}
                </dd>
              </div>
              <div className="py-2.5 flex items-center justify-between gap-3">
                <dt className="text-[#52635B]">Cash Trapped in Dead Stock</dt>
                <dd className="font-mono font-semibold text-red-700 tabular-nums">
                  {formatINR(metrics.deadStockValuePaise)}
                </dd>
              </div>
              <div className="py-2.5 flex items-center justify-between gap-3">
                <dt className="text-[#52635B]">Pending Supplier Return Credit</dt>
                <dd className="font-mono font-semibold text-[#103D2B] tabular-nums">
                  {formatINR(metrics.returnCreditPaise)}
                </dd>
              </div>
            </dl>
          </SectionCard>

          {/* Operational Intelligence: Needs Attention */}
          <SectionCard>
            <SectionHeader
              title="Needs Attention Today"
              subtitle="Out-of-stock fast movers, idle shelf stock, and near-expiry alerts"
            />
            <div className="divide-y divide-[#E5EAE5]">
              {metrics.stockoutFastMovers.slice(0, 3).map((item) => (
                <div
                  key={`stockout-${item.id}`}
                  className="px-5 py-3.5 flex items-center justify-between gap-3 hover:bg-[#FAF7EF]/40 transition-colors"
                >
                  <div className="flex items-start gap-2.5 min-w-0">
                    <AlertTriangle className="h-4 w-4 text-amber-700 shrink-0 mt-0.5" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-[#172B22] truncate">{item.name}</p>
                      <p className="text-xs text-[#65766D]">
                        Out of stock · Sells ~{item.avgDailySales.toFixed(1)}/day
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => navigate('/restock')}
                    className="shrink-0 rounded-lg border border-[#E5EAE5] bg-[#FAF7EF] px-2.5 py-1.5 text-xs font-semibold text-[#103D2B] hover:border-[#145C3A] transition-colors whitespace-nowrap"
                  >
                    Restock
                  </button>
                </div>
              ))}

              {metrics.deadOrExpiryItems.slice(0, 3).map((item) => {
                const expDays = daysUntil(item.expiryDate);
                const nearExp = isNearExpiry(item);
                return (
                  <div
                    key={`dead-${item.id}`}
                    className="px-5 py-3.5 flex items-center justify-between gap-3 hover:bg-[#FAF7EF]/40 transition-colors"
                  >
                    <div className="flex items-start gap-2.5 min-w-0">
                      <Package className="h-4 w-4 text-red-700 shrink-0 mt-0.5" />
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-[#172B22] truncate">{item.name}</p>
                        <p className="text-xs text-[#65766D]">
                          {item.stockQty} units · {formatINR(item.costPaise * item.stockQty)} tied up
                          {nearExp && expDays !== null
                            ? ` · Exp ${expDays}d`
                            : ` · Idle ${daysSince(item.lastSoldAt)}d`}
                        </p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => navigate('/rescue')}
                      className="shrink-0 rounded-lg border border-[#E5EAE5] bg-white px-2.5 py-1.5 text-xs font-semibold text-[#145C3A] hover:bg-[#FAF7EF] hover:border-[#145C3A]/60 transition-colors whitespace-nowrap"
                    >
                      Rescue
                    </button>
                  </div>
                );
              })}

              {metrics.stockoutFastMovers.length === 0 && metrics.deadOrExpiryItems.length === 0 && (
                <EmptyState
                  icon={<CheckCircle2 className="h-5 w-5" />}
                  title="All shelves healthy"
                  description="No urgent fast-mover stockouts or dead-stock alerts require action right now."
                />
              )}
            </div>
          </SectionCard>
        </div>
      </div>

      {/* Recent Store Activity */}
      <SectionCard>
        <SectionHeader
          title="Recent Store Activity"
          subtitle="Latest completed counter bills and confirmed Udhaar repayments"
          action={
            <button
              type="button"
              onClick={() => navigate('/reports')}
              className="inline-flex items-center gap-1 text-xs font-semibold text-[#145C3A] hover:text-[#103D2B] whitespace-nowrap"
            >
              <span>View all bills</span>
              <ArrowUpRight className="h-3.5 w-3.5" />
            </button>
          }
        />

        {recentActivity.length === 0 ? (
          <EmptyState
            icon={<Receipt className="h-5 w-5" />}
            title="No store transactions yet"
            description="Complete a bill on the Counter or record an Udhaar repayment to see activity here."
            action={
              <button
                type="button"
                onClick={() => navigate('/counter')}
                className="min-h-[38px] rounded-lg bg-[#145C3A] px-4 py-2 text-xs font-semibold text-white hover:bg-[#103D2B] transition-colors"
              >
                Open Counter
              </button>
            }
          />
        ) : (
          <div className="divide-y divide-[#E5EAE5]">
            {recentActivity.map((item) => (
              <div
                key={item.id}
                className="px-5 py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-[#FAF7EF]/45 transition-colors"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-semibold text-[#172B22]">{item.title}</p>
                    <span className="text-xs font-medium text-[#65766D]">· {item.methodLabel}</span>
                  </div>
                  <p className="mt-0.5 text-xs text-[#65766D] truncate">
                    {item.subtitle} ·{' '}
                    {new Date(item.createdAt).toLocaleString('en-IN', {
                      day: '2-digit',
                      month: 'short',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </p>
                </div>
                <div className="flex items-center justify-between sm:justify-end gap-4 shrink-0">
                  <span className="font-mono text-sm font-bold text-[#103D2B] tabular-nums">
                    {formatINR(item.amountPaise)}
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      if (item.kind === 'sale') {
                        setPreviewSale(item.sale);
                      } else {
                        setPreviewPayment(item.payment);
                      }
                    }}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-[#E5EAE5] bg-white px-3 py-1.5 text-xs font-medium text-[#172B22] hover:bg-[#FAF7EF] hover:border-[#145C3A] transition-colors whitespace-nowrap"
                  >
                    <Receipt className="h-3.5 w-3.5 text-[#145C3A]" />
                    <span>Receipt</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      <ReceiptModal sale={previewSale} onClose={() => setPreviewSale(null)} />
      <PaymentReceipt payment={previewPayment} onClose={() => setPreviewPayment(null)} />
    </div>
  );
}
