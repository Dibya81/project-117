"use client";

/**
 * Reveal — IntersectionObserver entrance animation.
 * Children rise, de-blur and settle once when they enter the viewport.
 * `delay` staggers siblings; `as` keeps semantics. Pure CSS after trigger.
 */
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

type Direction = "up" | "down" | "left" | "right" | "zoom";

const OFFSET: Record<Direction, string> = {
  up: "translateY(26px)",
  down: "translateY(-18px)",
  left: "translateX(26px)",
  right: "translateX(-26px)",
  zoom: "scale(0.94)",
};

export function Reveal({
  children,
  delay = 0,
  from = "up",
  className,
  style,
  once = true,
}: {
  children: ReactNode;
  delay?: number;
  from?: Direction;
  className?: string;
  style?: CSSProperties;
  once?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            setInView(true);
            if (once) io.disconnect();
          } else if (!once) {
            setInView(false);
          }
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -6% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [once]);

  const hidden: CSSProperties = {
    opacity: 0,
    transform: OFFSET[from],
    filter: "blur(7px)",
  };
  const shown: CSSProperties = {
    opacity: 1,
    transform: "none",
    filter: "blur(0)",
  };

  return (
    <div
      ref={ref}
      className={className}
      style={{
        ...(inView ? shown : hidden),
        transition: `opacity 760ms var(--ease-out) ${delay}ms, transform 760ms var(--ease-out) ${delay}ms, filter 760ms var(--ease-out) ${delay}ms`,
        willChange: inView ? "auto" : "opacity, transform, filter",
        ...style,
      }}
    >
      {children}
    </div>
  );
}
