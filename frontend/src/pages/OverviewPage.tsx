import React, { useEffect, useState } from 'react';
import { NavTab } from '../components/Navbar';
import { api, ApiError } from '../services/api';
import { DocumentSummary, SystemHealth } from '../types';

interface OverviewPageProps {
  machineModel: string;
  onNavigate: (tab: NavTab) => void;
}

interface OverviewData {
  summary: DocumentSummary;
  conflicts: number;
  pendingReviews: number;
  auditLogs: Array<Record<string, unknown>>;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({ machineModel, onNavigate }) => {
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([
      api.getDocumentSummary(),
      api.getConflicts(machineModel),
      api.getReviewQueue('pending'),
      api.getAuditTrail(),
    ])
      .then(([summary, conflicts, reviews, auditLogs]) => {
        if (!active) return;
        setData({
          summary,
          conflicts: conflicts.filter((conflict) => conflict.status !== 'resolved').length,
          pendingReviews: reviews.length,
          auditLogs: auditLogs.slice(0, 8),
        });
        setError(null);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setData(null);
        setError(reason instanceof ApiError ? reason.message : 'Dashboard data could not be loaded.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [machineModel]);

  const statusCounts = data?.summary.status_counts ?? {};

  return (
    <div className="page-container">
      <section className="page-heading">
        <div>
          <p className="eyebrow">Operations overview</p>
          <h1>Knowledge operations</h1>
          <p className="page-description">
            Document authority, human review and recent system activity for <strong>{machineModel}</strong>.
          </p>
        </div>
        <div className="heading-actions">
          <button type="button" className="btn btn-secondary" onClick={() => onNavigate('library')}>
            Browse documents
          </button>
          <button type="button" className="btn btn-primary" onClick={() => onNavigate('assistant')}>
            Open assistant
          </button>
        </div>
      </section>

      {error && (
        <div className="notice notice-error" role="alert">
          <strong>Overview unavailable.</strong> {error}
        </div>
      )}

      <section className="metric-grid" aria-label="Operational summaries">
        <Metric label="Documents" value={loading ? null : data?.summary.total_documents} detail="All recorded revisions" />
        <Metric label="Approved" value={loading ? null : statusCounts.Approved ?? 0} detail="Status only; check authority dates" tone="positive" />
        <Metric label="Superseded" value={loading ? null : statusCounts.Superseded ?? 0} detail="Retained for revision history" />
        <Metric label="Open conflicts" value={loading ? null : data?.conflicts} detail="Human resolution required" tone="warning" onClick={() => onNavigate('conflicts')} />
        <Metric label="Pending review" value={loading ? null : data?.pendingReviews} detail="Benchmark history excluded; unverified history retained" onClick={() => onNavigate('review')} />
      </section>

      {data && data.summary.synthetic_documents > 0 && (
        <div className="notice notice-warning" role="note">
          <strong>{data.summary.synthetic_documents} synthetic document(s)</strong> are present in the registry. Synthetic records are not operational authority.
        </div>
      )}

      <div className="overview-grid">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Document registry</p>
              <h2>Approval status</h2>
            </div>
            <button type="button" className="text-button" onClick={() => onNavigate('library')}>
              View library
            </button>
          </div>
          {loading ? (
            <div className="loading-state" role="status">Loading document summary…</div>
          ) : data ? (
            <dl className="status-list">
              {Object.entries(statusCounts).length === 0 ? (
                <div className="empty-state">No documents have been registered.</div>
              ) : Object.entries(statusCounts).map(([status, count]) => (
                <div className="status-row" key={status}>
                  <dt>{status}</dt>
                  <dd>{count}</dd>
                </div>
              ))}
            </dl>
          ) : null}
          <p className="panel-footnote">
            Approval status is not a substitute for effective-date, expiry-date or machine-scope checks.
          </p>
        </section>

        <section className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Audit trail</p>
              <h2>Recent activity</h2>
            </div>
            <button
              type="button"
              className="text-button"
              onClick={() => window.location.reload()}
              disabled={loading}
            >
              Refresh
            </button>
          </div>
          {loading ? (
            <div className="loading-state" role="status">Loading audit events…</div>
          ) : data?.auditLogs.length ? (
            <div className="activity-list">
              {data.auditLogs.map((log) => (
                <article className="activity-item" key={String(log.id)}>
                  <div className="activity-main">
                    <strong>{String(log.action || 'Event')}</strong>
                    <span>{String(log.resource_type || 'system')}</span>
                  </div>
                  <div className="activity-meta">
                    <span>{String(log.actor || 'Unknown actor')}</span>
                    <time>{log.timestamp ? new Date(String(log.timestamp)).toLocaleString() : 'Time unavailable'}</time>
                  </div>
                </article>
              ))}
            </div>
          ) : data ? (
            <div className="empty-state">No audit events have been recorded.</div>
          ) : null}
        </section>
      </div>
    </div>
  );
};

interface MetricProps {
  label: string;
  value: number | null | undefined;
  detail: string;
  tone?: 'positive' | 'warning';
  onClick?: () => void;
}

const Metric: React.FC<MetricProps> = ({ label, value, detail, tone, onClick }) => {
  const content = (
    <>
      <span className="metric-label">{label}</span>
      <strong className={`metric-value ${tone ? `tone-${tone}` : ''}`}>
        {value === null || value === undefined ? '—' : value.toLocaleString()}
      </strong>
      <span className="metric-detail">{detail}</span>
    </>
  );
  return onClick ? (
    <button type="button" className="metric-card metric-action" onClick={onClick}>{content}</button>
  ) : (
    <div className="metric-card">{content}</div>
  );
};
