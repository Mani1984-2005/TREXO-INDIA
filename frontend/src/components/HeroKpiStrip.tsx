import { AlertTriangle, ArrowRight, Coins, IndianRupee, Wallet } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { TRANSLATIONS } from '../i18n/translations';
import { useLedgerStore } from '../store/useLedgerStore';
import {
  calculateEstimatedLostSalesPaise,
  calculateTrappedCashPaise,
  formatINR,
  isDeadStock,
  isNearExpiry,
  isStockoutFastMover,
} from '../utils/money';
import { KpiCell, KpiStrip } from './ui/DesignSystem';

export function HeroKpiStrip() {
  const navigate = useNavigate();
  const products = useLedgerStore((s) => s.products);
  const salesSummary = useLedgerStore((s) => s.salesSummary);
  const language = useLedgerStore((s) => s.language);
  const t = TRANSLATIONS[language];

  const trappedCashPaise = calculateTrappedCashPaise(products);
  const deadOrExpiryCount = products.filter((p) => isDeadStock(p) || isNearExpiry(p)).length;
  const lostSalesPaise = calculateEstimatedLostSalesPaise(products);
  const stockoutCount = products.filter((p) => isStockoutFastMover(p)).length;

  const todaySalesPaise = salesSummary?.todayRevenuePaise ?? 0;
  const todayBills = salesSummary?.todayBillsCount ?? 0;
  const rescuedCashPaise = salesSummary?.totalRescuedCashPaise ?? 0;

  return (
    <KpiStrip columns={4} ariaLabel="Store cash health summary" className="no-print">
      <KpiCell
        label={t.cashTrappedLabel}
        value={formatINR(trappedCashPaise)}
        icon={<Coins className="h-3.5 w-3.5" />}
        tone={trappedCashPaise > 0 ? 'crimson' : 'emerald'}
        caption={`${deadOrExpiryCount} ${deadOrExpiryCount === 1 ? 'item' : 'items'} idle or expiring`}
        action={
          <button
            type="button"
            onClick={() => navigate('/rescue')}
            className="inline-flex items-center gap-1 font-semibold text-[#145C3A] hover:text-[#103D2B] whitespace-nowrap transition-colors"
          >
            <span>Rescue</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        }
      />

      <KpiCell
        label={t.lostSalesLabel}
        value={formatINR(lostSalesPaise)}
        icon={<AlertTriangle className="h-3.5 w-3.5" />}
        tone={lostSalesPaise > 0 ? 'amber' : 'default'}
        caption={`${stockoutCount} fast movers out · Estimate`}
        action={
          <button
            type="button"
            onClick={() => navigate('/restock')}
            className="inline-flex items-center gap-1 font-semibold text-[#145C3A] hover:text-[#103D2B] whitespace-nowrap transition-colors"
          >
            <span>Restock</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        }
      />

      <KpiCell
        label={t.todaySalesLabel}
        value={formatINR(todaySalesPaise)}
        icon={<IndianRupee className="h-3.5 w-3.5" />}
        tone="default"
        caption={`${todayBills} ${todayBills === 1 ? 'bill' : 'bills'} completed today`}
      />

      <KpiCell
        label={t.cashRescuedLabel}
        value={formatINR(rescuedCashPaise)}
        icon={<Wallet className="h-3.5 w-3.5" />}
        tone="emerald"
        caption="Unlocked at counter from slow stock"
      />
    </KpiStrip>
  );
}
