import React, { useEffect, useState } from 'react';
import { devManagerApi, ServiceInfo } from '@/services/devManager';
import { Layout } from '@/components/Layout';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';

const DevConsolePage: React.FC = () => {
  const [services, setServices] = useState<ServiceInfo[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [offset, setOffset] = useState<number>(0);
  const [profiles, setProfiles] = useState<Record<string, string[]>>({});
  const [token, setToken] = useState<string>('');

  const refresh = async () => {
    setLoading(true);
    try {
      const list = await devManagerApi.list();
      setServices(list);
      const pf = await devManagerApi.listProfiles();
      setProfiles(pf || {});
      if (selected) {
        const page = await devManagerApi.logsPaged(selected, offset, 200);
        setLogs(page.lines || []);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, [selected]);

  const onStart = async (name: string) => { await devManagerApi.start(name); refresh(); };
  const onStop = async (name: string) => { await devManagerApi.stop(name); refresh(); };
  const onRestart = async (name: string) => { await devManagerApi.restart(name); refresh(); };
  const onDownloadLog = async (name: string) => { window.open(devManagerApi.downloadLogUrl(name), '_blank'); };
  const onApplyProfile = async (name: string, stopOthers = false) => { await devManagerApi.applyProfile(name, stopOthers); refresh(); };
  const onKillPort = async (port: number) => { await devManagerApi.killPort(port, token || undefined); refresh(); };

  return (
    <Layout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">Dev Manager 控制台</h1>
          <Button onClick={refresh} disabled={loading}>刷新</Button>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-600">管理令牌</label>
          <input value={token} onChange={e=>setToken(e.target.value)} className="border rounded px-2 py-1 text-sm" placeholder="可选：DEVMAN_TOKEN" />
          <div className="ml-auto flex items-center gap-2">
            <span className="text-sm text-gray-600">Profiles:</span>
            {Object.keys(profiles).map(name => (
              <Button key={name} onClick={()=>onApplyProfile(name, true)} variant="ghost">{name}</Button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {services.map(s => (
            <Card key={s.id}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium">{s.name}</div>
                  <div className="text-sm">
                    <span className={s.running? 'text-green-600':'text-gray-500'}>{s.running ? `运行中 PID=${s.pid}` : '未运行'}</span>
                    {typeof (s as any).healthy !== 'undefined' && (
                      <span className={(s as any).healthy? 'text-green-600 ml-2':'text-red-600 ml-2'}>
                        {(s as any).healthy? '健康' : '不健康'}
                        {(s as any).latency_ms? ` ${(s as any).latency_ms}ms`: ''}
                      </span>
                    )}
                  </div>
                </div>
                <div className="space-x-2">
                  {!s.running && <Button onClick={() => onStart(s.id)}>Start</Button>}
                  {s.running && <Button onClick={() => onStop(s.id)} variant="secondary">Stop</Button>}
                  <Button onClick={() => onRestart(s.id)} variant="ghost">Restart</Button>
                </div>
              </div>
              <div className="mt-3 flex items-center gap-2">
                <Button onClick={() => setSelected(s.id)} variant={selected===s.id? 'secondary':'ghost'}>查看日志</Button>
                <Button onClick={() => onDownloadLog(s.id)} variant="ghost">下载日志</Button>
              </div>
            </Card>
          ))}
        </div>
        {selected && (
          <Card>
            <div className="flex items-center justify-between mb-2">
              <div className="font-medium">日志 - {selected}</div>
              <div className="flex items-center gap-2">
                <Button onClick={() => setOffset(Math.max(0, offset - 200))} variant="ghost">上一页</Button>
                <Button onClick={() => setOffset(offset + 200)} variant="ghost">下一页</Button>
                <Button onClick={() => setSelected(null)} variant="ghost">关闭</Button>
              </div>
            </div>
            <pre className="bg-black text-green-200 p-3 rounded max-h-[480px] overflow-auto text-sm">
{logs.join('\n')}
            </pre>
          </Card>
        )}
      </div>
    </Layout>
  );
};

export default DevConsolePage;

