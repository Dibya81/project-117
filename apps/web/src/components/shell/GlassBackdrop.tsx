"use client";

/**
 * GlassBackdrop — the console's living ice-blue field.
 *
 * Replaces the dark cinematic `Aurora` inside the shell. Three slow, very low
 * contrast radial fields drift behind everything (transform-only, so it stays
 * on the compositor), over the `#F0F7FF → #E6EFFC` base the spec names. It is
 * `position: fixed` and `pointer-events: none`, so no page has to reserve space
 * for it and nothing can intercept a click.
 *
 * Deliberately NOT animated with Framer Motion: a full-viewport animation
 * driven by React state would re-render the tree every frame. This is CSS
 * keyframes on transform only.
 */
export function GlassBackdrop() {
  return (
    <div
      aria-hidden="true"
      data-testid="glass-backdrop"
      className="pointer-events-none fixed inset-0 z-0 overflow-hidden"
      style={{
        background: "linear-gradient(160deg, #F0F7FF 0%, #EAF3FD 45%, #E6EFFC 100%)",
      }}
    >
      {/* Cyan field, top-left. */}
      <div
        className="absolute -left-[18vmax] -top-[24vmax] h-[62vmax] w-[62vmax] rounded-full"
        style={{
          background:
            "radial-gradient(circle at 42% 42%, rgba(34,211,238,0.20), rgba(34,211,238,0) 62%)",
          filter: "blur(80px)",
          animation: "p117-mesh-a 28s ease-in-out infinite",
          willChange: "transform",
        }}
      />
      {/* Deep ice field, bottom-right. */}
      <div
        className="absolute -bottom-[28vmax] -right-[16vmax] h-[58vmax] w-[58vmax] rounded-full"
        style={{
          background:
            "radial-gradient(circle at 50% 50%, rgba(56,142,255,0.18), rgba(56,142,255,0) 64%)",
          filter: "blur(90px)",
          animation: "p117-mesh-b 34s ease-in-out infinite",
          willChange: "transform",
        }}
      />
      {/* A pale highlight that keeps the middle from going muddy. */}
      <div
        className="absolute left-1/3 top-1/4 h-[42vmax] w-[42vmax] rounded-full"
        style={{
          background:
            "radial-gradient(circle at 50% 50%, rgba(255,255,255,0.85), rgba(255,255,255,0) 60%)",
          filter: "blur(70px)",
          animation: "p117-mesh-c 40s ease-in-out infinite",
          willChange: "transform",
        }}
      />
      {/* Blueprint grid, barely there. */}
      <div
        className="absolute inset-0 opacity-[0.5]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(15,23,42,0.030) 1px, transparent 1px), linear-gradient(90deg, rgba(15,23,42,0.030) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          maskImage: "radial-gradient(ellipse at 50% 0%, #000 20%, transparent 78%)",
          WebkitMaskImage: "radial-gradient(ellipse at 50% 0%, #000 20%, transparent 78%)",
        }}
      />
      <style jsx>{`
        @keyframes p117-mesh-a {
          0%, 100% { transform: translate3d(0, 0, 0) scale(1); }
          50% { transform: translate3d(6vmax, 4vmax, 0) scale(1.08); }
        }
        @keyframes p117-mesh-b {
          0%, 100% { transform: translate3d(0, 0, 0) scale(1.05); }
          50% { transform: translate3d(-7vmax, -5vmax, 0) scale(1); }
        }
        @keyframes p117-mesh-c {
          0%, 100% { transform: translate3d(-3vmax, 2vmax, 0) scale(1); opacity: 0.75; }
          50% { transform: translate3d(4vmax, -3vmax, 0) scale(1.12); opacity: 1; }
        }
        @media (prefers-reduced-motion: reduce) {
          .pointer-events-none > div { animation: none !important; }
        }
      `}</style>
    </div>
  );
}
