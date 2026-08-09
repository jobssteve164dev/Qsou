// API响应通用类型
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  message?: string;
  error?: string;
}

// 搜索相关类型
export interface SearchDocument {
  id: string;
  title: string;
  content: string;
  source: string;
  url: string;
  publish_date: string;
  category: string;
  tags: string[];
  score?: number;
  source_id?: string;
  raw_object_id?: string;
}

export interface SearchRequest {
  query: string;
  page?: number;
  size?: number;
  category?: string;
  source?: string;
  start_date?: string;
  end_date?: string;
  sort_by?: 'relevance' | 'date' | 'popularity';
}

export interface SearchResponse {
  documents: SearchDocument[];
  total: number;
  page: number;
  size: number;
  total_pages: number;
  took: number;
}

// 向量搜索类型
export interface VectorSearchRequest {
  query: string;
  limit?: number;
  score_threshold?: number;
  category?: string;
}

export interface VectorSearchResponse {
  documents: SearchDocument[];
  took: number;
}

// 智能分析相关类型
export interface AnalysisRequest {
  topic: string;
  keywords: string[];
  time_range?: {
    start: string;
    end: string;
  };
  sources?: string[];
}

export interface AnalysisReport {
  id: string;
  topic: string;
  summary: string;
  key_points: string[];
  sentiment: {
    positive: number;
    neutral: number;
    negative: number;
  };
  trends: {
    date: string;
    value: number;
  }[];
  related_documents: SearchDocument[];
  created_at: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
}

// 用户认证类型
export interface User {
  username: string;
  role: 'user' | 'admin';
  id?: string;
  email?: string;
  created_at?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  user: User;
}

// 监控和统计类型
export interface SystemStats {
  documents_count: number;
  searches_today: number;
  analysis_reports: number;
  system_status: 'healthy' | 'warning' | 'error';
  services: {
    data_assets?: boolean;
    elasticsearch: boolean;
    qdrant: boolean;
    crawler: boolean;
    processor: boolean;
  };
  service_states?: {
    data_assets?: 'healthy' | 'disabled' | 'idle' | 'unavailable';
    elasticsearch?: 'healthy' | 'disabled' | 'idle' | 'unavailable';
    qdrant?: 'healthy' | 'disabled' | 'idle' | 'unavailable';
    crawler?: 'healthy' | 'disabled' | 'idle' | 'unavailable';
    processor?: 'healthy' | 'disabled' | 'idle' | 'unavailable';
  };
  service_messages?: {
    elasticsearch?: string;
    qdrant?: string;
    crawler?: string;
    processor?: string;
  };
}

export interface DataAssetStatus {
  status: 'healthy' | 'unhealthy';
  registered_sources: number;
  active_sources?: number;
  raw_objects: number;
  document_versions: number;
  active_documents: number;
  processing: Record<string, number>;
  network?: Record<string, number>;
  collector: {
    state: 'starting' | 'not_started' | 'running' | 'idle' | 'degraded' | 'stopping' | 'disabled' | 'unknown';
    source_ids?: string[];
    active_source_id?: string | null;
    poll_seconds?: number;
    last_started_at?: string;
    last_finished_at?: string;
    next_run_at?: string;
    results?: Record<string, number>;
  };
}

export interface DataSourceStatus {
  source_id: string;
  source_name: string;
  authority_tier: 'primary' | 'secondary' | 'discovery';
  document_types: string[];
  schedule?: string;
  rights_status?: string;
  health_state: string;
  adapter_id: string;
  adapter_version: string;
  adapter_kind: string;
  enabled: boolean;
  collection_state: 'not_started' | 'queued' | 'running' | 'healthy' | 'degraded' | 'failed' | 'cancelled' | 'stale' | 'authorization_required' | 'disabled';
  raw_count: number;
  document_versions: number;
  active_documents: number;
  last_fetched_at?: string | null;
  last_document_at?: string | null;
  cursor?: {
    last_successful_at?: string;
    latest_published_at?: string | null;
  } | null;
  active_request?: {
    request_id: string;
    state: 'queued' | 'running';
    requested_at: string;
    claimed_at?: string | null;
  } | null;
  last_run?: {
    run_id: string;
    state: string;
    started_at: string;
    finished_at?: string | null;
    entrypoints_total: number;
    entrypoints_succeeded: number;
    detail_discovered: number;
    detail_fetched: number;
    documents_emitted: number;
    metrics?: {
      documents_indexed?: number;
      new_document_versions?: number;
    } | null;
    evidence_archived: number;
    failures: number;
  } | null;
}

export interface EvidenceRecord {
  raw_object_id: string;
  source_id: string;
  url: string;
  content_type: string;
  first_fetched_at: string;
  last_fetched_at: string;
  fetch_count: number;
}
