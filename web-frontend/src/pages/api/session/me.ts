import type { NextApiRequest, NextApiResponse } from 'next';

import {
  backendBaseUrl,
  clearSessionCookie,
  readSessionToken,
} from '@/server/session';

export default async function handler(request: NextApiRequest, response: NextApiResponse) {
  if (request.method !== 'GET') {
    response.setHeader('Allow', 'GET');
    return response.status(405).json({ error: 'Method not allowed' });
  }

  const token = readSessionToken(request);
  if (!token) {
    return response.status(200).json({ user: null });
  }

  try {
    const upstream = await fetch(`${backendBaseUrl()}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!upstream.ok) {
      clearSessionCookie(response);
      return response.status(200).json({ user: null });
    }
    return response.status(200).json({ user: await upstream.json() });
  } catch {
    return response.status(502).json({ error: '暂时无法验证登录状态' });
  }
}
