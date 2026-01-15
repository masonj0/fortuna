/** @type {import('next').NextConfig} */
const nextConfig = {
  // CRITICAL: Enable static export
  output: 'export',

  // Disable image optimization for static export
  images: {
    unoptimized: true,
  },

  // Base path if needed
  basePath: '',

  // Trailing slashes
  trailingSlash: true,
}

module.exports = nextConfig