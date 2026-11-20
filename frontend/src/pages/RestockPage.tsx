import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ClipboardList,
  MessageCircle,
  PauseCircle,
  Plus,
  ShoppingCart,
  Trash2,
  TrendingDown,
  XCircle,
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
import {
  EmptyState,
  KpiCell,
  KpiStrip,
  PageHeader,
  SectionCard,
  SectionHeader,
  SegmentedTabs,
  StatusText,
} from '../components/ui/DesignSystem';
import { STORE_INFO } from '../config';
import { useSaveShortcut } from '../hooks/useGlobalShortcuts';
import { useLedgerStore } from '../store/useLedgerStore';
import type { ForecastHorizon, ForecastRow } from '../types/domain';
import { formatINR } from '../utils/money';

const HORIZONS: { id: ForecastHorizon; label: string }[] = [
  { id: '1W', label: '1 Week' },
  { id: '1M', label: '1 Month' },
  { id: '6M', label: '6 Months' },
  { id: '1Y', label: '1 Year' },
];

export function RestockPage() {
  const [poDraft, setPoDraft] = useState<Record<string, number>>({});
  const [submittingPo, setSubmittingPo] = useState(false);

  const products = useLedgerStore((s) => s.products);
  const forecastHorizon = useLedgerStore((s) => s.forecastHorizon);
  const forecastRows = useLedgerStore((s) => s.forecastRows);
  const purchaseOrders = useLedgerStore((s) => s.purchaseOrders);
  const setForecastHorizon = useLedgerStore((s) => s.setForecastHorizon);
  const createPurchaseOrder = useLedgerStore((s) => s.createPurchaseOrder);

  const productMap = useMemo(() => new Map(products.map((p) => [p.id, p])), [products]);

  const stockoutRows = useMemo(
    () => forecastRows.filter((r) => r.status === 'Out of Stock'),
    [forecastRows]
  );

  const lowStockRows = useMemo(
    () => forecastRows.filter((r) => r.status === 'Low Stock'),
    [forecastRows]
  );

  const totalLostSalesPaise = useMemo(
    () => forecastRows.reduce((sum, r) => sum + r.estimatedLostSalesPaise, 0),
    [forecastRows]
  );

  const chartData = useMemo(() => {
    return forecastRows
      .filter((r) => !r.stopReordering && r.forecastedDemand > 0)
      .slice(0, 8)
      .map((r) => ({
        name: r.name.split(' ').slice(0, 2).join(' '),
        currentStock: r.currentStock,
        forecastedDemand: r.forecastedDemand,
      }));
  }, [forecastRows]);

  const togglePoItem = (row: ForecastRow) => {
    setPoDraft((prev) => {
      if (prev[row.productId]) {
        const next = { ...prev };
        delete next[row.productId];
        return next;
      }
      return {
        ...prev,
        [row.productId]: Math.max(1, row.recommendedOrderQty || 10),
      };
    });
  };

  const addAllUrgentToPo = () => {
    const next: Record<string, number> = { ...poDraft };
    for (const row of forecastRows) {
      if ((row.status === 'Out of Stock' || row.status === 'Low Stock') && !row.stopReordering) {
        next[row.productId] = Math.max(1, row.recommendedOrderQty || 10);
      }
    }
    setPoDraft(next);
  };

  const poDraftItems = useMemo(() => {
    return Object.entries(poDraft)
      .map(([productId, qty]) => {
        const row = forecastRows.find((r) => r.productId === productId);
        const prod = productMap.get(productId);
        if (!row || !prod || qty <= 0) return null;
        return {
          productId: row.productId,
          sku: row.sku,
          name: row.name,
          supplierId: row.supplierId,
          supplierName: row.supplierName,
          qty,
          unitCostPaise: prod.costPaise,
          lineTotalPaise: qty * prod.costPaise,
        };
      })
      .filter((x): x is NonNullable<typeof x> => x !== null);
  }, [poDraft, forecastRows, productMap]);

  const poDraftTotalPaise = useMemo(
    () => poDraftItems.reduce((sum, i) => sum + i.lineTotalPaise, 0),
    [poDraftItems]
  );

  const poWhatsAppHref = useMemo(() => {
    const lines = [
      `Purchase Order Request — ${STORE_INFO.shopName}:`,
      ...poDraftItems.map((i) => `- ${i.name} (${i.sku}): ${i.qty} units [${i.supplierName}]`),
      `Estimated Value: ${formatINR(poDraftTotalPaise)}`,
      'Sent via Trexo',
    ];
    return `https://wa.me/?text=${encodeURIComponent(lines.join('\n'))}`;
  }, [poDraftItems, poDraftTotalPaise]);

  const handleSubmitPo = async () => {
    if (poDraftItems.length === 0 || submittingPo) return;
    setSubmittingPo(true);
    try {
      await createPurchaseOrder(
        poDraftItems.map(({ lineTotalPaise: _omit, ...rest }) => rest)
      );
      setPoDraft({});
    } finally {
      setSubmittingPo(false);
    }
  };

  useSaveShortcut(() => {
    void handleSubmitPo();
  }, poDraftItems.length > 0 && !submittingPo);

  const activeHorizonLabel = HORIZONS.find((h) => h.id === forecastHorizon)?.label ?? '1 Month';

  return (
    <div className="space-y-6 trexo-fade-in">
      <PageHeader
        title="Restock Planner"
        description="Compare shelf inventory against projected demand and prepare distributor purchase orders."
        actions={
          <>
            <SegmentedTabs
              value={forecastHorizon}
              onChange={(h) => void setForecastHorizon(h)}
              options={HORIZONS}
              ariaLabel="Forecast horizon"
            />
            <button
              type="button"
              onClick={addAllUrgentToPo}
              className="min-h-[40px] inline-flex items-center gap-1.5 rounded-lg bg-[#145C3A] px-4 py-2 text-xs sm:text-sm font-semibold text-white hover:bg-[#103D2B] transition-colors whitespace-nowrap shadow-[0_1px_2px_rgba(16,61,43,0.16)]"
            >
              <Plus className="h-4 w-4" />
              <span>Add All Urgent to PO</span>
            </button>
          </>
        }
      />

      {/* Restock KPI Strip */}
      <KpiStrip columns={3} ariaLabel="Restock summary">
        <KpiCell
          label="Out of Stock & Low Fast Movers"
          value={`${stockoutRows.length + lowStockRows.length}`}
          icon={<AlertTriangle className="h-3.5 w-3.5" />}
          caption={`${stockoutRows.length} out of stock · ${lowStockRows.length} running low`}
          tone={stockoutRows.length > 0 ? 'crimson' : 'amber'}
        />
        <KpiCell
          label="Estimated Missed Sales"
          value={formatINR(totalLostSalesPaise)}
          icon={<TrendingDown className="h-3.5 w-3.5" />}
          caption={`Projected over ${activeHorizonLabel} · Demo forecast`}
          tone={totalLostSalesPaise > 0 ? 'amber' : 'emerald'}
        />
        <KpiCell
          label="Active PO Draft Value"
          value={formatINR(poDraftTotalPaise)}
          icon={<ShoppingCart className="h-3.5 w-3.5" />}
          caption={`${poDraftItems.length} ${poDraftItems.length === 1 ? 'item' : 'items'} queued for supplier order`}
          tone="emerald"
        />
      </KpiStrip>

      {/* Demand vs Stock Chart + Sticky PO Draft Split */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <SectionCard className="lg:col-span-8">
          <SectionHeader
            title={`Current Stock vs ${activeHorizonLabel} Demand`}
            subtitle="Shelf units compared against seeded demand projection (Demo forecast)"
            action={
              <div className="flex items-center gap-4 text-xs text-[#65766D]">
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-xs bg-[#C6A15B]" aria-hidden="true" />
                  Current Stock
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-xs bg-[#145C3A]" aria-hidden="true" />
                  Forecast Demand
                </span>
              </div>
            }
          />
          <div className="p-5">
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E5EAE5" vertical={false} />
                  <XAxis
                    dataKey="name"
                    tick={{ fill: '#65766D', fontSize: 11 }}
                    axisLine={{ stroke: '#E5EAE5' }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: '#65766D', fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    cursor={{ fill: '#FAF7EF' }}
                    contentStyle={{
                      borderRadius: '10px',
                      border: '1px solid #E5EAE5',
                      boxShadow: '0 6px 20px rgba(16, 61, 43, 0.08)',
                      fontSize: '12px',
                      color: '#172B22',
                    }}
                  />
                  <Bar
                    dataKey="currentStock"
                    name="Current Stock"
                    fill="#C6A15B"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={28}
                  />
                  <Bar
                    dataKey="forecastedDemand"
                    name="Forecast Demand"
                    fill="#145C3A"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={28}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </SectionCard>

        {/* Purchase Order Draft Panel */}
        <aside className="lg:col-span-4 lg:sticky lg:top-22 rounded-xl border border-[#DCE3DD] bg-white shadow-[0_2px_10px_rgba(16,61,43,0.06)] overflow-hidden">
          <div className="flex items-center justify-between border-b border-white/10 bg-[#103D2B] px-5 py-4 text-white">
            <div className="flex items-center gap-2 min-w-0">
              <ShoppingCart className="h-4 w-4 text-[#C6A15B] shrink-0" />
              <h3 className="text-sm font-semibold truncate">
                Purchase Order Draft ({poDraftItems.length})
              </h3>
            </div>
            {poDraftItems.length > 0 && (
              <button
                type="button"
                onClick={() => setPoDraft({})}
                className="text-xs font-medium text-white/75 hover:text-red-200 transition-colors shrink-0"
              >
                Clear
              </button>
            )}
          </div>

          {poDraftItems.length === 0 ? (
            <EmptyState
              icon={<ClipboardList className="h-5 w-5" />}
              title="No items selected for PO"
              description="Select out-of-stock or low-stock fast movers from the forecast list below."
              className="py-9"
            />
          ) : (
            <div className="divide-y divide-[#E5EAE5] max-h-64 overflow-y-auto trexo-scroll px-5">
              {poDraftItems.map((item) => (
                <div key={item.productId} className="py-3 flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-[#172B22] truncate">{item.name}</p>
                    <p className="text-[11px] text-[#65766D] truncate">
                      {item.supplierName} ·{' '}
                      <span className="font-mono tabular-nums">
                        {formatINR(item.lineTotalPaise)}
                      </span>
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <input
                      type="number"
                      min={1}
                      value={item.qty}
                      onChange={(e) =>
                        setPoDraft((prev) => ({
                          ...prev,
                          [item.productId]: Math.max(1, Number(e.target.value) || 1),
                        }))
                      }
                      aria-label={`Order quantity for ${item.name}`}
                      className="w-16 rounded-md border border-[#D4DDD6] px-2 py-1 text-right font-mono text-xs tabular-nums focus:border-[#145C3A] focus:outline-none"
                    />
                    <button
                      type="button"
                      onClick={() =>
                        setPoDraft((prev) => {
                          const next = { ...prev };
                          delete next[item.productId];
                          return next;
                        })
                      }
                      className="p-1.5 text-[#718078] hover:text-red-700 transition-colors"
                      aria-label={`Remove ${item.name} from PO`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="border-t border-[#E4DCC6] bg-[#FAF7EF] p-4 space-y-3">
            <div className="flex items-baseline justify-between">
              <span className="text-xs font-semibold text-[#52635B]">Estimated PO Cost</span>
              <span className="font-mono text-base font-bold text-[#103D2B] tabular-nums">
                {formatINR(poDraftTotalPaise)}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={poDraftItems.length === 0 || submittingPo}
                onClick={handleSubmitPo}
                className="flex-1 min-h-[42px] rounded-lg bg-[#145C3A] px-3.5 py-2.5 text-xs font-semibold text-white hover:bg-[#103D2B] disabled:bg-[#D4DDD6] disabled:text-[#718078] transition-colors"
              >
                {submittingPo ? 'Saving PO...' : 'Create Purchase Order'}
              </button>

              {poDraftItems.length > 0 && (
                <a
                  href={poWhatsAppHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="min-h-[42px] min-w-[42px] inline-flex items-center justify-center rounded-lg border border-[#D8CEB6] bg-white p-2.5 text-[#145C3A] hover:border-[#145C3A] transition-colors"
                  title="Share PO via WhatsApp"
                  aria-label="Share Purchase Order via WhatsApp"
                >
                  <MessageCircle className="h-4 w-4" />
                </a>
              )}
            </div>
          </div>
        </aside>
      </div>

      {/* Forecast Recommendations Table (lg+) / Responsive Cards (< lg) */}
      <SectionCard>
        <SectionHeader
          title="Demand Forecast & Recommended Orders"
          subtitle={`Horizon: ${activeHorizonLabel} · Historical velocity shown alongside projected demand (Demo forecast)`}
        />

        {/* Desktop Table */}
        <div className="hidden lg:block overflow-x-auto trexo-scroll">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[#E5EAE5] bg-[#FAF7EF] text-xs font-semibold text-[#52635B]">
                <th className="px-5 py-3">Item &amp; Supplier</th>
                <th className="px-4 py-3 text-right">On Shelf</th>
                <th className="px-4 py-3 text-right">Sales Pace</th>
                <th className="px-4 py-3 text-right">Projected Demand</th>
                <th className="px-4 py-3 text-right">Suggested Order</th>
                <th className="px-4 py-3 text-right">Est. Lost Sales</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-5 py-3 text-right">PO Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E5EAE5]">
              {forecastRows.map((row) => {
                const inPo = Boolean(poDraft[row.productId]);
                const noHistory = row.avgDailySales === 0 && row.forecastedDemand === 0;
                return (
                  <tr key={row.productId} className="hover:bg-[#FAF7EF]/50 transition-colors">
                    <td className="px-5 py-3.5 max-w-[260px]">
                      <p className="font-semibold text-[#172B22] truncate">{row.name}</p>
                      <p className="text-xs text-[#65766D] truncate">
                        <span className="font-mono">{row.sku}</span> · {row.supplierName}
                      </p>
                    </td>
                    <td className="px-4 py-3.5 text-right font-mono tabular-nums font-medium text-[#172B22]">
                      {row.currentStock}
                    </td>
                    <td className="px-4 py-3.5 text-right font-mono tabular-nums text-xs text-[#65766D] whitespace-nowrap">
                      {noHistory ? (
                        <span className="font-sans text-[#718078]">No sales history</span>
                      ) : (
                        `${row.avgDailySales.toFixed(1)}/day`
                      )}
                    </td>
                    <td className="px-4 py-3.5 text-right font-mono tabular-nums text-[#52635B] whitespace-nowrap">
                      {noHistory ? (
                        <span className="font-sans text-xs text-[#718078]">—</span>
                      ) : (
                        row.forecastedDemand
                      )}
                    </td>
                    <td className="px-4 py-3.5 text-right font-mono font-semibold tabular-nums text-[#103D2B]">
                      {row.recommendedOrderQty > 0 ? `+${row.recommendedOrderQty}` : '—'}
                    </td>
                    <td className="px-4 py-3.5 text-right font-mono tabular-nums whitespace-nowrap">
                      {row.estimatedLostSalesPaise > 0 ? (
                        <span className="font-semibold text-amber-700">
                          {formatINR(row.estimatedLostSalesPaise)}
                        </span>
                      ) : (
                        <span className="text-[#718078]">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3.5 whitespace-nowrap">
                      {row.status === 'Out of Stock' ? (
                        <StatusText
                          tone="crimson"
                          label="Out of Stock"
                          icon={<XCircle className="h-3.5 w-3.5" />}
                        />
                      ) : row.status === 'Low Stock' ? (
                        <StatusText
                          tone="amber"
                          label="Low Stock"
                          icon={<AlertTriangle className="h-3.5 w-3.5" />}
                        />
                      ) : row.status === 'Stopped' ? (
                        <StatusText
                          tone="muted"
                          label="Paused"
                          icon={<PauseCircle className="h-3.5 w-3.5" />}
                        />
                      ) : (
                        <StatusText
                          tone="emerald"
                          label="Healthy"
                          icon={<CheckCircle2 className="h-3.5 w-3.5" />}
                        />
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-right whitespace-nowrap">
                      {row.stopReordering ? (
                        <span className="text-xs text-[#718078]">Paused</span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => togglePoItem(row)}
                          className={`min-h-[34px] inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                            inPo
                              ? 'bg-[#FAF7EF] text-[#103D2B] border border-[#145C3A]'
                              : 'border border-[#D4DDD6] bg-white text-[#172B22] hover:border-[#145C3A]'
                          }`}
                        >
                          {inPo ? (
                            <>
                              <Check className="h-3.5 w-3.5 text-[#145C3A]" />
                              <span>In PO ({poDraft[row.productId]})</span>
                            </>
                          ) : (
                            <>
                              <Plus className="h-3.5 w-3.5" />
                              <span>Add to PO</span>
                            </>
                          )}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Mobile (1-col) & Tablet (2-col) Cards */}
        <div className="lg:hidden grid grid-cols-1 md:grid-cols-2 gap-px bg-[#E5EAE5]">
          {forecastRows.map((row) => {
            const inPo = Boolean(poDraft[row.productId]);
            const noHistory = row.avgDailySales === 0 && row.forecastedDemand === 0;
            return (
              <div key={row.productId} className="bg-white p-4 space-y-2.5">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-[#172B22] leading-snug">{row.name}</p>
                    <p className="text-xs text-[#65766D] truncate mt-0.5">
                      <span className="font-mono">{row.sku}</span> · {row.supplierName}
                    </p>
                  </div>
                  <span
                    className={`text-xs font-semibold shrink-0 ${
                      row.status === 'Out of Stock'
                        ? 'text-red-700'
                        : row.status === 'Low Stock'
                          ? 'text-amber-700'
                          : row.status === 'Stopped'
                            ? 'text-[#65766D]'
                            : 'text-[#145C3A]'
                    }`}
                  >
                    {row.status}
                  </span>
                </div>
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-[#52635B] pt-1">
                  <span className="font-mono tabular-nums">
                    Shelf {row.currentStock} ·{' '}
                    {noHistory
                      ? 'No sales history'
                      : `Need ${row.forecastedDemand} (${row.avgDailySales.toFixed(1)}/d)`}
                  </span>
                  {!row.stopReordering && (
                    <button
                      type="button"
                      onClick={() => togglePoItem(row)}
                      className={`min-h-[34px] inline-flex items-center gap-1 rounded-lg px-3 py-1 text-xs font-semibold transition-colors ${
                        inPo
                          ? 'bg-[#FAF7EF] text-[#103D2B] border border-[#145C3A]'
                          : 'border border-[#D4DDD6] bg-white text-[#172B22]'
                      }`}
                    >
                      {inPo ? `In PO (${poDraft[row.productId]})` : '+ Add to PO'}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </SectionCard>

      {/* Purchase Order History */}
      <SectionCard>
        <SectionHeader
          title="Recent Purchase Orders"
          subtitle="Distributor orders recorded from this store"
        />
        {purchaseOrders.length === 0 ? (
          <EmptyState
            icon={<ClipboardList className="h-5 w-5" />}
            title="No purchase orders created yet"
            description="Add urgent low-stock items to your PO draft above to log a supplier order."
            className="py-9"
          />
        ) : (
          <div className="divide-y divide-[#E5EAE5]">
            {purchaseOrders.map((po) => (
              <div
                key={po.id}
                className="px-5 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2 hover:bg-[#FAF7EF]/45 transition-colors"
              >
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-[#172B22] font-mono">
                    {po.poNumber}{' '}
                    <span className="font-sans text-xs font-semibold text-[#145C3A]">
                      · {po.status}
                    </span>
                  </p>
                  <p className="text-xs text-[#65766D] mt-0.5 leading-relaxed">
                    {new Date(po.createdAt).toLocaleDateString('en-IN', {
                      day: '2-digit',
                      month: 'short',
                      year: 'numeric',
                    })}{' '}
                    · {po.items.map((i) => `${i.name} (${i.qty})`).join(', ')}
                  </p>
                </div>
                <span className="font-mono text-sm font-bold text-[#103D2B] tabular-nums shrink-0">
                  {formatINR(po.totalPaise)}
                </span>
              </div>
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
