import { useLedgerStore } from '../../store/useLedgerStore';
import type { Customer, CustomerPaymentEntry } from '../../types/domain';
import { formatINR } from '../../utils/money';
import {
  type ConfirmedPaymentResult,
  type PaymentAttemptResult,
  UpiPaymentModal,
} from './UpiPaymentModal';

interface UdhaarRepaymentModalProps {
  customer: Customer | null;
  initialMethod?: 'cash' | 'upi';
  onClose: () => void;
  onPaymentConfirmed: (payment: CustomerPaymentEntry) => void;
}

export function UdhaarRepaymentModal({
  customer,
  initialMethod = 'upi',
  onClose,
  onPaymentConfirmed,
}: UdhaarRepaymentModalProps) {
  const recordPartialPayment = useLedgerStore((s) => s.recordPartialPayment);
  const recordPaymentAttempt = useLedgerStore((s) => s.recordPaymentAttempt);

  if (!customer) return null;

  const handleConfirm = async (result: ConfirmedPaymentResult) => {
    const payment = await recordPartialPayment(customer.id, result.amountPaise, {
      paymentMethod: result.paymentMethod,
      transactionRef: result.transactionRef,
      utrNumber: result.utrNumber,
      upiIdUsed: result.upiIdUsed,
      status: result.status,
      isDemo: result.isDemo,
    });
    onPaymentConfirmed(payment);
  };

  const handleAttemptStatus = async (attempt: PaymentAttemptResult) => {
    if (attempt.amountPaise <= 0) return;
    await recordPaymentAttempt(customer.id, attempt.amountPaise, {
      paymentMethod: attempt.paymentMethod,
      status: attempt.status,
      transactionRef: attempt.transactionRef,
      upiIdUsed: attempt.upiIdUsed,
      isDemo: attempt.isDemo,
    });
  };

  return (
    <UpiPaymentModal
      open={Boolean(customer)}
      title="Record Udhaar Repayment"
      subtitle={`${customer.name} · ${customer.phone}`}
      amountPaise={customer.duePaise}
      editableAmount
      maxAmountPaise={customer.duePaise}
      initialPaymentMethod={initialMethod}
      allowedMethods={['upi', 'cash'] as const}
      referencePrefix="UDHAAR"
      transactionNote={`Udhaar Repayment - ${customer.name}`}
      summaryContent={
        <div className="rounded-xl border border-[#E5DEC9] bg-[#FAF7EF] p-4 flex items-center justify-between gap-4">
          <div className="min-w-0">
            <p className="text-[11px] font-medium text-[#5B6B62]">Customer Account</p>
            <p className="text-sm font-bold text-[#103D2B] truncate">{customer.name}</p>
            <p className="text-xs text-[#5B6B62] truncate">{customer.address}</p>
          </div>
          <div className="text-right shrink-0">
            <p className="text-[11px] font-medium text-[#5B6B62]">Outstanding Balance</p>
            <p className="font-mono text-lg font-bold text-amber-800 tabular-nums">
              {formatINR(customer.duePaise)}
            </p>
          </div>
        </div>
      }
      renderAmountFeedback={(enteredPaise, isValid) =>
        isValid ? (
          <p className="text-xs text-[#5B6B62]">
            Balance after confirmation:{' '}
            <span className="font-mono font-semibold text-[#145C3A] tabular-nums">
              {formatINR(Math.max(0, customer.duePaise - enteredPaise))}
            </span>
            {customer.duePaise - enteredPaise === 0 ? ' · Account will be fully settled' : ''}
          </p>
        ) : (
          <p className="text-xs text-amber-700">
            Enter an amount between ₹1 and {formatINR(customer.duePaise)}.
          </p>
        )
      }
      onClose={onClose}
      onConfirmPayment={handleConfirm}
      onPaymentAttemptStatus={handleAttemptStatus}
    />
  );
}
