import { useState, useEffect } from 'react';
import { systemApi } from '@/services/api';
import { SystemStats } from '@/types';

export const useSystemStats = () => {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await systemApi.getStats();
      
      if (response.success && response.data) {
        setStats(response.data);
      } else {
        setError(response.error || '获取系统统计失败');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取系统统计失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    
    // 每5分钟自动刷新统计数据
    const interval = setInterval(fetchStats, 5 * 60 * 1000);
    
    return () => clearInterval(interval);
  }, []);

  return {
    stats,
    loading,
    error,
    refetch: fetchStats,
  };
};
