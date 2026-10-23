import React, { useState } from 'react';
import { api } from '../services/api';
import { RetrievedPassage } from '../types';

export const EvidenceExplorerPage: React.FC = () => {
  const [query, setQuery] = useState('spindle warm-up procedure');
  const [mode, setMode] = useState<'hybrid' | 'bm25' | 'vector'>('hybrid');
  const [topK, setTopK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<RetrievedPassage[]>([]);
  const [latency, setLatency] = useState<number | null>(null);
  const [providerUsed, setProviderUsed] = useState<string>('');
  const [selectedPassage, setSelectedPassage] = useState<RetrievedPassage | null>(null);

  const handleSearch = async () => {
    if (!query.trim()) return;
    try {
      setLoading(true);
      const res = await api.searchRetrieval(query, mode, topK);
      setResults(res.results || []);
      setLatency(res.retrieval_latency_ms);
      setProviderUsed(res.provider_used);
      if (res.results && res.results.length > 0) {
        setSelectedPassage(res.results[0]);
      }
    } catch (e: any) {
      alert(`Search error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container space-y-6">
      {/* Header */}
      <div className="card space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-3">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <span>🔍 Evidence Explorer & Rank Breakdown</span>
              <span className="badge badge-pending text-xs font-mono">Reciprocal Rank Fusion</span>
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Directly test BM25 keyword matching, Dense vector semantics, and RRF rank fusion with chunk-level transparency.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 bg-slate-900 border border-slate-700 px-3 py-1.5 rounded text-xs">
              <span className="text-slate-400">Mode:</span>
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as any)}
                className="bg-transparent text-cyan-300 font-mono font-semibold focus:outline-none"
              >
                <option value="hybrid" className="bg-slate-900 text-white">Hybrid (BM25 + Dense RRF)</option>
                <option value="bm25" className="bg-slate-900 text-white">BM25 Keyword</option>
                <option value="vector" className="bg-slate-900 text-white">Dense Vector</option>
              </select>
            </div>

            <div className="flex items-center gap-2 bg-slate-900 border border-slate-700 px-3 py-1.5 rounded text-xs">
              <span className="text-slate-400">Top K:</span>
              <input
                type="number"
                min={1}
                max={10}
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                className="w-12 bg-transparent text-cyan-300 font-mono font-semibold focus:outline-none"
              />
            </div>
          </div>
        </div>

        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Search passages across manufacturing corpus..."
            className="input-field"
          />
          <button onClick={handleSearch} disabled={loading} className="btn btn-primary px-6">
            {loading ? 'Searching...' : 'Execute Retrieval'}
          </button>
        </div>

        {latency !== null && (
          <div className="flex items-center justify-between text-xs font-mono text-slate-400 pt-1">
            <span>Provider: <strong className="text-cyan-400">{providerUsed}</strong></span>
            <span>Retrieved in <strong className="text-emerald-400">{latency} ms</strong></span>
          </div>
        )}
      </div>

      {/* Results View */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Ranked Passage List */}
        <div className="lg:col-span-2 space-y-3">
          <h3 className="text-xs font-semibold uppercase text-slate-400 tracking-wider">
            Retrieved Passages ({results.length})
          </h3>

          {results.length === 0 && !loading && (
            <div className="card text-center py-8 text-slate-400 text-xs">
              No passages retrieved. Click 'Execute Retrieval' to test the retrieval pipeline.
            </div>
          )}

          {results.map((p, idx) => {
            const isSelected = selectedPassage?.chunk_id === p.chunk_id;
            return (
              <div
                key={p.chunk_id}
                onClick={() => setSelectedPassage(p)}
                className={`card p-4 space-y-2 cursor-pointer transition-all ${
                  isSelected ? 'border-cyan-400 bg-slate-900' : 'hover:border-slate-600'
                }`}
              >
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded bg-cyan-600/30 text-cyan-400 flex items-center justify-center font-mono font-bold text-xs">
                      #{idx + 1}
                    </span>
                    <span className="font-mono font-bold text-white">
                      {p.document_number} ({p.revision})
                    </span>
                    <span className="badge badge-approved text-[10px]">Page {p.page_number}</span>
                  </div>

                  <div className="flex items-center gap-3 font-mono text-xs">
                    {p.bm25_rank && <span className="text-amber-400">BM25 Rank: #{p.bm25_rank}</span>}
                    {p.vector_rank && <span className="text-cyan-400">Vector Rank: #{p.vector_rank}</span>}
                    <span className="text-emerald-400 font-bold">RRF Score: {p.score}</span>
                  </div>
                </div>

                <div className="text-xs text-slate-300 font-sans line-clamp-3">
                  {p.content}
                </div>

                <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono pt-1 border-t border-slate-800">
                  <span>Section: {p.section_title}</span>
                  <span>{p.has_images ? '📷 Contains Embedded Visual' : 'Text Only'}</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Right: Detailed Passage & Visual Inspector */}
        <div className="space-y-4">
          <h3 className="text-xs font-semibold uppercase text-slate-400 tracking-wider">
            Evidence Detail & Visual Inspection
          </h3>

          {selectedPassage ? (
            <div className="card space-y-4 border-slate-700">
              <div className="border-b border-slate-800 pb-2">
                <div className="font-mono text-xs text-cyan-400 font-bold">
                  {selectedPassage.document_number} {selectedPassage.revision} - Page {selectedPassage.page_number}
                </div>
                <div className="text-xs text-slate-400 mt-0.5">{selectedPassage.document_title}</div>
              </div>

              <div className="text-xs font-mono bg-slate-950 p-3 rounded space-y-1">
                <div><span className="text-slate-500">SECTION:</span> {selectedPassage.section_title}</div>
                <div><span className="text-slate-500">AUTHORITY:</span> {selectedPassage.is_authoritative ? 'APPROVED OPERATIONAL' : 'NON-AUTHORITATIVE'}</div>
                <div><span className="text-slate-500">FINAL SCORE:</span> {selectedPassage.score}</div>
              </div>

              <div className="space-y-1">
                <span className="text-xs text-slate-400 font-semibold">Passage Content:</span>
                <div className="p-3 bg-slate-900 border border-slate-800 rounded text-xs text-slate-200 whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto">
                  {selectedPassage.content}
                </div>
              </div>

              {selectedPassage.image_paths && selectedPassage.image_paths.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-slate-800">
                  <span className="text-xs text-slate-400 font-semibold">Page Schematic Snapshot:</span>
                  <div className="border border-slate-800 rounded overflow-hidden bg-slate-950">
                    <img
                      src={selectedPassage.image_paths[0]}
                      alt="Extracted Schematic"
                      className="w-full h-auto object-contain"
                    />
                  </div>
                  <p className="text-[10px] text-slate-500 italic">
                    Note: Multimodal support provides linked high-resolution extraction and OCR text indexing.
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div className="card text-center py-12 text-slate-500 text-xs">
              Select a passage to inspect full metadata and visual diagrams.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
