import { beforeEach, describe, expect, it } from 'vitest';
import { authService } from './authService';

describe('owner prototype authService', () => {
  beforeEach(() => {
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

  it('accepts the temporary development password', async () => {
    const res = await authService.verifyOwnerPassword('123456789', 0);
    expect(res.ok).toBe(true);
    expect(res.errorCode).toBeUndefined();
  });
});
