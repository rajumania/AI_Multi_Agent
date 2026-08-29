import React, { useState } from 'react';
import { HelpCircle, ChevronDown, ChevronUp } from 'lucide-react';

interface SeverityBreakdownItem {
  factor: string;
  points: number;
  rationale: string;
}

interface ExplainabilityCardProps {
  severity: string;
  score?: number;
  explanation?: string;
  breakdown?: SeverityBreakdownItem[];
}

export const ExplainabilityCard: React.FC<ExplainabilityCardProps> = ({
  severity,
  score,
  explanation,
  breakdown
}) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div style={{
      background: '#f8fafc',
      border: '1px solid #e2e8f0',
      borderRadius: '6px',
      padding: '0.65rem 0.85rem',
      fontSize: '0.78125rem'
    }}>
      <div
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
        onClick={() => setIsOpen(!isOpen)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#0369a1', fontWeight: 600 }}>
          <HelpCircle size={15} />
          <span>Why is this rated {(severity || 'unknown').toUpperCase()}? (Auditable Policy Score: {score || 75}/100)</span>
        </div>
        <button style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer' }}>
          {isOpen ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>
      </div>

      {isOpen && (
        <div style={{ marginTop: '0.65rem', borderTop: '1px solid #cbd5e1', paddingTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
          <p style={{ margin: '0 0 0.4rem', color: '#334155', lineHeight: 1.4 }}>
            {explanation || `Evaluated by the deterministic emergency-safety policy using exposure, active hazard signals, and casualty-risk metrics.`}
          </p>

          {breakdown && breakdown.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
              {breakdown.map((item, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#ffffff', padding: '0.35rem 0.5rem', borderRadius: '4px', border: '1px solid #e2e8f0', fontSize: '0.72rem' }}>
                  <div>
                    <strong style={{ color: '#0f172a' }}>{item.factor}</strong>
                    <div style={{ color: '#64748b', fontSize: '0.68rem' }}>{item.rationale}</div>
                  </div>
                  <span style={{ fontWeight: 700, color: item.points > 0 ? '#dc2626' : '#16a34a', background: item.points > 0 ? '#fee2e2' : '#dcfce7', padding: '1px 6px', borderRadius: '4px' }}>
                    +{item.points} pts
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
