export const DEADSTOCK_DAYS = 30;
export const NEAR_EXPIRY_DAYS = 14;
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';

/** Base URL of the FastAPI backend (no trailing slash). */
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1').replace(
  /\/+$/,
  ''
);

export const STORE_INFO = {
  shopName: 'Shree Lakshmi Kirana & General Store',
  ownerName: 'Mahesh Kulkarni',
  location: 'Hubballi Main Bazaar, Karnataka',
  phone: '+91 98450 22194',
  gstin: '29AABCS1429B1Z5',
};

export const STORAGE_KEYS = {
  STATE_V1: 'trexo_ledger_state_v1',
  UPI_CONFIG_V1: 'trexo_upi_config_v1',
};

/**
 * Store UPI Configuration Defaults.
 *
 * IMPORTANT: Do NOT hardcode or invent a real merchant UPI ID in source code.
 * The store owner enters their actual UPI ID (VPA) at runtime through the
 * Store UPI Settings screen, which persists locally in browser storage.
 */
export const UPI_CONFIG_DEFAULTS = {
  /** Leave blank until the store owner configures their actual UPI ID (e.g., yourstore@bank). */
  upiId: '',
  merchantName: STORE_INFO.shopName,
  currency: 'INR' as const,
};

