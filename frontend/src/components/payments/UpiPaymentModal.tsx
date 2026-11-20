import {
  AlertTriangle,
  Banknote,
  CheckCircle2,
  MapPin,
  Phone,
  QrCode,
  Store,
  X,
} from 'lucide-react';
import { type FormEvent, type ReactNode, useEffect, useMemo, useRef, useState } from 'react';
import { STORE_INFO } from '../../config';
import { useLedgerStore } from '../../store/useLedgerStore';
import type { UpiPaymentStatus } from '../../types/domain';
import { formatINR, rupeesToPaise } from '../../utils/money';
import {
  buildUpiPaymentUri,
  generateUpiTransactionRef,
  isValidUpiId,
} from '../../utils/upi';
import { PaymentConfirmation } from './PaymentConfirmation';
import { PaymentMethodSelector } from './PaymentMethodSelector';
import { PaymentStatusIndicator } from './PaymentStatusIndicator';
import { UpiQrDisplay } from './UpiQrDisplay';

export interface ConfirmedPaymentResult {
  paymentMethod: 'cash' | 'upi';
  amountPaise: number;
  transactionRef: string;
  utrNumber?: string;
  upiIdUsed?: string;
  status: 'confirmed';
  isDemo: true;
  confirmedAt: string;
}

export interface PaymentAttemptResult {
  paymentMethod: 'upi';
  amountPaise: number;
  transactionRef: string;
  status: 'failed' | 'cancelled';
  upiIdUsed?: string;
  isDemo: true;
}

export interface UpiPaymentModalProps {
  open: boolean;
  title: string;
  subtitle?: string;
  /** Default / fixed payable amount in integer paise */
  amountPaise: number;
  /** Allow editing the payable amount (e.g., partial Udhaar repayments) */
  editableAmount?: boolean;
  /** Upper bound in paise when editableAmount is true (prevents overpayment) */
  maxAmountPaise?: number;
  /** Default payment method when modal opens */
  initialPaymentMethod?: 'cash' | 'upi';
  /** Payment methods available inside the modal */
  allowedMethods?: readonly ('cash' | 'upi')[];
  /** Prefix used when generating unique transaction references */
  referencePrefix?: 'BILL' | 'UDHAAR';
  /** UPI payment note (`tn`) encoded in QR & intent link */
  transactionNote: string;
  /** Optional contextual summary (e.g., itemized Counter bill or Udhaar customer card) */
  summaryContent?: ReactNode;
  /** Optional helper line rendered below the editable amount input */
  renderAmountFeedback?: (amountPaise: number, isValid: boolean) => ReactNode;
  onClose: () => void;
  /** Invoked ONLY after explicit manual confirmation by the store owner */
  onConfirmPayment: (result: ConfirmedPaymentResult) => Promise<void>;
  /** Optional callback when a demo UPI attempt is marked failed or cancelled */
  onPaymentAttemptStatus?: (attempt: PaymentAttemptResult) => void | Promise<void>;
}

export function UpiPaymentModal({
  open,
  title,
  subtitle,
  amountPaise,
  editableAmount = false,
  maxAmountPaise,
  initialPaymentMethod = 'upi',
  allowedMethods = ['upi', 'cash'] as const,
  referencePrefix = 'BILL',
  transactionNote,
  summaryContent,
  renderAmountFeedback,
  onClose,
  onConfirmPayment,
  onPaymentAttemptStatus,
}: UpiPaymentModalProps) {
  const upiConfig = useLedgerStore((s) => s.upiConfig);
  const pushToast = useLedgerStore((s) => s.pushToast);

  const [paymentMethod, setPaymentMethod] = useState<'cash' | 'upi'>(initialPaymentMethod);
  const [amountRupeesInput, setAmountRupeesInput] = useState('');
  const [transactionRef, setTransactionRef] = useState(() =>
    generateUpiTransactionRef(referencePrefix)
  );
  const [status, setStatus] = useState<UpiPaymentStatus>('initiated');
  const [utrNumber, setUtrNumber] = useState('');
  const [isConfirming, setIsConfirming] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Strict duplicate-confirmation lock across rapid clicks
  const confirmedRefsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (open) {
      setPaymentMethod(initialPaymentMethod);
      const initialRupees = (Math.max(0, amountPaise) / 100).toFixed(
        amountPaise % 100 === 0 ? 0 : 2
      );
      setAmountRupeesInput(initialRupees);
      setTransactionRef(generateUpiTransactionRef(referencePrefix));
      setStatus('initiated');
      setUtrNumber('');
      setIsConfirming(false);
      setErrorMessage(null);
    }
  }, [open, initialPaymentMethod, amountPaise, referencePrefix]);

  useEffect(() => {
    if (!open) return;
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isConfirming) {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [open, isConfirming, onClose]);

  const effectiveAmountPaise = editableAmount
    ? Number.isFinite(Number(amountRupeesInput))
      ? rupeesToPaise(Number(amountRupeesInput))
      : 0
    : Math.max(0, Math.round(amountPaise));

  const effectiveMaxPaise =
    editableAmount && typeof maxAmountPaise === 'number' ? maxAmountPaise : undefined;
  const isOverMax =
    typeof effectiveMaxPaise === 'number' && effectiveAmountPaise > effectiveMaxPaise;
  const isAmountValid = effectiveAmountPaise > 0 && !isOverMax;

  const hasValidUpi = isValidUpiId(upiConfig.upiId);
  const merchantName = upiConfig.merchantName || STORE_INFO.shopName;

  // Build standard NPCI UPI intent URI dynamically whenever amount, store details, or reference change
  const upiUri = useMemo(() => {
    if (!open || !hasValidUpi || !isAmountValid) return null;
    try {
      return buildUpiPaymentUri({
        upiId: upiConfig.upiId,
        merchantName,
        transactionRef,
        transactionNote,
        amountPaise: effectiveAmountPaise,
      });
    } catch {
      return null;
    }
  }, [
    open,
    hasValidUpi,
    isAmountValid,
    upiConfig.upiId,
    merchantName,
    transactionRef,
    transactionNote,
    effectiveAmountPaise,
  ]);

  if (!open) return null;

  const canConfirmUpi =
    hasValidUpi &&
    Boolean(upiUri) &&
    isAmountValid &&
    (status === 'initiated' || status === 'awaiting_verification') &&
    !confirmedRefsRef.current.has(transactionRef);

  const handleEditableAmountChange = (nextValue: string) => {
    setAmountRupeesInput(nextValue);
    setErrorMessage(null);
    // Keep QR & confirmation status in sync when payment amount changes dynamically
    if (status === 'awaiting_verification') {
      setStatus('initiated');
    } else if (status === 'failed' || status === 'cancelled') {
      setTransactionRef(generateUpiTransactionRef(referencePrefix));
      setStatus('initiated');
    }
  };

  const quickPresets =
    editableAmount && typeof effectiveMaxPaise === 'number'
      ? [
          ...(effectiveMaxPaise >= 20000 ? [{ label: '₹200', value: '200' }] : []),
          ...(effectiveMaxPaise >= 50000 ? [{ label: '₹500', value: '500' }] : []),
          {
            label: 'Full Due',
            value: (effectiveMaxPaise / 100).toFixed(effectiveMaxPaise % 100 === 0 ? 0 : 2),
          },
        ]
      : [];

  const handleMethodChange = (nextMethod: 'cash' | 'upi') => {
    if (isConfirming) return;
    setPaymentMethod(nextMethod);
    setErrorMessage(null);
    if (nextMethod === 'upi' && (status === 'failed' || status === 'cancelled')) {
      setTransactionRef(generateUpiTransactionRef(referencePrefix));
      setStatus('initiated');
    }
  };

  const handleUpiAppLaunched = () => {
    // Opening a UPI app NEVER auto-confirms payment — only advances to Awaiting Verification
    if (status === 'initiated') {
      setStatus('awaiting_verification');
    }
  };

  const handleConfirmUpi = async () => {
    if (!canConfirmUpi || isConfirming) return;
    if (confirmedRefsRef.current.has(transactionRef)) {
      setErrorMessage('This UPI transaction reference has already been confirmed.');
      return;
    }

    setErrorMessage(null);
    setIsConfirming(true);
    confirmedRefsRef.current.add(transactionRef);

    try {
      await onConfirmPayment({
        paymentMethod: 'upi',
        amountPaise: effectiveAmountPaise,
        transactionRef,
        utrNumber: utrNumber.trim() || undefined,
        upiIdUsed: upiConfig.upiId.trim(),
        status: 'confirmed',
        isDemo: true,
        confirmedAt: new Date().toISOString(),
      });
      setStatus('confirmed');
    } catch (err) {
      confirmedRefsRef.current.delete(transactionRef);
      setErrorMessage(
        err instanceof Error ? err.message : 'Unable to confirm UPI payment. Please try again.'
      );
    } finally {
      setIsConfirming(false);
    }
  };

  const handleConfirmCash = async (e: FormEvent) => {
    e.preventDefault();
    if (!isAmountValid || isConfirming) {
      if (isOverMax && typeof effectiveMaxPaise === 'number') {
        setErrorMessage(
          `Payment amount cannot exceed ${formatINR(effectiveMaxPaise)}.`
        );
      } else {
        setErrorMessage('Enter a valid amount greater than ₹0.');
      }
      return;
    }

    const cashRef = generateUpiTransactionRef('CASH');
    if (confirmedRefsRef.current.has(cashRef)) return;

    setErrorMessage(null);
    setIsConfirming(true);
    confirmedRefsRef.current.add(cashRef);

    try {
      await onConfirmPayment({
        paymentMethod: 'cash',
        amountPaise: effectiveAmountPaise,
        transactionRef: cashRef,
        status: 'confirmed',
        isDemo: true,
        confirmedAt: new Date().toISOString(),
      });
      setStatus('confirmed');
    } catch (err) {
      confirmedRefsRef.current.delete(cashRef);
      setErrorMessage(
        err instanceof Error ? err.message : 'Unable to record cash payment. Please try again.'
      );
    } finally {
      setIsConfirming(false);
    }
  };

  const handleMarkFailed = async () => {
    setStatus('failed');
    setErrorMessage(null);
    if (onPaymentAttemptStatus) {
      await onPaymentAttemptStatus({
        paymentMethod: 'upi',
        amountPaise: Math.min(
          effectiveAmountPaise,
          effectiveMaxPaise ?? effectiveAmountPaise
        ),
        transactionRef,
        status: 'failed',
        upiIdUsed: upiConfig.upiId.trim() || undefined,
        isDemo: true,
      });
    } else {
      pushToast(
        'UPI payment marked failed',
        'No bill or balance was modified. Retry or switch to Cash.',
        'amber'
      );
    }
  };

  const handleCancelPayment = async () => {
    setStatus('cancelled');
    setErrorMessage(null);
    if (onPaymentAttemptStatus) {
      await onPaymentAttemptStatus({
        paymentMethod: 'upi',
        amountPaise: Math.min(
          effectiveAmountPaise,
          effectiveMaxPaise ?? effectiveAmountPaise
        ),
        transactionRef,
        status: 'cancelled',
        upiIdUsed: upiConfig.upiId.trim() || undefined,
        isDemo: true,
      });
    } else {
      pushToast(
        'UPI payment cancelled',
        'No bill or balance was modified. Retry or switch to Cash.',
        'slate'
      );
    }
  };

  const handleRetryNewReference = () => {
    setTransactionRef(generateUpiTransactionRef(referencePrefix));
    setStatus('initiated');
    setUtrNumber('');
    setErrorMessage(null);
  };

  const isUpiMode = paymentMethod === 'upi';

  return (
    <div
      className="no-print fixed inset-0 z-50 flex items-center justify-center bg-[#103D2B]/55 backdrop-blur-[1px] p-3 sm:p-5 overflow-y-auto"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={() => {
        if (!isConfirming) onClose();
      }}
    >
      <div
        className={`trexo-modal-in my-auto w-full rounded-xl border border-[#D8CEB6] bg-white shadow-2xl overflow-hidden transition-all ${
          isUpiMode ? 'max-w-4xl' : 'max-w-lg'
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header Bar */}
        <div className="flex items-center justify-between gap-4 border-b border-[#E5DEC9] bg-[#103D2B] px-5 py-4 text-white">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              {isUpiMode ? (
                <QrCode className="h-4 w-4 text-[#C6A15B] shrink-0" />
              ) : (
                <Banknote className="h-4 w-4 text-[#C6A15B] shrink-0" />
              )}
              <h2 className="text-sm sm:text-base font-bold tracking-tight truncate">{title}</h2>
            </div>
            {subtitle && (
              <p className="mt-0.5 text-xs text-emerald-100/80 truncate">{subtitle}</p>
            )}
          </div>
          <button
            type="button"
            disabled={isConfirming}
            onClick={onClose}
            className="rounded-lg p-2 text-emerald-100 hover:bg-white/10 hover:text-white disabled:opacity-40 shrink-0"
            aria-label="Close payment modal"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Store Identity Bar */}
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-[#E5DEC9] bg-[#FAF7EF] px-5 py-2.5 text-xs text-[#5B6B62]">
          <div className="flex items-center gap-2 min-w-0">
            <Store className="h-3.5 w-3.5 text-[#145C3A] shrink-0" />
            <span className="font-semibold text-[#103D2B] truncate">
              {upiConfig.merchantName || STORE_INFO.shopName}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px]">
            <span className="inline-flex items-center gap-1">
              <MapPin className="h-3 w-3 text-[#9A7A3A]" />
              <span>{STORE_INFO.location}</span>
            </span>
            <span className="inline-flex items-center gap-1 font-mono">
              <Phone className="h-3 w-3 text-[#9A7A3A]" />
              <span>{STORE_INFO.phone}</span>
            </span>
          </div>
        </div>

        {/* Responsive Content Body */}
        <div className="p-4 sm:p-6 max-h-[80vh] overflow-y-auto trexo-scroll">
          <div
            className={
              isUpiMode
                ? 'grid grid-cols-1 lg:grid-cols-12 gap-5 items-start'
                : 'space-y-4'
            }
          >
            {/* Left Column (UPI: QR Display; Cash: Full Controls) */}
            <div className={isUpiMode ? 'lg:col-span-6 space-y-4' : 'space-y-4'}>
              {/* Payment Method Selector (Cash / UPI) */}
              {allowedMethods.length > 1 && (
                <PaymentMethodSelector
                  value={paymentMethod}
                  onChange={handleMethodChange}
                  options={allowedMethods}
                  label="Select Payment Method"
                />
              )}

              {/* Optional Summary Slot (shown here in Cash mode or when editable amount is used) */}
              {(!isUpiMode || editableAmount) && summaryContent}

              {/* Editable Amount Field (e.g. Udhaar Repayments) */}
              {editableAmount && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <label
                      htmlFor="reusable-payment-amount"
                      className="block text-xs font-semibold text-[#172B22]"
                    >
                      Payment Amount (₹)
                    </label>
                    {quickPresets.length > 0 && (
                      <div className="flex items-center gap-1.5">
                        {quickPresets.map((preset) => (
                          <button
                            key={preset.label}
                            type="button"
                            disabled={isConfirming}
                            onClick={() => handleEditableAmountChange(preset.value)}
                            className="rounded-md border border-[#D8CEB6] bg-white px-2 py-1 text-[11px] font-mono font-medium text-[#172B22] hover:border-[#145C3A] hover:text-[#145C3A] whitespace-nowrap"
                          >
                            {preset.label}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  <input
                    id="reusable-payment-amount"
                    type="number"
                    min="1"
                    max={typeof effectiveMaxPaise === 'number' ? effectiveMaxPaise / 100 : undefined}
                    step="any"
                    disabled={isConfirming}
                    value={amountRupeesInput}
                    onChange={(e) => handleEditableAmountChange(e.target.value)}
                    className="w-full rounded-lg border border-[#D4DDD6] bg-white px-3.5 py-2.5 text-base font-mono font-semibold text-[#103D2B] tabular-nums focus:border-[#145C3A] focus:outline-none"
                  />

                  {isOverMax && typeof effectiveMaxPaise === 'number' ? (
                    <p className="flex items-center gap-1.5 text-xs font-medium text-red-700">
                      <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                      <span>
                        Amount cannot exceed outstanding balance ({formatINR(effectiveMaxPaise)}).
                      </span>
                    </p>
                  ) : renderAmountFeedback ? (
                    renderAmountFeedback(effectiveAmountPaise, isAmountValid)
                  ) : !isAmountValid ? (
                    <p className="text-xs text-amber-700">
                      Enter a valid amount greater than ₹0.
                    </p>
                  ) : null}
                </div>
              )}

              {/* UPI QR Display */}
              {isUpiMode && (
                <UpiQrDisplay
                  amountPaise={isAmountValid ? effectiveAmountPaise : 0}
                  transactionRef={transactionRef}
                  transactionNote={transactionNote}
                  upiUri={upiUri}
                  onUpiAppLaunched={handleUpiAppLaunched}
                  disabled={
                    !isAmountValid ||
                    status === 'failed' ||
                    status === 'cancelled' ||
                    status === 'confirmed'
                  }
                />
              )}

              {/* Cash Collection Confirmation Panel */}
              {!isUpiMode && (
                <form onSubmit={handleConfirmCash} className="space-y-4">
                  <div className="rounded-xl border border-[#E5DEC9] bg-[#FAF7EF] p-4 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-[#5B6B62]">Cash Payable</span>
                      <span className="font-mono text-lg font-bold text-[#103D2B] tabular-nums">
                        {formatINR(isAmountValid ? effectiveAmountPaise : 0)}
                      </span>
                    </div>
                    <p className="text-[11px] text-[#5B6B62] leading-relaxed">
                      DEMO RECORD · Confirm only after counting physical cash at the counter.
                    </p>
                  </div>

                  {errorMessage && (
                    <div
                      role="alert"
                      className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-xs text-red-800"
                    >
                      {errorMessage}
                    </div>
                  )}

                  <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#E5EAE5]">
                    <button
                      type="button"
                      disabled={isConfirming}
                      onClick={onClose}
                      className="min-h-[44px] rounded-lg border border-[#D4DDD6] bg-white px-4 py-2 text-sm font-medium text-[#172B22] hover:bg-[#FAF7EF] whitespace-nowrap"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={!isAmountValid || isConfirming}
                      className="min-h-[44px] inline-flex items-center gap-2 rounded-lg bg-[#145C3A] px-5 py-2 text-sm font-semibold text-white hover:bg-[#103D2B] disabled:bg-[#D4DDD6] disabled:text-[#718078] whitespace-nowrap"
                    >
                      <CheckCircle2 className="h-4 w-4 shrink-0" />
                      <span>
                        {isConfirming
                          ? 'Recording...'
                          : `Confirm Cash ${isAmountValid ? formatINR(effectiveAmountPaise) : ''}`}
                      </span>
                    </button>
                  </div>
                </form>
              )}
            </div>

            {/* Right Column (UPI Mode Only): Contextual Summary, Demo Status & Manual Verification */}
            {isUpiMode && (
              <div className="lg:col-span-6 space-y-4">
                {!editableAmount && summaryContent}

                <PaymentStatusIndicator status={status} isDemo />

                <PaymentConfirmation
                  amountPaise={isAmountValid ? effectiveAmountPaise : 0}
                  status={status}
                  canConfirm={canConfirmUpi}
                  isConfirming={isConfirming}
                  utrNumber={utrNumber}
                  onUtrChange={setUtrNumber}
                  onSetStatus={(next) => {
                    setStatus(next);
                    setErrorMessage(null);
                  }}
                  onConfirmPayment={() => void handleConfirmUpi()}
                  onMarkFailed={() => void handleMarkFailed()}
                  onCancelPayment={() => void handleCancelPayment()}
                  onRetryNewReference={handleRetryNewReference}
                  errorMessage={errorMessage}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
