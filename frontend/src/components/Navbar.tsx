import React from 'react';

export type NavTab = 
  | 'overview' 
  | 'assistant' 
  | 'library' 
  | 'evidence' 
  | 'conflicts' 
  | 'review' 
  | 'evaluation';

interface NavbarProps {
  currentTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  pendingReviewsCount: number;
  conflictsCount: number;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentTab,
  onSelectTab,
  pendingReviewsCount,
  conflictsCount,
}) => {
  const navItems: { id: NavTab; label: string; icon: string; badge?: number; badgeColor?: string }[] = [
    { id: 'overview', label: 'Overview Dashboard', icon: '📊' },
    { id: 'assistant', label: 'Shop Floor Assistant', icon: '🤖' },
    { id: 'library', label: 'Document Library', icon: '📚' },
    { id: 'evidence', label: 'Evidence Explorer', icon: '🔍' },
    { id: 'conflicts', label: 'Revision & Conflicts', icon: '⚖️', badge: conflictsCount, badgeColor: '#d97706' },
    { id: 'review', label: 'Expert Review Queue', icon: '🛡️', badge: pendingReviewsCount, badgeColor: '#dc2626' },
    { id: 'evaluation', label: 'Evaluation & Benchmarks', icon: '📈' },
  ];

  return (
    <aside className="sidebar">
      {/* Brand Header */}
      <div className="sidebar-header">
        <div className="brand-icon">M</div>
        <div>
          <div className="font-bold text-xs tracking-wider text-white" style={{ letterSpacing: '0.06em' }}>
            MANUFACTURING AI
          </div>
          <div className="text-[11px] text-slate-400 font-mono">ASSISTANT v1.0</div>
        </div>
      </div>

      {/* Target Machine Status */}
      <div className="machine-status-box">
        <div className="flex items-center justify-between text-xs mb-1">
          <span className="text-slate-400 font-semibold" style={{ fontSize: '10px' }}>TARGET UNIT</span>
          <span className="badge badge-approved" style={{ fontSize: '10px', padding: '1px 6px' }}>
            ONLINE
          </span>
        </div>
        <div className="font-mono font-bold text-cyan-400 text-sm">DEMO-CNC-01</div>
        <div className="text-[11px] text-slate-400 mt-0.5">3-Axis Vertical Mill</div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-2 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className={`nav-item-btn ${isActive ? 'active' : ''}`}
            >
              <div className="flex items-center gap-3" style={{ minWidth: 0 }}>
                <span style={{ fontSize: '15px', flexShrink: 0 }}>{item.icon}</span>
                <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {item.label}
                </span>
              </div>
              {item.badge !== undefined && item.badge > 0 && (
                <span
                  style={{
                    backgroundColor: item.badgeColor || '#2563eb',
                    color: '#ffffff',
                    fontSize: '10px',
                    fontWeight: 700,
                    padding: '1px 6px',
                    borderRadius: '999px',
                    flexShrink: 0,
                    marginLeft: '8px',
                    fontFamily: 'var(--font-mono)'
                  }}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer Info */}
      <div className="p-3 border-t border-slate-800 text-[11px] text-slate-400 font-mono text-center">
        Hybrid RRF + Deterministic Guard
      </div>
    </aside>
  );
};
