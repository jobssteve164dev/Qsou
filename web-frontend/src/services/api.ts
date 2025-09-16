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
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器 - 统一错误处理
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
    }
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
    const response: AxiosResponse<ApiResponse<T>> = await apiClient.request({
      method,
      url,
      data,
    });
    return response.data;
  } catch (error: any) {
    console.error(`API请求失败 [${method.toUpperCase()} ${url}]:`, error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '网络请求失败',
    };
  }
}

// 搜索API
export const searchApi = {
  // 全文搜索
  search: async (params: SearchRequest): Promise<ApiResponse<SearchResponse>> => {
    return apiRequest<SearchResponse>('post', '/search', params);
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
