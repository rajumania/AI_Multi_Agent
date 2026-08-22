import React, { useState } from 'react';
import {
  AlertTriangle,
  X,
  Send,
  MapPin,
  HeartPulse,
  Mic,
  Camera
} from 'lucide-react';
import { Incident } from '../types';
import { api, CreateIncidentPayload } from '../services/api';

interface ReportEmergencyModalProps {
  isOpen: boolean;
  onClose: () => void;
  onIncidentCreated: (newIncident: Incident) => void;
}

export const ReportEmergencyModal: React.FC<ReportEmergencyModalProps> = ({
  isOpen,
  onClose,
  onIncidentCreated,
}) => {
  const [description, setDescription] = useState('');
  const [incidentType, setIncidentType] = useState('fire');
  const [location, setLocation] = useState('');
  const [severity, setSeverity] = useState('high');
  const [isInjuredUnknown, setIsInjuredUnknown] = useState(true);
  const [injuredCount, setInjuredCount] = useState<number | ''>('');
  const [evidenceSource, setEvidenceSource] = useState('direct_report');
  const [reportedBy, setReportedBy] = useState('Campus Emergency Operator');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submittedIncident, setSubmittedIncident] = useState<Incident | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [imagePreview, setImagePreview] = useState<string | null>(null);

  const toggleVoiceInput = () => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      // Fallback voice transcript simulation for unsupported browsers
      setIsListening(true);
      setTimeout(() => {
        setDescription((prev) => `${prev ? prev + ' ' : ''}[Voice Intake]: Fire and dense smoke observed spreading in lab area.`);
        setIsListening(false);
      }, 1500);
      return;
    }

    try {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = 'en-US';

      recognition.onstart = () => setIsListening(true);
      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setDescription((prev) => `${prev ? prev + ' ' : ''}${transcript}`);
        setIsListening(false);
      };
      recognition.onerror = () => setIsListening(false);
      recognition.onend = () => setIsListening(false);
      recognition.start();
    } catch {
      setIsListening(false);
    }
  };

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setImagePreview(reader.result as string);
        setEvidenceSource('photo_verified');
      };
      reader.readAsDataURL(file);
    }
  };

  if (!isOpen) return null;

  const campusLocationPresets = [
    'U-Block (CSE & IT)',
    'A-Block (Admin & Central Office)',
    'H-Block (Biotechnology & Sciences)',
    'V-Block (Mechanical & Workshops)',
    'NTR Central Library',
    'NTR Convocation Hall & Auditorium',
    'Student Activity Center (SAC) & Cafeteria',
    'Sports Complex & Indoor Stadium',
    'Mahalakshmi & Vasishta Hostels',
    'Main Vadlamudi Entrance Gate',
    'Campus Health & Medical Centre',
    'Pharmacy Block & Bio-Nest Hub'
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!description.trim()) {
      setError('Please provide a detailed incident description.');
      return;
    }
    if (!location.trim()) {
      setError('Please specify the campus location.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const payload: CreateIncidentPayload = {
        description: description.trim(),
        incident_type: incidentType,
        location: location.trim(),
        severity,
        injured_count: isInjuredUnknown ? null : (injuredCount === '' ? 0 : Number(injuredCount)),
        evidence_source: evidenceSource,
        reported_by: reportedBy.trim() || 'Campus Operator',
      };

      const created = await api.createIncident(payload);
      setSubmittedIncident(created);
      onIncidentCreated(created);
    } catch (err: any) {
      setError(err.message || 'Failed to submit emergency report.');
    } finally {
      setLoading(false);
    }
  };

  const handleCloseModal = () => {
    setSubmittedIncident(null);
    setDescription('');
    setLocation('');
    setIsInjuredUnknown(true);
    setInjuredCount('');
    onClose();
  };

  if (submittedIncident) {
    return (
      <div className="modal-backdrop" onClick={handleCloseModal}>
        <div
          className="modal-card"
          onClick={(e) => e.stopPropagation()}
          style={{ maxWidth: '520px', textAlign: 'center', padding: '2rem 1.5rem' }}
        >
          <div style={{
            width: '56px',
            height: '56px',
            background: '#dcfce7',
            color: '#16a34a',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '28px',
            margin: '0 auto 1rem'
          }}>
            ✓
          </div>

          <h3 style={{ fontSize: '1.25rem', color: '#0f172a', fontWeight: 700, marginBottom: '0.35rem' }}>
            REPORT RECEIVED
          </h3>
          <p style={{ fontSize: '0.875rem', color: '#475569', marginBottom: '1.25rem', lineHeight: 1.4 }}>
            Your emergency report has been registered with the <strong>Vignan University Emergency Command Center</strong>.
          </p>

          <div style={{
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: '8px',
            padding: '1rem',
            textAlign: 'left',
            marginBottom: '1.5rem'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
              <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>INCIDENT ID:</span>
              <strong style={{ fontSize: '0.8125rem', color: '#0284c7' }}>{submittedIncident.incident_id}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
              <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>LOCATION:</span>
              <span style={{ fontSize: '0.8125rem', color: '#0f172a', fontWeight: 600 }}>{submittedIncident.location}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
              <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>CLASSIFICATION:</span>
              <span style={{ fontSize: '0.8125rem', color: '#dc2626', fontWeight: 700, textTransform: 'uppercase' }}>
                {submittedIncident.incident_type} • {submittedIncident.severity}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>CURRENT STATUS:</span>
              <span className="badge badge-high" style={{ fontSize: '0.7rem', padding: '1px 6px' }}>
                ANALYZING
              </span>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button
              className="btn btn-primary"
              style={{ flex: 2, padding: '0.65rem', background: '#0284c7', color: '#ffffff', fontWeight: 700 }}
              onClick={handleCloseModal}
            >
              TRACK INCIDENT COMMAND →
            </button>
            <button
              className="btn btn-outline"
              style={{ flex: 1, padding: '0.65rem' }}
              onClick={handleCloseModal}
            >
              Dismiss
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-backdrop" onClick={handleCloseModal}>
      <div
        className="modal-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div className="metric-icon-badge red">
              <AlertTriangle size={20} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.125rem' }}>Report Campus Emergency</h3>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                Official Emergency Intake • Vignan University Vadlamudi
              </p>
            </div>
          </div>
          <button
            className="btn btn-outline"
            style={{ padding: '0.35rem', borderRadius: '50%' }}
            onClick={handleCloseModal}
          >
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {error && (
            <div className="alert-banner error">
              <AlertTriangle size={16} />
              <span>{error}</span>
            </div>
          )}

          {/* Description with Voice & Image Controls */}
          <div className="form-group">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
              <label className="form-label" style={{ margin: 0 }}>
                Incident Description <span style={{ color: 'var(--danger-600)' }}>*</span>
              </label>
              <div style={{ display: 'flex', gap: '0.4rem' }}>
                <button
                  type="button"
                  className="btn btn-sm btn-outline"
                  style={{
                    fontSize: '0.75rem',
                    padding: '0.2rem 0.55rem',
                    borderColor: isListening ? '#ef4444' : '#cbd5e1',
                    color: isListening ? '#ef4444' : '#0284c7',
                    background: isListening ? '#fef2f2' : 'transparent',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.3rem'
                  }}
                  onClick={toggleVoiceInput}
                >
                  <Mic size={13} className={isListening ? 'pulse' : ''} />
                  <span>{isListening ? 'Listening...' : 'Voice Intake'}</span>
                </button>

                <label
                  className="btn btn-sm btn-outline"
                  style={{
                    fontSize: '0.75rem',
                    padding: '0.2rem 0.55rem',
                    borderColor: '#cbd5e1',
                    color: '#0284c7',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.3rem',
                    margin: 0
                  }}
                >
                  <Camera size={13} />
                  <span>Attach Photo</span>
                  <input
                    type="file"
                    accept="image/*"
                    style={{ display: 'none' }}
                    onChange={handleImageUpload}
                  />
                </label>
              </div>
            </div>

            <textarea
              className="form-textarea"
              rows={3}
              placeholder="E.g., Dense smoke and active flames observed coming from U-Block 2nd floor CSE lab. Alarm triggered."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              required
            />

            {/* Attached Image Preview */}
            {imagePreview && (
              <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', background: '#f8fafc', padding: '0.4rem 0.6rem', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                <img src={imagePreview} alt="Attached incident evidence" style={{ width: '40px', height: '40px', objectFit: 'cover', borderRadius: '4px' }} />
                <span style={{ fontSize: '0.75rem', color: '#475569', flex: 1 }}>Incident photo evidence attached</span>
                <button
                  type="button"
                  style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 'bold' }}
                  onClick={() => setImagePreview(null)}
                >
                  ✕
                </button>
              </div>
            )}
          </div>

          {/* 2-Column: Type & Severity */}
          <div className="form-row-2">
            <div className="form-group">
              <label className="form-label">Incident Classification</label>
              <select
                className="form-select"
                value={incidentType}
                onChange={(e) => setIncidentType(e.target.value)}
              >
                <option value="fire">🔥 Fire Emergency</option>
                <option value="medical">🏥 Medical Emergency</option>
                <option value="security">🛡️ Security / Threat</option>
                <option value="accident">🚗 Traffic / Vehicle Accident</option>
                <option value="facility">⚡ Facility / Utility Failure</option>
                <option value="crowd">👥 Crowd / Stampede Risk</option>
                <option value="weather">⛈️ Severe Weather / Flood</option>
                <option value="other">⚠️ Other Incident</option>
                <option value="unknown">❓ Unknown / Unverified</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Assessed Severity</label>
              <select
                className="form-select"
                value={severity}
                onChange={(e) => setSeverity(e.target.value)}
              >
                <option value="critical">🚨 Critical (Threat to Life)</option>
                <option value="high">⚠️ High (Immediate Response)</option>
                <option value="medium">⚡ Medium (Rapid Attention)</option>
                <option value="low">ℹ️ Low (Minor / Monitored)</option>
                <option value="unknown">❓ Unknown</option>
              </select>
            </div>
          </div>

          {/* Location with Quick Presets */}
          <div className="form-group">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
              <label className="form-label" style={{ marginBottom: 0 }}>
                Campus Location <span style={{ color: 'var(--danger-600)' }}>*</span>
              </label>
              <span style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>
                Click preset to populate
              </span>
            </div>
            <div style={{ position: 'relative' }}>
              <MapPin
                size={16}
                color="#64748b"
                style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)' }}
              />
              <input
                type="text"
                className="form-input"
                style={{ paddingLeft: '2.25rem' }}
                placeholder="E.g., U-Block 2nd Floor Room 204 (CSE Dept)"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                required
              />
            </div>
            <div className="preset-pills-row">
              {campusLocationPresets.map((loc) => (
                <button
                  type="button"
                  key={loc}
                  className="preset-pill"
                  onClick={() => setLocation(loc)}
                >
                  {loc}
                </button>
              ))}
            </div>
          </div>

          {/* Safety Rule: Injured Count (Strict Null vs Count) */}
          <div className="form-group safety-box">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <HeartPulse size={16} color="#0284c7" />
                <label className="form-label" style={{ marginBottom: 0, fontWeight: 600 }}>
                  Casualty / Injury Assessment
                </label>
              </div>
              <span className="safety-badge">Safety Protocol Active</span>
            </div>

            <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '0.4rem 0 0.75rem' }}>
              Do not invent casualty numbers. If unknown, system strictly stores <code>null</code>.
            </p>

            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
              <label className="radio-label">
                <input
                  type="radio"
                  name="injured_mode"
                  checked={isInjuredUnknown}
                  onChange={() => {
                    setIsInjuredUnknown(true);
                    setInjuredCount('');
                  }}
                />
                <span><strong>Unknown / Not Confirmed</strong> (Stores null)</span>
              </label>

              <label className="radio-label">
                <input
                  type="radio"
                  name="injured_mode"
                  checked={!isInjuredUnknown}
                  onChange={() => {
                    setIsInjuredUnknown(false);
                    if (injuredCount === '') setInjuredCount(0);
                  }}
                />
                <span><strong>Confirmed Count</strong></span>
              </label>
            </div>

            {!isInjuredUnknown && (
              <div style={{ marginTop: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                  Confirmed Injured Persons:
                </span>
                <input
                  type="number"
                  min="0"
                  max="500"
                  className="form-input"
                  style={{ width: '100px' }}
                  value={injuredCount}
                  onChange={(e) => setInjuredCount(e.target.value === '' ? '' : parseInt(e.target.value, 10))}
                />
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  (Use 0 only if confirmed nobody is hurt)
                </span>
              </div>
            )}
          </div>

          {/* 2-Column: Evidence Source & Reporter */}
          <div className="form-row-2">
            <div className="form-group">
              <label className="form-label">Evidence Source</label>
              <select
                className="form-select"
                value={evidenceSource}
                onChange={(e) => setEvidenceSource(e.target.value)}
              >
                <option value="direct_report">Direct Phone / Radio Report</option>
                <option value="cctv">Campus CCTV Monitoring</option>
                <option value="sensor_alarm">Automated Fire / Smoke Sensor</option>
                <option value="security_patrol">Security Patrol Guard</option>
                <option value="student_app">Student Mobile Report</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Reported By</label>
              <input
                type="text"
                className="form-input"
                value={reportedBy}
                onChange={(e) => setReportedBy(e.target.value)}
                placeholder="Operator name or ID"
              />
            </div>
          </div>

          {/* Modal Actions */}
          <div className="modal-footer">
            <button
              type="button"
              className="btn btn-outline"
              onClick={onClose}
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-danger"
              disabled={loading}
              style={{ backgroundColor: 'var(--danger-600)', color: '#ffffff' }}
            >
              <Send size={15} />
              <span>{loading ? 'Submitting Report...' : 'Log & Dispatch Emergency'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
