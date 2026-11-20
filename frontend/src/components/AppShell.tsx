import {
  ArrowUpRight,
  BarChart3,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  Coins,
  Keyboard,
  LayoutDashboard,
  Loader2,
  LogOut,
  Menu,
  Package,
  PanelLeftClose,
  PanelLeftOpen,
  QrCode,
  Receipt,
  RefreshCw,
  Search,
  ShoppingCart,
  Store,
  WifiOff,
  X,
} from 'lucide-react';
import { type ComponentType, type ReactNode, useCallback, useEffect, useRef, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { STORE_INFO } from '../config';
import { useGlobalShortcuts } from '../hooks/useGlobalShortcuts';
import { useSyncState } from '../hooks/useSyncState';
import { TRANSLATIONS } from '../i18n/translations';
import { useLedgerStore } from '../store/useLedgerStore';
import type { LanguageCode } from '../types/domain';
import { isDeadStock, isNearExpiry, isStockoutFastMover } from '../utils/money';
import { dispatchFocusCounterSearch, getModifierLabel } from '../utils/shortcuts';
import { isValidUpiId } from '../utils/upi';
import { UpiSettingsModal } from './payments/UpiSettingsModal';
import { QuickSearchModal } from './QuickSearchModal';
import { ShortcutsHelpModal } from './ShortcutsHelpModal';

interface AppShellProps {
  children: ReactNode;
}

interface SidebarNavItem {
  to: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  count: number | null;
  tone: 'neutral' | 'gold' | 'crimson' | 'amber';
}

interface SidebarNavGroup {
  id: string;
  label: string;
  items: SidebarNavItem[];
}

export function AppShell({ children }: AppShellProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [quickSearchOpen, setQuickSearchOpen] = useState(false);
  const [shortcutsHelpOpen, setShortcutsHelpOpen] = useState(false);
  const [upiSettingsOpen, setUpiSettingsOpen] = useState(false);
  const accountMenuRef = useRef<HTMLDivElement>(null);
  const location = useLocation();
  const navigate = useNavigate();

  const language = useLedgerStore((s) => s.language);
  const setLanguage = useLedgerStore((s) => s.setLanguage);
  const logoutOwner = useLedgerStore((s) => s.logoutOwner);
  const products = useLedgerStore((s) => s.products);
  const supplierReturns = useLedgerStore((s) => s.supplierReturns);
  const customers = useLedgerStore((s) => s.customers);
  const cart = useLedgerStore((s) => s.cart);
  const clearCart = useLedgerStore((s) => s.clearCart);
  const clearLastCompletedSale = useLedgerStore((s) => s.clearLastCompletedSale);
  const upiConfig = useLedgerStore((s) => s.upiConfig);
  const pushToast = useLedgerStore((s) => s.pushToast);
  const toasts = useLedgerStore((s) => s.toasts);
  const dismissToast = useLedgerStore((s) => s.dismissToast);
  const syncState = useSyncState();

  const t = TRANSLATIONS[language];
  const modLabel = getModifierLabel();

  useEffect(() => {
    if (!accountMenuOpen) return;
    const onPointerDown = (e: MouseEvent) => {
      if (accountMenuRef.current && !accountMenuRef.current.contains(e.target as Node)) {
        setAccountMenuOpen(false);
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setAccountMenuOpen(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    window.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [accountMenuOpen]);

  const handleNewTransaction = useCallback(() => {
    clearLastCompletedSale();
    const hadItems = cart.length > 0;
    if (hadItems) {
      clearCart();
    }
    navigate('/counter');
    setMobileMenuOpen(false);
    pushToast(
      'New transaction ready',
      hadItems ? 'Previous cart cleared. Ready for next bill.' : 'Counter focused for new bill.',
      'emerald'
    );
    setTimeout(() => dispatchFocusCounterSearch(), 50);
  }, [cart.length, clearCart, clearLastCompletedSale, navigate, pushToast]);

  const handleDismissShellOverlays = useCallback(() => {
    if (upiSettingsOpen) {
      setUpiSettingsOpen(false);
      return true;
    }
    if (accountMenuOpen) {
      setAccountMenuOpen(false);
      return true;
    }
    if (mobileMenuOpen) {
      setMobileMenuOpen(false);
      return true;
    }
    return false;
  }, [upiSettingsOpen, accountMenuOpen, mobileMenuOpen]);

  useGlobalShortcuts({
    quickSearchOpen,
    setQuickSearchOpen,
    shortcutsHelpOpen,
    setShortcutsHelpOpen,
    onNewTransaction: handleNewTransaction,
    onDismissOverlays: handleDismissShellOverlays,
  });

  const savedTimeLabel = syncState.lastSavedAt
    ? new Date(syncState.lastSavedAt).toLocaleTimeString('en-IN', {
        hour: '2-digit',
        minute: '2-digit',
      })
    : null;

  const handleLogout = () => {
    setMobileMenuOpen(false);
    setAccountMenuOpen(false);
    logoutOwner();
    navigate('/', { replace: true });
  };

  const rescueCount = products.filter((p) => isDeadStock(p) || isNearExpiry(p)).length;
  const stockoutCount = products.filter((p) => isStockoutFastMover(p)).length;
  const activeUdhaarCount = customers.filter((c) => c.duePaise > 0).length;
  const hasValidUpi = isValidUpiId(upiConfig.upiId);
  const cartQty = cart.reduce((a, c) => a + c.qty, 0);

  const navGroups: SidebarNavGroup[] = [
    {
      id: 'overview',
      label: 'Overview',
      items: [
        {
          to: '/',
          label: t.navDashboard,
          icon: LayoutDashboard,
          count: null,
          tone: 'neutral',
        },
      ],
    },
    {
      id: 'operations',
      label: 'Operations',
      items: [
        {
          to: '/counter',
          label: t.navCounter,
          icon: ShoppingCart,
          count: cartQty > 0 ? cartQty : null,
          tone: 'gold',
        },
        {
          to: '/inventory',
          label: t.navInventory,
          icon: Package,
          count: products.length,
          tone: 'neutral',
        },
        {
          to: '/rescue',
          label: t.navRescue,
          icon: Coins,
          count: rescueCount + supplierReturns.length > 0 ? rescueCount : null,
          tone: 'crimson',
        },
        {
          to: '/restock',
          label: t.navRestock,
          icon: RefreshCw,
          count: stockoutCount > 0 ? stockoutCount : null,
          tone: 'amber',
        },
      ],
    },
    {
      id: 'finance',
      label: 'Finance',
      items: [
        {
          to: '/customers',
          label: t.navUdhaar,
          icon: BookOpen,
          count: activeUdhaarCount > 0 ? activeUdhaarCount : null,
          tone: 'neutral',
        },
        {
          to: '/reports',
          label: t.navReports,
          icon: BarChart3,
          count: null,
          tone: 'neutral',
        },
      ],
    },
  ];

  const routeTitles: Record<string, string> = {
    '/': t.navDashboard,
    '/counter': t.navCounter,
    '/inventory': t.navInventory,
    '/rescue': t.navRescue,
    '/restock': t.navRestock,
    '/customers': t.navUdhaar,
    '/reports': t.navReports,
  };
  const currentTitle = routeTitles[location.pathname] ?? t.navDashboard;
  const isOnCounter = location.pathname === '/counter';

  const languages: { code: LanguageCode; label: string }[] = [
    { code: 'en', label: 'EN' },
    { code: 'hi', label: 'हिंदी' },
    { code: 'kn', label: 'ಕನ್ನಡ' },
  ];

  const renderSidebar = (isMobileDrawer: boolean) => {
    const collapsed = !isMobileDrawer && sidebarCollapsed;

    return (
      <div className="flex h-full flex-col bg-[#103D2B] text-white select-none border-r border-[#0C3122]">
        {/* Brand Header */}
        <div
          className={`flex h-16 items-center border-b border-white/10 ${
            collapsed ? 'justify-center px-2' : 'justify-between px-4'
          }`}
        >
          <button
            type="button"
            onClick={() => {
              navigate('/');
              setMobileMenuOpen(false);
            }}
            className="flex items-center gap-2.5 text-left min-w-0 focus-visible:outline-none group"
            title="Trexo Dashboard"
          >
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#145C3A] border border-[#C6A15B]/55 text-[#FAF7EF] shadow-[inset_0_1px_0_rgba(255,255,255,0.12)] transition-transform duration-150 group-hover:scale-[1.03]">
              <svg
                viewBox="0 0 24 24"
                className="h-4.5 w-4.5"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M5 7h14" />
                <path d="M12 7v11" />
                <path d="M8.5 18h7" className="stroke-[#C6A15B]" />
              </svg>
            </span>
            {!collapsed && (
              <div className="min-w-0">
                <p className="text-[15px] font-bold tracking-[0.04em] text-white leading-tight whitespace-nowrap">
                  TREXO
                </p>
                <p className="text-[11px] text-[#C6A15B]/95 truncate max-w-[152px] mt-0.5">
                  {STORE_INFO.shopName}
                </p>
              </div>
            )}
          </button>

          {isMobileDrawer ? (
            <button
              type="button"
              onClick={() => setMobileMenuOpen(false)}
              className="rounded-lg p-1.5 text-white/70 hover:bg-white/10 hover:text-white transition-colors"
              aria-label="Close navigation"
            >
              <X className="h-5 w-5" />
            </button>
          ) : (
            !collapsed && (
              <button
                type="button"
                onClick={() => setSidebarCollapsed(true)}
                className="rounded-lg p-1.5 text-white/55 hover:bg-white/10 hover:text-white transition-colors"
                aria-label="Collapse sidebar"
                title="Collapse sidebar"
              >
                <PanelLeftClose className="h-4 w-4" />
              </button>
            )
          )}
        </div>

        {/* Expand button when collapsed */}
        {collapsed && (
          <div className="flex justify-center pt-3">
            <button
              type="button"
              onClick={() => setSidebarCollapsed(false)}
              className="rounded-lg p-2 text-white/65 hover:bg-white/10 hover:text-white transition-colors"
              aria-label="Expand sidebar"
              title="Expand sidebar"
            >
              <PanelLeftOpen className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Grouped Navigation */}
        <nav
          className="flex-1 px-2.5 py-4 overflow-y-auto trexo-scroll space-y-5"
          aria-label="Primary Navigation"
        >
          {navGroups.map((group) => (
            <div key={group.id} className="space-y-1">
              {!collapsed && (
                <p className="px-3 pb-1 text-[11px] font-medium text-white/45 tracking-tight">
                  {group.label}
                </p>
              )}
              {group.items.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === '/'}
                    onClick={() => setMobileMenuOpen(false)}
                    title={collapsed ? item.label : undefined}
                    className={({ isActive }) =>
                      `group flex items-center rounded-lg transition-all duration-150 whitespace-nowrap min-h-[40px] ${
                        collapsed ? 'justify-center px-2' : 'justify-between px-3'
                      } ${
                        isActive
                          ? 'bg-[#145C3A] text-white font-semibold shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]'
                          : 'text-white/72 hover:bg-white/7 hover:text-white font-medium'
                      }`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <span className="flex items-center gap-2.5 min-w-0">
                          <Icon
                            className={`h-4 w-4 shrink-0 transition-colors ${
                              isActive
                                ? 'text-[#C6A15B]'
                                : 'text-white/55 group-hover:text-white/90'
                            }`}
                          />
                          {!collapsed && <span className="text-[13px] truncate">{item.label}</span>}
                        </span>
                        {!collapsed && item.count !== null && (
                          <span
                            className={`font-mono text-[11px] tabular-nums ${
                              item.tone === 'crimson'
                                ? 'font-semibold text-red-200'
                                : item.tone === 'amber'
                                  ? 'font-semibold text-amber-200'
                                  : item.tone === 'gold'
                                    ? 'font-semibold text-[#C6A15B]'
                                    : isActive
                                      ? 'text-white/80'
                                      : 'text-white/45'
                            }`}
                          >
                            {item.count}
                          </span>
                        )}
                      </>
                    )}
                  </NavLink>
                );
              })}
            </div>
          ))}

          {/* Settings Group */}
          <div className="space-y-1 pt-1 border-t border-white/10">
            {!collapsed && (
              <p className="px-3 pt-3 pb-1 text-[11px] font-medium text-white/45 tracking-tight">
                Settings
              </p>
            )}
            <button
              type="button"
              onClick={() => {
                setMobileMenuOpen(false);
                setUpiSettingsOpen(true);
              }}
              title={hasValidUpi ? `Store UPI: ${upiConfig.upiId}` : 'Configure Store UPI ID'}
              className={`w-full group flex items-center rounded-lg transition-colors min-h-[40px] text-white/75 hover:bg-white/7 hover:text-white ${
                collapsed ? 'justify-center px-2' : 'justify-between gap-2 px-3'
              }`}
            >
              <span className="flex items-center gap-2.5 min-w-0">
                <QrCode className="h-4 w-4 shrink-0 text-[#C6A15B]" />
                {!collapsed && (
                  <span className="truncate text-[13px] font-medium">
                    {hasValidUpi ? 'Store UPI' : 'Set Store UPI'}
                  </span>
                )}
              </span>
              {!collapsed && (
                <span className="font-mono text-[10px] font-medium text-[#C6A15B]/90 truncate max-w-[82px]">
                  {hasValidUpi ? upiConfig.upiId.split('@')[0] : 'Setup'}
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => {
                setMobileMenuOpen(false);
                setShortcutsHelpOpen(true);
              }}
              title="Keyboard shortcuts"
              className={`w-full group flex items-center rounded-lg transition-colors min-h-[40px] text-white/70 hover:bg-white/7 hover:text-white ${
                collapsed ? 'justify-center px-2' : 'justify-between gap-2 px-3'
              }`}
            >
              <span className="flex items-center gap-2.5 min-w-0">
                <Keyboard className="h-4 w-4 shrink-0 text-white/55 group-hover:text-white/90" />
                {!collapsed && <span className="truncate text-[13px] font-medium">Shortcuts</span>}
              </span>
              {!collapsed && (
                <kbd className="font-mono text-[10px] text-white/45">{modLabel}+/</kbd>
              )}
            </button>
          </div>
        </nav>

        {/* Bottom Store Sync & Account Footer */}
        <div className="border-t border-white/10 p-3 space-y-2.5">
          {!collapsed && (
            <div
              className="flex items-center gap-2 px-2 py-1 text-[11px] text-white/70"
              role="status"
              aria-live="polite"
              title={savedTimeLabel ? `Last saved at ${savedTimeLabel}` : t.localSavedNote}
            >
              {syncState.mode === 'saving' ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-[#C6A15B]" />
                  <span className="truncate">{t.syncSaving}</span>
                </>
              ) : syncState.mode === 'offline' ? (
                <>
                  <WifiOff className="h-3.5 w-3.5 shrink-0 text-amber-300" />
                  <span className="truncate text-amber-200">{t.syncOffline}</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-300" />
                  <span className="truncate">
                    {t.syncSaved}
                    {savedTimeLabel ? ` · ${savedTimeLabel}` : ''}
                  </span>
                </>
              )}
            </div>
          )}

          {/* Mobile language switcher inside drawer for small viewports */}
          {isMobileDrawer && (
            <div
              className="grid grid-cols-3 gap-1 rounded-lg bg-white/10 p-1 sm:hidden"
              role="group"
              aria-label="Display language"
            >
              {languages.map((lang) => (
                <button
                  key={lang.code}
                  type="button"
                  onClick={() => setLanguage(lang.code)}
                  className={`rounded-md py-1.5 text-xs font-medium transition-colors whitespace-nowrap ${
                    language === lang.code
                      ? 'bg-[#FAF7EF] text-[#103D2B] font-semibold'
                      : 'text-white/75 hover:text-white'
                  }`}
                >
                  {lang.label}
                </button>
              ))}
            </div>
          )}

          <button
            type="button"
            onClick={handleLogout}
            title={t.signOut}
            className={`w-full inline-flex items-center rounded-lg border border-white/12 px-3 py-2 text-xs font-medium text-white/80 hover:bg-white/10 hover:text-white transition-colors whitespace-nowrap min-h-[38px] ${
              collapsed ? 'justify-center px-2' : 'justify-center gap-2'
            }`}
          >
            <LogOut className="h-3.5 w-3.5 shrink-0" />
            {!collapsed && <span>{t.signOut}</span>}
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-[#F3F5F2] text-[#172B22] flex">
      {/* Desktop Fixed Deep-Forest Sidebar */}
      <aside
        className={`no-print hidden lg:flex lg:flex-col lg:fixed lg:inset-y-0 lg:z-30 transition-[width] duration-200 ease-out ${
          sidebarCollapsed ? 'lg:w-[72px]' : 'lg:w-64'
        }`}
      >
        {renderSidebar(false)}
      </aside>

      {/* Mobile Navigation Drawer */}
      {mobileMenuOpen && (
        <div className="no-print fixed inset-0 z-50 flex lg:hidden">
          <div
            className="fixed inset-0 bg-[#103D2B]/45 backdrop-blur-[1px]"
            onClick={() => setMobileMenuOpen(false)}
            aria-hidden="true"
          />
          <div className="trexo-sidebar-in relative z-10 w-64 max-w-[84vw] shadow-2xl">
            {renderSidebar(true)}
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div
        className={`flex flex-1 flex-col min-w-0 transition-[padding] duration-200 ease-out ${
          sidebarCollapsed ? 'lg:pl-[72px]' : 'lg:pl-64'
        }`}
      >
        {/* Clean Single-Row Top Bar */}
        <header className="no-print sticky top-0 z-20 flex h-16 items-center justify-between gap-2 sm:gap-3 border-b border-[#E5EAE5] bg-white/95 backdrop-blur-sm px-3 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              className="rounded-lg p-2 text-[#172B22] hover:bg-[#F3F5F2] lg:hidden min-h-[40px] min-w-[40px] flex items-center justify-center shrink-0"
              aria-label="Open navigation"
            >
              <Menu className="h-5 w-5" />
            </button>

            <div className="flex items-center gap-2 text-sm min-w-0 whitespace-nowrap">
              <span className="font-medium text-[#718078] hidden md:inline">Trexo</span>
              <span className="text-[#CBD4CE] hidden md:inline" aria-hidden="true">
                /
              </span>
              <h1 className="text-[15px] sm:text-base font-bold tracking-[-0.015em] text-[#172B22] truncate">
                {currentTitle}
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-1.5 sm:gap-2.5 shrink-0">
            {/* Quick Search Trigger */}
            <button
              type="button"
              onClick={() => setQuickSearchOpen(true)}
              className="min-h-[38px] inline-flex items-center gap-2 rounded-lg border border-[#E5EAE5] bg-[#F3F5F2]/80 px-2.5 sm:px-3 py-1.5 text-xs text-[#65766D] hover:border-[#145C3A]/35 hover:bg-white hover:text-[#172B22] transition-colors whitespace-nowrap"
              aria-label="Quick search"
            >
              <Search className="h-3.5 w-3.5 shrink-0 text-[#145C3A]" />
              <span className="hidden md:inline">Search products, bills…</span>
              <kbd className="hidden sm:inline font-mono text-[10px] font-medium text-[#718078]">
                {modLabel}+K
              </kbd>
            </button>

            {/* Language Selector (EN / हिंदी / ಕನ್ನಡ) */}
            <div
              className="hidden sm:inline-flex items-center gap-0.5 rounded-lg border border-[#E5EAE5] bg-[#F3F5F2] p-0.5"
              role="group"
              aria-label="Display language"
            >
              {languages.map((lang) => (
                <button
                  key={lang.code}
                  type="button"
                  onClick={() => setLanguage(lang.code)}
                  className={`min-h-[32px] rounded-md px-2.5 py-1 text-xs font-medium transition-colors whitespace-nowrap ${
                    language === lang.code
                      ? 'bg-white text-[#103D2B] font-semibold shadow-[0_1px_2px_rgba(16,61,43,0.08)]'
                      : 'text-[#65766D] hover:text-[#172B22]'
                  }`}
                >
                  {lang.label}
                </button>
              ))}
            </div>

            {/* Store Account Dropdown */}
            <div className="relative" ref={accountMenuRef}>
              <button
                type="button"
                onClick={() => setAccountMenuOpen((o) => !o)}
                aria-expanded={accountMenuOpen}
                aria-haspopup="menu"
                aria-label="Store account menu"
                className="min-h-[38px] inline-flex items-center gap-1.5 rounded-lg border border-[#E5EAE5] bg-white px-2.5 py-1.5 text-xs font-medium text-[#172B22] hover:bg-[#FAF7EF] transition-colors whitespace-nowrap"
              >
                <Store className="h-3.5 w-3.5 text-[#145C3A] shrink-0" />
                <span className="hidden xl:inline max-w-[130px] truncate">Owner</span>
                <ChevronDown className="h-3.5 w-3.5 text-[#718078] shrink-0" />
              </button>

              {accountMenuOpen && (
                <div
                  role="menu"
                  className="trexo-fade-in absolute right-0 mt-2 w-64 rounded-xl border border-[#E5EAE5] bg-white shadow-xl overflow-hidden z-40"
                >
                  <div className="border-b border-[#E5EAE5] bg-[#FAF7EF] px-4 py-3">
                    <p className="text-xs font-bold text-[#103D2B] truncate">
                      {STORE_INFO.shopName}
                    </p>
                    <p className="text-[11px] text-[#65766D] truncate mt-0.5">
                      {STORE_INFO.location}
                    </p>
                  </div>
                  <div className="p-1.5 space-y-0.5 text-xs">
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => {
                        setAccountMenuOpen(false);
                        setUpiSettingsOpen(true);
                      }}
                      className="w-full flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-left font-medium text-[#172B22] hover:bg-[#F3F5F2] transition-colors"
                    >
                      <span className="flex items-center gap-2.5 min-w-0">
                        <QrCode className="h-3.5 w-3.5 text-[#145C3A] shrink-0" />
                        <span className="truncate">Store UPI Settings</span>
                      </span>
                      <span className="font-mono text-[10px] text-[#718078] shrink-0">
                        {hasValidUpi ? 'Active' : 'Setup'}
                      </span>
                    </button>
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => {
                        setAccountMenuOpen(false);
                        setShortcutsHelpOpen(true);
                      }}
                      className="w-full flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-left font-medium text-[#172B22] hover:bg-[#F3F5F2] transition-colors"
                    >
                      <span className="flex items-center gap-2.5">
                        <Keyboard className="h-3.5 w-3.5 text-[#145C3A] shrink-0" />
                        <span>Keyboard Shortcuts</span>
                      </span>
                      <kbd className="font-mono text-[10px] text-[#718078]">{modLabel}+/</kbd>
                    </button>
                    <div className="my-1 border-t border-[#E5EAE5]" />
                    <button
                      type="button"
                      role="menuitem"
                      onClick={handleLogout}
                      className="w-full flex items-center gap-2.5 rounded-lg px-3 py-2 text-left font-medium text-red-700 hover:bg-red-50 transition-colors"
                    >
                      <LogOut className="h-3.5 w-3.5" />
                      <span>{t.signOut}</span>
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Single Primary CTA */}
            {isOnCounter ? (
              <button
                type="button"
                onClick={() => navigate('/rescue')}
                className="min-h-[38px] inline-flex items-center gap-1.5 rounded-lg bg-[#145C3A] px-3 sm:px-3.5 py-2 text-xs sm:text-sm font-semibold text-white hover:bg-[#103D2B] transition-colors whitespace-nowrap shrink-0"
              >
                <span className="hidden sm:inline">{t.rescueAction}</span>
                <span className="sm:hidden">Rescue</span>
                <ArrowUpRight className="h-4 w-4 shrink-0" />
              </button>
            ) : (
              <button
                type="button"
                onClick={() => navigate('/counter')}
                className="min-h-[38px] inline-flex items-center gap-1.5 rounded-lg bg-[#145C3A] px-3 sm:px-3.5 py-2 text-xs sm:text-sm font-semibold text-white hover:bg-[#103D2B] transition-colors whitespace-nowrap shrink-0"
              >
                <Receipt className="h-4 w-4 shrink-0" />
                <span className="hidden sm:inline">Open Counter</span>
                <span className="sm:hidden">Counter</span>
              </button>
            )}
          </div>
        </header>

        {/* Page Content Container */}
        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8 max-w-[1440px] w-full mx-auto">
          {children}
        </main>
      </div>

      {/* Toast Stack */}
      {toasts.length > 0 && (
        <div
          className="no-print fixed bottom-5 right-5 z-50 flex flex-col gap-2 max-w-sm w-[calc(100vw-2.5rem)]"
          aria-live="polite"
        >
          {toasts.map((toast) => (
            <div
              key={toast.id}
              className="trexo-fade-in flex items-start justify-between gap-3 rounded-xl border border-[#E5EAE5] bg-white px-4 py-3 shadow-lg"
            >
              <div className="min-w-0">
                <p
                  className={`text-sm font-semibold ${
                    toast.tone === 'amber'
                      ? 'text-amber-800'
                      : toast.tone === 'emerald'
                        ? 'text-[#145C3A]'
                        : 'text-[#172B22]'
                  }`}
                >
                  {toast.title}
                </p>
                {toast.detail && (
                  <p className="mt-0.5 text-xs text-[#65766D] leading-relaxed">{toast.detail}</p>
                )}
              </div>
              <button
                type="button"
                onClick={() => dismissToast(toast.id)}
                className="rounded p-1 text-[#718078] hover:bg-[#F3F5F2] hover:text-[#172B22] shrink-0 transition-colors"
                aria-label="Dismiss notice"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      <QuickSearchModal
        open={quickSearchOpen}
        onClose={() => setQuickSearchOpen(false)}
        onNewTransaction={handleNewTransaction}
      />
      <ShortcutsHelpModal
        open={shortcutsHelpOpen}
        onClose={() => setShortcutsHelpOpen(false)}
      />
      <UpiSettingsModal
        open={upiSettingsOpen}
        onClose={() => setUpiSettingsOpen(false)}
      />
    </div>
  );
}
