import { Incident, LiveEvent } from '../types';

export type AudioCapabilityState = 'NOT_ENABLED' | 'INITIALIZING' | 'READY' | 'BLOCKED';
export type VoiceAlertState = 'IDLE' | 'ACTIVE' | 'MUTED' | 'STOPPED';

export interface VoiceAlertControllerState {
  audioState: AudioCapabilityState;
  voiceState: VoiceAlertState;
  incident: Incident | null;
  error: string | null;
}

interface VoiceAlertControllerOptions {
  onStateChange: (state: VoiceAlertControllerState) => void;
  onClientEvent?: (event: LiveEvent) => void;
  repeatDelayMs?: number;
}

const TERMINAL_STATUSES: ReadonlySet<string> = new Set([
  'resolved',
  // Kept as a wire-level compatibility value; the current backend lifecycle
  // uses resolved/closed and does not declare a separate completed status.
  'completed',
  'closed',
  'cancelled',
  'rejected',
  'action_failed',
]);

export const isEmergencyActive = (incident?: Incident | null): boolean => Boolean(
  incident && !TERMINAL_STATUSES.has(String(incident.status).toLowerCase()),
);

const hasSpeechCapability = () => (
  typeof window !== 'undefined'
  && typeof window.speechSynthesis !== 'undefined'
  && typeof window.SpeechSynthesisUtterance !== 'undefined'
);

const getAudioContextConstructor = () => {
  if (typeof window === 'undefined') return undefined;
  return window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
};

export class VoiceAlertController {
  private readonly onStateChange: (state: VoiceAlertControllerState) => void;
  private readonly onClientEvent?: (event: LiveEvent) => void;
  private readonly repeatDelayMs: number;
  private state: VoiceAlertControllerState = {
    audioState: 'NOT_ENABLED',
    voiceState: 'IDLE',
    incident: null,
    error: null,
  };
  private activeIncidentId: string | null = null;
  private repeatTimer: number | null = null;
  private audioContext: AudioContext | null = null;
  private initializationPromise: Promise<boolean> | null = null;
  private muted = false;
  private stoppedByOperator = false;
  private disposed = false;
  private announcedIncidentIds = new Set<string>();
  private resolvedIncidentIds = new Set<string>();

  constructor(options: VoiceAlertControllerOptions) {
    this.onStateChange = options.onStateChange;
    this.onClientEvent = options.onClientEvent;
    this.repeatDelayMs = options.repeatDelayMs ?? 1200;
  }

  getState(): VoiceAlertControllerState {
    return this.state;
  }

  private updateState(update: Partial<VoiceAlertControllerState>) {
    if (this.disposed) return;
    this.state = { ...this.state, ...update };
    this.onStateChange(this.state);
  }

  private emitClientEvent(eventName: string, description: string, incidentId = this.state.incident?.incident_id) {
    if (!this.onClientEvent) return;
    const now = new Date();
    this.onClientEvent({
      event_name: eventName,
      incident_id: incidentId,
      timestamp: now.toISOString(),
      time_display: now.toLocaleTimeString(),
      description,
    });
  }

  private clearRepeatTimer() {
    if (this.repeatTimer !== null) window.clearTimeout(this.repeatTimer);
    this.repeatTimer = null;
  }

  private cancelSpeech() {
    this.clearRepeatTimer();
    if (hasSpeechCapability()) window.speechSynthesis.cancel();
  }

  private setBlocked(error: string) {
    this.cancelSpeech();
    this.updateState({
      audioState: 'BLOCKED',
      voiceState: 'IDLE',
      error,
    });
  }

  private async resumeAudioContext() {
    const AudioContextConstructor = getAudioContextConstructor();
    if (!AudioContextConstructor) return;

    if (!this.audioContext || this.audioContext.state === 'closed') {
      this.audioContext = new AudioContextConstructor();
    }
    await this.audioContext.resume();
    if (this.audioContext.state !== 'running') {
      throw new Error('The browser AudioContext did not enter the running state.');
    }

    // Exercise the output path during the user gesture without producing an audible tone.
    const buffer = this.audioContext.createBuffer(1, 1, this.audioContext.sampleRate);
    const source = this.audioContext.createBufferSource();
    const gain = this.audioContext.createGain();
    gain.gain.value = 0;
    source.buffer = buffer;
    source.connect(gain);
    gain.connect(this.audioContext.destination);
    source.start();
  }

  private verifySpeechSynthesis(): Promise<void> {
    if (!hasSpeechCapability()) {
      return Promise.reject(new Error('This browser does not provide the Web Speech API.'));
    }

    const synthesis = window.speechSynthesis;
    // Reading voices forces browsers that load voices lazily to initialize their speech service.
    synthesis.getVoices();

    return new Promise((resolve, reject) => {
      let settled = false;
      let timeout = 0;
      const finish = (success: boolean, error?: string) => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timeout);
        synthesis.cancel();
        if (success) resolve();
        else reject(new Error(error || 'The browser blocked speech synthesis.'));
      };
      // Verify that the browser speech engine really starts an utterance.
      const probe = new window.SpeechSynthesisUtterance('Audio enabled.');
      probe.volume = 0.15;
      probe.rate = 1;
      probe.onstart = () => finish(true);
      probe.onerror = () => finish(false);
      timeout = window.setTimeout(() => finish(false), 3000);
      try {
        synthesis.cancel();
        synthesis.speak(probe);
      } catch {
        finish(false);
      }
    });
  }

  async initializeAudio(): Promise<boolean> {
    if (this.disposed) return false;
    if (this.state.audioState === 'READY') return true;
    if (this.initializationPromise) return this.initializationPromise;

    this.initializationPromise = this.initializeAudioInternal();
    try {
      return await this.initializationPromise;
    } finally {
      this.initializationPromise = null;
    }
  }

  private async initializeAudioInternal(): Promise<boolean> {
    if (this.disposed) return false;
    if (this.state.audioState === 'READY') return true;

    this.updateState({ audioState: 'INITIALIZING', error: null });
    try {
      // Start the speech probe before the first await. This keeps the browser's
      // transient user activation attached to speechSynthesis.speak() when the
      // operator clicks ENABLE AUDIO.
      await this.verifySpeechSynthesis();
      await this.resumeAudioContext();
      try {
        sessionStorage.setItem('campusflow.audio.enabled', 'true');
      } catch {
        // The browser may disable storage in private/restricted contexts. The
        // in-memory controller state remains the authoritative ready state.
      }
      this.updateState({ audioState: 'READY', error: null });
      this.speakActiveIncident();
      return true;
    } catch (error: any) {
      this.setBlocked(`AUDIO BLOCKED — ${error?.message || 'Browser speech or speaker access is unavailable.'}`);
      return false;
    }
  }

  handleIncident(incident: Incident) {
    if (this.disposed) return;

    if (!isEmergencyActive(incident)) {
      this.resolvedIncidentIds.add(incident.incident_id);
      if (this.activeIncidentId === incident.incident_id) {
        this.activeIncidentId = null;
        this.muted = false;
        this.stoppedByOperator = false;
        this.cancelSpeech();
        this.updateState({
          incident,
          // A resolved incident must leave the capability ready/inactive, not
          // looking as though an active emergency is still sounding.
          voiceState: 'IDLE',
          error: null,
        });
        this.emitClientEvent('voice_alert_stopped', 'Voice alert stopped because the incident is no longer active.', incident.incident_id);
      } else if (this.state.incident?.incident_id === incident.incident_id) {
        this.updateState({ incident, voiceState: 'IDLE', error: null });
      }
      return;
    }

    if (this.resolvedIncidentIds.has(incident.incident_id)) return;

    const isNewIncident = this.activeIncidentId !== incident.incident_id;
    this.state = { ...this.state, incident };
    if (isNewIncident) {
      this.cancelSpeech();
      this.activeIncidentId = incident.incident_id;
      this.muted = false;
      this.stoppedByOperator = false;
      this.announcedIncidentIds.delete(incident.incident_id);
      this.updateState({ voiceState: 'IDLE', error: null });
    } else {
      this.onStateChange(this.state);
      // Duplicate WebSocket frames and React re-renders update the incident
      // snapshot but must not cancel and replay an already-running alert.
      return;
    }
    this.speakActiveIncident();
  }

  /**
   * Handle lifecycle-only WebSocket frames immediately. Terminal frames often
   * arrive before the follow-up REST snapshot; using the current incident
   * keeps audio from continuing during that small network race.
   */
  handleLifecycleEvent(event: LiveEvent) {
    if (!event.incident_id || !event.status || !this.state.incident) return;
    if (event.incident_id !== this.state.incident.incident_id) return;
    if (!TERMINAL_STATUSES.has(String(event.status).toLowerCase())) return;
    this.handleIncident({
      ...this.state.incident,
      status: String(event.status).toLowerCase() as Incident['status'],
      updated_at: event.timestamp || this.state.incident.updated_at,
    });
  }

  syncIncidents(incidents: Incident[]) {
    const activeIncident = incidents.find(isEmergencyActive);
    const currentIncident = this.state.incident;
    if (currentIncident) {
      const latest = incidents.find((item) => item.incident_id === currentIncident.incident_id);
      if (latest) this.handleIncident(latest);
    }
    if (activeIncident && activeIncident.incident_id !== this.activeIncidentId) {
      this.handleIncident(activeIncident);
    }
  }

  private speakActiveIncident() {
    const incident = this.state.incident;
    if (
      !incident
      || !isEmergencyActive(incident)
      || incident.incident_id !== this.activeIncidentId
      || this.state.audioState !== 'READY'
      || this.muted
      || this.stoppedByOperator
      || this.disposed
    ) return;

    if (!hasSpeechCapability()) {
      this.setBlocked('AUDIO BLOCKED — This browser does not provide speech synthesis.');
      return;
    }

    this.clearRepeatTimer();
    const synthesis = window.speechSynthesis;
    synthesis.cancel();
    const injuryText = incident.injured_count === null || incident.injured_count === undefined
      ? ''
      : ` ${incident.injured_count} people injured.`;
    const alertText = `Emergency alert. A ${incident.severity} severity ${incident.incident_type} incident has been reported at ${incident.location}.${injuryText} Please follow the emergency response plan.`;
    const utterance = new window.SpeechSynthesisUtterance(alertText);
    utterance.rate = 0.94;
    utterance.onstart = () => {
      if (this.activeIncidentId !== incident.incident_id || this.disposed) return;
      this.updateState({ voiceState: 'ACTIVE', error: null });
      if (!this.announcedIncidentIds.has(incident.incident_id)) {
        this.announcedIncidentIds.add(incident.incident_id);
        this.emitClientEvent('voice_alert_started', 'Browser voice emergency alert started.', incident.incident_id);
      }
    };
    utterance.onend = () => {
      if (
        this.activeIncidentId === incident.incident_id
        && isEmergencyActive(this.state.incident)
        && !this.muted
        && !this.stoppedByOperator
        && this.state.audioState === 'READY'
      ) {
        this.repeatTimer = window.setTimeout(() => this.speakActiveIncident(), this.repeatDelayMs);
      }
    };
    utterance.onerror = () => {
      if (this.activeIncidentId === incident.incident_id) {
        this.setBlocked('AUDIO BLOCKED — Browser speech or speaker access was blocked. Click ENABLE AUDIO to try again.');
      }
    };
    try {
      synthesis.speak(utterance);
    } catch {
      this.setBlocked('AUDIO BLOCKED — Browser speech or speaker access was blocked. Click ENABLE AUDIO to try again.');
    }
  }

  mute() {
    if (!this.activeIncidentId) return;
    this.muted = true;
    this.stoppedByOperator = false;
    this.cancelSpeech();
    this.updateState({ voiceState: 'MUTED' });
    this.emitClientEvent('voice_alert_muted', 'Browser voice alert muted by the authorized commander.');
  }

  unmute() {
    if (!this.activeIncidentId) return;
    this.muted = false;
    this.stoppedByOperator = false;
    this.updateState({ voiceState: 'IDLE', error: null });
    this.emitClientEvent('voice_alert_unmuted', 'Browser voice alert unmuted by the authorized commander.');
    this.speakActiveIncident();
  }

  replay() {
    this.muted = false;
    this.stoppedByOperator = false;
    this.updateState({ voiceState: 'IDLE', error: null });
    this.speakActiveIncident();
  }

  stop() {
    const incidentId = this.activeIncidentId;
    this.stoppedByOperator = true;
    this.muted = false;
    this.cancelSpeech();
    if (incidentId) this.updateState({ voiceState: 'STOPPED' });
    if (incidentId) this.emitClientEvent('voice_alert_stopped', 'Browser voice alert stopped by the authorized commander.', incidentId);
  }

  dispose() {
    this.disposed = true;
    this.initializationPromise = null;
    this.cancelSpeech();
    if (this.audioContext && this.audioContext.state !== 'closed') void this.audioContext.close();
    this.audioContext = null;
  }
}
