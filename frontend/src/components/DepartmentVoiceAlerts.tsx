import React, { useEffect, useMemo, useState } from 'react';
import { BellRing, Volume2, VolumeX } from 'lucide-react';
import { buildSafeVoiceMessage, shouldVoiceAlert } from '../services/voiceAlert';

export interface DepartmentAlert {
  notificationId?: number;
  title: string;
  message: string;
  level: string;
  incidentId?: string;
  department: string;
}

const ENABLED_KEY = 'campusflow.department.voice.enabled';
const MUTED_KEY = 'campusflow.department.voice.muted';

function speechAvailable() {
  return typeof window !== 'undefined' && typeof window.speechSynthesis !== 'undefined' && typeof window.SpeechSynthesisUtterance !== 'undefined';
}

export const DepartmentVoiceAlerts: React.FC<{ alert: DepartmentAlert | null; onAcknowledge: () => void }> = ({ alert, onAcknowledge }) => {
  const [enabled, setEnabled] = useState(() => localStorage.getItem(ENABLED_KEY) === 'true');
  const [muted, setMuted] = useState(() => localStorage.getItem(MUTED_KEY) === 'true');
  const [status, setStatus] = useState<'ready' | 'blocked' | 'fallback'>('ready');
  const voiceText = useMemo(() => alert ? buildSafeVoiceMessage(alert) : '', [alert]);

  const playFallbackTone = () => {
    try {
      const AudioContextConstructor = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AudioContextConstructor) { setStatus('fallback'); return; }
      const context = new AudioContextConstructor();
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.frequency.value = 740;
      gain.gain.value = 0.04;
      oscillator.connect(gain); gain.connect(context.destination);
      oscillator.start(); oscillator.stop(context.currentTime + 0.16);
      setStatus('fallback');
    } catch { setStatus('fallback'); }
  };

  const speak = () => {
    if (!alert || !shouldVoiceAlert(alert, enabled, muted)) return;
    if (!speechAvailable()) { playFallbackTone(); return; }
    try {
      window.speechSynthesis.cancel();
      const utterance = new window.SpeechSynthesisUtterance(voiceText);
      utterance.rate = 0.95;
      utterance.onstart = () => setStatus('ready');
      utterance.onerror = () => { setStatus('blocked'); playFallbackTone(); };
      window.speechSynthesis.speak(utterance);
    } catch { setStatus('blocked'); playFallbackTone(); }
  };

  useEffect(() => { speak(); }, [alert, enabled, muted]);

  const enable = () => {
    setEnabled(true); localStorage.setItem(ENABLED_KEY, 'true');
    if (speechAvailable()) {
      try { window.speechSynthesis.cancel(); window.speechSynthesis.speak(new window.SpeechSynthesisUtterance('Emergency alerts enabled.')); } catch { setStatus('blocked'); }
    } else setStatus('fallback');
  };
  const toggleMute = () => { const next = !muted; setMuted(next); localStorage.setItem(MUTED_KEY, String(next)); if (next && speechAvailable()) window.speechSynthesis.cancel(); };

  if (!alert) return <div style={{ display: 'flex', gap: '.35rem', alignItems: 'center', justifyContent: 'flex-end', flexWrap: 'wrap', marginBottom: '.65rem' }}>{!enabled && <button onClick={enable} style={controlStyle}>Enable Emergency Alerts</button>}{enabled && <><button onClick={toggleMute} style={controlStyle}>{muted ? <VolumeX size={13} /> : <Volume2 size={13} />} {muted ? 'Unmute' : 'Mute'}</button><button onClick={speak} style={controlStyle}>Test Alert</button></>}{status !== 'ready' && <small style={{ color: '#b45309' }}>{status === 'fallback' ? 'Sound fallback active' : 'Speech blocked; check browser permissions'}</small>}</div>;
  return <section aria-live="assertive" style={{ marginBottom: '.85rem', padding: '.8rem', border: '1px solid #fca5a5', borderLeft: '4px solid #dc2626', borderRadius: 10, background: '#fff1f2', boxShadow: '0 8px 18px rgba(127,29,29,.08)' }}>
    <div style={{ display: 'flex', gap: '.5rem', alignItems: 'flex-start' }}><BellRing size={18} color="#b91c1c" /><div style={{ flex: 1 }}><strong style={{ display: 'block', color: '#991b1b', fontSize: '.8rem' }}>NEW EMERGENCY ASSIGNMENT</strong><div style={{ marginTop: '.3rem', color: '#7f1d1d', fontSize: '.75rem', fontWeight: 700 }}>{alert.title}</div><div style={{ marginTop: '.2rem', color: '#7f1d1d', fontSize: '.72rem' }}>{alert.message}</div><div style={{ display: 'flex', gap: '.35rem', flexWrap: 'wrap', marginTop: '.55rem' }}>
      {!enabled && <button onClick={enable} style={controlStyle}>Enable Emergency Alerts</button>}
      {enabled && <><button onClick={toggleMute} style={controlStyle}>{muted ? <VolumeX size={13} /> : <Volume2 size={13} />} {muted ? 'Unmute' : 'Mute'}</button><button onClick={speak} style={controlStyle}>Test Alert</button></>}
      <button onClick={onAcknowledge} style={{ ...controlStyle, background: '#991b1b', color: '#fff', borderColor: '#991b1b' }}>Acknowledge</button>
    </div>{status !== 'ready' && <small style={{ display: 'block', marginTop: '.4rem', color: '#b45309' }}>{status === 'fallback' ? 'Speech unavailable; visual and sound alert remain active.' : 'Browser speech was blocked; enable alerts from a user gesture.'}</small>}</div></div>
  </section>;
};

const controlStyle: React.CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: '.25rem', border: '1px solid #fecaca', borderRadius: 7, background: '#fff', color: '#991b1b', padding: '.32rem .5rem', fontSize: '.67rem', fontWeight: 800, cursor: 'pointer' };
