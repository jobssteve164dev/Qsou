import React, { useEffect } from 'react';
import { useRouter } from 'next/router';

import { useAuth as useAuthContext } from '@/components/auth/AuthContext';

interface UseAuthOptions {
  redirectTo?: string;
  redirectIfFound?: boolean;
  enableSilentLogin?: boolean;
}

export function useAuth(options: UseAuthOptions = {}) {
  const { redirectTo = '/login', redirectIfFound = false } = options;
  const auth = useAuthContext();
  const router = useRouter();

  useEffect(() => {
    if (auth.loading) return;
    if (redirectIfFound && auth.isAuthenticated) {
      router.replace(redirectTo);
    } else if (!redirectIfFound && !auth.isAuthenticated) {
      router.replace(`${redirectTo}?returnUrl=${encodeURIComponent(router.asPath)}`);
    }
  }, [auth.isAuthenticated, auth.loading, redirectIfFound, redirectTo, router]);

  return {
    isAuthenticated: auth.isAuthenticated,
    isLoading: auth.loading,
    user: auth.user,
    logout: auth.logout,
  };
}

export function withAuth<P extends object>(
  Component: React.ComponentType<P>,
  options: UseAuthOptions = {},
) {
  return function ProtectedComponent(props: P) {
    const { isAuthenticated, isLoading } = useAuth(options);
    if (isLoading || !isAuthenticated) return null;
    return <Component {...props} />;
  };
}
