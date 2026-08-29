import { describe, expect, it, vi } from 'vitest';
import { createOfflineOperationId } from './offlineStore';
import { isOfflineNetworkError } from './offlineSync';

describe('offline report safeguards', () => {
  it('creates a stable-looking client operation identifier', () => {
    expect(createOfflineOperationId()).toMatch(/^offline-/);
  });

  it('recognizes browser/network failures but not server validation errors', () => {
    vi.stubGlobal('navigator', { onLine: true });
    expect(isOfflineNetworkError(new TypeError('Failed to fetch'))).toBe(true);
    expect(isOfflineNetworkError(new Error('HTTP 422'))).toBe(false);
    vi.unstubAllGlobals();
  });
});
