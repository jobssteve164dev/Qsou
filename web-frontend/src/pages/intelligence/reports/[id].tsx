import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { 
  ArrowLeft, Download, Share2, RefreshCw, Trash2, 
  TrendingUp, TrendingDown, Clock, FileText, 
  BarChart3, PieChart, Activity
} from 'lucide-react';
import { Layout } from '@/components/Layout';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Loading } from '@/components/ui/Loading';
import { analysisApi } from '@/services/api';
import { AnalysisReport, SearchDocument } from '@/types';
import { dateUtils, textUtils, errorUtils, numberUtils } from '@/utils';
import { useAuth } from '@/hooks/useAuth';

const ReportDetailPage: React.FC = () => {
  const router = useRouter();
  const { id } = router.query;
  
  // 使用认证Hook，开发环境下会自动静默登录
  const { isAuthenticated, isLoading: authLoading } = useAuth({
    redirectTo: '/login',
    redirectIfFound: false,
    enableSilentLogin: true, // 开发环境启用静默登录
  });
  
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  // 获取报告详情
  const fetchReport = async () => {
    if (!id || typeof id !== 'string') return;

    try {
      setLoading(true);
      setError(null);
      
      const response = await analysisApi.getAnalysis(id);
      
      if (response.success && response.data) {
        setReport(response.data);
      } else {
        setError(response.error || '获取报告详情失败');
      }
    } catch (err) {
      setError(errorUtils.getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  // 删除报告
  const handleDeleteReport = async () => {
    if (!report || !confirm('确定要删除这个分析报告吗？此操作无法撤销。')) {
      return;
    }

    try {
      setDeleting(true);
      
      const response = await analysisApi.deleteAnalysis(report.id);
      
      if (response.success) {
        router.push('/intelligence');
      } else {
        alert(response.error || '删除报告失败');
      }
    } catch (err) {
      alert(errorUtils.getErrorMessage(err));
    } finally {
      setDeleting(false);
    }
  };

  // 刷新报告（用于处理中的报告）
  const handleRefreshReport = () => {
    fetchReport();
  };

  // 导出报告
  const handleExportReport = () => {
    if (!report) return;
    
    // 这里可以实现PDF导出等功能
    const content = `
分析报告：${report.topic}

生成时间：${dateUtils.formatDateTime(report.created_at)}

概要：
${report.summary}

关键要点：
${report.key_points.map((point, index) => `${index + 1}. ${point}`).join('\n')}

情感分析：
积极：${numberUtils.formatPercentage(report.sentiment?.positive || 0)}
中性：${numberUtils.formatPercentage(report.sentiment?.neutral || 0)}
消极：${numberUtils.formatPercentage(report.sentiment?.negative || 0)}

相关文档数量：${report.related_documents?.length || 0}
    `;

    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${report.topic}-分析报告.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    // 等待认证完成后再获取报告
    if (!authLoading && isAuthenticated && id) {
      fetchReport();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, isAuthenticated, id]); // 当认证状态或ID改变时重新获取报告

  // 获取状态颜色和文本
  const getStatusColor = (status: AnalysisReport['status']) => {
    const colors = {
      pending: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      processing: 'bg-blue-100 text-blue-800 border-blue-200',
      completed: 'bg-green-100 text-green-800 border-green-200',
      failed: 'bg-red-100 text-red-800 border-red-200',
    };
    return colors[status];
  };

  const getStatusText = (status: AnalysisReport['status']) => {
    const statusMap = {
      pending: '等待处理',
      processing: '分析中',
      completed: '分析完成',
      failed: '分析失败',
    };
    return statusMap[status];
  };

  // 处理认证加载状态
  if (authLoading) {
    return (
      <Layout>
        <Head>
          <title>智能分析报告 - QSou</title>
        </Head>
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">
              {process.env.NODE_ENV === 'development' ? '正在自动登录...' : '正在验证身份...'}
            </p>
          </div>
        </div>
      </Layout>
    );
  }

  // 未认证状态会由useAuth自动处理重定向
  if (!isAuthenticated) {
    return null;
  }

  if (loading) {
    return (
      <Layout>
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <Loading size="lg" text="加载报告详情中..." />
        </div>
      </Layout>
    );
  }

  if (error || !report) {
    return (
      <Layout>
        <div className="min-h-screen bg-gray-50">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <Card className="border-red-200 bg-red-50">
              <CardContent className="py-8 text-center">
                <div className="text-red-600 mb-4">
                  <FileText className="h-12 w-12 mx-auto mb-2" />
                  <h3 className="text-lg font-medium">加载失败</h3>
                </div>
                <p className="text-red-500 text-sm mb-4">{error || '报告不存在'}</p>
                <div className="space-x-4">
                  <Button onClick={() => router.back()} variant="outline">
                    返回
                  </Button>
                  <Button onClick={fetchReport}>
                    重试
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <Head>
        <title>{report.topic} - 智能分析报告</title>
        <meta name="description" content={textUtils.truncate(report.summary, 160)} />
      </Head>

      <div className="min-h-screen bg-gray-50">
        {/* 页面头部 */}
        <div className="bg-white border-b border-gray-200">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="py-6">
              <div className="flex items-start justify-between">
                <div className="flex items-start space-x-4">
                  <Link 
                    href="/intelligence"
                    className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
                  >
                    <ArrowLeft className="h-5 w-5 text-gray-600" />
                  </Link>
                  
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-2">
                      <h1 className="text-2xl font-bold text-gray-900">
                        {report.topic}
                      </h1>
                      <span className={`px-3 py-1 text-sm font-medium rounded-full border ${getStatusColor(report.status)}`}>
                        {getStatusText(report.status)}
                      </span>
                    </div>
                    
                    <div className="flex items-center space-x-4 text-sm text-gray-600">
                      <div className="flex items-center space-x-1">
                        <Clock className="h-4 w-4" />
                        <span>创建于 {dateUtils.formatDateTime(report.created_at)}</span>
                      </div>
                      
                      {report.related_documents && (
                        <div className="flex items-center space-x-1">
                          <FileText className="h-4 w-4" />
                          <span>{report.related_documents.length} 个相关文档</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center space-x-3">
                  {report.status === 'processing' && (
                    <Button 
                      variant="outline" 
                      onClick={handleRefreshReport}
                      className="flex items-center space-x-2"
                    >
                      <RefreshCw className="h-4 w-4" />
                      <span>刷新</span>
                    </Button>
                  )}
                  
                  {report.status === 'completed' && (
                    <>
                      <Button 
                        variant="outline" 
                        onClick={handleExportReport}
                        className="flex items-center space-x-2"
                      >
                        <Download className="h-4 w-4" />
                        <span>导出</span>
                      </Button>
                      
                      <Button 
                        variant="outline"
                        className="flex items-center space-x-2"
                      >
                        <Share2 className="h-4 w-4" />
                        <span>分享</span>
                      </Button>
                    </>
                  )}
                  
                  <Button 
                    variant="outline" 
                    onClick={handleDeleteReport}
                    loading={deleting}
                    className="text-red-600 hover:text-red-700 border-red-300 hover:border-red-400"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 报告内容 */}
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {report.status === 'pending' && (
            <Card className="mb-8 border-yellow-200 bg-yellow-50">
              <CardContent className="py-6 text-center">
                <div className="text-yellow-600">
                  <Clock className="h-8 w-8 mx-auto mb-2" />
                  <h3 className="text-lg font-medium">分析任务已提交</h3>
                  <p className="text-sm mt-1">您的分析任务正在排队处理中，请稍后查看结果</p>
                </div>
              </CardContent>
            </Card>
          )}

          {report.status === 'processing' && (
            <Card className="mb-8 border-blue-200 bg-blue-50">
              <CardContent className="py-6 text-center">
                <div className="text-blue-600">
                  <Activity className="h-8 w-8 mx-auto mb-2 animate-pulse" />
                  <h3 className="text-lg font-medium">正在分析中</h3>
                  <p className="text-sm mt-1">系统正在收集和分析相关数据，预计需要几分钟时间</p>
                </div>
              </CardContent>
            </Card>
          )}

          {report.status === 'failed' && (
            <Card className="mb-8 border-red-200 bg-red-50">
              <CardContent className="py-6 text-center">
                <div className="text-red-600">
                  <FileText className="h-8 w-8 mx-auto mb-2" />
                  <h3 className="text-lg font-medium">分析失败</h3>
                  <p className="text-sm mt-1">分析过程中发生错误，请重新创建分析任务</p>
                </div>
              </CardContent>
            </Card>
          )}

          {report.status === 'completed' && (
            <div className="space-y-8">
              {/* 概要信息 */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center space-x-2">
                    <FileText className="h-5 w-5" />
                    <span>分析概要</span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-gray-700 leading-relaxed whitespace-pre-wrap">
                    {report.summary}
                  </p>
                </CardContent>
              </Card>

              {/* 关键要点 */}
              {report.key_points && report.key_points.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center space-x-2">
                      <BarChart3 className="h-5 w-5" />
                      <span>关键要点</span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-3">
                      {report.key_points.map((point, index) => (
                        <li key={index} className="flex items-start space-x-3">
                          <span className="flex-shrink-0 w-6 h-6 bg-primary-100 text-primary-600 text-sm font-medium rounded-full flex items-center justify-center">
                            {index + 1}
                          </span>
                          <span className="text-gray-700">{point}</span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}

              {/* 情感分析 */}
              {report.sentiment && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center space-x-2">
                      <PieChart className="h-5 w-5" />
                      <span>情感分析</span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                      <div className="text-center">
                        <div className="text-2xl font-bold text-green-600 mb-1">
                          {numberUtils.formatPercentage(report.sentiment.positive)}
                        </div>
                        <div className="text-sm text-gray-600 flex items-center justify-center">
                          <TrendingUp className="h-4 w-4 mr-1 text-green-500" />
                          积极情感
                        </div>
                      </div>
                      
                      <div className="text-center">
                        <div className="text-2xl font-bold text-gray-600 mb-1">
                          {numberUtils.formatPercentage(report.sentiment.neutral)}
                        </div>
                        <div className="text-sm text-gray-600">
                          中性情感
                        </div>
                      </div>
                      
                      <div className="text-center">
                        <div className="text-2xl font-bold text-red-600 mb-1">
                          {numberUtils.formatPercentage(report.sentiment.negative)}
                        </div>
                        <div className="text-sm text-gray-600 flex items-center justify-center">
                          <TrendingDown className="h-4 w-4 mr-1 text-red-500" />
                          消极情感
                        </div>
                      </div>
                    </div>

                    {/* 情感分布图 */}
                    <div className="mt-6">
                      <div className="w-full bg-gray-200 rounded-full h-4 flex overflow-hidden">
                        <div 
                          className="bg-green-500 h-full" 
                          style={{ width: `${report.sentiment.positive * 100}%` }}
                        ></div>
                        <div 
                          className="bg-gray-400 h-full" 
                          style={{ width: `${report.sentiment.neutral * 100}%` }}
                        ></div>
                        <div 
                          className="bg-red-500 h-full" 
                          style={{ width: `${report.sentiment.negative * 100}%` }}
                        ></div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* 趋势分析 */}
              {report.trends && report.trends.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center space-x-2">
                      <Activity className="h-5 w-5" />
                      <span>趋势分析</span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      <p className="text-sm text-gray-600">
                        基于时间序列数据的趋势分析图表
                      </p>
                      
                      {/* 这里可以集成图表库如 Chart.js 或 D3.js 来显示趋势图 */}
                      <div className="h-64 bg-gray-100 rounded-lg flex items-center justify-center">
                        <div className="text-center text-gray-500">
                          <BarChart3 className="h-12 w-12 mx-auto mb-2" />
                          <p>趋势图表</p>
                          <p className="text-sm">集成图表库后显示</p>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* 相关文档 */}
              {report.related_documents && report.related_documents.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center space-x-2">
                      <FileText className="h-5 w-5" />
                      <span>相关文档 ({report.related_documents.length})</span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {report.related_documents.slice(0, 10).map((doc, index) => (
                        <RelatedDocumentItem key={doc.id} document={doc} index={index} />
                      ))}
                      
                      {report.related_documents.length > 10 && (
                        <div className="text-center pt-4">
                          <Button variant="outline" size="sm">
                            查看更多文档 ({report.related_documents.length - 10})
                          </Button>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
};

// 相关文档项组件
const RelatedDocumentItem: React.FC<{ document: SearchDocument; index: number }> = ({ document, index }) => {
  return (
    <div className="border border-gray-200 rounded-lg p-4 hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between mb-2">
        <h4 className="text-sm font-medium text-gray-900 line-clamp-2 flex-1">
          <Link 
            href={document.url} 
            target="_blank" 
            rel="noopener noreferrer"
            className="hover:text-primary-600"
          >
            {document.title}
          </Link>
        </h4>
        <span className="text-xs text-gray-400 ml-2">#{index + 1}</span>
      </div>
      
      <p className="text-xs text-gray-600 mb-2 line-clamp-2">
        {textUtils.extractSummary(document.content, 100)}
      </p>
      
      <div className="flex items-center justify-between text-xs text-gray-500">
        <div className="flex items-center space-x-2">
          <span>{document.source}</span>
          <span>•</span>
          <span>{dateUtils.formatRelative(document.publish_date)}</span>
        </div>
        
        {document.score && (
          <span>相关度: {Math.round(document.score * 100)}%</span>
        )}
      </div>
    </div>
  );
};

export default ReportDetailPage;
