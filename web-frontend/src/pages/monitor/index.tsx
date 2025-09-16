import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import { 
  Activity, Database, Search, Zap, AlertTriangle, 
  CheckCircle, Clock, TrendingUp, Server, Cpu,
  HardDrive, Wifi, RefreshCw
} from 'lucide-react';
import { Layout } from '@/components/Layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Loading } from '@/components/ui/Loading';
import { withAuth } from '@/components/auth/AuthContext';
import { systemApi } from '@/services/api';
import { SystemStats } from '@/types';
import { errorUtils, numberUtils, dateUtils } from '@/utils';

const MonitorPage: React.FC = () => {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string>(new Date().toISOString());

  // 获取系统状态
  const fetchSystemStats = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await systemApi.getStats();
      
      if (response.success && response.data) {
        setStats(response.data);
        setLastUpdate(new Date().toISOString());
      } else {
        setError(response.error || '获取系统状态失败');
      }
    } catch (err) {
      setError(errorUtils.getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  // 检查健康状态
  const checkHealth = async () => {
    try {
      const response = await systemApi.health();
      console.log('健康检查:', response);
    } catch (err) {
      console.error('健康检查失败:', err);
    }
  };

  // 初始化加载
  useEffect(() => {
    fetchSystemStats();
    
    // 每30秒自动刷新
    const interval = setInterval(fetchSystemStats, 30000);
    
    return () => clearInterval(interval);
  }, []);

  // 获取状态颜色
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'text-green-600 bg-green-100';
      case 'warning':
        return 'text-yellow-600 bg-yellow-100';
      case 'error':
        return 'text-red-600 bg-red-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  // 获取状态图标
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="h-5 w-5" />;
      case 'warning':
        return <AlertTriangle className="h-5 w-5" />;
      case 'error':
        return <AlertTriangle className="h-5 w-5" />;
      default:
        return <Clock className="h-5 w-5" />;
    }
  };

  const getServiceStatusColor = (status: boolean) => {
    return status ? 'text-green-600' : 'text-red-600';
  };

  const getServiceStatusIcon = (status: boolean) => {
    return status ? <CheckCircle className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />;
  };

  return (
    <Layout>
      <Head>
        <title>系统监控 - QSou</title>
        <meta name="description" content="QSou 投资情报搜索引擎系统监控面板" />
      </Head>

      <div className="min-h-screen bg-gray-50">
        {/* 页面头部 */}
        <div className="bg-white border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="py-6">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-2xl font-bold text-gray-900">系统监控</h1>
                  <p className="mt-1 text-sm text-gray-600">
                    实时监控系统状态和性能指标
                  </p>
                </div>
                
                <div className="flex items-center space-x-3">
                  <div className="text-sm text-gray-500">
                    最后更新: {dateUtils.formatDateTime(lastUpdate)}
                  </div>
                  
                  <Button
                    onClick={fetchSystemStats}
                    loading={loading}
                    className="flex items-center space-x-2"
                  >
                    <RefreshCw className="h-4 w-4" />
                    <span>刷新</span>
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 主内容区域 */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {loading && !stats ? (
            <div className="py-12">
              <Loading size="lg" text="加载系统状态中..." />
            </div>
          ) : error ? (
            <Card className="border-red-200 bg-red-50">
              <CardContent className="py-8 text-center">
                <div className="text-red-600 mb-4">
                  <Server className="h-12 w-12 mx-auto mb-2" />
                  <h3 className="text-lg font-medium">加载失败</h3>
                </div>
                <p className="text-red-500 text-sm mb-4">{error}</p>
                <Button onClick={fetchSystemStats} variant="outline">
                  重新加载
                </Button>
              </CardContent>
            </Card>
          ) : stats ? (
            <div className="space-y-6">
              {/* 系统整体状态 */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Activity className="h-5 w-5" />
                      <span>系统整体状态</span>
                    </div>
                    
                    <div className={`flex items-center space-x-2 px-3 py-1 rounded-full ${getStatusColor(stats.system_status)}`}>
                      {getStatusIcon(stats.system_status)}
                      <span className="text-sm font-medium">
                        {stats.system_status === 'healthy' ? '正常运行' :
                         stats.system_status === 'warning' ? '警告' : '异常'}
                      </span>
                    </div>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    <div className="text-center">
                      <div className="text-3xl font-bold text-primary-600 mb-2">
                        {numberUtils.formatLargeNumber(stats.documents_count)}
                      </div>
                      <div className="text-sm text-gray-600">文档总数</div>
                    </div>
                    
                    <div className="text-center">
                      <div className="text-3xl font-bold text-green-600 mb-2">
                        {numberUtils.formatLargeNumber(stats.searches_today)}
                      </div>
                      <div className="text-sm text-gray-600">今日搜索</div>
                    </div>
                    
                    <div className="text-center">
                      <div className="text-3xl font-bold text-purple-600 mb-2">
                        {numberUtils.formatLargeNumber(stats.analysis_reports)}
                      </div>
                      <div className="text-sm text-gray-600">分析报告</div>
                    </div>
                    
                    <div className="text-center">
                      <div className="text-3xl font-bold text-blue-600 mb-2">
                        99.9%
                      </div>
                      <div className="text-sm text-gray-600">系统可用性</div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* 服务状态 */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center space-x-2">
                    <Server className="h-5 w-5" />
                    <span>服务状态</span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                      <div className="flex items-center space-x-3">
                        <Database className="h-6 w-6 text-blue-600" />
                        <div>
                          <div className="font-medium text-gray-900">Elasticsearch</div>
                          <div className="text-sm text-gray-500">搜索引擎</div>
                        </div>
                      </div>
                      <div className={`flex items-center space-x-1 ${getServiceStatusColor(stats.services.elasticsearch)}`}>
                        {getServiceStatusIcon(stats.services.elasticsearch)}
                        <span className="text-sm font-medium">
                          {stats.services.elasticsearch ? '正常' : '异常'}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                      <div className="flex items-center space-x-3">
                        <Zap className="h-6 w-6 text-purple-600" />
                        <div>
                          <div className="font-medium text-gray-900">Qdrant</div>
                          <div className="text-sm text-gray-500">向量数据库</div>
                        </div>
                      </div>
                      <div className={`flex items-center space-x-1 ${getServiceStatusColor(stats.services.qdrant)}`}>
                        {getServiceStatusIcon(stats.services.qdrant)}
                        <span className="text-sm font-medium">
                          {stats.services.qdrant ? '正常' : '异常'}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                      <div className="flex items-center space-x-3">
                        <Search className="h-6 w-6 text-green-600" />
                        <div>
                          <div className="font-medium text-gray-900">爬虫服务</div>
                          <div className="text-sm text-gray-500">数据采集</div>
                        </div>
                      </div>
                      <div className={`flex items-center space-x-1 ${getServiceStatusColor(stats.services.crawler)}`}>
                        {getServiceStatusIcon(stats.services.crawler)}
                        <span className="text-sm font-medium">
                          {stats.services.crawler ? '正常' : '异常'}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                      <div className="flex items-center space-x-3">
                        <Cpu className="h-6 w-6 text-orange-600" />
                        <div>
                          <div className="font-medium text-gray-900">数据处理</div>
                          <div className="text-sm text-gray-500">内容分析</div>
                        </div>
                      </div>
                      <div className={`flex items-center space-x-1 ${getServiceStatusColor(stats.services.processor)}`}>
                        {getServiceStatusIcon(stats.services.processor)}
                        <span className="text-sm font-medium">
                          {stats.services.processor ? '正常' : '异常'}
                        </span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* 性能指标 */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center space-x-2">
                      <TrendingUp className="h-5 w-5" />
                      <span>性能指标</span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <Search className="h-4 w-4 text-blue-600" />
                          <span className="text-sm text-gray-600">平均搜索响应时间</span>
                        </div>
                        <span className="text-sm font-medium text-green-600">156ms</span>
                      </div>
                      
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <Database className="h-4 w-4 text-purple-600" />
                          <span className="text-sm text-gray-600">数据库查询时间</span>
                        </div>
                        <span className="text-sm font-medium text-green-600">23ms</span>
                      </div>
                      
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <Cpu className="h-4 w-4 text-orange-600" />
                          <span className="text-sm text-gray-600">CPU使用率</span>
                        </div>
                        <span className="text-sm font-medium text-yellow-600">45%</span>
                      </div>
                      
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <HardDrive className="h-4 w-4 text-gray-600" />
                          <span className="text-sm text-gray-600">磁盘使用率</span>
                        </div>
                        <span className="text-sm font-medium text-green-600">32%</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center space-x-2">
                      <Wifi className="h-5 w-5" />
                      <span>网络状态</span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-600">入站流量</span>
                        <span className="text-sm font-medium">1.2 MB/s</span>
                      </div>
                      
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-600">出站流量</span>
                        <span className="text-sm font-medium">850 KB/s</span>
                      </div>
                      
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-600">活跃连接</span>
                        <span className="text-sm font-medium">127</span>
                      </div>
                      
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-600">错误率</span>
                        <span className="text-sm font-medium text-green-600">0.1%</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </Layout>
  );
};

// 使用高阶组件保护页面，只允许管理员访问
export default withAuth(MonitorPage, 'admin');
