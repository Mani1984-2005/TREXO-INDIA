import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLedgerStore } from '../store/useLedgerStore';
import {
  dispatchFocusCounterSearch,
  dispatchSaveAction,
  isAltShortcut,
  isEditableElement,
  isPrimaryShortcut,
  type SaveActionDetail,
  SHORTCUT_EVENTS,
} from '../utils/shortcuts';

export interface UseGlobalShortcutsOptions {
  quickSearchOpen: boolean;
  setQuickSearchOpen: (open: boolean | ((prev: boolean) => boolean)) => void;
  shortcutsHelpOpen: boolean;
  setShortcutsHelpOpen: (open: boolean | ((prev: boolean) => boolean)) => void;
  onNewTransaction: () => void;
  /** Optional custom save handler override; defaults to standardized form/page save dispatch */
  onSave?: () => boolean;
  /** Optional hook to dismiss additional shell-level overlays (e.g. UPI settings, menus) on Escape */
  onDismissOverlays?: () => boolean;
}

const ROUTE_BY_DIGIT: Record<string, string> = {
  '1': '/',
  '2': '/counter',
  '3': '/inventory',
  '4': '/rescue',
  '5': '/restock',
  '6': '/customers',
  '7': '/reports',
};

/**
 * Standardized global keyboard shortcut listener mounted inside AppShell.
 * Handles:
 *  - Ctrl/Cmd+K: Quick Search palette
 *  - Ctrl/Cmd+N (and Alt+N): New Counter Transaction
 *  - Ctrl/Cmd+S: Context-aware Save across forms, modals, and active pages
 *  - Ctrl/Cmd+/ or ?: Keyboard Shortcuts Help
 *  - Alt+1..7: Direct workspace navigation
 *  - Escape: Dismiss open shell overlays / receipt
 */
export function useGlobalShortcuts({
  quickSearchOpen,
  setQuickSearchOpen,
  shortcutsHelpOpen,
  setShortcutsHelpOpen,
  onNewTransaction,
  onSave,
  onDismissOverlays,
}: UseGlobalShortcutsOptions): void {
  const navigate = useNavigate();
  const clearLastCompletedSale = useLedgerStore((s) => s.clearLastCompletedSale);
  const markSavedNow = useLedgerStore((s) => s.markSavedNow);
  const pushToast = useLedgerStore((s) => s.pushToast);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+K / Cmd+K: Toggle Quick Search palette
      if (isPrimaryShortcut(e, 'k')) {
        e.preventDefault();
        setShortcutsHelpOpen(false);
        setQuickSearchOpen((prev) => !prev);
        return;
      }

      // Ctrl+N / Cmd+N or Alt+N: New Transaction on Counter
      if (isPrimaryShortcut(e, 'n') || isAltShortcut(e, 'n')) {
        e.preventDefault();
        setQuickSearchOpen(false);
        setShortcutsHelpOpen(false);
        onNewTransaction();
        return;
      }

      // Ctrl+S / Cmd+S: Context-aware Save / Submit open form / Trigger page save
      if (isPrimaryShortcut(e, 's')) {
        e.preventDefault();
        if (quickSearchOpen || shortcutsHelpOpen) return;
        const handled = onSave ? onSave() : dispatchSaveAction();
        if (!handled) {
          markSavedNow();
          pushToast('All records saved', 'Store ledger is synced on this device.', 'emerald');
        }
        return;
      }

      // Ctrl+/ / Cmd+/ or ? (outside editable inputs): Toggle Keyboard Shortcuts Help
      if (
        isPrimaryShortcut(e, '/') ||
        (e.key === '?' && !e.ctrlKey && !e.metaKey && !e.altKey && !isEditableElement(e.target))
      ) {
        e.preventDefault();
        setQuickSearchOpen(false);
        setShortcutsHelpOpen((prev) => !prev);
        return;
      }

      // Alt+1..7: Quick workspace navigation
      if (e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey && ROUTE_BY_DIGIT[e.key]) {
        e.preventDefault();
        setQuickSearchOpen(false);
        setShortcutsHelpOpen(false);
        const dest = ROUTE_BY_DIGIT[e.key];
        navigate(dest);
        if (dest === '/counter') {
          setTimeout(() => dispatchFocusCounterSearch(), 50);
        }
        return;
      }

      // Esc: Dismiss open shell overlays or completed receipt modal
      if (e.key === 'Escape') {
        if (quickSearchOpen) {
          e.preventDefault();
          setQuickSearchOpen(false);
          return;
        }
        if (shortcutsHelpOpen) {
          e.preventDefault();
          setShortcutsHelpOpen(false);
          return;
        }
        if (onDismissOverlays?.()) {
          e.preventDefault();
          return;
        }
        clearLastCompletedSale();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [
    quickSearchOpen,
    setQuickSearchOpen,
    shortcutsHelpOpen,
    setShortcutsHelpOpen,
    onNewTransaction,
    onSave,
    onDismissOverlays,
    navigate,
    clearLastCompletedSale,
    markSavedNow,
    pushToast,
  ]);
}

/**
 * Standardized hook for pages/forms to respond to Ctrl+S / Cmd+S without re-binding listeners
 * on every render. When `enabled` is true, calling Ctrl+S invokes `onSave` and marks the
 * global save event as handled.
 */
export function useSaveShortcut(onSave: () => void | Promise<void>, enabled = true): void {
  const savedHandlerRef = useRef(onSave);
  savedHandlerRef.current = onSave;

  useEffect(() => {
    if (!enabled) return;
    const listener = (event: Event) => {
      const custom = event as CustomEvent<SaveActionDetail>;
      if (custom.detail.handled) return;
      custom.detail.handled = true;
      void savedHandlerRef.current();
    };
    window.addEventListener(SHORTCUT_EVENTS.SAVE_ACTION, listener);
    return () => window.removeEventListener(SHORTCUT_EVENTS.SAVE_ACTION, listener);
  }, [enabled]);
}

/**
 * Standardized hook for focusing the Counter search input when Ctrl+N / Alt+N triggers a new bill.
 */
export function useCounterFocusShortcut(onFocus: () => void): void {
  const focusRef = useRef(onFocus);
  focusRef.current = onFocus;

  useEffect(() => {
    const listener = () => focusRef.current();
    window.addEventListener(SHORTCUT_EVENTS.FOCUS_COUNTER_SEARCH, listener);
    return () => window.removeEventListener(SHORTCUT_EVENTS.FOCUS_COUNTER_SEARCH, listener);
  }, []);
}
