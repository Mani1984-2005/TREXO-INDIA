import {
  ArrowRight,
  BarChart3,
  BookOpen,
  Coins,
  LayoutDashboard,
  Package,
  Plus,
  RefreshCw,
  Search,
  ShoppingCart,
  User,
  X,
} from 'lucide-react';
import { type KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLedgerStore } from '../store/useLedgerStore';
import type { Product } from '../types/domain';
import { formatINR, getEffectivePricePaise } from '../utils/money';
import { dispatchFocusCounterSearch } from '../utils/shortcuts';

interface QuickSearchModalProps {
  open: boolean;
  onClose: () => void;
  onNewTransaction: () => void;
}

type SearchResultItem =
  | {
      id: string;
      kind: 'product';
      title: string;
      subtitle: string;
      meta: string;
      outOfStock: boolean;
      product: Product;
    }
  | {
      id: string;
      kind: 'customer';
      title: string;
      subtitle: string;
      meta: string;
    }
  | {
      id: string;
      kind: 'action';
      title: string;
      subtitle: string;
      shortcutHint?: string;
      icon: 'dashboard' | 'counter' | 'inventory' | 'rescue' | 'restock' | 'udhaar' | 'reports' | 'new';
      onSelect: () => void;
    };

export function QuickSearchModal({ open, onClose, onNewTransaction }: QuickSearchModalProps) {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);

  const language = useLedgerStore((s) => s.language);
  const products = useLedgerStore((s) => s.products);
  const customers = useLedgerStore((s) => s.customers);
  const addToCart = useLedgerStore((s) => s.addToCart);

  useEffect(() => {
    if (open) {
      setQuery('');
      setActiveIndex(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const results = useMemo<SearchResultItem[]>(() => {
    const q = query.trim().toLowerCase();

    const navActions: SearchResultItem[] = [
      {
        id: 'act-new-bill',
        kind: 'action',
        title: 'Start New Transaction',
        subtitle: 'Clear current bill and focus Counter billing',
        shortcutHint: 'Ctrl+N',
        icon: 'new',
        onSelect: () => {
          onClose();
          onNewTransaction();
        },
      },
      {
        id: 'nav-dashboard',
        kind: 'action',
        title: 'Open Store Dashboard',
        subtitle: 'Daily sales overview, stock alerts, and cash position',
        shortcutHint: 'Alt+1',
        icon: 'dashboard',
        onSelect: () => {
          onClose();
          navigate('/');
        },
      },
      {
        id: 'nav-counter',
        kind: 'action',
        title: 'Open Counter POS',
        subtitle: 'Billing, UPI QR checkout, and receipt printing',
        shortcutHint: 'Alt+2',
        icon: 'counter',
        onSelect: () => {
          onClose();
          navigate('/counter');
          setTimeout(() => dispatchFocusCounterSearch(), 50);
        },
      },
      {
        id: 'nav-inventory',
        kind: 'action',
        title: 'Open Inventory Ledger',
        subtitle: 'Stock counts, dead stock, and near expiry',
        shortcutHint: 'Alt+3',
        icon: 'inventory',
        onSelect: () => {
          onClose();
          navigate('/inventory');
        },
      },
      {
        id: 'nav-rescue',
        kind: 'action',
        title: 'Open Rescue Stuck Cash',
        subtitle: 'Counter offers, cash flow history, and supplier return slips',
        shortcutHint: 'Alt+4',
        icon: 'rescue',
        onSelect: () => {
          onClose();
          navigate('/rescue');
        },
      },
      {
        id: 'nav-restock',
        kind: 'action',
        title: 'Open Restock Planner',
        subtitle: 'Demand forecasts and purchase orders',
        shortcutHint: 'Alt+5',
        icon: 'restock',
        onSelect: () => {
          onClose();
          navigate('/restock');
        },
      },
      {
        id: 'nav-udhaar',
        kind: 'action',
        title: 'Open Udhaar Ledger',
        subtitle: 'Customer credit balances and UPI/Cash repayments',
        shortcutHint: 'Alt+6',
        icon: 'udhaar',
        onSelect: () => {
          onClose();
          navigate('/customers');
        },
      },
      {
        id: 'nav-reports',
        kind: 'action',
        title: 'Open Sales Reports',
        subtitle: 'Revenue breakdown, CSV export, and receipt reprint',
        shortcutHint: 'Alt+7',
        icon: 'reports',
        onSelect: () => {
          onClose();
          navigate('/reports');
        },
      },
    ];

    const matchedProducts: SearchResultItem[] = products
      .filter((p) => {
        if (!q) return p.stockQty > 0;
        return (
          p.name.toLowerCase().includes(q) ||
          p.sku.toLowerCase().includes(q) ||
          p.category.toLowerCase().includes(q) ||
          (p.hindiName && p.hindiName.toLowerCase().includes(q)) ||
          (p.kannadaName && p.kannadaName.toLowerCase().includes(q))
        );
      })
      .slice(0, q ? 6 : 4)
      .map((p) => {
        const displayName =
          language === 'hi' && p.hindiName
            ? p.hindiName
            : language === 'kn' && p.kannadaName
              ? p.kannadaName
              : p.name;
        const effPrice = getEffectivePricePaise(p);
        return {
          id: `prod-${p.id}`,
          kind: 'product',
          title: displayName,
          subtitle: `${p.sku} · ${p.unit} · ${p.stockQty > 0 ? `${p.stockQty} in stock` : 'Out of stock'}`,
          meta: formatINR(effPrice),
          outOfStock: p.stockQty <= 0,
          product: p,
        };
      });

    const matchedCustomers: SearchResultItem[] = q
      ? customers
          .filter(
            (c) =>
              c.name.toLowerCase().includes(q) ||
              c.phone.toLowerCase().includes(q) ||
              c.address.toLowerCase().includes(q)
          )
          .slice(0, 3)
          .map((c) => ({
            id: `cust-${c.id}`,
            kind: 'customer',
            title: c.name,
            subtitle: `${c.phone} · ${c.address}`,
            meta: c.duePaise > 0 ? `Due ${formatINR(c.duePaise)}` : 'Settled',
          }))
      : [];

    const matchedActions = q
      ? navActions.filter(
          (a) =>
            a.title.toLowerCase().includes(q) || a.subtitle.toLowerCase().includes(q)
        )
      : navActions.slice(0, 5);

    return [...matchedProducts, ...matchedCustomers, ...matchedActions];
  }, [query, products, customers, language, navigate, onClose, onNewTransaction]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  if (!open) return null;

  const executeItem = (item: SearchResultItem) => {
    if (item.kind === 'product') {
      if (item.outOfStock) {
        onClose();
        navigate('/restock');
      } else {
        addToCart(item.product.id, 1);
        onClose();
        navigate('/counter');
      }
      return;
    }

    if (item.kind === 'customer') {
      onClose();
      navigate('/customers');
      return;
    }

    item.onSelect();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((prev) => (results.length > 0 ? (prev + 1) % results.length : 0));
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((prev) =>
        results.length > 0 ? (prev - 1 + results.length) % results.length : 0
      );
      return;
    }
    if (e.key === 'Enter' && results[activeIndex]) {
      e.preventDefault();
      executeItem(results[activeIndex]);
    }
  };

  const renderActionIcon = (icon: Extract<SearchResultItem, { kind: 'action' }>['icon']) => {
    switch (icon) {
      case 'new':
        return <Plus className="h-4 w-4 text-[#145C3A]" />;
      case 'dashboard':
        return <LayoutDashboard className="h-4 w-4 text-[#145C3A]" />;
      case 'counter':
        return <ShoppingCart className="h-4 w-4 text-[#718078]" />;
      case 'inventory':
        return <Package className="h-4 w-4 text-[#718078]" />;
      case 'rescue':
        return <Coins className="h-4 w-4 text-[#718078]" />;
      case 'restock':
        return <RefreshCw className="h-4 w-4 text-[#718078]" />;
      case 'udhaar':
        return <BookOpen className="h-4 w-4 text-[#718078]" />;
      case 'reports':
        return <BarChart3 className="h-4 w-4 text-[#718078]" />;
    }
  };

  return (
    <div
      className="no-print fixed inset-0 z-50 flex items-start justify-center bg-[#103D2B]/50 backdrop-blur-[1px] px-3 sm:px-4 pt-[10vh] sm:pt-[12vh]"
      role="dialog"
      aria-modal="true"
      aria-label="Quick Search"
      onClick={onClose}
    >
      <div
        className="trexo-modal-in w-full max-w-xl rounded-xl border border-[#D8CEB6] bg-white shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input Row */}
        <div className="flex items-center gap-3 border-b border-[#E5EAE5] px-4 py-3.5">
          <Search className="h-4 w-4 shrink-0 text-[#145C3A]" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search products to add to bill, customers, or pages…"
            aria-label="Quick search items, customers, and pages"
            className="w-full bg-transparent text-sm text-[#172B22] placeholder:text-[#718078] focus:outline-none"
          />
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-[#718078] hover:bg-[#F3F5F2] hover:text-[#172B22]"
            aria-label="Close quick search"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Results List */}
        <div className="max-h-[55vh] overflow-y-auto trexo-scroll divide-y divide-[#E5EAE5]">
          {results.length === 0 ? (
            <div className="px-5 py-10 text-center">
              <p className="text-sm font-medium text-[#172B22]">No matches found</p>
              <p className="mt-1 text-xs text-[#718078]">
                Try an item name, SKU, customer name, or page title.
              </p>
            </div>
          ) : (
            results.map((item, idx) => {
              const isSelected = idx === activeIndex;
              return (
                <button
                  key={item.id}
                  type="button"
                  onMouseEnter={() => setActiveIndex(idx)}
                  onClick={() => executeItem(item)}
                  className={`w-full flex items-center justify-between gap-3 px-4 py-3 text-left transition-colors ${
                    isSelected ? 'bg-[#FAF7EF]' : 'bg-white hover:bg-[#F3F5F2]/60'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[#E5EAE5] bg-[#FAF7EF]">
                      {item.kind === 'product' ? (
                        <Package className="h-4 w-4 text-[#145C3A]" />
                      ) : item.kind === 'customer' ? (
                        <User className="h-4 w-4 text-[#C6A15B]" />
                      ) : (
                        renderActionIcon(item.icon)
                      )}
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-[#172B22] truncate">{item.title}</p>
                      <p className="text-xs text-[#718078] truncate">{item.subtitle}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2.5 shrink-0">
                    {item.kind === 'product' && (
                      <>
                        <span className="font-mono text-sm font-semibold text-[#172B22] tabular-nums">
                          {item.meta}
                        </span>
                        <span
                          className={`text-xs font-semibold whitespace-nowrap ${
                            item.outOfStock ? 'text-amber-700' : 'text-[#145C3A]'
                          }`}
                        >
                          {item.outOfStock ? 'Restock' : '+ Bill'}
                        </span>
                      </>
                    )}
                    {item.kind === 'customer' && (
                      <span className="font-mono text-xs font-semibold text-[#103D2B] tabular-nums">
                        {item.meta}
                      </span>
                    )}
                    {item.kind === 'action' && (
                      <span className="inline-flex items-center gap-1.5 text-xs text-[#718078]">
                        {item.shortcutHint && (
                          <kbd className="font-mono text-[11px] text-[#718078]">
                            {item.shortcutHint}
                          </kbd>
                        )}
                        <ArrowRight className="h-3.5 w-3.5" />
                      </span>
                    )}
                  </div>
                </button>
              );
            })
          )}
        </div>

        {/* Footer hints */}
        <div className="flex items-center justify-between gap-4 border-t border-[#E5EAE5] bg-[#FAF7EF] px-4 py-2.5 text-[11px] text-[#718078]">
          <span>
            <kbd className="font-mono font-semibold text-[#172B22]">↑↓</kbd> Navigate ·{' '}
            <kbd className="font-mono font-semibold text-[#172B22]">Enter</kbd> Select / Add to Bill
          </span>
          <span>
            <kbd className="font-mono font-semibold text-[#172B22]">Esc</kbd> Close
          </span>
        </div>
      </div>
    </div>
  );
}
