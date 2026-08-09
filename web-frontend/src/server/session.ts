import type { IncomingMessage, ServerResponse } from 'node:http';

const COOKIE_NAME = 'qsou_session';
const SESSION_MAX_AGE = 24 * 60 * 60;

export const backendBaseUrl = () =>
  (process.env.API_INTERNAL_URL || 'http://api:8000').replace(/\/$/, '');

export const readSessionToken = (request: IncomingMessage): string | null => {
  const cookies = request.headers.cookie?.split(';') || [];
  for (const cookie of cookies) {
    const [name, ...value] = cookie.trim().split('=');
    if (name === COOKIE_NAME) {
      return decodeURIComponent(value.join('='));
    }
  }
  return null;
};

export const setSessionCookie = (response: ServerResponse, token: string) => {
  const secure = process.env.NODE_ENV === 'production' ? '; Secure' : '';
  response.setHeader(
    'Set-Cookie',
    `${COOKIE_NAME}=${encodeURIComponent(token)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${SESSION_MAX_AGE}${secure}`,
  );
};

export const clearSessionCookie = (response: ServerResponse) => {
  const secure = process.env.NODE_ENV === 'production' ? '; Secure' : '';
  response.setHeader(
    'Set-Cookie',
    `${COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0${secure}`,
  );
};

export const isSameOriginRequest = (request: IncomingMessage) => {
  const origin = request.headers.origin;
  if (!origin) return true;
  try {
    return new URL(origin).host === request.headers.host;
  } catch {
    return false;
  }
};
