import { Printer, X } from 'lucide-react';
import { useEffect } from 'react';
import { STORE_INFO } from '../config';
import type { SupplierReturnItem } from '../types/domain';
import { formatINR } from '../utils/money';

interface SupplierReturnSlipModalProps {
  items: SupplierReturnItem[];
  onClose: () => void;
  onConfirmPrint: (returnIds: string[]) => Promise<void>;
}

export function SupplierReturnSlipModal({
  items,
  onClose,
  onConfirmPrint,
}: SupplierReturnSlipModalProps) {
  useEffect(() => {
    if (items.length === 0) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [items.length, onClose]);

  if (items.length === 0) return null;

  const totalCreditPaise = items.reduce((sum, i) => sum + i.totalCreditPaise, 0);
  const dateLabel = new Date().toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });

  const handlePrint = async () => {
    await onConfirmPrint(items.map((i) => i.id));
    window.print();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#103D2B]/55 backdrop-blur-[1px] p-3 sm:p-4 print:static print:bg-white print:p-0"
      role="dialog"
      aria-modal="true"
      aria-label="Supplier Return Slip"
      onClick={onClose}
    >
      <div
        className="trexo-modal-in print-surface flex max-h-[90vh] w-full max-w-2xl flex-col rounded-xl border border-[#D8CEB6] bg-white shadow-2xl overflow-hidden print:max-h-none print:overflow-visible"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="no-print flex items-center justify-between border-b border-white/10 bg-[#103D2B] px-5 py-4 text-white shrink-0">
          <h2 className="text-sm font-semibold">Supplier Return Debit Note</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-white/75 hover:bg-white/10 hover:text-white transition-colors"
            aria-label="Close return slip"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto trexo-scroll p-5 sm:p-6 text-[#172B22] print:overflow-visible">
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[#E5EAE5] pb-4">
            <div>
              <p className="text-[11px] font-bold tracking-[0.18em] text-[#145C3A]">TREXO</p>
              <h3 className="mt-0.5 text-lg font-bold text-[#103D2B]">{STORE_INFO.shopName}</h3>
              <p className="text-xs text-[#5B6B62]">{STORE_INFO.location}</p>
              <p className="text-xs text-[#718078]">
                Ph: {STORE_INFO.phone} · GSTIN: {STORE_INFO.gstin}
              </p>
            </div>
            <div className="text-right text-xs">
              <p className="font-bold text-[#103D2B]">SUPPLIER RETURN SLIP</p>
              <p className="text-[#5B6B62] mt-0.5">Date: {dateLabel}</p>
              <p className="text-[#718078]">Lines: {items.length}</p>
            </div>
          </div>

          <div className="mt-4 overflow-x-auto trexo-scroll print:overflow-visible">
            <table className="w-full min-w-[460px] text-xs">
              <thead>
                <tr className="border-b border-[#E5EAE5] text-[#65766D]">
                  <th className="py-2 text-left font-semibold">SKU / Item</th>
                  <th className="py-2 text-left font-semibold">Supplier</th>
                  <th className="py-2 text-left font-semibold">Reason</th>
                  <th className="py-2 text-right font-semibold">Qty</th>
                  <th className="py-2 text-right font-semibold">Cost Credit</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5EAE5]">
                {items.map((item) => (
                  <tr key={item.id}>
                    <td className="py-2.5 pr-3">
                      <p className="font-semibold text-[#172B22]">{item.productName}</p>
                      <p className="font-mono text-[11px] text-[#65766D]">{item.sku}</p>
                    </td>
                    <td className="py-2.5 pr-3 text-[#172B22]">{item.supplierName}</td>
                    <td className="py-2.5 pr-3 text-[#65766D]">{item.reason}</td>
                    <td className="py-2.5 text-right font-mono tabular-nums">{item.qty}</td>
                    <td className="py-2.5 text-right font-mono font-semibold text-[#103D2B] tabular-nums">
                      {formatINR(item.totalCreditPaise)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex items-center justify-between border-t border-[#E5EAE5] pt-4">
            <span className="text-xs text-[#718078]">
              Please adjust against next distributor invoice or issue credit note.
            </span>
            <div className="text-right">
              <p className="text-xs text-[#718078]">Total Return Credit</p>
              <p className="font-mono text-lg font-bold text-[#103D2B] tabular-nums">
                {formatINR(totalCreditPaise)}
              </p>
            </div>
          </div>

          <p className="mt-6 text-center text-[11px] text-[#718078] border-t border-dashed border-[#E5EAE5] pt-3">
            Authorized Store Signatory · Powered by TREXO
          </p>
        </div>

        <div className="no-print flex items-center justify-end gap-2 border-t border-[#E5DEC9] bg-[#FAF7EF] px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="min-h-[40px] rounded-lg border border-[#D4DDD6] bg-white px-4 py-2 text-sm font-medium text-[#172B22] hover:bg-[#F3F5F2] whitespace-nowrap"
          >
            Close
          </button>
          <button
            type="button"
            onClick={handlePrint}
            className="min-h-[40px] inline-flex items-center gap-2 rounded-lg bg-[#145C3A] px-4 py-2 text-sm font-semibold text-white hover:bg-[#103D2B] whitespace-nowrap"
          >
            <Printer className="h-4 w-4" />
            <span>Print Return Slip</span>
          </button>
        </div>
      </div>
    </div>
  );
}
