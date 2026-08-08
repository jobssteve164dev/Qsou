import React, { useCallback, useEffect, useState } from 'react';
import Head from 'next/head';
import { Database, Download, ExternalLink, RefreshCw, ShieldCheck } from 'lucide-react';

import { Layout } from '@/components/Layout';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Loading } from '@/components/ui/Loading';
import { dataAssetApi } from '@/services/api';
import { DataAssetStatus, DataSourceStatus, EvidenceRecord } from '@/types';


const formatTime = (value?: string | null) => {
  if (!value) return '等待首次采集';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN');
};


const DataAssetsPage: React.FC = () => {
  const [status, setStatus] = useState<DataAssetStatus | null>(null);
  const [sources, setSources] = useState<DataSourceStatus[]>([]);
  const [evidence, setEvidence] = useState<EvidenceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const [statusResponse, sourcesResponse, evidenceResponse] = await Promise.all([
      dataAssetApi.status(),
      dataAssetApi.sources(),
      dataAssetApi.evidence(20),
    ]);

    if (!statusResponse.success || !statusResponse.data) {
      setError(statusResponse.error || '暂时无法读取数据资产状态');
    } else {
      setStatus(statusResponse.data);
      setSources(sourcesResponse.data?.sources || []);
      setEvidence(evidenceResponse.data?.evidence || []);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Layout>
      <Head>
        <title>我的数据 - QSou</title>
        <meta name="description" content="查看 QSou 已经保存的来源、文档和原始证据" />
      </Head>

      <div className="min-h-screen bg-gray-50">
        <div className="border-b border-gray-200 bg-white">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-7 sm:px-6 lg:px-8">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">我的数据</h1>
              <p className="mt-1 text-sm text-gray-600">查看已经掌握的来源、历史证据和可搜索文档</p>
            </div>
            <div className="flex gap-3">
              <Button variant="outline" onClick={load} disabled={loading}>
                <RefreshCw className="mr-2 h-4 w-4" />刷新
              </Button>
              <a href={dataAssetApi.exportUrl()}>
                <Button>
                  <Download className="mr-2 h-4 w-4" />导出全部数据
                </Button>
              </a>
            </div>
          </div>
        </div>

        <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
          {loading && !status ? (
            <Loading size="lg" text="正在读取我的数据…" />
          ) : error ? (
            <Card className="border-red-200 bg-red-50">
              <CardContent className="py-8 text-center text-red-700">{error}</CardContent>
            </Card>
          ) : status ? (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  ['持续来源', status.registered_sources],
                  ['原始证据', status.raw_objects],
                  ['可搜索文档', status.active_documents],
                  ['历史版本', status.document_versions],
                ].map(([label, value]) => (
                  <Card key={label}>
                    <CardContent className="py-6">
                      <div className="text-3xl font-bold text-gray-900">{value}</div>
                      <div className="mt-1 text-sm text-gray-500">{label}</div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <ShieldCheck className="h-5 w-5 text-primary-600" />来源覆盖
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200 text-sm">
                      <thead>
                        <tr className="text-left text-gray-500">
                          <th className="pb-3 font-medium">来源</th>
                          <th className="pb-3 font-medium">性质</th>
                          <th className="pb-3 font-medium">已保存证据</th>
                          <th className="pb-3 font-medium">最近采集</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {sources.map((source) => (
                          <tr key={source.source_id}>
                            <td className="py-3 font-medium text-gray-900">{source.source_name}</td>
                            <td className="py-3 text-gray-600">
                              {source.authority_tier === 'primary' ? '一手来源' : '补充来源'}
                            </td>
                            <td className="py-3 text-gray-600">{source.raw_count}</td>
                            <td className="py-3 text-gray-600">{formatTime(source.last_fetched_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Database className="h-5 w-5 text-primary-600" />最近保存的证据
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {evidence.length === 0 ? (
                    <div className="py-8 text-center text-sm text-gray-500">尚未采集数据。运行采集器后，证据会出现在这里。</div>
                  ) : (
                    <div className="divide-y divide-gray-100">
                      {evidence.map((item) => (
                        <div key={item.raw_object_id} className="flex items-center justify-between gap-4 py-4">
                          <div className="min-w-0">
                            <div className="truncate font-medium text-gray-900">{item.url}</div>
                            <div className="mt-1 text-sm text-gray-500">
                              {sources.find((source) => source.source_id === item.source_id)?.source_name || item.source_id}
                              {' · '}{formatTime(item.first_fetched_at)}
                            </div>
                          </div>
                          <a
                            href={dataAssetApi.evidenceContentUrl(item.raw_object_id)}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex shrink-0 items-center text-sm font-medium text-primary-600 hover:text-primary-700"
                          >
                            查看证据<ExternalLink className="ml-1 h-4 w-4" />
                          </a>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          ) : null}
        </div>
      </div>
    </Layout>
  );
};

export default DataAssetsPage;
