import type { CreateIncidentPayload } from './api';

export interface OfflineSnapshot<T> {
  value: T;
  cachedAt: string;
}

export interface OfflineIncidentOperation {
  id: string;
  type: 'incident_report';
  payload: CreateIncidentPayload;
  createdAt: string;
  attempts: number;
  lastError?: string;
}

const DB_NAME = 'aitam-offline-store';
const DB_VERSION = 1;
const SNAPSHOT_STORE = 'snapshots';
const QUEUE_STORE = 'incident-queue';
const FALLBACK_PREFIX = 'aitam-offline:';

function hasIndexedDb(): boolean {
  return typeof indexedDB !== 'undefined';
}

function fallbackKey(store: string, key: string): string {
  return `${FALLBACK_PREFIX}${store}:${key}`;
}

function readFallback<T>(store: string, key: string): T | null {
  try {
    const raw = localStorage.getItem(fallbackKey(store, key));
    return raw ? JSON.parse(raw) as T : null;
  } catch {
    return null;
  }
}

function writeFallback(store: string, key: string, value: unknown): void {
  try {
    localStorage.setItem(fallbackKey(store, key), JSON.stringify(value));
  } catch {
    // Storage may be disabled or full. Offline support remains best-effort.
  }
}

function removeFallback(store: string, key: string): void {
  try { localStorage.removeItem(fallbackKey(store, key)); } catch { /* best effort */ }
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(SNAPSHOT_STORE)) db.createObjectStore(SNAPSHOT_STORE);
      if (!db.objectStoreNames.contains(QUEUE_STORE)) db.createObjectStore(QUEUE_STORE, { keyPath: 'id' });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error('IndexedDB unavailable'));
  });
}

function idbRequest<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error('Offline storage request failed'));
  });
}

export function createOfflineOperationId(): string {
  const random = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `offline-${random}`;
}

export async function saveOfflineSnapshot<T>(key: string, value: T): Promise<void> {
  const snapshot: OfflineSnapshot<T> = { value, cachedAt: new Date().toISOString() };
  if (!hasIndexedDb()) { writeFallback(SNAPSHOT_STORE, key, snapshot); return; }
  try {
    const db = await openDb();
    await idbRequest(db.transaction(SNAPSHOT_STORE, 'readwrite').objectStore(SNAPSHOT_STORE).put(snapshot, key));
    db.close();
  } catch {
    writeFallback(SNAPSHOT_STORE, key, snapshot);
  }
}

export async function readOfflineSnapshot<T>(key: string): Promise<OfflineSnapshot<T> | null> {
  if (!hasIndexedDb()) return readFallback<OfflineSnapshot<T>>(SNAPSHOT_STORE, key);
  try {
    const db = await openDb();
    const snapshot = await idbRequest<OfflineSnapshot<T> | undefined>(db.transaction(SNAPSHOT_STORE, 'readonly').objectStore(SNAPSHOT_STORE).get(key));
    db.close();
    return snapshot || readFallback<OfflineSnapshot<T>>(SNAPSHOT_STORE, key);
  } catch {
    return readFallback<OfflineSnapshot<T>>(SNAPSHOT_STORE, key);
  }
}

export async function enqueueOfflineIncident(payload: CreateIncidentPayload, id = createOfflineOperationId()): Promise<OfflineIncidentOperation> {
  const operation: OfflineIncidentOperation = { id, type: 'incident_report', payload, createdAt: new Date().toISOString(), attempts: 0 };
  if (!hasIndexedDb()) { writeFallback(QUEUE_STORE, id, operation); return operation; }
  try {
    const db = await openDb();
    await idbRequest(db.transaction(QUEUE_STORE, 'readwrite').objectStore(QUEUE_STORE).put(operation));
    db.close();
  } catch {
    writeFallback(QUEUE_STORE, id, operation);
  }
  return operation;
}

export async function listOfflineIncidents(): Promise<OfflineIncidentOperation[]> {
  if (!hasIndexedDb()) {
    const values: OfflineIncidentOperation[] = [];
    try {
      for (let index = 0; index < localStorage.length; index += 1) {
        const key = localStorage.key(index);
        if (key?.startsWith(`${FALLBACK_PREFIX}${QUEUE_STORE}:`)) {
          const item = readFallback<OfflineIncidentOperation>(QUEUE_STORE, key.slice(`${FALLBACK_PREFIX}${QUEUE_STORE}:`.length));
          if (item) values.push(item);
        }
      }
    } catch { /* empty queue */ }
    return values.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  }
  try {
    const db = await openDb();
    const values = await idbRequest<OfflineIncidentOperation[]>(db.transaction(QUEUE_STORE, 'readonly').objectStore(QUEUE_STORE).getAll());
    db.close();
    return values.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  } catch {
    return [];
  }
}

export async function updateOfflineIncident(operation: OfflineIncidentOperation): Promise<void> {
  if (!hasIndexedDb()) { writeFallback(QUEUE_STORE, operation.id, operation); return; }
  try {
    const db = await openDb();
    await idbRequest(db.transaction(QUEUE_STORE, 'readwrite').objectStore(QUEUE_STORE).put(operation));
    db.close();
  } catch { writeFallback(QUEUE_STORE, operation.id, operation); }
}

export async function removeOfflineIncident(id: string): Promise<void> {
  if (!hasIndexedDb()) { removeFallback(QUEUE_STORE, id); return; }
  try {
    const db = await openDb();
    await idbRequest(db.transaction(QUEUE_STORE, 'readwrite').objectStore(QUEUE_STORE).delete(id));
    db.close();
  } catch { removeFallback(QUEUE_STORE, id); }
}
