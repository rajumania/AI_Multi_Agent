import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../services/api';
import { Incident, LiveEvent } from '../types';

export interface OperatorLocation {
  latitude: number;
  longitude: number;
  accuracy?: number;
  timestamp: string;
  source: 'REAL' | 'DEMO';
}

interface RealOperationsControlsProps {
  incident?: Incident;
  wsState?: 'CONNECTED' | 'CONNECTING' | 'OFFLINE';
  demoPushVisible?: boolean;
  onClientEvent?: (event: LiveEvent) => void;
  onGpsLocation?: (location: OperatorLocation | null) => void;
}

const DEMO_LOCATION = { latitude: 16.2334, longitude: 80.5513 };
const DEFAULT_GPS_TOKEN = 'campusflow-secret-telemetry-key';

const isEmergencyActive = (incident?: Incident) => Boolean(
  incident && incident.status !== 'resolved' && incident.status !== 'closed'
);

export const RealOperationsControls: React.FC<RealOperationsControlsProps> = ({
  incident,
  wsState = 'OFFLINE',
  demoPushVisible = false,
  onClientEvent,
  onGpsLocation,
}) => {
  const [voiceReady, setVoiceReady] = useState(false);
  const [muted, setMuted] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [stopped, setStopped] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [needsAudioEnable, setNeedsAudioEnable] = useState(false);
  const [gpsMode, setGpsMode] = useState<'LIVE' | 'DEMO LOCATION' | 'OFFLINE'>('OFFLINE');
  const [gpsNotice, setGpsNotice] = useState<string | null>(null);
  const [lastPosition, setLastPosition] = useState<OperatorLocation | null>(null);

  const watchId = useRef<number | null>(null);
  const demoTimer = useRef<number | null>(null);
  const repeatTimer = useRef<number | null>(null);
  const mutedRef = useRef(false);
  const stoppedRef = useRef(false);

  const emitClientEvent = useCallback((eventName: string, description: string) => {
    const now = new Date();
    onClientEvent?.({
      event_name: eventName,
      incident_id: incident?.incident_id,
      timestamp: now.toISOString(),
      time_display: now.toLocaleTimeString(),
      description,
    });
  }, [incident?.incident_id, onClientEvent]);

  useEffect(() => {
    setVoiceReady('speechSynthesis' in window && 'SpeechSynthesisUtterance' in window);
  }, []);

  const alertText = incident
    ? `Emergency alert. ${incident.incident_type} reported in ${incident.location}. Campus emergency response has been activated. Security, medical and evacuation teams are being coordinated.`
    : 'Emergency alert. Fire reported in U-Block, second floor. Campus emergency response has been activated. Security, medical and evacuation teams are being coordinated.';

  const cancelSpeech = useCallback(() => {
    if (repeatTimer.current !== null) window.clearTimeout(repeatTimer.current);
    repeatTimer.current = null;
    window.speechSynthesis?.cancel();
    setSpeaking(false);
  }, []);

  const speakAlert = useCallback((force = false) => {
    if (!voiceReady || !window.speechSynthesis) {
      setVoiceError('Browser speech is unavailable in this browser.');
      return;
    }
    if (!force && (mutedRef.current || stoppedRef.current || !isEmergencyActive(incident))) return;

    setVoiceError(null);
    setNeedsAudioEnable(false);
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(alertText);
    utterance.rate = 0.94;
    utterance.onstart = () => {
      setSpeaking(true);
      emitClientEvent('voice_alert_started', 'Browser voice emergency alert started.');
    };
    utterance.onend = () => {
      setSpeaking(false);
      if (!mutedRef.current && !stoppedRef.current && isEmergencyActive(incident)) {
        repeatTimer.current = window.setTimeout(() => speakAlert(), 1200);
      }
    };
    utterance.onerror = () => {
      setSpeaking(false);
      setNeedsAudioEnable(true);
      setVoiceError('Browser autoplay or speaker access blocked. Click ENABLE AUDIO to start the real browser alert.');
    };
    try {
      window.speechSynthesis.speak(utterance);
    } catch {
      setNeedsAudioEnable(true);
      setVoiceError('Click ENABLE AUDIO to allow browser speech.');
    }
  }, [alertText, emitClientEvent, incident, voiceReady]);

  useEffect(() => {
    stoppedRef.current = false;
    mutedRef.current = false;
    setStopped(false);
    setMuted(false);
    cancelSpeech();

    if (isEmergencyActive(incident) && (incident?.severity === 'critical' || incident?.severity === 'high')) {
      const timer = window.setTimeout(() => speakAlert(), 180);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [incident?.incident_id, incident?.severity, incident?.status, cancelSpeech, speakAlert]);

  useEffect(() => () => {
    cancelSpeech();
    if (watchId.current !== null) navigator.geolocation?.clearWatch(watchId.current);
    if (demoTimer.current !== null) window.clearInterval(demoTimer.current);
  }, [cancelSpeech]);

  const mute = () => {
    mutedRef.current = true;
    setMuted(true);
    cancelSpeech();
    emitClientEvent('voice_alert_muted', 'Browser voice alert muted by operator.');
  };

  const replay = () => {
    mutedRef.current = false;
    stoppedRef.current = false;
    setMuted(false);
    setStopped(false);
    speakAlert(true);
  };

  const stopAlert = () => {
    stoppedRef.current = true;
    mutedRef.current = false;
    setStopped(true);
    setMuted(false);
    cancelSpeech();
    emitClientEvent('voice_alert_stopped', 'Browser voice alert stopped by operator.');
  };

  const enableAudio = () => {
    mutedRef.current = false;
    stoppedRef.current = false;
    setMuted(false);
    setStopped(false);
    speakAlert(true);
  };

  const publishLocation = (location: OperatorLocation) => {
    setLastPosition(location);
    onGpsLocation?.(location);
  };

  const enableLiveGps = () => {
    setGpsNotice(null);
    if (!navigator.geolocation) {
      setGpsMode('OFFLINE');
      setGpsNotice('This browser cannot provide GPS. Use DEMO LOCATION for the judge flow.');
      return;
    }
    if (watchId.current !== null) navigator.geolocation.clearWatch(watchId.current);
    watchId.current = navigator.geolocation.watchPosition(async (position) => {
      const { latitude, longitude, accuracy, heading, speed } = position.coords;
      const timestamp = new Date(position.timestamp || Date.now()).toISOString();
      const location: OperatorLocation = { latitude, longitude, accuracy, timestamp, source: 'REAL' };
      setGpsMode('LIVE');
      publishLocation(location);
      setGpsNotice('REAL browser GPS active. Backend telemetry is attempted when available.');
      try {
        await api.sendTelemetry({ vehicle_id: 'RESPONDER-PHONE-001', latitude, longitude, accuracy: accuracy || 0, heading: heading || 0, speed: speed || 0, timestamp }, import.meta.env.VITE_GPS_DEVICE_TOKEN || DEFAULT_GPS_TOKEN);
      } catch {
        setGpsNotice('REAL browser GPS active; backend telemetry endpoint did not accept this device ping.');
      }
    }, (error) => {
      setGpsMode('OFFLINE');
      setGpsNotice(error.code === error.PERMISSION_DENIED
        ? 'GPS permission was denied. Use DEMO LOCATION — SIMULATED.'
        : 'Live GPS is unavailable. Use DEMO LOCATION — SIMULATED.');
    }, { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 });
  };

  const useDemoLocation = () => {
    if (watchId.current !== null) navigator.geolocation?.clearWatch(watchId.current);
    watchId.current = null;
    if (demoTimer.current !== null) window.clearInterval(demoTimer.current);
    const publishDemo = () => {
      const location: OperatorLocation = { ...DEMO_LOCATION, timestamp: new Date().toISOString(), source: 'DEMO' };
      setGpsMode('DEMO LOCATION');
      setGpsNotice('DEMO GPS — SIMULATED. Coordinates are fixed campus demo data, not a real device.');
      publishLocation(location);
    };
    publishDemo();
    demoTimer.current = window.setInterval(publishDemo, 5000);
  };

  const stopGps = () => {
    if (watchId.current !== null) navigator.geolocation?.clearWatch(watchId.current);
    if (demoTimer.current !== null) window.clearInterval(demoTimer.current);
    watchId.current = null;
    demoTimer.current = null;
    setGpsMode('OFFLINE');
    setGpsNotice('GPS stopped by operator.');
    onGpsLocation?.(null);
  };

  useEffect(() => {
    if (!incident) {
      if (watchId.current !== null) navigator.geolocation?.clearWatch(watchId.current);
      if (demoTimer.current !== null) window.clearInterval(demoTimer.current);
      watchId.current = null;
      demoTimer.current = null;
      setGpsMode('OFFLINE');
      onGpsLocation?.(null);
    }
  }, [incident?.incident_id]);

  const active = isEmergencyActive(incident);

  return (
    <section className="panel-card operations-panel" style={{ marginBottom: '1rem' }}>
      <div className="panel-header">
        <div className="panel-title">REAL-TIME DEVICE CAPABILITIES</div>
        <span className="demo-label">DEMO MODE — EXTERNAL PAID SERVICES NOT REQUIRED</span>
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
        <div className="ops-status-grid">
          <span className={voiceReady ? 'ops-status real' : 'ops-status offline'}>VOICE: {voiceReady ? 'BROWSER READY' : 'UNAVAILABLE'}</span>
          <span className={`ops-status ${gpsMode === 'OFFLINE' ? 'offline' : gpsMode === 'DEMO LOCATION' ? 'demo' : 'real'}`}>GPS: {gpsMode}</span>
          <span className={`ops-status ${wsState === 'CONNECTED' ? 'real' : 'offline'}`}>WEBSOCKET: {wsState}</span>
          <span className="ops-status demo">DEMO PUSH: {demoPushVisible ? 'IN APP ACTIVE' : 'READY'}</span>
        </div>

        {active && (
          <div className="voice-alert-strip" role="status">
            <div>
              <strong>VOICE ALERT {stopped ? 'STOPPED' : muted ? 'MUTED' : speaking ? 'ACTIVE' : 'READY'}</strong>
              <small>REAL browser speaker • repeats while this emergency is active</small>
            </div>
            <div className="quick-actions-group">
              {needsAudioEnable && <button className="btn btn-danger" onClick={enableAudio}>CLICK TO ENABLE AUDIO</button>}
              <button className="btn btn-outline" onClick={mute} disabled={muted || stopped}>MUTE</button>
              <button className="btn btn-outline" onClick={replay}>REPLAY</button>
              <button className="btn btn-danger" onClick={stopAlert}>STOP ALERT</button>
            </div>
          </div>
        )}
        {voiceError && <small role="status" style={{ color: '#b91c1c' }}>{voiceError}</small>}

        <div className="gps-control-row">
          <div>
            <strong>GPS: {gpsMode}</strong>
            {lastPosition && <small>{lastPosition.source === 'REAL' ? 'REAL DEVICE' : 'DEMO GPS — SIMULATED'} • {lastPosition.latitude.toFixed(6)}, {lastPosition.longitude.toFixed(6)} • {new Date(lastPosition.timestamp).toLocaleTimeString()}</small>}
            {gpsNotice && <small>{gpsNotice}</small>}
          </div>
          <div className="quick-actions-group">
            <button className="btn btn-outline" onClick={enableLiveGps}>ENABLE LIVE GPS</button>
            {(gpsMode === 'OFFLINE' || gpsMode === 'DEMO LOCATION') && <button className="btn btn-outline" onClick={useDemoLocation}>USE DEMO LOCATION</button>}
            <button className="btn btn-outline" onClick={stopGps} disabled={gpsMode === 'OFFLINE'}>STOP GPS</button>
          </div>
        </div>

        <div className="ops-integrations-note">
          <span>OPTIONAL EXTERNAL INTEGRATIONS</span>
          <span>EMAIL: OPTIONAL / NOT CONFIGURED</span>
          <span>SMS: OPTIONAL</span>
          <span>PHONE: OPTIONAL</span>
          <span>FCM: OPTIONAL</span>
        </div>
      </div>
    </section>
  );
};
