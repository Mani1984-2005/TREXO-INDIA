import {
  AlertTriangle,
  Check,
  Copy,
  ExternalLink,
  Pencil,
  QrCode,
  Smartphone,
} from 'lucide-react';
import { type FormEvent, useEffect, useMemo, useState } from 'react';
import { STORE_INFO } from '../../config';
import { useLedgerStore } from '../../store/useLedgerStore';
import { formatINR } from '../../utils/money';
import {
  buildUpiPaymentUri,
  generateUpiQrSvg,
  isValidUpiId,
  SUPPORTED_UPI_APPS,
} from '../../utils/upi';

interface UpiQrDisplayProps {
  amountPaise: number;
  transactionRef: string;
  transactionNote: string;
  /** Optional pre-built UPI intent URI owned by parent modal (keeps QR & link strictly in sync) */
  upiUri?: string | null;
  onUpiAppLaunched?: () => void;
  disabled?: boolean;
}

export function UpiQrDisplay({
  amountPaise,
  transactionRef,
  transactionNote,
  upiUri: controlledUpiUri,
  onUpiAppLaunched,
  disabled = false,
}: UpiQrDisplayProps) {
  const upiConfig = useLedgerStore((s) => s.upiConfig);
  const setUpiConfig = useLedgerStore((s) => s.setUpiConfig);

  const [editingUpi, setEditingUpi] = useState(false);
  const [upiDraft, setUpiDraft] = useState(upiConfig.upiId);
  const [upiError, setUpiError] = useState<string | null>(null);
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);
  const [qrError, setQrError] = useState<string | null>(null);
  const [copiedField, setCopiedField] = useState<'upi' | 'ref' | null>(null);

  useEffect(() => {
    setUpiDraft(upiConfig.upiId);
  }, [upiConfig.upiId]);

  const hasValidUpi = isValidUpiId(upiConfig.upiId);
  const hasValidAmount = Number.isFinite(amountPaise) && amountPaise > 0;

  const upiUri = useMemo(() => {
    if (controlledUpiUri !== undefined) return controlledUpiUri;
    if (!hasValidUpi || !hasValidAmount) return null;
    try {
      return buildUpiPaymentUri({
        upiId: upiConfig.upiId,
        merchantName: upiConfig.merchantName || STORE_INFO.shopName,
        transactionRef,
        transactionNote,
        amountPaise,
      });
    } catch {
      return null;
    }
  }, [
    controlledUpiUri,
    hasValidUpi,
    hasValidAmount,
    upiConfig.upiId,
    upiConfig.merchantName,
    transactionRef,
    transactionNote,
    amountPaise,
  ]);

  useEffect(() => {
    let active = true;
    if (!upiUri) {
      setQrDataUrl(null);
      setQrError(null);
      return;
    }

    generateUpiQrSvg(upiUri)
      .then((svg) => {
        if (!active) return;
        const encoded = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
        setQrDataUrl(encoded);
        setQrError(null);
      })
      .catch(() => {
        if (!active) return;
        setQrDataUrl(null);
        setQrError('Unable to render QR code for the current payment details.');
      });

    return () => {
      active = false;
    };
  }, [upiUri]);

  const handleSaveUpiId = (e: FormEvent) => {
    e.preventDefault();
    const cleaned = upiDraft.trim();
    if (!isValidUpiId(cleaned)) {
      setUpiError('Enter a valid UPI ID format such as yourstore@okaxis or mobile@ybl');
      return;
    }
    setUpiError(null);
    setUpiConfig(cleaned, STORE_INFO.shopName);
    setEditingUpi(false);
  };

  const handleCopy = async (text: string, field: 'upi' | 'ref') => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 1800);
    } catch {
      // Clipboard API unavailable in restricted contexts
    }
  };

  const showConfigForm = !hasValidUpi || editingUpi;
  const merchantName = upiConfig.merchantName || STORE_INFO.shopName;

  return (
    <div className="rounded-xl border border-[#E2DAC8] bg-[#FAF7EF] p-5 space-y-4">
      {/* Store & Amount Header */}
      <div className="flex items-start justify-between gap-3 border-b border-[#E5DEC9] pb-3.5">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold tracking-wider text-[#9A7A3A]">
            TREXO UPI COLLECTION
          </p>
          <h3 className="mt-0.5 text-sm font-bold text-[#103D2B] truncate">{merchantName}</h3>
        </div>
        <div className="text-right shrink-0">
          <p className="text-[11px] text-[#5B6B62]">Payable Amount</p>
          <p className="font-mono text-xl font-bold text-[#103D2B] tabular-nums">
            {formatINR(amountPaise)}
          </p>
        </div>
      </div>

      {/* Store UPI Configuration Form (when unconfigured or editing) */}
      {showConfigForm ? (
        <form
          onSubmit={handleSaveUpiId}
          className="rounded-xl border border-[#D8CEB6] bg-white p-4 space-y-3"
        >
          <div className="flex items-start gap-2.5">
            <QrCode className="h-4 w-4 text-[#145C3A] shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-[#172B22]">
                {hasValidUpi ? 'Update Store UPI ID' : 'Configure Your Store UPI ID'}
              </p>
              <p className="mt-0.5 text-xs text-[#5B6B62] leading-relaxed">
                Trexo does not prefill or invent merchant UPI credentials. Enter your store&apos;s
                actual UPI ID to generate scannable QR codes.
              </p>
            </div>
          </div>

          <div>
            <label
              htmlFor="inline-store-upi-id"
              className="block text-xs font-medium text-[#172B22] mb-1"
            >
              Store UPI ID (VPA)
            </label>
            <input
              id="inline-store-upi-id"
              type="text"
              value={upiDraft}
              onChange={(e) => {
                setUpiDraft(e.target.value);
                if (upiError) setUpiError(null);
              }}
              placeholder="e.g., yourstore@okaxis or yournumber@ybl"
              autoComplete="off"
              className="w-full rounded-lg border border-[#D4DDD6] bg-white px-3 py-2.5 text-sm font-mono text-[#172B22] placeholder:font-sans placeholder:text-[#718078] focus:border-[#145C3A] focus:outline-none"
            />
            {upiError && (
              <p className="mt-1.5 flex items-center gap-1 text-xs text-red-700">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                <span>{upiError}</span>
              </p>
            )}
          </div>

          <div className="flex items-center justify-end gap-2 pt-1">
            {hasValidUpi && (
              <button
                type="button"
                onClick={() => {
                  setUpiDraft(upiConfig.upiId);
                  setUpiError(null);
                  setEditingUpi(false);
                }}
                className="min-h-[40px] rounded-lg border border-[#D4DDD6] bg-white px-3.5 py-2 text-xs font-medium text-[#172B22] hover:bg-[#FAF7EF] whitespace-nowrap"
              >
                Cancel
              </button>
            )}
            <button
              type="submit"
              className="min-h-[40px] rounded-lg bg-[#145C3A] px-4 py-2 text-xs font-semibold text-white hover:bg-[#103D2B] transition-colors whitespace-nowrap"
            >
              Save UPI ID &amp; Show QR
            </button>
          </div>
        </form>
      ) : (
        <>
          {/* Scannable QR Display Frame */}
          <div className="flex flex-col items-center rounded-xl border border-[#E5DEC9] bg-white p-4 sm:p-5">
            {!hasValidAmount || !upiUri ? (
              <div className="flex h-48 w-48 sm:h-52 sm:w-52 flex-col items-center justify-center rounded-lg border border-dashed border-[#D4DDD6] bg-[#F3F5F2] p-4 text-center text-xs text-[#5B6B62]">
                Enter a valid amount greater than ₹0 to generate the UPI QR code.
              </div>
            ) : qrError ? (
              <div className="flex h-48 w-48 sm:h-52 sm:w-52 flex-col items-center justify-center rounded-lg border border-red-200 bg-red-50 p-4 text-center text-xs text-red-700">
                {qrError}
              </div>
            ) : qrDataUrl ? (
              <div
                className={`relative rounded-xl border-2 border-[#145C3A]/15 bg-white p-3 transition-opacity ${
                  disabled ? 'opacity-45' : 'opacity-100'
                }`}
              >
                <img
                  src={qrDataUrl}
                  alt={`UPI QR Code for ${formatINR(amountPaise, true)} to ${merchantName} (${upiConfig.upiId})`}
                  className="h-48 w-48 sm:h-56 sm:w-56 block"
                  referrerPolicy="no-referrer"
                />
              </div>
            ) : (
              <div className="h-48 w-48 sm:h-52 sm:w-52 animate-pulse rounded-lg bg-[#F3F5F2]" />
            )}

            <p className="mt-3 text-xs font-medium text-[#172B22] text-center">
              Customer scans with Google Pay, PhonePe, Paytm, BHIM, or any UPI app
            </p>

            {/* Supported UPI Apps Strip (unboxed clean typographic presentation, GPay featured) */}
            <div className="mt-2 flex flex-wrap items-center justify-center gap-x-2.5 gap-y-1 text-[11px] text-[#5B6B62]">
              {SUPPORTED_UPI_APPS.map((app, index) => (
                <span key={app.id} className="inline-flex items-center gap-2">
                  {index > 0 && (
                    <span className="text-[#C6A15B]" aria-hidden="true">
                      ·
                    </span>
                  )}
                  <span className={app.featured ? 'font-semibold text-[#145C3A]' : ''}>
                    {app.name}
                  </span>
                </span>
              ))}
            </div>
          </div>

          {/* Store UPI ID & Reference Details */}
          <div className="divide-y divide-[#E5DEC9] rounded-xl border border-[#E5DEC9] bg-white text-xs">
            <div className="flex items-center justify-between gap-2 px-3.5 py-2.5">
              <div className="min-w-0">
                <p className="text-[11px] text-[#5B6B62]">Store UPI ID</p>
                <p className="font-mono font-semibold text-[#172B22] truncate">
                  {upiConfig.upiId}
                </p>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <button
                  type="button"
                  onClick={() => void handleCopy(upiConfig.upiId, 'upi')}
                  className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-[11px] font-medium text-[#145C3A] hover:bg-[#FAF7EF] whitespace-nowrap"
                  aria-label="Copy Store UPI ID"
                >
                  {copiedField === 'upi' ? (
                    <>
                      <Check className="h-3.5 w-3.5" />
                      <span>Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-3.5 w-3.5" />
                      <span>Copy</span>
                    </>
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => setEditingUpi(true)}
                  className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-[11px] font-medium text-[#5B6B62] hover:bg-slate-100 hover:text-[#172B22] whitespace-nowrap"
                  aria-label="Edit Store UPI ID"
                >
                  <Pencil className="h-3 w-3" />
                  <span>Edit</span>
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between gap-2 px-3.5 py-2.5">
              <div className="min-w-0">
                <p className="text-[11px] text-[#5B6B62]">Transaction Reference</p>
                <p className="font-mono font-medium text-[#172B22] truncate">{transactionRef}</p>
              </div>
              <button
                type="button"
                onClick={() => void handleCopy(transactionRef, 'ref')}
                className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-[11px] font-medium text-[#5B6B62] hover:bg-slate-100 hover:text-[#172B22] whitespace-nowrap shrink-0"
                aria-label="Copy transaction reference"
              >
                {copiedField === 'ref' ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-[#145C3A]" />
                    <span className="text-[#145C3A]">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5" />
                    <span>Copy Ref</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Mobile / Compatible Device UPI Intent Link */}
          {upiUri && (
            <div className="space-y-2">
              <a
                href={disabled ? undefined : upiUri}
                onClick={(e) => {
                  if (disabled) {
                    e.preventDefault();
                    return;
                  }
                  onUpiAppLaunched?.();
                }}
                aria-disabled={disabled}
                className={`min-h-[44px] w-full inline-flex items-center justify-center gap-2 rounded-lg border border-[#145C3A] bg-white px-3.5 py-2.5 text-center text-xs font-semibold leading-snug text-[#145C3A] transition-colors ${
                  disabled
                    ? 'pointer-events-none opacity-50'
                    : 'hover:bg-[#145C3A] hover:text-white'
                }`}
              >
                <Smartphone className="h-4 w-4 shrink-0" />
                <span>Pay via UPI app (GPay / PhonePe / Paytm / BHIM)</span>
                <ExternalLink className="h-3.5 w-3.5 shrink-0" />
              </a>

              <details className="text-[11px] text-[#5B6B62]">
                <summary className="cursor-pointer select-none text-center hover:text-[#103D2B]">
                  Inspect live UPI intent URI ({formatINR(amountPaise, true)})
                </summary>
                <p className="mt-1.5 break-all rounded-lg border border-[#E5DEC9] bg-white p-2.5 font-mono text-[10px] text-[#172B22]">
                  {upiUri}
                </p>
              </details>
            </div>
          )}
        </>
      )}
    </div>
  );
}
