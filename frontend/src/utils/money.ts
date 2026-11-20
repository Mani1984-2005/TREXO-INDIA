import { DEADSTOCK_DAYS, NEAR_EXPIRY_DAYS } from '../config';
import type { Product } from '../types/domain';

/**
 * Converts rupees input (number) safely to integer paise.
 */
export function rupeesToPaise(rupees: number): number {
  if (!Number.isFinite(rupees)) return 0;
  return Math.round(rupees * 100);
}

/**
 * Formats integer paise in Indian rupee notation (e.g., ₹12,450 or ₹12,450.50).
 */
export function formatINR(paise: number, showZeroPaise = false): string {
  const safe = Number.isFinite(paise) ? Math.round(paise) : 0;
  const isNegative = safe < 0;
  const absPaise = Math.abs(safe);
  const rupees = Math.floor(absPaise / 100);
  const remPaise = absPaise % 100;

  const formattedRupees = new Intl.NumberFormat('en-IN').format(rupees);
  const decimalPart =
    remPaise > 0 || showZeroPaise ? `.${String(remPaise).padStart(2, '0')}` : '';

  return `${isNegative ? '-' : ''}₹${formattedRupees}${decimalPart}`;
}

/**
 * Returns the active counter price in paise (counter discount if active, otherwise selling price).
 */
export function getEffectivePricePaise(product: Pick<Product, 'sellingPricePaise' | 'counterDiscountPricePaise'>): number {
  if (
    product.counterDiscountPricePaise !== null &&
    product.counterDiscountPricePaise >= 0 &&
    product.counterDiscountPricePaise < product.sellingPricePaise
  ) {
    return product.counterDiscountPricePaise;
  }
  return product.sellingPricePaise;
}

/**
 * Computes discount percentage between original and discounted price.
 */
export function getDiscountPercent(originalPaise: number, discountedPaise: number): number {
  if (originalPaise <= 0 || discountedPaise >= originalPaise) return 0;
  return Math.round(((originalPaise - discountedPaise) / originalPaise) * 100);
}

/**
 * Calculates integer line total in paise.
 */
export function calculateLineTotalPaise(unitPricePaise: number, qty: number): number {
  if (!Number.isFinite(unitPricePaise) || !Number.isFinite(qty) || qty <= 0) return 0;
  return Math.round(unitPricePaise) * Math.round(qty);
}

export interface CartCalculationLine {
  unitPricePaise: number;
  originalPricePaise: number;
  qty: number;
}

export interface CartTotals {
  subtotalPaise: number;
  discountSavedPaise: number;
  totalPaise: number;
  itemCount: number;
}

/**
 * Computes exact cart totals in integer paise.
 */
export function calculateCartTotals(lines: CartCalculationLine[]): CartTotals {
  let subtotalPaise = 0;
  let totalPaise = 0;
  let itemCount = 0;

  for (const line of lines) {
    const qty = Math.max(0, Math.round(line.qty));
    if (qty === 0) continue;
    const orig = Math.max(0, Math.round(line.originalPricePaise));
    const eff = Math.max(0, Math.round(line.unitPricePaise));
    subtotalPaise += orig * qty;
    totalPaise += eff * qty;
    itemCount += qty;
  }

  return {
    subtotalPaise,
    discountSavedPaise: Math.max(0, subtotalPaise - totalPaise),
    totalPaise,
    itemCount,
  };
}

/**
 * Days elapsed since a given ISO date string.
 */
export function daysSince(isoDate: string, now: Date = new Date()): number {
  const then = new Date(isoDate);
  if (Number.isNaN(then.getTime())) return 0;
  const diffMs = now.getTime() - then.getTime();
  return Math.max(0, Math.floor(diffMs / (1000 * 60 * 60 * 24)));
}

/**
 * Days remaining until an expiry ISO date string (negative if expired).
 */
export function daysUntil(isoDate: string | null, now: Date = new Date()): number | null {
  if (!isoDate) return null;
  const target = new Date(isoDate);
  if (Number.isNaN(target.getTime())) return null;
  const diffMs = target.getTime() - now.getTime();
  return Math.ceil(diffMs / (1000 * 60 * 60 * 24));
}

export function isDeadStock(product: Product, now: Date = new Date()): boolean {
  if (product.stockQty <= 0) return false;
  return daysSince(product.lastSoldAt, now) >= DEADSTOCK_DAYS;
}

export function isNearExpiry(product: Product, now: Date = new Date()): boolean {
  if (product.stockQty <= 0 || !product.expiryDate) return false;
  const left = daysUntil(product.expiryDate, now);
  return left !== null && left <= NEAR_EXPIRY_DAYS;
}

export function isStockoutFastMover(product: Product): boolean {
  return !product.stopReordering && product.stockQty === 0 && product.avgDailySales >= 2;
}

export function isLowStock(product: Product): boolean {
  return !product.stopReordering && product.stockQty <= product.reorderLevel;
}

/**
 * Cash trapped in dead stock = stockQty * costPaise for items idle >= DEADSTOCK_DAYS or near expiry.
 */
export function calculateTrappedCashPaise(products: Product[], now: Date = new Date()): number {
  return products.reduce((sum, p) => {
    if (p.stockQty > 0 && (isDeadStock(p, now) || isNearExpiry(p, now))) {
      return sum + p.stockQty * p.costPaise;
    }
    return sum;
  }, 0);
}

/**
 * Seeded estimate of 7-day sales lost to stockouts on fast movers.
 */
export function calculateEstimatedLostSalesPaise(products: Product[]): number {
  return products.reduce((sum, p) => {
    if (isStockoutFastMover(p)) {
      const estSevenDayUnits = Math.round(p.avgDailySales * 7);
      return sum + estSevenDayUnits * p.sellingPricePaise;
    }
    return sum;
  }, 0);
}

/**
 * Checks whether an ISO timestamp falls on the same local calendar day as `referenceDate`.
 * Prevents UTC-vs-IST midnight date drift in Indian retail reports.
 */
export function isSameLocalDay(isoDate: string, referenceDate: Date = new Date()): boolean {
  const date = new Date(isoDate);
  if (Number.isNaN(date.getTime())) return false;
  return (
    date.getFullYear() === referenceDate.getFullYear() &&
    date.getMonth() === referenceDate.getMonth() &&
    date.getDate() === referenceDate.getDate()
  );
}

/**
 * Checks whether an ISO timestamp falls within the trailing `days` local days (inclusive of today).
 */
export function isWithinLocalDays(
  isoDate: string,
  days: number,
  referenceDate: Date = new Date()
): boolean {
  const date = new Date(isoDate);
  if (Number.isNaN(date.getTime()) || days <= 0) return false;
  const startOfWindow = new Date(
    referenceDate.getFullYear(),
    referenceDate.getMonth(),
    referenceDate.getDate() - (days - 1),
    0,
    0,
    0,
    0
  );
  const endOfToday = new Date(
    referenceDate.getFullYear(),
    referenceDate.getMonth(),
    referenceDate.getDate(),
    23,
    59,
    59,
    999
  );
  return date.getTime() >= startOfWindow.getTime() && date.getTime() <= endOfToday.getTime();
}
