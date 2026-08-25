import React, { useEffect, useRef, useState } from 'react';
import { Incident } from '../types';
import { AudioCapabilityState, isEmergencyActive, VoiceAlertState } from '../services/voiceAlertController';

export interface OperatorLocation {
  latitude: number;
  longitude: number;
  accuracy?: number;
  timestamp: string;
  source: 'REAL' | 'DEMO';
}

interface RealOperationsControlsProps {
  incident?: Incident;
  voiceIncident?: Incident | null;
  audioState?: AudioCapabilityState;
  voiceState?: VoiceAlertState;
  voiceError?: string | null;
  onEnableAudio?: () => void;
  onMute?: () => void;
  onUnmute?: () => void;
  onReplay?: () => void;
  onStopVoice?: () => void;
  wsState?: 'CONNECTED' | 'CONNECTING' | 'OFFLINE';
  demoPushVisible?: boolean;
  onGpsLocation?: (location: OperatorLocation | null) => void;
}

const DEMO_LOCATION = { latitude: 16.2334, longitude: 80.5513 };

export const RealOperationsControls: React.FC<RealOperationsControlsProps> = ({
  incident,
  voiceIncident = null,
  audioState = 'NOT_ENABLED',
  voiceState = 'IDLE',
  voiceError = null,
  onEnableAudio,
  onMute,
  onUnmute,
  onReplay,
  onStopVoice,
  wsState = 'OFFLINE',
  demoPushVisible = false,
  onGpsLocation,
}) => {
  const [gpsMode, setGpsMode] = useState<'LIVE' | 'DEMO LOCATION' | 'OFFLINE'>('OFFLINE');
  const [gpsNotice, setGpsNotice] = useState<string | null>(null);
  const [lastPosition, setLastPosition] = useState<OperatorLocation | null>(null);

  const watchId = useRef<number | null>(null);
  const demoTimer = useRef<number | null>(null);

  useEffect(() => () => {
    if (watchId.current !== null) navigator.geolocation?.clearWatch(watchId.current);
    if (demoTimer.current !== null) window.clearInterval(demoTimer.current);
  }, []);

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
    watchId.current = navigator.geolocation.watchPosition((position) => {
      const { latitude, longitude, accuracy } = position.coords;
      const location: OperatorLocation = { latitude, longitude, accuracy, timestamp: new Date(position.timestamp || Date.now()).toISOString(), source: 'REAL' };
      setGpsMode('LIVE');
      publishLocation(location);
      setGpsNotice('REAL browser GPS active. Transport telemetry is sent only from an assigned Transport resource map.');
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
  const voiceDisplayIncident = incident || voiceIncident;
  const hasVoiceStatus = Boolean(voiceDisplayIncident) && (active || voiceState === 'STOPPED' || voiceState === 'MUTED');
  const voiceStatusLabel = audioState === 'BLOCKED'
    ? 'AUDIO BLOCKED'
    : voiceState === 'STOPPED'
      ? 'INCIDENT RESOLVED — VOICE ALERT STOPPED'
      : voiceState === 'MUTED'
        ? 'VOICE ALERT MUTED'
        : voiceState === 'ACTIVE'
          ? 'EMERGENCY VOICE ACTIVE'
          : audioState === 'READY'
            ? 'VOICE ALERT READY'
            : 'VOICE ALERT WAITING FOR AUDIO';

  return (
    <section className="panel-card operations-panel" style={{ marginBottom: '1rem' }}>
      <div className="panel-header">
        <div className="panel-title">REAL-TIME DEVICE CAPABILITIES</div>
        <span className="panel-tag">LOCAL BROWSER CAPABILITIES • EXTERNAL PROVIDERS OPTIONAL</span>
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
        <div className="ops-status-grid">
          <span className={`ops-status ${audioState === 'READY' ? 'real' : 'offline'}`}>AUDIO: {audioState === 'READY' ? 'READY' : audioState.replace('_', ' ')}</span>
          {audioState !== 'READY' && <button className="btn btn-danger" onClick={onEnableAudio} disabled={audioState === 'INITIALIZING'}>{audioState === 'INITIALIZING' ? 'INITIALIZING AUDIO...' : 'ENABLE AUDIO'}</button>}
          <span className={`ops-status ${gpsMode === 'OFFLINE' ? 'offline' : gpsMode === 'DEMO LOCATION' ? 'demo' : 'real'}`}>GPS: {gpsMode}</span>
          <span className={`ops-status ${wsState === 'CONNECTED' ? 'real' : 'offline'}`}>WEBSOCKET: {wsState}</span>
          <span className="ops-status real">IN-APP ALERT: {demoPushVisible ? 'ACTIVE' : 'READY'}</span>
        </div>

        {hasVoiceStatus && (
          <div className="voice-alert-strip" role="status">
            <div>
              <strong>{voiceStatusLabel}</strong>
              <small>REAL browser speaker • repeats while this emergency is active</small>
            </div>
            <div className="quick-actions-group">
              {audioState !== 'READY' && <button className="btn btn-danger" onClick={onEnableAudio} disabled={audioState === 'INITIALIZING'}>ENABLE AUDIO</button>}
              {active && voiceState !== 'MUTED' && <button className="btn btn-outline" onClick={onMute}>MUTE</button>}
              {active && voiceState === 'MUTED' && <button className="btn btn-outline" onClick={onUnmute}>UNMUTE</button>}
              {active && <button className="btn btn-outline" onClick={onReplay}>REPLAY</button>}
              {active && <button className="btn btn-danger" onClick={onStopVoice}>STOP ALERT</button>}
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
