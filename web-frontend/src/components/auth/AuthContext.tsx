import React, {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { useRouter } from 'next/router';

import { User } from '@/types';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<{ ok: boolean; error?: string }>;
  logout: () => Promise<void>;
  isAuthenticated: boolean;
  hasRole: (role: string) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const checkSession = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/session/me', {
        method: 'GET',
        credentials: 'same-origin',
        cache: 'no-store',
      });
      if (!response.ok) {
        setUser(null);
        return;
      }
      const payload = await response.json();
      setUser(payload.user || null);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkSession();
  }, [checkSession]);

  const login = useCallback(async (username: string, password: string) => {
    try {
      const response = await fetch('/api/session/login', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.user) {
        return { ok: false, error: payload.error || '登录失败，请稍后重试' };
      }
      setUser(payload.user);
      return { ok: true };
    } catch {
      return { ok: false, error: '暂时无法连接登录服务，请稍后重试' };
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await fetch('/api/session/logout', {
        method: 'POST',
        credentials: 'same-origin',
      });
    } finally {
      setUser(null);
    }
  }, []);

  const value = useMemo<AuthContextType>(
    () => ({
      user,
      loading,
      login,
      logout,
      isAuthenticated: Boolean(user),
      hasRole: (role: string) => Boolean(user && (user.role === role || user.role === 'admin')),
    }),
    [loading, login, logout, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
};

export const AuthBoundary: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      const returnUrl = router.asPath.startsWith('/') ? router.asPath : '/';
      router.replace(`/login?returnUrl=${encodeURIComponent(returnUrl)}`);
    }
  }, [isAuthenticated, loading, router]);

  if (loading) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-slate-950 text-slate-100">
        <div className="text-center" role="status" aria-live="polite">
          <div className="mx-auto mb-4 h-9 w-9 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
          <p className="text-sm text-slate-300">正在确认登录状态</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) return null;
  return <>{children}</>;
};

export const withAuth = <P extends object>(
  WrappedComponent: React.ComponentType<P>,
  requiredRole?: string,
) => {
  const AuthenticatedComponent: React.FC<P> = (props) => {
    const { hasRole } = useAuth();
    const router = useRouter();

    useEffect(() => {
      if (requiredRole && !hasRole(requiredRole)) router.replace('/403');
    }, [hasRole, router]);

    if (requiredRole && !hasRole(requiredRole)) return null;
    return (
      <AuthBoundary>
        <WrappedComponent {...props} />
      </AuthBoundary>
    );
  };
  AuthenticatedComponent.displayName = `withAuth(${WrappedComponent.displayName || WrappedComponent.name})`;
  return AuthenticatedComponent;
};
