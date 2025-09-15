import React, { useState } from 'react';
import { Filter, Calendar, Tag, Globe, SlidersHorizontal, X } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { SearchRequest } from '@/types';
import { dateUtils } from '@/utils';

interface SearchFiltersProps {
  filters: Partial<SearchRequest>;
  onChange: (filters: Partial<SearchRequest>) => void;
  onReset: () => void;
  categories: string[];
  sources: string[];
}

const SearchFilters: React.FC<SearchFiltersProps> = ({
  filters,
  onChange,
  onReset,
  categories = [],
  sources = [],
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [tempFilters, setTempFilters] = useState<Partial<SearchRequest>>(filters);

  // 应用筛选器
  const handleApplyFilters = () => {
    onChange(tempFilters);
    setIsExpanded(false);
  };

  // 重置筛选器
  const handleResetFilters = () => {
    const resetFilters = {
      category: '',
      source: '',
      start_date: '',
      end_date: '',
      sort_by: 'relevance' as const,
    };
    setTempFilters(resetFilters);
    onReset();
    setIsExpanded(false);
  };

  // 更新临时筛选器
  const updateTempFilter = (key: keyof SearchRequest, value: any) => {
    setTempFilters(prev => ({
      ...prev,
      [key]: value,
    }));
  };

  // 获取当前激活的筛选器数量
  const getActiveFiltersCount = () => {
    let count = 0;
    if (filters.category) count++;
    if (filters.source) count++;
    if (filters.start_date) count++;
    if (filters.end_date) count++;
    if (filters.sort_by && filters.sort_by !== 'relevance') count++;
    return count;
  };

  const activeFiltersCount = getActiveFiltersCount();

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      {/* 筛选器头部 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <Filter className="h-5 w-5 text-gray-600" />
          <span className="font-medium text-gray-900">筛选器</span>
          {activeFiltersCount > 0 && (
            <span className="bg-primary-100 text-primary-700 text-xs px-2 py-1 rounded-full">
              {activeFiltersCount} 个激活
            </span>
          )}
        </div>
        
        <div className="flex items-center space-x-2">
          {activeFiltersCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleResetFilters}
              className="text-gray-500 hover:text-gray-700"
            >
              <X className="h-4 w-4 mr-1" />
              清除
            </Button>
          )}
          
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center space-x-1"
          >
            <SlidersHorizontal className="h-4 w-4" />
            <span>{isExpanded ? '收起' : '展开'}</span>
          </Button>
        </div>
      </div>

      {/* 快速筛选器（始终显示） */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
        {/* 分类筛选 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            <Tag className="inline h-4 w-4 mr-1" />
            分类
          </label>
          <select
            value={tempFilters.category || ''}
            onChange={(e) => updateTempFilter('category', e.target.value)}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
          >
            <option value="">全部分类</option>
            {categories.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
        </div>

        {/* 来源筛选 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            <Globe className="inline h-4 w-4 mr-1" />
            来源
          </label>
          <select
            value={tempFilters.source || ''}
            onChange={(e) => updateTempFilter('source', e.target.value)}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
          >
            <option value="">全部来源</option>
            {sources.map((source) => (
              <option key={source} value={source}>
                {source}
              </option>
            ))}
          </select>
        </div>

        {/* 排序方式 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            排序方式
          </label>
          <select
            value={tempFilters.sort_by || 'relevance'}
            onChange={(e) => updateTempFilter('sort_by', e.target.value as 'relevance' | 'date' | 'popularity')}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
          >
            <option value="relevance">相关性</option>
            <option value="date">时间</option>
            <option value="popularity">热度</option>
          </select>
        </div>

        {/* 应用按钮 */}
        <div className="flex items-end">
          <Button
            onClick={handleApplyFilters}
            className="w-full"
            size="sm"
          >
            应用筛选
          </Button>
        </div>
      </div>

      {/* 高级筛选器（可展开/收起） */}
      {isExpanded && (
        <div className="border-t border-gray-200 pt-4 space-y-4">
          {/* 时间范围筛选 */}
          <div>
            <label className="flex items-center text-sm font-medium text-gray-700 mb-2">
              <Calendar className="h-4 w-4 mr-1" />
              时间范围
            </label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">开始日期</label>
                <Input
                  type="date"
                  value={tempFilters.start_date || ''}
                  onChange={(e) => updateTempFilter('start_date', e.target.value)}
                  max={tempFilters.end_date || dateUtils.formatDate(new Date().toISOString())}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">结束日期</label>
                <Input
                  type="date"
                  value={tempFilters.end_date || ''}
                  onChange={(e) => updateTempFilter('end_date', e.target.value)}
                  min={tempFilters.start_date}
                  max={dateUtils.formatDate(new Date().toISOString())}
                />
              </div>
            </div>
          </div>

          {/* 快捷时间选择 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              快捷时间选择
            </label>
            <div className="flex flex-wrap gap-2">
              {[
                { label: '今天', days: 0 },
                { label: '最近3天', days: 3 },
                { label: '最近一周', days: 7 },
                { label: '最近一月', days: 30 },
                { label: '最近三月', days: 90 },
              ].map((period) => (
                <Button
                  key={period.label}
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const endDate = new Date();
                    const startDate = new Date();
                    startDate.setDate(endDate.getDate() - period.days);
                    
                    updateTempFilter('start_date', dateUtils.formatDate(startDate.toISOString()));
                    updateTempFilter('end_date', dateUtils.formatDate(endDate.toISOString()));
                  }}
                  className="text-xs"
                >
                  {period.label}
                </Button>
              ))}
            </div>
          </div>

          {/* 操作按钮 */}
          <div className="flex justify-between pt-4 border-t border-gray-200">
            <Button
              variant="outline"
              onClick={handleResetFilters}
              className="flex items-center space-x-1"
            >
              <X className="h-4 w-4" />
              <span>重置全部</span>
            </Button>
            
            <div className="space-x-2">
              <Button
                variant="outline"
                onClick={() => setIsExpanded(false)}
              >
                取消
              </Button>
              <Button
                onClick={handleApplyFilters}
              >
                应用筛选
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* 当前激活的筛选器标签 */}
      {activeFiltersCount > 0 && (
        <div className="mt-4 pt-3 border-t border-gray-200">
          <div className="flex flex-wrap gap-2">
            {filters.category && (
              <span className="inline-flex items-center px-2 py-1 text-xs bg-primary-100 text-primary-800 rounded-full">
                分类: {filters.category}
                <button
                  onClick={() => onChange({ ...filters, category: '' })}
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
                  onClick={() => onChange({ ...filters, source: '' })}
                  className="ml-1 hover:text-green-600"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            )}
            
            {(filters.start_date || filters.end_date) && (
              <span className="inline-flex items-center px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded-full">
                时间: {filters.start_date && dateUtils.formatDate(filters.start_date)} - {filters.end_date && dateUtils.formatDate(filters.end_date)}
                <button
                  onClick={() => onChange({ ...filters, start_date: '', end_date: '' })}
                  className="ml-1 hover:text-blue-600"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export { SearchFilters };
