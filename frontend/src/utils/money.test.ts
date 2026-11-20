import { describe, expect, it } from 'vitest';
import {
  calculateCartTotals,
  calculateLineTotalPaise,
  formatINR,
  getDiscountPercent,
  getEffectivePricePaise,
  isSameLocalDay,
  isWithinLocalDays,
  rupeesToPaise,
} from './money';

describe('paise & cart math', () => {
  it('converts rupees to exact integer paise', () => {
    expect(rupeesToPaise(19.99)).toBe(1999);
    expect(rupeesToPaise(250)).toBe(25000);
    expect(rupeesToPaise(0.1 + 0.2)).toBe(30);
  });

  it('formats Indian rupees with lakh/thousand grouping', () => {
    expect(formatINR(1245000)).toBe('₹12,450');
    expect(formatINR(1245050)).toBe('₹12,450.50');
    expect(formatINR(10000000)).toBe('₹1,00,000');
  });

  it('computes line totals and counter discounts accurately', () => {
    expect(calculateLineTotalPaise(4550, 3)).toBe(13650);
    expect(getEffectivePricePaise({ sellingPricePaise: 50000, counterDiscountPricePaise: 40000 })).toBe(40000);
    expect(getEffectivePricePaise({ sellingPricePaise: 50000, counterDiscountPricePaise: null })).toBe(50000);
    expect(getDiscountPercent(50000, 40000)).toBe(20);
  });

  it('calculates cart totals and savings in paise without drift', () => {
    const totals = calculateCartTotals([
      { originalPricePaise: 52000, unitPricePaise: 41600, qty: 2 },
      { originalPricePaise: 2800, unitPricePaise: 2800, qty: 3 },
    ]);
    expect(totals.subtotalPaise).toBe(112400);
    expect(totals.totalPaise).toBe(91600);
    expect(totals.discountSavedPaise).toBe(20800);
    expect(totals.itemCount).toBe(5);
  });

  it('filters local calendar days and trailing day windows accurately', () => {
    const ref = new Date(2026, 10, 19, 14, 30, 0); // Nov 19, 2026 14:30 local
    const sameDayEarly = new Date(2026, 10, 19, 0, 15, 0).toISOString();
    const yesterdayLate = new Date(2026, 10, 18, 23, 45, 0).toISOString();
    const sixDaysAgo = new Date(2026, 10, 13, 12, 0, 0).toISOString();
    const tenDaysAgo = new Date(2026, 10, 9, 12, 0, 0).toISOString();

    expect(isSameLocalDay(sameDayEarly, ref)).toBe(true);
    expect(isSameLocalDay(yesterdayLate, ref)).toBe(false);
    expect(isSameLocalDay('invalid-date', ref)).toBe(false);

    expect(isWithinLocalDays(sameDayEarly, 7, ref)).toBe(true);
    expect(isWithinLocalDays(sixDaysAgo, 7, ref)).toBe(true);
    expect(isWithinLocalDays(tenDaysAgo, 7, ref)).toBe(false);
    expect(isWithinLocalDays(tenDaysAgo, 30, ref)).toBe(true);
  });
});

