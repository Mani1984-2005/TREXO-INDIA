export const SHORTCUT_EVENTS = {
  FOCUS_COUNTER_SEARCH: 'trexo:focus-counter-search',
  SAVE_ACTION: 'trexo:save-action',
} as const;

export interface SaveActionDetail {
  handled: boolean;
}

/**
 * Checks whether an element is an editable text input where plain single-key shortcuts
 * (like `?`) should not hijack typing.
 */
export function isEditableElement(target: EventTarget | null): boolean {
  if (!target || !(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
  if (target.isContentEditable) return true;
  return false;
}

/**
 * Matches Ctrl (Windows/Linux) or Cmd/Meta (macOS) + key cleanly, ignoring Alt/Shift noise.
 */
export function isPrimaryShortcut(
  e: Pick<KeyboardEvent, 'ctrlKey' | 'metaKey' | 'altKey' | 'shiftKey' | 'key'>,
  targetKey: string
): boolean {
  const hasPrimary = (e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey;
  return hasPrimary && e.key.toLowerCase() === targetKey.toLowerCase();
}

/**
 * Matches Alt + key (without Ctrl/Meta) for quick view switching and Alt+N fallback.
 */
export function isAltShortcut(
  e: Pick<KeyboardEvent, 'ctrlKey' | 'metaKey' | 'altKey' | 'shiftKey' | 'key'>,
  targetKey: string
): boolean {
  return e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey && e.key.toLowerCase() === targetKey.toLowerCase();
}

export function dispatchFocusCounterSearch(): void {
  window.dispatchEvent(new CustomEvent(SHORTCUT_EVENTS.FOCUS_COUNTER_SEARCH));
}

/**
 * Dispatches a context-aware Save event.
 * 1. If a modal dialog (`[role="dialog"]`) is open:
 *    - Submits its active `<form>` via `requestSubmit()` if one exists.
 *    - Otherwise absorbs the shortcut (returns `true`) so background pages do not save behind
 *      manual-verification or read-only modals (e.g. UPI QR confirmation or receipts).
 * 2. Otherwise dispatches `SHORTCUT_EVENTS.SAVE_ACTION` so the active page can handle it.
 */
export function dispatchSaveAction(): boolean {
  if (typeof document !== 'undefined') {
    const dialogs = document.querySelectorAll<HTMLElement>('[role="dialog"]');
    if (dialogs.length > 0) {
      const topDialog = dialogs[dialogs.length - 1];
      const dialogForm = topDialog.querySelector<HTMLFormElement>('form');
      if (dialogForm) {
        if (typeof dialogForm.requestSubmit === 'function') {
          dialogForm.requestSubmit();
        } else {
          dialogForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        }
      }
      return true;
    }
  }

  const detail: SaveActionDetail = { handled: false };
  window.dispatchEvent(new CustomEvent<SaveActionDetail>(SHORTCUT_EVENTS.SAVE_ACTION, { detail }));
  return detail.handled;
}

export function getModifierLabel(): '⌘' | 'Ctrl' {
  if (typeof navigator !== 'undefined' && /Mac|iPhone|iPad|iPod/i.test(navigator.platform)) {
    return '⌘';
  }
  return 'Ctrl';
}
