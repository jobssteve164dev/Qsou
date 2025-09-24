import axios from 'axios';

type ServiceInfo = {
  id: string;
  name: string;
  running: boolean;
  pid?: number;
};

const devClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_DEVMAN_URL || 'http://localhost:5500',
  timeout: 20000,
  headers: { 'Content-Type': 'application/json' },
});

export const devManagerApi = {
  list: async (): Promise<ServiceInfo[]> => {
    const res = await devClient.get('/services');
    return res.data as ServiceInfo[];
  },
  listProfiles: async (): Promise<Record<string, string[]>> => {
    const res = await devClient.get('/profiles');
    return res.data as Record<string, string[]>;
  },
  start: async (name: string): Promise<{ result: string; pid?: number }> => {
    const res = await devClient.post('/services/start', { name });
    return res.data;
  },
  stop: async (name: string): Promise<{ result: string }> => {
    const res = await devClient.post('/services/stop', { name });
    return res.data;
  },
  restart: async (name: string): Promise<{ result: string; pid?: number }> => {
    const res = await devClient.post('/services/restart', { name });
    return res.data;
  },
  logs: async (name: string, lines = 200): Promise<string[]> => {
    const res = await devClient.get(`/services/${encodeURIComponent(name)}/logs`, { params: { lines } });
    return (res.data?.lines ?? []) as string[];
  },
  logsPaged: async (name: string, offset = 0, limit = 200): Promise<{ total: number; lines: string[] }> => {
    const res = await devClient.get(`/services/${encodeURIComponent(name)}/logs/paged`, { params: { offset, limit } });
    return res.data as { total: number; lines: string[] };
  },
  downloadLogUrl: (name: string) => `${process.env.NEXT_PUBLIC_DEVMAN_URL || 'http://localhost:5500'}/services/${encodeURIComponent(name)}/logs/download`,
  applyProfile: async (name: string, stopOthers = false): Promise<{ result: string }> => {
    const res = await devClient.post('/profiles/apply', { name, stop_others: stopOthers });
    return res.data;
  },
  killPort: async (port: number, token?: string): Promise<{ result: string; pid?: number }> => {
    const res = await devClient.post('/diagnose/kill_port', { port, token });
    return res.data;
  },
};

export type { ServiceInfo };


