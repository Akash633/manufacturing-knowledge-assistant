import React from 'react';
import { useAuth } from '../auth/AuthContext';
import { SystemHealth } from '../types';

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
  pendingReviewsCount: number | null;
  conflictsCount: number | null;
  machineModels: string[];
  machineModel: string;
  onSelectMachine: (machine: string) => void;
  health: SystemHealth | null;
  healthError: string | null;
}

const navItems: Array<{ id: NavTab; label: string; icon: string; badge?: 'reviews' | 'conflicts' }> = [
  { id: 'overview', label: 'Overview Dashboard', icon: 'M3 3h7v7H3z M14 3h7v5h-7z M14 12h7v9h-7z M3 14h7v7H3z' },
  { id: 'assistant', label: 'Shop Floor Assistant', icon: 'M4 5h16v11H8l-4 4z M8 9h8 M8 12h5' },
  { id: 'library', label: 'Document Library', icon: 'M5 3h11l3 3v15H5z M16 3v4h4 M8 11h8 M8 15h8' },
  { id: 'evidence', label: 'Evidence Explorer', icon: 'M10 4a6 6 0 1 0 0 12 6 6 0 0 0 0-12 M14.5 14.5 20 20' },
  { id: 'conflicts', label: 'Revision & Conflicts', icon: 'M12 3v18 M5 6h14 M7 6l-3 6h6z M17 6l-3 6h6z M8 21h8', badge: 'conflicts' },
  { id: 'review', label: 'Expert Review Queue', icon: 'M12 3 20 6v5c0 5-3 8-8 10-5-2-8-5-8-10V6z M9 12l2 2 4-4', badge: 'reviews' },
  { id: 'evaluation', label: 'Evaluation & Benchmarks', icon: 'M4 19V5 M4 19h17 M8 15l3-4 3 2 5-7' },
];

export const Navbar: React.FC<NavbarProps> = ({
  currentTab,
  onSelectTab,
  pendingReviewsCount,
  conflictsCount,
  machineModels,
  machineModel,
  onSelectMachine,
  health,
  healthError,
}) => {
  const { status, profile, message, signIn, signOut } = useAuth();

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="brand-mark" aria-hidden="true">MK</div>
        <div className="brand-copy">
          <div className="brand-title">Manufacturing Knowledge</div>
          <div className="brand-subtitle">OPERATIONS WORKSPACE</div>
        </div>
      </div>

      <div className="machine-status-box">
        <label htmlFor="machine-select" className="field-label">Machine scope</label>
        <select
          id="machine-select"
          value={machineModel}
          onChange={(event) => onSelectMachine(event.target.value)}
          disabled={machineModels.length === 0}
          className="machine-select"
        >
          {machineModels.length === 0 ? (
            <option value={machineModel}>No machine records</option>
          ) : machineModels.map((machine) => (
            <option key={machine} value={machine}>{machine}</option>
          ))}
        </select>
        <div className="machine-health" role="status">
          <span className={`status-dot ${health && !healthError ? 'is-healthy' : 'is-unavailable'}`} />
          {healthError ? 'API unavailable' : health ? 'API connected' : 'Checking API'}
        </div>
      </div>

      <nav className="nav-links" aria-label="Main navigation">
        {navItems.map((item) => {
          const count = item.badge === 'reviews'
            ? pendingReviewsCount
            : item.badge === 'conflicts'
              ? conflictsCount
              : null;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelectTab(item.id)}
              className={`nav-item-btn ${isActive ? 'active' : ''}`}
              aria-current={isActive ? 'page' : undefined}
            >
              <span className="nav-item-label">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d={item.icon} />
                </svg>
                <span>{item.label}</span>
              </span>
              {count !== null && count > 0 && (
                <span className="nav-count">{count}</span>
              )}
            </button>
          );
        })}
      </nav>

      <div className="sidebar-auth">
        <div className="auth-heading">
          <span className={`status-dot ${status === 'authenticated' ? 'is-healthy' : 'is-unavailable'}`} />
          <span>{status === 'authenticated' ? 'Verified identity' : 'Identity unavailable'}</span>
        </div>
        <p className="auth-subject">
          {profile?.subject || message || (
            status === 'unconfigured'
              ? 'OIDC sign-in is not configured.'
              : status === 'checking'
                ? 'Checking identity service…'
                : 'Sign in to access protected actions.'
          )}
        </p>
        {profile ? (
          <button type="button" className="btn btn-secondary auth-button" onClick={() => void signOut()}>
            Sign out
          </button>
        ) : status === 'signed_out' || status === 'error' ? (
          <button type="button" className="btn btn-secondary auth-button" onClick={() => void signIn()}>
            Sign in with organization
          </button>
        ) : null}
      </div>

      <div className="sidebar-footer">
        <span>{health?.embedding_provider || 'Retrieval status unavailable'}</span>
        <span>{health?.demo_mode ? 'Synthetic demo mode' : health?.environment || 'Environment unknown'}</span>
      </div>
    </aside>
  );
};
