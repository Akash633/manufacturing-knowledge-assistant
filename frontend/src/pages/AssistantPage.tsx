import React, { FormEvent, useState } from 'react';
import { api, ApiError } from '../services/api';
import { GroundedAnswerResponse } from '../types';

interface AssistantPageProps {
  machineModel: string;
}

export const AssistantPage: React.FC<AssistantPageProps> = ({ machineModel }) => {
  const [question, setQuestion] = useState('');
  const [mode, setMode] = useState<'hybrid' | 'bm25' | 'vector'>('hybrid');
  const [filterApproved, setFilterApproved] = useState(true);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<GroundedAnswerResponse[]>([]);
  const [error, setError] = useState<string | null>(null);

  const sampleQueries = [
    { label: 'Spindle warm-up', query: `What is the spindle warm-up procedure and duration for ${machineModel}?` },
    { label: 'Titanium feed conflict', query: `What is the maximum allowable feed rate for Titanium Grade 5 on ${machineModel}?` },
    { label: 'Safety interlock', query: 'How do I bypass the safety door interlock while the spindle is running?' },
    { label: 'Out of scope', query: `What is the laser cutting assist gas pressure on ${machineModel}?` },
  ];

  const handleAsk = async (event?: FormEvent, queryText?: string) => {
    event?.preventDefault();
    const query = (queryText ?? question).trim();
    if (!query || loading) return;

    setError(null);
    setLoading(true);
    try {
      const response = await api.askQuestion(query, mode, machineModel, filterApproved);
      setHistory((current) => [response, ...current]);
      setQuestion('');
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'The assistant could not complete the request.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container">
      <section className="page-heading">
        <div>
          <p className="eyebrow">Evidence-grounded Q&amp;A</p>
          <h1>Shop floor assistant</h1>
          <p className="page-description">
            Answers are based on retrieved source passages. They are not machine authorization or a substitute for current site procedures.
          </p>
        </div>
      </section>

      <section className="panel assistant-composer">
        <form onSubmit={(event) => void handleAsk(event)}>
          <label className="field-label" htmlFor="assistant-question">Question for {machineModel}</label>
          <textarea
            id="assistant-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask about a procedure, maintenance task or documented parameter…"
            rows={3}
            disabled={loading}
          />
          <div className="composer-controls">
            <label className="control-inline">
              Retrieval method
              <select value={mode} onChange={(event) => setMode(event.target.value as typeof mode)}>
                <option value="hybrid">Hybrid search</option>
                <option value="bm25">Keyword (BM25)</option>
                <option value="vector">Vector</option>
              </select>
            </label>
            <label className="checkbox-control">
              <input
                type="checkbox"
                checked={filterApproved}
                onChange={(event) => setFilterApproved(event.target.checked)}
              />
              Approved revisions only
            </label>
            <button type="submit" className="btn btn-primary" disabled={loading || !question.trim()}>
              {loading ? 'Searching evidence…' : 'Ask assistant'}
            </button>
          </div>
        </form>
        <div className="scenario-row" aria-label="Example questions">
          <span className="field-label">Examples</span>
          {sampleQueries.map((item) => (
            <button
              key={item.label}
              type="button"
              className="text-button"
              disabled={loading}
              onClick={() => {
                setQuestion(item.query);
                void handleAsk(undefined, item.query);
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      </section>

      {error && <div className="notice notice-error" role="alert">{error}</div>}

      {loading && <div className="loading-state" role="status">Retrieving approved evidence and checking governance…</div>}

      {history.length === 0 && !loading && (
        <div className="empty-state panel">
          No questions yet. Ask a question or choose an example to inspect its source evidence.
        </div>
      )}

      <section className="answer-list" aria-label="Assistant responses">
        {history.map((response, index) => (
          <article className="panel answer-card" key={`${response.audit_log_id || response.question}-${index}`}>
            <div className="answer-heading">
              <div>
                <p className="eyebrow">Question</p>
                <h2>{response.question}</h2>
              </div>
              <div className="answer-meta">
                <span className={`status-pill ${response.abstained ? 'status-warning' : 'status-positive'}`}>
                  {response.abstained
                    ? `Abstained · ${response.abstention_reason.replace(/_/g, ' ')}`
                    : 'Response returned'}
                </span>
                <span>{response.retrieval_mode_used} · {response.latency_ms} ms</span>
              </div>
            </div>

            {response.conflicts_detected.length > 0 && (
              <div className="notice notice-warning" role="alert">
                <strong>Unresolved document conflict.</strong>
                <ul>
                  {response.conflicts_detected.map((conflict) => <li key={conflict}>{conflict}</li>)}
                </ul>
              </div>
            )}
            {response.safety_escalation.is_safety_critical && (
              <div className="notice notice-error" role="alert">
                Safety review required. Do not perform the requested operation. {response.safety_escalation.escalation_reason}
              </div>
            )}
            {response.abstention_explanation && (
              <div className="notice notice-warning">{response.abstention_explanation}</div>
            )}

            <div className="answer-body">{response.answer}</div>
            <p className="answer-disclaimer">
              Provider: <strong>{response.provider_used.replace(/_/g, ' ')}</strong>. Returned text is not an approval or authorization to operate equipment.
            </p>

            {response.citations.length > 0 && (
              <section className="evidence-section">
                <div className="panel-heading">
                  <h3>Sources cited ({response.citations.length})</h3>
                  <span>{response.citations.every((citation) => citation.is_valid) ? 'Citations validated' : 'Citation validation warning'}</span>
                </div>
                <div className="citation-grid">
                  {response.citations.map((citation) => (
                    <article className="citation-card" key={citation.citation_id}>
                      <div className="citation-title">
                        <strong>{citation.document_number}</strong>
                        <span>{citation.revision} · p. {citation.page_number}</span>
                      </div>
                      <p>{citation.snippet}</p>
                      <div className="citation-meta">
                        <span>{citation.section_title || 'Section not specified'}</span>
                        <span>{citation.is_authoritative ? 'Authoritative at retrieval' : 'Not authoritative'}</span>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            )}

            {response.retrieved_passages.length > 0 && (
              <details className="retrieved-details">
                <summary>Retrieved evidence ({response.retrieved_passages.length})</summary>
                <div className="retrieved-list">
                  {response.retrieved_passages.map((passage) => (
                    <article key={passage.chunk_id}>
                      <div className="citation-title">
                        <strong>{passage.document_number} {passage.revision}</strong>
                        <span>Page {passage.page_number}</span>
                      </div>
                      <p>{passage.content}</p>
                    </article>
                  ))}
                </div>
              </details>
            )}
          </article>
        ))}
      </section>
    </div>
  );
};
