import React from 'react';
import type { AppProps } from 'next/app';
import Head from 'next/head';
import { AuthBoundary, AuthProvider } from '@/components/auth/AuthContext';
import '@/styles/globals.css';

export default function App({ Component, pageProps }: AppProps) {
  const isPublicPage = Component.displayName === 'PublicPage';
  return (
    <AuthProvider>
      <Head>
        <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
      </Head>
      {isPublicPage ? <Component {...pageProps} /> : <AuthBoundary><Component {...pageProps} /></AuthBoundary>}
    </AuthProvider>
  );
}
