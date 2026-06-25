export interface GraphNode {
  id: string;
  label: string;
  node_type: 'REPOSITORY' | 'FILE' | 'CLASS' | 'FUNCTION' | 'SECURITY_FINDING' | 'IMPORT' | 'CALL';
  file_path?: string;
  start_line?: number;
  end_line?: number;
  security_score?: number;
  dead_code: boolean;
  architecture_smell: boolean;
  metadata?: any;
}

export interface GraphEdge {
  source: string;
  target: string;
  relationship: string;
}

export interface RepositoryGraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface SecurityFinding {
  id: string;
  rule_id: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
  description: string;
  line_number: number;
}

export interface NodeDetails {
  id: string;
  type: string;
  name: string;
  file_path?: string;
  symbol_name?: string;
  start_line?: number;
  end_line?: number;
  security_findings: SecurityFinding[];
  dead_code: boolean;
  architecture_smell: boolean;
  metadata?: any;
}

export interface Repository {
  id: string;
  name: string;
  root_path: string;
  language: string;
  indexed_at: string;
  hash: string;
}

export interface RetrievedChunk {
  score: number;
  file_path: string;
  symbol_name?: string;
  start_line?: number;
  end_line?: number;
  chunk_type: string;
}

export interface ChatMessage {
  message_id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  citations?: RetrievedChunk[];
  metadata?: {
    provider?: string;
    model?: string;
    latency_ms?: number;
    prompt_version?: string;
  };
}

export interface ChatSession {
  session_id: string;
  repository_id: string;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
}
