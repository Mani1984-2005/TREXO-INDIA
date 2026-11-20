import { describe, expect, it } from 'vitest';
import { isAltShortcut, isPrimaryShortcut } from './shortcuts';

describe('keyboard shortcut matchers', () => {
  it('matches Ctrl+K and Cmd+K primary shortcuts case-insensitively', () => {
    expect(
      isPrimaryShortcut({ ctrlKey: true, metaKey: false, altKey: false, shiftKey: false, key: 'k' }, 'k')
    ).toBe(true);
    expect(
      isPrimaryShortcut({ ctrlKey: false, metaKey: true, altKey: false, shiftKey: false, key: 'K' }, 'k')
    ).toBe(true);
    expect(
      isPrimaryShortcut({ ctrlKey: true, metaKey: false, altKey: false, shiftKey: true, key: 'K' }, 'k')
    ).toBe(false);
  });

  it('matches Ctrl+N and Ctrl+S without triggering on unmodified keys', () => {
    expect(
      isPrimaryShortcut({ ctrlKey: true, metaKey: false, altKey: false, shiftKey: false, key: 'n' }, 'n')
    ).toBe(true);
    expect(
      isPrimaryShortcut({ ctrlKey: true, metaKey: false, altKey: false, shiftKey: false, key: 's' }, 's')
    ).toBe(true);
    expect(
      isPrimaryShortcut({ ctrlKey: false, metaKey: false, altKey: false, shiftKey: false, key: 's' }, 's')
    ).toBe(false);
  });

  it('matches Alt+1 through Alt+7 and Alt+N cleanly', () => {
    expect(
      isAltShortcut({ ctrlKey: false, metaKey: false, altKey: true, shiftKey: false, key: '1' }, '1')
    ).toBe(true);
    expect(
      isAltShortcut({ ctrlKey: false, metaKey: false, altKey: true, shiftKey: false, key: '7' }, '7')
    ).toBe(true);
    expect(
      isAltShortcut({ ctrlKey: false, metaKey: false, altKey: true, shiftKey: false, key: 'n' }, 'n')
    ).toBe(true);
    expect(
      isAltShortcut({ ctrlKey: true, metaKey: false, altKey: true, shiftKey: false, key: '1' }, '1')
    ).toBe(false);
  });

  it('matches Ctrl+/ for keyboard shortcuts help overlay', () => {
    expect(
      isPrimaryShortcut({ ctrlKey: true, metaKey: false, altKey: false, shiftKey: false, key: '/' }, '/')
    ).toBe(true);
    expect(
      isPrimaryShortcut({ ctrlKey: false, metaKey: true, altKey: false, shiftKey: false, key: '/' }, '/')
    ).toBe(true);
  });
});

