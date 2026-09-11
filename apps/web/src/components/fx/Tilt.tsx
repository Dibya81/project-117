"use client";

/**
 * Tilt — perspective card with tracking glare.
 * Subtle (max 6deg) so dense ops pages stay readable; the glare sells depth.
 */
import { useRef, type ReactNode, type CSSProperties, type PointerEvent as ReactPointerEvent } from "react";

export function Tilt({
  children,
  max = 6,
  className,
  style,
}: {
  children: ReactNode;
  max?: number;
  className?: string;
  style?: CSSProperties;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const frame = useRef(0);

  const onMove = (e: ReactPointerEvent) => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const r = el.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width;
    const py = (e.clientY - r.top) / r.height;
    const rx = (0.5 - py) * max;
    const ry = (px - 0.5) * max;
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      el.style.transition = "transform 80ms linear";
      el.style.transform = `perspective(900px) rotateX(${rx.toFixed(2)}deg) rotateY(${ry.toFixed(2)}deg) translateZ(0)`;
      el.style.setProperty("--glare-x", `${(px * 100).toFixed(1)}%`);
      el.style.setProperty("--glare-y", `${(py * 100).toFixed(1)}%`);
      el.style.setProperty("--glare-o", "1");
    });
  };

  const onLeave = () => {
    const el = ref.current;
    if (!el) return;
    cancelAnimationFrame(frame.current);
    el.style.transition = "transform 560ms var(--ease-out)";
    el.style.transform = "perspective(900px) rotateX(0deg) rotateY(0deg)";
    el.style.setProperty("--glare-o", "0");
  };

  return (
    <div
      ref={ref}
      className={`fx-tilt${className ? ` ${className}` : ""}`}
      style={style}
      onPointerMove={onMove}
      onPointerLeave={onLeave}
    >
      {children}
      <style jsx>{`
        .fx-tilt {
          position: relative;
          transform-style: preserve-3d;
          will-change: transform;
        }
        .fx-tilt::after {
          content: "";
          position: absolute;
          inset: 0;
          border-radius: inherit;
          pointer-events: none;
          opacity: var(--glare-o, 0);
          transition: opacity 420ms ease;
          background: radial-gradient(
            480px circle at var(--glare-x, 50%) var(--glare-y, 50%),
            rgba(180, 225, 255, 0.09),
            transparent 45%
          );
        }
      `}</style>
    </div>
  );
}
