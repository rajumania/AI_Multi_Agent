import React from 'react';
import { AlertTriangle, CheckCircle2 } from 'lucide-react';

interface DomainPlaceholderPageProps {
  title: string;
  description: string;
  phase: string;
}

export const DomainPlaceholderPage: React.FC<DomainPlaceholderPageProps> = ({ title, description, phase }) => (
  <div className="app-content">
    <div className="dashboard-title-row">
      <div>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
    </div>
    <section className="panel-card" style={{ padding: '2rem', maxWidth: 760 }}>
      <div className="panel-title"><AlertTriangle size={18} /> Foundation ready</div>
      <p style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>{phase}</p>
      <div style={{ display: 'flex', alignItems: 'center', gap: '.45rem', color: 'var(--success-700, #047857)', fontSize: '.82rem' }}>
        <CheckCircle2 size={15} /> Existing backend contracts remain available while this capability is implemented incrementally.
      </div>
    </section>
  </div>
);
