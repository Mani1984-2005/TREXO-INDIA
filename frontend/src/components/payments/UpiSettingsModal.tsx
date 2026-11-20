import { AlertTriangle, QrCode, ShieldCheck, Trash2, X } from 'lucide-react';
import { type FormEvent, useEffect, useState } from 'react';
import { STORE_INFO } from '../../config';
import { useLedgerStore } from '../../store/useLedgerStore';
import { isValidUpiId } from '../../utils/upi';

interface UpiSettingsModalProps {
  open: boolean;
  onClose: () => void;
}

export function UpiSettingsModal({ open, onClose }: UpiSettingsModalProps) {
  const upiConfig = useLedgerStore((s) => s.upiConfig);
  const setUpiConfig = useLedgerStore((s) => s.setUpiConfig);

  const [upiId, setUpiId] = useState(upiConfig.upiId);
  const [merchantName, setMerchantName] = useState(
    upiConfig.merchantName || STORE_INFO.shopName
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setUpiId(upiConfig.upiId);
      setMerchantName(upiConfig.merchantName || STORE_INFO.shopName);
      setError(null);
    }
  }, [open, upiConfig.upiId, upiConfig.merchantName]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = upiId.trim();
    if (!isValidUpiId(trimmed)) {
      setError('Enter a valid UPI ID in handle@bank format (for example: yourstore@okaxis).');
      return;
    }
    setError(null);
    setUpiConfig(trimmed, merchantName.trim() || STORE_INFO.shopName);
    onClose();
  };

  const handleClear = () => {
    setUpiConfig('', STORE_INFO.shopName);
    setUpiId('');
    setError(null);
  };

  return (
    <div
      className="no-print fixed inset-0 z-50 flex items-center justify-center bg-[#103D2B]/55 backdrop-blur-[1px] p-3 sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Store UPI Configuration"
      onClick={onClose}
    >
      <div
        className="trexo-modal-in w-full max-w-md max-h-[90vh] flex flex-col rounded-xl border border-[#D8CEB6] bg-white shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[#E5DEC9] bg-[#103D2B] px-5 py-4 text-white">
          <div className="flex items-center gap-2">
            <QrCode className="h-4 w-4 text-[#C6A15B]" />
            <h2 className="text-sm font-bold">Store UPI Configuration</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-emerald-100 hover:bg-white/10 hover:text-white"
            aria-label="Close UPI settings"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="overflow-y-auto trexo-scroll p-5 space-y-4">
          <div className="rounded-lg border border-[#E5DEC9] bg-[#FAF7EF] p-3.5 text-xs text-[#5B6B62] leading-relaxed">
            <p className="font-semibold text-[#172B22]">Owner-Managed UPI ID</p>
            <p className="mt-1">
              Enter the actual UPI ID registered to{' '}
              <span className="font-medium text-[#103D2B]">{STORE_INFO.shopName}</span>. This UPI
              ID is saved only on this device to generate standard NPCI UPI QR codes for Google
              Pay, PhonePe, Paytm, BHIM, and other UPI apps.
            </p>
          </div>

          <div>
            <label htmlFor="settings-merchant-name" className="block text-xs font-medium text-[#172B22] mb-1">
              Payee Display Name (pn)
            </label>
            <input
              id="settings-merchant-name"
              type="text"
              value={merchantName}
              onChange={(e) => setMerchantName(e.target.value)}
              className="w-full rounded-lg border border-[#D4DDD6] px-3 py-2 text-sm text-[#172B22] focus:border-[#145C3A] focus:outline-none"
            />
          </div>

          <div>
            <label htmlFor="settings-upi-id" className="block text-xs font-medium text-[#172B22] mb-1">
              Store UPI ID / VPA (pa)
            </label>
            <input
              id="settings-upi-id"
              type="text"
              value={upiId}
              onChange={(e) => {
                setUpiId(e.target.value);
                if (error) setError(null);
              }}
              placeholder="Enter your actual store UPI ID (e.g., store@okaxis)"
              autoComplete="off"
              className="w-full rounded-lg border border-[#D4DDD6] px-3 py-2.5 text-sm font-mono text-[#172B22] placeholder:font-sans placeholder:text-[#718078] focus:border-[#145C3A] focus:outline-none"
            />
            {error && (
              <p className="mt-1.5 flex items-center gap-1 text-xs text-red-700">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                <span>{error}</span>
              </p>
            )}
          </div>

          <div className="flex items-start gap-2 text-[11px] text-[#5B6B62]">
            <ShieldCheck className="h-4 w-4 text-[#145C3A] shrink-0 mt-0.5" />
            <span>
              Frontend prototype mode: Trexo does not auto-verify UPI credits. Always verify
              incoming settlement in your merchant app or bank SMS before confirming a bill or
              Udhaar payment.
            </span>
          </div>

          <div className="flex items-center justify-between gap-2 pt-3 border-t border-[#E5EAE5]">
            {upiConfig.upiId ? (
              <button
                type="button"
                onClick={handleClear}
                className="inline-flex items-center gap-1 rounded-lg px-2.5 py-2 text-xs font-medium text-red-700 hover:bg-red-50 whitespace-nowrap"
              >
                <Trash2 className="h-3.5 w-3.5" />
                <span>Clear UPI ID</span>
              </button>
            ) : (
              <span />
            )}

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                className="min-h-[40px] rounded-lg border border-[#D4DDD6] bg-white px-4 py-2 text-xs font-medium text-[#172B22] hover:bg-[#FAF7EF] whitespace-nowrap"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="min-h-[40px] rounded-lg bg-[#145C3A] px-4 py-2 text-xs font-semibold text-white hover:bg-[#103D2B] whitespace-nowrap"
              >
                Save UPI ID
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
