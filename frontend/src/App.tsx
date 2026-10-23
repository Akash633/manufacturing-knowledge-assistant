import React, { useState, useEffect } from 'react';
import { Navbar, NavTab } from './components/Navbar';
import { OverviewPage } from './pages/OverviewPage';
import { AssistantPage } from './pages/AssistantPage';
import { DocumentLibraryPage } from './pages/DocumentLibraryPage';
import { EvidenceExplorerPage } from './pages/EvidenceExplorerPage';
import { ConflictCenterPage } from './pages/ConflictCenterPage';
import { ReviewQueuePage } from './pages/ReviewQueuePage';
import { EvaluationPage } from './pages/EvaluationPage';
import { api } from './services/api';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<NavTab>('overview');
  const [pendingReviewsCount, setPendingReviewsCount] = useState(0);
  const [conflictsCount, setConflictsCount] = useState(0);

  useEffect(() => {
    loadBadgeCounts();
  }, [currentTab]);

  const loadBadgeCounts = async () => {
    try {
      const [reviewData, conflictData] = await Promise.all([
        api.getReviewQueue('pending').catch(() => []),
        api.getConflicts().catch(() => []),
      ]);
      setPendingReviewsCount(reviewData.length || 0);
      setConflictsCount(conflictData.length || 0);
    } catch (e) {
      // ignore
    }
  };

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <Navbar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        pendingReviewsCount={pendingReviewsCount}
        conflictsCount={conflictsCount}
      />

      {/* Main Content Area */}
      <div className="main-content">
        {/* Prominent Safety & Demo Disclaimer Banner */}
        <div className="disclaimer-banner">
          ⚠️ SYNTHETIC DEMONSTRATION DATA. NOT VALID FOR REAL MACHINE OPERATION.
        </div>

        {/* Top Header Bar */}
        <header className="top-bar">
          <div className="flex items-center gap-3">
            <span className="font-bold text-white text-sm tracking-wide">DEMO-CNC-01</span>
            <span className="text-slate-500 font-mono text-xs">|</span>
            <span className="badge badge-approved text-xs">REVISION AWARE</span>
            <span className="text-xs text-slate-400 font-mono hidden md:inline">
              Authority Enforced by Status & Effective Date
            </span>
          </div>

          <div className="flex items-center gap-3 text-xs font-mono">
            <span className="text-slate-400">LLM Mode:</span>
            <span className="text-cyan-400 font-semibold bg-slate-900 border border-slate-700 px-2 py-0.5 rounded">
              Deterministic Demo
            </span>
          </div>
        </header>

        {/* Dynamic Page Views */}
        <main className="flex-1 overflow-y-auto">
          {currentTab === 'overview' && <OverviewPage onNavigate={setCurrentTab} />}
          {currentTab === 'assistant' && <AssistantPage />}
          {currentTab === 'library' && <DocumentLibraryPage />}
          {currentTab === 'evidence' && <EvidenceExplorerPage />}
          {currentTab === 'conflicts' && <ConflictCenterPage />}
          {currentTab === 'review' && <ReviewQueuePage />}
          {currentTab === 'evaluation' && <EvaluationPage />}
        </main>
      </div>
    </div>
  );
};

export default App;
