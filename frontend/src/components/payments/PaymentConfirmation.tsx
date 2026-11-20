import {
  CheckCircle2,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from 'lucide-react';
import type { UpiPaymentStatus } from '../../types/domain';
import { formatINR } from '../../utils/money';

interface PaymentConfirmationProps {
  amountPaise: number;
  status: UpiPaymentStatus;
  canConfirm: boolean;
  isConfirming: boolean;
  utrNumber: string;
  onUtrChange: (value: string) => void;
  onSetStatus: (status: UpiPaymentStatus) => void;
  onConfirmPayment: () => void;
  onMarkFailed: () => void;
  onCancelPayment: () => void;
  onRetryNewReference: () => void;
  errorMessage?: string | null;
}

export function PaymentConfirmation({
  amountPaise,
  status,
  canConfirm,
  isConfirming,
  utrNumber,
  onUtrChange,
  onSetStatus,
  onConfirmPayment,
  onMarkFailed,
  onCancelPayment,
  onRetryNewReference,
  errorMessage,
}: PaymentConfirmationProps) {
  const isTerminalFailure = status === 'failed' || status === 'cancelled';
  const isConfirmed = status === 'confirmed';

  return (
    <div className="space-y-4">
      {/* Owner Verification Checklist */}
      <div className="rounded-xl border border-[#E2DAC8] bg-white p-4 space-y-2.5">
        <div className="flex items-start gap-2.5">
          <ShieldCheck className="h-4 w-4 text-[#145C3A] shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="text-xs font-semibold text-[#172B22]">
              Manual Owner Verification Required
            </p>
            <ol className="list-decimal pl-4 space-y-1 text-xs text-[#5B6B62] leading-relaxed">
              <li>Let the customer scan the QR or pay via their UPI app.</li>
              <li>
                Confirm credit of{' '}
                <span className="font-mono font-semibold text-[#172B22] tabular-nums">
                  {formatINR(amountPaise)}
                </span>{' '}
                inside your merchant app (Google Pay for Business / PhonePe / Bank SMS).
              </li>
              <li>
                Do not rely on customer screenshots alone. Click confirm only after receiving funds.
              </li>
            </ol>
          </div>
        </div>

        {/* Optional UTR / UPI Reference Input */}
        <div className="pt-2 border-t border-[#E5EAE5]">
          <label
            htmlFor="upi-utr-input"
            className="block text-xs font-medium text-[#172B22] mb-1"
          >
            UPI UTR / Bank Reference (optional)
          </label>
          <input
            id="upi-utr-input"
            type="text"
            value={utrNumber}
            disabled={isConfirmed || isConfirming}
            onChange={(e) => onUtrChange(e.target.value)}
            placeholder="e.g., 12-digit UTR from merchant alert"
            maxLength={32}
            className="w-full rounded-lg border border-[#D4DDD6] bg-white px-3 py-2 text-xs font-mono text-[#172B22] placeholder:font-sans placeholder:text-[#718078] focus:border-[#145C3A] focus:outline-none disabled:bg-[#F3F5F2] disabled:text-[#718078]"
          />
        </div>
      </div>

      {/* Demo Mode Simulation Controls */}
      <div className="rounded-xl border border-[#E2DAC8] bg-[#FAF7EF] p-3.5 space-y-2.5">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[11px] font-semibold tracking-wider text-[#9A7A3A]">
            DEMO SIMULATION CONTROLS
          </span>
          <span className="text-[11px] text-[#5B6B62]">Frontend prototype only</span>
        </div>
        <p className="text-[11px] text-[#5B6B62] leading-relaxed">
          No real bank or payment API is connected. Simulate UPI states below — balances and bills
          only update after manual owner confirmation.
        </p>

        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            disabled={isConfirmed || isConfirming}
            onClick={() => onSetStatus('initiated')}
            className={`min-h-[36px] rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors whitespace-nowrap ${
              status === 'initiated'
                ? 'border-[#145C3A] bg-[#145C3A] text-white'
                : 'border-[#D8CEB6] bg-white text-[#172B22] hover:bg-slate-50 disabled:opacity-50'
            }`}
          >
            Initiated
          </button>
          <button
            type="button"
            disabled={isConfirmed || isConfirming}
            onClick={() => onSetStatus('awaiting_verification')}
            className={`min-h-[36px] rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors whitespace-nowrap ${
              status === 'awaiting_verification'
                ? 'border-amber-700 bg-amber-700 text-white'
                : 'border-[#D8CEB6] bg-white text-[#172B22] hover:bg-slate-50 disabled:opacity-50'
            }`}
          >
            Awaiting Verification
          </button>
          <button
            type="button"
            disabled={isConfirmed || isConfirming}
            onClick={onMarkFailed}
            className={`min-h-[36px] rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors whitespace-nowrap ${
              status === 'failed'
                ? 'border-red-700 bg-red-700 text-white'
                : 'border-[#D8CEB6] bg-white text-red-700 hover:bg-red-50 disabled:opacity-50'
            }`}
          >
            Simulate Failed
          </button>
          <button
            type="button"
            disabled={isConfirmed || isConfirming}
            onClick={onCancelPayment}
            className={`min-h-[36px] rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors whitespace-nowrap ${
              status === 'cancelled'
                ? 'border-slate-700 bg-slate-700 text-white'
                : 'border-[#D8CEB6] bg-white text-slate-700 hover:bg-slate-100 disabled:opacity-50'
            }`}
          >
            Simulate Cancelled
          </button>
        </div>
      </div>

      {errorMessage && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-xs text-red-800"
        >
          <XCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Primary Action Area */}
      {isTerminalFailure ? (
        <button
          type="button"
          onClick={onRetryNewReference}
          className="min-h-[46px] w-full inline-flex items-center justify-center gap-2 rounded-lg bg-[#103D2B] px-4 py-3 text-sm font-semibold text-white hover:bg-[#145C3A] transition-colors whitespace-nowrap"
        >
          <RefreshCw className="h-4 w-4 shrink-0" />
          <span>Retry with New Transaction Reference</span>
        </button>
      ) : (
        <button
          type="button"
          disabled={!canConfirm || isConfirming || isConfirmed}
          onClick={onConfirmPayment}
          className="min-h-[46px] w-full inline-flex items-center justify-center gap-2 rounded-lg bg-[#145C3A] px-4 py-3 text-sm font-semibold text-white hover:bg-[#103D2B] disabled:bg-[#D4DDD6] disabled:text-[#718078] transition-colors"
        >
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>
            {isConfirming
              ? 'Recording Confirmed Payment...'
              : isConfirmed
                ? 'Payment Already Confirmed'
                : `Confirm ${formatINR(amountPaise)} Received (Manual)`}
          </span>
        </button>
      )}
    </div>
  );
}
