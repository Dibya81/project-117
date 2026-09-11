/** Shared math for the landing engines. No dependencies. */

export const clamp01 = (v) => Math.min(1, Math.max(0, v));
export const lerp = (a, b, t) => a + (b - a) * t;

/** 0 until a, 1 after b, smooth between. */
export const ramp = (p, a, b) => {
  const t = clamp01((p - a) / (b - a));
  return t * t * (3 - 2 * t);
};

export const easeOutExpo = (t) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t));
export const easeInOutCubic = (t) =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
export const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);

/** Deterministic PRNG (mulberry32) so layouts are stable across resizes. */
export function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const MONO = '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace';
export const SANS = 'Inter, "Helvetica Neue", "Segoe UI", Arial, sans-serif';

export const COLORS = {
  ink: "#e9eef4",
  ink2: "#aab8c6",
  ink3: "#66788a",
  cyan: "#46b8e8",
  orange: "#e8713a",
  red: "#ef4444",
  green: "#34d399",
  line: "#1f2a38",
};

/** Size a canvas to its CSS box at (capped) devicePixelRatio. */
export function fitCanvas(canvas) {
  const dprCap = window.innerWidth < 760 ? 1.5 : 2;
  const dpr = Math.min(window.devicePixelRatio || 1, dprCap);
  const w = Math.round(canvas.clientWidth * dpr);
  const h = Math.round(canvas.clientHeight * dpr);
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w;
    canvas.height = h;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  return { ctx, w, h, dpr };
}
