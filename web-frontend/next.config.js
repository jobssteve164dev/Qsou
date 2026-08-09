/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  output: 'standalone',
  async redirects() {
    return [
      { source: '/intelligence/:path*', destination: '/', permanent: false },
      { source: '/monitor/:path*', destination: '/data', permanent: false },
      { source: '/403', destination: '/', permanent: false },
    ]
  },
}

module.exports = nextConfig
