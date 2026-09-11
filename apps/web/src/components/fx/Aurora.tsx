"use client";

/**
 * Aurora — the fixed ambient background shared by landing and console.
 * Two drifting energy fields (cyan + ember), a blueprint grid, film grain
 * and a vignette. One element, zero repaint cost after mount (transform-only
 * animation). `calm` drops intensity for the console register.
 */
export function Aurora({ calm = false }: { calm?: boolean }) {
  return (
    <div className={`fx-aurora${calm ? " fx-aurora--calm" : ""}`} aria-hidden="true">
      <div className="fx-aurora__blob fx-aurora__blob--cyan" />
      <div className="fx-aurora__blob fx-aurora__blob--ember" />
      <div className="fx-aurora__grid" />
      <div className="fx-aurora__grain" />
      <div className="fx-aurora__vignette" />
      <style jsx>{`
        .fx-aurora {
          position: fixed;
          inset: 0;
          z-index: 0;
          overflow: hidden;
          pointer-events: none;
          background: var(--bg-0);
        }
        .fx-aurora__blob {
          position: absolute;
          width: 62vmax;
          height: 62vmax;
          border-radius: 50%;
          filter: blur(90px);
          will-change: transform;
        }
        .fx-aurora__blob--cyan {
          top: -24vmax;
          left: -18vmax;
          background: radial-gradient(circle at 40% 40%, rgba(69, 213, 255, 0.16), transparent 62%);
          animation: p117-aurora-drift 26s ease-in-out infinite;
        }
        .fx-aurora__blob--ember {
          bottom: -26vmax;
          right: -16vmax;
          background: radial-gradient(circle at 60% 60%, rgba(255, 122, 61, 0.12), transparent 60%);
          animation: p117-aurora-drift 32s ease-in-out infinite reverse;
        }
        .fx-aurora--calm .fx-aurora__blob--cyan { opacity: 0.55; }
        .fx-aurora--calm .fx-aurora__blob--ember { opacity: 0.5; }
        /* The console runs a bright canvas. Left dark, this layer painted over
           every static descendant (panels, headings) because it is a positioned
           z-index:0 element while they are not — so the console read as light
           chrome sitting on a dark page. In the calm register the field is
           light and the vignette opens instead of closing. */
        .fx-aurora--calm { background: #f8f9fa; }
        .fx-aurora--calm .fx-aurora__blob--cyan {
          background: radial-gradient(circle at 40% 40%, rgba(37, 99, 235, 0.1), transparent 62%);
        }
        .fx-aurora--calm .fx-aurora__blob--ember {
          background: radial-gradient(circle at 60% 60%, rgba(124, 58, 237, 0.08), transparent 60%);
        }
        .fx-aurora--calm .fx-aurora__grid {
          background-image:
            linear-gradient(rgba(100, 116, 139, 0.06) 1px, transparent 1px),
            linear-gradient(90deg, rgba(100, 116, 139, 0.06) 1px, transparent 1px);
        }
        .fx-aurora--calm .fx-aurora__grain { opacity: 0.018; }
        .fx-aurora--calm .fx-aurora__vignette { background: none; }
        .fx-aurora__grid {
          position: absolute;
          inset: 0;
          background-image:
            linear-gradient(rgba(140, 180, 220, 0.045) 1px, transparent 1px),
            linear-gradient(90deg, rgba(140, 180, 220, 0.045) 1px, transparent 1px);
          background-size: 56px 56px;
          mask-image: radial-gradient(ellipse 90% 80% at 50% 40%, #000 30%, transparent 78%);
        }
        .fx-aurora__grain {
          position: absolute;
          inset: -50%;
          opacity: 0.05;
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='240' height='240'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='240' height='240' filter='url(%23n)' opacity='0.9'/%3E%3C/svg%3E");
          animation: p117-grain 900ms steps(2) infinite;
        }
        @keyframes p117-grain {
          0% { transform: translate(0, 0); }
          25% { transform: translate(-2%, 1%); }
          50% { transform: translate(1%, -2%); }
          75% { transform: translate(-1%, 2%); }
          100% { transform: translate(2%, -1%); }
        }
        .fx-aurora__vignette {
          position: absolute;
          inset: 0;
          background: radial-gradient(ellipse 120% 90% at 50% 45%, transparent 55%, rgba(2, 4, 8, 0.75) 100%);
        }
      `}</style>
    </div>
  );
}
