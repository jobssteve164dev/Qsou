const apiInternalUrl = (process.env.API_INTERNAL_URL || 'http://localhost:8888').replace(/\/$/, '')

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: `${apiInternalUrl}/api/v1/:path*`,
      },
    ]
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8888/api/v1',
    // 开发环境静默登录开关（默认开启）。如需关闭，设置为 'false'
    NEXT_PUBLIC_ENABLE_DEV_SILENT_LOGIN: process.env.NEXT_PUBLIC_ENABLE_DEV_SILENT_LOGIN || 'true',
  },
}

module.exports = nextConfig
