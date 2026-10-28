import {
  AuthenticatedProfile,
  DocumentConflict,
  DocumentDetails,
  DocumentItem,
  DocumentSummary,
  EvaluationResponse,
  GroundedAnswerResponse,
  RetrievedPassage,
  ReviewItem,
  RevisionRecord,
  SystemHealth,
  WorkInstruction,
} from '../types';
import { getAccessToken } from './oidc';

const API_BASE = (import.meta.env.VITE_API_BASE_URL?.trim() || '/api').replace(/\/+$/, '');

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

interface DocumentListResponse {
  items: DocumentItem[];
  total: number;
}

interface RetrievalSearchResponse {
  results: RetrievedPassage[];
  retrieval_latency_ms: number;
  provider_used: string;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  accessToken?: string | null,
): Promise<T> {
  const headers = new Headers(init.headers);
  const token = accessToken === undefined ? await getAccessToken() : accessToken;
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    const body = await response.text();
    let message = `Request failed (${response.status}).`;
    if (body) {
      try {
        const payload = JSON.parse(body) as { detail?: unknown; message?: unknown };
        if (typeof payload.detail === 'string') message = payload.detail;
        else if (typeof payload.message === 'string') message = payload.message;
      } catch {
        message = `Request failed (${response.status}).`;
      }
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  async getHealth(): Promise<SystemHealth> {
    return request('/health');
  },

  async getCurrentUser(accessToken: string): Promise<AuthenticatedProfile> {
    return request('/auth/me', {}, accessToken);
  },

  async getDocuments(
    status?: string,
    machine?: string,
    skip = 0,
    limit = 50,
    search?: string,
  ): Promise<DocumentListResponse> {
    const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
    if (status) params.set('approval_status', status);
    if (machine) params.set('machine_model', machine);
    if (search?.trim()) params.set('search', search.trim());
    return request(`/documents?${params.toString()}`);
  },

  async getDocumentSummary(): Promise<DocumentSummary> {
    return request('/documents/summary');
  },

  async getMachineModels(): Promise<string[]> {
    const response = await request<{ items: string[] }>('/documents/machines');
    return response.items;
  },

  async getDocumentDetails(id: string): Promise<DocumentDetails> {
    return request(`/documents/${encodeURIComponent(id)}`);
  },

  async uploadDocument(formData: FormData): Promise<DocumentItem> {
    return request('/documents/upload', { method: 'POST', body: formData });
  },

  async updateDocumentStatus(
    id: string,
    approval_status: string,
    superseded_by_id?: string,
  ): Promise<DocumentItem> {
    return request(`/documents/${encodeURIComponent(id)}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approval_status, superseded_by_id }),
    });
  },

  async deleteDocument(id: string): Promise<void> {
    return request(`/documents/${encodeURIComponent(id)}`, { method: 'DELETE' });
  },

  async askQuestion(
    question: string,
    mode: 'hybrid' | 'bm25' | 'vector' = 'hybrid',
    machine_model = 'DEMO-CNC-01',
    filter_approved_only = true,
  ): Promise<GroundedAnswerResponse> {
    return request('/qa/ask', {
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
  },

  async searchRetrieval(
    query: string,
    mode: 'hybrid' | 'bm25' | 'vector' = 'hybrid',
    top_k = 5,
    machine_model = 'DEMO-CNC-01',
  ): Promise<RetrievalSearchResponse> {
    return request('/retrieval/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        mode,
        top_k,
        filter_approved_only: false,
        machine_model,
      }),
    });
  },

  async getConflicts(machine?: string): Promise<DocumentConflict[]> {
    const params = new URLSearchParams();
    if (machine) params.set('machine_model', machine);
    const query = params.toString();
    return request(`/governance/conflicts${query ? `?${query}` : ''}`);
  },

  async resolveConflict(
    conflict_id: string,
    winning_document_id: string,
    action_taken: 'mark_superseded' | 'withdraw_conflicting' | 'approve_exception',
    resolution_notes: string,
  ): Promise<{ status: string; conflict_id: string; winning_document_id: string; action_taken: string }> {
    return request('/governance/conflicts/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conflict_id,
        winning_document_id,
        action_taken,
        resolution_notes,
      }),
    });
  },

  async getRevisionMatrix(): Promise<RevisionRecord[]> {
    return request('/governance/revision-matrix');
  },

  async getAuditTrail(): Promise<Array<Record<string, unknown>>> {
    return request('/governance/audit-trail?limit=40');
  },

  async getReviewQueue(
    status?: string,
    origin: 'operational' | 'benchmark' | 'all' = 'operational',
  ): Promise<ReviewItem[]> {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    params.set('origin', origin);
    const query = params.toString();
    return request(`/review/queue${query ? `?${query}` : ''}`);
  },

  async takeReviewAction(
    item_id: string,
    action: 'approved' | 'rejected' | 'escalated',
    expert_notes: string,
  ): Promise<void> {
    return request(`/review/${encodeURIComponent(item_id)}/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, expert_notes }),
    });
  },

  async getWorkInstructions(): Promise<WorkInstruction[]> {
    return request('/instructions');
  },

  async draftWorkInstruction(
    title: string,
    task_summary: string,
    target_operation: string,
    machine_model: string,
  ): Promise<WorkInstruction> {
    return request('/instructions/draft', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title,
        task_summary,
        target_operation,
        machine_model,
        require_approved_sources_only: true,
      }),
    });
  },

  async approveWorkInstruction(id: string, comments: string): Promise<WorkInstruction> {
    return request(`/instructions/${encodeURIComponent(id)}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ comments }),
    });
  },

  async runEvaluation(): Promise<EvaluationResponse> {
    return request('/evaluation/run', { method: 'POST' });
  },

  async getEvaluationDataset(): Promise<{ cases: Array<Record<string, unknown>> }> {
    return request('/evaluation/dataset');
  },
};
