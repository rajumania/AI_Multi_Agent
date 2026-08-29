import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  X,
  Send,
  MapPin,
  LocateFixed,
  HeartPulse,
  Mic,
  Camera
} from 'lucide-react';
import { CampusLocation, Incident, IntelligencePreview } from '../types';
import { api, CreateIncidentPayload } from '../services/api';
import { LocationPicker, SelectedLocation } from './LocationPicker';
import { isOfflineNetworkError, queueIncidentReport } from '../services/offlineSync';

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
  const [disasterType, setDisasterType] = useState('other');
  const [location, setLocation] = useState('');
  const [severity, setSeverity] = useState('high');
  const [isInjuredUnknown, setIsInjuredUnknown] = useState(true);
  const [injuredCount, setInjuredCount] = useState<number | ''>('');
  const [evidenceSource, setEvidenceSource] = useState('direct_report');
  const [reportedBy, setReportedBy] = useState('Community Reporter');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submittedIncident, setSubmittedIncident] = useState<Incident | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [imageEvidenceRef, setImageEvidenceRef] = useState<string | null>(null);
  const [imageUploadStatus, setImageUploadStatus] = useState<'idle' | 'uploading' | 'stored' | 'failed'>('idle');
  const [campusLocations, setCampusLocations] = useState<CampusLocation[]>([]);
  const [zoneLocations, setZoneLocations] = useState<CampusLocation[]>([]);
  const [zoneRegions, setZoneRegions] = useState<Record<string, string>>({});
  const [selectedLocation, setSelectedLocation] = useState<SelectedLocation | null>(null);
  const [selectedZone, setSelectedZone] = useState<{ id: string; region_id: string } | null>(null);
  const [locationConfirmed, setLocationConfirmed] = useState(false);
  const [gpsState, setGpsState] = useState<'idle' | 'requesting' | 'ready' | 'denied'>('idle');
  const [gpsError, setGpsError] = useState<string | null>(null);
  const [analysisPreview, setAnalysisPreview] = useState<IntelligencePreview | null>(null);

  // Keep hook order stable when the modal opens and closes. This memo used to
  // sit below the closed-modal early return, which caused a render-time Hooks
  // error on the first Community report attempt.
  const locationOptions = useMemo(() => [...campusLocations, ...zoneLocations], [campusLocations, zoneLocations]);

  useEffect(() => {
    if (!isOpen) return;
    Promise.all([api.getCampusLocations(), api.getZones()]).then(([locations, zones]) => {
      setCampusLocations(locations);
      setZoneLocations(zones.map((zone: any) => ({ location_id: zone.id, name: zone.name, kind: 'disaster_zone', latitude: zone.latitude, longitude: zone.longitude, aliases: [], coordinate_source: 'backend zone', verification_status: 'backend-provided' })));
      setZoneRegions(Object.fromEntries(zones.map((zone: any) => [zone.id, zone.region_id])));
    }).catch(() => { setCampusLocations([]); setZoneLocations([]); setZoneRegions({}); });
  }, [isOpen]);

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
      setImageEvidenceRef(null);
      setAnalysisPreview(null);
      setError(null);
      setImageUploadStatus('uploading');
      const reader = new FileReader();
      reader.onloadend = () => {
        setImagePreview(reader.result as string);
      };
      reader.readAsDataURL(file);
      void api.uploadEvidence(file).then((stored) => {
        setImageEvidenceRef(stored.reference);
        setEvidenceSource('community_upload');
        setImageUploadStatus('stored');
      }).catch((uploadError: any) => {
        setImageUploadStatus('failed');
        setError(uploadError?.message || 'Evidence upload failed. The image was not attached to the report.');
      });
    }
  };

  const useCurrentLocation = () => {
    if (!navigator.geolocation) {
      setGpsState('denied');
      setGpsError('This browser does not expose geolocation. Select a map location manually.');
      return;
    }
    setGpsState('requesting');
    setGpsError(null);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const latitude = position.coords.latitude;
        const longitude = position.coords.longitude;
        setSelectedLocation({ latitude, longitude, label: `Current device location (${latitude.toFixed(6)}, ${longitude.toFixed(6)})` });
        setSelectedZone(null);
        setLocation(`Current device location (${latitude.toFixed(6)}, ${longitude.toFixed(6)})`);
        setLocationConfirmed(false);
        setGpsState('ready');
      },
      (positionError) => {
        setGpsState('denied');
        setGpsError(positionError.code === positionError.PERMISSION_DENIED ? 'Location permission was denied. Select a map location manually.' : 'The browser could not determine your location.');
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
    );
  };

  if (!isOpen) return null;

  const buildAnalysisPayload = () => {
    if (!selectedLocation) return null;
    return {
      description: description.trim(), incident_type: incidentType, disaster_type: disasterType,
      location: location.trim() || `Coordinates ${selectedLocation.latitude.toFixed(6)}, ${selectedLocation.longitude.toFixed(6)}`,
      severity, injured_count: isInjuredUnknown ? null : (injuredCount === '' ? 0 : Number(injuredCount)),
      evidence_source: evidenceSource, reported_by: reportedBy.trim() || 'Community Reporter',
      image_url: imageEvidenceRef || undefined, latitude: selectedLocation.latitude, longitude: selectedLocation.longitude,
      ...(selectedZone ? { zone_id: selectedZone.id, region_id: selectedZone.region_id } : {}),
    };
  };

  const analyzeIncident = async () => {
    const payload = buildAnalysisPayload();
    if (!payload || !payload.description || !payload.location) {
      setError('Provide a description and select an exact location before analysis.');
      return;
    }
    if (imagePreview && !imageEvidenceRef) {
      setError('Wait for the evidence upload to finish before analyzing the incident.');
      return;
    }
    setLoading(true); setError(null);
    try { setAnalysisPreview(await api.previewIntelligence(payload)); }
    catch (err: any) { setError(err.message || 'Could not analyze the selected location.'); }
    finally { setLoading(false); }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!description.trim()) {
      setError('Please provide a detailed incident description.');
      return;
    }
    if (!location.trim()) {
      setError('Please specify the incident location.');
      return;
    }
    if (!selectedLocation) {
      setError('Select a map location or capture your exact GPS coordinates before sending.');
      return;
    }
    if (!locationConfirmed) {
      setError('Confirm the selected location before sending the emergency report.');
      return;
    }
    if (!analysisPreview) {
      setError('Analyze the incident before submitting it.');
      return;
    }
    if (imagePreview && !imageEvidenceRef) {
      setError('Wait for the evidence upload to finish before submitting the report.');
      return;
    }

    setLoading(true);
    setError(null);

    const payload: CreateIncidentPayload = {
      description: description.trim(),
      incident_type: incidentType,
      location: location.trim(),
      severity,
      injured_count: isInjuredUnknown ? null : (injuredCount === '' ? 0 : Number(injuredCount)),
      evidence_source: evidenceSource,
      reported_by: reportedBy.trim() || 'Community Reporter',
      ...(disasterType !== 'other' ? { disaster_type: disasterType } : {}),
      ...(selectedZone ? { zone_id: selectedZone.id, region_id: selectedZone.region_id } : {}),
      ...(imageEvidenceRef ? { image_url: imageEvidenceRef } : {}),
      ...(selectedLocation ? { latitude: selectedLocation.latitude, longitude: selectedLocation.longitude } : {}),
    };

    try {
      const created = await api.createIncident(payload);
      setSubmittedIncident(created);
      onIncidentCreated(created);
    } catch (err: any) {
      if (isOfflineNetworkError(err)) {
        try {
          const queued = await queueIncidentReport(payload);
          setSubmittedIncident(queued.incident);
          onIncidentCreated(queued.incident);
          return;
        } catch {
          setError('You are offline and this device could not save the report. Please try again.');
        }
      } else {
        setError(err.message || 'Failed to submit emergency report.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCloseModal = () => {
    setSubmittedIncident(null);
    setDescription('');
    setLocation('');
    setSelectedLocation(null);
    setSelectedZone(null);
    setImagePreview(null);
    setImageEvidenceRef(null);
    setImageUploadStatus('idle');
    setLocationConfirmed(false);
    setGpsState('idle');
    setGpsError(null);
    setAnalysisPreview(null);
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
            {submittedIncident.sync_state === 'queued' ? 'REPORT SAVED OFFLINE' : 'REPORT RECEIVED'}
          </h3>
          <p style={{ fontSize: '0.875rem', color: '#475569', marginBottom: '1.25rem', lineHeight: 1.4 }}>
            {submittedIncident.sync_state === 'queued'
              ? <>Your report is safely queued on this device and will be sent to the <strong>AITAM Disaster Response Command Center</strong> when connectivity returns.</>
              : <>Your emergency report has been registered with the <strong>AITAM Disaster Response Command Center</strong>.</>}
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
                {submittedIncident.sync_state === 'queued' ? 'QUEUED OFFLINE' : 'ANALYZING'}
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
              <h3 style={{ fontSize: '1.125rem' }}>Report Disaster Event</h3>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                Official Emergency Intake • AITAM Disaster Response Network
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
              onChange={(e) => { setDescription(e.target.value); setAnalysisPreview(null); }}
              required
            />

            {/* Attached Image Preview */}
            {imagePreview && (
              <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', background: '#f8fafc', padding: '0.4rem 0.6rem', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                <img src={imagePreview} alt="Attached incident evidence" style={{ width: '40px', height: '40px', objectFit: 'cover', borderRadius: '4px' }} />
                <span style={{ fontSize: '0.75rem', color: imageUploadStatus === 'failed' ? '#b91c1c' : '#475569', flex: 1 }}>
                  {imageUploadStatus === 'uploading' ? 'Uploading evidence…' : imageUploadStatus === 'stored' ? 'Evidence uploaded securely · ready for analysis' : 'Evidence upload failed · image was not attached'}
                </span>
                <button
                  type="button"
                  style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 'bold' }}
                  onClick={() => { setImagePreview(null); setImageEvidenceRef(null); setImageUploadStatus('idle'); setAnalysisPreview(null); setEvidenceSource('direct_report'); }}
                >
                  ✕
                </button>
              </div>
            )}
          </div>

          {/* 2-Column: Type & Severity */}
          <div className="form-row-2">
            <div className="form-group">
              <label className="form-label">Disaster Type</label>
              <select
                className="form-select"
                value={disasterType}
                onChange={(e) => {
                  const next = e.target.value;
                  setDisasterType(next);
                  setAnalysisPreview(null);
                  setIncidentType(next === 'fire' ? 'fire' : next === 'other' ? 'other' : 'weather');
                }}
              >
                <option value="flood">Flood</option>
                <option value="landslide">Landslide</option>
                <option value="cyclone">Cyclone / Severe Weather</option>
                <option value="earthquake">Earthquake</option>
                <option value="urban_flood">Urban Flooding</option>
                <option value="fire">Fire</option>
                <option value="other">Other Hazard</option>
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
                Incident Location <span style={{ color: 'var(--danger-600)' }}>*</span>
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
                placeholder="Enter a place label or use exact coordinates"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                required
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '.55rem', marginTop: '.55rem', flexWrap: 'wrap' }}>
              <button type="button" className="btn btn-sm btn-outline" onClick={useCurrentLocation} disabled={gpsState === 'requesting'} style={{ display: 'inline-flex', alignItems: 'center', gap: '.3rem', color: '#0369a1' }}><LocateFixed size={14} /> {gpsState === 'requesting' ? 'Requesting GPS…' : 'Use my exact GPS location'}</button>
              {gpsState === 'ready' && <span style={{ fontSize: '.7rem', color: '#166534', fontWeight: 700 }}>GPS captured; confirm before sending.</span>}
              {gpsError && <span style={{ fontSize: '.7rem', color: '#b91c1c' }}>{gpsError}</span>}
            </div>
            <div className="preset-pills-row">
              {locationOptions.map((loc) => (
                <button
                  type="button"
                  key={loc.location_id}
                  className="preset-pill"
                  onClick={() => {
                    setLocation(loc.name);
                    const zone = zoneLocations.find((item) => item.location_id === loc.location_id);
                    if (zone) setSelectedZone({ id: zone.location_id, region_id: zoneRegions[zone.location_id] || '' });
                    setSelectedLocation({ latitude: loc.latitude, longitude: loc.longitude, label: loc.name });
                      setLocationConfirmed(true);
                  }}
                >
                  {loc.name}
                </button>
              ))}
            </div>
            <div style={{ marginTop: '0.8rem' }}>
              <LocationPicker locations={locationOptions} value={selectedLocation} onChange={(value) => { setSelectedLocation(value); setSelectedZone(null); setLocationConfirmed(false); setAnalysisPreview(null); }} />
              {selectedLocation && (
                <button type="button" onClick={() => { setLocationConfirmed(true); if (selectedLocation.label) setLocation(selectedLocation.label); }} style={{ marginTop: '0.55rem', width: '100%', border: '1px solid #0284c7', borderRadius: 7, background: locationConfirmed ? '#dcfce7' : '#0284c7', color: locationConfirmed ? '#166534' : '#fff', padding: '0.5rem', fontSize: '0.72rem', fontWeight: 800, cursor: 'pointer' }}>
                  {locationConfirmed ? 'LOCATION CONFIRMED' : 'CONFIRM LOCATION'}
                </button>
              )}
            </div>
          </div>

          {analysisPreview && (
            <div style={{ marginTop: '.75rem', padding: '.8rem', border: '1px solid #bae6fd', borderRadius: 8, background: '#f0f9ff', fontSize: '.75rem', color: '#0f172a' }}>
              <strong>ANALYSIS RESULT · {analysisPreview.data_status}</strong>
              <div>Location: {analysisPreview.reverse_geocode?.label || analysisPreview.location} ({analysisPreview.latitude.toFixed(6)}, {analysisPreview.longitude.toFixed(6)})</div>
              <div>Weather: {analysisPreview.weather.condition} · {analysisPreview.weather.status} · {analysisPreview.weather.source}</div>
              <div>Earthquakes: {analysisPreview.earthquake_status === 'NO_QUALIFYING_EVENT' ? 'No qualifying earthquake detected in the configured window.' : `${analysisPreview.earthquakes.length} qualifying event(s)`}</div>
              <div>Severe weather: {analysisPreview.severe_weather_status} · {analysisPreview.severe_weather.length} warning(s)</div>
              <div style={{ marginTop: 4, fontWeight: 800 }}>Risk: {String(analysisPreview.risk.level).toUpperCase()} · {analysisPreview.risk.score}/100 · confidence {analysisPreview.risk.confidence}</div>
              <div>Reasons: {analysisPreview.risk.contributing_factors?.join(' · ') || 'Limited available evidence'}</div>
              <div>Departments: {analysisPreview.departments.map((item) => item.department).join(', ') || 'None recommended'}</div>
              {analysisPreview.image_analysis.status === 'LIVE' ? (
                <div>Image evidence: LIVE · {analysisPreview.image_analysis.provider} · confidence {Math.round(Number(analysisPreview.image_analysis.confidence || 0) * 100)}% · supporting evidence only</div>
              ) : analysisPreview.image_analysis.status === 'IMAGE_ANALYSIS_UNAVAILABLE' ? (
                <div>Image evidence: IMAGE_ANALYSIS_UNAVAILABLE · {analysisPreview.image_analysis.error || 'No backend vision provider is configured.'}</div>
              ) : imageEvidenceRef ? (
                <div>Image evidence: {analysisPreview.image_analysis.status || 'NOT_PROVIDED'} · uploaded reference retained</div>
              ) : null}
          </div>
          )}

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
                <option value="cctv">Area CCTV Monitoring</option>
                <option value="sensor_alarm">Automated Fire / Smoke Sensor</option>
                <option value="security_patrol">Security Patrol Guard</option>
                <option value="community_mobile">Community Mobile Report</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Reported By</label>
              <input
                type="text"
                className="form-input"
                value={reportedBy}
                onChange={(e) => setReportedBy(e.target.value)}
                placeholder="Reporter name or ID"
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
            <button type="button" className="btn btn-outline" onClick={analyzeIncident} disabled={loading} style={{ color: '#0369a1', borderColor: '#7dd3fc' }}>
              {loading ? 'Analyzing…' : 'Analyze Incident'}
            </button>
            <button
              type="submit"
              className="btn btn-danger"
              disabled={loading}
              style={{ backgroundColor: 'var(--danger-600)', color: '#ffffff' }}
            >
              <Send size={15} />
              <span>{loading ? 'Working...' : 'Submit Emergency'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
