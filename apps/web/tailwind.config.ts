import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#0b0f14",
        panel: "#111720",
        raised: "#161e29",
        line: "#1f2a38",
        ink: {
          1: "#e6edf4",
          2: "#9fb0c3",
          3: "#5c6b7e",
        },
        accent: { DEFAULT: "#38bdf8", dim: "#0c4a6e" },
        warn: "#f59e0b",
        crit: "#ef4444",
        ok: "#34d399",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: { DEFAULT: "4px", panel: "8px" },
      animation: {
        "pulse-soft": "pulseSoft 2.4s ease-in-out infinite",
        "trace-in": "traceIn 240ms ease-out both",
      },
      keyframes: {
        pulseSoft: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.45" },
        },
        traceIn: {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
export default config;
