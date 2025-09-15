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
  id: string;
  username: string;
  email: string;
  role: 'user' | 'admin';
  created_at: string;
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
    elasticsearch: boolean;
    qdrant: boolean;
    crawler: boolean;
    processor: boolean;
  };
}
