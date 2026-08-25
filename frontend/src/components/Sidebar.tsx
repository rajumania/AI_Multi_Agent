import React from 'react';
import {
  LayoutDashboard,
  AlertTriangle,
  Layers,
  FileCheck,
  History,
  ShieldCheck,
  Cpu,
  UserCog,
  X,
} from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  showDepartmentManagement?: boolean;
  mobileOpen?: boolean;
  onClose?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, onTabChange, showDepartmentManagement = false, mobileOpen = false, onClose }) => {
  const navItems = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'command3d', label: 'AI Command 3D', icon: Cpu },
    { id: 'incidents', label: 'Incidents', icon: AlertTriangle },
    { id: 'resources', label: 'Campus Resources', icon: Layers },
    { id: 'responses', label: 'Response Plans', icon: FileCheck },
    { id: 'activity', label: 'Activity Logs', icon: History },
    ...(showDepartmentManagement
      ? [{ id: 'department-management', label: 'Department Management', icon: UserCog }]
      : []),
  ];

  return (
    <>
      <button
        type="button"
        className={`app-sidebar-backdrop ${mobileOpen ? 'is-open' : ''}`}
        aria-label="Close navigation"
        aria-hidden={!mobileOpen}
        tabIndex={mobileOpen ? 0 : -1}
        onClick={onClose}
      />
    <aside className={`app-sidebar ${mobileOpen ? 'is-open' : ''}`}>
      <button type="button" className="sidebar-mobile-close" aria-label="Close navigation" onClick={onClose}>
        <X size={19} />
      </button>
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
              onClose?.();
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
    </>
  );
};
