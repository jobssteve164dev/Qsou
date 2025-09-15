import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { Eye, EyeOff, LogIn, Lock, User, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { authApi } from '@/services/api';
import { LoginRequest } from '@/types';
import { errorUtils } from '@/utils';

const LoginPage: React.FC = () => {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  
  const [formData, setFormData] = useState<LoginRequest>({
    username: '',
    password: '',
  });

  // 检查是否已经登录
  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      router.push('/');
    }
  }, [router]);

  // 更新表单数据
  const updateFormData = (field: keyof LoginRequest, value: string) => {
    setFormData(prev => ({
      ...prev,
      [field]: value,
    }));
    
    // 清除错误信息
    if (error) {
      setError(null);
    }
  };

  // 表单验证
  const validateForm = (): boolean => {
    if (!formData.username.trim()) {
      setError('请输入用户名或邮箱');
      return false;
    }

    if (!formData.password) {
      setError('请输入密码');
      return false;
    }

    if (formData.password.length < 6) {
      setError('密码至少需要6位字符');
      return false;
    }

    return true;
  };

  // 处理登录
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await authApi.login({
        username: formData.username.trim(),
        password: formData.password,
      });

      if (response.success && response.data) {
        // 登录成功，重定向到首页或返回页面
        const returnUrl = (router.query.returnUrl as string) || '/';
        router.push(returnUrl);
      } else {
        setError(response.error || '登录失败，请检查用户名和密码');
      }
    } catch (err) {
      setError(errorUtils.getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  // 处理键盘事件
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleLogin(e as any);
    }
  };

  return (
    <>
      <Head>
        <title>登录 - QSou 投资情报搜索引擎</title>
        <meta name="description" content="登录 QSou 投资情报搜索引擎，享受专业的财经数据检索服务" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
        <div className="w-full max-w-md">
          {/* Logo 和标题 */}
          <div className="text-center mb-8">
            <div className="flex justify-center mb-6">
              <div className="h-16 w-16 bg-primary-600 rounded-xl flex items-center justify-center">
                <span className="text-white font-bold text-2xl">Q</span>
              </div>
            </div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              欢迎回来
            </h1>
            <p className="text-gray-600">
              登录您的 QSou 账户
            </p>
          </div>

          {/* 登录表单 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-center space-x-2">
                <LogIn className="h-5 w-5" />
                <span>用户登录</span>
              </CardTitle>
            </CardHeader>
            
            <CardContent>
              <form onSubmit={handleLogin} className="space-y-6">
                {/* 错误提示 */}
                {error && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <div className="flex items-start">
                      <AlertCircle className="h-5 w-5 text-red-400 mt-0.5 mr-3 flex-shrink-0" />
                      <div className="text-sm text-red-800">
                        {error}
                      </div>
                    </div>
                  </div>
                )}

                {/* 用户名/邮箱 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    用户名或邮箱 *
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <User className="h-4 w-4 text-gray-400" />
                    </div>
                    <Input
                      type="text"
                      value={formData.username}
                      onChange={(e) => updateFormData('username', e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="请输入用户名或邮箱"
                      className="pl-10"
                      autoComplete="username"
                      required
                    />
                  </div>
                </div>

                {/* 密码 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    密码 *
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <Lock className="h-4 w-4 text-gray-400" />
                    </div>
                    <Input
                      type={showPassword ? 'text' : 'password'}
                      value={formData.password}
                      onChange={(e) => updateFormData('password', e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="请输入密码"
                      className="pl-10 pr-10"
                      autoComplete="current-password"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600"
                    >
                      {showPassword ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                </div>

                {/* 记住我和忘记密码 */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <input
                      id="remember-me"
                      type="checkbox"
                      className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                    />
                    <label htmlFor="remember-me" className="ml-2 block text-sm text-gray-700">
                      记住我
                    </label>
                  </div>

                  <Link
                    href="/forgot-password"
                    className="text-sm text-primary-600 hover:text-primary-500"
                  >
                    忘记密码？
                  </Link>
                </div>

                {/* 登录按钮 */}
                <Button
                  type="submit"
                  className="w-full"
                  loading={loading}
                  disabled={loading}
                >
                  {loading ? '正在登录...' : '登录'}
                </Button>

                {/* 分隔线 */}
                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-gray-300" />
                  </div>
                  <div className="relative flex justify-center text-sm">
                    <span className="px-2 bg-white text-gray-500">或者</span>
                  </div>
                </div>

                {/* 演示账户 */}
                <div className="bg-gray-50 rounded-lg p-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">演示账户</h4>
                  <div className="space-y-2 text-xs text-gray-600">
                    <div className="flex justify-between">
                      <span>管理员:</span>
                      <code className="bg-white px-2 py-1 rounded">admin / admin123</code>
                    </div>
                    <div className="flex justify-between">
                      <span>普通用户:</span>
                      <code className="bg-white px-2 py-1 rounded">user / user123</code>
                    </div>
                  </div>
                </div>
              </form>
            </CardContent>
          </Card>

          {/* 注册链接 */}
          <div className="mt-6 text-center">
            <p className="text-sm text-gray-600">
              还没有账户？{' '}
              <Link
                href="/register"
                className="font-medium text-primary-600 hover:text-primary-500"
              >
                立即注册
              </Link>
            </p>
          </div>

          {/* 版权信息 */}
          <div className="mt-8 text-center text-xs text-gray-500">
            <p>© 2025 QSou 投资情报搜索引擎. All rights reserved.</p>
          </div>
        </div>
      </div>
    </>
  );
};

export default LoginPage;
