export type ApprovalStatus = 
  | 'Approved' 
  | 'Draft' 
  | 'Pending Review' 
  | 'Superseded' 
  | 'Withdrawn' 
  | 'Expired' 
  | 'Not Yet Effective';

export interface DocumentItem {
  id: string;
  document_number: string;
  title: string;
  revision: string;
  approval_status: ApprovalStatus;
  machine_model: string;
  section_category: string;
  effective_date: string | null;
  expiry_date: string | null;
  superseded_by_id: string | null;
  supersedes_id: string | null;
  file_path: string;
  file_type: string;
  file_size_bytes: number;
  checksum: string | null;
  page_count: number;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface RetrievedPassage {
  chunk_id: string;
  document_id: string;
  document_number: string;
  document_title: string;
  revision: string;
  approval_status: string;
  is_authoritative: boolean;
  page_number: number;
  section_title: string;
  content: string;
  score: number;
  bm25_rank?: number | null;
  vector_rank?: number | null;
  bm25_score?: number | null;
  vector_score?: number | null;
  has_images: boolean;
  image_paths: string[];
  ocr_applied: boolean;
}

export interface Citation {
  citation_id: string;
  chunk_id: string;
  document_id: string;
  document_number: string;
  revision: string;
  approval_status: string;
  page_number: number;
  section_title: string;
  snippet: string;
  is_authoritative: boolean;
  is_valid: boolean;
}

export interface SafetyEscalationInfo {
  is_safety_critical: boolean;
  risk_level: 'none' | 'low' | 'medium' | 'high' | 'critical';
  matched_rules: string[];
  escalation_reason?: string | null;
  requires_expert_review: boolean;
  review_item_id?: string | null;
}

export interface GroundedAnswerResponse {
  question: string;
  answer: string;
  abstained: boolean;
  abstention_reason: string;
  abstention_explanation?: string | null;
  citations: Citation[];
  retrieved_passages: RetrievedPassage[];
  safety_escalation: SafetyEscalationInfo;
  conflicts_detected: string[];
  authoritative_doc_ids: string[];
  retrieval_mode_used: string;
  provider_used: string;
  latency_ms: number;
  audit_log_id?: string | null;
}

export interface DocumentConflict {
  conflict_id: string;
  parameter_or_topic: string;
  description: string;
  document_a_id: string;
  document_a_number: string;
  document_a_revision: string;
  document_a_status: string;
  instruction_a: string;
  document_b_id: string;
  document_b_number: string;
  document_b_revision: string;
  document_b_status: string;
  instruction_b: string;
  severity: 'high' | 'critical' | 'medium';
  recommended_action: string;
  status: string;
}

export interface ReviewItem {
  id: string;
  item_type: string;
  status: string;
  priority: string;
  title: string;
  summary: string;
  details: Record<string, any>;
  proposed_action?: string | null;
  expert_notes?: string | null;
  reviewer?: string | null;
  resolved_at?: string | null;
  created_at: string;
}

export interface InstructionStep {
  step_number: number;
  title: string;
  description: string;
  safety_hazard?: string | null;
  verification_check?: string | null;
  source_citation?: string | null;
}

export interface WorkInstruction {
  id: string;
  instruction_number: string;
  title: string;
  machine_model: string;
  task_summary: string;
  approved_source_doc_ids: string[];
  steps: InstructionStep[];
  safety_warnings: string[];
  required_ppe: string[];
  status: string;
  is_published: boolean;
  created_by: string;
  reviewed_by?: string | null;
  review_comments?: string | null;
  reviewed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface BenchmarkMetrics {
  recall_at_1: number;
  recall_at_3: number;
  recall_at_5: number;
  citation_validity_precision: number;
  abstention_accuracy: number;
  safety_escalation_compliance: number;
  conflict_detection_rate: number;
  revision_freshness_rate: number;
  avg_latency_ms: number;
}

export interface EvaluationResponse {
  timestamp: string;
  total_benchmark_queries: number;
  comparison: Record<string, { bm25: number; hybrid: number; delta: number }>;
  detailed_modes: {
    bm25_baseline: { mode: string; metrics: BenchmarkMetrics; queries: any[] };
    hybrid_rrf_proposed: { mode: string; metrics: BenchmarkMetrics; queries: any[] };
  };
}
