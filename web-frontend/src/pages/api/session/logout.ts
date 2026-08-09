import type { NextApiRequest, NextApiResponse } from 'next';

import { clearSessionCookie, isSameOriginRequest } from '@/server/session';

export default function handler(request: NextApiRequest, response: NextApiResponse) {
  if (request.method !== 'POST') {
    response.setHeader('Allow', 'POST');
    return response.status(405).json({ error: 'Method not allowed' });
  }
  if (!isSameOriginRequest(request)) {
    return response.status(403).json({ error: '请求来源不受信任' });
  }
  clearSessionCookie(response);
  return response.status(204).end();
}
