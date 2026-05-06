import path from "path";
import { fileURLToPath } from "url";
import type { NextConfig } from "next";

/** Directory containing this config (the `frontend` app root). */
const appRoot = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Stops Next from walking up the tree and picking an unrelated lockfile as the workspace root (can affect tracing).
  outputFileTracingRoot: appRoot,
  experimental: {
    // Avoids dev-only "SegmentViewNode" / React Client Manifest errors from the App Router segment explorer (Next 15.5+).
    devtoolSegmentExplorer: false,
  },
};

export default nextConfig;
