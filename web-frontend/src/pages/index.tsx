import React, { useState, useEffect, useCallback } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { Layout } from '@/components/Layout';
import { SearchBox } from '@/components/search/SearchBox';
import { SearchResults } from '@/components/search/SearchResults';
import { SearchFilters } from '@/components/search/SearchFilters';
import { searchApi, systemApi } from '@/services/api';
import { SearchRequest, SearchResponse, SystemStats } from '@/types';
import { errorUtils, urlUtils } from '@/utils';

const HomePage: React.FC = () => {
  const router = useRouter();
  const [query, setQuery] = useState<string>('');
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [systemStats, setSystemStats] = useState<SystemStats | null>(null);
  
  // 搜索筛选器状态
  const [filters, setFilters] = useState<Partial<SearchRequest>>({
    page: 1,
    size: 20,
    sort_by: 'relevance',
  });

  // 可用的分类和来源（从系统统计或缓存获取）
  const [categories] = useState<string[]>([
    'news', 'announcement', 'report', 'analysis', 'research'
  ]);
  const [sources] = useState<string[]>([
    '新浪财经', '东方财富', '证券时报', '上交所', '深交所', '中证网'
  ]);

  // 从URL同步搜索参数
  useEffect(() => {
    const urlParams = urlUtils.parseQueryString(window.location.search.slice(1));
    
    if (urlParams.q) {
      setQuery(urlParams.q);
      const newFilters = {
        ...filters,
        category: urlParams.category || '',
        source: urlParams.source || '',
        start_date: urlParams.start_date || '',
        end_date: urlParams.end_date || '',
        sort_by: (urlParams.sort_by as any) || 'relevance',
        page: parseInt(urlParams.page) || 1,
      };
      setFilters(newFilters);
      
      // 自动执行搜索
      performSearch(urlParams.q, newFilters);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // 只在组件加载时执行一次

  // 获取系统统计信息
  useEffect(() => {
    const fetchSystemStats = async () => {
      try {
        const response = await systemApi.getStats();
        if (response.success && response.data) {
          setSystemStats(response.data);
        }
      } catch (error) {
        console.error('获取系统统计失败:', error);
      }
    };

    fetchSystemStats();
  }, []);

  // 执行搜索
  const performSearch = useCallback(async (searchQuery: string, searchFilters: Partial<SearchRequest>) => {
    if (!searchQuery.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const searchParams: SearchRequest = {
        query: searchQuery.trim(),
        page: searchFilters.page || 1,
        size: searchFilters.size || 20,
        category: searchFilters.category || undefined,
        source: searchFilters.source || undefined,
        start_date: searchFilters.start_date || undefined,
        end_date: searchFilters.end_date || undefined,
        sort_by: searchFilters.sort_by || 'relevance',
      };

      const response = await searchApi.search(searchParams);
      
      if (response.success && response.data) {
        setResults(response.data);
        
        // 更新URL参数（不触发页面刷新）
        const queryParams = urlUtils.buildQueryString({
          q: searchQuery,
          ...searchFilters,
        });
        
        const newUrl = `${window.location.pathname}?${queryParams}`;
        window.history.replaceState({ path: newUrl }, '', newUrl);
      } else {
        setError(response.error || '搜索请求失败');
      }
    } catch (err) {
      setError(errorUtils.getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  // 处理搜索
  const handleSearch = (searchQuery: string) => {
    setQuery(searchQuery);
    const newFilters = { ...filters, page: 1 }; // 重置到第一页
    setFilters(newFilters);
    performSearch(searchQuery, newFilters);
  };

  // 处理筛选器变化
  const handleFiltersChange = (newFilters: Partial<SearchRequest>) => {
    const updatedFilters = { ...filters, ...newFilters, page: 1 }; // 重置到第一页
    setFilters(updatedFilters);
    
    if (query.trim()) {
      performSearch(query, updatedFilters);
    }
  };

  // 重置筛选器
  const handleFiltersReset = () => {
    const resetFilters = {
      page: 1,
      size: 20,
      sort_by: 'relevance' as const,
    };
    setFilters(resetFilters);
    
    if (query.trim()) {
      performSearch(query, resetFilters);
    }
  };

  // 加载更多结果
  const handleLoadMore = () => {
    if (!results || loading) return;
    
    const nextPage = (filters.page || 1) + 1;
    if (nextPage <= results.total_pages) {
      const newFilters = { ...filters, page: nextPage };
      setFilters(newFilters);
      performSearch(query, newFilters);
    }
  };

  const hasMore = results ? (filters.page || 1) < results.total_pages : false;

  return (
    <Layout>
      <Head>
        <title>QSou - 投资情报搜索引擎</title>
        <meta name="description" content="专业的投资情报搜索引擎，为量化交易提供实时、准确的财经资讯检索服务" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <div className="min-h-screen bg-gray-50">
        {/* 搜索头部区域 */}
        <div className="bg-white border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            {/* 主搜索区域 */}
            <div className="py-8">
              <div className="text-center mb-6">
                <h1 className="text-3xl font-bold text-gray-900 mb-2">
                  投资情报搜索引擎
                </h1>
                <p className="text-gray-600 max-w-2xl mx-auto">
                  搜索最新财经资讯、公司公告、行业报告，为您的投资决策提供数据支持
                </p>
              </div>

              <SearchBox
                onSearch={handleSearch}
                initialQuery={query}
                loading={loading}
              />
            </div>

            {/* 系统统计信息 */}
            {systemStats && (
              <div className="pb-6">
                <div className="flex justify-center space-x-8 text-sm text-gray-600">
                  <div className="text-center">
                    <div className="font-semibold text-lg text-primary-600">
                      {systemStats.documents_count.toLocaleString()}
                    </div>
                    <div>文档总数</div>
                  </div>
                  <div className="text-center">
                    <div className="font-semibold text-lg text-green-600">
                      {systemStats.searches_today.toLocaleString()}
                    </div>
                    <div>今日搜索</div>
                  </div>
                  <div className="text-center">
                    <div className="font-semibold text-lg text-purple-600">
                      {systemStats.analysis_reports.toLocaleString()}
                    </div>
                    <div>分析报告</div>
                  </div>
                  <div className="text-center">
                    <div className={`font-semibold text-lg ${
                      systemStats.system_status === 'healthy' ? 'text-green-600' :
                      systemStats.system_status === 'warning' ? 'text-yellow-600' : 'text-red-600'
                    }`}>
                      {systemStats.system_status === 'healthy' ? '正常' :
                       systemStats.system_status === 'warning' ? '警告' : '异常'}
                    </div>
                    <div>系统状态</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 主内容区域 */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex flex-col lg:flex-row gap-6">
            {/* 左侧 - 筛选器 */}
            <div className="lg:w-80 flex-shrink-0">
              <div className="sticky top-6">
                <SearchFilters
                  filters={filters}
                  onChange={handleFiltersChange}
                  onReset={handleFiltersReset}
                  categories={categories}
                  sources={sources}
                />
              </div>
            </div>

            {/* 右侧 - 搜索结果 */}
            <div className="flex-1">
              <SearchResults
                results={results}
                query={query}
                loading={loading}
                error={error}
                onLoadMore={handleLoadMore}
                hasMore={hasMore}
              />
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default HomePage;
