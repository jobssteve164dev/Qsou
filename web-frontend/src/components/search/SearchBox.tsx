import React, { useState, useEffect, useRef } from 'react';
import { Search, X } from 'lucide-react';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { searchApi } from '@/services/api';
import { debounce } from '@/utils';

interface SearchBoxProps {
  onSearch: (query: string) => void;
  initialQuery?: string;
  loading?: boolean;
  placeholder?: string;
}

const SearchBox: React.FC<SearchBoxProps> = ({
  onSearch,
  initialQuery = '',
  loading = false,
  placeholder = '搜索投资资讯、公司公告、行业报告...',
}) => {
  const [query, setQuery] = useState(initialQuery);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [trending, setTrending] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

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

  // 处理搜索
  const handleSearch = () => {
    if (query.trim()) {
      onSearch(query.trim());
      setShowSuggestions(false);
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
    onSearch(suggestion);
    setShowSuggestions(false);
  };

  // 清空搜索
  const handleClear = () => {
    setQuery('');
    setSuggestions([]);
    setShowSuggestions(false);
    inputRef.current?.focus();
  };

  // 处理输入框聚焦
  const handleFocus = () => {
    if (query.trim() && suggestions.length > 0) {
      setShowSuggestions(true);
    } else if (!query.trim() && trending.length > 0) {
      setShowSuggestions(true);
    }
  };

  // 处理点击外部关闭建议
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (inputRef.current && !inputRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // 初始化热门搜索
  useEffect(() => {
    fetchTrending();
  }, []);

  return (
    <div className="relative w-full max-w-2xl mx-auto">
      {/* 搜索输入框 */}
      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <Search className="h-5 w-5 text-gray-400" />
        </div>
        
        <Input
          ref={inputRef}
          type="text"
          value={query}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={handleFocus}
          placeholder={placeholder}
          className="pl-10 pr-20 h-12 text-lg"
        />
        
        <div className="absolute inset-y-0 right-0 flex items-center">
          {query && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleClear}
              className="mr-1 h-8 w-8 p-0 hover:bg-gray-100"
            >
              <X className="h-4 w-4 text-gray-400" />
            </Button>
          )}
          
          <Button
            type="button"
            onClick={handleSearch}
            disabled={!query.trim() || loading}
            loading={loading}
            className="mr-2 px-4"
          >
            搜索
          </Button>
        </div>
      </div>

      {/* 搜索建议下拉菜单 */}
      {showSuggestions && (
        <div className="absolute top-full mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-80 overflow-y-auto">
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
            <div className="py-2 border-t border-gray-100">
              <div className="px-4 py-2 text-xs font-medium text-gray-500 uppercase tracking-wide">
                热门搜索
              </div>
              {trending.map((trend, index) => (
                <button
                  key={index}
                  onClick={() => handleSelectSuggestion(trend)}
                  className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-center space-x-3"
                >
                  <div className="h-4 w-4 flex items-center justify-center flex-shrink-0">
                    <span className="text-xs font-medium text-red-500">
                      {index + 1}
                    </span>
                  </div>
                  <span className="text-sm text-gray-700">{trend}</span>
                </button>
              ))}
            </div>
          )}

          {/* 空状态 */}
          {showSuggestions && suggestions.length === 0 && query.trim() && (
            <div className="py-8 text-center text-gray-500">
              <Search className="h-8 w-8 mx-auto mb-2 text-gray-300" />
              <p className="text-sm">暂无相关搜索建议</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export { SearchBox };
