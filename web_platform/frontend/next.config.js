/** @type {import('next').NextConfig} */
const nextConfig = {
  // CRITICAL for monolith: export as static site
  output: 'export',
  distDir: 'out',

  // Images cannot be optimized in static export
  images: {
    unoptimized: true,
  },

  // Trailing slashes for proper static file serving
  trailingSlash: true,

  // No custom base path (served from root)
  basePath: '',

  // Experimental optimizations
  experimental: {
    optimizePackageImports: ['@radix-ui/react-icons'],
  },
}

module.exports = nextConfig
