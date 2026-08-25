import { afterEach, describe, expect, it, vi } from 'vitest';
import { Incident } from '../types';
import { VoiceAlertController } from './voiceAlertController';

class FakeUtterance {
  text: string;
  volume = 1;
  rate = 1;
  onstart: (() => void) | null = null;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(text: string) {
    this.text = text;
  }
}

const makeIncident = (incidentId: string, status: string = 'reported'): Incident => ({
  incident_id: incidentId,
  description: 'Fire reported in the second floor lab.',
  incident_type: 'fire',
  location: 'U-Block',
  severity: 'high',
  injured_count: 3,
  status: status as Incident['status'],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
});

const installBrowser = (probeBlocked = false) => {
  const spoken: FakeUtterance[] = [];
  const synthesis = {
    cancel: vi.fn(),
    getVoices: vi.fn(() => []),
    speak: vi.fn((utterance: FakeUtterance) => {
      spoken.push(utterance);
      if (probeBlocked) utterance.onerror?.();
      else utterance.onstart?.();
    }),
  };
  const browser = {
    speechSynthesis: synthesis,
    SpeechSynthesisUtterance: FakeUtterance,
    setTimeout,
    clearTimeout,
  } as unknown as Window;
  vi.stubGlobal('window', browser);
  vi.stubGlobal('sessionStorage', { setItem: vi.fn() });
  return { synthesis, spoken };
};

const makeController = (onStateChange = vi.fn()) => new VoiceAlertController({ onStateChange });

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('VoiceAlertController', () => {
  it('starts with audio disabled', () => {
    installBrowser();
    expect(makeController().getState().audioState).toBe('NOT_ENABLED');
  });

  it('initializes audio only after a successful browser speech probe', async () => {
    installBrowser();
    const controller = makeController();
    expect(await controller.initializeAudio()).toBe(true);
    expect(controller.getState().audioState).toBe('READY');
  });

  it('starts an incident-specific alert from an incident event after audio is ready', async () => {
    const { spoken } = installBrowser();
    const controller = makeController();
    await controller.initializeAudio();
    controller.handleIncident(makeIncident('INC-A'));
    expect(controller.getState().voiceState).toBe('ACTIVE');
    expect(spoken[spoken.length - 1]?.text).toContain('high severity fire incident');
    expect(spoken[spoken.length - 1]?.text).toContain('U-Block');
    expect(spoken[spoken.length - 1]?.text).toContain('3 people injured');
  });

  it('does not create a duplicate speech loop for duplicate incident events', async () => {
    const { synthesis } = installBrowser();
    const controller = makeController();
    await controller.initializeAudio();
    const incident = makeIncident('INC-A');
    controller.handleIncident(incident);
    controller.handleIncident(incident);
    expect(synthesis.speak).toHaveBeenCalledTimes(2); // one probe and one alert
  });

  it('keeps one controlled repeat loop active while an incident remains active', async () => {
    vi.useFakeTimers();
    const { synthesis, spoken } = installBrowser();
    const controller = makeController();
    await controller.initializeAudio();
    controller.handleIncident(makeIncident('INC-A'));
    spoken[spoken.length - 1]?.onend?.();
    vi.advanceTimersByTime(1200);
    expect(synthesis.speak).toHaveBeenCalledTimes(3); // probe, first alert, one repeat
  });

  it.each(['resolved', 'completed', 'closed'])('stops immediately for %s incidents', async (status) => {
    vi.useFakeTimers();
    const { synthesis, spoken } = installBrowser();
    const controller = makeController();
    await controller.initializeAudio();
    controller.handleIncident(makeIncident('INC-A'));
    spoken[spoken.length - 1]?.onend?.();
    controller.handleIncident(makeIncident('INC-A', status));
    vi.advanceTimersByTime(3000);
    expect(controller.getState().voiceState).toBe('IDLE');
    expect(controller.getState().audioState).toBe('READY');
    expect(synthesis.cancel).toHaveBeenCalled();
    expect(synthesis.speak).toHaveBeenCalledTimes(2);
  });

  it('starts a new incident after the previous incident is resolved', async () => {
    const { synthesis } = installBrowser();
    const controller = makeController();
    await controller.initializeAudio();
    controller.handleIncident(makeIncident('INC-A'));
    controller.handleIncident(makeIncident('INC-A', 'resolved'));
    controller.handleIncident(makeIncident('INC-B'));
    expect(synthesis.speak).toHaveBeenCalledTimes(3); // probe plus A and B
    expect(controller.getState().incident?.incident_id).toBe('INC-B');
  });

  it('does not replay an alert when reconnect or a React re-render repeats the same snapshot', async () => {
    const { synthesis } = installBrowser();
    const controller = makeController();
    await controller.initializeAudio();
    const incident = makeIncident('INC-A');
    controller.handleIncident(incident);
    controller.syncIncidents([incident]);
    controller.handleIncident({ ...incident });
    expect(synthesis.speak).toHaveBeenCalledTimes(2);
  });

  it('mutes and resumes the current emergency without losing the incident', async () => {
    const { synthesis } = installBrowser();
    const controller = makeController();
    await controller.initializeAudio();
    const incident = makeIncident('INC-A');
    controller.handleIncident(incident);
    controller.mute();
    expect(controller.getState().voiceState).toBe('MUTED');
    controller.unmute();
    expect(controller.getState().incident?.incident_id).toBe('INC-A');
    expect(controller.getState().voiceState).toBe('ACTIVE');
    expect(synthesis.speak).toHaveBeenCalledTimes(3); // probe, alert, resumed alert
  });

  it('replays once without creating a second repeat timer', async () => {
    vi.useFakeTimers();
    const { synthesis, spoken } = installBrowser();
    const controller = makeController();
    await controller.initializeAudio();
    controller.handleIncident(makeIncident('INC-A'));
    controller.replay();
    spoken[spoken.length - 1]?.onend?.();
    vi.advanceTimersByTime(1200);
    expect(synthesis.speak).toHaveBeenCalledTimes(4); // probe, first, replay, one repeat
  });

  it('stops audio without changing the active incident status', async () => {
    vi.useFakeTimers();
    const { synthesis, spoken } = installBrowser();
    const controller = makeController();
    await controller.initializeAudio();
    const incident = makeIncident('INC-A');
    controller.handleIncident(incident);
    spoken[spoken.length - 1]?.onend?.();
    controller.stop();
    vi.advanceTimersByTime(3000);
    expect(controller.getState().voiceState).toBe('STOPPED');
    expect(controller.getState().incident?.incident_id).toBe('INC-A');
    expect(synthesis.speak).toHaveBeenCalledTimes(2); // probe and first alert
  });

  it('reports a blocked browser truthfully and leaves audio not ready', async () => {
    installBrowser(true);
    const controller = makeController();
    expect(await controller.initializeAudio()).toBe(false);
    expect(controller.getState().audioState).toBe('BLOCKED');
    expect(controller.getState().error).toContain('AUDIO BLOCKED');
  });
});
