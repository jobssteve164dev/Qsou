import type { NextApiRequest, NextApiResponse } from 'next';

import { backendBaseUrl, isSameOriginRequest, setSessionCookie } from '@/server/session';

export default async function handler(request: NextApiRequest, response: NextApiResponse) {
  if (request.method !== 'POST') {
    response.setHeader('Allow', 'POST');
    return response.status(405).json({ error: 'Method not allowed' });
  }
  if (!isSameOriginRequest(request)) {
    return response.status(403).json({ error: '请求来源不受信任' });
  }

  const username = typeof request.body?.username === 'string' ? request.body.username.trim() : '';
  const password = typeof request.body?.password === 'string' ? request.body.password : '';
  if (!username || !password) {
    return response.status(400).json({ error: '请输入用户名和密码' });
  }

  try {
    const upstream = await fetch(`${backendBaseUrl()}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!upstream.ok) {
      return response.status(upstream.status === 401 ? 401 : 502).json({
        error: upstream.status === 401 ? '用户名或密码不正确' : '登录服务暂时不可用',
      });
    }

    const payload = await upstream.json();
    if (!payload?.token || !payload?.user) {
      return response.status(502).json({ error: '登录服务返回了无效响应' });
    }
    setSessionCookie(response, payload.token);
    return response.status(200).json({ user: payload.user });
  } catch {
    return response.status(502).json({ error: '暂时无法连接登录服务，请稍后重试' });
  }
}
