import React, { FormEvent, useEffect, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { api, ApiError } from '../services/api';
import { ReviewItem, WorkInstruction } from '../types';

interface ReviewQueuePageProps {
  machineModel: string;
}

export const ReviewQueuePage: React.FC<ReviewQueuePageProps> = ({ machineModel }) => {
  const { can, status: authStatus } = useAuth();
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [instructions, setInstructions] = useState<WorkInstruction[]>([]);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [originFilter, setOriginFilter] = useState<'operational' | 'benchmark' | 'all'>('operational');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedItem, setSelectedItem] = useState<ReviewItem | null>(null);
  const [expertNotes, setExpertNotes] = useState('');
  const [acting, setActing] = useState(false);
  const [showDraftModal, setShowDraftModal] = useState(false);
  const [wiTitle, setWiTitle] = useState('');
  const [wiSummary, setWiSummary] = useState('');
  const [wiOperation, setWiOperation] = useState('');
  const [drafting, setDrafting] = useState(false);
  const [draftResult, setDraftResult] = useState<string | null>(null);

  const loadReviewData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [queueData, wiData] = await Promise.all([
        api.getReviewQueue(statusFilter || undefined, originFilter),
        api.getWorkInstructions(),
      ]);
      setItems(queueData);
      setInstructions(wiData.filter((instruction) => instruction.machine_model === machineModel));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'Review data could not be loaded.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadReviewData();
  }, [machineModel, statusFilter, originFilter]);

  const handleAction = async (action: 'approved' | 'rejected' | 'escalated') => {
    if (!selectedItem || expertNotes.trim().length < 3) return;
    if (!window.confirm(`Confirm ${action} for "${selectedItem.title}"?`)) return;
    setActing(true);
    setError(null);
    try {
      await api.takeReviewAction(selectedItem.id, action, expertNotes.trim());
      setSelectedItem(null);
      setExpertNotes('');
      await loadReviewData();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'The review action could not be recorded.');
    } finally {
      setActing(false);
    }
  };

  const handleDraftInstruction = async (event: FormEvent) => {
    event.preventDefault();
    setDraftResult(null);
    setError(null);
    setDrafting(true);
    try {
      const draft = await api.draftWorkInstruction(wiTitle, wiSummary, wiOperation || 'Setup and maintenance', machineModel);
      setDraftResult(`${draft.instruction_number} created as an unpublished evidence draft.`);
      setShowDraftModal(false);
      setWiTitle('');
      setWiSummary('');
      setWiOperation('');
      await loadReviewData();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'A work-instruction draft could not be created.');
    } finally {
      setDrafting(false);
    }
  };

  const handleApproveInstruction = async (instruction: WorkInstruction) => {
    if (!window.confirm(`Approve and publish ${instruction.instruction_number}? Verify its cited evidence before proceeding.`)) return;
    setError(null);
    try {
      await api.approveWorkInstruction(instruction.id, 'Reviewed cited source evidence and safety controls.');
      await loadReviewData();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'The work instruction could not be approved.');
    }
  };

  const reviewAllowed = can('expert_reviewer');
  const instructionApproverAllowed = can('instruction_approver');

  return (
    <div className="page-container">
      <section className="page-heading">
        <div>
          <p className="eyebrow">Human governance</p>
          <h1>Expert review queue</h1>
          <p className="page-description">Review escalations and evidence-based draft instructions for {machineModel}. Approval and publication require verified roles.</p>
        </div>
        <div className="heading-actions">
          <label className="control-inline">
            Queue
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="pending">Pending only</option>
              <option value="">All review history</option>
            </select>
          </label>
          <label className="control-inline">
            Origin
            <select
              value={originFilter}
              onChange={(event) => {
                const value = event.target.value;
                if (value === 'operational' || value === 'benchmark' || value === 'all') {
                  setOriginFilter(value);
                }
              }}
            >
              <option value="operational">Operational &amp; unclassified</option>
              <option value="benchmark">Benchmark history</option>
              <option value="all">All origins</option>
            </select>
          </label>
          <button type="button" className="btn btn-primary" onClick={() => setShowDraftModal(true)}>
            Create evidence draft
          </button>
        </div>
      </section>

      {!reviewAllowed && (
        <div className="notice notice-neutral">
          Review decisions require a verified <code>expert_reviewer</code> role.
          {authStatus === 'unconfigured' && ' OIDC sign-in is not configured.'}
        </div>
      )}
      {!instructionApproverAllowed && (
        <div className="notice notice-neutral">
          Publishing a work instruction requires a verified <code>instruction_approver</code> role.
        </div>
      )}
      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {draftResult && <div className="notice notice-success" role="status">{draftResult}</div>}

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Decision items</p>
            <h2>Review queue <span className="count-badge">{items.length}</span></h2>
          </div>
          <button type="button" className="text-button" onClick={() => void loadReviewData()} disabled={loading}>Refresh</button>
        </div>
        {loading ? <div className="loading-state">Loading review records…</div> : null}
        {!loading && items.length === 0 && <div className="empty-state">No review items match this filter.</div>}
        <div className="review-grid">
          {items.map((item) => (
            <article className="review-card" key={item.id}>
              <div className="review-card-top">
                <span className={`status-pill ${item.priority === 'critical' ? 'status-negative' : item.priority === 'high' ? 'status-warning' : 'status-neutral'}`}>
                  {item.priority} priority
                </span>
                <span className="review-type">{item.item_type.replace(/_/g, ' ')}</span>
              </div>
              <div className="review-card-top">
                <span className={`status-pill ${item.origin === 'benchmark' ? 'status-warning' : 'status-neutral'}`}>
                  {item.origin === 'benchmark'
                    ? 'Benchmark history'
                    : item.origin === 'legacy_unclassified'
                      ? 'Legacy · unclassified'
                      : 'Operational'}
                </span>
              </div>
              <details className="review-origin-evidence">
                <summary>Origin evidence</summary>
                <p>{item.origin_evidence}</p>
              </details>
              <h3>{item.title}</h3>
              <p>{item.summary}</p>
              {item.proposed_action && <div className="review-action">{item.proposed_action}</div>}
              <div className="review-card-footer">
                <span>{new Date(item.created_at).toLocaleString()}</span>
                <span>{item.reviewer ? `Reviewed by ${item.reviewer}` : item.status}</span>
              </div>
              {item.status === 'pending' && item.origin !== 'benchmark' && (
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => {
                    setSelectedItem(item);
                    setExpertNotes('');
                  }}
                  disabled={!reviewAllowed}
                >
                  Review item
                </button>
              )}
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Source-backed drafts</p>
            <h2>Work instructions ({instructions.length})</h2>
          </div>
        </div>
        {instructions.length === 0 && !loading && <div className="empty-state">No work-instruction drafts exist for this machine.</div>}
        <div className="instruction-list">
          {instructions.map((instruction) => (
            <article className="instruction-card" key={instruction.id}>
              <div className="instruction-heading">
                <div>
                  <p className="eyebrow">{instruction.instruction_number} · {instruction.machine_model}</p>
                  <h3>{instruction.title}</h3>
                </div>
                <span className={`status-pill ${instruction.is_published ? 'status-positive' : 'status-warning'}`}>
                  {instruction.is_published ? 'Published' : 'Unpublished draft'}
                </span>
              </div>
              <p>{instruction.task_summary}</p>
              {instruction.safety_warnings.map((warning) => (
                <div className="notice notice-warning" key={warning}>{warning}</div>
              ))}
              <div className="instruction-steps">
                {instruction.steps.map((step) => (
                  <article className="chunk-card" key={step.step_number}>
                    <strong>{step.step_number}. {step.title}</strong>
                    <p>{step.description}</p>
                    {step.source_citation && <small>Source: {step.source_citation}</small>}
                    {step.verification_check && <small>Review check: {step.verification_check}</small>}
                  </article>
                ))}
              </div>
              <div className="instruction-footer">
                <span>{instruction.approved_source_doc_ids.length} cited source document(s)</span>
                {instruction.is_published ? (
                  <span>Reviewed by {instruction.reviewed_by || 'Reviewer unavailable'}</span>
                ) : (
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => void handleApproveInstruction(instruction)}
                    disabled={!instructionApproverAllowed}
                  >
                    Approve and publish
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      </section>

      {selectedItem && (
        <div className="modal-backdrop" role="presentation">
          <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="review-title">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Review decision</p>
                <h2 id="review-title">{selectedItem.title}</h2>
              </div>
              <button type="button" className="icon-button" onClick={() => setSelectedItem(null)} disabled={acting} aria-label="Close review dialog">×</button>
            </div>
            <p>{selectedItem.summary}</p>
            <label className="form-field">
              <span>Reviewer rationale (required)</span>
              <textarea value={expertNotes} onChange={(event) => setExpertNotes(event.target.value)} minLength={3} rows={4} />
            </label>
            <div className="form-actions">
              <button type="button" className="btn btn-danger" onClick={() => void handleAction('rejected')} disabled={acting || !reviewAllowed || expertNotes.trim().length < 3}>Reject</button>
              <button type="button" className="btn btn-secondary" onClick={() => void handleAction('escalated')} disabled={acting || !reviewAllowed || expertNotes.trim().length < 3}>Escalate</button>
              <button type="button" className="btn btn-primary" onClick={() => void handleAction('approved')} disabled={acting || !reviewAllowed || expertNotes.trim().length < 3}>Approve review item</button>
            </div>
          </section>
        </div>
      )}

      {showDraftModal && (
        <div className="modal-backdrop" role="presentation">
          <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="draft-title">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Evidence-based drafting</p>
                <h2 id="draft-title">Create a work-instruction draft</h2>
              </div>
              <button type="button" className="icon-button" onClick={() => setShowDraftModal(false)} disabled={drafting} aria-label="Close draft dialog">×</button>
            </div>
            <div className="notice notice-warning">
              Drafts contain retrieved approved source excerpts, not generated operating steps. A qualified reviewer must validate and approve before publication.
            </div>
            <form onSubmit={(event) => void handleDraftInstruction(event)} className="form-grid">
              <label className="form-field form-span">
                <span>Draft title</span>
                <input value={wiTitle} onChange={(event) => setWiTitle(event.target.value)} minLength={5} maxLength={200} required />
              </label>
              <label className="form-field form-span">
                <span>Target operation</span>
                <input value={wiOperation} onChange={(event) => setWiOperation(event.target.value)} required />
              </label>
              <label className="form-field form-span">
                <span>Task description for evidence retrieval</span>
                <textarea value={wiSummary} onChange={(event) => setWiSummary(event.target.value)} minLength={10} rows={4} required />
              </label>
              <div className="form-actions form-span">
                <button type="button" className="btn btn-secondary" onClick={() => setShowDraftModal(false)} disabled={drafting}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={drafting}>
                  {drafting ? 'Checking approved evidence…' : 'Create draft'}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
};
