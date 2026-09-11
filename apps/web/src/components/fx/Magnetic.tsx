"use client";

/**
 * Magnetic — pointer-attracted wrapper with spring return.
 * Wraps CTAs; strength scales the pull. Transform-only, GPU friendly.
 */
import { useRef, type ReactNode, type CSSProperties, type PointerEvent as ReactPointerEvent } from "react";

export function Magnetic({
  children,
  strength = 0.35,
  className,
  style,
}: {
  children: ReactNode;
  strength?: number;
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
    const x = (e.clientX - (r.left + r.width / 2)) * strength;
    const y = (e.clientY - (r.top + r.height / 2)) * strength;
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      el.style.transition = "transform 90ms linear";
      el.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
    });
  };

  const onLeave = () => {
    const el = ref.current;
    if (!el) return;
    cancelAnimationFrame(frame.current);
    el.style.transition = "transform 620ms var(--ease-spring)";
    el.style.transform = "translate(0, 0)";
  };

  return (
    <div
      ref={ref}
      className={className}
      style={{ display: "inline-block", ...style }}
      onPointerMove={onMove}
      onPointerLeave={onLeave}
    >
      {children}
    </div>
  );
}
