import React, { useState } from 'react';
import { api } from '../services/api';
import { GroundedAnswerResponse, Citation } from '../types';

export const AssistantPage: React.FC = () => {
  const [question, setQuestion] = useState('');
  const [mode, setMode] = useState<'hybrid' | 'bm25' | 'vector'>('hybrid');
  const [filterApproved, setFilterApproved] = useState(true);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<GroundedAnswerResponse[]>([]);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);

  const sampleQueries = [
    { label: 'Spindle Warm-up Cycle', query: 'What is the spindle warm-up procedure and duration for DEMO-CNC-01?' },
    { label: 'Titanium Feed Conflict', query: 'What is the maximum allowable feed rate when face milling Titanium Grade 5?' },
    { label: 'Safety Interlock (Escalation)', query: 'How do I bypass the safety door interlock to inspect chips while spindle is running?' },
    { label: 'LOTO Electrical (High Risk)', query: 'Can I open the 480V electrical cabinet to check drive fuses without performing lockout tagout?' },
    { label: 'Axis Backlash & Way Lube', query: 'What is the maximum allowable X-axis backlash and lubrication oil specification?' },
    { label: 'Unanswerable (Out of Scope)', query: 'What is the laser cutting assist gas pressure setting on DEMO-CNC-01?' },
  ];

  const handleAsk = async (queryText?: string) => {
    const q = (queryText || question).trim();
    if (!q) return;

    try {
      setLoading(true);
      const res = await api.askQuestion(q, mode, 'DEMO-CNC-01', filterApproved);
      setHistory((prev) => [res, ...prev]);
      if (res.citations.length > 0) {
        setSelectedCitation(res.citations[0]);
      }
      setQuestion('');
    } catch (e: any) {
      alert(`Error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container space-y-6">
      {/* Header & Query Panel */}
      <div className="card space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-3">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <span>🤖 Shop Floor AI Assistant</span>
              <span className="badge badge-approved text-xs">Grounded Execution</span>
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Ask operational, setup, maintenance, or parameter questions. Answers strictly derive from authorized documents.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 bg-slate-900 border border-slate-700 px-3 py-1.5 rounded-md text-xs">
              <span className="text-slate-400">Retrieval:</span>
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as any)}
                className="bg-transparent text-cyan-300 font-mono font-semibold focus:outline-none cursor-pointer"
              >
                <option value="hybrid" className="bg-slate-900 text-white">Hybrid (BM25 + Dense RRF)</option>
                <option value="bm25" className="bg-slate-900 text-white">BM25 Keyword Only</option>
                <option value="vector" className="bg-slate-900 text-white">Dense Vector Only</option>
              </select>
            </div>

            <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={filterApproved}
                onChange={(e) => setFilterApproved(e.target.checked)}
                className="rounded text-cyan-500 focus:ring-0"
              />
              Approved Revisions Only
            </label>
          </div>
        </div>

        {/* Input Box */}
        <div className="space-y-3">
          <div className="flex gap-2">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
              placeholder="e.g. What is the approved spindle warm-up routine? What is the way lube oil spec?"
              className="input-field"
              style={{ flex: 1 }}
              disabled={loading}
            />
            <button
              onClick={() => handleAsk()}
              disabled={loading || !question.trim()}
              className="btn btn-primary px-6 min-w-[130px]"
            >
              {loading ? 'Retrieving...' : 'Ask Assistant'}
            </button>
          </div>

          {/* Preset Scenario Buttons */}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <span className="text-xs text-slate-400 font-semibold">Test Scenarios:</span>
            {sampleQueries.map((item, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setQuestion(item.query);
                  handleAsk(item.query);
                }}
                className="btn btn-secondary py-1 px-2.5 text-xs font-normal"
                style={{ fontSize: '11px' }}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Conversation Stream */}
      <div className="space-y-6">
        {history.length === 0 && !loading && (
          <div className="card text-center py-12 text-slate-400 space-y-3">
            <div className="text-4xl">🛠️</div>
            <h3 className="font-semibold text-white">Awaiting Shop Floor Inquiries</h3>
            <p className="text-xs max-w-md mx-auto">
              Select one of the preset test scenarios above or type an operational query. The assistant retrieves evidence first, checks revision freshness, flags conflicts, and validates citations.
            </p>
          </div>
        )}

        {history.map((resp, idx) => (
          <div key={idx} className="card space-y-4 border-slate-700">
            {/* Question Header */}
            <div className="flex items-start justify-between gap-4 border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <span className="brand-icon" style={{ width: '24px', height: '24px', fontSize: '12px' }}>
                  Q
                </span>
                <span className="font-semibold text-white text-base">{resp.question}</span>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <span className="font-mono text-xs text-slate-400">
                  Latency: <strong className="text-cyan-300">{resp.latency_ms} ms</strong>
                </span>
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-900 text-slate-300 border border-slate-700">
                  {resp.retrieval_mode_used.toUpperCase()}
                </span>
              </div>
            </div>

            {/* Status Badges */}
            <div className="flex flex-wrap gap-2">
              {resp.abstained ? (
                <span className="badge badge-superseded">
                  ⚠️ ABSTAINED: {resp.abstention_reason.replace('_', ' ').toUpperCase()}
                </span>
              ) : (
                <span className="badge badge-approved">
                  ✓ GROUNDED & VERIFIED
                </span>
              )}

              {resp.safety_escalation.is_safety_critical && (
                <span className="badge" style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#fca5a5', border: '1px solid rgba(239, 68, 68, 0.5)' }}>
                  🚨 MANDATORY SAFETY REVIEW TRIGGERED
                </span>
              )}

              {resp.conflicts_detected.length > 0 && (
                <span className="badge" style={{ background: 'rgba(245, 158, 11, 0.2)', color: '#fde68a', border: '1px solid rgba(245, 158, 11, 0.5)' }}>
                  ⚖️ {resp.conflicts_detected.length} CONFLICT(S) DETECTED
                </span>
              )}
            </div>

            {/* Answer Content */}
            <div className="p-4 bg-slate-900 rounded-md border border-slate-800 text-sm leading-relaxed whitespace-pre-line text-slate-200 font-sans">
              {resp.answer}
            </div>

            {/* Verifiable Citations */}
            {resp.citations.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-slate-800">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-semibold uppercase text-slate-400 tracking-wider">
                    Traceable Citations ({resp.citations.length})
                  </h4>
                  <span className="text-[11px] text-emerald-400 font-mono">
                    ✓ Verified Against Retrieved Passages
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {resp.citations.map((cit) => (
                    <div
                      key={cit.citation_id}
                      onClick={() => setSelectedCitation(cit)}
                      className="p-3 bg-slate-950 border border-slate-800 rounded hover:border-cyan-500 cursor-pointer transition-colors space-y-1"
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-mono font-bold text-cyan-400">
                          [{cit.citation_id}] {cit.document_number} ({cit.revision})
                        </span>
                        <span className="badge badge-approved text-[10px]">Page {cit.page_number}</span>
                      </div>
                      <div className="text-xs text-slate-300 line-clamp-2 italic">
                        "{cit.snippet}"
                      </div>
                      <div className="text-[10px] text-slate-500 font-mono pt-1">
                        Section: {cit.section_title} | Authority: {cit.is_authoritative ? 'APPROVED' : 'NON-AUTHORITATIVE'}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
