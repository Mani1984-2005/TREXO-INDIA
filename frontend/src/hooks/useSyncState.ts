import { useEffect, useState } from 'react';
import { useLedgerStore } from '../store/useLedgerStore';

export type SyncStatusMode = 'saving' | 'offline' | 'synced';

export interface SyncState {
  mode: SyncStatusMode;
  isOnline: boolean;
  lastSavedAt: string | null;
}

export function useSyncState(): SyncState {
  const [isOnline, setIsOnline] = useState<boolean>(() =>
    typeof navigator !== 'undefined' ? navigator.onLine : true
  );
  const isSaving = useLedgerStore((s) => s.isSaving);
  const lastSavedAt = useLedgerStore((s) => s.lastSavedAt);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const mode: SyncStatusMode = isSaving ? 'saving' : !isOnline ? 'offline' : 'synced';

  return {
    mode,
    isOnline,
    lastSavedAt,
  };
}
