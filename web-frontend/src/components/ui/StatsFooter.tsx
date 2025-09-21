import React from 'react';

interface StatsFooterProps {
  statsData?: {
    documents_count: number;
    searches_today: number;
    analysis_reports: number;
  };
  loading?: boolean;
}

const StatsFooter: React.FC<StatsFooterProps> = ({ statsData, loading = false }) => {
  if (loading) {
    return (
      <div className="bg-gray-50 border-t border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-center">
            <div className="animate-pulse flex space-x-8">
              <div className="h-4 bg-gray-300 rounded w-20"></div>
              <div className="h-4 bg-gray-300 rounded w-20"></div>
              <div className="h-4 bg-gray-300 rounded w-20"></div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!statsData) {
    return null;
  }

  return (
    <div className="bg-gray-50 border-t border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex flex-wrap justify-center items-center gap-6 text-sm">
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-primary-600">
              {statsData.documents_count.toLocaleString()}
            </span>
            <span className="text-gray-600">文档总数</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-green-600">
              {statsData.searches_today.toLocaleString()}
            </span>
            <span className="text-gray-600">今日搜索</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-purple-600">
              {statsData.analysis_reports.toLocaleString()}
            </span>
            <span className="text-gray-600">分析报告</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export { StatsFooter };
