import React, { useState, useEffect, useCallback } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { Layout } from '@/components/Layout';
import { UnifiedSearchBar } from '@/components/search/UnifiedSearchBar';
import { SearchResults } from '@/components/search/SearchResults';
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

  // 处理搜索（来自统一搜索栏）
  const handleSearch = (searchQuery: string, searchFilters: Partial<SearchRequest>) => {
    setQuery(searchQuery);
    const newFilters = { ...searchFilters, page: 1, size: filters.size || 20 };
    setFilters(newFilters);
    performSearch(searchQuery, newFilters);
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

      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
        {/* 搜索头部区域 - 优化响应式布局 */}
        <div className="bg-white/80 backdrop-blur-sm border-b border-gray-200">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8">
            {/* 主搜索区域 */}
            <div className="py-6 sm:py-8 lg:py-10">
              <div className="text-center mb-6 sm:mb-8">
                <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-gray-900 mb-2">
                  投资情报搜索引擎
                </h1>
                <p className="text-sm sm:text-base text-gray-600 max-w-2xl mx-auto px-4">
                  搜索最新财经资讯、公司公告、行业报告，为您的投资决策提供数据支持
                </p>
              </div>

              {/* 统一搜索栏 */}
              <div className="max-w-4xl mx-auto px-4">
                <UnifiedSearchBar
                  onSearch={handleSearch}
                  initialQuery={query}
                  initialFilters={filters}
                  loading={loading}
                  showStats={true}
                  statsData={systemStats ? {
                    documents_count: systemStats.documents_count,
                    searches_today: systemStats.searches_today,
                    analysis_reports: systemStats.analysis_reports,
                  } : undefined}
                />
              </div>
            </div>
          </div>
        </div>

        {/* 主内容区域 - 响应式单栏布局 */}
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
          {/* 搜索结果 */}
          <div className="max-w-4xl mx-auto px-4">
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

        {/* 底部占位，避免内容被遮挡 */}
        <div className="h-20" />
      </div>
    </Layout>
  );
};

export default HomePage;
