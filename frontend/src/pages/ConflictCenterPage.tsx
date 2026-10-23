import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { DocumentConflict } from '../types';

export const ConflictCenterPage: React.FC = () => {
  const [conflicts, setConflicts] = useState<DocumentConflict[]>([]);
  const [matrix, setMatrix] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedConflict, setSelectedConflict] = useState<DocumentConflict | null>(null);
  const [resolutionNotes, setResolutionNotes] = useState('');
  const [resolving, setResolving] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [confData, matData] = await Promise.all([
        api.getConflicts(),
        api.getRevisionMatrix(),
      ]);
      setConflicts(confData || []);
      setMatrix(matData || []);
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleResolve = async (action: string) => {
    if (!selectedConflict) return;
    try {
      setResolving(true);
      await api.resolveConflict(selectedConflict.conflict_id, action, resolutionNotes || 'Resolved per Quality Engineering override.');
      alert('Conflict resolution logged in audit ledger.');
      setSelectedConflict(null);
      setResolutionNotes('');
      await loadData();
    } catch (e: any) {
      alert(`Resolution error: ${e.message}`);
    } finally {
      setResolving(false);
    }
  };

  return (
    <div className="page-container space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <span>⚖️ Revision & Parameter Conflict Center</span>
            <span className="badge badge-superseded text-xs">Human Verification Mandatory</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Detects contradictory operational directives between approved SOPs and active Quality Alerts.
          </p>
        </div>

        <button onClick={loadData} className="btn btn-secondary text-xs">
          🔄 Scan for Conflicts
        </button>
      </div>

      {/* Detected Conflicts Section */}
      <div className="space-y-4">
        <h3 className="text-xs font-semibold uppercase text-slate-400 tracking-wider">
          Detected Technical Conflicts ({conflicts.length})
        </h3>

        {conflicts.length === 0 && !loading && (
          <div className="card text-center py-8 text-emerald-400 text-xs">
            ✓ No unresolved operational contradictions detected across approved documents.
          </div>
        )}

        {conflicts.map((conf) => (
          <div key={conf.conflict_id} className="card border-amber-600/50 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center gap-2">
                <span className="badge bg-amber-900/40 text-amber-300 border border-amber-700">
                  {conf.severity.toUpperCase()} PRIORITY
                </span>
                <span className="font-bold text-white text-sm">{conf.parameter_or_topic} Discrepancy</span>
              </div>
              <span className="font-mono text-xs text-slate-400">{conf.conflict_id}</span>
            </div>

            <p className="text-xs text-slate-300">{conf.description}</p>

            {/* Side-by-Side Comparison */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Document A */}
              <div className="p-3 bg-slate-900/80 border border-slate-800 rounded space-y-2">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-mono font-bold text-cyan-400">
                    {conf.document_a_number} ({conf.document_a_revision})
                  </span>
                  <span className="badge badge-approved text-[10px]">{conf.document_a_status}</span>
                </div>
                <div className="text-xs text-slate-200 font-mono bg-slate-950 p-2 rounded">
                  "{conf.instruction_a}"
                </div>
              </div>

              {/* Document B */}
              <div className="p-3 bg-slate-900/80 border border-amber-900/50 rounded space-y-2">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-mono font-bold text-amber-400">
                    {conf.document_b_number} ({conf.document_b_revision})
                  </span>
                  <span className="badge badge-approved text-[10px]">{conf.document_b_status}</span>
                </div>
                <div className="text-xs text-slate-200 font-mono bg-slate-950 p-2 rounded">
                  "{conf.instruction_b}"
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-slate-800 text-xs">
              <span className="text-slate-400 italic">{conf.recommended_action}</span>
              <button
                onClick={() => setSelectedConflict(conf)}
                className="btn btn-primary py-1 px-3 text-xs"
              >
                Resolve Discrepancy
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Revision Authority Matrix */}
      <div className="card space-y-4">
        <h3 className="text-xs font-semibold uppercase text-slate-400 tracking-wider">
          Revision Family Tree & Explicit Authority Matrix
        </h3>

        <div className="overflow-x-auto">
          <table>
            <thead>
              <tr>
                <th>Document</th>
                <th>Revision</th>
                <th>Title</th>
                <th>Explicit Status</th>
                <th>Authority Status</th>
                <th>Effective Range</th>
                <th>Superseded Link</th>
              </tr>
            </thead>
            <tbody>
              {matrix.map((row) => (
                <tr key={row.id}>
                  <td className="font-mono font-bold text-cyan-400 text-xs">{row.document_number}</td>
                  <td className="font-mono text-xs">{row.revision}</td>
                  <td className="text-white text-xs">{row.title}</td>
                  <td>
                    <span className={`badge ${
                      row.approval_status === 'Approved' ? 'badge-approved' :
                      row.approval_status === 'Superseded' ? 'badge-superseded' : 'badge-draft'
                    }`}>
                      {row.approval_status}
                    </span>
                  </td>
                  <td>
                    <span className={row.is_authoritative ? 'text-emerald-400 font-semibold text-xs' : 'text-red-400 font-semibold text-xs'}>
                      {row.is_authoritative ? '✓ Authoritative' : '✗ Non-Authoritative'}
                    </span>
                  </td>
                  <td className="font-mono text-xs text-slate-400">
                    {row.effective_date ? new Date(row.effective_date).toLocaleDateString() : 'N/A'}
                  </td>
                  <td className="font-mono text-xs text-slate-400 truncate max-w-xs">
                    {row.superseded_by_id ? `Superseded by ID ${row.superseded_by_id.slice(0, 8)}...` : 'None'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Resolution Modal */}
      {selectedConflict && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="card w-full max-w-lg space-y-4 border-slate-700">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-bold text-white text-base">Authorize Conflict Resolution</h3>
              <button onClick={() => setSelectedConflict(null)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <p className="text-xs text-slate-300">
              Select the governing operational directive for <strong>{selectedConflict.parameter_or_topic}</strong>:
            </p>

            <div className="space-y-2 text-xs">
              <label className="block text-slate-400">Resolution Engineering Notes*</label>
              <textarea
                value={resolutionNotes}
                onChange={(e) => setResolutionNotes(e.target.value)}
                placeholder="e.g. Enforce QA-CNC-2024-03 restriction of 1200 mm/min on Ti-6Al-4V until tool fixture redesign is released."
                className="input-field h-24"
              />
            </div>

            <div className="flex flex-col gap-2 pt-2 border-t border-slate-800">
              <button
                onClick={() => handleResolve('enforce_quality_alert')}
                disabled={resolving}
                className="btn btn-primary text-xs w-full"
              >
                Enforce Quality Alert ({selectedConflict.document_b_number}) Limit
              </button>
              <button
                onClick={() => handleResolve('retain_base_sop')}
                disabled={resolving}
                className="btn btn-secondary text-xs w-full"
              >
                Approve Base SOP Standard Parameter
              </button>
              <button
                onClick={() => setSelectedConflict(null)}
                className="btn btn-secondary text-xs w-full mt-1"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
