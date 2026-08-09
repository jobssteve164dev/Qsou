import React from 'react';
import Link from 'next/link';
import { ArrowRight, Database, ShieldCheck } from 'lucide-react';

interface WelcomeScreenProps {
  onSearchSuggestion?: (query: string) => void;
}

const WelcomeScreen: React.FC<WelcomeScreenProps> = () => (
  <div className="grid gap-5 sm:grid-cols-2">
    <div className="rounded-2xl border border-slate-200 bg-white p-6">
      <Database className="h-6 w-6 text-cyan-700" aria-hidden="true" />
      <h2 className="mt-4 text-lg font-semibold text-slate-950">只返回已保存的数据</h2>
      <p className="mt-2 text-sm leading-6 text-slate-600">资料库为空时会如实显示空状态，不用演示内容补足结果。</p>
    </div>
    <div className="rounded-2xl border border-slate-200 bg-white p-6">
      <ShieldCheck className="h-6 w-6 text-cyan-700" aria-hidden="true" />
      <h2 className="mt-4 text-lg font-semibold text-slate-950">每条结果都能回到证据</h2>
      <p className="mt-2 text-sm leading-6 text-slate-600">来源、采集时间、内容版本与原始响应保持关联。</p>
      <Link href="/data" className="mt-4 inline-flex min-h-11 items-center gap-2 text-sm font-medium text-cyan-700 hover:text-cyan-900">查看数据资产 <ArrowRight className="h-4 w-4" /></Link>
    </div>
  </div>
);

export { WelcomeScreen };
