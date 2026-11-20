import { Banknote, BookOpen, QrCode } from 'lucide-react';
import type { PaymentMethod } from '../../types/domain';

interface PaymentMethodSelectorProps<T extends PaymentMethod = PaymentMethod> {
  value: T;
  onChange: (method: T) => void;
  options: readonly T[];
  label?: string;
  showUpiAppsHint?: boolean;
}

const MODE_META: Record<
  PaymentMethod,
  { label: string; icon: typeof Banknote; subLabel: string }
> = {
  cash: { label: 'Cash', icon: Banknote, subLabel: 'Counter cash' },
  upi: { label: 'UPI', icon: QrCode, subLabel: 'GPay · PhonePe · Paytm' },
  udhaar: { label: 'Udhaar', icon: BookOpen, subLabel: 'Customer credit' },
};

export function PaymentMethodSelector<T extends PaymentMethod = PaymentMethod>({
  value,
  onChange,
  options,
  label = 'Payment Method',
  showUpiAppsHint = true,
}: PaymentMethodSelectorProps<T>) {
  const gridCols = options.length === 2 ? 'grid-cols-2' : 'grid-cols-3';

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-[#5B6B62]">{label}</p>
        {showUpiAppsHint && value === 'upi' && (
          <span className="text-[11px] text-[#145C3A] font-medium truncate">
            GPay · PhonePe · Paytm · BHIM
          </span>
        )}
      </div>

      <div
        className={`grid ${gridCols} gap-1.5 rounded-lg border border-[#E5E0D3] bg-[#FAF7EF] p-1`}
        role="radiogroup"
        aria-label={label}
      >
        {options.map((mode) => {
          const meta = MODE_META[mode];
          const Icon = meta.icon;
          const isSelected = value === mode;

          return (
            <button
              key={mode}
              type="button"
              role="radio"
              aria-checked={isSelected}
              onClick={() => onChange(mode)}
              className={`min-h-[42px] inline-flex items-center justify-center gap-1.5 rounded-md px-3 py-2 text-xs font-semibold transition-colors whitespace-nowrap ${
                isSelected
                  ? 'bg-[#145C3A] text-white shadow-xs'
                  : 'text-[#172B22] hover:bg-white/80'
              }`}
            >
              <Icon className="h-3.5 w-3.5 shrink-0" />
              <span>{meta.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
