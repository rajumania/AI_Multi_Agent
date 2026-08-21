import React from 'react';
import { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  label: string;
  value: string | number;
  subtext: string;
  icon: LucideIcon;
  variant?: 'blue' | 'red' | 'teal' | 'green';
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  subtext,
  icon: Icon,
  variant = 'blue'
}) => {
  return (
    <div className="metric-card">
      <div className="metric-header">
        <span className="metric-label">{label}</span>
        <div className={`metric-icon-badge ${variant}`}>
          <Icon size={18} />
        </div>
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-subtext">{subtext}</div>
    </div>
  );
};
