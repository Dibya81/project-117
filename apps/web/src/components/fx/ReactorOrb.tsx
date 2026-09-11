"use client";

/**
 * ReactorOrb — lazy host for the WebGL reactor core.
 * SSR-disabled dynamic import; a pure-CSS fallback orb holds the space while
 * the chunk loads (and permanently if WebGL is unavailable).
 */
import dynamic from "next/dynamic";

const Scene = dynamic(() => import("./ReactorCoreScene"), {
  ssr: false,
  loading: () => <div className="fx-orb-fallback" aria-hidden="true" />,
});

export function ReactorOrb({
  size = "hero",
  className,
}: {
  size?: "hero" | "compact";
  className?: string;
}) {
  return (
    <div
      className={`fx-orb fx-orb--${size}${className ? ` ${className}` : ""}`}
      role="img"
      aria-label="Project 117 reactor core — a contained sphere of energy"
    >
      <Scene dpr={size === "hero" ? 1.75 : 1.25} />
      <style jsx>{`
        .fx-orb {
          position: relative;
          width: 100%;
          height: 100%;
          min-height: 220px;
        }
        .fx-orb--compact {
          min-height: 190px;
        }
        .fx-orb :global(canvas) {
          outline: none;
        }
        .fx-orb-fallback {
          position: absolute;
          inset: 0;
          display: grid;
          place-items: center;
        }
        .fx-orb-fallback::before {
          content: "";
          width: 34%;
          aspect-ratio: 1;
          border-radius: 50%;
          background: radial-gradient(circle at 38% 34%, rgba(69, 213, 255, 0.75), rgba(69, 213, 255, 0.08) 58%, transparent 72%);
          box-shadow: 0 0 60px rgba(69, 213, 255, 0.3);
          animation: p117-float-y 5s ease-in-out infinite;
        }
      `}</style>
    </div>
  );
}
