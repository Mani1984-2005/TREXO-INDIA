import {
  ArrowDownLeft,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Coins,
  FileText,
  Receipt,
  RotateCcw,
  Tag,
  TrendingUp,
  Wallet,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { SupplierReturnSlipModal } from '../components/SupplierReturnSlipModal';
import {
  EmptyState,
  KpiCell,
  KpiStrip,
  PageHeader,
  SectionCard,
  SegmentedTabs,
  StatusText,
} from '../components/ui/DesignSystem';
import { useLedgerStore } from '../store/useLedgerStore';
import type { Product, ReturnReason } from '../types/domain';
import {
  calculateTrappedCashPaise,
  daysSince,
  daysUntil,
  formatINR,
  getDiscountPercent,
  isDeadStock,
  isNearExpiry,
  isSameLocalDay,
  isWithinLocalDays,
  rupeesToPaise,
} from '../utils/money';

type RescueTab = 'stuck' | 'returns' | 'movements';
type DateFilter = 'all' | 'today' | '7d' | '30d';

const RETURN_REASONS: ReturnReason[] = [
  'Dead stock (slow moving)',
  'Near expiry',
  'Damaged packaging',
  'Excess supply',
];

interface CashMovementRow {
  id: string;
  createdAt: string;
  direction: 'inflow' | 'outflow';
  title: string;
  subtitle: string;
  mode: string;
  amountPaise: number;
}

export function RescueCashPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<RescueTab>('stuck');
  const [dateFilter, setDateFilter] = useState<DateFilter>('all');
  const [customPrices, setCustomPrices] = useState<Record<string, string>>({});
  const [returnDrafts, setReturnDrafts] = useState<
    Record<string, { qty: number; reason: ReturnReason }>
  >({});
  const [showSlipModal, setShowSlipModal] = useState(false);

  const products = useLedgerStore((s) => s.products);
  const sales = useLedgerStore((s) => s.sales);
  const salesSummary = useLedgerStore((s) => s.salesSummary);
  const customerPayments = useLedgerStore((s) => s.customerPayments);
  const purchaseOrders = useLedgerStore((s) => s.purchaseOrders);
  const suppliers = useLedgerStore((s) => s.suppliers);
  const supplierReturns = useLedgerStore((s) => s.supplierReturns);
  const setCounterDiscount = useLedgerStore((s) => s.setCounterDiscount);
  const returnToSupplier = useLedgerStore((s) => s.returnToSupplier);
  const markReturnSlipGenerated = useLedgerStore((s) => s.markReturnSlipGenerated);
  const clearReturnedItem = useLedgerStore((s) => s.clearReturnedItem);
  const addToCart = useLedgerStore((s) => s.addToCart);

  const supplierMap = useMemo(() => new Map(suppliers.map((s) => [s.id, s])), [suppliers]);

  const stuckProducts = useMemo(() => {
    return products
      .filter((p) => p.stockQty > 0 && (isDeadStock(p) || isNearExpiry(p)))
      .sort((a, b) => b.stockQty * b.costPaise - a.stockQty * a.costPaise);
  }, [products]);

  const trappedCashPaise = useMemo(() => calculateTrappedCashPaise(products), [products]);
  const pendingReturnCreditPaise = useMemo(
    () => supplierReturns.reduce((sum, r) => sum + r.totalCreditPaise, 0),
    [supplierReturns]
  );

  // Build real cash movements from sales (cash/upi), confirmed udhaar repayments, and purchase orders
  const allMovements = useMemo<CashMovementRow[]>(() => {
    const saleInflows: CashMovementRow[] = sales
      .filter((s) => s.paymentMethod === 'cash' || s.paymentMethod === 'upi')
      .map((s) => ({
        id: `sale-${s.id}`,
        createdAt: s.createdAt,
        direction: 'inflow',
        title: `Counter Bill ${s.invoiceNo}`,
        subtitle: s.customerName ?? 'Walk-in Customer',
        mode: s.paymentMethod === 'upi' ? (s.isDemoPayment ? 'UPI · Demo' : 'UPI') : 'Cash',
        amountPaise: s.totalPaise,
      }));

    const udhaarInflows: CashMovementRow[] = customerPayments
      .filter((p) => p.status === 'confirmed')
      .map((p) => ({
        id: `repay-${p.id}`,
        createdAt: p.createdAt,
        direction: 'inflow',
        title: `Udhaar Collection · ${p.customerName}`,
        subtitle: `Ref ${p.transactionRef}`,
        mode: p.paymentMethod === 'upi' ? (p.isDemo ? 'UPI · Demo' : 'UPI') : 'Cash',
        amountPaise: p.amountPaise,
      }));

    const poOutflows: CashMovementRow[] = purchaseOrders.map((po) => ({
      id: `po-${po.id}`,
      createdAt: po.createdAt,
      direction: 'outflow',
      title: `Purchase Order ${po.poNumber}`,
      subtitle: `${po.items.length} ${po.items.length === 1 ? 'line item' : 'line items'} · ${po.status}`,
      mode: 'Supplier PO',
      amountPaise: po.totalPaise,
    }));

    return [...saleInflows, ...udhaarInflows, ...poOutflows].sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    );
  }, [sales, customerPayments, purchaseOrders]);

  const filteredMovements = useMemo(() => {
    if (dateFilter === 'all') return allMovements;
    return allMovements.filter((m) => {
      if (dateFilter === 'today') return isSameLocalDay(m.createdAt);
      if (dateFilter === '7d') return isWithinLocalDays(m.createdAt, 7);
      return isWithinLocalDays(m.createdAt, 30);
    });
  }, [allMovements, dateFilter]);

  const totalCollectedInflowPaise = useMemo(
    () =>
      allMovements
        .filter((m) => m.direction === 'inflow')
        .reduce((acc, m) => acc + m.amountPaise, 0),
    [allMovements]
  );

  const filteredFlowTotals = useMemo(() => {
    let inflow = 0;
    let outflow = 0;
    for (const m of filteredMovements) {
      if (m.direction === 'inflow') inflow += m.amountPaise;
      else outflow += m.amountPaise;
    }
    return { inflow, outflow, net: inflow - outflow };
  }, [filteredMovements]);

  const applyPresetDiscount = async (product: Product, pct: number) => {
    const rawPaise = Math.round(product.sellingPricePaise * (1 - pct / 100));
    const roundedRupees = Math.max(1, Math.round(rawPaise / 100));
    await setCounterDiscount(product.id, roundedRupees * 100);
  };

  const applyCustomPrice = async (product: Product) => {
    const raw = customPrices[product.id];
    const parsed = Number(raw);
    if (!Number.isFinite(parsed) || parsed <= 0) return;
    await setCounterDiscount(product.id, rupeesToPaise(parsed));
    setCustomPrices((prev) => ({ ...prev, [product.id]: '' }));
  };

  const handleMoveToReturn = async (product: Product) => {
    const draft = returnDrafts[product.id] ?? {
      qty: Math.min(product.stockQty, Math.max(1, Math.ceil(product.stockQty / 2))),
      reason: isNearExpiry(product) ? 'Near expiry' : 'Dead stock (slow moving)',
    };
    await returnToSupplier(product.id, draft.qty, draft.reason);
  };

  const handleSellAtCounter = (product: Product) => {
    addToCart(product.id, 1);
    navigate('/counter');
  };

  return (
    <div className="space-y-6 trexo-fade-in">
      <PageHeader
        title="Rescue Cash & Cash Flow"
        description="Unlock capital tied up in dead or near-expiry shelf stock, prepare distributor return slips, and track real store cash movements."
        actions={
          supplierReturns.length > 0 ? (
            <button
              type="button"
              onClick={() => setShowSlipModal(true)}
              className="min-h-[42px] inline-flex items-center gap-1.5 rounded-lg bg-[#145C3A] px-4 py-2 text-xs sm:text-sm font-semibold text-white hover:bg-[#103D2B] transition-colors whitespace-nowrap shadow-[0_1px_2px_rgba(16,61,43,0.16)]"
            >
              <FileText className="h-4 w-4" />
              <span>Preview Return Slip</span>
            </button>
          ) : undefined
        }
      />

      {/* Financial Overview KPI Strip */}
      <KpiStrip columns={4} ariaLabel="Cash flow and dead stock overview" className="no-print">
        <KpiCell
          label="Cash & UPI Inflow Collected"
          value={formatINR(totalCollectedInflowPaise)}
          icon={<Wallet className="h-3.5 w-3.5" />}
          caption="Counter cash/UPI bills + Udhaar collections"
          tone="emerald"
        />
        <KpiCell
          label="Cash Trapped in Dead Stock"
          value={formatINR(trappedCashPaise)}
          icon={<Coins className="h-3.5 w-3.5" />}
          caption={`Across ${stuckProducts.length} idle or near-expiry items`}
          tone={trappedCashPaise > 0 ? 'crimson' : 'emerald'}
        />
        <KpiCell
          label="Cash Unlocked via Counter"
          value={formatINR(salesSummary?.totalRescuedCashPaise ?? 0)}
          icon={<TrendingUp className="h-3.5 w-3.5" />}
          caption="Recovered from slow-moving stock sales"
          tone="emerald"
        />
        <KpiCell
          label="Queued Supplier Return Credit"
          value={formatINR(pendingReturnCreditPaise)}
          icon={<RotateCcw className="h-3.5 w-3.5" />}
          caption={`${supplierReturns.length} ${supplierReturns.length === 1 ? 'line' : 'lines'} awaiting distributor credit`}
          tone={pendingReturnCreditPaise > 0 ? 'amber' : 'default'}
        />
      </KpiStrip>

      {/* Main Workspace */}
      <SectionCard className="no-print">
        <div className="border-b border-[#E5EAE5] px-4 sm:px-5 py-4 flex flex-wrap items-center justify-between gap-3">
          <SegmentedTabs
            value={activeTab}
            onChange={setActiveTab}
            ariaLabel="Rescue cash workspace view"
            options={[
              { id: 'stuck', label: `Stuck & Near-Expiry (${stuckProducts.length})` },
              { id: 'returns', label: `Supplier Returns (${supplierReturns.length})` },
              { id: 'movements', label: `Cash Movements (${allMovements.length})` },
            ]}
          />

          {activeTab === 'returns' && supplierReturns.length > 0 && (
            <button
              type="button"
              onClick={() => setShowSlipModal(true)}
              className="min-h-[38px] inline-flex items-center gap-1.5 rounded-lg bg-[#145C3A] px-4 py-2 text-xs font-semibold text-white hover:bg-[#103D2B] transition-colors whitespace-nowrap"
            >
              <FileText className="h-4 w-4" />
              <span>Generate Return Slip</span>
            </button>
          )}

          {activeTab === 'movements' && (
            <SegmentedTabs
              value={dateFilter}
              onChange={setDateFilter}
              ariaLabel="Cash movement date filter"
              options={[
                { id: 'all', label: 'All' },
                { id: 'today', label: 'Today' },
                { id: '7d', label: '7D' },
                { id: '30d', label: '30D' },
              ]}
            />
          )}
        </div>

        {activeTab === 'stuck' &&
          (stuckProducts.length === 0 ? (
            <EmptyState
              icon={<CheckCircle2 className="h-5 w-5" />}
              title="Zero cash trapped in dead stock"
              description="All slow-moving and near-expiry items have been cleared or moved to supplier returns."
            />
          ) : (
            <div className="divide-y divide-[#E5EAE5]">
              {stuckProducts.map((product) => {
                const idleDays = daysSince(product.lastSoldAt);
                const expDays = daysUntil(product.expiryDate);
                const nearExp = isNearExpiry(product);
                const trapped = product.stockQty * product.costPaise;
                const hasOffer = product.counterDiscountPricePaise !== null;
                const offerPct = hasOffer
                  ? getDiscountPercent(
                      product.sellingPricePaise,
                      product.counterDiscountPricePaise!
                    )
                  : 0;
                const supplier = supplierMap.get(product.supplierId);
                const draft = returnDrafts[product.id] ?? {
                  qty: Math.min(product.stockQty, Math.max(1, Math.ceil(product.stockQty / 2))),
                  reason: nearExp ? 'Near expiry' : 'Dead stock (slow moving)',
                };

                return (
                  <div key={product.id} className="p-4 sm:p-5 space-y-4">
                    <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                      <div className="space-y-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-[#65766D]">
                          <span className="font-mono">{product.sku}</span>
                          <span>·</span>
                          <span>{product.category}</span>
                          <span>·</span>
                          <span>{supplier?.name ?? 'Assigned Distributor'}</span>
                        </div>
                        <h3 className="text-base font-bold text-[#172B22]">{product.name}</h3>
                        <p className="text-xs text-[#52635B]">
                          <span className="font-mono font-semibold text-[#172B22] tabular-nums">
                            {product.stockQty}
                          </span>{' '}
                          units on shelf ·{' '}
                          <span className="text-red-700 font-semibold">{idleDays} days idle</span>
                          {expDays !== null && (
                            <>
                              {' · '}
                              <span
                                className={
                                  nearExp ? 'text-amber-700 font-semibold' : 'text-[#65766D]'
                                }
                              >
                                {expDays <= 0 ? 'Expired' : `Expires in ${expDays} days`}
                              </span>
                            </>
                          )}
                        </p>
                      </div>

                      <div className="md:text-right shrink-0">
                        <p className="text-xs text-[#65766D]">Trapped Cost Capital</p>
                        <p className="font-mono text-xl font-bold text-red-700 tabular-nums">
                          {formatINR(trapped)}
                        </p>
                        <p className="text-xs text-[#65766D] font-mono tabular-nums">
                          Cost {formatINR(product.costPaise)} · Regular{' '}
                          {formatINR(product.sellingPricePaise)}
                        </p>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 pt-3.5 border-t border-[#E5EAE5]">
                      {/* Option 1: Counter Discount */}
                      <div className="space-y-2.5">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#172B22]">
                            <Tag className="h-3.5 w-3.5 text-[#145C3A]" />
                            <span>Option 1: Apply Counter Discount</span>
                          </span>
                          {hasOffer && (
                            <span className="text-xs font-semibold text-[#145C3A] font-mono tabular-nums">
                              Live at {formatINR(product.counterDiscountPricePaise!)} ({offerPct}%
                              off)
                            </span>
                          )}
                        </div>

                        <div className="flex flex-wrap items-center gap-2">
                          {[10, 15, 20, 25].map((pct) => (
                            <button
                              key={pct}
                              type="button"
                              onClick={() => applyPresetDiscount(product, pct)}
                              className="min-h-[36px] rounded-lg border border-[#D4DDD6] bg-white px-3 py-1.5 text-xs font-semibold text-[#172B22] hover:border-[#145C3A] hover:text-[#145C3A] transition-colors"
                            >
                              -{pct}%
                            </button>
                          ))}

                          <div className="flex items-center gap-1.5">
                            <input
                              type="number"
                              min="1"
                              placeholder="Custom ₹"
                              value={customPrices[product.id] ?? ''}
                              onChange={(e) =>
                                setCustomPrices((prev) => ({
                                  ...prev,
                                  [product.id]: e.target.value,
                                }))
                              }
                              className="w-24 min-h-[36px] rounded-lg border border-[#D4DDD6] px-2.5 py-1.5 text-xs font-mono text-[#172B22] focus:border-[#145C3A] focus:outline-none"
                            />
                            <button
                              type="button"
                              onClick={() => applyCustomPrice(product)}
                              className="min-h-[36px] rounded-lg bg-[#103D2B] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#145C3A] transition-colors"
                            >
                              Apply
                            </button>
                          </div>

                          {hasOffer && (
                            <button
                              type="button"
                              onClick={() => setCounterDiscount(product.id, null)}
                              className="text-xs font-medium text-[#65766D] hover:text-red-700"
                            >
                              Clear offer
                            </button>
                          )}
                        </div>

                        <div>
                          <button
                            type="button"
                            onClick={() => handleSellAtCounter(product)}
                            className="inline-flex items-center gap-1 text-xs font-semibold text-[#145C3A] hover:text-[#103D2B]"
                          >
                            <span>Add to Counter Bill now</span>
                            <ArrowRight className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>

                      {/* Option 2: Supplier Return */}
                      <div className="space-y-2.5 xl:border-l xl:border-[#E5EAE5] xl:pl-4">
                        <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#172B22]">
                          <RotateCcw className="h-3.5 w-3.5 text-amber-700" />
                          <span>Option 2: Return to Supplier</span>
                        </span>

                        <div className="flex flex-wrap items-center gap-2">
                          <input
                            type="number"
                            min={1}
                            max={product.stockQty}
                            value={draft.qty}
                            onChange={(e) =>
                              setReturnDrafts((prev) => ({
                                ...prev,
                                [product.id]: {
                                  ...draft,
                                  qty: Math.min(
                                    product.stockQty,
                                    Math.max(1, Number(e.target.value) || 1)
                                  ),
                                },
                              }))
                            }
                            aria-label={`Return quantity for ${product.name}`}
                            className="w-20 min-h-[36px] rounded-lg border border-[#D4DDD6] px-2.5 py-1.5 text-xs font-mono text-[#172B22] focus:border-[#145C3A] focus:outline-none"
                          />

                          <select
                            value={draft.reason}
                            onChange={(e) =>
                              setReturnDrafts((prev) => ({
                                ...prev,
                                [product.id]: {
                                  ...draft,
                                  reason: e.target.value as ReturnReason,
                                },
                              }))
                            }
                            className="min-h-[36px] max-w-full rounded-lg border border-[#D4DDD6] bg-white px-2.5 py-1.5 text-xs text-[#172B22] focus:border-[#145C3A] focus:outline-none"
                          >
                            {RETURN_REASONS.map((r) => (
                              <option key={r} value={r}>
                                {r}
                              </option>
                            ))}
                          </select>

                          <button
                            type="button"
                            onClick={() => handleMoveToReturn(product)}
                            className="min-h-[36px] rounded-lg border border-[#D8CEB6] bg-[#FAF7EF] px-3 py-1.5 text-xs font-semibold text-[#103D2B] hover:border-[#145C3A] transition-colors whitespace-nowrap"
                          >
                            Move to Return List
                          </button>
                        </div>
                        <p className="text-xs text-[#65766D] font-mono tabular-nums">
                          Estimated credit: {formatINR(draft.qty * product.costPaise)} from{' '}
                          <span className="font-sans">{supplier?.name ?? 'Supplier'}</span>
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ))}

        {activeTab === 'returns' &&
          (supplierReturns.length === 0 ? (
            <EmptyState
              icon={<RotateCcw className="h-5 w-5" />}
              title="Supplier return list is empty"
              description="Move unsold dead stock or near-expiry packs from the Stuck Stock tab to generate a distributor debit note."
            />
          ) : (
            <>
              <div className="hidden lg:block overflow-x-auto trexo-scroll">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-[#E5EAE5] bg-[#FAF7EF] text-xs font-semibold text-[#52635B]">
                      <th className="px-5 py-3">Item &amp; SKU</th>
                      <th className="px-4 py-3">Supplier</th>
                      <th className="px-4 py-3">Reason</th>
                      <th className="px-4 py-3 text-right">Qty</th>
                      <th className="px-4 py-3 text-right">Credit Value</th>
                      <th className="px-4 py-3">Slip Status</th>
                      <th className="px-5 py-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E5EAE5]">
                    {supplierReturns.map((ret) => (
                      <tr key={ret.id} className="hover:bg-[#FAF7EF]/50 transition-colors">
                        <td className="px-5 py-3.5">
                          <p className="font-semibold text-[#172B22]">{ret.productName}</p>
                          <p className="font-mono text-xs text-[#65766D]">{ret.sku}</p>
                        </td>
                        <td className="px-4 py-3.5 text-[#172B22]">{ret.supplierName}</td>
                        <td className="px-4 py-3.5 text-xs text-[#65766D]">{ret.reason}</td>
                        <td className="px-4 py-3.5 text-right font-mono tabular-nums">{ret.qty}</td>
                        <td className="px-4 py-3.5 text-right font-mono font-semibold text-[#103D2B] tabular-nums">
                          {formatINR(ret.totalCreditPaise)}
                        </td>
                        <td className="px-4 py-3.5">
                          {ret.slipGeneratedAt ? (
                            <StatusText tone="emerald" label="Slip printed" />
                          ) : (
                            <StatusText tone="amber" label="Pending slip" />
                          )}
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          <button
                            type="button"
                            onClick={() => clearReturnedItem(ret.id)}
                            className="text-xs font-semibold text-[#145C3A] hover:text-[#103D2B] whitespace-nowrap"
                          >
                            Mark Settled
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="lg:hidden grid grid-cols-1 md:grid-cols-2 gap-px bg-[#E5EAE5]">
                {supplierReturns.map((ret) => (
                  <div key={ret.id} className="bg-white p-4 space-y-2.5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-[#172B22]">{ret.productName}</p>
                        <p className="text-xs text-[#65766D] truncate">
                          <span className="font-mono">{ret.sku}</span> · {ret.supplierName}
                        </p>
                      </div>
                      <span className="font-mono text-sm font-bold text-[#103D2B] tabular-nums shrink-0">
                        {formatINR(ret.totalCreditPaise)}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs pt-1 border-t border-[#E5EAE5]/70">
                      <span className="text-[#52635B]">
                        Qty <span className="font-mono font-semibold">{ret.qty}</span> · {ret.reason}{' '}
                        ·{' '}
                        <span
                          className={
                            ret.slipGeneratedAt
                              ? 'font-semibold text-[#145C3A]'
                              : 'font-semibold text-amber-700'
                          }
                        >
                          {ret.slipGeneratedAt ? 'Slip printed' : 'Pending slip'}
                        </span>
                      </span>
                      <button
                        type="button"
                        onClick={() => clearReturnedItem(ret.id)}
                        className="font-semibold text-[#145C3A] hover:text-[#103D2B] whitespace-nowrap shrink-0"
                      >
                        Mark Settled
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          ))}

        {activeTab === 'movements' && (
          <div>
            {/* Inflow / Outflow / Net Strip */}
            <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-[#E4DCC6] border-b border-[#E4DCC6] bg-[#FAF7EF]">
              <div className="px-5 py-3.5">
                <p className="text-xs text-[#52635B]">Period Inflow (Cash + UPI)</p>
                <p className="mt-1 font-mono text-lg font-bold text-[#145C3A] tabular-nums">
                  +{formatINR(filteredFlowTotals.inflow)}
                </p>
              </div>
              <div className="px-5 py-3.5">
                <p className="text-xs text-[#52635B]">Period Outflow (Supplier POs)</p>
                <p className="mt-1 font-mono text-lg font-bold text-red-700 tabular-nums">
                  -{formatINR(filteredFlowTotals.outflow)}
                </p>
              </div>
              <div className="px-5 py-3.5">
                <p className="text-xs text-[#52635B]">Net Cash Flow</p>
                <p
                  className={`mt-1 font-mono text-lg font-bold tabular-nums ${
                    filteredFlowTotals.net >= 0 ? 'text-[#103D2B]' : 'text-red-700'
                  }`}
                >
                  {filteredFlowTotals.net >= 0 ? '+' : '-'}
                  {formatINR(Math.abs(filteredFlowTotals.net))}
                </p>
              </div>
            </div>

            {filteredMovements.length === 0 ? (
              <EmptyState
                icon={<Receipt className="h-5 w-5" />}
                title="No cash movements in this range"
                description="Switch to All or record counter bills, Udhaar repayments, or purchase orders."
              />
            ) : (
              <div className="divide-y divide-[#E5EAE5]">
                {filteredMovements.map((m) => (
                  <div
                    key={m.id}
                    className="px-4 sm:px-5 py-3.5 flex items-center justify-between gap-3 hover:bg-[#FAF7EF]/45 transition-colors"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <span
                        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                          m.direction === 'inflow'
                            ? 'bg-emerald-50 text-[#145C3A]'
                            : 'bg-red-50 text-red-700'
                        }`}
                      >
                        {m.direction === 'inflow' ? (
                          <ArrowDownLeft className="h-4 w-4" />
                        ) : (
                          <ArrowUpRight className="h-4 w-4" />
                        )}
                      </span>
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-[#172B22] truncate">{m.title}</p>
                        <p className="text-xs text-[#65766D] truncate">
                          {m.subtitle} · {m.mode} ·{' '}
                          {new Date(m.createdAt).toLocaleString('en-IN', {
                            day: '2-digit',
                            month: 'short',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </p>
                      </div>
                    </div>
                    <span
                      className={`font-mono text-sm font-bold tabular-nums shrink-0 ${
                        m.direction === 'inflow' ? 'text-[#145C3A]' : 'text-red-700'
                      }`}
                    >
                      {m.direction === 'inflow' ? '+' : '-'}
                      {formatINR(m.amountPaise)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </SectionCard>

      {showSlipModal && (
        <SupplierReturnSlipModal
          items={supplierReturns}
          onClose={() => setShowSlipModal(false)}
          onConfirmPrint={markReturnSlipGenerated}
        />
      )}
    </div>
  );
}
