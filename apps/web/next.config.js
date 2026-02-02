/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
  webpack: (config, { isServer }) => {
    // Handle canvas for pdfjs-dist
    if (!isServer) {
      config.resolve.alias.canvas = false;
    }

    // Configure pdfjs-dist to work with Next.js
    config.resolve.alias = {
      ...config.resolve.alias,
      canvas: false,
      encoding: false,
    };

    return config;
  },
}

module.exports = nextConfig
