import React from 'react';
import Link from 'next/link';
import { Calendar, ExternalLink, Tag, TrendingUp } from 'lucide-react';
import { SearchDocument, SearchResponse } from '@/types';
import { Card, CardContent } from '@/components/ui/Card';
import { Loading } from '@/components/ui/Loading';
import { dateUtils, textUtils, numberUtils } from '@/utils';

interface SearchResultsProps {
  results: SearchResponse | null;
  query: string;
  loading: boolean;
  error: string | null;
  onLoadMore?: () => void;
  hasMore?: boolean;
}

const SearchResults: React.FC<SearchResultsProps> = ({
  results,
  query,
  loading,
  error,
  onLoadMore,
  hasMore = false,
}) => {
  if (loading && !results) {
    return (
      <div className="py-12">
        <Loading size="lg" text="正在搜索相关资讯..." />
      </div>
    );
  }

  if (error) {
    return (
      <Card className="border-red-200 bg-red-50">
        <CardContent className="py-8 text-center">
          <div className="text-red-600 mb-4">
            <ExternalLink className="h-12 w-12 mx-auto mb-2" />
            <h3 className="text-lg font-medium">搜索出现错误</h3>
          </div>
          <p className="text-red-500 text-sm mb-4">{error}</p>
          <button 
            onClick={() => window.location.reload()}
            className="text-primary-600 hover:text-primary-700 font-medium"
          >
            重新尝试
          </button>
        </CardContent>
      </Card>
    );
  }

  if (!results || results.documents.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <div className="text-gray-400 mb-4">
            <TrendingUp className="h-12 w-12 mx-auto mb-2" />
            <h3 className="text-lg font-medium text-gray-600">未找到相关结果</h3>
          </div>
          <p className="text-gray-500 text-sm mb-4">
            尝试使用不同的关键词或扩大搜索范围
          </p>
          <div className="text-sm text-gray-400">
            <p>建议:</p>
            <ul className="mt-2 space-y-1">
              <li>• 检查搜索关键词的拼写</li>
              <li>• 尝试使用更通用的关键词</li>
              <li>• 调整筛选条件</li>
            </ul>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* 搜索统计信息 */}
      <div className="flex items-center justify-between text-sm text-gray-600">
        <div>
          找到 <span className="font-medium text-primary-600">
            {numberUtils.formatLargeNumber(results.total)}
          </span> 条相关结果，
          用时 <span className="font-medium">
            {results.took}ms
          </span>
        </div>
        <div>
          第 {results.page} 页，共 {results.total_pages} 页
        </div>
      </div>

      {/* 搜索结果列表 */}
      <div className="space-y-4">
        {results.documents.map((document, index) => (
          <SearchResultItem
            key={document.id}
            document={document}
            query={query}
            index={index}
          />
        ))}
      </div>

      {/* 加载更多按钮 */}
      {hasMore && (
        <div className="text-center py-6">
          {loading ? (
            <Loading size="md" text="加载中..." />
          ) : (
            <button
              onClick={onLoadMore}
              className="px-6 py-2 text-primary-600 hover:text-primary-700 font-medium border border-primary-600 hover:bg-primary-50 rounded-md transition-colors"
            >
              加载更多结果
            </button>
          )}
        </div>
      )}
    </div>
  );
};

// 单个搜索结果项组件
const SearchResultItem: React.FC<{
  document: SearchDocument;
  query: string;
  index: number;
}> = ({ document, query, index }) => {
  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      'news': 'bg-blue-100 text-blue-800',
      'announcement': 'bg-green-100 text-green-800',
      'report': 'bg-purple-100 text-purple-800',
      'analysis': 'bg-orange-100 text-orange-800',
      'default': 'bg-gray-100 text-gray-800',
    };
    return colors[category.toLowerCase()] || colors.default;
  };

  const getSourceIcon = (source: string) => {
    // 这里可以根据不同来源返回不同的图标
    return <ExternalLink className="h-4 w-4" />;
  };

  return (
    <Card className="hover:shadow-md transition-shadow duration-200">
      <CardContent className="p-6">
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1 min-w-0">
            {/* 标题 */}
            <h3 className="text-lg font-medium text-gray-900 mb-2 leading-6">
              <Link
                href={document.url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-primary-600 transition-colors"
                dangerouslySetInnerHTML={{
                  __html: textUtils.highlight(document.title, query)
                }}
              />
            </h3>

            {/* 内容摘要 */}
            <p 
              className="text-sm text-gray-600 leading-5 mb-3"
              dangerouslySetInnerHTML={{
                __html: textUtils.highlight(
                  textUtils.extractSummary(document.content, 200),
                  query
                )
              }}
            />

            {/* 元信息 */}
            <div className="flex items-center space-x-4 text-xs text-gray-500">
              <div className="flex items-center space-x-1">
                <Calendar className="h-3 w-3" />
                <span>{dateUtils.formatRelative(document.publish_date)}</span>
              </div>
              
              <div className="flex items-center space-x-1">
                {getSourceIcon(document.source)}
                <span>{document.source}</span>
              </div>

              {document.score && (
                <div className="flex items-center space-x-1">
                  <TrendingUp className="h-3 w-3" />
                  <span>相关度: {(document.score * 100).toFixed(0)}%</span>
                </div>
              )}
            </div>
          </div>

          {/* 右侧标签和序号 */}
          <div className="flex-shrink-0 ml-4">
            <div className="flex items-center space-x-2 mb-2">
              <span className="text-xs text-gray-400">#{index + 1}</span>
            </div>
            
            <div className="flex flex-col space-y-1">
              <span className={`px-2 py-1 text-xs font-medium rounded-full ${getCategoryColor(document.category)}`}>
                {document.category}
              </span>
            </div>
          </div>
        </div>

        {/* 标签 */}
        {document.tags && document.tags.length > 0 && (
          <div className="flex items-center flex-wrap gap-1">
            <Tag className="h-3 w-3 text-gray-400" />
            {document.tags.slice(0, 5).map((tag, tagIndex) => (
              <span
                key={tagIndex}
                className="inline-flex items-center px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-700 rounded hover:bg-gray-200 cursor-pointer"
                onClick={() => {
                  // 这里可以添加点击标签搜索的功能
                  console.log('搜索标签:', tag);
                }}
              >
                {tag}
              </span>
            ))}
            {document.tags.length > 5 && (
              <span className="text-xs text-gray-400">
                +{document.tags.length - 5} 个标签
              </span>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export { SearchResults };
