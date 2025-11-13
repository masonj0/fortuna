/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',  // Critical for static HTML export
  distDir: 'out',
  trailingSlash: true,
  images: {
    unoptimized: true  // Required for static export
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8000/api/:path*',
      },
    ]
  },
};

export default nextConfig;
