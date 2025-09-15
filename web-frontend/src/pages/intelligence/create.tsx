import React, { useState } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { ArrowLeft, Plus, X, Calendar, Tag, Globe } from 'lucide-react';
import { Layout } from '@/components/Layout';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { analysisApi } from '@/services/api';
import { AnalysisRequest } from '@/types';
import { dateUtils, errorUtils } from '@/utils';

const CreateAnalysisPage: React.FC = () => {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // 表单数据
  const [formData, setFormData] = useState<{
    topic: string;
    keywords: string[];
    time_range: {
      start: string;
      end: string;
    };
    sources: string[];
  }>({
    topic: '',
    keywords: [],
    time_range: {
      start: '',
      end: dateUtils.formatDate(new Date().toISOString()),
    },
    sources: [],
  });

  // 临时输入状态
  const [keywordInput, setKeywordInput] = useState('');
  const [sourceInput, setSourceInput] = useState('');

  // 预设的数据源
  const availableSources = [
    '新浪财经', '东方财富', '证券时报', '中证网', 
    '上交所', '深交所', '财新网', '第一财经'
  ];

  // 更新表单字段
  const updateFormData = (field: string, value: any) => {
    setFormData(prev => ({
      ...prev,
      [field]: value,
    }));
  };

  // 添加关键词
  const addKeyword = () => {
    const keyword = keywordInput.trim();
    if (keyword && !formData.keywords.includes(keyword)) {
      updateFormData('keywords', [...formData.keywords, keyword]);
      setKeywordInput('');
    }
  };

  // 移除关键词
  const removeKeyword = (keyword: string) => {
    updateFormData('keywords', formData.keywords.filter(k => k !== keyword));
  };

  // 添加数据源
  const addSource = () => {
    const source = sourceInput.trim();
    if (source && !formData.sources.includes(source)) {
      updateFormData('sources', [...formData.sources, source]);
      setSourceInput('');
    }
  };

  // 移除数据源
  const removeSource = (source: string) => {
    updateFormData('sources', formData.sources.filter(s => s !== source));
  };

  // 快速添加预设数据源
  const addPresetSource = (source: string) => {
    if (!formData.sources.includes(source)) {
      updateFormData('sources', [...formData.sources, source]);
    }
  };

  // 表单验证
  const validateForm = (): boolean => {
    if (!formData.topic.trim()) {
      setError('请输入分析主题');
      return false;
    }

    if (formData.keywords.length === 0) {
      setError('请至少添加一个关键词');
      return false;
    }

    if (formData.time_range.start && formData.time_range.end) {
      const startDate = new Date(formData.time_range.start);
      const endDate = new Date(formData.time_range.end);
      
      if (startDate > endDate) {
        setError('开始时间不能晚于结束时间');
        return false;
      }
    }

    return true;
  };

  // 提交表单
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const request: AnalysisRequest = {
        topic: formData.topic.trim(),
        keywords: formData.keywords,
        time_range: formData.time_range.start && formData.time_range.end ? {
          start: formData.time_range.start,
          end: formData.time_range.end,
        } : undefined,
        sources: formData.sources.length > 0 ? formData.sources : undefined,
      };

      const response = await analysisApi.createAnalysis(request);

      if (response.success && response.data) {
        // 创建成功，跳转到报告详情页
        router.push(`/intelligence/reports/${response.data.id}`);
      } else {
        setError(response.error || '创建分析任务失败');
      }
    } catch (err) {
      setError(errorUtils.getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <Head>
        <title>新建智能分析 - QSou</title>
        <meta name="description" content="创建新的投资主题智能分析任务" />
      </Head>

      <div className="min-h-screen bg-gray-50">
        {/* 页面头部 */}
        <div className="bg-white border-b border-gray-200">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="py-6">
              <div className="flex items-center space-x-4">
                <Link 
                  href="/intelligence"
                  className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <ArrowLeft className="h-5 w-5 text-gray-600" />
                </Link>
                
                <div>
                  <h1 className="text-2xl font-bold text-gray-900">新建智能分析</h1>
                  <p className="mt-1 text-sm text-gray-600">
                    创建投资主题分析任务，系统将自动收集相关信息并生成深度报告
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 表单内容 */}
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <form onSubmit={handleSubmit}>
            <div className="space-y-8">
              {/* 基本信息 */}
              <Card>
                <CardHeader>
                  <CardTitle>基本信息</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* 分析主题 */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      分析主题 *
                    </label>
                    <Input
                      type="text"
                      value={formData.topic}
                      onChange={(e) => updateFormData('topic', e.target.value)}
                      placeholder="例如：新能源汽车行业2024年发展趋势分析"
                      className="text-lg"
                    />
                    <p className="mt-1 text-sm text-gray-500">
                      请输入明确的分析主题，系统将基于此主题进行数据收集和分析
                    </p>
                  </div>

                  {/* 关键词 */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      关键词 *
                    </label>
                    <div className="flex space-x-2 mb-3">
                      <Input
                        type="text"
                        value={keywordInput}
                        onChange={(e) => setKeywordInput(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            addKeyword();
                          }
                        }}
                        placeholder="输入关键词后按回车添加"
                        className="flex-1"
                      />
                      <Button type="button" onClick={addKeyword}>
                        <Plus className="h-4 w-4" />
                      </Button>
                    </div>
                    
                    {formData.keywords.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {formData.keywords.map((keyword) => (
                          <span
                            key={keyword}
                            className="inline-flex items-center px-3 py-1 text-sm bg-primary-100 text-primary-800 rounded-full"
                          >
                            <Tag className="h-3 w-3 mr-1" />
                            {keyword}
                            <button
                              type="button"
                              onClick={() => removeKeyword(keyword)}
                              className="ml-2 text-primary-600 hover:text-primary-800"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                    
                    <p className="mt-1 text-sm text-gray-500">
                      添加相关关键词以提高分析准确性，例如：新能源汽车、特斯拉、比亚迪、电池技术
                    </p>
                  </div>
                </CardContent>
              </Card>

              {/* 分析范围 */}
              <Card>
                <CardHeader>
                  <CardTitle>分析范围</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* 时间范围 */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      <Calendar className="inline h-4 w-4 mr-1" />
                      时间范围
                    </label>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">开始日期</label>
                        <Input
                          type="date"
                          value={formData.time_range.start}
                          onChange={(e) => updateFormData('time_range', {
                            ...formData.time_range,
                            start: e.target.value
                          })}
                          max={formData.time_range.end}
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">结束日期</label>
                        <Input
                          type="date"
                          value={formData.time_range.end}
                          onChange={(e) => updateFormData('time_range', {
                            ...formData.time_range,
                            end: e.target.value
                          })}
                          min={formData.time_range.start}
                          max={dateUtils.formatDate(new Date().toISOString())}
                        />
                      </div>
                    </div>
                    
                    {/* 快捷时间选择 */}
                    <div className="mt-3 flex flex-wrap gap-2">
                      {[
                        { label: '最近一周', days: 7 },
                        { label: '最近一月', days: 30 },
                        { label: '最近三月', days: 90 },
                        { label: '最近半年', days: 180 },
                      ].map((period) => (
                        <Button
                          key={period.label}
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            const endDate = new Date();
                            const startDate = new Date();
                            startDate.setDate(endDate.getDate() - period.days);
                            
                            updateFormData('time_range', {
                              start: dateUtils.formatDate(startDate.toISOString()),
                              end: dateUtils.formatDate(endDate.toISOString()),
                            });
                          }}
                          className="text-xs"
                        >
                          {period.label}
                        </Button>
                      ))}
                    </div>
                    
                    <p className="mt-1 text-sm text-gray-500">
                      选择数据分析的时间范围，留空则分析所有可用数据
                    </p>
                  </div>

                  {/* 数据源 */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      <Globe className="inline h-4 w-4 mr-1" />
                      数据源
                    </label>
                    
                    <div className="flex space-x-2 mb-3">
                      <Input
                        type="text"
                        value={sourceInput}
                        onChange={(e) => setSourceInput(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            addSource();
                          }
                        }}
                        placeholder="输入数据源名称"
                        className="flex-1"
                      />
                      <Button type="button" onClick={addSource}>
                        <Plus className="h-4 w-4" />
                      </Button>
                    </div>

                    {/* 预设数据源快捷选择 */}
                    <div className="mb-3">
                      <p className="text-xs text-gray-500 mb-2">快速选择常用数据源：</p>
                      <div className="flex flex-wrap gap-2">
                        {availableSources.map((source) => (
                          <button
                            key={source}
                            type="button"
                            onClick={() => addPresetSource(source)}
                            disabled={formData.sources.includes(source)}
                            className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                              formData.sources.includes(source)
                                ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed'
                                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50 cursor-pointer'
                            }`}
                          >
                            {source}
                          </button>
                        ))}
                      </div>
                    </div>
                    
                    {formData.sources.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {formData.sources.map((source) => (
                          <span
                            key={source}
                            className="inline-flex items-center px-3 py-1 text-sm bg-green-100 text-green-800 rounded-full"
                          >
                            <Globe className="h-3 w-3 mr-1" />
                            {source}
                            <button
                              type="button"
                              onClick={() => removeSource(source)}
                              className="ml-2 text-green-600 hover:text-green-800"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                    
                    <p className="mt-1 text-sm text-gray-500">
                      指定数据来源，留空则从所有可用数据源进行分析
                    </p>
                  </div>
                </CardContent>
              </Card>

              {/* 错误提示 */}
              {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <div className="flex">
                    <div className="flex-shrink-0">
                      <X className="h-5 w-5 text-red-400" />
                    </div>
                    <div className="ml-3">
                      <p className="text-sm text-red-800">{error}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setError(null)}
                      className="ml-auto flex-shrink-0 text-red-400 hover:text-red-600"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              )}

              {/* 提交按钮 */}
              <div className="flex justify-end space-x-4">
                <Link href="/intelligence">
                  <Button variant="outline" type="button">
                    取消
                  </Button>
                </Link>
                
                <Button type="submit" loading={loading} disabled={loading}>
                  {loading ? '创建中...' : '创建分析任务'}
                </Button>
              </div>
            </div>
          </form>
        </div>
      </div>
    </Layout>
  );
};

export default CreateAnalysisPage;
