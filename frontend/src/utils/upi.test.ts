import { describe, expect, it } from 'vitest';
import {
  buildUpiPaymentUri,
  formatUpiAmount,
  generateUpiQrSvg,
  generateUpiTransactionRef,
  isValidUpiId,
} from './upi';

describe('UPI payment utilities', () => {
  it('validates standard UPI VPA formats and rejects malformed IDs', () => {
    expect(isValidUpiId('merchant.store@okaxis')).toBe(true);
    expect(isValidUpiId('lakshmi_kirana@ybl')).toBe(true);
    expect(isValidUpiId('9845022194@paytm')).toBe(true);
    expect(isValidUpiId('')).toBe(false);
    expect(isValidUpiId('missing-at-symbol')).toBe(false);
    expect(isValidUpiId('bad@')).toBe(false);
    expect(isValidUpiId('@bank')).toBe(false);
    expect(isValidUpiId('has space@oksbi')).toBe(false);
  });

  it('formats integer paise into exact 2-decimal INR amounts', () => {
    expect(formatUpiAmount(25500)).toBe('255.00');
    expect(formatUpiAmount(14550)).toBe('145.50');
    expect(formatUpiAmount(99)).toBe('0.99');
    expect(formatUpiAmount(0)).toBe('0.00');
  });

  it('builds a standard NPCI UPI URI with pa, pn, tr, tn, am, and cu=INR', () => {
    const uri = buildUpiPaymentUri({
      upiId: 'owner.configured@oksbi',
      merchantName: 'Shree Lakshmi Kirana & General Store',
      transactionRef: 'TRX-BILL-20261119-1234AB',
      transactionNote: 'Counter Bill Payment',
      amountPaise: 94550,
    });

    expect(uri.startsWith('upi://pay?')).toBe(true);
    const query = new URLSearchParams(uri.replace('upi://pay?', ''));
    expect(query.get('pa')).toBe('owner.configured@oksbi');
    expect(query.get('pn')).toBe('Shree Lakshmi Kirana & General Store');
    expect(query.get('tr')).toBe('TRX-BILL-20261119-1234AB');
    expect(query.get('tn')).toBe('Counter Bill Payment');
    expect(query.get('am')).toBe('945.50');
    expect(query.get('cu')).toBe('INR');
  });

  it('rejects URI generation when UPI ID is missing or amount is non-positive', () => {
    expect(() =>
      buildUpiPaymentUri({
        upiId: '',
        merchantName: 'Shree Lakshmi Kirana & General Store',
        transactionRef: 'TRX-BILL-1',
        transactionNote: 'Test',
        amountPaise: 10000,
      })
    ).toThrow();

    expect(() =>
      buildUpiPaymentUri({
        upiId: 'owner@okhdfcbank',
        merchantName: 'Shree Lakshmi Kirana & General Store',
        transactionRef: 'TRX-BILL-2',
        transactionNote: 'Test',
        amountPaise: 0,
      })
    ).toThrow();
  });

  it('generates distinct transaction references', () => {
    const refA = generateUpiTransactionRef('BILL');
    const refB = generateUpiTransactionRef('UDHAAR');
    expect(refA).toContain('TRX-BILL-');
    expect(refB).toContain('TRX-UDHAAR-');
    expect(refA).not.toBe(refB);
  });

  it('renders a valid SVG QR code for a UPI payment URI', async () => {
    const uri = buildUpiPaymentUri({
      upiId: 'owner@okicici',
      merchantName: 'Shree Lakshmi Kirana & General Store',
      transactionRef: 'TRX-UDHAAR-20261119-9988CD',
      transactionNote: 'Udhaar Repayment - Ramesh Sharma',
      amountPaise: 50000,
    });
    const svg = await generateUpiQrSvg(uri);
    expect(svg).toContain('<svg');
    expect(svg).toContain('</svg>');
  });

  it('updates both the UPI intent URI and generated QR code when the payment amount changes', async () => {
    const base = {
      upiId: 'owner@okaxis',
      merchantName: 'Shree Lakshmi Kirana & General Store',
      transactionRef: 'TRX-UDHAAR-20261119-DYN01',
      transactionNote: 'Udhaar Repayment - Sunita Devi Patil',
    };

    const uriFirst = buildUpiPaymentUri({ ...base, amountPaise: 20000 });
    const uriUpdated = buildUpiPaymentUri({ ...base, amountPaise: 82000 });

    expect(uriFirst).toContain('am=200.00');
    expect(uriUpdated).toContain('am=820.00');
    expect(uriFirst).not.toBe(uriUpdated);

    const [svgFirst, svgUpdated] = await Promise.all([
      generateUpiQrSvg(uriFirst),
      generateUpiQrSvg(uriUpdated),
    ]);
    expect(svgFirst).toContain('<svg');
    expect(svgUpdated).toContain('<svg');
    expect(svgFirst).not.toBe(svgUpdated);
  });
});
