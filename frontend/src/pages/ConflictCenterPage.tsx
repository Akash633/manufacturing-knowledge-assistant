import React, { FormEvent, useEffect, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { api, ApiError } from '../services/api';
import { DocumentConflict, RevisionRecord } from '../types';

interface ConflictCenterPageProps {
  machineModel: string;
}

type ResolutionAction = 'approve_exception' | 'mark_superseded' | 'withdraw_conflicting';

export const ConflictCenterPage: React.FC<ConflictCenterPageProps> = ({ machineModel }) => {
  const { can, status: authStatus } = useAuth();
  const [conflicts, setConflicts] = useState<DocumentConflict[]>([]);
  const [matrix, setMatrix] = useState<RevisionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedConflict, setSelectedConflict] = useState<DocumentConflict | null>(null);
  const [winnerId, setWinnerId] = useState('');
  const [resolutionAction, setResolutionAction] = useState<ResolutionAction>('approve_exception');
  const [resolutionNotes, setResolutionNotes] = useState('');
  const [resolving, setResolving] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([api.getConflicts(machineModel), api.getRevisionMatrix()])
      .then(([conflictData, matrixData]) => {
        if (!active) return;
        setConflicts(conflictData);
        setMatrix(matrixData.filter((row) => row.machine_model === machineModel || row.machine_model === 'ALL'));
        setError(null);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(reason instanceof ApiError ? reason.message : 'Conflict and revision data could not be loaded.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [machineModel]);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const [conflictData, matrixData] = await Promise.all([
        api.getConflicts(machineModel),
        api.getRevisionMatrix(),
      ]);
      setConflicts(conflictData);
      setMatrix(matrixData.filter((row) => row.machine_model === machineModel || row.machine_model === 'ALL'));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'Conflict data could not be refreshed.');
    } finally {
      setLoading(false);
    }
  };

  const openResolution = (conflict: DocumentConflict) => {
    setSelectedConflict(conflict);
    setWinnerId(conflict.document_b_id);
    setResolutionAction('approve_exception');
    setResolutionNotes('');
    setSuccess(null);
  };

  const handleResolve = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedConflict || !winnerId || resolutionNotes.trim().length < 3) return;
    if (resolutionAction !== 'approve_exception' && !can('document_approver')) {
      setError('This disposition also requires the document_approver role.');
      return;
    }
    const actionLabel = resolutionAction === 'approve_exception'
      ? 'record this approved exception'
      : resolutionAction === 'mark_superseded'
        ? 'mark the non-winning document superseded'
        : 'withdraw the non-winning document';
    if (!window.confirm(`Confirm: ${actionLabel}? This changes how the conflict is governed.`)) return;

    setResolving(true);
    setError(null);
    try {
      const result = await api.resolveConflict(
        selectedConflict.conflict_id,
        winnerId,
        resolutionAction,
        resolutionNotes.trim(),
      );
      setSuccess(`Resolution recorded for ${result.conflict_id}. Future answers will use the selected governing source.`);
      setSelectedConflict(null);
      await refresh();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'Conflict resolution could not be recorded.');
    } finally {
      setResolving(false);
    }
  };

  const openConflicts = conflicts.filter((conflict) => conflict.status !== 'resolved');
  const resolvedConflicts = conflicts.filter((conflict) => conflict.status === 'resolved');
  return (
    <div className="page-container">
      <section className="page-heading">
        <div>
          <p className="eyebrow">Revision governance</p>
          <h1>Conflicts &amp; authority</h1>
          <p className="page-description">Compare active source instructions and review document authority for {machineModel}.</p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={() => void refresh()} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh records'}
        </button>
      </section>

      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {success && <div className="notice notice-success" role="status">{success}</div>}
      {!can('conflict_resolver') && (
        <div className="notice notice-neutral">
          Conflict resolutions require a verified <code>conflict_resolver</code> role.
          {authStatus === 'unconfigured' && ' OIDC sign-in is not configured.'}
        </div>
      )}

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Human disposition required</p>
            <h2>Active conflicts <span className="count-badge">{openConflicts.length}</span></h2>
          </div>
        </div>
        {loading ? <div className="loading-state">Loading conflict scan…</div> : null}
        {!loading && openConflicts.length === 0 && (
          <div className="empty-state">No unresolved conflicts were detected for this machine scope.</div>
        )}
        <div className="conflict-list">
          {openConflicts.map((conflict) => (
            <article className="conflict-card" key={conflict.conflict_id}>
              <div className="conflict-header">
                <div>
                  <span className={`status-pill ${conflict.severity === 'critical' ? 'status-negative' : 'status-warning'}`}>
                    {conflict.severity} severity
                  </span>
                  <h3>{conflict.parameter_or_topic}</h3>
                </div>
                <code>{conflict.conflict_id}</code>
              </div>
              <p className="conflict-description">{conflict.description}</p>
              <div className="conflict-comparison">
                <SourceCard
                  label="Source A"
                  document={conflict.document_a_number}
                  revision={conflict.document_a_revision}
                  status={conflict.document_a_status}
                  instruction={conflict.instruction_a}
                />
                <SourceCard
                  label="Source B"
                  document={conflict.document_b_number}
                  revision={conflict.document_b_revision}
                  status={conflict.document_b_status}
                  instruction={conflict.instruction_b}
                />
              </div>
              <div className="conflict-footer">
                <p>{conflict.recommended_action}</p>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => openResolution(conflict)}
                  disabled={!can('conflict_resolver')}
                >
                  Review resolution
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>

      {resolvedConflicts.length > 0 && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Recorded decisions</p>
              <h2>Resolved conflicts ({resolvedConflicts.length})</h2>
            </div>
          </div>
          <div className="activity-list">
            {resolvedConflicts.map((conflict) => (
              <article className="activity-item" key={conflict.conflict_id}>
                <div className="activity-main">
                  <strong>{conflict.parameter_or_topic}</strong>
                  <span>{conflict.resolution_action?.replace(/_/g, ' ') || 'Resolved'}</span>
                </div>
                <div className="activity-meta">
                  <span>Governing document: {conflict.winning_document_id === conflict.document_a_id ? conflict.document_a_number : conflict.document_b_number}</span>
                  <span>{conflict.resolved_by || 'Resolver unavailable'}</span>
                </div>
                {conflict.resolution_notes && <p>{conflict.resolution_notes}</p>}
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Revision register</p>
            <h2>Document authority</h2>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Document</th><th>Revision</th><th>Status</th><th>Authority</th><th>Effective</th><th>Expires</th><th>Superseded by</th></tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} className="table-state">Loading revision register…</td></tr>
              ) : matrix.length === 0 ? (
                <tr><td colSpan={7} className="table-state">No revision records found for this machine.</td></tr>
              ) : matrix.map((row) => (
                <tr key={row.id}>
                  <td><strong>{row.document_number}</strong><small className="table-subtitle">{row.title}</small></td>
                  <td>{row.revision}</td>
                  <td><span className="status-pill status-neutral">{row.approval_status}</span></td>
                  <td title={row.authority_reason}>{row.is_authoritative ? 'Authoritative' : row.authority_reason}</td>
                  <td>{row.effective_date ? new Date(row.effective_date).toLocaleDateString() : 'Not specified'}</td>
                  <td>{row.expiry_date ? new Date(row.expiry_date).toLocaleDateString() : 'Not specified'}</td>
                  <td>{row.superseded_by_id ? matrix.find((document) => document.id === row.superseded_by_id)?.document_number || row.superseded_by_id.slice(0, 8) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {selectedConflict && (
        <div className="modal-backdrop" role="presentation">
          <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="resolve-title">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Authorized action</p>
                <h2 id="resolve-title">Resolve {selectedConflict.parameter_or_topic}</h2>
              </div>
              <button type="button" className="icon-button" onClick={() => setSelectedConflict(null)} disabled={resolving} aria-label="Close resolution dialog">×</button>
            </div>
            <form className="form-grid" onSubmit={(event) => void handleResolve(event)}>
              <label className="form-field form-span">
                <span>Governing source</span>
                <select value={winnerId} onChange={(event) => setWinnerId(event.target.value)} required>
                  <option value={selectedConflict.document_a_id}>{selectedConflict.document_a_number} · {selectedConflict.document_a_revision}</option>
                  <option value={selectedConflict.document_b_id}>{selectedConflict.document_b_number} · {selectedConflict.document_b_revision}</option>
                </select>
              </label>
              <label className="form-field form-span">
                <span>Disposition</span>
                <select value={resolutionAction} onChange={(event) => setResolutionAction(event.target.value as ResolutionAction)}>
                  <option value="approve_exception">Record a scoped governing-source exception</option>
                  {can('document_approver') && (
                    <>
                      <option value="mark_superseded">Mark the other document superseded</option>
                      <option value="withdraw_conflicting">Withdraw the other document</option>
                    </>
                  )}
                </select>
              </label>
              {resolutionAction !== 'approve_exception' && (
                <div className="notice notice-warning form-span">
                  This changes the status of the entire losing document, not only this parameter. Use only when the full document is no longer valid.
                </div>
              )}
              {!can('document_approver') && resolutionAction !== 'approve_exception' && (
                <div className="notice notice-neutral form-span">This disposition also requires the document_approver role.</div>
              )}
              <label className="form-field form-span">
                <span>Resolution rationale</span>
                <textarea value={resolutionNotes} onChange={(event) => setResolutionNotes(event.target.value)} minLength={3} maxLength={4000} required rows={4} />
              </label>
              {error && <div className="notice notice-error form-span" role="alert">{error}</div>}
              <div className="form-actions form-span">
                <button type="button" className="btn btn-secondary" onClick={() => setSelectedConflict(null)} disabled={resolving}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={resolving || !can('conflict_resolver') || (resolutionAction !== 'approve_exception' && !can('document_approver'))}>
                  {resolving ? 'Recording…' : 'Confirm resolution'}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
};

const SourceCard: React.FC<{
  label: string;
  document: string;
  revision: string;
  status: string;
  instruction: string;
}> = ({ label, document, revision, status, instruction }) => (
  <div className="source-card">
    <div className="source-card-heading">
      <span>{label}</span>
      <span className="status-pill status-neutral">{status}</span>
    </div>
    <strong>{document} · {revision}</strong>
    <blockquote>{instruction}</blockquote>
  </div>
);
