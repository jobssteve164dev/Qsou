import React, { useState, useEffect, useRef } from 'react';
import { Search, X, Filter, Calendar, Tag, Globe, ChevronDown, TrendingUp, Sparkles } from 'lucide-react';
import { useRouter } from 'next/router';
import { Button } from '@/components/ui/Button';
import { searchApi } from '@/services/api';
import { SearchRequest } from '@/types';
import { debounce, dateUtils } from '@/utils';

interface UnifiedSearchBarProps {
  onSearch: (query: string, filters: Partial<SearchRequest>) => void;
  initialQuery?: string;
  initialFilters?: Partial<SearchRequest>;
  loading?: boolean;
  placeholder?: string;
  showStats?: boolean;
  statsData?: {
    documents_count: number;
    searches_today: number;
    analysis_reports: number;
  };
}

const UnifiedSearchBar: React.FC<UnifiedSearchBarProps> = ({
  onSearch,
  initialQuery = '',
  initialFilters = {},
  loading = false,
  placeholder = '搜索投资资讯、公司公告、行业报告...',
  showStats = false,
  statsData,
}) => {
  const router = useRouter();
  const [query, setQuery] = useState(initialQuery);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [trending, setTrending] = useState<string[]>([]);
  const [showFilters, setShowFilters] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const searchBarRef = useRef<HTMLDivElement>(null);

  // 筛选器状态
  const [filters, setFilters] = useState<Partial<SearchRequest>>({
    category: initialFilters.category || '',
    source: initialFilters.source || '',
    start_date: initialFilters.start_date || '',
    end_date: initialFilters.end_date || '',
    sort_by: initialFilters.sort_by || 'relevance',
    ...initialFilters,
  });

  // 可用的分类和来源
  const categories = ['news', 'announcement', 'report', 'analysis', 'research'];
  const sources = ['新浪财经', '东方财富', '证券时报', '上交所', '深交所', '中证网'];

  // 获取搜索建议的防抖函数
  const debouncedGetSuggestions = debounce(async (searchQuery: string) => {
    if (searchQuery.length < 2) {
      setSuggestions([]);
      return;
    }

    try {
      const response = await searchApi.suggestions(searchQuery);
      if (response.success && response.data) {
        setSuggestions(response.data);
      }
    } catch (error) {
      console.error('获取搜索建议失败:', error);
    }
  }, 300);

  // 获取热门搜索
  useEffect(() => {
    const fetchTrending = async () => {
      try {
        const response = await searchApi.trending();
        if (response.success && response.data) {
          setTrending(response.data);
        }
      } catch (error) {
        console.error('获取热门搜索失败:', error);
      }
    };
    fetchTrending();
  }, []);

  // 处理搜索
  const handleSearch = () => {
    if (query.trim()) {
      onSearch(query.trim(), filters);
      setShowSuggestions(false);
      setShowFilters(false);
      inputRef.current?.blur();
    }
  };

  // 处理输入变化
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setQuery(value);
    
    if (value.trim()) {
      debouncedGetSuggestions(value.trim());
      setShowSuggestions(true);
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  };

  // 处理键盘事件
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSearch();
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
      inputRef.current?.blur();
    }
  };

  // 选择建议项
  const handleSelectSuggestion = (suggestion: string) => {
    setQuery(suggestion);
    onSearch(suggestion, filters);
    setShowSuggestions(false);
  };

  // 清空搜索
  const handleClear = () => {
    setQuery('');
    setSuggestions([]);
    setShowSuggestions(false);
    inputRef.current?.focus();
  };

  // 处理筛选器变化
  const updateFilter = (key: keyof SearchRequest, value: any) => {
    setFilters(prev => ({
      ...prev,
      [key]: value,
    }));
  };

  // 应用筛选并搜索
  const applyFilters = () => {
    handleSearch();
    setShowFilters(false);
  };

  // 重置筛选器
  const resetFilters = () => {
    const resetFilters = {
      category: '',
      source: '',
      start_date: '',
      end_date: '',
      sort_by: 'relevance' as const,
    };
    setFilters(resetFilters);
  };

  // 获取激活的筛选器数量
  const getActiveFiltersCount = () => {
    let count = 0;
    if (filters.category) count++;
    if (filters.source) count++;
    if (filters.start_date) count++;
    if (filters.end_date) count++;
    if (filters.sort_by && filters.sort_by !== 'relevance') count++;
    return count;
  };

  // 处理智能分析点击
  const handleIntelligenceClick = () => {
    const token = localStorage.getItem('auth_token');
    const isDev = process.env.NODE_ENV === 'development';
    
    // 如果是开发环境且没有token，执行静默登录
    if (isDev && !token) {
      performSilentLogin();
    } else if (!token) {
      // 生产环境跳转到登录页
      router.push('/login?returnUrl=/intelligence');
    } else {
      router.push('/intelligence');
    }
  };

  // 静默登录（仅用于开发环境）
  const performSilentLogin = async () => {
    try {
      const { authApi } = await import('@/services/api');
      const response = await authApi.login({
        username: 'admin',
        password: 'admin123',
      });
      
      if (response.success && response.data?.token) {
        router.push('/intelligence');
      }
    } catch (error) {
      console.error('静默登录失败，跳转到登录页面');
      router.push('/login?returnUrl=/intelligence');
    }
  };

  // 处理点击外部关闭
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (searchBarRef.current && !searchBarRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
        setShowFilters(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const activeFiltersCount = getActiveFiltersCount();

  return (
    <div ref={searchBarRef} className="w-full">
      {/* 主搜索栏 */}
      <div className="relative">
        <div className="bg-white rounded-xl shadow-lg overflow-visible p-2">
          <div className="flex flex-wrap sm:flex-nowrap items-center gap-2">
            {/* 搜索输入区域 */}
            <div className="flex-1 min-w-0 flex items-center">
              <Search className="h-5 w-5 text-gray-400 mr-3 flex-shrink-0" />
              
              <div className="flex-1 relative">
                <input
                  ref={inputRef}
                  type="text"
                  value={query}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyDown}
                  onFocus={() => {
                    if (query.trim() && suggestions.length > 0) {
                      setShowSuggestions(true);
                    } else if (!query.trim() && trending.length > 0) {
                      setShowSuggestions(true);
                    }
                  }}
                  placeholder={placeholder}
                  className="w-full h-11 border-2 border-gray-200 rounded-lg outline-none focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(59,130,246,0.15)] text-base px-3 transition-all"
                />
              </div>
              
              {query && (
                <button
                  type="button"
                  onClick={handleClear}
                  className="p-2 hover:bg-gray-100 rounded-lg ml-2 flex-shrink-0"
                >
                  <X className="h-4 w-4 text-gray-400" />
                </button>
              )}
            </div>

            {/* 快速筛选器（大屏幕显示） - 移除内置筛选，通过筛选按钮统一管理 */}

            {/* 操作按钮 */}
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setShowFilters(!showFilters)}
                className="relative px-3 h-11 rounded-lg hover:bg-gray-100"
                title="筛选"
              >
                <Filter className="h-4 w-4" />
                {activeFiltersCount > 0 && (
                  <span className="absolute -top-1 -right-1 h-4 w-4 bg-primary-600 text-white text-xs rounded-full flex items-center justify-center">
                    {activeFiltersCount}
                  </span>
                )}
                <span className="ml-1.5 hidden lg:inline text-sm">筛选</span>
              </Button>

              <Button
                type="button"
                variant="ghost"
                onClick={handleIntelligenceClick}
                className="px-3 h-11 rounded-lg hover:bg-gray-100"
                title="智能分析"
              >
                <Sparkles className="h-4 w-4" />
                <span className="ml-1.5 hidden lg:inline text-sm">智能分析</span>
              </Button>

              <Button
                type="button"
                onClick={handleSearch}
                disabled={!query.trim() || loading}
                loading={loading}
                className="px-4 h-11 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-300"
              >
                搜索
              </Button>
            </div>
          </div>

        </div>


        {/* 搜索建议下拉菜单 */}
        {showSuggestions && (
          <div className="absolute top-full mt-2 w-full bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-80 overflow-y-auto">
            {/* 搜索建议 */}
            {suggestions.length > 0 && (
              <div className="py-2">
                <div className="px-4 py-2 text-xs font-medium text-gray-500 uppercase tracking-wide">
                  搜索建议
                </div>
                {suggestions.map((suggestion, index) => (
                  <button
                    key={index}
                    onClick={() => handleSelectSuggestion(suggestion)}
                    className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-center space-x-3"
                  >
                    <Search className="h-4 w-4 text-gray-400 flex-shrink-0" />
                    <span className="text-sm text-gray-700">{suggestion}</span>
                  </button>
                ))}
              </div>
            )}

            {/* 热门搜索 */}
            {!query.trim() && trending.length > 0 && (
              <div className="py-2">
                <div className="px-4 py-2 text-xs font-medium text-gray-500 uppercase tracking-wide flex items-center">
                  <TrendingUp className="h-3 w-3 mr-1" />
                  热门搜索
                </div>
                {trending.map((trend, index) => (
                  <button
                    key={index}
                    onClick={() => handleSelectSuggestion(trend)}
                    className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-center space-x-3"
                  >
                    <span className="text-xs font-medium text-red-500 w-4">
                      {index + 1}
                    </span>
                    <span className="text-sm text-gray-700">{trend}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 高级筛选面板 */}
        {showFilters && (
          <div className="absolute top-full mt-2 w-full max-w-2xl bg-white border border-gray-200 rounded-lg shadow-xl z-50 p-4">
            <div className="space-y-4">
              {/* 基础筛选 */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    <Tag className="inline h-3 w-3 mr-1" />
                    分类
                  </label>
                  <select
                    value={filters.category || ''}
                    onChange={(e) => updateFilter('category', e.target.value)}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  >
                    <option value="">全部分类</option>
                    {categories.map((cat) => (
                      <option key={cat} value={cat}>{cat}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    <Globe className="inline h-3 w-3 mr-1" />
                    来源
                  </label>
                  <select
                    value={filters.source || ''}
                    onChange={(e) => updateFilter('source', e.target.value)}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  >
                    <option value="">全部来源</option>
                    {sources.map((src) => (
                      <option key={src} value={src}>{src}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    排序方式
                  </label>
                  <select
                    value={filters.sort_by || 'relevance'}
                    onChange={(e) => updateFilter('sort_by', e.target.value as any)}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  >
                    <option value="relevance">相关性</option>
                    <option value="date">时间</option>
                    <option value="popularity">热度</option>
                  </select>
                </div>
              </div>

              {/* 高级选项切换 */}
              <button
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center text-sm text-primary-600 hover:text-primary-700"
              >
                <ChevronDown className={`h-4 w-4 mr-1 transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
                高级筛选
              </button>

              {/* 高级筛选选项 */}
              {showAdvanced && (
                <div className="space-y-4 pt-4 border-t border-gray-200">
                  {/* 时间范围 */}
                  <div>
                    <label className="flex items-center text-sm font-medium text-gray-700 mb-2">
                      <Calendar className="h-3 w-3 mr-1" />
                      时间范围
                    </label>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">开始日期</label>
                        <input
                          type="date"
                          value={filters.start_date || ''}
                          onChange={(e) => updateFilter('start_date', e.target.value)}
                          max={filters.end_date || dateUtils.formatDate(new Date().toISOString())}
                          className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">结束日期</label>
                        <input
                          type="date"
                          value={filters.end_date || ''}
                          onChange={(e) => updateFilter('end_date', e.target.value)}
                          min={filters.start_date}
                          max={dateUtils.formatDate(new Date().toISOString())}
                          className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm"
                        />
                      </div>
                    </div>
                  </div>

                  {/* 快捷时间选择 */}
                  <div className="flex flex-wrap gap-2">
                    {[
                      { label: '今天', days: 0 },
                      { label: '最近3天', days: 3 },
                      { label: '最近一周', days: 7 },
                      { label: '最近一月', days: 30 },
                    ].map((period) => (
                      <Button
                        key={period.label}
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          const endDate = new Date();
                          const startDate = new Date();
                          startDate.setDate(endDate.getDate() - period.days);
                          
                          updateFilter('start_date', dateUtils.formatDate(startDate.toISOString()));
                          updateFilter('end_date', dateUtils.formatDate(endDate.toISOString()));
                        }}
                        className="text-xs"
                      >
                        {period.label}
                      </Button>
                    ))}
                  </div>
                </div>
              )}

              {/* 操作按钮 */}
              <div className="flex justify-between pt-4 border-t border-gray-200">
                <Button
                  variant="outline"
                  onClick={() => {
                    resetFilters();
                    setShowFilters(false);
                  }}
                >
                  重置
                </Button>
                
                <div className="space-x-2">
                  <Button
                    variant="outline"
                    onClick={() => setShowFilters(false)}
                  >
                    取消
                  </Button>
                  <Button onClick={applyFilters}>
                    应用筛选
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 统计信息（可选） */}
      {showStats && statsData && (
        <div className="mt-4 flex flex-wrap justify-center gap-4 text-sm text-gray-600">
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-primary-600">
              {statsData.documents_count.toLocaleString()}
            </span>
            <span>文档总数</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-green-600">
              {statsData.searches_today.toLocaleString()}
            </span>
            <span>今日搜索</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-purple-600">
              {statsData.analysis_reports.toLocaleString()}
            </span>
            <span>分析报告</span>
          </div>
        </div>
      )}

      {/* 当前筛选标签 */}
      {activeFiltersCount > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {filters.category && (
            <span className="inline-flex items-center px-2 py-1 text-xs bg-primary-100 text-primary-800 rounded-full">
              分类: {filters.category}
              <button
                onClick={() => updateFilter('category', '')}
                className="ml-1 hover:text-primary-600"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          )}
          
          {filters.source && (
            <span className="inline-flex items-center px-2 py-1 text-xs bg-green-100 text-green-800 rounded-full">
              来源: {filters.source}
              <button
                onClick={() => updateFilter('source', '')}
                className="ml-1 hover:text-green-600"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          )}
          
          {(filters.start_date || filters.end_date) && (
            <span className="inline-flex items-center px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded-full">
              时间: {filters.start_date} - {filters.end_date}
              <button
                onClick={() => {
                  updateFilter('start_date', '');
                  updateFilter('end_date', '');
                }}
                className="ml-1 hover:text-blue-600"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          )}
        </div>
      )}
    </div>
  );
};

export { UnifiedSearchBar };
