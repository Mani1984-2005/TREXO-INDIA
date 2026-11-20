import {
  AlertCircle,
  Ban,
  CheckCircle2,
  Clock,
  ShieldAlert,
} from 'lucide-react';
import type { UpiPaymentStatus } from '../../types/domain';
import { UPI_STATUS_LABELS } from '../../utils/upi';

interface PaymentStatusIndicatorProps {
  status: UpiPaymentStatus;
  isDemo?: boolean;
  compact?: boolean;
}

const STATUS_CONFIG: Record<
  UpiPaymentStatus,
  {
    icon: typeof Clock;
    textClass: string;
    surfaceClass: string;
    borderClass: string;
    helper: string;
  }
> = {
  initiated: {
    icon: Clock,
    textClass: 'text-[#103D2B]',
    surfaceClass: 'bg-[#FAF7EF]',
    borderClass: 'border-[#E2DAC8]',
    helper: 'QR code ready. Ask customer to scan or open their UPI app.',
  },
  awaiting_verification: {
    icon: ShieldAlert,
    textClass: 'text-amber-800',
    surfaceClass: 'bg-amber-50/70',
    borderClass: 'border-amber-200',
    helper: 'Verify incoming credit in your merchant UPI app or bank SMS before confirming.',
  },
  confirmed: {
    icon: CheckCircle2,
    textClass: 'text-[#145C3A]',
    surfaceClass: 'bg-emerald-50/70',
    borderClass: 'border-emerald-200',
    helper: 'Manually verified and confirmed by store owner.',
  },
  failed: {
    icon: AlertCircle,
    textClass: 'text-red-700',
    surfaceClass: 'bg-red-50/70',
    borderClass: 'border-red-200',
    helper: 'Payment marked failed. No bill or balance was updated.',
  },
  cancelled: {
    icon: Ban,
    textClass: 'text-slate-700',
    surfaceClass: 'bg-slate-100/80',
    borderClass: 'border-slate-200',
    helper: 'Payment cancelled by owner. Generate a new reference to retry.',
  },
};

export function PaymentStatusIndicator({
  status,
  isDemo = true,
  compact = false,
}: PaymentStatusIndicatorProps) {
  const cfg = STATUS_CONFIG[status];
  const Icon = cfg.icon;
  const label = UPI_STATUS_LABELS[status];

  if (compact) {
    return (
      <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${cfg.textClass}`}>
        <Icon className="h-3.5 w-3.5 shrink-0" />
        <span>{label}</span>
        {isDemo && (
          <span className="font-mono text-[10px] tracking-wide text-[#718078]">· DEMO</span>
        )}
      </span>
    );
  }

  return (
    <div
      className={`rounded-xl border ${cfg.borderClass} ${cfg.surfaceClass} px-4 py-3`}
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center justify-between gap-2">
        <div className={`flex items-center gap-2 text-sm font-semibold ${cfg.textClass}`}>
          <Icon className="h-4 w-4 shrink-0" />
          <span>{label}</span>
        </div>
        {isDemo && (
          <span className="font-mono text-[11px] font-semibold tracking-wider text-[#9A7A3A]">
            DEMO MODE
          </span>
        )}
      </div>
      <p className="mt-1 text-xs text-[#5B6B62] leading-relaxed">{cfg.helper}</p>
    </div>
  );
}
