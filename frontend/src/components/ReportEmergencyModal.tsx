import React, { useState } from 'react';
import {
  AlertTriangle,
  X,
  Send,
  MapPin,
  HeartPulse
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

  if (!isOpen) return null;

  const campusLocationPresets = [
    'CSE Block',
    'Main Entrance Gate',
    'Science & Tech Hub',
    'Sports Complex Arena',
    'North Auditorium',
    'Central Medical Center',
    'Student Activity Center'
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
      onIncidentCreated(created);
      onClose();
      // Reset form
      setDescription('');
      setLocation('');
      setIsInjuredUnknown(true);
      setInjuredCount('');
    } catch (err: any) {
      setError(err.message || 'Failed to submit emergency report.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
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
                Official Emergency Intake Protocol • Real-time Agent Dispatch Ready
              </p>
            </div>
          </div>
          <button
            className="btn btn-outline"
            style={{ padding: '0.35rem', borderRadius: '50%' }}
            onClick={onClose}
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

          {/* Description */}
          <div className="form-group">
            <label className="form-label">
              Incident Description <span style={{ color: 'var(--danger-600)' }}>*</span>
            </label>
            <textarea
              className="form-textarea"
              rows={3}
              placeholder="E.g., Dense smoke and active flames observed coming from CSE Block 2nd floor lab. Alarm triggered."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              required
            />
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
                placeholder="E.g., CSE Block 2nd Floor, Room 204"
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
