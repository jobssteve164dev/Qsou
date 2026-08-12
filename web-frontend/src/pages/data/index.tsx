import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import {
  Activity,
  ArrowRight,
  Clock3,
  Database,
  Download,
  ExternalLink,
  FileArchive,
  HardDrive,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';

import { Layout } from '@/components/Layout';
import { dataAssetApi } from '@/services/api';
import { DataAssetStatus, DataSourceStatus, EvidenceRecord } from '@/types';

const formatTime = (value?: string | null) => {
  if (!value) return '尚无记录';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN');
};

const formatBytes = (value: number) => {
  if (value < 1024) return `${value} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  const unitIndex = Math.min(Math.floor(Math.log(value) / Math.log(1024)) - 1, units.length - 1);
  return `${(value / 1024 ** (unitIndex + 1)).toFixed(unitIndex > 0 ? 1 : 0)} ${units[unitIndex]}`;
};

const collectorMessage = (collector?: DataAssetStatus['collector']) => {
  if (!collector) return { label: '正在读取', tone: 'bg-slate-200' };
  const map: Record<string, { label: string; tone: string }> = {
    starting: { label: '正在启动采集网络', tone: 'bg-cyan-500' },
    running: { label: '正在采集来源数据', tone: 'bg-cyan-500' },
    idle: { label: '运行正常，等待下一轮', tone: 'bg-emerald-500' },
    degraded: { label: '部分采集任务失败', tone: 'bg-amber-500' },
    not_started: { label: '等待采集器启动', tone: 'bg-slate-400' },
    stopping: { label: '采集器正在停止', tone: 'bg-amber-500' },
    disabled: { label: '采集器未启用', tone: 'bg-slate-400' },
    unknown: { label: '采集状态暂不可用', tone: 'bg-rose-500' },
  };
  return map[collector.state] || map.unknown;
};

const sourceState = (source: DataSourceStatus) => {
  const states: Record<DataSourceStatus['collection_state'], { label: string; tone: string; description: string }> = {
    healthy: { label: '详情入库正常', tone: 'bg-emerald-50 text-emerald-800', description: '最近一轮完整获取了全部已发现详情，并生成可搜索文档' },
    degraded: { label: '需要检查', tone: 'bg-amber-50 text-amber-800', description: '最近一轮存在详情获取或解析缺口，需要检查' },
    failed: { label: '采集失败', tone: 'bg-rose-50 text-rose-800', description: '最近一轮没有完成入口访问或解析' },
    queued: { label: '已排队', tone: 'bg-cyan-50 text-cyan-800', description: '已收到立即采集请求，采集器会按顺序处理' },
    running: { label: '正在采集', tone: 'bg-cyan-50 text-cyan-800', description: '当前正在运行这一来源的采集规则' },
    cancelled: { label: '已中止', tone: 'bg-slate-100 text-slate-700', description: '最近一轮采集被中止' },
    stale: { label: '数据已过期', tone: 'bg-amber-50 text-amber-800', description: '最近一次成功运行已经超过两倍采集周期' },
    authorization_required: { label: '待授权', tone: 'bg-violet-50 text-violet-800', description: '来源不允许通用自动采集，接入获授权的数据通道后才能运行' },
    disabled: { label: '未启用', tone: 'bg-slate-100 text-slate-600', description: '该来源当前不参与自动采集' },
    not_started: { label: '尚未运行', tone: 'bg-slate-100 text-slate-600', description: '来源已经登记，采集规则还没有完成首轮运行' },
  };
  return states[source.collection_state] || states.not_started;
};

const DataAssetsPage: React.FC = () => {
  const [status, setStatus] = useState<DataAssetStatus | null>(null);
  const [sources, setSources] = useState<DataSourceStatus[]>([]);
  const [evidence, setEvidence] = useState<EvidenceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const [statusResult, sourcesResult, evidenceResult] = await Promise.all([
      dataAssetApi.status(),
      dataAssetApi.sources(),
      dataAssetApi.evidence(30),
    ]);
    if (!statusResult.success || !statusResult.data) {
      setError(statusResult.error || '暂时无法读取数据资产');
    } else {
      setStatus(statusResult.data);
      setSources(sourcesResult.data?.sources || []);
      setEvidence(evidenceResult.data?.evidence || []);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const triggerSource = useCallback(async (sourceId: string) => {
    setTriggering(sourceId);
    setError(null);
    const result = await dataAssetApi.triggerSource(sourceId);
    if (!result.success) {
      setError(result.error || '暂时无法发起采集');
      setTriggering(null);
      return;
    }
    await load();
    setTriggering(null);
  }, [load]);

  const sourceNames = useMemo(
    () => new Map(sources.map((source) => [source.source_id, source.source_name])),
    [sources],
  );
  const collector = collectorMessage(status?.collector);

  return (
    <Layout>
      <Head>
        <title>数据资产 · QSou</title>
        <meta name="description" content="查看已经保存的来源、原始证据和可搜索文档" />
      </Head>

      <section className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8 sm:flex-row sm:items-end sm:justify-between sm:px-6 lg:px-8">
          <div>
            <p className="mb-2 text-sm font-medium text-cyan-700">数据资产</p>
            <h1 className="text-3xl font-semibold tracking-tight text-slate-950">我真正掌握了什么</h1>
            <p className="mt-3 max-w-2xl leading-7 text-slate-600">查看来源、采集状态、原始证据和文档版本。数字只来自实际保存的数据。</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button type="button" onClick={load} disabled={loading} className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 text-sm font-medium text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-600 disabled:opacity-50">
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />刷新
            </button>
            <a href={dataAssetApi.exportUrl()} className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-cyan-200">
              <Download className="h-4 w-4" aria-hidden="true" />导出 JSONL
            </a>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl space-y-6 px-4 py-8 sm:px-6 lg:px-8">
        {error ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-5 py-4 text-rose-800" role="alert">
            <p className="font-medium">无法读取数据资产</p><p className="mt-1 text-sm">{error}</p>
          </div>
        ) : loading && !status ? (
          <div className="py-20 text-center" role="status"><div className="mx-auto mb-4 h-9 w-9 animate-spin rounded-full border-2 border-cyan-600 border-t-transparent" /><p className="text-slate-600">正在读取数据资产</p></div>
        ) : status ? (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              {[
                { label: '登记来源', value: status.registered_sources, icon: ShieldCheck },
                { label: '原始证据', value: status.raw_objects, icon: FileArchive },
                { label: '可搜索文档', value: status.active_documents, icon: Database },
                { label: '保留版本', value: status.document_versions, icon: Clock3 },
                { label: '存档大小', value: formatBytes(status.archive_size_bytes), icon: HardDrive },
              ].map((item) => (
                <div key={item.label} className="rounded-2xl border border-slate-200 bg-white p-5">
                  <div className="flex items-center justify-between"><span className="text-sm text-slate-500">{item.label}</span><item.icon className="h-5 w-5 text-slate-400" aria-hidden="true" /></div>
                  <div className="mt-4 text-3xl font-semibold tabular-nums text-slate-950">{item.value}</div>
                </div>
              ))}
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
              <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-3">
                  <span className={`mt-1 h-3 w-3 shrink-0 rounded-full ${collector.tone}`} />
                  <div><h2 className="font-semibold text-slate-950">{collector.label}</h2><p className="mt-1 text-sm text-slate-500">采集是持续任务；失败状态不会被伪装成“没有新数据”。</p></div>
                </div>
                <dl className="grid grid-cols-2 gap-x-8 gap-y-3 text-sm sm:text-right">
                  <div><dt className="text-slate-500">最近完成</dt><dd className="mt-1 font-medium text-slate-800">{formatTime(status.collector.last_finished_at)}</dd></div>
                  <div><dt className="text-slate-500">下次检查</dt><dd className="mt-1 font-medium text-slate-800">{formatTime(status.collector.next_run_at)}</dd></div>
                </dl>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white">
              <div className="border-b border-slate-100 px-5 py-5 sm:px-6"><h2 className="text-lg font-semibold text-slate-950">情报来源网络</h2><p className="mt-1 text-sm text-slate-500">只有最近一轮完整获取已发现详情并生成文档，才会显示为正常。</p></div>
              <div className="grid gap-px bg-slate-100 sm:grid-cols-2 lg:grid-cols-3">
                {sources.map((source) => {
                  const state = sourceState(source);
                  return (
                    <article key={source.source_id} className="bg-white p-5 sm:p-6" title={state.description}>
                    <div className="flex items-start justify-between gap-4">
                      <div><h3 className="font-semibold text-slate-950">{source.source_name}</h3><p className="mt-1 text-xs text-slate-500">{source.authority_tier === 'primary' ? '一手来源' : source.authority_tier === 'secondary' ? '补充来源' : '线索来源'} · 采集规则 v{source.adapter_version}</p></div>
                      <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${state.tone}`}>{state.label}</span>
                    </div>
                    <p className="mt-3 min-h-10 text-sm leading-5 text-slate-600">{state.description}</p>
                    <dl className="mt-4 grid grid-cols-3 gap-3 border-t border-slate-100 pt-4 text-sm">
                      <div><dt className="text-xs text-slate-500">原始证据</dt><dd className="mt-1 font-semibold tabular-nums text-slate-950">{source.raw_count}</dd></div>
                      <div><dt className="text-xs text-slate-500">发现详情</dt><dd className="mt-1 font-semibold tabular-nums text-slate-950">{source.last_run?.detail_discovered ?? 0}</dd></div>
                      <div><dt className="text-xs text-slate-500">可搜索文档</dt><dd className="mt-1 font-semibold tabular-nums text-slate-950">{source.active_documents}</dd></div>
                    </dl>
                    <div className="mt-4 flex items-center justify-between gap-3 text-xs text-slate-500">
                      <span>{source.collection_state === 'running' ? '本轮开始' : '最近完成'}</span>
                      <span className="text-right text-slate-700">{formatTime(source.collection_state === 'running' ? source.last_run?.started_at : source.last_run?.finished_at)}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => triggerSource(source.source_id)}
                      disabled={!source.enabled || triggering === source.source_id || source.collection_state === 'queued' || source.collection_state === 'running'}
                      className="mt-4 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-4 text-sm font-medium text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-600 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <RefreshCw className={`h-4 w-4 ${triggering === source.source_id ? 'animate-spin' : ''}`} aria-hidden="true" />
                      {!source.enabled ? '需要授权通道' : source.collection_state === 'queued' ? '等待采集' : source.collection_state === 'running' ? '正在采集' : '立即采集'}
                    </button>
                    </article>
                  );
                })}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white">
              <div className="flex items-end justify-between border-b border-slate-100 px-5 py-5 sm:px-6"><div><h2 className="text-lg font-semibold text-slate-950">最近保存的证据</h2><p className="mt-1 text-sm text-slate-500">原始响应按内容标识保存，不用搜索索引替代证据。</p></div></div>
              {evidence.length === 0 ? (
                <div className="px-6 py-14 text-center">
                  <Activity className="mx-auto h-9 w-9 text-slate-400" aria-hidden="true" />
                  <h3 className="mt-4 font-semibold text-slate-950">还没有保存到原始证据</h3>
                  <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-slate-600">采集器完成首轮后，真实证据会出现在这里。系统不会填充演示数据。</p>
                </div>
              ) : (
                <div className="divide-y divide-slate-100">
                  {evidence.map((item) => (
                    <article key={item.raw_object_id} className="flex flex-col gap-4 px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
                      <div className="min-w-0"><div className="truncate font-medium text-slate-950">{item.url}</div><div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500"><span>{sourceNames.get(item.source_id) || item.source_id}</span><span>{formatTime(item.first_fetched_at)}</span><span>抓取 {item.fetch_count} 次</span></div></div>
                      <a href={dataAssetApi.evidenceContentUrl(item.raw_object_id)} target="_blank" rel="noreferrer" className="inline-flex min-h-11 shrink-0 items-center gap-2 font-medium text-cyan-700 hover:text-cyan-900">查看归档证据 <ExternalLink className="h-4 w-4" aria-hidden="true" /></a>
                    </article>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded-2xl bg-slate-950 p-6 text-white sm:flex sm:items-center sm:justify-between">
              <div><h2 className="font-semibold">现在去搜索已保存的数据</h2><p className="mt-1 text-sm text-slate-400">搜索结果只来自上面的可搜索文档。</p></div>
              <Link href="/" className="mt-4 inline-flex min-h-11 items-center gap-2 font-medium text-cyan-300 hover:text-cyan-200 sm:mt-0">开始搜索 <ArrowRight className="h-4 w-4" /></Link>
            </div>
          </>
        ) : null}
      </section>
    </Layout>
  );
};

export default DataAssetsPage;
