import axios, { AxiosResponse } from 'axios';
import { 
  ApiResponse, 
  SearchRequest, 
  SearchResponse, 
  VectorSearchRequest,
  VectorSearchResponse,
  AnalysisRequest,
  AnalysisReport,
  LoginRequest,
  LoginResponse,
  SystemStats
} from '@/types';

// 创建axios实例
const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8888/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器 - 添加认证token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      (config.headers as any).Authorization = `Bearer ${token}`;
    }

    // 生成并附加 Trace-ID，便于后端/日志串联
    const traceId = (globalThis as any).crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    (config.headers as any)['X-Trace-ID'] = traceId;
    // 记录起始时间
    (config as any).metadata = { start: Date.now(), traceId };

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器 - 统一错误处理
apiClient.interceptors.response.use(
  (response) => {
    // 调试日志：记录请求-响应耗时与Trace-ID
    try {
      const meta = (response.config as any).metadata || {};
      const duration = meta.start ? Date.now() - meta.start : undefined;
      const traceId = response.headers['x-request-id'] || response.headers['x-trace-id'] || meta.traceId;
      // 仅在开发环境输出
      if (process.env.NODE_ENV !== 'production') {
        // eslint-disable-next-line no-console
        console.info('[API]', response.status, response.config.method?.toUpperCase(), response.config.url, { durationMs: duration, traceId });
      }
    } catch {}
    return response;
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
    }
    try {
      const traceId = error.response?.headers?.['x-request-id'] || (error.config as any)?.metadata?.traceId;
      if (process.env.NODE_ENV !== 'production') {
        // eslint-disable-next-line no-console
        console.error('[API ERROR]', error.config?.method?.toUpperCase(), error.config?.url, error.response?.status, { traceId, detail: error.response?.data });
      }
    } catch {}
    return Promise.reject(error);
  }
);

// 通用API请求函数
async function apiRequest<T>(
  method: 'get' | 'post' | 'put' | 'delete',
  url: string,
  data?: any
): Promise<ApiResponse<T>> {
  try {
    const response: AxiosResponse<any> = await apiClient.request({
      method,
      url,
      data,
    });
    // 兼容后端既可能返回包裹结构，也可能直接返回实体对象
    const body = response.data;
    if (body && typeof body === 'object' && 'success' in body) {
      return body as ApiResponse<T>;
    }
    return { success: true, data: body } as ApiResponse<T>;
  } catch (error: any) {
    // eslint-disable-next-line no-console
    console.error(`API请求失败 [${method.toUpperCase()} ${url}]:`, error);
    const traceId = error?.response?.headers?.['x-request-id'] || (error?.config as any)?.metadata?.traceId;
    return {
      success: false,
      error: error.response?.data?.message || error.message || '网络请求失败',
      // @ts-expect-error 附带 traceId 便于 UI/日志串联（可选字段）
      traceId,
    };
  }
}

// 搜索API
export const searchApi = {
  // 全文搜索
  search: async (params: SearchRequest): Promise<ApiResponse<SearchResponse>> => {
    // 将前端请求形状转换为后端需要的形状
    const payload: any = {
      query: params.query,
      page: params.page ?? 1,
      page_size: params.size ?? 20,
      sort_by: params.sort_by ?? 'relevance',
      search_type: 'hybrid',
    };
    const filters: any = {};
    if (params.category) filters.category = params.category;
    if (params.source) filters.source = params.source;
    if (params.start_date) filters.start_date = params.start_date;
    if (params.end_date) filters.end_date = params.end_date;
    if (Object.keys(filters).length > 0) payload.filters = filters;

    const res = await apiRequest<any>('post', '/search', payload);
    if (!res.success || !res.data) return res as ApiResponse<SearchResponse>;

    // 将后端返回形状转换为前端所需 SearchResponse 形状
    const d = res.data;
    const page = payload.page;
    const size = payload.page_size;
    const total = d.total_count ?? 0;
    const documents = (d.results || []).map((item: any) => ({
      id: item.id,
      title: item.title,
      content: item.content,
      source: item.source,
      url: item.url,
      publish_date: item.published_at,
      category: item.category || '',
      tags: item.tags || [],
      score: item.relevance_score,
    }));

    const mapped: SearchResponse = {
      documents,
      total,
      page,
      size,
      total_pages: Math.max(1, Math.ceil(total / Math.max(1, size))),
      took: d.search_time_ms ?? 0,
    };

    return { success: true, data: mapped };
  },

  // 向量搜索
  vectorSearch: async (params: VectorSearchRequest): Promise<ApiResponse<VectorSearchResponse>> => {
    return apiRequest<VectorSearchResponse>('post', '/search/vector', params);
  },

  // 搜索建议
  suggestions: async (query: string): Promise<ApiResponse<string[]>> => {
    return apiRequest<string[]>('get', `/search/suggestions?q=${encodeURIComponent(query)}`);
  },

  // 热门搜索
  trending: async (): Promise<ApiResponse<string[]>> => {
    return apiRequest<string[]>('get', '/search/trending');
  },
};

// 智能分析API
export const analysisApi = {
  // 创建分析任务
  createAnalysis: async (request: AnalysisRequest): Promise<ApiResponse<AnalysisReport>> => {
    return apiRequest<AnalysisReport>('post', '/intelligence/analyze', request);
  },

  // 获取分析报告
  getAnalysis: async (id: string): Promise<ApiResponse<AnalysisReport>> => {
    return apiRequest<AnalysisReport>('get', `/intelligence/reports/${id}`);
  },

  // 获取分析报告列表
  getAnalysisList: async (page = 1, size = 10): Promise<ApiResponse<{
    reports: AnalysisReport[];
    total: number;
    page: number;
    size: number;
  }>> => {
    return apiRequest('get', `/intelligence/reports?page=${page}&size=${size}`);
  },

  // 删除分析报告
  deleteAnalysis: async (id: string): Promise<ApiResponse<void>> => {
    return apiRequest<void>('delete', `/intelligence/reports/${id}`);
  },
};

// 用户认证API
export const authApi = {
  // 登录
  login: async (credentials: LoginRequest): Promise<ApiResponse<LoginResponse>> => {
    const response = await apiRequest<LoginResponse>('post', '/auth/login', credentials);
    
    // 如果登录成功，保存token到localStorage
    if (response.success && response.data?.token) {
      localStorage.setItem('auth_token', response.data.token);
    }
    
    return response;
  },

  // 注册
  register: async (userData: {
    username: string;
    email: string;
    password: string;
  }): Promise<ApiResponse<LoginResponse>> => {
    return apiRequest<LoginResponse>('post', '/auth/register', userData);
  },

  // 登出
  logout: async (): Promise<void> => {
    localStorage.removeItem('auth_token');
  },

  // 获取当前用户信息
  getCurrentUser: async (): Promise<ApiResponse<any>> => {
    return apiRequest('get', '/auth/me');
  },
};

// 系统监控API
export const systemApi = {
  // 获取系统状态
  getStats: async (): Promise<ApiResponse<SystemStats>> => {
    return apiRequest<SystemStats>('get', '/system/stats');
  },

  // 健康检查
  health: async (): Promise<ApiResponse<{ status: string }>> => {
    return apiRequest('get', '/system/health');
  },
};

export default apiClient;
