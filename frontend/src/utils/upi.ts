import QRCode from 'qrcode';
import { STORAGE_KEYS, STORE_INFO, UPI_CONFIG_DEFAULTS } from '../config';
import type { UpiMerchantConfig, UpiPaymentStatus } from '../types/domain';

export interface UpiPaymentUriParams {
  /** Payee VPA / Store UPI ID (pa) */
  upiId: string;
  /** Payee Name / Store Name (pn) */
  merchantName: string;
  /** Unique Transaction Reference (tr) */
  transactionRef: string;
  /** Transaction Note / Payment Description (tn) */
  transactionNote: string;
  /** Exact amount in integer paise -> formatted as INR decimals (am) */
  amountPaise: number;
}

export interface SupportedUpiApp {
  id: 'gpay' | 'phonepe' | 'paytm' | 'bhim' | 'other';
  name: string;
  shortLabel: string;
  featured?: boolean;
}

export const SUPPORTED_UPI_APPS: SupportedUpiApp[] = [
  { id: 'gpay', name: 'Google Pay', shortLabel: 'GPay', featured: true },
  { id: 'phonepe', name: 'PhonePe', shortLabel: 'PhonePe' },
  { id: 'paytm', name: 'Paytm', shortLabel: 'Paytm' },
  { id: 'bhim', name: 'BHIM', shortLabel: 'BHIM' },
  { id: 'other', name: 'Any UPI App', shortLabel: 'UPI' },
];

export const UPI_STATUS_LABELS: Record<UpiPaymentStatus, string> = {
  initiated: 'Payment Initiated',
  awaiting_verification: 'Awaiting Verification',
  confirmed: 'Payment Confirmed',
  failed: 'Payment Failed',
  cancelled: 'Payment Cancelled',
};

/**
 * Validates standard NPCI UPI VPA syntax (e.g., handle@bank).
 * Does not verify live merchant ownership (requires a secure payment backend in production).
 */
export function isValidUpiId(raw: string): boolean {
  const trimmed = raw.trim();
  if (!trimmed || trimmed.length < 5 || trimmed.length > 100) return false;
  return /^[a-zA-Z0-9._-]{2,64}@[a-zA-Z][a-zA-Z0-9]{1,32}$/.test(trimmed);
}

/**
 * Formats integer paise into a standard 2-decimal INR string for UPI `am` parameter.
 */
export function formatUpiAmount(amountPaise: number): string {
  const safePaise = Math.max(0, Math.round(Number.isFinite(amountPaise) ? amountPaise : 0));
  return (safePaise / 100).toFixed(2);
}

/**
 * Generates a unique, human-readable transaction reference for a counter bill or Udhaar repayment.
 */
export function generateUpiTransactionRef(context: 'BILL' | 'UDHAAR' | 'CASH'): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  const timePart = String(now.getTime()).slice(-4);
  const rand = Math.random().toString(36).slice(2, 6).toUpperCase();
  return `TRX-${context}-${y}${m}${d}-${timePart}${rand}`;
}

/**
 * Builds an NPCI-compliant UPI payment URI with pa, pn, tr, tn, am, and cu=INR.
 * Throws if upiId is invalid or amountPaise <= 0 so invalid QRs are never generated.
 */
export function buildUpiPaymentUri(params: UpiPaymentUriParams): string {
  const pa = params.upiId.trim();
  if (!isValidUpiId(pa)) {
    throw new Error('A valid Store UPI ID is required before generating a UPI payment URI.');
  }
  const safePaise = Math.round(params.amountPaise);
  if (!Number.isFinite(safePaise) || safePaise <= 0) {
    throw new Error('Payment amount must be greater than ₹0.');
  }

  const pn = (params.merchantName.trim() || STORE_INFO.shopName).slice(0, 80);
  const tr = params.transactionRef.trim().replace(/[^a-zA-Z0-9._-]/g, '').slice(0, 35);
  const tn = params.transactionNote.trim().slice(0, 80);
  const am = formatUpiAmount(safePaise);

  // Preserve '@' in pa for maximum compatibility across Indian UPI apps (GPay, PhonePe, Paytm, BHIM)
  const encodedPa = encodeURIComponent(pa).replace(/%40/g, '@');
  const queryParts = [
    `pa=${encodedPa}`,
    `pn=${encodeURIComponent(pn)}`,
    `tr=${encodeURIComponent(tr)}`,
    `tn=${encodeURIComponent(tn)}`,
    `am=${encodeURIComponent(am)}`,
    `cu=INR`,
  ];

  return `upi://pay?${queryParts.join('&')}`;
}

/**
 * Generates an inline SVG QR code for a given UPI payment URI.
 */
export async function generateUpiQrSvg(upiUri: string): Promise<string> {
  return QRCode.toString(upiUri, {
    type: 'svg',
    errorCorrectionLevel: 'M',
    margin: 2,
    color: {
      dark: '#103D2B',
      light: '#FFFFFF',
    },
  });
}

/**
 * Loads the store owner's configured UPI ID from localStorage.
 * Returns an empty upiId by default — never invents a merchant UPI ID.
 */
export function loadUpiMerchantConfig(): UpiMerchantConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.UPI_CONFIG_V1);
    if (!raw) {
      return {
        upiId: UPI_CONFIG_DEFAULTS.upiId,
        merchantName: UPI_CONFIG_DEFAULTS.merchantName,
        updatedAt: null,
      };
    }
    const parsed = JSON.parse(raw) as Partial<UpiMerchantConfig>;
    return {
      upiId: typeof parsed.upiId === 'string' ? parsed.upiId.trim() : '',
      merchantName:
        typeof parsed.merchantName === 'string' && parsed.merchantName.trim()
          ? parsed.merchantName.trim()
          : STORE_INFO.shopName,
      updatedAt: typeof parsed.updatedAt === 'string' ? parsed.updatedAt : null,
    };
  } catch {
    return {
      upiId: UPI_CONFIG_DEFAULTS.upiId,
      merchantName: UPI_CONFIG_DEFAULTS.merchantName,
      updatedAt: null,
    };
  }
}

/**
 * Persists the store owner's UPI configuration to localStorage.
 */
export function saveUpiMerchantConfig(config: UpiMerchantConfig): UpiMerchantConfig {
  const sanitized: UpiMerchantConfig = {
    upiId: config.upiId.trim(),
    merchantName: config.merchantName.trim() || STORE_INFO.shopName,
    updatedAt: new Date().toISOString(),
  };
  try {
    localStorage.setItem(STORAGE_KEYS.UPI_CONFIG_V1, JSON.stringify(sanitized));
  } catch {
    // Ignore storage quota errors
  }
  return sanitized;
}
