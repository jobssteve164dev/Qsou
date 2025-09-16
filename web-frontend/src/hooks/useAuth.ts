import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { authApi } from '@/services/api';

interface UseAuthOptions {
  redirectTo?: string;
  redirectIfFound?: boolean;
  enableSilentLogin?: boolean;
}

interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: any | null;
}

/**
 * 认证Hook - 处理登录状态检查和静默登录
 * @param options 配置选项
 */
export function useAuth(options: UseAuthOptions = {}) {
  const {
    redirectTo = '/login',
    redirectIfFound = false,
    enableSilentLogin = true,
  } = options;

  const router = useRouter();
  const [authState, setAuthState] = useState<AuthState>({
    isAuthenticated: false,
    isLoading: true,
    user: null,
  });

  useEffect(() => {
    const checkAuth = async () => {
      // 检查本地token
      const token = localStorage.getItem('auth_token');
      
      if (token) {
        // 如果有token，验证其有效性
        try {
          const response = await authApi.getCurrentUser();
          if (response.success && response.data) {
            setAuthState({
              isAuthenticated: true,
              isLoading: false,
              user: response.data,
            });
            
            if (redirectIfFound && redirectTo) {
              router.push(redirectTo);
            }
            return;
          }
        } catch (error) {
          // Token无效，清除
          localStorage.removeItem('auth_token');
        }
      }

      // 开发环境下执行静默登录
      if (process.env.NODE_ENV === 'development' && enableSilentLogin && !token) {
        await performSilentLogin();
      } else {
        // 生产环境或静默登录失败
        setAuthState({
          isAuthenticated: false,
          isLoading: false,
          user: null,
        });

        if (!redirectIfFound && redirectTo) {
          router.push(`${redirectTo}?returnUrl=${encodeURIComponent(router.asPath)}`);
        }
      }
    };

    checkAuth();
  }, [redirectTo, redirectIfFound, enableSilentLogin, router]);

  /**
   * 执行静默登录（仅开发环境）
   */
  const performSilentLogin = async () => {
    try {
      console.log('[Dev Mode] 尝试静默登录...');
      
      const response = await authApi.login({
        username: 'admin',
        password: 'admin123',
      });

      if (response.success && response.data?.token) {
        console.log('[Dev Mode] 静默登录成功');
        
        // 获取用户信息
        const userResponse = await authApi.getCurrentUser();
        if (userResponse.success && userResponse.data) {
          setAuthState({
            isAuthenticated: true,
            isLoading: false,
            user: userResponse.data,
          });
          
          if (redirectIfFound && redirectTo) {
            router.push(redirectTo);
          }
          return;
        }
      }
    } catch (error) {
      console.error('[Dev Mode] 静默登录失败:', error);
    }

    // 静默登录失败，设置为未认证状态
    setAuthState({
      isAuthenticated: false,
      isLoading: false,
      user: null,
    });

    if (!redirectIfFound && redirectTo) {
      router.push(`${redirectTo}?returnUrl=${encodeURIComponent(router.asPath)}`);
    }
  };

  /**
   * 登出
   */
  const logout = async () => {
    await authApi.logout();
    setAuthState({
      isAuthenticated: false,
      isLoading: false,
      user: null,
    });
    router.push('/');
  };

  return {
    ...authState,
    logout,
  };
}

/**
 * 保护页面组件的HOC
 * @param Component 需要保护的组件
 * @param options 配置选项
 */
export function withAuth<P extends object>(
  Component: React.ComponentType<P>,
  options: UseAuthOptions = {}
) {
  return function ProtectedComponent(props: P) {
    const { isAuthenticated, isLoading } = useAuth(options);

    if (isLoading) {
      return (
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">正在验证身份...</p>
          </div>
        </div>
      );
    }

    if (!isAuthenticated) {
      return null; // useAuth会自动处理重定向
    }

    return <Component {...props} />;
  };
}
