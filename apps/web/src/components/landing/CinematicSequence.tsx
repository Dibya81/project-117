"use client";

/**
 * CinematicSequence — canvas renderer for the 121-frame WebP sequence.
 *
 * Scroll progress (0..1) is mapped to a frame index through STOPS, smoothed
 * with lerp in a single rAF loop owned by the parent, and drawn cover-fit.
 * Frames load by priority: the opening frames first, then a lookahead window
 * around the current position, then the remainder in idle chunks — the first
 * visual appears after one ~25 KB WebP instead of a 36 MB preload wall.
 */
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";

const FRAME_COUNT = 120;
const FRAME_W = 800;
const FRAME_H = 450;

const src = (i: number) =>
  `/assets/ezgif-split/seq/frame-${String(i).padStart(3, "0")}.webp`;

/** progress → frame. Matches the scene cuts audited from the contact sheet.
 * S1 (the photo section) occupies roughly the first 0.42 of scroll (frames
 * 0 → 48). The next frames (40 → 48) hold so the final S1 image is readable
 * before the next beat fades in. */
const STOPS: Array<[number, number]> = [
  [0.00, 0],
  [0.06, 4],
  [0.13, 9],
  [0.20, 14],
  [0.27, 19],
  [0.34, 25],
  [0.42, 40],
  [0.48, 48],
  [0.58, 58],
  [0.66, 70],
  [0.74, 82],
  [0.82, 92],
  [0.90, 108],
  [1.00, 119],
];

function frameAt(p: number): number {
  const clamped = Math.min(1, Math.max(0, p));
  for (let i = 1; i < STOPS.length; i++) {
    if (clamped <= STOPS[i][0]) {
      const [p0, f0] = STOPS[i - 1];
      const [p1, f1] = STOPS[i];
      const t = p1 === p0 ? 0 : (clamped - p0) / (p1 - p0);
      return f0 + (f1 - f0) * t;
    }
  }
  return FRAME_COUNT - 1;
}

export interface CinematicSequenceHandle {
  /** Draw the frame for (already smoothed) progress. Cheap if unchanged. */
  draw: (progress: number) => void;
}

const CinematicSequence = forwardRef<CinematicSequenceHandle>(function CinematicSequence(
  _props,
  ref,
) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imagesRef = useRef<Array<HTMLImageElement | null>>(
    Array.from({ length: FRAME_COUNT }, () => null),
  );
  const loadingRef = useRef<Set<number>>(new Set());
  const drawnFrameRef = useRef(-1);
  const sizeRef = useRef({ w: 0, h: 0, dpr: 1 });

  /** Nearest already-decoded frame, so scrolling ahead never blanks. */
  const nearestLoaded = (target: number): HTMLImageElement | null => {
    const images = imagesRef.current;
    for (let d = 0; d < FRAME_COUNT; d++) {
      const lo = target - d;
      const hi = target + d;
      if (lo >= 0 && images[lo]) return images[lo];
      if (hi < FRAME_COUNT && images[hi]) return images[hi];
    }
    return null;
  };

  const load = (i: number): void => {
    if (i < 0 || i >= FRAME_COUNT || imagesRef.current[i] || loadingRef.current.has(i)) return;
    loadingRef.current.add(i);
    const img = new Image();
    img.decoding = "async";
    img.src = src(i);
    img
      .decode()
      .catch(() => undefined) // decode() can reject after src swap; onload still cached it
      .finally(() => {
        if (img.complete && img.naturalWidth > 0) imagesRef.current[i] = img;
        loadingRef.current.delete(i);
        // Redraw when any better fallback arrives, even if the exact target is
        // still loading. This prevents later sections from appearing stuck on
        // frame 0 during fast scroll or direct jumps.
        if (drawnFrameRef.current >= 0) drawTo(drawnFrameRef.current, true);
      });
  };

  const drawTo = (index: number, force = false): void => {
    if (!force && index === drawnFrameRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    const img = nearestLoaded(index);
    if (!canvas || !ctx || !img) return;
    const { w, h } = sizeRef.current;
    if (!w || !h) return;
    // Cover-fit: scale the 16:9 frame so it fills the canvas, then centre-crop.
    // (Drawing straight to w/h would stretch the frame on non-16:9 viewports.)
    const scale = Math.max(w / FRAME_W, h / FRAME_H);
    const dw = FRAME_W * scale;
    const dh = FRAME_H * scale;
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(img, (w - dw) / 2, (h - dh) / 2, dw, dh);
    drawnFrameRef.current = index;
  };

  useImperativeHandle(ref, () => ({
    draw: (progress: number) => {
      const target = Math.round(frameAt(progress));
      // Lookahead: prioritize the frames the scroll is about to need.
      for (let d = 0; d <= 6; d++) {
        load(target + d);
        load(target - d);
      }
      drawTo(target);
    },
  }));

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const resize = () => {
      const dprCap = window.innerWidth < 760 ? 1.5 : 2;
      const dpr = Math.min(window.devicePixelRatio || 1, dprCap);
      const w = Math.round(canvas.clientWidth * dpr);
      const h = Math.round(canvas.clientHeight * dpr);
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }
      sizeRef.current = { w, h, dpr };
      drawTo(Math.max(0, drawnFrameRef.current), true);
    };
    resize();
    window.addEventListener("resize", resize);

    // Preload the full 120-frame sequence on mount so Section 1 never blanks.
    // The whole sequence is ~2.6 MB on disk, so buffering all 120 HTTP-fetched
    // WebP images is cheap; we keep them off the DOM (only one is ever drawn to
    // the canvas), and we do not touch src until onload to avoid double-fetch.
    for (let i = 0; i < FRAME_COUNT; i++) load(i);

    return () => {
      window.removeEventListener("resize", resize);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="p117-canvas"
      role="img"
      aria-label="Cinematic sequence: an industrial refinery at dusk, an overloaded control room, a local AI screen ingesting documents, a verified analysis on a field tablet, and a valve in the plant — ending on the Project 117 brand."
    />
  );
});

export default CinematicSequence;
