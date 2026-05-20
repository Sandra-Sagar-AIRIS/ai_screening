import path from "path";
import { fileURLToPath } from "url";
import type { NextConfig } from "next";

/** Directory containing this config (the `frontend` app root). */
const appRoot = path.dirname(fileURLToPath(import.meta.url));

const apiBackend =
  process.env.API_BACKEND_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // livekit-client ships as ESM — Next.js must transpile it for Webpack.
  transpilePackages: ["livekit-client"],
  // Stops Next from walking up the tree and picking an unrelated lockfile as the workspace root (can affect tracing).
  outputFileTracingRoot: appRoot,
  experimental: {
    // Avoids dev-only "SegmentViewNode" / React Client Manifest errors from the App Router segment explorer (Next 15.5+).
    devtoolSegmentExplorer: false,
  },
  async headers() {
    return [
      {
        // Tell browsers never to cache HTML pages.
        // _next/static/* assets are served with immutable content-hash URLs
        // and are NOT matched here — they keep their long-lived cache headers.
        // Without this, a clean rebuild (new CSS hash) + cached HTML = no CSS.
        source: "/((?!_next/static|_next/image|favicon.ico).*)",
        headers: [
          {
            key: "Cache-Control",
            value: "no-store",
          },
        ],
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiBackend}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
