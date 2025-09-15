import React from 'react';
import type { AppProps } from 'next/app';
import { AuthProvider } from '@/components/auth/AuthContext';
import '@/styles/globals.css';

export default function App({ Component, pageProps }: AppProps) {
  return (
    <AuthProvider>
      <div className="app-container">
        <Component {...pageProps} />
      </div>
    </AuthProvider>
  );
}
