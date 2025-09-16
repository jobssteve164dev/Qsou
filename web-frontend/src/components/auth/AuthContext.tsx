import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useRouter } from 'next/router';
import { authApi } from '@/services/api';
import { User } from '@/types';
import { errorUtils } from '@/utils';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  isAuthenticated: boolean;
  hasRole: (role: string) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  // 检查当前用户状态
  const checkAuthStatus = async () => {
    const token = localStorage.getItem('auth_token');
    
    if (!token) {
      setLoading(false);
      return;
    }

    try {
      const response = await authApi.getCurrentUser();
      
      if (response.success && response.data) {
        setUser(response.data);
      } else {
        // Token 无效，清除本地存储
        localStorage.removeItem('auth_token');
        setUser(null);
      }
    } catch (error) {
      console.error('检查认证状态失败:', error);
      localStorage.removeItem('auth_token');
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  // 登录
  const login = async (username: string, password: string): Promise<boolean> => {
    try {
      const response = await authApi.login({ username, password });
      
      if (response.success && response.data) {
        setUser(response.data.user);
        return true;
      } else {
        return false;
      }
    } catch (error) {
      console.error('登录失败:', errorUtils.getErrorMessage(error));
      return false;
    }
  };

  // 登出
  const logout = () => {
    localStorage.removeItem('auth_token');
    setUser(null);
    router.push('/login');
  };

  // 检查是否已认证
  const isAuthenticated = !!user;

  // 检查用户角色
  const hasRole = (role: string): boolean => {
    if (!user) return false;
    return user.role === role || user.role === 'admin';
  };

  // 初始化时检查认证状态
  useEffect(() => {
    checkAuthStatus();
  }, []);

  // 监听路由变化，检查页面权限
  useEffect(() => {
    const handleRouteChange = (url: string) => {
      // 受保护的路由列表
      const protectedRoutes = ['/intelligence', '/monitor'];
      const adminRoutes = ['/monitor'];
      
      const isProtectedRoute = protectedRoutes.some(route => url.startsWith(route));
      const isAdminRoute = adminRoutes.some(route => url.startsWith(route));
      
      if (!loading) {
        if (isProtectedRoute && !isAuthenticated) {
          router.push(`/login?returnUrl=${encodeURIComponent(url)}`);
        } else if (isAdminRoute && !hasRole('admin')) {
          router.push('/403'); // 权限不足页面
        }
      }
    };

    router.events.on('routeChangeStart', handleRouteChange);
    
    // 检查当前页面
    if (!loading) {
      handleRouteChange(router.pathname);
    }

    return () => {
      router.events.off('routeChangeStart', handleRouteChange);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router, loading, isAuthenticated, user]); // hasRole 依赖于 user，不需要单独添加

  const value: AuthContextType = {
    user,
    loading,
    login,
    logout,
    isAuthenticated,
    hasRole,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

// Hook 用于使用认证上下文
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// 高阶组件：保护需要认证的页面
export const withAuth = <P extends object>(
  WrappedComponent: React.ComponentType<P>,
  requiredRole?: string
) => {
  const AuthenticatedComponent: React.FC<P> = (props) => {
    const { user, loading, isAuthenticated, hasRole } = useAuth();
    const router = useRouter();

    useEffect(() => {
      if (!loading) {
        if (!isAuthenticated) {
          router.push(`/login?returnUrl=${encodeURIComponent(router.asPath)}`);
        } else if (requiredRole && !hasRole(requiredRole)) {
          router.push('/403');
        }
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [loading, isAuthenticated, user, router]); // hasRole 依赖于 user，不需要单独添加

    if (loading) {
      return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
            <p className="text-gray-600">验证身份中...</p>
          </div>
        </div>
      );
    }

    if (!isAuthenticated || (requiredRole && !hasRole(requiredRole))) {
      return null; // 重定向将由 useEffect 处理
    }

    return <WrappedComponent {...props} />;
  };

  AuthenticatedComponent.displayName = `withAuth(${WrappedComponent.displayName || WrappedComponent.name})`;
  
  return AuthenticatedComponent;
};
