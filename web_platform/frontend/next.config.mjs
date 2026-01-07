/** @type {import('next').NextConfig} */
const nextConfig = {
  // CRITICAL: Export as static HTML
  output: 'export',

  // Export to 'out' directory
  distDir: 'out',

  // Disable image optimization (doesn't work in static export)
  images: {
    unoptimized: true,
  },

  // Ensure trailing slashes work
  trailingSlash: true,

  // Base path (none for monolith)
  basePath: '',

  // Asset prefix (none for monolith)
  assetPrefix: '',

  // API proxy for development (not used in monolith)
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
