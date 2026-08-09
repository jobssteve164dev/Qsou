import React, { useEffect, useState } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { Database, Eye, EyeOff, LockKeyhole, ShieldCheck, User } from 'lucide-react';

import { useAuth } from '@/components/auth/AuthContext';

const safeReturnUrl = (value: unknown) => {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')) return '/';
  return value;
};

const LoginPage: React.FC = () => {
  const router = useRouter();
  const { isAuthenticated, loading: sessionLoading, login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionLoading && isAuthenticated) {
      router.replace(safeReturnUrl(router.query.returnUrl));
    }
  }, [isAuthenticated, router, sessionLoading]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!username.trim() || !password) {
      setError('请输入用户名和密码');
      return;
    }
    setSubmitting(true);
    setError(null);
    const result = await login(username.trim(), password);
    setSubmitting(false);
    if (!result.ok) {
      setError(result.error || '登录失败，请稍后重试');
      return;
    }
    await router.replace(safeReturnUrl(router.query.returnUrl));
  };

  return (
    <>
      <Head>
        <title>登录 · QSou</title>
        <meta name="description" content="登录 QSou，访问你的私人投资数据资产" />
        <meta name="robots" content="noindex,nofollow" />
      </Head>
      <main className="relative grid min-h-dvh overflow-hidden bg-slate-950 lg:grid-cols-[1.05fr_0.95fr]">
        <section className="relative hidden overflow-hidden border-r border-slate-800 p-12 lg:flex lg:flex-col lg:justify-between">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_15%,rgba(34,211,238,0.17),transparent_35%),radial-gradient(circle_at_85%_70%,rgba(14,165,233,0.12),transparent_40%)]" />
          <div className="relative flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center rounded-xl bg-cyan-400 text-lg font-bold text-slate-950">Q</span>
            <div>
              <div className="font-semibold text-white">QSou</div>
              <div className="text-sm text-slate-400">自主投资数据</div>
            </div>
          </div>
          <div className="relative max-w-xl">
            <p className="mb-5 text-sm font-medium uppercase tracking-[0.22em] text-cyan-300">Data you own</p>
            <h1 className="text-4xl font-semibold leading-tight text-white xl:text-5xl">
              搜索自己持续积累的资料，回到每一条原始证据。
            </h1>
            <div className="mt-10 grid gap-4 text-sm text-slate-300 sm:grid-cols-3">
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
                <Database className="mb-3 h-5 w-5 text-cyan-300" aria-hidden="true" />
                自有数据存储
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
                <ShieldCheck className="mb-3 h-5 w-5 text-cyan-300" aria-hidden="true" />
                来源与版本可追溯
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
                <LockKeyhole className="mb-3 h-5 w-5 text-cyan-300" aria-hidden="true" />
                私人访问空间
              </div>
            </div>
          </div>
          <p className="relative text-xs text-slate-500">搜索结果仅用于研究，不构成投资建议</p>
        </section>

        <section className="flex items-center justify-center bg-slate-50 px-5 py-10 sm:px-8">
          <div className="w-full max-w-md">
            <div className="mb-8 lg:hidden">
              <div className="mb-8 flex items-center gap-3">
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-slate-950 font-bold text-cyan-300">Q</span>
                <span className="font-semibold text-slate-950">QSou</span>
              </div>
            </div>
            <div className="mb-8">
              <p className="mb-2 text-sm font-medium text-cyan-700">私人数据空间</p>
              <h2 className="text-3xl font-semibold tracking-tight text-slate-950">登录后继续</h2>
              <p className="mt-3 text-base leading-7 text-slate-600">输入你的账号和密码，进入搜索、来源证据和数据导出。</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5" noValidate>
              {error && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800" role="alert">
                  {error}
                </div>
              )}
              <div>
                <label htmlFor="username" className="mb-2 block text-sm font-medium text-slate-800">用户名</label>
                <div className="relative">
                  <User className="pointer-events-none absolute left-3 top-3.5 h-5 w-5 text-slate-400" aria-hidden="true" />
                  <input
                    id="username"
                    name="username"
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    autoComplete="username"
                    className="min-h-12 w-full rounded-xl border border-slate-300 bg-white pl-11 pr-4 text-base text-slate-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
                    required
                    autoFocus
                  />
                </div>
              </div>
              <div>
                <label htmlFor="password" className="mb-2 block text-sm font-medium text-slate-800">密码</label>
                <div className="relative">
                  <LockKeyhole className="pointer-events-none absolute left-3 top-3.5 h-5 w-5 text-slate-400" aria-hidden="true" />
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    autoComplete="current-password"
                    className="min-h-12 w-full rounded-xl border border-slate-300 bg-white pl-11 pr-12 text-base text-slate-950 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((value) => !value)}
                    className="absolute right-1 top-1 inline-flex h-10 w-10 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-600"
                    aria-label={showPassword ? '隐藏密码' : '显示密码'}
                  >
                    {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
              </div>
              <button
                type="submit"
                disabled={submitting || sessionLoading}
                className="inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-slate-950 px-5 text-base font-semibold text-white transition hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-cyan-200 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? '正在登录…' : '登录'}
              </button>
            </form>
          </div>
        </section>
      </main>
    </>
  );
};

LoginPage.displayName = 'PublicPage';
export default LoginPage;
