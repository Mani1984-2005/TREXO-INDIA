import {
  AlertTriangle,
  CheckCircle2,
  MessageCircle,
  Minus,
  Package,
  Pencil,
  Plus,
  Search,
  X,
  XCircle,
} from 'lucide-react';
import { type FormEvent, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { HeroKpiStrip } from '../components/HeroKpiStrip';
import {
  EmptyState,
  PageHeader,
  SectionCard,
  SegmentedTabs,
  StatusText,
} from '../components/ui/DesignSystem';
import { STORE_INFO } from '../config';
import { useLedgerStore } from '../store/useLedgerStore';
import type { Product, ProductCategory } from '../types/domain';
import {
  daysSince,
  daysUntil,
  formatINR,
  getEffectivePricePaise,
  isDeadStock,
  isLowStock,
  isNearExpiry,
  rupeesToPaise,
} from '../utils/money';

type InventoryTab = 'all' | 'dead' | 'expiry' | 'low';

const CATEGORIES: ProductCategory[] = [
  'Grains & Atta',
  'Edible Oils',
  'Dairy & Daily',
  'Snacks & Beverages',
  'Home & Personal',
  'Specialty & Dry Fruits',
];

export function InventoryPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<InventoryTab>('all');
  const [query, setQuery] = useState('');
  const [showProductModal, setShowProductModal] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  // Add / Edit Item Form State
  const [name, setName] = useState('');
  const [sku, setSku] = useState('');
  const [category, setCategory] = useState<ProductCategory>('Grains & Atta');
  const [unit, setUnit] = useState('1 kg');
  const [costRupees, setCostRupees] = useState('');
  const [sellingRupees, setSellingRupees] = useState('');
  const [mrpRupees, setMrpRupees] = useState('');
  const [stockQty, setStockQty] = useState('12');
  const [reorderLevel, setReorderLevel] = useState('6');
  const [expiryDate, setExpiryDate] = useState('');
  const [supplierId, setSupplierId] = useState('');

  const products = useLedgerStore((s) => s.products);
  const suppliers = useLedgerStore((s) => s.suppliers);
  const adjustStock = useLedgerStore((s) => s.adjustStock);
  const setStopReordering = useLedgerStore((s) => s.setStopReordering);
  const createProduct = useLedgerStore((s) => s.createProduct);
  const updateProduct = useLedgerStore((s) => s.updateProduct);

  const closeProductModal = () => {
    setShowProductModal(false);
    setEditingProduct(null);
    setFormError(null);
  };

  const openAddModal = () => {
    setEditingProduct(null);
    setFormError(null);
    setName('');
    setSku('');
    setCategory('Grains & Atta');
    setUnit('1 kg');
    setCostRupees('');
    setSellingRupees('');
    setMrpRupees('');
    setStockQty('12');
    setReorderLevel('6');
    setExpiryDate('');
    setSupplierId(suppliers[0]?.id || 'sup-1');
    setShowProductModal(true);
  };

  const openEditModal = (product: Product) => {
    setEditingProduct(product);
    setFormError(null);
    setName(product.name);
    setSku(product.sku);
    setCategory(product.category);
    setUnit(product.unit);
    setCostRupees(String(product.costPaise / 100));
    setSellingRupees(String(product.sellingPricePaise / 100));
    setMrpRupees(String(product.mrpPaise / 100));
    setStockQty(String(product.stockQty));
    setReorderLevel(String(product.reorderLevel));
    setExpiryDate(product.expiryDate ? product.expiryDate.slice(0, 10) : '');
    setSupplierId(product.supplierId);
    setShowProductModal(true);
  };

  useEffect(() => {
    if (!showProductModal) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        closeProductModal();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [showProductModal]);

  const supplierMap = useMemo(() => new Map(suppliers.map((s) => [s.id, s])), [suppliers]);

  const counts = useMemo(() => {
    return {
      all: products.length,
      dead: products.filter((p) => isDeadStock(p)).length,
      expiry: products.filter((p) => isNearExpiry(p)).length,
      low: products.filter((p) => isLowStock(p)).length,
    };
  }, [products]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return products.filter((p) => {
      if (tab === 'dead' && !isDeadStock(p)) return false;
      if (tab === 'expiry' && !isNearExpiry(p)) return false;
      if (tab === 'low' && !isLowStock(p)) return false;
      if (!q) return true;
      return (
        p.name.toLowerCase().includes(q) ||
        p.sku.toLowerCase().includes(q) ||
        p.category.toLowerCase().includes(q)
      );
    });
  }, [products, tab, query]);

  const lowStockWhatsAppHref = useMemo(() => {
    const lowItems = products.filter((p) => isLowStock(p));
    const lines = [
      `Restock list from ${STORE_INFO.shopName}:`,
      ...lowItems.map(
        (p) =>
          `- ${p.name} (${p.sku}): ${p.stockQty} left, need ${Math.max(p.reorderLevel * 2, 10)} units`
      ),
      'Sent via Trexo',
    ];
    return `https://wa.me/?text=${encodeURIComponent(lines.join('\n'))}`;
  }, [products]);

  const liveMarginInfo = useMemo(() => {
    const cost = Number(costRupees);
    const sell = Number(sellingRupees);
    if (!Number.isFinite(cost) || !Number.isFinite(sell) || cost <= 0 || sell <= 0) {
      return null;
    }
    const marginPaise = rupeesToPaise(sell - cost);
    const marginPct = Math.round(((sell - cost) / sell) * 100);
    return { marginPaise, marginPct };
  }, [costRupees, sellingRupees]);

  const handleSaveProduct = async (e: FormEvent) => {
    e.preventDefault();
    const trimmedName = name.trim();
    const costNum = Number(costRupees);
    const sellNum = Number(sellingRupees);
    const mrpNum = mrpRupees.trim() ? Number(mrpRupees) : sellNum;
    const qtyNum = Number(stockQty);
    const reorderNum = Number(reorderLevel);

    if (!trimmedName) {
      setFormError('Enter a product name.');
      return;
    }
    if (!Number.isFinite(costNum) || costNum <= 0) {
      setFormError('Purchase cost must be greater than ₹0.');
      return;
    }
    if (!Number.isFinite(sellNum) || sellNum <= 0) {
      setFormError('Selling price must be greater than ₹0.');
      return;
    }
    if (!Number.isFinite(mrpNum) || mrpNum < sellNum) {
      setFormError('MRP must be equal to or greater than the selling price.');
      return;
    }
    if (!Number.isFinite(qtyNum) || qtyNum < 0) {
      setFormError('Stock quantity cannot be negative.');
      return;
    }
    if (!Number.isFinite(reorderNum) || reorderNum < 0) {
      setFormError('Reorder level cannot be negative.');
      return;
    }

    setFormError(null);
    const cost = rupeesToPaise(costNum);
    const sell = rupeesToPaise(sellNum);
    const mrp = rupeesToPaise(mrpNum);
    const normalizedExpiry = expiryDate ? new Date(`${expiryDate}T00:00:00`).toISOString() : null;
    const resolvedSupplierId = supplierId || suppliers[0]?.id || 'sup-1';

    if (editingProduct) {
      await updateProduct(editingProduct.id, {
        name: trimmedName,
        sku: sku.trim() || editingProduct.sku,
        category,
        unit: unit.trim() || '1 unit',
        mrpPaise: mrp,
        costPaise: cost,
        sellingPricePaise: sell,
        stockQty: Math.floor(qtyNum),
        reorderLevel: Math.floor(reorderNum),
        expiryDate: normalizedExpiry,
        supplierId: resolvedSupplierId,
      });
    } else {
      await createProduct({
        name: trimmedName,
        sku: sku.trim() || `SKU-${Math.floor(100 + Math.random() * 900)}`,
        category,
        unit: unit.trim() || '1 unit',
        mrpPaise: mrp,
        costPaise: cost,
        sellingPricePaise: sell,
        stockQty: Math.floor(qtyNum),
        reorderLevel: Math.floor(reorderNum),
        expiryDate: normalizedExpiry,
        supplierId: resolvedSupplierId,
      });
    }

    closeProductModal();
  };

  return (
    <div className="space-y-6 trexo-fade-in">
      <PageHeader
        title="Inventory Ledger"
        description="Manage shelf stock levels, pricing, idle capital, and expiry dates across your store."
        actions={
          <>
            {counts.low > 0 && (
              <a
                href={lowStockWhatsAppHref}
                target="_blank"
                rel="noopener noreferrer"
                className="min-h-[42px] inline-flex items-center gap-1.5 rounded-lg border border-[#E5EAE5] bg-white px-3.5 py-2 text-xs font-semibold text-[#172B22] hover:bg-[#FAF7EF] hover:border-[#145C3A] transition-colors whitespace-nowrap"
              >
                <MessageCircle className="h-4 w-4 text-[#145C3A]" />
                <span>WhatsApp Low Stock</span>
              </a>
            )}
            <button
              type="button"
              onClick={openAddModal}
              className="min-h-[42px] inline-flex items-center gap-1.5 rounded-lg bg-[#145C3A] px-4 py-2 text-xs sm:text-sm font-semibold text-white hover:bg-[#103D2B] transition-colors whitespace-nowrap shadow-[0_1px_2px_rgba(16,61,43,0.16)]"
            >
              <Plus className="h-4 w-4" />
              <span>Add Product</span>
            </button>
          </>
        }
      />

      <HeroKpiStrip />

      {/* Toolbar & Inventory View */}
      <SectionCard>
        <div className="border-b border-[#E5EAE5] p-4 flex flex-col lg:flex-row lg:items-center justify-between gap-3.5">
          <SegmentedTabs
            value={tab}
            onChange={setTab}
            ariaLabel="Inventory filter"
            options={[
              { id: 'all', label: `All Stock (${counts.all})` },
              { id: 'dead', label: `Dead Stock (${counts.dead})` },
              { id: 'expiry', label: `Near Expiry (${counts.expiry})` },
              { id: 'low', label: `Low / Out (${counts.low})` },
            ]}
          />

          <div className="relative w-full lg:w-72">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#718078]" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter by product, SKU, or category…"
              className="w-full min-h-[40px] rounded-lg border border-[#D4DDD6] bg-white py-2 pl-9 pr-8 text-sm text-[#172B22] placeholder:text-[#718078] focus:border-[#145C3A] focus:outline-none"
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-[#718078] hover:text-[#172B22]"
                aria-label="Clear filter"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>

        {products.length === 0 ? (
          <EmptyState
            icon={<Package className="h-5 w-5" />}
            title="Your inventory is empty"
            description="Add your first product with purchase cost, selling price, and opening stock."
            action={
              <button
                type="button"
                onClick={openAddModal}
                className="min-h-[40px] inline-flex items-center gap-1.5 rounded-lg bg-[#145C3A] px-4 py-2 text-xs font-semibold text-white hover:bg-[#103D2B]"
              >
                <Plus className="h-4 w-4" />
                <span>Add First Product</span>
              </button>
            }
          />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<Search className="h-5 w-5" />}
            title="No items in this view"
            description={
              tab === 'dead'
                ? 'All slow-moving items have been cleared or sold.'
                : 'Try adjusting your search or switching inventory tabs.'
            }
            action={
              (query || tab !== 'all') && (
                <button
                  type="button"
                  onClick={() => {
                    setQuery('');
                    setTab('all');
                  }}
                  className="min-h-[38px] rounded-lg border border-[#E5EAE5] bg-white px-4 py-2 text-xs font-semibold text-[#172B22] hover:bg-[#FAF7EF]"
                >
                  Show All Stock
                </button>
              )
            }
          />
        ) : (
          <>
            {/* Desktop Data Table (lg+ avoids cramped columns on 768px portrait tablet) */}
            <div className="hidden lg:block overflow-x-auto trexo-scroll">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-[#E5EAE5] bg-[#FAF7EF] text-xs font-semibold text-[#52635B]">
                    <th className="px-5 py-3">Item &amp; SKU</th>
                    <th className="px-4 py-3 text-right">Stock</th>
                    <th className="px-4 py-3 text-right">Cost</th>
                    <th className="px-4 py-3 text-right">Counter Price</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-5 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5EAE5]">
                  {filtered.map((p) => {
                    const dead = isDeadStock(p);
                    const nearExp = isNearExpiry(p);
                    const expDays = daysUntil(p.expiryDate);
                    const idleDays = daysSince(p.lastSoldAt);
                    const effPrice = getEffectivePricePaise(p);
                    const supplier = supplierMap.get(p.supplierId);

                    return (
                      <tr key={p.id} className="hover:bg-[#FAF7EF]/50 transition-colors">
                        <td className="px-5 py-3.5 max-w-[280px]">
                          <p className="font-semibold text-[#172B22] truncate">{p.name}</p>
                          <p className="mt-0.5 text-xs text-[#65766D] truncate">
                            <span className="font-mono">{p.sku}</span> · {p.category} ·{' '}
                            {supplier?.name ?? 'Local Distributor'}
                          </p>
                        </td>

                        <td className="px-4 py-3.5 text-right whitespace-nowrap">
                          <div className="inline-flex items-center gap-1 rounded-lg border border-[#E5EAE5] bg-[#F3F5F2]/70 p-0.5">
                            <button
                              type="button"
                              onClick={() => adjustStock(p.id, -1)}
                              disabled={p.stockQty <= 0}
                              className="rounded-md bg-white p-1.5 text-[#172B22] hover:text-[#145C3A] disabled:opacity-40 transition-colors"
                              aria-label={`Decrease stock for ${p.name}`}
                            >
                              <Minus className="h-3.5 w-3.5" />
                            </button>
                            <span className="w-9 text-center font-mono text-sm font-semibold text-[#172B22] tabular-nums">
                              {p.stockQty}
                            </span>
                            <button
                              type="button"
                              onClick={() => adjustStock(p.id, 1)}
                              className="rounded-md bg-white p-1.5 text-[#172B22] hover:text-[#145C3A] transition-colors"
                              aria-label={`Increase stock for ${p.name}`}
                            >
                              <Plus className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </td>

                        <td className="px-4 py-3.5 text-right font-mono text-[#65766D] tabular-nums whitespace-nowrap">
                          {formatINR(p.costPaise)}
                        </td>

                        <td className="px-4 py-3.5 text-right font-mono tabular-nums whitespace-nowrap">
                          <span className="font-semibold text-[#103D2B]">
                            {formatINR(effPrice)}
                          </span>
                          {effPrice < p.sellingPricePaise && (
                            <p className="text-[11px] text-[#145C3A] font-sans font-medium">
                              Offer (was {formatINR(p.sellingPricePaise)})
                            </p>
                          )}
                        </td>

                        <td className="px-4 py-3.5 text-xs">
                          {p.stockQty === 0 ? (
                            <StatusText
                              tone="crimson"
                              label="Out of Stock"
                              icon={<XCircle className="h-3.5 w-3.5" />}
                            />
                          ) : p.stockQty <= p.reorderLevel ? (
                            <StatusText
                              tone="amber"
                              label={`Low Stock (min ${p.reorderLevel})`}
                              icon={<AlertTriangle className="h-3.5 w-3.5" />}
                            />
                          ) : (
                            <StatusText
                              tone="emerald"
                              label="In Stock"
                              icon={<CheckCircle2 className="h-3.5 w-3.5" />}
                            />
                          )}

                          {dead && p.stockQty > 0 && (
                            <p className="mt-0.5 text-[11px] text-red-700">
                              Dead stock · {idleDays}d idle ·{' '}
                              <span className="font-mono tabular-nums">
                                {formatINR(p.stockQty * p.costPaise)}
                              </span>
                            </p>
                          )}
                          {!dead && nearExp && expDays !== null && p.stockQty > 0 && (
                            <p className="mt-0.5 text-[11px] text-amber-700">
                              Near expiry · {expDays}d left
                            </p>
                          )}
                          {p.stopReordering && (
                            <p className="mt-0.5 text-[11px] text-[#65766D]">Reordering paused</p>
                          )}
                        </td>

                        <td className="px-5 py-3.5 text-right whitespace-nowrap">
                          <div className="inline-flex items-center gap-3 text-xs font-semibold">
                            <button
                              type="button"
                              onClick={() => openEditModal(p)}
                              className="inline-flex items-center gap-1 text-[#172B22] hover:text-[#145C3A] transition-colors"
                              aria-label={`Edit ${p.name}`}
                            >
                              <Pencil className="h-3 w-3" />
                              <span>Edit</span>
                            </button>
                            {(dead || nearExp) && p.stockQty > 0 && (
                              <button
                                type="button"
                                onClick={() => navigate('/rescue')}
                                className="text-[#145C3A] hover:text-[#103D2B] transition-colors"
                              >
                                Rescue
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={() => setStopReordering(p.id, !p.stopReordering)}
                              className="text-[#65766D] hover:text-[#172B22] transition-colors"
                            >
                              {p.stopReordering ? 'Resume' : 'Pause'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile (1-col) & Tablet (2-col) Responsive Card Grid (< lg) */}
            <div className="lg:hidden grid grid-cols-1 md:grid-cols-2 gap-px bg-[#E5EAE5]">
              {filtered.map((p) => {
                const dead = isDeadStock(p);
                const nearExp = isNearExpiry(p);
                const expDays = daysUntil(p.expiryDate);
                const effPrice = getEffectivePricePaise(p);
                const supplier = supplierMap.get(p.supplierId);

                return (
                  <div key={p.id} className="bg-white p-4 flex flex-col justify-between gap-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-[#172B22] leading-snug">
                          {p.name}
                        </p>
                        <p className="mt-0.5 text-xs text-[#65766D] truncate">
                          <span className="font-mono">{p.sku}</span> · {p.category}
                        </p>
                        <p className="text-[11px] text-[#718078] truncate mt-0.5">
                          {supplier?.name ?? 'Local Distributor'} · {p.unit}
                        </p>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="font-mono text-sm font-bold text-[#103D2B] tabular-nums">
                          {formatINR(effPrice)}
                        </p>
                        <p className="text-[11px] font-mono text-[#65766D] tabular-nums">
                          Cost {formatINR(p.costPaise)}
                        </p>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center justify-between gap-2.5 text-xs">
                      <div className="min-w-0">
                        {p.stockQty === 0 ? (
                          <StatusText
                            tone="crimson"
                            label="Out of Stock"
                            icon={<XCircle className="h-3.5 w-3.5" />}
                          />
                        ) : p.stockQty <= p.reorderLevel ? (
                          <StatusText
                            tone="amber"
                            label={`Low Stock (min ${p.reorderLevel})`}
                            icon={<AlertTriangle className="h-3.5 w-3.5" />}
                          />
                        ) : (
                          <StatusText
                            tone="emerald"
                            label="In Stock"
                            icon={<CheckCircle2 className="h-3.5 w-3.5" />}
                          />
                        )}
                        {dead && p.stockQty > 0 && (
                          <p className="mt-0.5 text-[11px] text-red-700">
                            Dead ({daysSince(p.lastSoldAt)}d) · {formatINR(p.stockQty * p.costPaise)}
                          </p>
                        )}
                        {!dead && nearExp && expDays !== null && p.stockQty > 0 && (
                          <p className="mt-0.5 text-[11px] text-amber-700">
                            Near expiry · {expDays}d left
                          </p>
                        )}
                      </div>

                      <div className="inline-flex items-center gap-1 rounded-lg border border-[#E5EAE5] bg-[#F3F5F2]/80 p-0.5 shrink-0">
                        <button
                          type="button"
                          onClick={() => adjustStock(p.id, -1)}
                          disabled={p.stockQty <= 0}
                          className="min-h-[34px] min-w-[34px] flex items-center justify-center rounded-md bg-white text-[#172B22] disabled:opacity-40"
                          aria-label={`Decrease stock for ${p.name}`}
                        >
                          <Minus className="h-3.5 w-3.5" />
                        </button>
                        <span className="w-8 text-center font-mono text-sm font-semibold tabular-nums">
                          {p.stockQty}
                        </span>
                        <button
                          type="button"
                          onClick={() => adjustStock(p.id, 1)}
                          className="min-h-[34px] min-w-[34px] flex items-center justify-center rounded-md bg-white text-[#172B22]"
                          aria-label={`Increase stock for ${p.name}`}
                        >
                          <Plus className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-2.5 border-t border-[#E5EAE5]/80 text-xs font-semibold">
                      <button
                        type="button"
                        onClick={() => openEditModal(p)}
                        className="inline-flex items-center gap-1 text-[#172B22] hover:text-[#145C3A]"
                      >
                        <Pencil className="h-3 w-3" />
                        <span>Edit Details</span>
                      </button>
                      {(dead || nearExp) && p.stockQty > 0 && (
                        <button
                          type="button"
                          onClick={() => navigate('/rescue')}
                          className="text-[#145C3A] hover:text-[#103D2B]"
                        >
                          Rescue Cash
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => setStopReordering(p.id, !p.stopReordering)}
                        className="text-[#65766D] hover:text-[#172B22]"
                      >
                        {p.stopReordering ? 'Resume Reorder' : 'Stop Reorder'}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </SectionCard>

      {/* Add / Edit Item Modal */}
      {showProductModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#103D2B]/55 backdrop-blur-[1px] p-3 sm:p-4"
          role="dialog"
          aria-modal="true"
          aria-label={editingProduct ? 'Edit inventory product' : 'Add new inventory item'}
          onClick={closeProductModal}
        >
          <div
            className="trexo-modal-in flex max-h-[90vh] w-full max-w-lg flex-col rounded-xl border border-[#D8CEB6] bg-white shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-white/10 bg-[#103D2B] px-5 py-4 text-white shrink-0">
              <div>
                <h2 className="text-base font-semibold">
                  {editingProduct ? 'Edit Inventory Product' : 'Add Inventory Product'}
                </h2>
                <p className="text-[11px] text-white/70 mt-0.5">
                  {editingProduct
                    ? `Updating ${editingProduct.sku}`
                    : 'Record purchase cost, counter selling price, and opening stock'}
                </p>
              </div>
              <button
                type="button"
                onClick={closeProductModal}
                className="rounded-lg p-1.5 text-white/75 hover:bg-white/10 hover:text-white transition-colors"
                aria-label="Close modal"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form
              onSubmit={handleSaveProduct}
              noValidate
              className="flex flex-col flex-1 min-h-0"
            >
              <div className="overflow-y-auto trexo-scroll p-5 space-y-4">
                {formError && (
                  <p
                    role="alert"
                    className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-800"
                  >
                    {formError}
                  </p>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="sm:col-span-2">
                    <label className="block text-xs font-semibold text-[#172B22] mb-1">
                      Product Name
                    </label>
                    <input
                      required
                      type="text"
                      value={name}
                      onChange={(e) => {
                        setName(e.target.value);
                        if (formError) setFormError(null);
                      }}
                      placeholder="e.g., India Gate Basmati Rice 5kg"
                      className="w-full min-h-[40px] rounded-lg border border-[#D4DDD6] px-3 py-2 text-sm text-[#172B22] focus:border-[#145C3A] focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-[#172B22] mb-1">
                      SKU Code
                    </label>
                    <input
                      type="text"
                      value={sku}
                      onChange={(e) => setSku(e.target.value)}
                      placeholder="e.g., GRN-024"
                      className="w-full min-h-[40px] rounded-lg border border-[#D4DDD6] px-3 py-2 text-sm font-mono text-[#172B22] focus:border-[#145C3A] focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-[#172B22] mb-1">Unit</label>
                    <input
                      type="text"
                      value={unit}
                      onChange={(e) => setUnit(e.target.value)}
                      placeholder="e.g., 1 kg pack"
                      className="w-full min-h-[40px] rounded-lg border border-[#D4DDD6] px-3 py-2 text-sm text-[#172B22] focus:border-[#145C3A] focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-[#172B22] mb-1">
                      Category
                    </label>
                    <select
                      value={category}
                      onChange={(e) => setCategory(e.target.value as ProductCategory)}
                      className="w-full min-h-[40px] rounded-lg border border-[#D4DDD6] bg-white px-3 py-2 text-sm text-[#172B22] focus:border-[#145C3A] focus:outline-none"
                    >
                      {CATEGORIES.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-[#172B22] mb-1">
                      Supplier
                    </label>
                    <select
                      value={supplierId || suppliers[0]?.id || ''}
                      onChange={(e) => setSupplierId(e.target.value)}
                      className="w-full min-h-[40px] rounded-lg border border-[#D4DDD6] bg-white px-3 py-2 text-sm text-[#172B22] focus:border-[#145C3A] focus:outline-none"
                    >
                      {suppliers.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-[#172B22] mb-1">
                      Purchase Cost (₹)
                    </label>
                    <input
                      required
                      type="number"
                      min="1"
                      step="0.5"
                      value={costRupees}
                      onChange={(e) => {
                        setCostRupees(e.target.value);
                        if (formError) setFormError(null);
                      }}
                      placeholder="180"
                      className="w-full min-h-[40px] rounded-lg border border-[#D4DDD6] px-3 py-2 text-sm font-mono text-[#172B22] focus:border-[#145C3A] focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-[#172B22] mb-1">
                      Selling Price (₹)
                    </label>
                    <input
                      required
                      type="number"
                      min="1"
                      step="0.5"
                      value={sellingRupees}
                      onChange={(e) => {
                        setSellingRupees(e.target.value);
                        if (formError) setFormError(null);
                      }}
                      placeholder="220"
                      className="w-full min-h-[40px] rounded-lg border border-[#D4DDD6] px-3 py-2 text-sm font-mono text-[#172B22] focus:border-[#145C3A] focus:outline-none"
                    />
                  </div>

                  {liveMarginInfo && (
                    <div className="sm:col-span-2 rounded-lg border border-[#E4DCC6] bg-[#FAF7EF] px-3.5 py-2 flex items-center justify-between text-xs">
                      <span className="text-[#52635B]">Unit Margin Preview</span>
                      <span
                        className={`font-mono font-semibold tabular-nums ${
                          liveMarginInfo.marginPaise >= 0 ? 'text-[#145C3A]' : 'text-red-700'
                        }`}
                      >
                        {formatINR(liveMarginInfo.marginPaise)} ({liveMarginInfo.marginPct}%)
                      </span>
                    </div>
                  )}

                  <div>
                    <label className="block text-xs font-semibold text-[#172B22] mb-1">
                      MRP (₹, optional)
                    </label>
                    <input
                      type="number"
                      min="1"
                      step="0.5"
                      value={mrpRupees}
                      onChange={(e) => {
                        setMrpRupees(e.target.value);
                        if (formError) setFormError(null);
                      }}
                      placeholder="Defaults to selling price"
                      className="w-full min-h-[40px] rounded-lg border border-[#D4DDD6] px-3 py-2 text-sm font-mono text-[#172B22] focus:border-[#145C3A] focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-[#172B22] mb-1">
                      {editingProduct ? 'Current Stock Qty' : 'Opening Stock Qty'}
                    </label>
                    <input
                      required
                      type="number"
                      min="0"
                      value={stockQty}
                      onChange={(e) => {
                        setStockQty(e.target.value);
                        if (formError) setFormError(null);
                      }}
                      className="w-full min-h-[40px] rounded-lg border border-[#D4DDD6] px-3 py-2 text-sm font-mono text-[#172B22] focus:border-[#145C3A] focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-[#172B22] mb-1">
                      Reorder Level (min units)
                    </label>
                    <input
                      required
                      type="number"
                      min="0"
                      value={reorderLevel}
                      onChange={(e) => {
                        setReorderLevel(e.target.value);
                        if (formError) setFormError(null);
                      }}
                      className="w-full min-h-[40px] rounded-lg border border-[#D4DDD6] px-3 py-2 text-sm font-mono text-[#172B22] focus:border-[#145C3A] focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-[#172B22] mb-1">
                      Expiry Date (optional)
                    </label>
                    <input
                      type="date"
                      value={expiryDate}
                      onChange={(e) => setExpiryDate(e.target.value)}
                      className="w-full min-h-[40px] rounded-lg border border-[#D4DDD6] px-3 py-2 text-sm text-[#172B22] focus:border-[#145C3A] focus:outline-none"
                    />
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-[#E4DCC6] bg-[#FAF7EF] shrink-0">
                <button
                  type="button"
                  onClick={closeProductModal}
                  className="min-h-[40px] rounded-lg border border-[#D4DDD6] bg-white px-4 py-2 text-sm font-medium text-[#172B22] hover:bg-[#F3F5F2] transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="min-h-[40px] rounded-lg bg-[#145C3A] px-4 py-2 text-sm font-semibold text-white hover:bg-[#103D2B] transition-colors"
                >
                  {editingProduct ? 'Save Changes' : 'Save Product'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
