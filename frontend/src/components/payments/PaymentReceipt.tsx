import { CheckCircle2, Printer, X } from 'lucide-react';
import { useEffect } from 'react';
import { STORE_INFO } from '../../config';
import type { CustomerPaymentEntry } from '../../types/domain';
import { formatINR } from '../../utils/money';
import { UPI_STATUS_LABELS } from '../../utils/upi';

interface PaymentReceiptProps {
  payment: CustomerPaymentEntry | null;
  onClose: () => void;
}

export function PaymentReceipt({ payment, onClose }: PaymentReceiptProps) {
  useEffect(() => {
    if (!payment) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [payment, onClose]);

  if (!payment) return null;

  const formattedDateTime = new Date(payment.createdAt).toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  const methodLabel = payment.paymentMethod === 'upi' ? 'UPI' : 'Cash';
  const statusLabel = UPI_STATUS_LABELS[payment.status];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#103D2B]/55 backdrop-blur-[1px] p-3 sm:p-4 print:static print:bg-white print:p-0"
      role="dialog"
      aria-modal="true"
      aria-label={`Payment Receipt ${payment.transactionRef}`}
      onClick={onClose}
    >
      <div
        className="trexo-modal-in print-surface w-full max-w-md max-h-[90vh] flex flex-col rounded-xl border border-[#D8CEB6] bg-white shadow-2xl overflow-hidden print:max-h-none"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Chrome */}
        <div className="no-print flex items-center justify-between border-b border-[#E5DEC9] bg-[#FAF7EF] px-5 py-3.5">
          <div className="flex items-center gap-2 min-w-0">
            <CheckCircle2 className="h-4 w-4 text-[#145C3A] shrink-0" />
            <h2 className="text-sm font-semibold text-[#103D2B] truncate">
              Udhaar Payment Receipt
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-500 hover:bg-white hover:text-slate-800"
            aria-label="Close payment receipt"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Printable Receipt Body */}
        <div className="p-5 sm:p-6 text-[#172B22] flex-1 overflow-y-auto trexo-scroll print:overflow-visible">
          <div className="text-center border-b border-dashed border-slate-300 pb-4">
            <p className="text-[11px] font-bold tracking-[0.2em] text-[#145C3A]">TREXO</p>
            <h3 className="mt-1 text-base font-bold text-[#103D2B]">{STORE_INFO.shopName}</h3>
            <p className="text-xs text-[#5B6B62] mt-0.5">{STORE_INFO.location}</p>
            <p className="text-xs text-[#718078] mt-0.5">
              Ph: {STORE_INFO.phone} · GSTIN: {STORE_INFO.gstin}
            </p>
          </div>

          {/* Primary Amount Summary */}
          <div className="mt-5 rounded-xl border border-[#E5DEC9] bg-[#FAF7EF] px-4 py-4 text-center print:bg-white print:border-slate-300">
            <p className="text-xs font-medium text-[#5B6B62]">Udhaar Repayment Received</p>
            <p className="mt-1 font-mono text-2xl font-bold text-[#103D2B] tabular-nums">
              {formatINR(payment.amountPaise)}
            </p>
            <p className="mt-1 text-xs font-medium text-[#145C3A]">
              {statusLabel}
              {payment.isDemo ? ' · DEMO' : ''}
            </p>
          </div>

          {/* Structured Receipt Rows */}
          <dl className="mt-5 divide-y divide-slate-100 text-xs">
            <div className="flex items-center justify-between gap-4 py-2.5">
              <dt className="text-[#5B6B62]">Customer Reference</dt>
              <dd className="font-semibold text-[#172B22] text-right">{payment.customerName}</dd>
            </div>
            <div className="flex items-center justify-between gap-4 py-2.5">
              <dt className="text-[#5B6B62]">Payment Method</dt>
              <dd className="font-semibold text-[#172B22] text-right">{methodLabel}</dd>
            </div>
            <div className="flex items-center justify-between gap-4 py-2.5">
              <dt className="text-[#5B6B62]">
                {payment.paymentMethod === 'upi' ? 'UPI Transaction Ref' : 'Receipt Reference'}
              </dt>
              <dd className="font-mono font-medium text-[#172B22] text-right break-all">
                {payment.transactionRef}
              </dd>
            </div>
            {payment.utrNumber && (
              <div className="flex items-center justify-between gap-4 py-2.5">
                <dt className="text-[#5B6B62]">Bank UTR Reference</dt>
                <dd className="font-mono font-medium text-[#172B22] text-right">
                  {payment.utrNumber}
                </dd>
              </div>
            )}
            {payment.upiIdUsed && (
              <div className="flex items-center justify-between gap-4 py-2.5">
                <dt className="text-[#5B6B62]">Store UPI ID</dt>
                <dd className="font-mono text-[#172B22] text-right">{payment.upiIdUsed}</dd>
              </div>
            )}
            <div className="flex items-center justify-between gap-4 py-2.5">
              <dt className="text-[#5B6B62]">Date &amp; Time</dt>
              <dd className="font-mono text-[#172B22] text-right">{formattedDateTime}</dd>
            </div>
            <div className="flex items-center justify-between gap-4 py-2.5">
              <dt className="text-[#5B6B62]">Payment Status</dt>
              <dd className="font-semibold text-[#145C3A] text-right">
                {statusLabel}
                {payment.isDemo ? ' (Demo)' : ''}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-4 py-2.5">
              <dt className="text-[#5B6B62]">Previous Balance</dt>
              <dd className="font-mono tabular-nums text-[#5B6B62] text-right">
                {formatINR(payment.previousDuePaise)}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-4 py-2.5">
              <dt className="font-semibold text-[#172B22]">Remaining Udhaar Due</dt>
              <dd className="font-mono font-bold tabular-nums text-[#103D2B] text-right">
                {formatINR(payment.remainingDuePaise)}
              </dd>
            </div>
          </dl>

          {payment.isDemo && (
            <p className="mt-4 rounded-lg border border-[#E5DEC9] bg-[#FAF7EF] px-3 py-2 text-[11px] text-[#5B6B62] text-center">
              DEMO RECORD · Manually confirmed in frontend prototype. Real settlement verification
              must come from your bank or payment provider.
            </p>
          )}

          <p className="mt-5 text-center text-[11px] text-slate-400 border-t border-dashed border-slate-200 pt-3">
            Thank you for your payment · TREXO Store Ledger
          </p>
        </div>

        {/* Action Footer */}
        <div className="no-print flex items-center justify-end gap-2 border-t border-[#E5DEC9] bg-[#FAF7EF] px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="min-h-[42px] rounded-lg border border-[#D4DDD6] bg-white px-4 py-2 text-sm font-medium text-[#172B22] hover:bg-[#FAF7EF] whitespace-nowrap"
          >
            Done
          </button>
          <button
            type="button"
            onClick={() => window.print()}
            className="min-h-[42px] inline-flex items-center gap-2 rounded-lg bg-[#145C3A] px-4 py-2 text-sm font-semibold text-white hover:bg-[#103D2B] whitespace-nowrap"
          >
            <Printer className="h-4 w-4" />
            <span>Print Receipt</span>
          </button>
        </div>
      </div>
    </div>
  );
}
