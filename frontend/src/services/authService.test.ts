import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

let authService: typeof import('./authService').authService;

describe('owner prototype authService', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  beforeEach(async () => {
    vi.stubEnv('VITE_USE_MOCK', 'true');
    vi.resetModules();
    ({ authService } = await import('./authService'));
    authService.logout();
  });

  it('rejects empty or whitespace-only passwords', async () => {
    const res1 = await authService.verifyOwnerPassword('', 0);
    expect(res1.ok).toBe(false);
    expect(res1.errorCode).toBe('empty');

    const res2 = await authService.verifyOwnerPassword('   ', 0);
    expect(res2.ok).toBe(false);
    expect(res2.errorCode).toBe('empty');
  });

  it('rejects incorrect passwords', async () => {
    const res = await authService.verifyOwnerPassword('wrong-pass', 0);
    expect(res.ok).toBe(false);
    expect(res.errorCode).toBe('invalid');
  });

  it('does not accept a hardcoded prototype password', async () => {
    const res = await authService.verifyOwnerPassword('123456789', 0);
    expect(res.ok).toBe(false);
    expect(res.errorCode).toBe('invalid');
  });

  it('authenticates through the API and attaches the returned token to protected calls', async () => {
    vi.stubEnv('VITE_USE_MOCK', 'false');
    vi.resetModules();

    const token = 'signed-test-token';
    const fetchMock = vi.fn<typeof fetch>();
    fetchMock
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ token, expires_in: 43200, token_type: 'bearer' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      )
      .mockResolvedValueOnce(
        new Response('[]', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      )
      .mockResolvedValueOnce(new Response('', { status: 401 }))
      .mockRejectedValueOnce(new Error('offline'));
    vi.stubGlobal('fetch', fetchMock);

    const { authService: apiAuthService } = await import('./authService');
    const { api } = await import('./apiClient');

    const login = await apiAuthService.verifyOwnerPassword('api-test-owner', 0);
    expect(login.ok).toBe(true);
    expect(fetchMock.mock.calls[0][0]).toBe(
      'http://127.0.0.1:8000/api/v1/auth/login'
    );
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      password: 'api-test-owner',
    });

    await api.get('/store/products');
    const protectedHeaders = new Headers(fetchMock.mock.calls[1][1]?.headers);
    expect(protectedHeaders.get('Authorization')).toBe(`Bearer ${token}`);

    const invalid = await apiAuthService.verifyOwnerPassword('incorrect', 0);
    expect(invalid).toEqual({ ok: false, errorCode: 'invalid' });

    const unavailable = await apiAuthService.verifyOwnerPassword('api-test-owner', 0);
    expect(unavailable).toEqual({ ok: false, errorCode: 'network' });
  });
});
