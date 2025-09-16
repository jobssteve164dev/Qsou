import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { Search, BarChart3, Settings, User, LogOut } from 'lucide-react';
import { Button } from './ui/Button';
import { useAuth } from './auth/AuthContext';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const router = useRouter();
  const currentPath = router.pathname;
  const { user, logout, hasRole } = useAuth();

  const navigation = [
    {
      name: '搜索',
      href: '/',
      icon: Search,
      current: currentPath === '/',
    },
    {
      name: '智能分析',
      href: '/intelligence',
      icon: BarChart3,
      current: currentPath.startsWith('/intelligence'),
    },
    ...(hasRole('admin') ? [{
      name: '系统监控',
      href: '/monitor',
      icon: Settings,
      current: currentPath.startsWith('/monitor'),
    }] : []),
  ];

  const handleLogout = () => {
    logout();
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 顶部导航栏 */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* 左侧 - Logo */}
            <div className="flex items-center">
              <Link href="/" className="flex items-center space-x-2">
                <div className="h-8 w-8 bg-primary-600 rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-lg">Q</span>
                </div>
                <span className="text-xl font-bold text-gray-900">QSou</span>
              </Link>
            </div>

            {/* 中间 - 导航菜单 */}
            <nav className="hidden md:flex space-x-8">
              {navigation.map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={`
                      inline-flex items-center px-1 pt-1 text-sm font-medium
                      ${
                        item.current
                          ? 'border-b-2 border-primary-500 text-primary-600'
                          : 'text-gray-500 hover:text-gray-700 hover:border-gray-300'
                      }
                    `}
                  >
                    <Icon className="mr-2 h-4 w-4" />
                    {item.name}
                  </Link>
                );
              })}
            </nav>

            {/* 右侧 - 用户菜单 */}
            <div className="flex items-center space-x-4">
              {user && (
                <div className="text-sm text-gray-700">
                  欢迎, <span className="font-medium">{user.username}</span>
                  {user.role === 'admin' && (
                    <span className="ml-1 px-2 py-0.5 text-xs bg-primary-100 text-primary-700 rounded-full">
                      管理员
                    </span>
                  )}
                </div>
              )}
              
              <Button
                variant="ghost"
                size="sm"
                onClick={handleLogout}
                className="text-gray-500 hover:text-gray-700"
              >
                <LogOut className="h-4 w-4 mr-2" />
                退出登录
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* 移动端导航菜单 */}
      <div className="md:hidden bg-white border-b border-gray-200">
        <div className="px-2 pt-2 pb-3 space-y-1">
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`
                  block px-3 py-2 text-base font-medium rounded-md
                  ${
                    item.current
                      ? 'bg-primary-50 border-primary-500 text-primary-700'
                      : 'text-gray-500 hover:bg-gray-50 hover:text-gray-700'
                  }
                `}
              >
                <div className="flex items-center">
                  <Icon className="mr-3 h-5 w-5" />
                  {item.name}
                </div>
              </Link>
            );
          })}
        </div>
      </div>

      {/* 主要内容区域 */}
      <main className="flex-1">
        {children}
      </main>

      {/* 底部 */}
      <footer className="bg-white border-t border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="text-center text-sm text-gray-500">
            <p>© 2025 QSou 投资情报搜索引擎. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export { Layout };
