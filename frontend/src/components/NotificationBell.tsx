import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Bell, Check, CheckCheck, X } from 'lucide-react';
import { api } from '../services/api';
import { NotificationItem } from '../types';
import { recentNotifications, unreadNotificationCount } from '../portal/notificationPresentation';

export const NotificationBell: React.FC<{ refreshKey?: number }> = ({ refreshKey = 0 }) => {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setItems(await api.getNotifications());
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Unable to load notifications.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load, refreshKey]);

  const unread = useMemo(() => unreadNotificationCount(items), [items]);
  const markRead = async (item: NotificationItem) => {
    try {
      const updated = await api.markNotificationRead(item.id);
      setItems((previous) => previous.map((entry) => entry.id === updated.id ? updated : entry));
    } catch (err: any) {
      setError(err.message || 'Unable to mark notification read.');
    }
  };
  const markAllRead = async () => {
    try {
      const updated = await api.markAllNotificationsRead();
      const ids = new Set(updated.map((item) => item.id));
      setItems((previous) => previous.map((item) => ids.has(item.id) ? { ...item, read: 1 } : item));
    } catch (err: any) { setError(err.message || 'Unable to mark notifications read.'); }
  };

  return (
    <div className="notification-bell" style={{ position: 'relative' }}>
      <button className="notification-bell-button" aria-label="Notifications" onClick={() => setOpen((value) => !value)} style={{ position: 'relative', display: 'inline-flex', padding: '0.45rem', border: '1px solid #334155', borderRadius: 7, background: 'transparent', color: '#cbd5e1', cursor: 'pointer' }}>
        <Bell size={17} />
        {unread > 0 && <span style={{ position: 'absolute', top: -5, right: -5, minWidth: 16, height: 16, padding: '0 3px', borderRadius: 999, background: '#ef4444', color: '#fff', fontSize: 10, fontWeight: 800, display: 'grid', placeItems: 'center' }}>{unread > 99 ? '99+' : unread}</span>}
      </button>
      {open && <div className="notification-panel" style={{ position: 'absolute', zIndex: 30, top: 'calc(100% + 0.55rem)', right: 0, width: 320, maxWidth: '80vw', background: '#fff', color: '#0f172a', border: '1px solid #cbd5e1', borderRadius: 10, boxShadow: '0 12px 28px rgba(15,23,42,0.25)', padding: '0.7rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.45rem' }}><strong style={{ fontSize: '0.8rem' }}>Notifications</strong><div style={{ display: 'flex', gap: '.35rem', alignItems: 'center' }}>{unread > 0 && <button aria-label="Mark all notifications read" onClick={() => void markAllRead()} style={{ border: 0, background: 'transparent', color: '#0284c7', cursor: 'pointer' }}><CheckCheck size={14} /></button>}<button aria-label="Close notifications" onClick={() => setOpen(false)} style={{ border: 0, background: 'transparent', color: '#64748b', cursor: 'pointer' }}><X size={14} /></button></div></div>
        {loading && <div style={{ padding: '1rem', color: '#64748b', fontSize: '0.75rem' }}>Loading…</div>}
        {!loading && error && <div style={{ padding: '0.6rem', color: '#b91c1c', background: '#fef2f2', fontSize: '0.72rem', borderRadius: 6 }}>{error}</div>}
        {!loading && !error && items.length === 0 && <div style={{ padding: '1rem', color: '#64748b', fontSize: '0.75rem' }}>No recent notifications.</div>}
        {!loading && !error && recentNotifications(items, 20).map((item) => (
          <div key={item.id} style={{ padding: '0.55rem 0.25rem', borderBottom: '1px solid #e2e8f0', opacity: item.read ? 0.65 : 1 }}>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <span style={{ alignSelf: 'flex-start', marginTop: 2, padding: '2px 5px', borderRadius: 4, background: item.priority === 'critical' ? '#fee2e2' : item.priority === 'high' ? '#ffedd5' : '#e0f2fe', color: item.priority === 'critical' ? '#b91c1c' : item.priority === 'high' ? '#c2410c' : '#0369a1', fontSize: 9, fontWeight: 800 }}>{String(item.priority || item.level || 'medium').toUpperCase()}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: '0.72rem', fontWeight: 800 }}>{item.title}</div>
              <div style={{ marginTop: 2, fontSize: '0.68rem', color: '#475569', lineHeight: 1.35 }}>{item.message}</div>
              <div style={{ marginTop: 3, fontSize: '0.6rem', color: '#64748b' }}>{item.department || 'Operations'}{item.incident_id ? ` · ${item.incident_id}` : ''} · {new Date(item.created_at).toLocaleString()}</div>
              <div style={{ marginTop: 2, fontSize: '0.58rem', color: '#94a3b8' }}>Status: {item.lifecycle_status || (item.read ? 'READ' : 'CREATED')}</div>
            </div>
            {!item.read && (
              <button aria-label={`Mark ${item.title} read`} onClick={() => void markRead(item)} style={{ alignSelf: 'center', border: 0, background: 'transparent', color: '#0284c7', cursor: 'pointer' }}>
                <Check size={14} />
              </button>
            )}
            <button type="button" aria-label={`Show details for ${item.title}`} onClick={() => setExpandedId((value) => value === item.id ? null : item.id)} style={{ alignSelf: 'flex-start', border: 0, background: 'transparent', color: '#64748b', cursor: 'pointer', fontSize: 11 }}>{expandedId === item.id ? '−' : '+'}</button>
            </div>
            {expandedId === item.id && item.details && <div style={{ margin: '0.45rem 0 0 1.4rem', padding: '0.45rem', background: '#f8fafc', borderRadius: 6, fontSize: '0.62rem', color: '#334155', lineHeight: 1.45 }}>
              {Boolean(item.details.location_label) && <div><strong>Location:</strong> {String(item.details.location_label)}</div>}
              {(item.details.latitude !== undefined && item.details.longitude !== undefined) && <div><strong>Coordinates:</strong> {String(item.details.latitude)}, {String(item.details.longitude)}</div>}
              {Boolean(item.details.hazard_type) && <div><strong>Hazard:</strong> {String(item.details.hazard_type)}</div>}
              {(item.details.risk_level || item.details.risk_score !== undefined) && <div><strong>Risk:</strong> {String(item.details.risk_level || 'UNKNOWN')}{item.details.risk_score !== undefined ? ` (${String(item.details.risk_score)})` : ''}</div>}
              {Boolean(item.details.targeting_reason) && <div><strong>Why targeted:</strong> {String(item.details.targeting_reason)}</div>}
              {Boolean(item.details.approval_status) && <div><strong>Approval:</strong> {String(item.details.approval_status)}</div>}
              {Boolean(item.details.response_status) && <div><strong>Response:</strong> {String(item.details.response_status)}</div>}
              {Array.isArray(item.details.evidence_summary) && item.details.evidence_summary.length > 0 && <div><strong>Evidence:</strong> {(item.details.evidence_summary as unknown[]).map((value) => String(value)).join('; ')}</div>}
            </div>}
          </div>
        ))}
      </div>}
    </div>
  );
};
