import React, { useState } from 'react';
import { api, ApiError } from '../services/api';
import { EvaluationResponse } from '../types';

interface DatasetCase {
  id?: string;
  category?: string;
  query?: string;
  expected_docs?: string[];
  should_abstain?: boolean;
  expected_abstention_reason?: string;
  is_safety_critical?: boolean;
}

const metricLabels: Record<string, string> = {
  recall_at_1: 'Recall @ 1',
  recall_at_3: 'Recall @ 3',
  recall_at_5: 'Recall @ 5',
  citation_validity_precision: 'Citation validity precision',
  abstention_accuracy: 'Abstention accuracy',
  safety_escalation_compliance: 'Safety escalation compliance',
  conflict_detection_rate: 'Conflict detection rate',
  revision_freshness_rate: 'Revision freshness rate',
  avg_latency_ms: 'Average latency',
};

const formatMetric = (key: string, value: number | null | undefined): string => {
  if (value === null || value === undefined || !Number.isFinite(value)) return 'Not measured';
  return key === 'avg_latency_ms' ? `${value.toFixed(2)} ms` : `${(value * 100).toFixed(1)}%`;
};

export const EvaluationPage: React.FC = () => {
  const [evalData, setEvalData] = useState<EvaluationResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [datasetCases, setDatasetCases] = useState<DatasetCase[]>([]);
  const [showDataset, setShowDataset] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [datasetLoading, setDatasetLoading] = useState(false);

  const handleRunEvaluation = async () => {
    setError(null);
    setRunning(true);
    try {
      setEvalData(await api.runEvaluation());
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'The benchmark run could not be completed.');
    } finally {
      setRunning(false);
    }
  };

  const handleLoadDataset = async () => {
    setError(null);
    setDatasetLoading(true);
    try {
      const data = await api.getEvaluationDataset();
      setDatasetCases(data.cases as DatasetCase[]);
      setShowDataset(true);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'The benchmark dataset could not be loaded.');
    } finally {
      setDatasetLoading(false);
    }
  };

  const comparison = evalData?.comparison ?? {};
  const metricKeys = Object.keys(comparison);

  return (
    <div className="page-container">
      <section className="page-heading">
        <div>
          <p className="eyebrow">Measured system behavior</p>
          <h1>Evaluation &amp; benchmarks</h1>
          <p className="page-description">
            Run the configured ground-truth suite against the current document registry. Results are generated on request and are not a certification of operational safety.
          </p>
        </div>
        <div className="heading-actions">
          <button type="button" className="btn btn-secondary" onClick={() => void handleLoadDataset()} disabled={datasetLoading}>
            {datasetLoading ? 'Loading cases…' : 'View benchmark cases'}
          </button>
          <button type="button" className="btn btn-primary" onClick={() => void handleRunEvaluation()} disabled={running}>
            {running ? 'Running benchmark…' : 'Run benchmark'}
          </button>
        </div>
      </section>

      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {running && <div className="loading-state" role="status">Evaluating retrieval modes against the configured test dataset…</div>}

      {evalData ? (
        <>
          <div className="benchmark-run-meta">
            <span>Run timestamp <strong>{evalData.timestamp}</strong></span>
            <span>Benchmark queries <strong>{evalData.total_benchmark_queries}</strong></span>
          </div>
          <section className="metric-grid" aria-label="Measured benchmark metrics">
            {metricKeys.map((key) => (
              <article className="metric-card" key={key}>
                <span className="metric-label">{metricLabels[key] || key.replace(/_/g, ' ')}</span>
                <strong className="metric-value">{formatMetric(key, comparison[key]?.hybrid)}</strong>
                <span className="metric-detail">
                  BM25 {formatMetric(key, comparison[key]?.bm25)}
                  {' · Δ '}
                  {formatMetric(key, comparison[key]?.delta)}
                </span>
              </article>
            ))}
          </section>
          <section className="panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Per-mode comparison</p>
                <h2>Returned benchmark metrics</h2>
              </div>
            </div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Metric</th><th>BM25 baseline</th><th>Hybrid retrieval</th><th>Difference</th></tr></thead>
                <tbody>
                  {metricKeys.map((key) => (
                    <tr key={key}>
                      <td>{metricLabels[key] || key.replace(/_/g, ' ')}</td>
                      <td>{formatMetric(key, comparison[key]?.bm25)}</td>
                      <td>{formatMetric(key, comparison[key]?.hybrid)}</td>
                      <td>{formatMetric(key, comparison[key]?.delta)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {metricKeys.length === 0 && <div className="empty-state">The benchmark returned no comparable metrics.</div>}
          </section>
        </>
      ) : !running ? (
        <section className="panel empty-state benchmark-empty">
          <p>No benchmark run has been recorded in this view.</p>
          <p>Run the suite to view measured results for the current database and configured dataset.</p>
        </section>
      ) : null}

      {showDataset && (
        <div className="modal-backdrop" role="presentation">
          <section className="modal-panel dataset-modal" role="dialog" aria-modal="true" aria-labelledby="dataset-title">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Configured test input</p>
                <h2 id="dataset-title">Benchmark cases ({datasetCases.length})</h2>
              </div>
              <button type="button" className="icon-button" onClick={() => setShowDataset(false)} aria-label="Close benchmark cases">×</button>
            </div>
            <div className="dataset-list">
              {datasetCases.map((testCase, index) => (
                <article className="dataset-case" key={testCase.id || index}>
                  <div className="dataset-case-heading">
                    <strong>{testCase.id || `Case ${index + 1}`}</strong>
                    <span>{testCase.category || 'Uncategorized'}</span>
                  </div>
                  <p>{testCase.query || 'No query provided.'}</p>
                  <div className="dataset-case-meta">
                    <span>Expected documents: {testCase.expected_docs?.length ? testCase.expected_docs.join(', ') : 'None specified'}</span>
                    <span>{testCase.should_abstain ? `Expected abstention${testCase.expected_abstention_reason ? `: ${testCase.expected_abstention_reason}` : ''}` : 'Answer expected'}</span>
                    {testCase.is_safety_critical && <span className="status-pill status-warning">Safety critical</span>}
                  </div>
                </article>
              ))}
              {datasetCases.length === 0 && <div className="empty-state">The benchmark dataset contains no cases.</div>}
            </div>
          </section>
        </div>
      )}
    </div>
  );
};
