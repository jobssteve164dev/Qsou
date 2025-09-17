import React from 'react';
import { 
  TrendingUp, 
  BarChart3, 
  Globe, 
  FileText, 
  Building2, 
  Lightbulb,
  ArrowRight,
  Star,
  Target
} from 'lucide-react';
import { SystemStats } from '@/types';
import { numberUtils } from '@/utils';

interface WelcomeScreenProps {
  systemStats?: SystemStats;
  onSearchSuggestion?: (query: string) => void;
}

const WelcomeScreen: React.FC<WelcomeScreenProps> = ({ 
  systemStats, 
  onSearchSuggestion 
}) => {
  // 热门搜索建议
  const popularSearches = [
    { query: '人工智能', category: '科技', icon: Lightbulb },
    { query: '新能源', category: '能源', icon: Globe },
    { query: '生物医药', category: '医疗', icon: Building2 },
    { query: '消费电子', category: '科技', icon: Target },
  ];

  // 功能特色
  const features = [
    {
      icon: TrendingUp,
      title: '智能搜索',
      description: '基于Elasticsearch的全文搜索，支持中英文混合查询'
    },
    {
      icon: TrendingUp,
      title: '实时数据',
      description: '实时更新的财经资讯、公司公告和行业报告'
    },
    {
      icon: BarChart3,
      title: '智能分析',
      description: 'AI驱动的投资情报分析和趋势预测'
    },
    {
      icon: FileText,
      title: '多源整合',
      description: '整合多个权威数据源，提供全面的投资信息'
    }
  ];

  const handleSearchSuggestion = (query: string) => {
    if (onSearchSuggestion) {
      onSearchSuggestion(query);
    }
  };

  return (
    <div className="space-y-6">

      {/* 系统统计信息 */}
      {systemStats && (
        <div className="bg-gradient-to-r from-primary-50 to-blue-50 rounded-xl p-6 border border-primary-100">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center">
              <div className="text-2xl font-bold text-primary-600 mb-1">
                {numberUtils.formatLargeNumber(systemStats.documents_count)}
              </div>
              <div className="text-sm text-gray-600">文档总数</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-primary-600 mb-1">
                {numberUtils.formatLargeNumber(systemStats.searches_today)}
              </div>
              <div className="text-sm text-gray-600">今日搜索</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-primary-600 mb-1">
                {numberUtils.formatLargeNumber(systemStats.analysis_reports)}
              </div>
              <div className="text-sm text-gray-600">分析报告</div>
            </div>
          </div>
        </div>
      )}

      {/* 热门搜索建议 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex items-center mb-4">
          <TrendingUp className="h-5 w-5 text-primary-600 mr-2" />
          <h3 className="text-lg font-semibold text-gray-900">热门搜索</h3>
        </div>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {popularSearches.map((item, index) => {
            const IconComponent = item.icon;
            return (
              <button
                key={index}
                onClick={() => handleSearchSuggestion(item.query)}
                className="flex items-center p-3 rounded-lg border border-gray-200 hover:border-primary-300 hover:bg-primary-50 transition-all duration-200 group"
              >
                <div className="flex-shrink-0 w-8 h-8 bg-gray-100 rounded-lg flex items-center justify-center mr-3 group-hover:bg-primary-100 transition-colors">
                  <IconComponent className="h-4 w-4 text-gray-600 group-hover:text-primary-600" />
                </div>
                <div className="flex-1 text-left">
                  <div className="font-medium text-gray-900 group-hover:text-primary-700">
                    {item.query}
                  </div>
                  <div className="text-sm text-gray-500">{item.category}</div>
                </div>
                <ArrowRight className="h-4 w-4 text-gray-400 group-hover:text-primary-500 transition-colors" />
              </button>
            );
          })}
        </div>
      </div>

      {/* 功能特色 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex items-center mb-6">
          <Star className="h-5 w-5 text-primary-600 mr-2" />
          <h3 className="text-lg font-semibold text-gray-900">平台特色</h3>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {features.map((feature, index) => {
            const IconComponent = feature.icon;
            return (
              <div key={index} className="flex items-start space-x-4">
                <div className="flex-shrink-0 w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center">
                  <IconComponent className="h-5 w-5 text-primary-600" />
                </div>
                <div>
                  <h4 className="font-medium text-gray-900 mb-1">{feature.title}</h4>
                  <p className="text-sm text-gray-600 leading-relaxed">
                    {feature.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 使用提示 */}
      <div className="bg-blue-50 rounded-xl p-6 border border-blue-200">
        <div className="flex items-start space-x-3">
          <div className="flex-shrink-0 w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center mt-0.5">
            <Lightbulb className="h-3 w-3 text-blue-600" />
          </div>
          <div>
            <h4 className="font-medium text-blue-900 mb-2">使用提示</h4>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>• 支持中英文混合搜索，如"AI人工智能"、"新能源股票"</li>
              <li>• 可以使用引号进行精确匹配，如"特斯拉财报"</li>
              <li>• 支持时间范围筛选，获取特定时期的信息</li>
              <li>• 点击"智能分析"获取AI驱动的投资洞察</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export { WelcomeScreen };
