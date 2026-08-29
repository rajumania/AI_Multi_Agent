import React, { useEffect, useState } from 'react';
import { RefreshCw, Wifi, WifiOff } from 'lucide-react';
import { flushOfflineQueue, getOfflineQueueCount, startOfflineSync, subscribeOfflineQueue } from '../services/offlineSync';

export const OfflineStatus: React.FC = () => {
  const [online, setOnline] = useState(() => typeof navigator === 'undefined' || navigator.onLine);
  const [queued, setQueued] = useState(0);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    const updateOnline = () => setOnline(navigator.onLine);
    window.addEventListener('online', updateOnline);
    window.addEventListener('offline', updateOnline);
    const unsubscribe = subscribeOfflineQueue(setQueued);
    const stopSync = startOfflineSync();
    return () => {
      window.removeEventListener('online', updateOnline);
      window.removeEventListener('offline', updateOnline);
      unsubscribe();
      stopSync();
    };
  }, []);

  const syncNow = async () => {
    if (!online || syncing) return;
    setSyncing(true);
    try { await flushOfflineQueue(); } finally {
      setQueued(await getOfflineQueueCount());
      setSyncing(false);
    }
  };

  if (online && queued === 0) return null;
  return (
    <div role="status" aria-live="polite" className={`offline-status ${online ? 'offline-status-queue' : 'offline-status-offline'}`}>
      {online ? <Wifi size={15} aria-hidden="true" /> : <WifiOff size={15} aria-hidden="true" />}
      <span>{online ? `${queued} report${queued === 1 ? '' : 's'} waiting to sync` : 'Offline — showing saved data'}</span>
      {online && <button type="button" onClick={() => void syncNow()} disabled={syncing} aria-label="Sync queued reports">
        <RefreshCw size={13} className={syncing ? 'spin' : ''} /> Sync
      </button>}
    </div>
  );
};
