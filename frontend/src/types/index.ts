export interface User {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
}

export interface Repository {
  id: string;
  user_id: string;
  name: string;
  source_type: string;
  source_url?: string;
  default_branch: string;
  commit_sha?: string;
  primary_language?: string;
  status: 'pending' | 'cloning' | 'indexing' | 'ready' | 'failed';
  total_files: number;
  total_chunks: number;
  error_message?: string;
  created_at: string;
  updated_at: string;
  last_indexed_at?: string;
}

export interface RepositoryStatus {
  id: string;
  status: string;
  progress: number;
  current_stage: string;
  error_message?: string;
  total_files: number;
  total_chunks: number;
  last_indexed_at?: string;
}

export interface RepositoryFileItem {
  id: string;
  file_path: string;
  language?: string;
  file_size: number;
  indexed_at: string;
}

export interface FileContent {
  file_path: string;
  language?: string;
  content: string;
  total_lines: number;
  file_size: number;
}

export interface CitationItem {
  file_path: string;
  start_line: number;
  end_line: number;
  symbol_name?: string;
  snippet?: string;
  score?: number;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  citations: CitationItem[];
  model?: string;
  token_usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens?: number;
  };
  created_at: string;
}

export interface ChatSession {
  id: string;
  user_id: string;
  repository_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface SuggestedFixItem {
  file_path: string;
  description: string;
  unified_diff: string;
  validation_steps: string[];
  confidence: 'High' | 'Medium' | 'Low';
}

export interface DebugAnalyzeResponse {
  error_summary: string;
  potential_root_cause: string;
  evidence_from_codebase: string;
  affected_files: string[];
  citations: CitationItem[];
  suggested_fixes: SuggestedFixItem[];
  tests_to_validate: string[];
  confidence_limitations: string;
}

export interface ReviewFinding {
  title: string;
  severity: 'Critical' | 'High' | 'Medium' | 'Low' | 'Informational';
  category: string;
  description: string;
  evidence: string;
  file_path: string;
  start_line: number;
  end_line: number;
  suggested_improvement: string;
  confidence: string;
}

export interface CodeReviewResponse {
  repository_id: string;
  target: string;
  total_findings: number;
  findings: ReviewFinding[];
  summary: string;
}

export interface SearchResultItem {
  chunk_id: string;
  file_path: string;
  start_line: number;
  end_line: number;
  symbol_name?: string;
  symbol_type?: string;
  language?: string;
  content: string;
  score: number;
  retrieval_method: string;
}

export interface AgentWorkflowResponse {
  repository_id: string;
  intent: string;
  detected_language?: string;
  extracted_symbols: string[];
  extracted_files: string[];
  direct_answer: string;
  explanation?: string;
  execution_flow?: string;
  citations: CitationItem[];
  execution_log: string[];
  session_id?: string;
}

export interface DiffChangeResponse {
  id: string;
  repository_id: string;
  user_id: string;
  status: string;
  patch_content: string;
  created_at: string;
  approved_at?: string;
  applied_at?: string;
}
