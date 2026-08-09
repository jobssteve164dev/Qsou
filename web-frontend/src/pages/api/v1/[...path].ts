import http from 'node:http';
import type { NextApiRequest, NextApiResponse } from 'next';

import { backendBaseUrl, isSameOriginRequest, readSessionToken } from '@/server/session';

export const config = {
  api: {
    responseLimit: false,
  },
};

export default function handler(request: NextApiRequest, response: NextApiResponse) {
  const token = readSessionToken(request);
  if (!token) {
    return response.status(401).json({ detail: '请先登录' });
  }
  if (!['GET', 'HEAD'].includes(request.method || '') && !isSameOriginRequest(request)) {
    return response.status(403).json({ detail: '请求来源不受信任' });
  }

  const base = new URL(backendBaseUrl());
  const body = ['GET', 'HEAD'].includes(request.method || '')
    ? undefined
    : Buffer.from(JSON.stringify(request.body ?? {}));

  const upstream = http.request(
    {
      protocol: base.protocol,
      hostname: base.hostname,
      port: base.port || 80,
      method: request.method,
      path: request.url,
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: request.headers.accept || '*/*',
        'Content-Type': request.headers['content-type'] || 'application/json',
        ...(body ? { 'Content-Length': body.byteLength } : {}),
        ...(request.headers['x-trace-id']
          ? { 'X-Trace-ID': String(request.headers['x-trace-id']) }
          : {}),
      },
    },
    (upstreamResponse) => {
      response.statusCode = upstreamResponse.statusCode || 502;
      for (const name of ['content-type', 'content-disposition', 'content-length', 'x-request-id']) {
        const value = upstreamResponse.headers[name];
        if (value !== undefined) response.setHeader(name, value);
      }
      upstreamResponse.pipe(response);
    },
  );

  upstream.on('error', () => {
    if (!response.headersSent) {
      response.status(502).json({ detail: '数据服务暂时不可用' });
    } else {
      response.end();
    }
  });
  request.on('aborted', () => upstream.destroy());
  if (body) upstream.write(body);
  upstream.end();
  return undefined;
}
