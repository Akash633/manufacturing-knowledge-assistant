import React, { FormEvent, useState } from 'react';
import { api, ApiError } from '../services/api';
import { RetrievedPassage } from '../types';

interface EvidenceExplorerPageProps {
  machineModel: string;
}

export const EvidenceExplorerPage: React.FC<EvidenceExplorerPageProps> = ({ machineModel }) => {
  const [query, setQuery] = useState('spindle warm-up procedure');
  const [mode, setMode] = useState<'hybrid' | 'bm25' | 'vector'>('hybrid');
  const [topK, setTopK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<RetrievedPassage[]>([]);
  const [latency, setLatency] = useState<number | null>(null);
  const [selectedPassage, setSelectedPassage] = useState<RetrievedPassage | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!query.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await api.searchRetrieval(query, mode, topK, machineModel);
      setResults(response.results || []);
      setLatency(response.retrieval_latency_ms);
      setSelectedPassage(response.results?.[0] || null);
      setHasSearched(true);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : 'Evidence search could not be completed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container">
      <section className="page-heading">
        <div>
          <p className="eyebrow">Retrieval diagnostics</p>
          <h1>Evidence explorer</h1>
          <p className="page-description">
            Inspect ranked passages for {machineModel}. Results include non-authoritative records; verify status and revision before use.
          </p>
        </div>
      </section>

      <section className="panel search-panel">
        <form className="evidence-search-form" onSubmit={(event) => void handleSearch(event)}>
          <label className="field-label" htmlFor="evidence-query">Search source evidence</label>
          <div className="search-controls">
            <input
              id="evidence-query"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search terms or an operational question"
              disabled={loading}
            />
            <label className="control-inline">
              Method
              <select value={mode} onChange={(event) => setMode(event.target.value as typeof mode)}>
                <option value="hybrid">Hybrid</option>
                <option value="bm25">BM25</option>
                <option value="vector">Vector</option>
              </select>
            </label>
            <label className="control-inline">
              Results
              <input
                type="number"
                min={1}
                max={10}
                value={topK}
                onChange={(event) => setTopK(Math.min(10, Math.max(1, Number(event.target.value) || 1)))}
              />
            </label>
            <button type="submit" className="btn btn-primary" disabled={loading || !query.trim()}>
              {loading ? 'Searching…' : 'Search evidence'}
            </button>
          </div>
        </form>
        {latency !== null && (
          <p className="search-meta">Last search completed in {latency.toFixed(1)} ms.</p>
        )}
      </section>

      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {loading && <div className="loading-state" role="status">Searching document passages…</div>}

      <div className="evidence-layout">
        <section className="result-column" aria-label="Retrieved passages">
          <div className="panel-heading">
            <h2>Ranked passages</h2>
            <span>{hasSearched ? `${results.length} result(s)` : 'Not searched yet'}</span>
          </div>
          {hasSearched && results.length === 0 && !loading && (
            <div className="empty-state panel">No passages matched this search for the selected machine.</div>
          )}
          {!hasSearched && !loading && (
            <div className="empty-state panel">Run a search to inspect the source passages and ranking metadata.</div>
          )}
          {results.map((passage, index) => (
            <button
              type="button"
              className={`result-card ${selectedPassage?.chunk_id === passage.chunk_id ? 'selected' : ''}`}
              key={passage.chunk_id}
              onClick={() => setSelectedPassage(passage)}
              aria-pressed={selectedPassage?.chunk_id === passage.chunk_id}
            >
              <div className="result-card-header">
                <strong>#{index + 1} · {passage.document_number} {passage.revision}</strong>
                <span>{passage.score.toFixed(4)}</span>
              </div>
              <div className="result-card-meta">
                <span>Page {passage.page_number} · {passage.section_title || 'Section not specified'}</span>
                <span className={`status-pill ${passage.is_authoritative ? 'status-positive' : 'status-neutral'}`}>
                  {passage.is_authoritative ? 'Authoritative' : passage.approval_status}
                </span>
              </div>
              <p>{passage.content}</p>
            </button>
          ))}
        </section>

        <aside className="panel evidence-detail">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Source record</p>
              <h2>Passage detail</h2>
            </div>
          </div>
          {selectedPassage ? (
            <>
              <dl className="detail-list">
                <div><dt>Document</dt><dd>{selectedPassage.document_number}</dd></div>
                <div><dt>Revision</dt><dd>{selectedPassage.revision}</dd></div>
                <div><dt>Page</dt><dd>{selectedPassage.page_number}</dd></div>
                <div><dt>Approval state</dt><dd>{selectedPassage.approval_status}</dd></div>
                <div><dt>Authority</dt><dd>{selectedPassage.is_authoritative ? 'Authoritative' : 'Not authoritative'}</dd></div>
                <div><dt>Score</dt><dd>{selectedPassage.score.toFixed(4)}</dd></div>
              </dl>
              <h3 className="section-title">{selectedPassage.section_title || 'Source passage'}</h3>
              <blockquote className="source-quote">{selectedPassage.content}</blockquote>
              {selectedPassage.image_paths?.length > 0 && (
                <div className="image-evidence">
                  <h3 className="section-title">Linked page image</h3>
                  <img src={selectedPassage.image_paths[0]} alt={`Extracted evidence from ${selectedPassage.document_number}, page ${selectedPassage.page_number}`} />
                </div>
              )}
            </>
          ) : (
            <div className="empty-state">Select a result to inspect its source metadata.</div>
          )}
        </aside>
      </div>
    </div>
  );
};
