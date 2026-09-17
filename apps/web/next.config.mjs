/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // `three` is client-only and heavy — keep it out of the server bundle.
  //
  // `lucide-react` is transpiled for a different reason: its published CJS build
  // (which Next renders on the server) and its ESM build (which the browser
  // runs) derive the icon's `class` attribute from different alias data. `Home`
  // arrives as `lucide lucide-house` from one and `lucide lucide-house
  // lucide-home` from the other, and React reports a hydration mismatch on an
  // attribute neither we nor the icon's consumer controls. Compiling the package
  // from its ESM source for BOTH environments gives the server and the client
  // the same markup — the actual fix, where suppressing the warning would only
  // hide it.
  // NOTE: `experimental.optimizePackageImports` for `@react-three/drei` was tried
  // here and measured as a no-op — the heavy chunk on the home route is three.js
  // core (676 KB), not drei's barrel, whose transmission material is its own
  // 28 KB chunk. Left out rather than kept as cargo-cult config.
  transpilePackages: ["three", "lucide-react"],
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
