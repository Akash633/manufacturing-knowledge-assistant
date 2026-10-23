import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { NavTab } from '../components/Navbar';

interface OverviewPageProps {
  onNavigate: (tab: NavTab) => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({ onNavigate }) => {
  const [stats, setStats] = useState({
    totalDocs: 0,
    approvedDocs: 0,
    supersededDocs: 0,
    conflicts: 0,
    pendingReviews: 0,
  });
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadOverviewData();
  }, []);

  const loadOverviewData = async () => {
    try {
      setLoading(true);
      const [docsData, conflictsData, reviewData, auditData] = await Promise.all([
        api.getDocuments(),
        api.getConflicts(),
        api.getReviewQueue('pending'),
        api.getAuditTrail(),
      ]);

      const items = docsData.items || [];
      setStats({
        totalDocs: items.length,
        approvedDocs: items.filter((d) => d.approval_status === 'Approved').length,
        supersededDocs: items.filter((d) => d.approval_status === 'Superseded').length,
        conflicts: conflictsData.length,
        pendingReviews: reviewData.length,
      });
      setAuditLogs(auditData.slice(0, 8));
    } catch (e) {
      console.error('Error loading overview data:', e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container space-y-6">
      {/* Top Welcome Card */}
      <div className="card" style={{ background: 'linear-gradient(135deg, #0e1a32 0%, #13223f 100%)', borderColor: '#28416d' }}>
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="badge badge-approved">SYSTEM ONLINE</span>
              <span className="text-xs text-slate-400 font-mono">REVISION GOVERNANCE ACTIVE</span>
            </div>
            <h2 className="text-xl font-bold text-white tracking-wide">
              Revision-Aware Manufacturing Assistant
            </h2>
            <p className="text-xs text-slate-300 max-w-2xl leading-relaxed">
              Traceable shop-floor knowledge operations for <strong>DEMO-CNC-01</strong>. All answers strictly ground in authorized SOPs and maintenance logs with verifiable citation validation.
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <button onClick={() => onNavigate('assistant')} className="btn btn-primary">
              💬 Open Assistant
            </button>
            <button onClick={() => onNavigate('evaluation')} className="btn btn-secondary">
              ⚡ Benchmark Suite
            </button>
          </div>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="card text-center py-4" style={{ backgroundColor: 'var(--bg-card)' }}>
          <div className="text-[11px] text-slate-400 font-bold uppercase tracking-wider">Total Documents</div>
          <div className="text-2xl font-bold font-mono text-cyan-400 mt-1">{loading ? '...' : stats.totalDocs}</div>
          <div className="text-[11px] text-slate-400 mt-0.5 font-mono">PDF & DOCX</div>
        </div>

        <div className="card text-center py-4">
          <div className="text-[11px] text-slate-400 font-bold uppercase tracking-wider">Approved Active</div>
          <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">{loading ? '...' : stats.approvedDocs}</div>
          <div className="text-[11px] text-emerald-400/80 mt-0.5 font-mono">Authoritative</div>
        </div>

        <div className="card text-center py-4">
          <div className="text-[11px] text-slate-400 font-bold uppercase tracking-wider">Superseded / Draft</div>
          <div className="text-2xl font-bold font-mono text-red-400 mt-1">{loading ? '...' : stats.supersededDocs}</div>
          <div className="text-[11px] text-slate-400 mt-0.5 font-mono">Non-Authoritative</div>
        </div>

        <div className="card text-center py-4 cursor-pointer hover:border-amber-500/60" onClick={() => onNavigate('conflicts')}>
          <div className="text-[11px] text-slate-400 font-bold uppercase tracking-wider">Detected Conflicts</div>
          <div className="text-2xl font-bold font-mono text-amber-400 mt-1">{loading ? '...' : stats.conflicts}</div>
          <div className="text-[11px] text-amber-400/80 mt-0.5 font-mono">Discrepancy Alerts</div>
        </div>

        <div className="card text-center py-4 cursor-pointer hover:border-red-500/60" onClick={() => onNavigate('review')}>
          <div className="text-[11px] text-slate-400 font-bold uppercase tracking-wider">Review Queue</div>
          <div className="text-2xl font-bold font-mono text-cyan-300 mt-1">{loading ? '...' : stats.pendingReviews}</div>
          <div className="text-[11px] text-slate-400 mt-0.5 font-mono">Pending Sign-off</div>
        </div>
      </div>

      {/* Two Column Layout: Equipment Spec & Recent Audits */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left: Machine Profile */}
        <div className="card space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h3 className="font-bold text-white text-sm uppercase tracking-wide">Target Machine Spec</h3>
              <p className="text-[11px] text-slate-400">DEMO-CNC-01 Physical Limits</p>
            </div>
            <span className="badge badge-approved text-[10px]">CONNECTED</span>
          </div>

          <div className="space-y-2.5 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Machine Model:</span>
              <span className="font-mono font-bold text-cyan-400">DEMO-CNC-01</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Spindle Taper:</span>
              <span className="font-mono text-white">BT40 / 12,000 Max RPM</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Coolant Pressure:</span>
              <span className="font-mono text-white">2.5 bar (Flood)</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">X-Backlash Limit:</span>
              <span className="font-mono text-emerald-400">0.008 mm (Measured: 0.004)</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Governing SOP:</span>
              <span className="font-mono text-cyan-300 font-semibold">SOP-CNC-001 (Rev B)</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-400">Active Quality Alert:</span>
              <span className="font-mono text-amber-400 font-semibold">QA-CNC-2024-03</span>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-800">
            <button onClick={() => onNavigate('library')} className="btn btn-secondary w-full text-xs py-2">
              Inspect Linked Documents ({stats.totalDocs})
            </button>
          </div>
        </div>

        {/* Right 2 cols: Traceable Audit Trail */}
        <div className="card md:col-span-2 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h3 className="font-bold text-white text-sm uppercase tracking-wide">Shop Floor Audit Ledger</h3>
              <p className="text-[11px] text-slate-400">Traceable chronological ledger of document ingestions, queries, and safety events</p>
            </div>
            <button onClick={loadOverviewData} className="btn btn-secondary text-xs py-1 px-3">
              🔄 Refresh
            </button>
          </div>

          <div className="overflow-x-auto">
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Action</th>
                  <th>Actor</th>
                  <th>Resource</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="text-center text-slate-500 py-6">
                      No audit events recorded yet.
                    </td>
                  </tr>
                ) : (
                  auditLogs.map((log) => {
                    const dt = new Date(log.timestamp).toLocaleTimeString();
                    return (
                      <tr key={log.id}>
                        <td className="font-mono text-xs text-slate-400 whitespace-nowrap">{dt}</td>
                        <td>
                          <span className="badge badge-pending text-[10px]">
                            {log.action}
                          </span>
                        </td>
                        <td className="text-xs text-slate-300 whitespace-nowrap">{log.actor}</td>
                        <td className="font-mono text-xs text-slate-400 whitespace-nowrap">{log.resource_type}</td>
                        <td className="text-xs text-slate-300 font-mono truncate max-w-xs">
                          {log.details_json}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
