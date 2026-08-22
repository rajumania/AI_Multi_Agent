import React from 'react';
import {
  LayoutDashboard,
  AlertTriangle,
  Layers,
  FileCheck,
  History,
  ShieldCheck
} from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, onTabChange }) => {
  const navItems = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'incidents', label: 'Incidents', icon: AlertTriangle },
    { id: 'resources', label: 'Campus Resources', icon: Layers },
    { id: 'responses', label: 'Response Plans', icon: FileCheck },
    { id: 'activity', label: 'Activity Logs', icon: History },
  ];

  return (
    <aside className="app-sidebar">
      {navItems.map((item) => {
        const Icon = item.icon;
        const isActive = activeTab === item.id;
        return (
          <a
            key={item.id}
            className={`nav-link ${isActive ? 'active' : ''}`}
            onClick={(e) => {
              e.preventDefault();
              onTabChange(item.id);
            }}
            href={`#${item.id}`}
          >
            <Icon className="nav-icon" />
            <span>{item.label}</span>
          </a>
        );
      })}

      <div className="sidebar-footer">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.25rem' }}>
          <ShieldCheck size={14} color="#0d9488" />
          <strong>Campus Operations</strong>
        </div>
        <div>Vignan University Safety Node</div>
        <div style={{ color: '#94a3b8', fontSize: '0.6875rem', marginTop: '0.25rem' }}>
          CAMPUSFLOW v1.0.0 (Step 1)
        </div>
      </div>
    </aside>
  );
};
