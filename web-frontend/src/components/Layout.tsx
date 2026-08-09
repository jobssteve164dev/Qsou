import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { Database, LogOut, Search } from 'lucide-react';

import { useAuth } from './auth/AuthContext';

interface LayoutProps {
  children: React.ReactNode;
}

const navigation = [
  { name: '搜索', href: '/', icon: Search },
  { name: '数据资产', href: '/data', icon: Database },
];

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const router = useRouter();
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
  };

  return (
    <div className="flex min-h-dvh flex-col bg-slate-50 text-slate-950">
      <a
        href="#main-content"
        className="sr-only z-50 rounded-md bg-white px-4 py-2 text-slate-950 focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        跳到主要内容
      </a>
      <header className="border-b border-slate-800 bg-slate-950 text-white">
        <div className="mx-auto flex min-h-16 max-w-6xl items-center gap-4 px-4 sm:px-6 lg:px-8">
          <Link href="/" className="flex min-h-11 items-center gap-3 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
            <span className="grid h-9 w-9 place-items-center rounded-lg bg-cyan-400 font-semibold text-slate-950">Q</span>
            <span>
              <span className="block text-base font-semibold leading-5">QSou</span>
              <span className="hidden text-xs text-slate-400 sm:block">自主投资数据</span>
            </span>
          </Link>

          <nav aria-label="主导航" className="ml-auto flex items-center gap-1 sm:ml-8">
            {navigation.map((item) => {
              const active = item.href === '/' ? router.pathname === '/' : router.pathname.startsWith(item.href);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? 'page' : undefined}
                  className={`inline-flex min-h-11 items-center gap-2 rounded-lg px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 ${
                    active ? 'bg-slate-800 text-white' : 'text-slate-300 hover:bg-slate-900 hover:text-white'
                  }`}
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  <span>{item.name}</span>
                </Link>
              );
            })}
          </nav>

          <div className="hidden h-7 w-px bg-slate-800 sm:block" />
          <div className="hidden text-right sm:block">
            <div className="text-sm font-medium text-slate-100">{user?.username}</div>
            <div className="text-xs text-slate-400">私人空间</div>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg text-slate-300 transition-colors hover:bg-slate-900 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
            aria-label="退出登录"
            title="退出登录"
          >
            <LogOut className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
      </header>

      <main id="main-content" className="flex-1">
        {children}
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-1 px-4 py-5 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <span>QSou · 你的数据，始终可追溯、可导出</span>
          <span>搜索结果不构成投资建议</span>
        </div>
      </footer>
    </div>
  );
};

export { Layout };
