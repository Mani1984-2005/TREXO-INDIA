import type { ReactNode } from 'react';

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}

export function PageHeader({ eyebrow, title, description, actions }: PageHeaderProps) {
  return (
    <div className="no-print flex flex-col sm:flex-row sm:items-end justify-between gap-4">
      <div className="min-w-0 space-y-1">
        {eyebrow && (
          <p className="text-xs font-medium text-[#718078] tracking-tight">{eyebrow}</p>
        )}
        <h2 className="text-2xl sm:text-[26px] font-bold tracking-[-0.02em] text-[#172B22] leading-tight text-balance">
          {title}
        </h2>
        {description && (
          <p className="text-xs sm:text-sm text-[#5F7068] max-w-2xl leading-relaxed">
            {description}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex flex-wrap items-center gap-2.5 shrink-0">{actions}</div>
      )}
    </div>
  );
}

interface SectionCardProps {
  children: ReactNode;
  variant?: 'default' | 'warm';
  className?: string;
}

export function SectionCard({
  children,
  variant = 'default',
  className = '',
}: SectionCardProps) {
  const surfaceClass =
    variant === 'warm'
      ? 'border-[#E4DCC6] bg-[#FAF7EF] shadow-[0_1px_2px_rgba(16,61,43,0.03)]'
      : 'border-[#E5EAE5] bg-white shadow-[0_1px_2px_rgba(16,61,43,0.04)]';

  return (
    <section className={`rounded-xl border overflow-hidden ${surfaceClass} ${className}`}>
      {children}
    </section>
  );
}

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  icon?: ReactNode;
  warm?: boolean;
}

export function SectionHeader({
  title,
  subtitle,
  action,
  icon,
  warm = false,
}: SectionHeaderProps) {
  return (
    <div
      className={`border-b px-5 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
        warm ? 'border-[#E4DCC6]' : 'border-[#E5EAE5]'
      }`}
    >
      <div className="flex items-start gap-2.5 min-w-0">
        {icon && (
          <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#F3F5F2] text-[#145C3A]">
            {icon}
          </span>
        )}
        <div className="min-w-0">
          <h3 className="text-sm font-semibold tracking-[-0.01em] text-[#172B22]">{title}</h3>
          {subtitle && (
            <p className="mt-0.5 text-xs text-[#65766D] leading-relaxed">{subtitle}</p>
          )}
        </div>
      </div>
      {action && <div className="flex items-center gap-2 shrink-0">{action}</div>}
    </div>
  );
}

interface SegmentedTabsProps<T extends string> {
  value: T;
  onChange: (next: T) => void;
  options: { id: T; label: string }[];
  ariaLabel: string;
}

export function SegmentedTabs<T extends string>({
  value,
  onChange,
  options,
  ariaLabel,
}: SegmentedTabsProps<T>) {
  return (
    <div
      className="inline-flex items-center gap-1 rounded-lg border border-[#E5EAE5] bg-[#F3F5F2] p-1 overflow-x-auto max-w-full trexo-scroll"
      role="tablist"
      aria-label={ariaLabel}
    >
      {options.map((opt) => {
        const active = value === opt.id;
        return (
          <button
            key={opt.id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(opt.id)}
            className={`min-h-[34px] rounded-md px-3 py-1.5 text-xs font-medium transition-all duration-150 whitespace-nowrap shrink-0 ${
              active
                ? 'bg-white text-[#103D2B] font-semibold shadow-[0_1px_2px_rgba(16,61,43,0.08)]'
                : 'text-[#65766D] hover:text-[#172B22]'
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

interface KpiCellProps {
  label: string;
  value: string;
  caption: string;
  icon?: ReactNode;
  tone?: 'default' | 'emerald' | 'amber' | 'crimson';
  action?: ReactNode;
  className?: string;
}

export function KpiCell({
  label,
  value,
  caption,
  icon,
  tone = 'default',
  action,
  className = '',
}: KpiCellProps) {
  const valueTone =
    tone === 'emerald'
      ? 'text-[#145C3A]'
      : tone === 'amber'
        ? 'text-amber-700'
        : tone === 'crimson'
          ? 'text-red-700'
          : 'text-[#172B22]';

  const iconTone =
    tone === 'emerald'
      ? 'bg-[#145C3A]/10 text-[#145C3A]'
      : tone === 'amber'
        ? 'bg-amber-50 text-amber-700'
        : tone === 'crimson'
          ? 'bg-red-50 text-red-700'
          : 'bg-[#F3F5F2] text-[#145C3A]';

  return (
    <div
      className={`bg-white p-5 flex flex-col justify-between gap-3 transition-colors duration-150 hover:bg-[#FAF7EF]/45 ${className}`}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-[#65766D] truncate">{label}</p>
        {icon && (
          <span
            className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${iconTone}`}
            aria-hidden="true"
          >
            {icon}
          </span>
        )}
      </div>
      <p
        className={`font-mono text-[22px] sm:text-2xl font-bold tracking-[-0.02em] tabular-nums leading-none ${valueTone}`}
      >
        {value}
      </p>
      <div className="flex items-center justify-between gap-2 text-xs text-[#65766D] min-w-0">
        <span className="truncate">{caption}</span>
        {action && <span className="shrink-0">{action}</span>}
      </div>
    </div>
  );
}

interface KpiStripProps {
  children: ReactNode;
  columns?: 3 | 4 | 5 | 6;
  ariaLabel?: string;
  className?: string;
}

export function KpiStrip({
  children,
  columns = 4,
  ariaLabel,
  className = '',
}: KpiStripProps) {
  const gridCols =
    columns === 6
      ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3'
      : columns === 5
        ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-5'
        : columns === 3
          ? 'grid-cols-1 sm:grid-cols-3'
          : 'grid-cols-1 sm:grid-cols-2 xl:grid-cols-4';

  return (
    <section
      aria-label={ariaLabel}
      className={`grid ${gridCols} gap-px rounded-xl border border-[#E5EAE5] bg-[#E5EAE5] shadow-[0_1px_2px_rgba(16,61,43,0.04)] overflow-hidden ${className}`}
    >
      {children}
    </section>
  );
}

interface StatusTextProps {
  label: string;
  tone: 'emerald' | 'amber' | 'crimson' | 'muted';
  icon?: ReactNode;
  className?: string;
}

export function StatusText({ label, tone, icon, className = '' }: StatusTextProps) {
  const colorClass =
    tone === 'emerald'
      ? 'text-[#145C3A]'
      : tone === 'amber'
        ? 'text-amber-700'
        : tone === 'crimson'
          ? 'text-red-700'
          : 'text-[#65766D]';

  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-semibold ${colorClass} ${className}`}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      <span>{label}</span>
    </span>
  );
}

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className = '',
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center px-6 py-12 ${className}`}
    >
      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#F3F5F2] text-[#145C3A]">
        {icon}
      </div>
      <p className="mt-3.5 text-sm font-semibold text-[#172B22]">{title}</p>
      <p className="mt-1 text-xs text-[#65766D] max-w-sm leading-relaxed">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
