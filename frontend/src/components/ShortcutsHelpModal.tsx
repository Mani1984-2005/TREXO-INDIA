import { Keyboard, X } from 'lucide-react';
import { useEffect } from 'react';
import { getModifierLabel } from '../utils/shortcuts';

interface ShortcutsHelpModalProps {
  open: boolean;
  onClose: () => void;
}

export function ShortcutsHelpModal({ open, onClose }: ShortcutsHelpModalProps) {
  const mod = getModifierLabel();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  const shortcutRows = [
    {
      keys: `${mod} + K`,
      action: 'Quick Search',
      description: 'Find items to add to bill, look up Udhaar accounts, or jump to any view.',
    },
    {
      keys: `${mod} + N`,
      secondaryKeys: 'Alt + N',
      action: 'New Transaction',
      description: 'Clear active cart, switch to Counter POS, and focus item search immediately.',
    },
    {
      keys: `${mod} + S`,
      action: 'Save / Complete',
      description: 'Submit an open form, complete the active Counter bill, or save a Purchase Order.',
    },
    {
      keys: 'Alt + 1 – 7',
      action: 'Switch Workspace',
      description:
        '1 Dashboard · 2 Counter · 3 Inventory · 4 Rescue Cash · 5 Restock · 6 Udhaar · 7 Reports.',
    },
    {
      keys: `${mod} + /`,
      secondaryKeys: '?',
      action: 'Keyboard Shortcuts',
      description: 'Open or close this shortcut reference.',
    },
    {
      keys: 'Esc',
      action: 'Close Overlay',
      description: 'Dismiss quick search, help dialog, or active receipt modal.',
    },
  ];

  return (
    <div
      className="no-print fixed inset-0 z-50 flex items-center justify-center bg-[#103D2B]/50 backdrop-blur-[1px] p-3 sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard Shortcuts"
      onClick={onClose}
    >
      <div
        className="trexo-modal-in flex max-h-[90vh] w-full max-w-lg flex-col rounded-xl border border-[#D8CEB6] bg-white shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-white/10 bg-[#103D2B] px-5 py-4 text-white shrink-0">
          <div className="flex items-center gap-2.5">
            <Keyboard className="h-4 w-4 text-[#C6A15B]" />
            <h2 className="text-sm font-semibold">Keyboard Shortcuts</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-white/75 hover:bg-white/10 hover:text-white transition-colors"
            aria-label="Close shortcuts reference"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="divide-y divide-[#E5EAE5] px-5 overflow-y-auto trexo-scroll">
          {shortcutRows.map((row) => (
            <div key={row.action} className="py-3.5 flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-[#172B22]">{row.action}</p>
                <p className="mt-0.5 text-xs text-[#718078]">{row.description}</p>
              </div>
              <div className="flex flex-col items-end gap-1 shrink-0">
                <kbd className="rounded-md border border-[#E5EAE5] bg-[#FAF7EF] px-2 py-1 font-mono text-xs font-semibold text-[#103D2B] whitespace-nowrap">
                  {row.keys}
                </kbd>
                {row.secondaryKeys && (
                  <span className="font-mono text-[11px] text-[#718078]">
                    or {row.secondaryKeys}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="flex items-center justify-end border-t border-[#E5EAE5] bg-[#FAF7EF] px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="min-h-[38px] rounded-lg bg-[#145C3A] px-4 py-1.5 text-xs font-semibold text-white hover:bg-[#103D2B]"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
