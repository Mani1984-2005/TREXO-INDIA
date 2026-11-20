import {
  AlertTriangle,
  ArrowUpRight,
  BookOpen,
  CheckCircle2,
  IndianRupee,
  MapPin,
  Phone,
  Plus,
  Printer,
  QrCode,
  Search,
  UserPlus,
  Users,
  Wallet,
  X,
} from 'lucide-react';
import { type FormEvent, useEffect, useMemo, useState } from 'react';
import { PaymentReceipt } from '../components/payments/PaymentReceipt';
import { PaymentStatusIndicator } from '../components/payments/PaymentStatusIndicator';
import { UdhaarRepaymentModal } from '../components/payments/UdhaarRepaymentModal';
import { UpiSettingsModal } from '../components/payments/UpiSettingsModal';
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
import type { Customer, CustomerPaymentEntry } from '../types/domain';
import { formatINR, rupeesToPaise } from '../utils/money';
import { isValidUpiId } from '../utils/upi';

type UdhaarFilter = 'all' | 'due' | 'settled';

export function CustomersPage() {
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<UdhaarFilter>('all');
  const [showAddModal, setShowAddModal] = useState(false);
  const [upiSettingsOpen, setUpiSettingsOpen] = useState(false);
  const [payingCustomer, setPayingCustomer] = useState<Customer | null>(null);
  const [initialPayMethod, setInitialPayMethod] = useState<'cash' | 'upi'>('upi');
  const [detailCustomerId, setDetailCustomerId] = useState<string | null>(null);
  const [activeReceipt, setActiveReceipt] = useState<CustomerPaymentEntry | null>(null);

  // New Customer Form
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [address, setAddress] = useState('');
  const [openingDueRupees, setOpeningDueRupees] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const customers = useLedgerStore((s) => s.customers);
  const customerPayments = useLedgerStore((s) => s.customerPayments);
  const upiConfig = useLedgerStore((s) => s.upiConfig);
  const createCustomer = useLedgerStore((s) => s.createCustomer);

  const totalDuePaise = useMemo(
    () => customers.reduce((sum, c) => sum + c.duePaise, 0),
    [customers]
  );

  const activeCreditCount = useMemo(
    () => customers.filter((c) => c.duePaise > 0).length,
    [customers]
  );

  const settledCount = customers.length - activeCreditCount;

  const totalCollectedPaise = useMemo(
    () =>
      customerPayments
        .filter((p) => p.status === 'confirmed')
        .reduce((sum, p) => sum + p.amountPaise, 0),
    [customerPayments]
  );

  const paymentsByCustomer = useMemo(() => {
    const map = new Map<string, CustomerPaymentEntry[]>();
    for (const entry of customerPayments) {
      const list = map.get(entry.customerId) ?? [];
      list.push(entry);
      map.set(entry.customerId, list);
    }
    return map;
  }, [customerPayments]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return customers.filter((c) => {
      if (statusFilter === 'due' && c.duePaise <= 0) return false;
      if (statusFilter === 'settled' && c.duePaise > 0) return false;
      if (!q) return true;
      return (
        c.name.toLowerCase().includes(q) ||
        c.phone.toLowerCase().includes(q) ||
        c.address.toLowerCase().includes(q)
      );
    });
  }, [customers, query, statusFilter]);

  const detailCustomer = useMemo(
    () => (detailCustomerId ? customers.find((c) => c.id === detailCustomerId) ?? null : null),
    [customers, detailCustomerId]
  );

  const detailHistory = useMemo(
    () => (detailCustomer ? paymentsByCustomer.get(detailCustomer.id) ?? [] : []),
    [detailCustomer, paymentsByCustomer]
  );

  const detailPaidTotalPaise = useMemo(
    () =>
      detailHistory
        .filter((e) => e.status === 'confirmed')
        .reduce((acc, e) => acc + e.amountPaise, 0),
    [detailHistory]
  );

  const handleCreateCustomer = async (e: FormEvent) => {
    e.preventDefault();
    const trimmedName = name.trim();
    const trimmedPhone = phone.trim();
    const openingDueNum = openingDueRupees.trim() ? Number(openingDueRupees) : 0;

    if (!trimmedName) {
      setFormError('Enter the customer full name.');
      return;
    }
    if (trimmedPhone.replace(/\D/g, '').length < 10) {
      setFormError('Enter a valid 10-digit mobile number.');
      return;
    }
    if (!Number.isFinite(openingDueNum) || openingDueNum < 0) {
      setFormError('Opening balance due cannot be negative.');
      return;
    }

    setFormError(null);
    await createCustomer({
      name: trimmedName,
      phone: trimmedPhone,
      address: address.trim(),
      openingDuePaise: rupeesToPaise(openingDueNum),
    });
    setName('');
    setPhone('');
    setAddress('');
    setOpeningDueRupees('');
    setShowAddModal(false);
  };

  const openPaymentModal = (customer: Customer, method: 'cash' | 'upi' = 'upi') => {
    setInitialPayMethod(method);
    setPayingCustomer(customer);
  };

  const hasValidUpi = isValidUpiId(upiConfig.upiId);

  useEffect(() => {
    if (!showAddModal && !detailCustomerId) return;
    // Let nested modals handle Escape first
    if (payingCustomer || upiSettingsOpen || activeReceipt) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        if (showAddModal) setShowAddModal(false);
        else if (detailCustomerId) setDetailCustomerId(null);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [showAddModal, detailCustomerId, payingCustomer, upiSettingsOpen, activeReceipt]);

  return (
    <div className="space-y-6 trexo-fade-in">
      <PageHeader
        title="Udhaar Ledger"
        description="Digital customer credit register with clear Indian rupee balances, UPI QR or Cash collections, and printable receipts."
        actions={
          <>
            <button
              type="button"
              onClick={() => setUpiSettingsOpen(true)}
              className="min-h-[42px] inline-flex items-center gap-1.5 rounded-lg border border-[#E5EAE5] bg-white px-3.5 py-2 text-xs font-semibold text-[#172B22] hover:bg-[#FAF7EF] hover:border-[#145C3A] transition-colors whitespace-nowrap"
            >
              <QrCode className="h-4 w-4 text-[#145C3A]" />
              <span>{hasValidUpi ? 'Store UPI ID' : 'Configure UPI'}</span>
            </button>
            <button
              type="button"
              onClick={() => setShowAddModal(true)}
              className="min-h-[42px] inline-flex items-center gap-1.5 rounded-lg bg-[#145C3A] px-4 py-2 text-xs sm:text-sm font-semibold text-white hover:bg-[#103D2B] transition-colors whitespace-nowrap shadow-[0_1px_2px_rgba(16,61,43,0.16)]"
            >
              <UserPlus className="h-4 w-4" />
              <span>Add Account</span>
            </button>
          </>
        }
      />

      {/* 4-Column Udhaar Summary Bar */}
      <KpiStrip columns={4} ariaLabel="Udhaar ledger summary" className="no-print">
        <KpiCell
          label="Total Udhaar Receivable"
          value={formatINR(totalDuePaise)}
          icon={<BookOpen className="h-3.5 w-3.5" />}
          caption="Outstanding credit across local accounts"
          tone={totalDuePaise > 0 ? 'crimson' : 'emerald'}
        />
        <KpiCell
          label="Accounts with Balance Due"
          value={String(activeCreditCount)}
          icon={<Users className="h-3.5 w-3.5" />}
          caption={`${settledCount} settled · ${customers.length} total`}
          tone={activeCreditCount > 0 ? 'amber' : 'emerald'}
        />
        <KpiCell
          label="Repayments Collected"
          value={formatINR(totalCollectedPaise)}
          icon={<Wallet className="h-3.5 w-3.5" />}
          caption={`${customerPayments.filter((p) => p.status === 'confirmed').length} confirmed receipts`}
          tone="emerald"
        />
        <div className="p-5 flex flex-col justify-between gap-3 bg-[#FAF7EF]">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-medium text-[#52635B]">Store UPI Collection ID</p>
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white border border-[#E4DCC6] text-[#145C3A]">
              <QrCode className="h-3.5 w-3.5" />
            </span>
          </div>
          <p className="font-mono text-sm font-bold text-[#103D2B] truncate">
            {hasValidUpi ? upiConfig.upiId : 'Not configured yet'}
          </p>
          <button
            type="button"
            onClick={() => setUpiSettingsOpen(true)}
            className="self-start inline-flex items-center gap-1 text-xs font-semibold text-[#145C3A] hover:text-[#103D2B] transition-colors"
          >
            <span>{hasValidUpi ? 'Update UPI ID' : 'Set Store UPI ID'}</span>
            <ArrowUpRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </KpiStrip>

      {/* Customer Ledger Table (lg+) & Responsive Card Grid (< lg) */}
      <SectionCard className="no-print">
        <div className="border-b border-[#E5EAE5] p-4 flex flex-col lg:flex-row lg:items-center justify-between gap-3.5">
          <SegmentedTabs
            value={statusFilter}
            onChange={setStatusFilter}
            ariaLabel="Filter Udhaar accounts"
            options={[
              { id: 'all', label: `All Accounts (${customers.length})` },
              { id: 'due', label: `Balance Due (${activeCreditCount})` },
              { id: 'settled', label: `Settled (${settledCount})` },
            ]}
          />
          <div className="relative w-full lg:w-72">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#718078]" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search name, phone, or locality…"
              className="w-full min-h-[40px] rounded-lg border border-[#D4DDD6] bg-white py-2 pl-9 pr-8 text-sm text-[#172B22] placeholder:text-[#718078] focus:border-[#145C3A] focus:outline-none"
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-[#718078] hover:text-[#172B22]"
                aria-label="Clear search"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>

        {customers.length === 0 ? (
          <EmptyState
            icon={<BookOpen className="h-5 w-5" />}
            title="No Udhaar accounts yet"
            description="Create your first customer credit account to track balances and collect UPI or Cash repayments."
            action={
              <button
                type="button"
                onClick={() => setShowAddModal(true)}
                className="min-h-[40px] inline-flex items-center gap-1.5 rounded-lg bg-[#145C3A] px-4 py-2 text-xs font-semibold text-white hover:bg-[#103D2B]"
              >
                <UserPlus className="h-4 w-4" />
                <span>Add First Account</span>
              </button>
            }
          />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<Search className="h-5 w-5" />}
            title="No customer accounts matched"
            description="Try clearing your search or switching the account status filter."
            action={
              <button
                type="button"
                onClick={() => {
                  setQuery('');
                  setStatusFilter('all');
                }}
                className="min-h-[38px] rounded-lg border border-[#E5EAE5] bg-white px-4 py-2 text-xs font-semibold text-[#172B22] hover:bg-[#FAF7EF]"
              >
                Show All Accounts
              </button>
            }
          />
        ) : (
          <>
            {/* Desktop Table (lg+ eliminates cramped inline buttons on 768px tablet) */}
            <div className="hidden lg:block overflow-x-auto trexo-scroll">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-[#E5EAE5] bg-[#FAF7EF] text-xs font-semibold text-[#52635B]">
                    <th className="px-5 py-3">Customer Account</th>
                    <th className="px-4 py-3">Phone &amp; Locality</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Outstanding Balance</th>
                    <th className="px-5 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5EAE5]">
                  {filtered.map((customer) => {
                    const history = paymentsByCustomer.get(customer.id) ?? [];
                    const isSelected = detailCustomerId === customer.id;

                    return (
                      <tr
                        key={customer.id}
                        className={`transition-colors ${
                          isSelected ? 'bg-[#FAF7EF]' : 'hover:bg-[#FAF7EF]/50'
                        }`}
                      >
                        <td className="px-5 py-3.5">
                          <button
                            type="button"
                            onClick={() => setDetailCustomerId(customer.id)}
                            className="text-left group"
                          >
                            <p className="font-semibold text-[#172B22] group-hover:text-[#145C3A] transition-colors">
                              {customer.name}
                            </p>
                            <p className="text-[11px] text-[#65766D] mt-0.5">
                              Last activity{' '}
                              {new Date(customer.lastTransactionAt).toLocaleDateString('en-IN', {
                                day: '2-digit',
                                month: 'short',
                                year: 'numeric',
                              })}{' '}
                              · {history.length} {history.length === 1 ? 'receipt' : 'receipts'}
                            </p>
                          </button>
                        </td>
                        <td className="px-4 py-3.5 text-xs text-[#52635B]">
                          <span className="font-mono text-[#172B22]">{customer.phone}</span>
                          {customer.address ? ` · ${customer.address}` : ''}
                        </td>
                        <td className="px-4 py-3.5 whitespace-nowrap">
                          {customer.duePaise > 0 ? (
                            <StatusText
                              tone="amber"
                              label="Balance Due"
                              icon={<AlertTriangle className="h-3.5 w-3.5" />}
                            />
                          ) : (
                            <StatusText
                              tone="emerald"
                              label="Settled"
                              icon={<CheckCircle2 className="h-3.5 w-3.5" />}
                            />
                          )}
                        </td>
                        <td className="px-4 py-3.5 text-right font-mono text-base font-bold tabular-nums whitespace-nowrap">
                          {customer.duePaise > 0 ? (
                            <span className="text-[#103D2B]">{formatINR(customer.duePaise)}</span>
                          ) : (
                            <span className="text-[#145C3A]">₹0</span>
                          )}
                        </td>
                        <td className="px-5 py-3.5 text-right whitespace-nowrap">
                          <div className="inline-flex items-center justify-end gap-1.5">
                            <button
                              type="button"
                              onClick={() => setDetailCustomerId(customer.id)}
                              className="min-h-[36px] rounded-lg border border-[#E5EAE5] bg-white px-2.5 py-1.5 text-xs font-semibold text-[#172B22] hover:bg-[#FAF7EF] hover:border-[#145C3A] transition-colors whitespace-nowrap"
                            >
                              Ledger
                            </button>
                            {customer.duePaise > 0 && (
                              <>
                                <button
                                  type="button"
                                  onClick={() => openPaymentModal(customer, 'upi')}
                                  className="min-h-[36px] inline-flex items-center gap-1.5 rounded-lg bg-[#145C3A] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#103D2B] transition-colors whitespace-nowrap"
                                >
                                  <QrCode className="h-3.5 w-3.5" />
                                  <span>Collect UPI</span>
                                </button>
                                <button
                                  type="button"
                                  onClick={() => openPaymentModal(customer, 'cash')}
                                  className="min-h-[36px] inline-flex items-center gap-1 rounded-lg border border-[#D4DDD6] bg-white px-2.5 py-1.5 text-xs font-semibold text-[#172B22] hover:border-[#145C3A] hover:text-[#145C3A] transition-colors whitespace-nowrap"
                                  title="Record Cash Repayment"
                                >
                                  <IndianRupee className="h-3.5 w-3.5" />
                                  <span>Cash</span>
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile (1-col) & Tablet (2-col) Card Grid (< lg) */}
            <div className="lg:hidden grid grid-cols-1 md:grid-cols-2 gap-px bg-[#E5EAE5]">
              {filtered.map((customer) => {
                const history = paymentsByCustomer.get(customer.id) ?? [];
                return (
                  <div
                    key={customer.id}
                    className="bg-white p-4 flex flex-col justify-between gap-3.5"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <button
                        type="button"
                        onClick={() => setDetailCustomerId(customer.id)}
                        className="text-left min-w-0"
                      >
                        <p className="text-sm font-bold text-[#172B22] truncate">{customer.name}</p>
                        <p className="text-xs text-[#65766D] font-mono mt-0.5">{customer.phone}</p>
                        <p className="text-xs text-[#65766D] truncate mt-0.5">
                          {customer.address ? `${customer.address} · ` : ''}
                          {history.length} {history.length === 1 ? 'receipt' : 'receipts'}
                        </p>
                      </button>
                      <div className="text-right shrink-0">
                        <p
                          className={`font-mono text-base font-bold tabular-nums ${
                            customer.duePaise > 0 ? 'text-[#103D2B]' : 'text-[#145C3A]'
                          }`}
                        >
                          {formatINR(customer.duePaise)}
                        </p>
                        <div className="mt-0.5 flex justify-end">
                          {customer.duePaise > 0 ? (
                            <StatusText tone="amber" label="Due" />
                          ) : (
                            <StatusText tone="emerald" label="Settled" />
                          )}
                        </div>
                      </div>
                    </div>

                    <div
                      className={`grid gap-2 ${
                        customer.duePaise > 0 ? 'grid-cols-3' : 'grid-cols-1'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => setDetailCustomerId(customer.id)}
                        className="min-h-[40px] rounded-lg border border-[#E4DCC6] bg-[#FAF7EF] px-2.5 py-2 text-xs font-semibold text-[#103D2B] hover:border-[#145C3A] transition-colors whitespace-nowrap"
                      >
                        {customer.duePaise > 0 ? 'Ledger' : 'View Ledger'}
                      </button>
                      {customer.duePaise > 0 && (
                        <>
                          <button
                            type="button"
                            onClick={() => openPaymentModal(customer, 'upi')}
                            className="min-h-[40px] inline-flex items-center justify-center gap-1 rounded-lg bg-[#145C3A] px-2.5 py-2 text-xs font-semibold text-white hover:bg-[#103D2B] transition-colors whitespace-nowrap"
                          >
                            <QrCode className="h-3.5 w-3.5 shrink-0" />
                            <span>UPI</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => openPaymentModal(customer, 'cash')}
                            className="min-h-[40px] inline-flex items-center justify-center gap-1 rounded-lg border border-[#D4DDD6] bg-white px-2.5 py-2 text-xs font-semibold text-[#172B22] hover:border-[#145C3A] transition-colors whitespace-nowrap"
                          >
                            <IndianRupee className="h-3.5 w-3.5 shrink-0 text-[#145C3A]" />
                            <span>Cash</span>
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </SectionCard>

      {/* Customer Detail Slide-Over Drawer */}
      {detailCustomer && (
        <div
          className="no-print fixed inset-0 z-50 flex justify-end bg-[#103D2B]/45 backdrop-blur-[1px]"
          role="dialog"
          aria-modal="true"
          aria-label={`${detailCustomer.name} Udhaar account details`}
          onClick={() => setDetailCustomerId(null)}
        >
          <div
            className="trexo-drawer-in relative flex h-full w-full max-w-md flex-col bg-white shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Deep-Forest Drawer Header */}
            <div className="flex items-start justify-between gap-3 bg-[#103D2B] px-5 py-5 text-white shrink-0">
              <div className="min-w-0">
                <p className="text-[11px] font-medium text-[#C6A15B]">Udhaar Account Ledger</p>
                <h2 className="mt-1 text-lg font-bold truncate">{detailCustomer.name}</h2>
                <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-white/75">
                  <span className="inline-flex items-center gap-1 font-mono">
                    <Phone className="h-3 w-3 text-[#C6A15B]" />
                    {detailCustomer.phone}
                  </span>
                  {detailCustomer.address && (
                    <span className="inline-flex items-center gap-1 truncate">
                      <MapPin className="h-3 w-3 text-[#C6A15B]" />
                      {detailCustomer.address}
                    </span>
                  )}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setDetailCustomerId(null)}
                className="rounded-lg p-1.5 text-white/75 hover:bg-white/10 hover:text-white transition-colors shrink-0"
                aria-label="Close customer details"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Balance & Quick Collect Area */}
            <div className="border-b border-[#E4DCC6] bg-[#FAF7EF] p-5 space-y-4 shrink-0">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-[#E4DCC6] bg-white p-3.5">
                  <p className="text-[11px] font-medium text-[#65766D]">Outstanding Balance</p>
                  <p
                    className={`mt-1 font-mono text-xl font-bold tabular-nums ${
                      detailCustomer.duePaise > 0 ? 'text-red-700' : 'text-[#145C3A]'
                    }`}
                  >
                    {formatINR(detailCustomer.duePaise)}
                  </p>
                </div>
                <div className="rounded-lg border border-[#E4DCC6] bg-white p-3.5">
                  <p className="text-[11px] font-medium text-[#65766D]">Total Repaid</p>
                  <p className="mt-1 font-mono text-xl font-bold text-[#145C3A] tabular-nums">
                    {formatINR(detailPaidTotalPaise)}
                  </p>
                </div>
              </div>

              {detailCustomer.duePaise > 0 ? (
                <div className="grid grid-cols-2 gap-2.5">
                  <button
                    type="button"
                    onClick={() => openPaymentModal(detailCustomer, 'upi')}
                    className="min-h-[42px] inline-flex items-center justify-center gap-1.5 rounded-lg bg-[#145C3A] px-3 py-2 text-xs font-semibold text-white hover:bg-[#103D2B] transition-colors whitespace-nowrap"
                  >
                    <QrCode className="h-4 w-4" />
                    <span>Collect via UPI</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => openPaymentModal(detailCustomer, 'cash')}
                    className="min-h-[42px] inline-flex items-center justify-center gap-1.5 rounded-lg border border-[#D4DDD6] bg-white px-3 py-2 text-xs font-semibold text-[#172B22] hover:border-[#145C3A] transition-colors whitespace-nowrap"
                  >
                    <IndianRupee className="h-4 w-4 text-[#145C3A]" />
                    <span>Record Cash</span>
                  </button>
                </div>
              ) : (
                <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-xs font-semibold text-[#145C3A] text-center">
                  Account settled · ₹0 balance due
                </p>
              )}
            </div>

            {/* Payment History List */}
            <div className="flex-1 overflow-y-auto trexo-scroll p-5 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-[#52635B]">
                  Repayment History ({detailHistory.length})
                </h3>
                <span className="text-[11px] text-[#718078]">Saved locally</span>
              </div>

              {detailHistory.length === 0 ? (
                <div className="rounded-xl border border-[#E5EAE5] bg-[#F3F5F2]/60 p-6 text-center">
                  <p className="text-sm font-medium text-[#172B22]">No repayments recorded yet</p>
                  <p className="mt-1 text-xs text-[#65766D] leading-relaxed">
                    UPI and Cash repayments for {detailCustomer.name} will appear here with
                    printable receipts.
                  </p>
                </div>
              ) : (
                <div className="space-y-2.5">
                  {detailHistory.map((entry) => (
                    <div
                      key={entry.id}
                      className="rounded-xl border border-[#E5EAE5] bg-white p-3.5 space-y-2"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="font-mono text-base font-bold text-[#103D2B] tabular-nums">
                            {formatINR(entry.amountPaise)}{' '}
                            <span className="font-sans text-xs font-semibold uppercase text-[#65766D]">
                              · {entry.paymentMethod}
                            </span>
                          </p>
                          <p className="text-[11px] text-[#65766D]">
                            {new Date(entry.createdAt).toLocaleString('en-IN', {
                              day: '2-digit',
                              month: 'short',
                              year: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </p>
                        </div>
                        <PaymentStatusIndicator
                          status={entry.status}
                          isDemo={entry.isDemo}
                          compact
                        />
                      </div>

                      <p className="font-mono text-[11px] text-[#52635B] break-all">
                        Ref: {entry.transactionRef}
                        {entry.utrNumber ? ` · UTR: ${entry.utrNumber}` : ''}
                      </p>

                      <div className="flex items-center justify-between pt-2 border-t border-[#E5EAE5] text-xs">
                        <span className="font-mono text-[#65766D] tabular-nums">
                          Balance after: {formatINR(entry.remainingDuePaise)}
                        </span>
                        {entry.status === 'confirmed' && (
                          <button
                            type="button"
                            onClick={() => setActiveReceipt(entry)}
                            className="inline-flex items-center gap-1 rounded-md border border-[#D8CEB6] bg-[#FAF7EF] px-2.5 py-1 text-[11px] font-semibold text-[#145C3A] hover:border-[#145C3A] transition-colors"
                          >
                            <Printer className="h-3 w-3" />
                            <span>Receipt</span>
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Add Customer Modal */}
      {showAddModal && (
        <div
          className="no-print fixed inset-0 z-50 flex items-center justify-center bg-[#103D2B]/55 backdrop-blur-[1px] p-3 sm:p-4"
          role="dialog"
          aria-modal="true"
          aria-label="Add Udhaar Customer"
          onClick={() => {
            setFormError(null);
            setShowAddModal(false);
          }}
        >
          <div
            className="trexo-modal-in flex max-h-[90vh] w-full max-w-md flex-col rounded-xl border border-[#D8CEB6] bg-white shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-white/10 bg-[#103D2B] px-5 py-4 text-white shrink-0">
              <div>
                <h2 className="text-base font-semibold">New Udhaar Account</h2>
                <p className="text-[11px] text-white/70 mt-0.5">
                  Create a local customer credit profile
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setFormError(null);
                  setShowAddModal(false);
                }}
                className="rounded-lg p-1.5 text-white/75 hover:bg-white/10 hover:text-white transition-colors"
                aria-label="Close modal"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <form
              onSubmit={handleCreateCustomer}
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
                <div>
                  <label className="block text-xs font-semibold text-[#172B22] mb-1">Full Name</label>
                  <input
                    required
                    type="text"
                    value={name}
                    onChange={(e) => {
                      setName(e.target.value);
                      if (formError) setFormError(null);
                    }}
                    placeholder="e.g., Basavaraj Patil"
                    className="w-full min-h-[40px] rounded-lg border border-[#D4DDD6] px-3 py-2 text-sm text-[#172B22] focus:border-[#145C3A] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#172B22] mb-1">
                    Mobile Number
                  </label>
                  <input
                    required
                    type="text"
                    value={phone}
                    onChange={(e) => {
                      setPhone(e.target.value);
                      if (formError) setFormError(null);
                    }}
                    placeholder="+91 98450 00000"
                    className="w-full min-h-[40px] rounded-lg border border-[#D4DDD6] px-3 py-2 text-sm font-mono text-[#172B22] focus:border-[#145C3A] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#172B22] mb-1">
                    Locality / Address
                  </label>
                  <input
                    type="text"
                    value={address}
                    onChange={(e) => setAddress(e.target.value)}
                    placeholder="e.g., Gokul Road 4th Cross"
                    className="w-full min-h-[40px] rounded-lg border border-[#D4DDD6] px-3 py-2 text-sm text-[#172B22] focus:border-[#145C3A] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#172B22] mb-1">
                    Opening Balance Due (₹, optional)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={openingDueRupees}
                    onChange={(e) => {
                      setOpeningDueRupees(e.target.value);
                      if (formError) setFormError(null);
                    }}
                    placeholder="0"
                    className="w-full min-h-[40px] rounded-lg border border-[#D4DDD6] px-3 py-2 text-sm font-mono text-[#172B22] focus:border-[#145C3A] focus:outline-none"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 px-5 py-3.5 border-t border-[#E4DCC6] bg-[#FAF7EF] shrink-0">
                <button
                  type="button"
                  onClick={() => {
                    setFormError(null);
                    setShowAddModal(false);
                  }}
                  className="min-h-[40px] rounded-lg border border-[#D4DDD6] bg-white px-4 py-2 text-sm font-medium text-[#172B22] hover:bg-[#F3F5F2] transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="min-h-[40px] inline-flex items-center gap-1.5 rounded-lg bg-[#145C3A] px-4 py-2 text-sm font-semibold text-white hover:bg-[#103D2B] transition-colors"
                >
                  <Plus className="h-4 w-4" />
                  <span>Save Account</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Udhaar Repayment Modal (UPI & Cash) */}
      <UdhaarRepaymentModal
        customer={payingCustomer}
        initialMethod={initialPayMethod}
        onClose={() => setPayingCustomer(null)}
        onPaymentConfirmed={(payment) => {
          setPayingCustomer(null);
          setDetailCustomerId(payment.customerId);
          setActiveReceipt(payment);
        }}
      />

      {/* Store UPI Settings Modal */}
      <UpiSettingsModal open={upiSettingsOpen} onClose={() => setUpiSettingsOpen(false)} />

      {/* Printable Payment Receipt */}
      <PaymentReceipt payment={activeReceipt} onClose={() => setActiveReceipt(null)} />
    </div>
  );
}
