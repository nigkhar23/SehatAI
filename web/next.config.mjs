/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export: the demo renders entirely from bundled engine snapshots
  // (web/lib/data/*). A dead backend link can never break the card — the live
  // FastAPI URL is an optional enhancement (NEXT_PUBLIC_API_BASE), not a hard dep.
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;
