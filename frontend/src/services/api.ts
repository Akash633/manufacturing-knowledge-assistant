import {
  DocumentItem,
  GroundedAnswerResponse,
  RetrievedPassage,
  DocumentConflict,
  ReviewItem,
  WorkInstruction,
  EvaluationResponse,
} from '../types';

const API_BASE = '/api';

export const api = {
  // Document endpoints
  async getDocuments(status?: string, machine?: string): Promise<{ items: DocumentItem[]; total: number }> {
    const params = new URLSearchParams();
    if (status) params.append('approval_status', status);
    if (machine) params.append('machine_model', machine);
    const res = await fetch(`${API_BASE}/documents?${params.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch documents');
    return res.json();
  },

  async getDocumentDetails(id: string): Promise<any> {
    const res = await fetch(`${API_BASE}/documents/${id}`);
    if (!res.ok) throw new Error('Failed to fetch document details');
    return res.json();
  },

  async uploadDocument(formData: FormData): Promise<DocumentItem> {
    const res = await fetch(`${API_BASE}/documents/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Upload failed');
    }
    return res.json();
  },

  async updateDocumentStatus(id: string, approval_status: string, superseded_by_id?: string): Promise<DocumentItem> {
    const res = await fetch(`${API_BASE}/documents/${id}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approval_status, superseded_by_id }),
    });
    if (!res.ok) throw new Error('Failed to update status');
    return res.json();
  },

  async deleteDocument(id: string): Promise<void> {
    const res = await fetch(`${API_BASE}/documents/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete document');
  },

  // Q&A endpoint
  async askQuestion(
    question: string,
    mode: 'hybrid' | 'bm25' | 'vector' = 'hybrid',
    machine_model: string = 'DEMO-CNC-01',
    filter_approved_only: boolean = true,
  ): Promise<GroundedAnswerResponse> {
    const res = await fetch(`${API_BASE}/qa/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        retrieval_mode: mode,
        machine_model,
        filter_approved_only,
        top_k: 5,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to answer question');
    }
    return res.json();
  },

  // Retrieval search
  async searchRetrieval(
    query: string,
    mode: 'hybrid' | 'bm25' | 'vector' = 'hybrid',
    top_k: number = 5,
  ): Promise<any> {
    const res = await fetch(`${API_BASE}/retrieval/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        mode,
        top_k,
        filter_approved_only: false,
        machine_model: 'DEMO-CNC-01',
      }),
    });
    if (!res.ok) throw new Error('Search failed');
    return res.json();
  },

  // Governance
  async getConflicts(): Promise<DocumentConflict[]> {
    const res = await fetch(`${API_BASE}/governance/conflicts`);
    if (!res.ok) throw new Error('Failed to fetch conflicts');
    return res.json();
  },

  async resolveConflict(conflict_id: string, action_taken: string, resolution_notes: string): Promise<any> {
    const res = await fetch(`${API_BASE}/governance/conflicts/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conflict_id, action_taken, resolution_notes, resolver: 'Lead Quality Specialist' }),
    });
    if (!res.ok) throw new Error('Failed to resolve conflict');
    return res.json();
  },

  async getRevisionMatrix(): Promise<any[]> {
    const res = await fetch(`${API_BASE}/governance/revision-matrix`);
    if (!res.ok) throw new Error('Failed to fetch revision matrix');
    return res.json();
  },

  async getAuditTrail(): Promise<any[]> {
    const res = await fetch(`${API_BASE}/governance/audit-trail?limit=40`);
    if (!res.ok) throw new Error('Failed to fetch audit trail');
    return res.json();
  },

  // Expert Review Queue
  async getReviewQueue(status?: string): Promise<ReviewItem[]> {
    const url = status ? `${API_BASE}/review/queue?status=${status}` : `${API_BASE}/review/queue`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch review queue');
    return res.json();
  },

  async takeReviewAction(item_id: string, action: string, expert_notes: string): Promise<any> {
    const res = await fetch(`${API_BASE}/review/${item_id}/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, expert_notes, reviewer_name: 'Senior Manufacturing Specialist' }),
    });
    if (!res.ok) throw new Error('Failed to submit review action');
    return res.json();
  },

  // Work Instructions
  async getWorkInstructions(): Promise<WorkInstruction[]> {
    const res = await fetch(`${API_BASE}/instructions`);
    if (!res.ok) throw new Error('Failed to fetch work instructions');
    return res.json();
  },

  async draftWorkInstruction(title: string, task_summary: string, target_operation: string): Promise<WorkInstruction> {
    const res = await fetch(`${API_BASE}/instructions/draft`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title,
        task_summary,
        target_operation,
        machine_model: 'DEMO-CNC-01',
        require_approved_sources_only: true,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to draft instruction');
    }
    return res.json();
  },

  async approveWorkInstruction(id: string): Promise<WorkInstruction> {
    const res = await fetch(`${API_BASE}/instructions/${id}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        reviewer_name: 'Plant Quality Lead',
        comments: 'Verified against active machine SOP-CNC-001 Rev B.',
      }),
    });
    if (!res.ok) throw new Error('Failed to approve instruction');
    return res.json();
  },

  // Evaluation
  async runEvaluation(): Promise<EvaluationResponse> {
    const res = await fetch(`${API_BASE}/evaluation/run`, { method: 'POST' });
    if (!res.ok) throw new Error('Evaluation execution failed');
    return res.json();
  },

  async getEvaluationDataset(): Promise<any> {
    const res = await fetch(`${API_BASE}/evaluation/dataset`);
    if (!res.ok) throw new Error('Failed to fetch dataset');
    return res.json();
  },
};
