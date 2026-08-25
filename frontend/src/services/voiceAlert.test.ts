import { describe, expect, it } from 'vitest';
import { buildSafeVoiceMessage, shouldVoiceAlert } from './voiceAlert';

describe('department voice alert policy', () => {
  const alert = { title: 'Medical assignment', message: 'Chemical emergency at V-Block.', level: 'critical' };

  it('speaks only enabled urgent alerts', () => {
    expect(shouldVoiceAlert(alert, true, false)).toBe(true);
    expect(shouldVoiceAlert(alert, false, false)).toBe(false);
    expect(shouldVoiceAlert(alert, true, true)).toBe(false);
    expect(shouldVoiceAlert({ ...alert, level: 'info' }, true, false)).toBe(false);
  });

  it('keeps voice content to safe structured notification text', () => {
    const message = buildSafeVoiceMessage({ ...alert, message: 'safe\nstructured content'.repeat(40) });
    expect(message).not.toContain('\n');
    expect(message.length).toBeLessThanOrEqual(240);
  });
});
