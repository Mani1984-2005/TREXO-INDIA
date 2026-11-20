/**
 * TEMPORARY PROTOTYPE AUTHENTICATION MODULE
 *
 * SECURITY NOTICE:
 * - This module provides a temporary frontend-only prototype login gate for local demo use.
 * - Frontend-only password checks DO NOT provide genuine security and MUST be replaced
 *   before any production deployment.
 * - Do NOT hardcode real production credentials in client-side code.
 *
 * PLANNED PRODUCTION ARCHITECTURE:
 * - Server-side password verification endpoint over HTTPS
 * - Password hashing with Argon2id or bcrypt on the backend
 * - Secure, HttpOnly, SameSite session cookies with expiration
 * - Login rate limiting and brute-force lockout protection
 * - Server-side route & API authorization checks and explicit server logout
 */

const SESSION_KEY = 'trexo_owner_session_v1';

// TEMPORARY DEVELOPMENT PASSWORD — MUST BE REPLACED WITH BACKEND AUTH BEFORE DEPLOYMENT
const DEV_PROTOTYPE_PASSCODE = '123456789';

export interface AuthResult {
  ok: boolean;
  errorCode?: 'empty' | 'invalid';
}

function getStorage(): Storage | null {
  try {
    if (typeof window !== 'undefined' && window.sessionStorage) {
      return window.sessionStorage;
    }
  } catch {
    // Ignore storage restriction errors in sandboxed iframes
  }
  return null;
}

export const authService = {
  isAuthenticated(): boolean {
    const storage = getStorage();
    if (!storage) return false;
    return storage.getItem(SESSION_KEY) === 'authenticated';
  },

  async verifyOwnerPassword(password: string, delayMs = 280): Promise<AuthResult> {
    const trimmed = password.trim();
    if (!trimmed) {
      return { ok: false, errorCode: 'empty' };
    }

    if (delayMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }

    if (password === DEV_PROTOTYPE_PASSCODE) {
      const storage = getStorage();
      if (storage) {
        storage.setItem(SESSION_KEY, 'authenticated');
      }
      return { ok: true };
    }

    return { ok: false, errorCode: 'invalid' };
  },

  logout(): void {
    const storage = getStorage();
    if (storage) {
      storage.removeItem(SESSION_KEY);
    }
  },
};
