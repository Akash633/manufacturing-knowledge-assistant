import React, { useEffect, useState } from 'react';
import { AuthProvider, useAuth } from './auth/AuthContext';
import { Navbar, NavTab } from './components/Navbar';
import { OverviewPage } from './pages/OverviewPage';
import { AssistantPage } from './pages/AssistantPage';
import { DocumentLibraryPage } from './pages/DocumentLibraryPage';
import { EvidenceExplorerPage } from './pages/EvidenceExplorerPage';
import { ConflictCenterPage } from './pages/ConflictCenterPage';
import { ReviewQueuePage } from './pages/ReviewQueuePage';
import { EvaluationPage } from './pages/EvaluationPage';
import { api } from './services/api';
import { SystemHealth } from './types';

const ApplicationShell: React.FC = () => {
  const { status: authStatus } = useAuth();
  const [currentTab, setCurrentTab] = useState<NavTab>('overview');
  const [pendingReviewsCount, setPendingReviewsCount] = useState<number | null>(null);
  const [conflictsCount, setConflictsCount] = useState<number | null>(null);
  const [machineModels, setMachineModels] = useState<string[]>([]);
  const [machineModel, setMachineModel] = useState('DEMO-CNC-01');
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  useEffect(() => {
    api.getHealth()
      .then((data) => {
        setHealth(data);
        setHealthError(null);
      })
      .catch(() => {
        setHealth(null);
        setHealthError('Unable to reach the backend health endpoint.');
      });

    api.getMachineModels()
      .then((models) => {
        setMachineModels(models);
        setMachineModel((current) => (
          models.includes(current) ? current : models[0] || current
        ));
      })
      .catch(() => setMachineModels([]));
  }, []);

  useEffect(() => {
    let active = true;
    Promise.allSettled([
      api.getReviewQueue('pending'),
      api.getConflicts(machineModel),
    ]).then(([reviews, conflicts]) => {
      if (!active) return;
      setPendingReviewsCount(reviews.status === 'fulfilled' ? reviews.value.length : null);
      setConflictsCount(
        conflicts.status === 'fulfilled'
          ? conflicts.value.filter((conflict) => conflict.status !== 'resolved').length
          : null,
      );
    });
    return () => {
      active = false;
    };
  }, [machineModel, currentTab]);

  const demoMode = health?.demo_mode === true;

  return (
    <div className="app-container">
      <Navbar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        pendingReviewsCount={pendingReviewsCount}
        conflictsCount={conflictsCount}
        machineModels={machineModels}
        machineModel={machineModel}
        onSelectMachine={setMachineModel}
        health={health}
        healthError={healthError}
      />

      <div className="main-content">
        <div className={`disclaimer-banner ${demoMode ? 'demo-banner' : 'operations-banner'}`} role="note">
          {demoMode
            ? 'Synthetic demonstration data — not valid for real machine operation.'
            : 'Use only current, site-approved documentation. Verify procedures at the machine before operation.'}
        </div>

        <header className="top-bar">
          <div className="top-bar-identity">
            <div className="top-bar-title">{machineModel}</div>
            <div className="top-bar-meta">
              {health?.environment || (healthError ? 'Backend unavailable' : 'Checking backend')}
            </div>
          </div>
          <div className="provider-status">
            <span className="top-bar-label">Answer provider</span>
            <strong>
              {health
                ? health.llm_provider.replace(/_/g, ' ')
                : healthError
                  ? 'Unavailable'
                  : 'Checking'}
            </strong>
          </div>
          <div
            className={`top-bar-auth ${
              authStatus === 'authenticated'
                ? 'is-configured'
                : authStatus === 'error'
                  ? 'is-error'
                  : 'is-unavailable'
            }`}
            role="status"
          >
            <span className={`status-dot ${authStatus === 'authenticated' ? 'is-healthy' : 'is-unavailable'}`} />
            <span>
              {authStatus === 'authenticated'
                ? 'Identity verified'
                : authStatus === 'signed_out'
                  ? 'Sign in required'
                  : authStatus === 'unconfigured'
                    ? 'OIDC not configured'
                    : authStatus === 'error'
                      ? 'Identity verification failed'
                      : 'Checking identity'}
            </span>
          </div>
        </header>

        <main className="main-area" id="main-content" tabIndex={-1}>
          {currentTab === 'overview' && (
            <OverviewPage machineModel={machineModel} onNavigate={setCurrentTab} />
          )}
          {currentTab === 'assistant' && <AssistantPage machineModel={machineModel} />}
          {currentTab === 'library' && <DocumentLibraryPage machineModel={machineModel} health={health} />}
          {currentTab === 'evidence' && <EvidenceExplorerPage machineModel={machineModel} />}
          {currentTab === 'conflicts' && <ConflictCenterPage machineModel={machineModel} />}
          {currentTab === 'review' && <ReviewQueuePage machineModel={machineModel} />}
          {currentTab === 'evaluation' && <EvaluationPage />}
        </main>
      </div>
    </div>
  );
};

export const App: React.FC = () => (
  <AuthProvider>
    <ApplicationShell />
  </AuthProvider>
);

export default App;
