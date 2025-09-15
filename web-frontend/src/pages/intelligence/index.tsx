import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { Plus, BarChart3, Clock, TrendingUp, Filter, Search, Eye } from 'lucide-react';
import { Layout } from '@/components/Layout';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Loading } from '@/components/ui/Loading';
import { analysisApi } from '@/services/api';
import { AnalysisReport } from '@/types';
import { dateUtils, textUtils, errorUtils } from '@/utils';

const IntelligencePage: React.FC = () => {
  const [reports, setReports] = useState<AnalysisReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filteredReports, setFilteredReports] = useState<AnalysisReport[]>([]);
  
  // 分页状态
  const [pagination, setPagination] = useState({
    page: 1,
    size: 10,
    total: 0,
  });

  // 获取分析报告列表
  const fetchReports = async (page: number = 1) => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await analysisApi.getAnalysisList(page, pagination.size);
      
      if (response.success && response.data) {
        setReports(response.data.reports);
        setPagination({
          page: response.data.page,
          size: response.data.size,
          total: response.data.total,
        });
      } else {
        setError(response.error || '获取报告列表失败');
      }
    } catch (err) {
      setError(errorUtils.getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  // 过滤报告
  useEffect(() => {
    if (!searchQuery.trim()) {
      setFilteredReports(reports);
    } else {
      const filtered = reports.filter(report => 
        report.topic.toLowerCase().includes(searchQuery.toLowerCase()) ||
        report.summary.toLowerCase().includes(searchQuery.toLowerCase())
      );
      setFilteredReports(filtered);
    }
  }, [reports, searchQuery]);

  // 初始化加载
  useEffect(() => {
    fetchReports();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // 只在组件加载时执行一次

  // 获取状态颜色
  const getStatusColor = (status: AnalysisReport['status']) => {
    const colors = {
      pending: 'bg-yellow-100 text-yellow-800',
      processing: 'bg-blue-100 text-blue-800',
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
    };
    return colors[status];
  };

  // 获取状态文本
  const getStatusText = (status: AnalysisReport['status']) => {
    const statusMap = {
      pending: '等待中',
      processing: '分析中',
      completed: '已完成',
      failed: '失败',
    };
    return statusMap[status];
  };

  return (
    <Layout>
      <Head>
        <title>智能情报分析 - QSou</title>
        <meta name="description" content="智能情报分析管理，创建和查看投资主题分析报告" />
      </Head>

      <div className="min-h-screen bg-gray-50">
        {/* 页面头部 */}
        <div className="bg-white border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="py-6">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-2xl font-bold text-gray-900">智能情报分析</h1>
                  <p className="mt-1 text-sm text-gray-600">
                    创建投资主题分析任务，自动生成深度分析报告
                  </p>
                </div>
                
                <div className="flex items-center space-x-3">
                  <Link href="/intelligence/create">
                    <Button className="flex items-center space-x-2">
                      <Plus className="h-4 w-4" />
                      <span>新建分析</span>
                    </Button>
                  </Link>
                </div>
              </div>

              {/* 搜索和筛选 */}
              <div className="mt-6 flex items-center space-x-4">
                <div className="flex-1 max-w-md">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <Input
                      type="text"
                      placeholder="搜索报告主题或内容..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-10"
                    />
                  </div>
                </div>
                
                <Button variant="outline" className="flex items-center space-x-2">
                  <Filter className="h-4 w-4" />
                  <span>筛选</span>
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* 主内容区域 */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {/* 统计卡片 */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <BarChart3 className="h-8 w-8 text-primary-600" />
                  </div>
                  <div className="ml-4">
                    <p className="text-sm font-medium text-gray-600">总报告数</p>
                    <p className="text-2xl font-bold text-gray-900">{pagination.total}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-6">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <Clock className="h-8 w-8 text-yellow-600" />
                  </div>
                  <div className="ml-4">
                    <p className="text-sm font-medium text-gray-600">处理中</p>
                    <p className="text-2xl font-bold text-gray-900">
                      {reports.filter(r => r.status === 'processing').length}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-6">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <TrendingUp className="h-8 w-8 text-green-600" />
                  </div>
                  <div className="ml-4">
                    <p className="text-sm font-medium text-gray-600">已完成</p>
                    <p className="text-2xl font-bold text-gray-900">
                      {reports.filter(r => r.status === 'completed').length}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-6">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <Eye className="h-8 w-8 text-blue-600" />
                  </div>
                  <div className="ml-4">
                    <p className="text-sm font-medium text-gray-600">等待中</p>
                    <p className="text-2xl font-bold text-gray-900">
                      {reports.filter(r => r.status === 'pending').length}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* 报告列表 */}
          {loading ? (
            <div className="py-12">
              <Loading size="lg" text="加载分析报告中..." />
            </div>
          ) : error ? (
            <Card className="border-red-200 bg-red-50">
              <CardContent className="py-8 text-center">
                <div className="text-red-600 mb-4">
                  <BarChart3 className="h-12 w-12 mx-auto mb-2" />
                  <h3 className="text-lg font-medium">加载失败</h3>
                </div>
                <p className="text-red-500 text-sm mb-4">{error}</p>
                <Button onClick={() => fetchReports()} variant="outline">
                  重新加载
                </Button>
              </CardContent>
            </Card>
          ) : filteredReports.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <div className="text-gray-400 mb-4">
                  <BarChart3 className="h-12 w-12 mx-auto mb-2" />
                  <h3 className="text-lg font-medium text-gray-600">
                    {searchQuery.trim() ? '没有找到匹配的报告' : '暂无分析报告'}
                  </h3>
                </div>
                <p className="text-gray-500 text-sm mb-4">
                  {searchQuery.trim() 
                    ? '尝试使用不同的搜索关键词'
                    : '点击"新建分析"按钮创建您的第一个智能分析报告'
                  }
                </p>
                {!searchQuery.trim() && (
                  <Link href="/intelligence/create">
                    <Button>
                      <Plus className="h-4 w-4 mr-2" />
                      新建分析
                    </Button>
                  </Link>
                )}
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredReports.map((report) => (
                  <ReportCard key={report.id} report={report} />
                ))}
              </div>

              {/* 分页 */}
              {pagination.total > pagination.size && (
                <div className="flex items-center justify-between">
                  <div className="text-sm text-gray-700">
                    显示第 {((pagination.page - 1) * pagination.size) + 1} - {Math.min(pagination.page * pagination.size, pagination.total)} 条，
                    共 {pagination.total} 条记录
                  </div>
                  
                  <div className="flex space-x-2">
                    <Button
                      variant="outline"
                      disabled={pagination.page <= 1}
                      onClick={() => fetchReports(pagination.page - 1)}
                    >
                      上一页
                    </Button>
                    <Button
                      variant="outline"
                      disabled={pagination.page * pagination.size >= pagination.total}
                      onClick={() => fetchReports(pagination.page + 1)}
                    >
                      下一页
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
};

// 报告卡片组件
const ReportCard: React.FC<{ report: AnalysisReport }> = ({ report }) => {
  const getStatusColor = (status: AnalysisReport['status']) => {
    const colors = {
      pending: 'bg-yellow-100 text-yellow-800',
      processing: 'bg-blue-100 text-blue-800',
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
    };
    return colors[status];
  };

  const getStatusText = (status: AnalysisReport['status']) => {
    const statusMap = {
      pending: '等待中',
      processing: '分析中',
      completed: '已完成',
      failed: '失败',
    };
    return statusMap[status];
  };

  return (
    <Card className="hover:shadow-md transition-shadow duration-200">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <CardTitle className="text-lg font-medium text-gray-900 line-clamp-2">
            {report.topic}
          </CardTitle>
          <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(report.status)}`}>
            {getStatusText(report.status)}
          </span>
        </div>
      </CardHeader>
      
      <CardContent className="pt-0">
        <p className="text-sm text-gray-600 mb-4 line-clamp-3">
          {textUtils.truncate(report.summary, 120)}
        </p>
        
        {/* 关键指标 */}
        {report.status === 'completed' && report.sentiment && (
          <div className="mb-4">
            <div className="text-xs text-gray-500 mb-2">情感分析</div>
            <div className="flex space-x-2">
              <div className="flex-1 bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-green-500 h-2 rounded-full" 
                  style={{ width: `${report.sentiment.positive * 100}%` }}
                ></div>
              </div>
              <span className="text-xs text-gray-600">
                {Math.round(report.sentiment.positive * 100)}% 积极
              </span>
            </div>
          </div>
        )}

        <div className="flex items-center justify-between text-xs text-gray-500">
          <div className="flex items-center space-x-2">
            <Clock className="h-3 w-3" />
            <span>{dateUtils.formatRelative(report.created_at)}</span>
          </div>
          
          <div className="flex items-center space-x-2">
            {report.related_documents && (
              <>
                <span>{report.related_documents.length} 文档</span>
                <span>•</span>
              </>
            )}
            <Link
              href={`/intelligence/reports/${report.id}`}
              className="text-primary-600 hover:text-primary-700 font-medium"
            >
              查看详情
            </Link>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default IntelligencePage;
