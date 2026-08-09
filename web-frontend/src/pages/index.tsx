import React, { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import {
  ArrowLeft,
  ArrowRight,
  Clock3,
  Database,
  ExternalLink,
  FileSearch,
  Search,
  ShieldCheck,
} from 'lucide-react';

import { Layout } from '@/components/Layout';
import { dataAssetApi, searchApi } from '@/services/api';
import { DataAssetStatus, DataSourceStatus, SearchResponse } from '@/types';

const formatTime = (value?: string | null) => {
  if (!value) return '时间未知';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN');
};

const collectorLabel = (state?: DataAssetStatus['collector']['state']) => {
  const labels: Record<string, string> = {
    running: '正在采集',
    idle: '等待下一轮采集',
    degraded: '部分来源采集失败',
    not_started: '等待采集器启动',
    stopping: '采集器正在停止',
    disabled: '采集器未启用',
    unknown: '采集状态暂不可用',
  };
  return labels[state || 'unknown'] || labels.unknown;
};

const HomePage: React.FC = () => {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [sourceId, setSourceId] = useState('');
  const [status, setStatus] = useState<DataAssetStatus | null>(null);
  const [sources, setSources] = useState<DataSourceStatus[]>([]);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    Promise.all([dataAssetApi.status(), dataAssetApi.sources()]).then(([statusResult, sourceResult]) => {
      if (statusResult.success && statusResult.data) setStatus(statusResult.data);
      if (sourceResult.success && sourceResult.data) setSources(sourceResult.data.sources);
    });
  }, []);

  const performSearch = useCallback(async (term: string, selectedSource: string, requestedPage = 1) => {
    const normalized = term.trim();
    if (!normalized) return;
    setLoading(true);
    setError(null);
    setSearched(true);
    const response = await searchApi.search({
      query: normalized,
      source: selectedSource || undefined,
      page: requestedPage,
      size: 12,
      sort_by: 'relevance',
    });
    if (response.success && response.data) {
      setResults(response.data);
      setPage(requestedPage);
    } else {
      setResults(null);
      setError(response.error || '暂时无法搜索，请稍后重试');
    }
    setLoading(false);
  }, []);

  const routeQuery = typeof router.query.q === 'string' ? router.query.q : '';
  const routeSource = typeof router.query.source === 'string' ? router.query.source : '';

  useEffect(() => {
    if (!router.isReady) return;
    setQuery(routeQuery);
    setSourceId(routeSource);
    if (routeQuery) performSearch(routeQuery, routeSource, 1);
  }, [performSearch, routeQuery, routeSource, router.isReady]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!query.trim()) {
      setError('请输入要查找的公司、主题或事件');
      return;
    }
    const nextQuery = query.trim();
    const routeIsUnchanged = nextQuery === routeQuery && sourceId === routeSource;
    await router.replace(
      { pathname: '/', query: { q: query.trim(), ...(sourceId ? { source: sourceId } : {}) } },
      undefined,
      { shallow: true },
    );
    if (routeIsUnchanged) await performSearch(nextQuery, sourceId, 1);
  };

  const sourceNames = useMemo(
    () => new Map(sources.map((source) => [source.source_id, source.source_name])),
    [sources],
  );
  const totalPages = results?.total_pages || 1;

  return (
    <Layout>
      <Head>
        <title>搜索我的投资数据 · QSou</title>
        <meta name="description" content="搜索自己持续采集、保存并可追溯的投资数据" />
      </Head>

      <section className="border-b border-slate-800 bg-slate-950 text-white">
        <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14 lg:px-8">
          <div className="max-w-3xl">
            <p className="mb-3 text-sm font-medium text-cyan-300">只搜索已经保存的数据</p>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">找到事实，也找到它的来源。</h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-slate-300">
              每条结果都来自你的数据资产，并保留来源、采集时间和原始证据。
            </p>
          </div>

          <form onSubmit={handleSubmit} className="mt-8 rounded-2xl bg-white p-2 shadow-2xl shadow-slate-950/30" role="search">
            <div className="flex flex-col gap-2 md:flex-row">
              <label htmlFor="search-query" className="sr-only">搜索我的数据</label>
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-4 top-3.5 h-5 w-5 text-slate-400" aria-hidden="true" />
                <input
                  id="search-query"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="输入公司、主题、公告或事件"
                  className="min-h-12 w-full rounded-xl border-0 bg-white pl-12 pr-4 text-base text-slate-950 outline-none placeholder:text-slate-400 focus:ring-2 focus:ring-cyan-500"
                />
              </div>
              <label htmlFor="search-source" className="sr-only">筛选来源</label>
              <select
                id="search-source"
                value={sourceId}
                onChange={(event) => setSourceId(event.target.value)}
                className="min-h-12 rounded-xl border border-slate-200 bg-slate-50 px-4 text-base text-slate-700 outline-none focus:border-cyan-600 focus:ring-2 focus:ring-cyan-100 md:w-52"
              >
                <option value="">全部来源</option>
                {sources.map((source) => (
                  <option key={source.source_id} value={source.source_id}>{source.source_name}</option>
                ))}
              </select>
              <button
                type="submit"
                disabled={loading}
                className="inline-flex min-h-12 items-center justify-center rounded-xl bg-cyan-400 px-7 font-semibold text-slate-950 transition hover:bg-cyan-300 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-cyan-200 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? '正在搜索…' : '搜索'}
              </button>
            </div>
          </form>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
        {error && (
          <div className="mb-6 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800" role="alert">{error}</div>
        )}

        {!searched ? (
          <div className="grid gap-5 lg:grid-cols-[1.35fr_0.65fr]">
            <div className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8">
              <div className="flex items-start gap-4">
                <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-cyan-50 text-cyan-700">
                  <ShieldCheck className="h-5 w-5" aria-hidden="true" />
                </span>
                <div>
                  <h2 className="text-xl font-semibold text-slate-950">
                    {status?.active_documents ? '你的资料库已经可以搜索' : '资料库正在建立'}
                  </h2>
                  <p className="mt-2 leading-7 text-slate-600">
                    {status?.active_documents
                      ? `当前有 ${status.active_documents} 份可搜索文档，每份文档都能回到已保存的原始证据。`
                      : '采集器会从已登记来源持续保存数据。这里不会用演示内容伪装结果。'}
                  </p>
                  <Link href="/data" className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-lg font-medium text-cyan-700 hover:text-cyan-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-600">
                    查看数据资产 <ArrowRight className="h-4 w-4" aria-hidden="true" />
                  </Link>
                </div>
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-6">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-sm text-slate-500">采集状态</div>
                  <div className="mt-1 font-semibold text-slate-950">{collectorLabel(status?.collector.state)}</div>
                </div>
                <span className={`h-3 w-3 rounded-full ${status?.collector.state === 'degraded' ? 'bg-amber-500' : 'bg-emerald-500'}`} />
              </div>
              <dl className="mt-6 grid grid-cols-2 gap-4 border-t border-slate-100 pt-5">
                <div><dt className="text-xs text-slate-500">登记来源</dt><dd className="mt-1 text-2xl font-semibold">{status?.registered_sources ?? '—'}</dd></div>
                <div><dt className="text-xs text-slate-500">原始证据</dt><dd className="mt-1 text-2xl font-semibold">{status?.raw_objects ?? '—'}</dd></div>
              </dl>
            </div>
          </div>
        ) : loading && !results ? (
          <div className="py-20 text-center" role="status"><div className="mx-auto mb-4 h-9 w-9 animate-spin rounded-full border-2 border-cyan-600 border-t-transparent" /><p className="text-slate-600">正在检索已保存的数据</p></div>
        ) : results && results.documents.length > 0 ? (
          <>
            <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div><h2 className="text-xl font-semibold text-slate-950">搜索结果</h2><p className="mt-1 text-sm text-slate-500">找到 {results.total} 条结果 · {results.took} 毫秒</p></div>
              <div className="text-sm text-slate-500">第 {page} / {totalPages} 页</div>
            </div>
            <div className="space-y-4">
              {results.documents.map((document) => (
                <article key={document.id} className="rounded-2xl border border-slate-200 bg-white p-5 transition hover:border-slate-300 hover:shadow-sm sm:p-6">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-slate-500">
                    <span className="rounded-full bg-cyan-50 px-2.5 py-1 font-medium text-cyan-800">{sourceNames.get(document.source_id || '') || document.source}</span>
                    <span className="inline-flex items-center gap-1.5"><Clock3 className="h-3.5 w-3.5" aria-hidden="true" />{formatTime(document.publish_date)}</span>
                  </div>
                  <h3 className="mt-4 text-lg font-semibold leading-7 text-slate-950">{document.title}</h3>
                  <p className="mt-2 line-clamp-3 text-sm leading-7 text-slate-600">{document.content}</p>
                  <div className="mt-5 flex flex-wrap gap-4 text-sm font-medium">
                    {document.raw_object_id && (
                      <a href={dataAssetApi.evidenceContentUrl(document.raw_object_id)} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center gap-2 text-cyan-700 hover:text-cyan-900">
                        查看归档证据 <ShieldCheck className="h-4 w-4" aria-hidden="true" />
                      </a>
                    )}
                    {document.url && (
                      <a href={document.url} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center gap-2 text-slate-600 hover:text-slate-950">
                        打开原始来源 <ExternalLink className="h-4 w-4" aria-hidden="true" />
                      </a>
                    )}
                  </div>
                </article>
              ))}
            </div>
            {totalPages > 1 && (
              <div className="mt-7 flex items-center justify-between">
                <button type="button" disabled={page <= 1 || loading} onClick={() => performSearch(query, sourceId, page - 1)} className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium disabled:opacity-40"><ArrowLeft className="h-4 w-4" />上一页</button>
                <button type="button" disabled={page >= totalPages || loading} onClick={() => performSearch(query, sourceId, page + 1)} className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium disabled:opacity-40">下一页<ArrowRight className="h-4 w-4" /></button>
              </div>
            )}
          </>
        ) : searched && !error ? (
          <div className="rounded-2xl border border-slate-200 bg-white px-6 py-14 text-center">
            <FileSearch className="mx-auto h-9 w-9 text-slate-400" aria-hidden="true" />
            <h2 className="mt-4 text-xl font-semibold text-slate-950">没有找到匹配内容</h2>
            <p className="mx-auto mt-2 max-w-lg leading-7 text-slate-600">换一个更短的关键词，或取消来源筛选。资料库只返回已经采集并保存的真实内容。</p>
          </div>
        ) : null}
      </section>
    </Layout>
  );
};

export default HomePage;
