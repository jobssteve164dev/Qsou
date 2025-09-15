import { clsx, type ClassValue } from "clsx";
import { format, formatDistanceToNow, parseISO } from "date-fns";
import { zhCN } from "date-fns/locale";

// 类名合并工具
export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

// 日期格式化工具
export const dateUtils = {
  // 格式化为相对时间
  formatRelative: (dateString: string): string => {
    try {
      const date = parseISO(dateString);
      return formatDistanceToNow(date, { 
        addSuffix: true,
        locale: zhCN 
      });
    } catch {
      return '未知时间';
    }
  },

  // 格式化为标准日期
  formatDate: (dateString: string, formatStr: string = 'yyyy-MM-dd'): string => {
    try {
      const date = parseISO(dateString);
      return format(date, formatStr, { locale: zhCN });
    } catch {
      return '无效日期';
    }
  },

  // 格式化为日期时间
  formatDateTime: (dateString: string): string => {
    return dateUtils.formatDate(dateString, 'yyyy-MM-dd HH:mm:ss');
  },
};

// 文本处理工具
export const textUtils = {
  // 截断文本
  truncate: (text: string, maxLength: number = 100): string => {
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength) + '...';
  },

  // 高亮搜索关键词
  highlight: (text: string, query: string): string => {
    if (!query || !text) return text;
    
    const regex = new RegExp(`(${query})`, 'gi');
    return text.replace(regex, '<mark class="bg-yellow-200 px-1 rounded">$1</mark>');
  },

  // 提取摘要
  extractSummary: (content: string, maxLength: number = 200): string => {
    const sentences = content.split(/[。！？.!?]/);
    let summary = '';
    
    for (const sentence of sentences) {
      if (summary.length + sentence.length <= maxLength) {
        summary += sentence + '。';
      } else {
        break;
      }
    }
    
    return summary || textUtils.truncate(content, maxLength);
  },
};

// 数字格式化工具
export const numberUtils = {
  // 格式化大数字
  formatLargeNumber: (num: number): string => {
    if (num < 1000) return num.toString();
    if (num < 10000) return (num / 1000).toFixed(1) + 'K';
    if (num < 100000000) return (num / 10000).toFixed(1) + '万';
    return (num / 100000000).toFixed(1) + '亿';
  },

  // 格式化百分比
  formatPercentage: (value: number, decimals: number = 1): string => {
    return `${(value * 100).toFixed(decimals)}%`;
  },
};

// URL工具
export const urlUtils = {
  // 构建查询字符串
  buildQueryString: (params: Record<string, any>): string => {
    const searchParams = new URLSearchParams();
    
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, String(value));
      }
    });
    
    return searchParams.toString();
  },

  // 解析查询字符串
  parseQueryString: (queryString: string): Record<string, string> => {
    const params = new URLSearchParams(queryString);
    const result: Record<string, string> = {};
    
    params.forEach((value, key) => {
      result[key] = value;
    });
    
    return result;
  },
};

// 本地存储工具
export const storageUtils = {
  // 获取存储值
  get: <T>(key: string, defaultValue?: T): T | null => {
    if (typeof window === 'undefined') return defaultValue || null;
    
    try {
      const item = localStorage.getItem(key);
      return item ? JSON.parse(item) : defaultValue || null;
    } catch {
      return defaultValue || null;
    }
  },

  // 设置存储值
  set: (key: string, value: any): void => {
    if (typeof window === 'undefined') return;
    
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      console.error('LocalStorage set failed:', error);
    }
  },

  // 删除存储值
  remove: (key: string): void => {
    if (typeof window === 'undefined') return;
    localStorage.removeItem(key);
  },
};

// 防抖函数
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timeoutId: NodeJS.Timeout;
  
  return (...args: Parameters<T>) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func(...args), delay);
  };
}

// 节流函数
export function throttle<T extends (...args: any[]) => any>(
  func: T,
  delay: number
): (...args: Parameters<T>) => void {
  let lastCall = 0;
  
  return (...args: Parameters<T>) => {
    const now = Date.now();
    
    if (now - lastCall >= delay) {
      lastCall = now;
      func(...args);
    }
  };
}

// 错误处理工具
export const errorUtils = {
  // 提取错误信息
  getErrorMessage: (error: any): string => {
    if (typeof error === 'string') return error;
    if (error?.message) return error.message;
    if (error?.error) return error.error;
    return '发生了未知错误';
  },

  // 判断是否为网络错误
  isNetworkError: (error: any): boolean => {
    return error?.code === 'NETWORK_ERROR' || 
           error?.message?.includes('Network Error') ||
           !navigator.onLine;
  },
};
