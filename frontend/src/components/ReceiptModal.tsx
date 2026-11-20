import { Printer, X } from 'lucide-react';
import { useEffect } from 'react';
import { STORE_INFO } from '../config';
import type { Sale } from '../types/domain';
import { formatINR } from '../utils/money';
import { UPI_STATUS_LABELS } from '../utils/upi';

interface ReceiptModalProps {
  sale: Sale | null;
  onClose: () => void;
}

export function ReceiptModal({ sale, onClose }: ReceiptModalProps) {
  useEffect(() => {
    if (!sale) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [sale, onClose]);

  if (!sale) return null;

  const formattedDate = new Date(sale.createdAt).toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  const paymentLabel =
    sale.paymentMethod === 'upi'
      ? 'UPI'
      : sale.paymentMethod === 'udhaar'
        ? 'Udhaar (Credit)'
        : 'Cash';

  const statusLabel = sale.paymentStatus
    ? UPI_STATUS_LABELS[sale.paymentStatus]
    : sale.paymentMethod === 'udhaar'
      ? 'Added to Udhaar Ledger'
      : 'Payment Confirmed';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#103D2B]/55 backdrop-blur-[1px] p-3 sm:p-4 print:static print:bg-white print:p-0"
      role="dialog"
      aria-modal="true"
      aria-label={`Receipt ${sale.invoiceNo}`}
      onClick={onClose}
    >
      <div
        className="trexo-modal-in print-surface w-full max-w-md max-h-[90vh] flex flex-col rounded-xl border border-[#D8CEB6] bg-white shadow-2xl overflow-hidden print:max-h-none"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal controls */}
        <div className="no-print flex items-center justify-between border-b border-[#E5DEC9] bg-[#FAF7EF] px-5 py-3.5">
          <h2 className="text-sm font-semibold text-[#103D2B]">Bill Receipt · {sale.invoiceNo}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-500 hover:bg-white hover:text-slate-800"
            aria-label="Close receipt"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Printable A5 Receipt Body */}
        <div className="p-5 sm:p-6 text-[#172B22] flex-1 overflow-y-auto trexo-scroll print:max-h-none print:overflow-visible">
          <div className="text-center border-b border-dashed border-slate-300 pb-4">
            <p className="text-[11px] font-bold tracking-[0.2em] text-[#145C3A]">TREXO</p>
            <h3 className="mt-1 text-base font-bold text-[#103D2B]">{STORE_INFO.shopName}</h3>
            <p className="text-xs text-[#5B6B62] mt-0.5">{STORE_INFO.location}</p>
            <p className="text-xs text-[#718078] mt-0.5">
              Ph: {STORE_INFO.phone} · GSTIN: {STORE_INFO.gstin}
            </p>
          </div>

          <div className="mt-4 flex items-start justify-between gap-3 text-xs text-[#5B6B62]">
            <div>
              <p className="font-mono font-semibold text-[#172B22]">{sale.invoiceNo}</p>
              <p>{formattedDate}</p>
            </div>
            <div className="text-right">
              <p className="font-medium text-[#172B22]">{sale.customerName ?? 'Walk-in Customer'}</p>
              <p>
                Mode: <span className="font-semibold text-[#172B22]">{paymentLabel}</span>
              </p>
              <p className="text-[11px] font-medium text-[#145C3A]">
                {statusLabel}
                {sale.isDemoPayment ? ' · DEMO' : ''}
              </p>
            </div>
          </div>

          {(sale.upiTransactionRef || sale.upiUtrNumber || sale.upiIdUsed) && (
            <div className="mt-3 rounded-lg border border-[#E5DEC9] bg-[#FAF7EF] px-3 py-2.5 text-[11px] space-y-1 print:bg-white print:border-slate-300">
              {sale.upiTransactionRef && (
                <div className="flex justify-between gap-2">
                  <span className="text-[#5B6B62]">UPI Ref:</span>
                  <span className="font-mono font-medium text-[#172B22] break-all text-right">
                    {sale.upiTransactionRef}
                  </span>
                </div>
              )}
              {sale.upiUtrNumber && (
                <div className="flex justify-between gap-2">
                  <span className="text-[#5B6B62]">Bank UTR:</span>
                  <span className="font-mono font-medium text-[#172B22] text-right">
                    {sale.upiUtrNumber}
                  </span>
                </div>
              )}
              {sale.upiIdUsed && (
                <div className="flex justify-between gap-2">
                  <span className="text-[#5B6B62]">Store UPI ID:</span>
                  <span className="font-mono text-[#172B22] text-right">{sale.upiIdUsed}</span>
                </div>
              )}
            </div>
          )}

          <table className="mt-4 w-full text-xs border-t border-b border-dashed border-slate-300">
            <thead>
              <tr className="text-slate-500 border-b border-slate-200">
                <th className="py-2 text-left font-medium">Item</th>
                <th className="py-2 text-right font-medium">Qty</th>
                <th className="py-2 text-right font-medium">Rate</th>
                <th className="py-2 text-right font-medium">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {sale.items.map((item) => (
                <tr key={item.productId}>
                  <td className="py-2 pr-2">
                    <p className="font-medium text-[#172B22]">{item.name}</p>
                    {item.unitPricePaise < item.originalPricePaise && (
                      <p className="text-[11px] text-[#145C3A]">
                        Counter offer (MRP {formatINR(item.originalPricePaise)})
                      </p>
                    )}
                  </td>
                  <td className="py-2 text-right font-mono tabular-nums">{item.qty}</td>
                  <td className="py-2 text-right font-mono tabular-nums">
                    {formatINR(item.unitPricePaise)}
                  </td>
                  <td className="py-2 text-right font-mono font-medium tabular-nums">
                    {formatINR(item.lineTotalPaise)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="mt-4 space-y-1.5 text-xs">
            <div className="flex justify-between text-[#5B6B62]">
              <span>Subtotal</span>
              <span className="font-mono tabular-nums">{formatINR(sale.subtotalPaise)}</span>
            </div>
            {sale.discountSavedPaise > 0 && (
              <div className="flex justify-between text-[#145C3A]">
                <span>Counter Savings</span>
                <span className="font-mono tabular-nums">-{formatINR(sale.discountSavedPaise)}</span>
              </div>
            )}
            <div className="flex justify-between pt-2 border-t border-slate-200 text-base font-bold text-[#103D2B]">
              <span>Net Payable</span>
              <span className="font-mono tabular-nums">{formatINR(sale.totalPaise)}</span>
            </div>
          </div>

          {sale.rescuedDeadStockPaise > 0 && (
            <p className="no-print mt-4 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
              Cash unlocked from slow/near-expiry stock: {formatINR(sale.rescuedDeadStockPaise)}
            </p>
          )}

          {sale.isDemoPayment && sale.paymentMethod === 'upi' && (
            <p className="mt-4 rounded-lg border border-[#E5DEC9] bg-[#FAF7EF] px-3 py-2 text-[11px] text-[#5B6B62] text-center">
              DEMO UPI TRANSACTION · Manually confirmed by owner in frontend prototype.
            </p>
          )}

          <p className="mt-6 text-center text-[11px] text-slate-400 border-t border-dashed border-slate-200 pt-3">
            Thank you for shopping with us · Powered by TREXO
          </p>
        </div>

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

