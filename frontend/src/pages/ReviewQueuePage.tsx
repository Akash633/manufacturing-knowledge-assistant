import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { ReviewItem, WorkInstruction } from '../types';

export const ReviewQueuePage: React.FC = () => {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [instructions, setInstructions] = useState<WorkInstruction[]>([]);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [loading, setLoading] = useState(true);
  const [selectedItem, setSelectedItem] = useState<ReviewItem | null>(null);
  const [expertNotes, setExpertNotes] = useState('');
  const [acting, setActing] = useState(false);

  // New Draft Instruction modal
  const [showDraftModal, setShowDraftModal] = useState(false);
  const [wiTitle, setWiTitle] = useState('');
  const [wiSummary, setWiSummary] = useState('');
  const [wiOperation, setWiOperation] = useState('');
  const [drafting, setDrafting] = useState(false);

  useEffect(() => {
    loadReviewData();
  }, [statusFilter]);

  const loadReviewData = async () => {
    try {
      setLoading(true);
      const [queueData, wiData] = await Promise.all([
        api.getReviewQueue(statusFilter || undefined),
        api.getWorkInstructions(),
      ]);
      setItems(queueData || []);
      setInstructions(wiData || []);
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleAction = async (action: 'approved' | 'rejected' | 'escalated') => {
    if (!selectedItem) return;
    try {
      setActing(true);
      await api.takeReviewAction(selectedItem.id, action, expertNotes || `Decision: ${action}`);
      alert(`Review item status updated to ${action.toUpperCase()}`);
      setSelectedItem(null);
      setExpertNotes('');
      await loadReviewData();
    } catch (e: any) {
      alert(`Action error: ${e.message}`);
    } finally {
      setActing(false);
    }
  };

  const handleDraftInstruction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!wiTitle || !wiSummary) return;

    try {
      setDrafting(true);
      await api.draftWorkInstruction(wiTitle, wiSummary, wiOperation || 'Setup & Calibration');
      setShowDraftModal(false);
      setWiTitle('');
      setWiSummary('');
      setWiOperation('');
      await loadReviewData();
      alert('Draft instruction created and placed in Pending Review queue. Remains unpublished until signed off.');
    } catch (e: any) {
      alert(`Draft error: ${e.message}`);
    } finally {
      setDrafting(false);
    }
  };

  const handleApproveInstruction = async (id: string) => {
    try {
      await api.approveWorkInstruction(id);
      await loadReviewData();
      alert('Work instruction signed off and published for shop-floor operators.');
    } catch (e: any) {
      alert(`Approval error: ${e.message}`);
    }
  };

  return (
    <div className="page-container space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <span>🛡️ Expert Review Queue & Instruction Governance</span>
            <span className="badge badge-pending text-xs">Human-in-the-Loop</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Mandatory sign-off for safety-critical queries, document conflicts, and draft work instructions.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input-field py-1.5 text-xs w-auto"
          >
            <option value="pending">Pending Items Only</option>
            <option value="">All Review History</option>
          </select>

          <button onClick={() => setShowDraftModal(true)} className="btn btn-primary text-xs">
            📝 Draft New Work Instruction
          </button>
        </div>
      </div>

      {/* Review Queue Items */}
      <div className="space-y-4">
        <h3 className="text-xs font-semibold uppercase text-slate-400 tracking-wider">
          Items Awaiting Expert Action ({items.length})
        </h3>

        {items.length === 0 && !loading && (
          <div className="card text-center py-8 text-slate-400 text-xs">
            ✓ No items pending review. All safety flags and discrepancies are resolved.
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {items.map((item) => (
            <div key={item.id} className="card border-slate-700 space-y-3">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <span className={`badge ${
                  item.priority === 'critical' ? 'bg-red-900/50 text-red-300 border-red-700' :
                  item.priority === 'high' ? 'bg-amber-900/50 text-amber-300 border-amber-700' : 'badge-draft'
                }`}>
                  {item.priority.toUpperCase()} PRIORITY
                </span>
                <span className="font-mono text-xs text-slate-400">{item.item_type}</span>
              </div>

              <div>
                <h4 className="font-bold text-white text-sm">{item.title}</h4>
                <p className="text-xs text-slate-300 mt-1">{item.summary}</p>
              </div>

              <div className="p-2.5 bg-slate-950 rounded text-xs font-mono text-cyan-300">
                Action Required: {item.proposed_action || 'Review and determine resolution.'}
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-slate-800 text-xs">
                <span className="text-slate-500 font-mono">
                  {new Date(item.created_at).toLocaleTimeString()}
                </span>
                <button
                  onClick={() => setSelectedItem(item)}
                  className="btn btn-secondary py-1 px-3 text-xs"
                >
                  Review Decision
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Work Instructions Section */}
      <div className="card space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div>
            <h3 className="font-bold text-white text-base">Shop Floor Work Instructions</h3>
            <p className="text-xs text-slate-400">
              Generated from approved documentation only. Strictly remains unpublished until approved.
            </p>
          </div>
          <span className="badge badge-approved text-xs">DEMO-CNC-01 Compliant</span>
        </div>

        <div className="space-y-4">
          {instructions.length === 0 ? (
            <div className="text-center py-6 text-slate-500 text-xs">
              No work instructions drafted yet. Click 'Draft New Work Instruction' to generate one from approved SOPs.
            </div>
          ) : (
            instructions.map((wi) => (
              <div key={wi.id} className="p-4 bg-slate-900 border border-slate-800 rounded space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-cyan-400 text-xs">{wi.instruction_number}</span>
                    <span className="font-bold text-white text-sm">{wi.title}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`badge ${wi.is_published ? 'badge-approved' : 'badge-draft'}`}>
                      {wi.is_published ? '✓ PUBLISHED' : '⚠️ UNPUBLISHED DRAFT'}
                    </span>
                    {!wi.is_published && (
                      <button
                        onClick={() => handleApproveInstruction(wi.id)}
                        className="btn btn-primary py-1 px-3 text-xs"
                      >
                        Approve & Publish
                      </button>
                    )}
                  </div>
                </div>

                <p className="text-xs text-slate-300">{wi.task_summary}</p>

                {/* Steps */}
                <div className="space-y-2 pt-2 border-t border-slate-800">
                  <span className="text-xs text-slate-400 font-semibold uppercase">Operational Steps:</span>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {wi.steps.map((st) => (
                      <div key={st.step_number} className="p-2.5 bg-slate-950 rounded border border-slate-800 text-xs space-y-1">
                        <div className="font-bold text-cyan-300 font-mono">Step {st.step_number}: {st.title}</div>
                        <div className="text-slate-300">{st.description}</div>
                        {st.safety_hazard && (
                          <div className="text-amber-400 text-[11px]">⚠️ Hazard: {st.safety_hazard}</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Decision Modal */}
      {selectedItem && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="card w-full max-w-lg space-y-4 border-slate-700">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-bold text-white text-base">Expert Review Sign-off</h3>
              <button onClick={() => setSelectedItem(null)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <div>
              <div className="text-xs text-slate-400">Review Item:</div>
              <div className="font-bold text-white text-sm">{selectedItem.title}</div>
              <p className="text-xs text-slate-300 mt-1">{selectedItem.summary}</p>
            </div>

            <div className="space-y-1 text-xs">
              <label className="block text-slate-400">Expert Reviewer Notes & Directives*</label>
              <textarea
                value={expertNotes}
                onChange={(e) => setExpertNotes(e.target.value)}
                placeholder="e.g. Verified procedure with safety guidelines. Authorized execution under supervisor supervision."
                className="input-field h-24"
              />
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
              <button
                onClick={() => handleAction('rejected')}
                disabled={acting}
                className="btn btn-danger text-xs"
              >
                Reject & Flag Hazard
              </button>
              <button
                onClick={() => handleAction('approved')}
                disabled={acting}
                className="btn btn-primary text-xs"
              >
                Approve & Sign-off
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Draft Instruction Modal */}
      {showDraftModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="card w-full max-w-lg space-y-4 border-slate-700">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-bold text-white text-base">Draft Shop Floor Work Instruction</h3>
              <button onClick={() => setShowDraftModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleDraftInstruction} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Instruction Title*</label>
                <input
                  type="text"
                  value={wiTitle}
                  onChange={(e) => setWiTitle(e.target.value)}
                  placeholder="e.g. Spindle Warm-up & Workpiece Chuck Setup"
                  className="input-field"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Target Operation</label>
                <input
                  type="text"
                  value={wiOperation}
                  onChange={(e) => setWiOperation(e.target.value)}
                  placeholder="e.g. Shift Startup Calibration"
                  className="input-field"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Task Summary & Operational Context*</label>
                <textarea
                  value={wiSummary}
                  onChange={(e) => setWiSummary(e.target.value)}
                  placeholder="Specify machine warm-up parameters, clamp pressures, and safety precautions..."
                  className="input-field h-24"
                  required
                />
              </div>

              <div className="p-2.5 bg-slate-950 border border-slate-800 rounded text-slate-400 text-[11px]">
                ℹ️ Draft instructions derive solely from approved documents and will be placed in the Expert Review Queue before publication.
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                <button type="button" onClick={() => setShowDraftModal(false)} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" disabled={drafting} className="btn btn-primary">
                  {drafting ? 'Synthesizing...' : 'Generate Draft Instruction'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
