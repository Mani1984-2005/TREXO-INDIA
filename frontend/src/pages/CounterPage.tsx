import {
  ArrowRight,
  Coins,
  Minus,
  Package,
  Plus,
  QrCode,
  Search,
  ShoppingBag,
  Trash2,
  X,
} from 'lucide-react';
import { type KeyboardEvent, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { HeroKpiStrip } from '../components/HeroKpiStrip';
import { PaymentMethodSelector } from '../components/payments/PaymentMethodSelector';
import {
  type ConfirmedPaymentResult,
  UpiPaymentModal,
} from '../components/payments/UpiPaymentModal';
import { UpiSettingsModal } from '../components/payments/UpiSettingsModal';
import { ReceiptModal } from '../components/ReceiptModal';
import { EmptyState, PageHeader, SectionCard } from '../components/ui/DesignSystem';
import { useCounterFocusShortcut, useSaveShortcut } from '../hooks/useGlobalShortcuts';
import { TRANSLATIONS } from '../i18n/translations';
import { useLedgerStore } from '../store/useLedgerStore';
import type { PaymentMethod, Product, ProductCategory } from '../types/domain';
import {
  calculateCartTotals,
  daysSince,
  daysUntil,
  formatINR,
  getDiscountPercent,
  getEffectivePricePaise,
  isDeadStock,
  isNearExpiry,
} from '../utils/money';
import { getModifierLabel } from '../utils/shortcuts';
import { isValidUpiId } from '../utils/upi';

type FilterTab = 'All' | 'Counter Offers' | ProductCategory;

const FILTER_TABS: FilterTab[] = [
  'All',
  'Counter Offers',
  'Grains & Atta',
  'Edible Oils',
  'Dairy & Daily',
  'Snacks & Beverages',
  'Home & Personal',
  'Specialty & Dry Fruits',
];

export function CounterPage() {
  const navigate = useNavigate();
  const searchInputRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState<FilterTab>('All');
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('cash');
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);
  const [upiModalOpen, setUpiModalOpen] = useState(false);
  const [upiSettingsOpen, setUpiSettingsOpen] = useState(false);

  const language = useLedgerStore((s) => s.language);
  const products = useLedgerStore((s) => s.products);
  const customers = useLedgerStore((s) => s.customers);
  const upiConfig = useLedgerStore((s) => s.upiConfig);
  const cart = useLedgerStore((s) => s.cart);
  const addToCart = useLedgerStore((s) => s.addToCart);
  const updateCartQty = useLedgerStore((s) => s.updateCartQty);
  const removeFromCart = useLedgerStore((s) => s.removeFromCart);
  const clearCart = useLedgerStore((s) => s.clearCart);
  const completeSale = useLedgerStore((s) => s.completeSale);
  const lastCompletedSale = useLedgerStore((s) => s.lastCompletedSale);
  const clearLastCompletedSale = useLedgerStore((s) => s.clearLastCompletedSale);
  const pushToast = useLedgerStore((s) => s.pushToast);

  const t = TRANSLATIONS[language];
  const modLabel = getModifierLabel();

  const getDisplayName = (product: Product) => {
    if (language === 'hi' && product.hindiName) return product.hindiName;
    if (language === 'kn' && product.kannadaName) return product.kannadaName;
    return product.name;
  };

  const productMap = useMemo(() => new Map(products.map((p) => [p.id, p])), [products]);

  const filteredProducts = useMemo(() => {
    const q = query.trim().toLowerCase();
    return products.filter((p) => {
      if (activeCategory === 'Counter Offers') {
        if (p.counterDiscountPricePaise === null) return false;
      } else if (activeCategory !== 'All' && p.category !== activeCategory) {
        return false;
      }

      if (!q) return true;
      return (
        p.name.toLowerCase().includes(q) ||
        p.sku.toLowerCase().includes(q) ||
        (p.hindiName && p.hindiName.toLowerCase().includes(q)) ||
        (p.kannadaName && p.kannadaName.toLowerCase().includes(q)) ||
        p.category.toLowerCase().includes(q)
      );
    });
  }, [products, query, activeCategory]);

  // Suggest top dead-stock or counter-discounted item to bundle at checkout
  const bundleCandidate = useMemo(() => {
    const candidates = products.filter(
      (p) =>
        p.stockQty > 0 &&
        (isDeadStock(p) || isNearExpiry(p) || p.counterDiscountPricePaise !== null)
    );
    if (candidates.length === 0) return null;
    return candidates.sort((a, b) => {
      const aDisc = a.counterDiscountPricePaise !== null ? 1 : 0;
      const bDisc = b.counterDiscountPricePaise !== null ? 1 : 0;
      if (aDisc !== bDisc) return bDisc - aDisc;
      return b.stockQty * b.costPaise - a.stockQty * a.costPaise;
    })[0];
  }, [products]);

  const cartLines = useMemo(() => {
    return cart
      .map((c) => {
        const product = productMap.get(c.productId);
        if (!product) return null;
        const unitPricePaise = getEffectivePricePaise(product);
        const originalPricePaise = product.sellingPricePaise;
        return {
          product,
          qty: c.qty,
          unitPricePaise,
          originalPricePaise,
          lineTotalPaise: unitPricePaise * c.qty,
          rescuesDeadStock: isDeadStock(product) || isNearExpiry(product),
        };
      })
      .filter((x): x is NonNullable<typeof x> => x !== null);
  }, [cart, productMap]);

  const totals = useMemo(
    () =>
      calculateCartTotals(
        cartLines.map((l) => ({
          unitPricePaise: l.unitPricePaise,
          originalPricePaise: l.originalPricePaise,
          qty: l.qty,
        }))
      ),
    [cartLines]
  );

  const handleSearchKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const firstInStock = filteredProducts.find((p) => p.stockQty > 0);
      if (firstInStock) {
        addToCart(firstInStock.id, 1);
        setQuery('');
      } else {
        pushToast('No in-stock item matched', 'Check Inventory or Restock Planner.', 'amber');
      }
    }
  };

  const handleCompleteSale = async () => {
    if (cartLines.length === 0 || submitting) return;

    // UPI payments must go through QR display + manual owner verification first
    if (paymentMethod === 'upi') {
      setUpiModalOpen(true);
      return;
    }

    if (paymentMethod === 'udhaar' && !selectedCustomerId) {
      pushToast(
        'Select a customer for Udhaar',
        'Choose an account before completing credit bill.',
        'amber'
      );
      return;
    }
    setSubmitting(true);
    try {
      await completeSale(paymentMethod, selectedCustomerId || null);
      if (paymentMethod === 'udhaar') {
        setPaymentMethod('cash');
        setSelectedCustomerId('');
      }
    } catch (err) {
      pushToast(
        'Unable to complete bill',
        err instanceof Error ? err.message : 'Please review cart items and try again.',
        'amber'
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleConfirmModalPayment = async (result: ConfirmedPaymentResult) => {
    if (result.paymentMethod === 'cash') {
      await completeSale('cash', null);
    } else {
      await completeSale('upi', null, {
        upiTransactionRef: result.transactionRef,
        upiUtrNumber: result.utrNumber,
        upiIdUsed: result.upiIdUsed,
        paymentStatus: result.status,
        isDemoPayment: result.isDemo,
      });
    }
    setUpiModalOpen(false);
  };

  // Standardized shortcut hooks: focus search on Ctrl+N and complete/open payment on Ctrl+S
  useCounterFocusShortcut(() => {
    searchInputRef.current?.focus();
    searchInputRef.current?.select();
  });

  useSaveShortcut(
    () => {
      void handleCompleteSale();
    },
    cartLines.length > 0 && !lastCompletedSale && !upiModalOpen && !upiSettingsOpen && !submitting
  );

  return (
    <div className="space-y-6 trexo-fade-in">
      <PageHeader
        title="Counter POS"
        description="High-speed everyday billing with instant Cash, UPI QR checkout, and customer Udhaar credit."
        actions={
          <p className="hidden lg:inline-flex items-center gap-3 text-xs text-[#65766D]">
            <span>
              <kbd className="font-mono text-[11px] font-semibold text-[#172B22]">{modLabel}+N</kbd>{' '}
              New bill
            </span>
            <span aria-hidden="true">·</span>
            <span>
              <kbd className="font-mono text-[11px] font-semibold text-[#172B22]">{modLabel}+S</kbd>{' '}
              Complete bill
            </span>
          </p>
        }
      />

      <HeroKpiStrip />

      <div className="no-print grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left: Search, Category Filters, Bundle Strip & Product Catalog */}
        <div className="lg:col-span-7 xl:col-span-8 space-y-5">
          {/* Search Bar & Category Filter */}
          <SectionCard className="p-4 space-y-3.5">
            <div className="relative flex items-center">
              <Search className="pointer-events-none absolute left-3.5 h-4 w-4 text-[#145C3A]" />
              <input
                ref={searchInputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleSearchKeyDown}
                placeholder={t.searchPlaceholder}
                aria-label="Search products to bill"
                className="w-full min-h-[44px] rounded-lg border border-[#D4DDD6] bg-white py-2.5 pl-10 pr-24 text-sm text-[#172B22] placeholder:text-[#718078] focus:border-[#145C3A] focus:outline-none transition-colors"
              />
              {query ? (
                <button
                  type="button"
                  onClick={() => {
                    setQuery('');
                    searchInputRef.current?.focus();
                  }}
                  className="absolute right-2.5 rounded-md p-1.5 text-[#718078] hover:bg-[#F3F5F2] hover:text-[#172B22]"
                  aria-label="Clear search"
                >
                  <X className="h-4 w-4" />
                </button>
              ) : (
                <span className="pointer-events-none hidden sm:inline absolute right-3 text-[11px] text-[#718078]">
                  Enter to add
                </span>
              )}
            </div>

            <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 trexo-scroll">
              {FILTER_TABS.map((cat) => {
                const isActive = activeCategory === cat;
                return (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => setActiveCategory(cat)}
                    className={`min-h-[34px] rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-150 whitespace-nowrap shrink-0 ${
                      isActive
                        ? 'bg-[#103D2B] text-white font-semibold'
                        : 'bg-[#F3F5F2] text-[#5F7068] hover:bg-[#E5EAE5] hover:text-[#172B22]'
                    }`}
                  >
                    {cat}
                  </button>
                );
              })}
            </div>
          </SectionCard>

          {/* Dead-Stock Bundle Suggestion Strip */}
          {bundleCandidate && (
            <SectionCard
              variant="warm"
              className="px-5 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
            >
              <div className="space-y-1 min-w-0">
                <div className="flex items-center gap-2 text-xs font-semibold text-[#145C3A]">
                  <Coins className="h-3.5 w-3.5 text-[#C6A15B] shrink-0" />
                  <span>{t.deadStockBundleTitle}</span>
                </div>
                <p className="text-sm font-semibold text-[#172B22] truncate">
                  {getDisplayName(bundleCandidate)}{' '}
                  <span className="font-normal text-[#65766D]">· {bundleCandidate.unit}</span>
                </p>
                <p className="text-xs text-[#52635B]">
                  {bundleCandidate.counterDiscountPricePaise !== null ? (
                    <>
                      Offer live at{' '}
                      <span className="font-mono font-semibold text-[#145C3A] tabular-nums">
                        {formatINR(bundleCandidate.counterDiscountPricePaise)}
                      </span>{' '}
                      (was {formatINR(bundleCandidate.sellingPricePaise)}) ·{' '}
                      {formatINR(bundleCandidate.stockQty * bundleCandidate.costPaise)} trapped
                    </>
                  ) : (
                    <>
                      Idle {daysSince(bundleCandidate.lastSoldAt)}d ·{' '}
                      {formatINR(bundleCandidate.stockQty * bundleCandidate.costPaise)} trapped in{' '}
                      {bundleCandidate.stockQty} units
                    </>
                  )}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {bundleCandidate.counterDiscountPricePaise === null && (
                  <button
                    type="button"
                    onClick={() => navigate('/rescue')}
                    className="min-h-[38px] inline-flex items-center gap-1 rounded-lg border border-[#D8CEB6] bg-white px-3 py-2 text-xs font-medium text-[#172B22] hover:border-[#145C3A] transition-colors whitespace-nowrap"
                  >
                    <span>Set Offer</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => addToCart(bundleCandidate.id, 1)}
                  className="min-h-[38px] inline-flex items-center gap-1.5 rounded-lg bg-[#145C3A] px-3.5 py-2 text-xs font-semibold text-white hover:bg-[#103D2B] transition-colors whitespace-nowrap"
                >
                  <Plus className="h-3.5 w-3.5" />
                  <span>Add to Bill</span>
                </button>
              </div>
            </SectionCard>
          )}

          {/* Product Catalog Grid */}
          {products.length === 0 ? (
            <SectionCard>
              <EmptyState
                icon={<Package className="h-5 w-5" />}
                title="No products in inventory yet"
                description="Add your store products in Inventory first so you can bill them at the Counter."
                action={
                  <button
                    type="button"
                    onClick={() => navigate('/inventory')}
                    className="min-h-[40px] rounded-lg bg-[#145C3A] px-4 py-2 text-xs font-semibold text-white hover:bg-[#103D2B] transition-colors"
                  >
                    Add First Product
                  </button>
                }
              />
            </SectionCard>
          ) : filteredProducts.length === 0 ? (
            <SectionCard>
              <EmptyState
                icon={<Search className="h-5 w-5" />}
                title="No items match your filter"
                description="Try another product name, SKU, or switch back to All categories."
                action={
                  <button
                    type="button"
                    onClick={() => {
                      setQuery('');
                      setActiveCategory('All');
                    }}
                    className="min-h-[38px] rounded-lg border border-[#E5EAE5] bg-white px-4 py-2 text-xs font-semibold text-[#172B22] hover:bg-[#FAF7EF] transition-colors"
                  >
                    Reset Search
                  </button>
                }
              />
            </SectionCard>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
              {filteredProducts.map((product) => {
                const effPrice = getEffectivePricePaise(product);
                const hasDiscount = effPrice < product.sellingPricePaise;
                const discountPct = getDiscountPercent(product.sellingPricePaise, effPrice);
                const outOfStock = product.stockQty <= 0;
                const lowStock = !outOfStock && product.stockQty <= product.reorderLevel;
                const dead = isDeadStock(product);
                const expDays = daysUntil(product.expiryDate);
                const nearExp = isNearExpiry(product);
                const inCartQty = cart.find((c) => c.productId === product.id)?.qty ?? 0;

                return (
                  <button
                    key={product.id}
                    type="button"
                    disabled={outOfStock}
                    onClick={() => addToCart(product.id, 1)}
                    className={`group text-left rounded-xl border p-4 transition-all duration-150 flex flex-col justify-between gap-3 ${
                      outOfStock
                        ? 'border-dashed border-[#D6DDD8] bg-[#F3F5F2]/85 opacity-65 cursor-not-allowed'
                        : inCartQty > 0
                          ? 'border-[#145C3A] bg-[#FAF7EF]/75 shadow-[0_1px_3px_rgba(20,92,58,0.12)]'
                          : 'border-[#E5EAE5] bg-white shadow-[0_1px_2px_rgba(16,61,43,0.04)] hover:border-[#145C3A]/55 hover:bg-[#FAF7EF]/35 active:scale-[0.99]'
                    }`}
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between gap-2 text-[11px] text-[#65766D]">
                        <span className="font-mono">{product.sku}</span>
                        <span className="truncate">{product.unit}</span>
                      </div>
                      <p className="text-sm font-semibold text-[#172B22] leading-snug line-clamp-2">
                        {getDisplayName(product)}
                      </p>
                      <p className="text-xs text-[#65766D]">
                        {outOfStock ? (
                          <span className="font-semibold text-red-700">Out of stock</span>
                        ) : (
                          <>
                            <span
                              className={`font-mono tabular-nums font-medium ${
                                lowStock ? 'text-amber-700 font-semibold' : 'text-[#172B22]'
                              }`}
                            >
                              {product.stockQty}
                            </span>{' '}
                            {lowStock ? 'left · Low' : 'in stock'}
                            {dead && (
                              <>
                                {' · '}
                                <span className="text-amber-700 font-medium">
                                  Slow ({daysSince(product.lastSoldAt)}d)
                                </span>
                              </>
                            )}
                            {!dead && nearExp && expDays !== null && (
                              <>
                                {' · '}
                                <span className="text-amber-700 font-medium">Exp {expDays}d</span>
                              </>
                            )}
                          </>
                        )}
                      </p>
                    </div>

                    <div className="flex items-end justify-between gap-2 pt-2.5 border-t border-[#E5EAE5]">
                      <div className="min-w-0">
                        <div className="flex items-baseline gap-2 flex-wrap">
                          <span className="font-mono text-base font-bold text-[#103D2B] tabular-nums">
                            {formatINR(effPrice)}
                          </span>
                          {hasDiscount && (
                            <span className="font-mono text-xs text-[#718078] line-through tabular-nums">
                              {formatINR(product.sellingPricePaise)}
                            </span>
                          )}
                        </div>
                        {hasDiscount && (
                          <p className="text-[11px] font-medium text-[#145C3A] mt-0.5">
                            Offer · {discountPct}% off
                          </p>
                        )}
                      </div>

                      {!outOfStock && (
                        <span
                          className={`text-xs font-semibold whitespace-nowrap shrink-0 transition-colors ${
                            inCartQty > 0
                              ? 'text-[#103D2B]'
                              : 'text-[#145C3A] group-hover:text-[#103D2B]'
                          }`}
                        >
                          {inCartQty > 0 ? `In bill · ${inCartQty}` : `+ ${t.addToBill}`}
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Right: Dedicated Sticky POS Billing Panel */}
        <aside className="lg:col-span-5 xl:col-span-4 lg:sticky lg:top-22 rounded-xl border border-[#DCE3DD] bg-white shadow-[0_2px_10px_rgba(16,61,43,0.06)] overflow-hidden">
          <div className="flex items-center justify-between border-b border-white/10 bg-[#103D2B] px-5 py-4 text-white">
            <div className="flex items-center gap-2.5 min-w-0">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-[#145C3A] text-[#C6A15B]">
                <ShoppingBag className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <h2 className="text-sm font-semibold leading-tight truncate">{t.currentBill}</h2>
                <p className="font-mono text-[11px] text-white/70 tabular-nums mt-0.5">
                  {totals.itemCount === 0
                    ? 'Ready for items'
                    : `${cartLines.length} ${cartLines.length === 1 ? 'line' : 'lines'} · ${totals.itemCount} ${totals.itemCount === 1 ? 'unit' : 'units'}`}
                </p>
              </div>
            </div>
            {cartLines.length > 0 && (
              <button
                type="button"
                onClick={clearCart}
                className="text-xs font-medium text-white/75 hover:text-red-200 transition-colors shrink-0"
              >
                {t.clearCart}
              </button>
            )}
          </div>

          {cartLines.length === 0 ? (
            <EmptyState
              icon={<ShoppingBag className="h-5 w-5" />}
              title={t.emptyCartTitle}
              description={t.emptyCartHint}
              className="py-10"
            />
          ) : (
            <div className="divide-y divide-[#E5EAE5] max-h-[340px] overflow-y-auto trexo-scroll px-5">
              {cartLines.map((line) => (
                <div
                  key={line.product.id}
                  className="py-3.5 flex flex-wrap sm:flex-nowrap items-center justify-between gap-2.5"
                >
                  <div className="min-w-[130px] flex-1">
                    <p className="text-sm font-medium text-[#172B22] truncate">
                      {getDisplayName(line.product)}
                    </p>
                    <p className="text-xs text-[#65766D] font-mono tabular-nums mt-0.5">
                      {formatINR(line.unitPricePaise)} × {line.qty}
                      {line.rescuesDeadStock && (
                        <span className="font-sans text-[#145C3A] font-medium">
                          {' · '}Cash rescue
                        </span>
                      )}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <div className="flex items-center rounded-lg border border-[#E5EAE5] bg-[#F3F5F2]">
                      <button
                        type="button"
                        onClick={() => updateCartQty(line.product.id, line.qty - 1)}
                        className="min-h-[34px] min-w-[32px] flex items-center justify-center text-[#172B22] hover:text-[#145C3A] transition-colors"
                        aria-label={`Decrease quantity for ${line.product.name}`}
                      >
                        <Minus className="h-3.5 w-3.5" />
                      </button>
                      <span className="w-7 text-center font-mono text-xs font-semibold text-[#172B22] tabular-nums">
                        {line.qty}
                      </span>
                      <button
                        type="button"
                        onClick={() => updateCartQty(line.product.id, line.qty + 1)}
                        disabled={line.qty >= line.product.stockQty}
                        className="min-h-[34px] min-w-[32px] flex items-center justify-center text-[#172B22] hover:text-[#145C3A] disabled:opacity-40 transition-colors"
                        aria-label={`Increase quantity for ${line.product.name}`}
                      >
                        <Plus className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <span className="w-16 text-right font-mono text-sm font-semibold text-[#103D2B] tabular-nums">
                      {formatINR(line.lineTotalPaise)}
                    </span>
                    <button
                      type="button"
                      onClick={() => removeFromCart(line.product.id)}
                      className="p-1.5 text-[#718078] hover:text-red-700 transition-colors"
                      aria-label={`Remove ${line.product.name}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Warm Cream Totals & Payment Checkout Area */}
          <div className="border-t border-[#E4DCC6] bg-[#FAF7EF] p-5 space-y-4">
            <div className="space-y-1.5 text-sm">
              <div className="flex justify-between text-[#52635B]">
                <span>Subtotal</span>
                <span className="font-mono tabular-nums">{formatINR(totals.subtotalPaise)}</span>
              </div>
              {totals.discountSavedPaise > 0 && (
                <div className="flex justify-between text-[#145C3A] font-medium">
                  <span>Counter Discount Savings</span>
                  <span className="font-mono tabular-nums">
                    -{formatINR(totals.discountSavedPaise)}
                  </span>
                </div>
              )}
              <div className="flex items-baseline justify-between pt-3 border-t border-[#E4DCC6]">
                <span className="text-sm font-bold text-[#103D2B]">Total Payable</span>
                <span className="font-mono text-2xl font-bold tracking-tight text-[#103D2B] tabular-nums">
                  {formatINR(totals.totalPaise)}
                </span>
              </div>
            </div>

            {/* Payment Method */}
            <PaymentMethodSelector
              value={paymentMethod}
              onChange={setPaymentMethod}
              options={['cash', 'upi', 'udhaar'] as const}
              label="Payment Mode"
            />

            {paymentMethod === 'upi' && (
              <div className="rounded-lg border border-[#E2DAC8] bg-white px-3.5 py-2.5 flex items-center justify-between gap-2 text-xs">
                <div className="min-w-0">
                  <p className="text-[11px] text-[#65766D]">Store UPI ID</p>
                  {isValidUpiId(upiConfig.upiId) ? (
                    <p className="font-mono font-semibold text-[#103D2B] truncate">
                      {upiConfig.upiId}
                    </p>
                  ) : (
                    <p className="font-medium text-amber-800 truncate">
                      Not configured yet · Enter on next step
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => setUpiSettingsOpen(true)}
                  className="rounded-md border border-[#D8CEB6] bg-[#FAF7EF] px-2.5 py-1.5 text-[11px] font-semibold text-[#145C3A] hover:border-[#145C3A] transition-colors whitespace-nowrap shrink-0"
                >
                  {isValidUpiId(upiConfig.upiId) ? 'Edit UPI' : 'Set UPI ID'}
                </button>
              </div>
            )}

            {paymentMethod === 'udhaar' && (
              <div className="space-y-1.5">
                <label
                  htmlFor="udhaar-customer-select"
                  className="block text-xs font-semibold text-[#172B22]"
                >
                  Customer Account
                </label>
                {customers.length === 0 ? (
                  <div className="rounded-lg border border-[#E2DAC8] bg-white px-3.5 py-3 flex items-center justify-between gap-2 text-xs">
                    <span className="text-[#52635B]">No Udhaar accounts created yet.</span>
                    <button
                      type="button"
                      onClick={() => navigate('/customers')}
                      className="font-semibold text-[#145C3A] hover:text-[#103D2B] whitespace-nowrap shrink-0"
                    >
                      Add Account
                    </button>
                  </div>
                ) : (
                  <select
                    id="udhaar-customer-select"
                    value={selectedCustomerId}
                    onChange={(e) => setSelectedCustomerId(e.target.value)}
                    className="w-full min-h-[42px] rounded-lg border border-[#D4DDD6] bg-white px-3 py-2 text-sm text-[#172B22] focus:border-[#145C3A] focus:outline-none"
                  >
                    <option value="">Choose Udhaar customer...</option>
                    {customers.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} (Due: {formatINR(c.duePaise)})
                      </option>
                    ))}
                  </select>
                )}
              </div>
            )}

            <button
              type="button"
              disabled={cartLines.length === 0 || submitting}
              onClick={handleCompleteSale}
              className="min-h-[48px] w-full inline-flex items-center justify-center gap-2 rounded-lg bg-[#145C3A] px-4 py-3 text-sm font-semibold text-white hover:bg-[#103D2B] disabled:bg-[#D4DDD6] disabled:text-[#718078] transition-colors whitespace-nowrap shadow-[0_1px_2px_rgba(16,61,43,0.16)]"
            >
              {paymentMethod === 'upi' && <QrCode className="h-4 w-4 shrink-0" />}
              <span>
                {submitting
                  ? 'Completing...'
                  : paymentMethod === 'upi'
                    ? `Show UPI QR · ${formatINR(totals.totalPaise)}`
                    : `${t.completeBill} · ${formatINR(totals.totalPaise)}`}
              </span>
            </button>
          </div>
        </aside>
      </div>

      <UpiPaymentModal
        open={upiModalOpen}
        title="Collect Counter Bill Payment"
        subtitle={`${cartLines.length} ${cartLines.length === 1 ? 'item' : 'items'} · Select UPI or Cash and confirm manually`}
        amountPaise={totals.totalPaise}
        initialPaymentMethod="upi"
        allowedMethods={['upi', 'cash'] as const}
        referencePrefix="BILL"
        transactionNote={`Counter Bill (${cartLines.length} items)`}
        summaryContent={
          <div className="rounded-xl border border-[#E5EAE5] bg-white overflow-hidden">
            <div className="flex items-center justify-between border-b border-[#E5EAE5] px-4 py-2.5">
              <span className="text-xs font-semibold text-[#172B22]">Bill Summary</span>
              <span className="font-mono text-xs text-[#65766D] tabular-nums">
                {totals.itemCount} {totals.itemCount === 1 ? 'unit' : 'units'}
              </span>
            </div>
            <div className="max-h-32 overflow-y-auto trexo-scroll divide-y divide-[#E5EAE5] px-4">
              {cartLines.map((line) => (
                <div
                  key={line.product.id}
                  className="flex items-center justify-between gap-2 py-2 text-xs"
                >
                  <span className="truncate text-[#172B22]">
                    {getDisplayName(line.product)}{' '}
                    <span className="font-mono text-[#718078]">× {line.qty}</span>
                  </span>
                  <span className="font-mono font-semibold text-[#172B22] tabular-nums shrink-0">
                    {formatINR(line.lineTotalPaise)}
                  </span>
                </div>
              ))}
            </div>
            <div className="border-t border-[#E5EAE5] bg-[#FAF7EF] px-4 py-2.5 space-y-1 text-xs">
              {totals.discountSavedPaise > 0 && (
                <div className="flex justify-between text-[#145C3A]">
                  <span>Counter Discount Savings (from {formatINR(totals.subtotalPaise)})</span>
                  <span className="font-mono tabular-nums">
                    -{formatINR(totals.discountSavedPaise)}
                  </span>
                </div>
              )}
              <div className="flex justify-between text-sm font-bold text-[#103D2B]">
                <span>Total Payable</span>
                <span className="font-mono tabular-nums">{formatINR(totals.totalPaise)}</span>
              </div>
            </div>
          </div>
        }
        onClose={() => setUpiModalOpen(false)}
        onConfirmPayment={handleConfirmModalPayment}
      />

      <UpiSettingsModal open={upiSettingsOpen} onClose={() => setUpiSettingsOpen(false)} />

      <ReceiptModal sale={lastCompletedSale} onClose={clearLastCompletedSale} />
    </div>
  );
}
