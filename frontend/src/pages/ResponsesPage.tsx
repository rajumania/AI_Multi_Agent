import React, { useEffect, useState } from 'react';
import { RefreshCw, CheckCircle, XCircle, ShieldCheck, AlertTriangle } from 'lucide-react';

import { ResponsePlan } from '../types';
import { api } from '../services/api';

export const ResponsesPage: React.FC = () => {
  const [plans, setPlans] = useState<ResponsePlan[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [approvingId, setApprovingId] = useState<string | null>(null);

  const fetchPlans = async () => {
    setLoading(true);
    try {
      const data = await api.getResponsePlans();
      setPlans(data);
    } catch (e) {
      console.error('Failed to load response plans', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlans();
  }, []);

  const handleApprove = async (planId: string, decision: 'approve' | 'reject') => {
    setApprovingId(planId);
    try {
      await api.decideApproval(planId, {
        decision,
        operator_name: 'AITAM Response Commander',
        notes: decision === 'approve' ? 'Direct command authorization.' : 'Plan rejected from responses board.'
      });
      fetchPlans();
    } catch (e) {
      console.error('Approval failed', e);
    } finally {
      setApprovingId(null);
    }
  };

  const filtered = plans.filter((p) => {
    if (statusFilter !== 'all' && p.approval_status !== statusFilter) return false;
    return true;
  });

  return (
    <div className="app-content">
      <div className="dashboard-title-row">
        <div>
          <h2>Emergency Response Plans & Authorization Board</h2>
          <p>Operational action plans formulated from emergency assessments, response protocols, and verified resource coordination.</p>
        </div>

        <div className="quick-actions-group">
          <button className="btn btn-outline" onClick={fetchPlans} disabled={loading}>
            <RefreshCw size={15} className={loading ? 'spin' : ''} />
            <span>Sync Plans</span>
          </button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="filter-bar" style={{ marginBottom: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Status:</span>
          <select
            className="form-select-sm"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All Response Plans ({plans.length})</option>
            <option value="pending">⏳ Awaiting Approval ({plans.filter(p => p.approval_status === 'pending').length})</option>
            <option value="approved">✅ Approved ({plans.filter(p => p.approval_status === 'approved').length})</option>
            <option value="rejected">❌ Rejected ({plans.filter(p => p.approval_status === 'rejected').length})</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
          Loading response plans from database...
        </div>
      ) : filtered.length === 0 ? (
        <div className="panel-card" style={{ padding: '3rem', textAlign: 'center' }}>
          <AlertTriangle size={32} color="#94a3b8" style={{ margin: '0 auto 0.5rem' }} />
          <h3>No Response Plans Found</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Generate response plans from the Incidents dashboard to populate this board.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {filtered.map((plan) => {
            const isPending = plan.approval_status === 'pending';
            const isApproved = plan.approval_status === 'approved';
            return (
              <div key={plan.plan_id} className="panel-card" style={{ borderLeft: `4px solid ${isApproved ? '#16a34a' : isPending ? '#f59e0b' : '#dc2626'}` }}>
                <div className="panel-header" style={{ padding: '0.85rem 1.25rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <ShieldCheck size={18} color="#0284c7" />
                    <div>
                      <strong style={{ fontSize: '0.9375rem', color: 'var(--text-primary)' }}>{plan.title}</strong>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        Plan ID: {plan.plan_id} • Target Incident: <strong>{plan.incident_id}</strong> • Location: <strong>{plan.location}</strong>
                      </div>
                    </div>
                  </div>

                  <span className={`badge ${isApproved ? 'badge-approved' : isPending ? 'badge-high' : 'badge-rejected'}`}>
                    {plan.approval_status.toUpperCase()}
                  </span>
                </div>

                <div className="panel-body" style={{ padding: '1rem 1.25rem' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1.25rem' }}>
                    <div>
                      <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.35rem' }}>
                        Synthesized Action Plan:
                      </div>
                      <ol style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.8125rem', color: '#0f172a', display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                        {plan.recommended_actions.map((act, idx) => (
                          <li key={idx}>{act}</li>
                        ))}
                      </ol>
                    </div>

                    <div>
                      <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.35rem' }}>
                        Allocated MCP Assets:
                      </div>
                      <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
                        {plan.allocated_resources.map((rid) => (
                          <span key={rid} style={{ background: '#e0f2fe', color: '#0369a1', padding: '0.15rem 0.45rem', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 700 }}>
                            {rid}
                          </span>
                        ))}
                      </div>

                      {isPending ? (
                        <div style={{ display: 'flex', gap: '0.4rem' }}>
                          <button
                            className="btn btn-sm"
                            style={{ background: '#16a34a', color: '#ffffff', border: 'none', padding: '0.35rem 0.65rem' }}
                            disabled={approvingId === plan.plan_id}
                            onClick={() => handleApprove(plan.plan_id, 'approve')}
                          >
                            <CheckCircle size={13} />
                            <span>Approve</span>
                          </button>
                          <button
                            className="btn btn-sm btn-outline"
                            style={{ borderColor: '#dc2626', color: '#dc2626', padding: '0.35rem 0.65rem' }}
                            disabled={approvingId === plan.plan_id}
                            onClick={() => handleApprove(plan.plan_id, 'reject')}
                          >
                            <XCircle size={13} />
                            <span>Reject</span>
                          </button>
                        </div>
                      ) : (
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                          <div>By: <strong>{plan.approved_by || 'Commander'}</strong></div>
                          <div>Notes: {plan.approval_notes}</div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
