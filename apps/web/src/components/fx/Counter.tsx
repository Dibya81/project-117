"use client";

/**
 * Counter — rAF-eased number count-up. Fires when scrolled into view.
 * Supports decimals, prefix/suffix, and respects reduced motion.
 */
import { useEffect, useRef, useState } from "react";

export function Counter({
  value,
  decimals = 0,
  prefix = "",
  suffix = "",
  duration = 1400,
  className,
  as: Tag = "span",
}: {
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  duration?: number;
  className?: string;
  /**
   * The element to render. Defaults to `span`; pass `"b"` where the caller's own
   * markup uses a bold value node, so the counter replaces that node instead of
   * nesting a second inline element inside it (nested spans break selectors that
   * expect the label to be an element's first `span`).
   */
  as?: "span" | "b" | "strong" | "div";
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const [display, setDisplay] = useState(0);
  const startedRef = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const run = () => {
      if (startedRef.current) return;
      startedRef.current = true;
      if (reduced) {
        setDisplay(value);
        return;
      }
      const t0 = performance.now();
      const tick = (now: number) => {
        const t = Math.min(1, (now - t0) / duration);
        const eased = 1 - Math.pow(1 - t, 4);
        setDisplay(value * eased);
        if (t < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    };

    if (typeof IntersectionObserver === "undefined") {
      run();
      return;
    }
    const io = new IntersectionObserver(
      (entries) => entries.some((e) => e.isIntersecting) && (run(), io.disconnect()),
      { threshold: 0.3 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [value, duration]);

  return (
    <Tag ref={ref as never} className={className}>
      {prefix}
      {display.toFixed(decimals)}
      {suffix}
    </Tag>
  );
}
