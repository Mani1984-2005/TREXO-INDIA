/**
 * Owner authentication.
 *
 * Two modes, selected by ``VITE_USE_MOCK``:
 *
 * - Mock mode (default) keeps the original client-side prototype gate for
 *   offline demos.  It is explicit that it is not real security.
 * - API mode (``VITE_USE_MOCK=false``) posts the passcode to the FastAPI
 *   backend and stores the returned HMAC bearer token in sessionStorage.  The
 *   passcode itself is never stored in the browser.
 */
import { API_BASE_URL, USE_MOCK } from '../config';
import { ApiClientError, getToken, setToken } from './apiClient';

const SESSION_KEY = 'trexo_owner_session_v1';

// TEMPORARY PROTOTYPE PASSWORD — only used when VITE_USE_MOCK is not "false".
const DEV_PROTOTYPE_PASSCODE = '123456789';

export interface AuthResult {
  ok: boolean;
  errorCode?: 'empty' | 'invalid' | 'network';
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

/** Read the ``exp`` claim without verifying it (the server is authoritative). */
function tokenIsFresh(token: string): boolean {
  try {
    const body = token.split('.', 1)[0];
    const padded = body.replace(/-/g, '+').replace(/_/g, '/');
    const payload = JSON.parse(atob(padded + '='.repeat((4 - (padded.length % 4)) % 4))) as {
      exp?: number;
    };
    return typeof payload.exp === 'number' ? payload.exp * 1000 > Date.now() : true;
  } catch {
    return false;
  }
}

export const authService = {
  isAuthenticated(): boolean {
    if (USE_MOCK) {
      const storage = getStorage();
      return storage?.getItem(SESSION_KEY) === 'authenticated';
    }
    const token = getToken();
    if (!token || !tokenIsFresh(token)) {
      setToken(null);
      return false;
    }
    return true;
  },

  async verifyOwnerPassword(password: string, delayMs = 280): Promise<AuthResult> {
    const trimmed = password.trim();
    if (!trimmed) {
      return { ok: false, errorCode: 'empty' };
    }

    if (USE_MOCK) {
      if (delayMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      }
      if (password === DEV_PROTOTYPE_PASSCODE) {
        getStorage()?.setItem(SESSION_KEY, 'authenticated');
        return { ok: true };
      }
      return { ok: false, errorCode: 'invalid' };
    }

    try {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ password }),
      });
      if (!response.ok) {
        return { ok: false, errorCode: response.status === 401 ? 'invalid' : 'network' };
      }
      const body = (await response.json()) as { token: string };
      setToken(body.token);
      return { ok: true };
    } catch (error) {
      if (error instanceof ApiClientError) {
        return { ok: false, errorCode: 'network' };
      }
      return { ok: false, errorCode: 'network' };
    }
  },

  logout(): void {
    if (USE_MOCK) {
      getStorage()?.removeItem(SESSION_KEY);
      return;
    }
    setToken(null);
  },
};
