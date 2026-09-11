/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The 3D scene is client-only and heavy — keep it out of the main bundle.
  transpilePackages: ["three"],
  env: {
    // DATA MODE — "live" is the only supported mode for demos and production.
    //
    //   live (default)  talks to the FastAPI backend at NEXT_PUBLIC_API_BASE.
    //                   If the backend is unreachable the app shows a hard
    //                   connectivity error; it never substitutes fake data.
    //   mock            runs the in-browser engine. Development only, and it
    //                   must be selected explicitly by setting
    //                   NEXT_PUBLIC_DATA_MODE=mock. Nothing falls back to it.
    NEXT_PUBLIC_DATA_MODE: process.env.NEXT_PUBLIC_DATA_MODE ?? "live",
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000",
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL ?? "ws://127.0.0.1:8000/api/jobs/ws",
  },
};

export default nextConfig;
