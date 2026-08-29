import { api } from './api';
import type { CreateIncidentPayload } from './api';
import { enqueueOfflineIncident, listOfflineIncidents, removeOfflineIncident, updateOfflineIncident } from './offlineStore';
import { Incident } from '../types';

export interface QueuedIncidentResult {
  incident: Incident;
  operationId: string;
}

type QueueListener = (count: number) => void;
const listeners = new Set<QueueListener>();

function notifyQueueChanged(count: number): void { listeners.forEach((listener) => listener(count)); }

export function subscribeOfflineQueue(listener: QueueListener): () => void {
  listeners.add(listener);
  void getOfflineQueueCount().then(listener);
  return () => listeners.delete(listener);
}

export async function getOfflineQueueCount(): Promise<number> {
  const operations = await listOfflineIncidents();
  return operations.length;
}

export function isOfflineNetworkError(error: unknown): boolean {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) return true;
  if (error instanceof TypeError) return true;
  const message = error instanceof Error ? error.message.toLowerCase() : String(error).toLowerCase();
  return message.includes('failed to fetch') || message.includes('networkerror') || message.includes('network request failed');
}

function queuedIncident(payload: CreateIncidentPayload, operationId: string): Incident {
  const now = new Date().toISOString();
  return {
    incident_id: `OFFLINE-${operationId.slice(-12).toUpperCase()}`,
    description: payload.description,
    incident_type: payload.incident_type as Incident['incident_type'],
    location: payload.location,
    severity: payload.severity as Incident['severity'],
    injured_count: payload.injured_count,
    evidence_source: payload.evidence_source,
    reported_by: payload.reported_by,
    latitude: payload.latitude,
    longitude: payload.longitude,
    status: 'reported',
    ai_provider_status: 'OFFLINE_QUEUED',
    current_step: 'Saved on this device; waiting for a secure connection.',
    next_action: 'The report will be submitted automatically when connectivity returns.',
    created_at: now,
    updated_at: now,
    client_operation_id: operationId,
    sync_state: 'queued',
  };
}

export async function queueIncidentReport(payload: CreateIncidentPayload): Promise<QueuedIncidentResult> {
  const operation = await enqueueOfflineIncident(payload);
  const count = await getOfflineQueueCount();
  notifyQueueChanged(count);
  return { incident: queuedIncident(payload, operation.id), operationId: operation.id };
}

export async function flushOfflineQueue(): Promise<number> {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) return getOfflineQueueCount();
  const operations = await listOfflineIncidents();
  let synced = 0;
  for (const operation of operations) {
    try {
      await api.createIncident(operation.payload, operation.id);
      await removeOfflineIncident(operation.id);
      synced += 1;
    } catch (error) {
      await updateOfflineIncident({ ...operation, attempts: operation.attempts + 1, lastError: error instanceof Error ? error.message : 'Submission failed' });
    }
  }
  notifyQueueChanged(await getOfflineQueueCount());
  return synced;
}

export function startOfflineSync(): () => void {
  const handleOnline = () => { void flushOfflineQueue(); };
  window.addEventListener('online', handleOnline);
  void flushOfflineQueue();
  return () => window.removeEventListener('online', handleOnline);
}
