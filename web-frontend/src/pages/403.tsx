import React from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { Shield, ArrowLeft, Home } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';

const ForbiddenPage: React.FC = () => {
  return (
    <>
      <Head>
        <title>权限不足 - QSou</title>
        <meta name="description" content="您没有权限访问此页面" />
      </Head>

      <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
        <div className="w-full max-w-md">
          <Card>
            <CardContent className="py-12 text-center">
              <div className="text-red-500 mb-6">
                <Shield className="h-16 w-16 mx-auto" />
              </div>
              
              <h1 className="text-3xl font-bold text-gray-900 mb-4">
                403
              </h1>
              
              <h2 className="text-xl font-medium text-gray-700 mb-4">
                权限不足
              </h2>
              
              <p className="text-gray-600 mb-8">
                抱歉，您没有权限访问此页面。请联系管理员获取相应权限。
              </p>
              
              <div className="space-y-4">
                <Link href="/">
                  <Button className="w-full flex items-center justify-center space-x-2">
                    <Home className="h-4 w-4" />
                    <span>返回首页</span>
                  </Button>
                </Link>
                
                <Button
                  variant="outline"
                  onClick={() => window.history.back()}
                  className="w-full flex items-center justify-center space-x-2"
                >
                  <ArrowLeft className="h-4 w-4" />
                  <span>返回上一页</span>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
};

export default ForbiddenPage;

