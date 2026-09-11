"use client";

/**
 * DocumentField — documents moving through space.
 *
 * A deep looping perspective rail of real refinery pages. Each card is drawn
 * from actual document content: a header strip, the section title, body lines
 * and a table. Cards travel from the far distance toward the viewer, so the
 * archive reads as material rather than decoration.
 *
 * Once per cycle a scan pass sweeps the page nearest the focal plane. As it
 * crosses, the entities on that page — equipment tags, measurements, document
 * ids — light up and detach. That is the visual argument the page makes:
 *
 *     raw page  →  understanding  →  structure  →  knowledge
 *
 * The ThreeUI filmstrip is the technical reference for depth, looping motion,
 * focus and parallax. None of its content is used; every page here is refinery
 * documentation from `src/lib/documents/field.ts`.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { CORPUS_PAGES, KIND_LABEL, loadGeneratedPages, type DocPage } from "@/lib/documents/field";

const FOCAL = 3.0;
const NEAR = 1.0;
const FAR = 3.2;
// Landscape technical pages. Portrait A4 cards leave dead space in a landscape
// viewport; a datasheet aspect fills the frame and suits engineering tables.
const CARD_W = 0.80;
const CARD_H = 0.46;
/** Cards travelling the rail at once. */
const SLOTS = 9;

interface Props {
  onSelect?: (page: DocPage) => void;
  /** Seconds for one card to travel the full rail. */
  speed?: number;
}

export default function DocumentField({ onSelect, speed = 1 }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const size = useRef({ w: 0, h: 0, dpr: 1 });
  const pointer = useRef({ x: 0, y: 0, tx: 0, ty: 0 });
  const journey = useRef(0);
  const scan = useRef(0);
  const raf = useRef(0);
  const last = useRef(0);
  const visible = useRef(true);
  const reduced = useRef(false);
  const hit = useRef<{ page: DocPage; x: number; y: number; w: number; h: number }[]>([]);
  const [hover, setHover] = useState<DocPage | null>(null);
  const [pages, setPages] = useState<DocPage[]>(CORPUS_PAGES);
  const [count, setCount] = useState(CORPUS_PAGES.length);

  // Append generated knowledge-base sections when present.
  useEffect(() => {
    let alive = true;
    loadGeneratedPages().then((extra) => {
      if (!alive || !extra.length) return;
      setPages([...CORPUS_PAGES, ...extra]);
      setCount(CORPUS_PAGES.length + extra.length);
    });
    return () => { alive = false; };
  }, []);

  const draw = useMemo(
    () => (t: number, dt: number) => {
      const canvas = canvasRef.current;
      const ctx = canvas?.getContext("2d");
      if (!canvas || !ctx) return;
      const { w, h, dpr } = size.current;
      if (!w || !h) return;

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      const n = pages.length;
      if (!n) return;

      // advance the rail unless reduced motion is requested
      if (!reduced.current) {
        journey.current += dt / (18 / speed);
        scan.current = (scan.current + dt / 9) % 1.6;
      }
      const phase = journey.current % 1;
      const p = pointer.current;
      p.x += (p.tx - p.x) * 0.055;
      p.y += (p.ty - p.y) * 0.055;

      const cx = w * 0.42;
      const cy = h * 0.50;
      // World unit → px at z = 1. Tuned so the nearest page fills roughly
      // 70% of the width and 60% of the height, and every card stays in frame.
      const unit = h * 0.30;
      const frontS = (FOCAL / NEAR) * unit;

      const hits: typeof hit.current = [];
      const cards: { page: DocPage; x: number; y: number; s: number; z: number; depth: number }[] = [];

      // Fixed slots rather than one card per page: with 27 pages on a looping
      // rail the cards bunched into an unreadable pile. Now SLOTS cards travel
      // the rail at even spacing, and a slot takes its next page exactly when
      // it wraps to the far end — so the swap happens where it cannot be seen.
      for (let s = 0; s < SLOTS; s++) {
        const d = (s / SLOTS + phase) % 1;
        const k = Math.floor(journey.current + s / SLOTS);
        const page = pages[(((s + k) % n) + n) % n];
        const z = NEAR + (FAR - NEAR) * d;
        const dep = 1 - d; // 1 near → 0 far
        const sz = (FOCAL / z) * unit;
        // Near pages sit low-right and large; far pages recede high-left and
        // small. `d` is distance, so both terms invert against it.
        const x = cx + (0.5 - d) * unit * 3.0 + p.x * (10 + dep * 26);
        const y = cy + (0.55 - d) * unit * 1.1 + p.y * (6 + dep * 14);
        cards.push({ page, x, y, s: sz, z, depth: dep });
      }

      // far → near paint order
      cards.sort((a, b) => a.depth - b.depth);

      for (const c of cards) {
        const { page, x, y, depth } = c;
        const cw = CARD_W * c.s;
        const ch = CARD_H * c.s;
        if (x + cw < -80 || x - cw > w + 80) continue;

        // Fully opaque for almost the whole run; only the last sliver of depth
        // fades, so the page arriving at the focal plane is the readable hero
        // rather than a ghost.
        const alpha = Math.min(1, depth * 2.6) * (1 - Math.max(0, (depth - 0.92) / 0.08) * 0.9);
        if (alpha <= 0.02) continue;

        const focused = depth > 0.62 && depth < 0.92;
        const left = x - cw / 2;
        const top = y - ch / 2;

        ctx.globalAlpha = alpha;

        // ---- page surface --------------------------------------------
        ctx.save();
        // slight perspective tilt, more pronounced with depth
        const skew = (0.5 - depth) * 0.06;
        ctx.transform(1, 0, skew, 1, 0, 0);

        const bg = ctx.createLinearGradient(left, top, left, top + ch);
        bg.addColorStop(0, focused ? "#ffffff" : "#fbfcfe");
        bg.addColorStop(1, "#eef2f7");
        ctx.fillStyle = bg;
        roundRect(ctx, left, top, cw, ch, Math.min(6, cw * 0.045));
        ctx.fill();

        // paper rules — the texture that makes it read as a document
        if (cw > 70) {
          ctx.strokeStyle = "rgba(15,23,42,0.07)";
          ctx.lineWidth = 1;
          ctx.beginPath();
          const gap = Math.max(7, ch * 0.055);
          for (let ly = top + ch * 0.30; ly < top + ch - gap * 0.6; ly += gap) {
            ctx.moveTo(left + cw * 0.07, ly);
            ctx.lineTo(left + cw * 0.93, ly);
          }
          ctx.stroke();
        }

        // header strip
        ctx.fillStyle = "rgba(37,99,235,0.08)";
        ctx.fillRect(left, top, cw, Math.max(6, ch * 0.075));
        ctx.strokeStyle = `rgba(37,99,235,${focused ? 0.5 : 0.22})`;
        ctx.lineWidth = 1;
        ctx.strokeRect(left + 0.5, top + 0.5, cw - 1, ch - 1);

        // left edge marker in the document's semantic colour
        ctx.fillStyle = kindColor(page.kind);
        ctx.fillRect(left, top, Math.max(2, cw * 0.012), ch);

        ctx.globalAlpha = alpha;
        ctx.restore();

        // ---- content (only when legible) ------------------------------
        // Landscape datasheet layout: title and body on the left, the
        // extracted table (or the entity panel) on the right. Only pages large
        // enough to actually be read render text — the receding ones stay as
        // paper, which stops far-card type bleeding through the near card.
        if (c.s > frontS * 0.7 && cw > 150 && ch > 80) {
          const pad = cw * 0.045;
          const leftW = (cw - pad * 3) * 0.56;
          const rightX = left + pad * 2 + leftW;
          const rightW = cw - pad * 2 - leftW - pad;

          ctx.textAlign = "left";
          ctx.textBaseline = "top";

          // header strip label
          const hdr = Math.max(7, ch * 0.052);
          ctx.font = `600 ${hdr}px ui-monospace, SFMono-Regular, Menlo, monospace`;
          ctx.fillStyle = "rgba(100,116,139,0.95)";
          ctx.fillText(truncate(ctx, page.doc, cw - pad * 2), left + pad, top + ch * 0.028);

          // title
          const titleSize = Math.max(8, ch * 0.085);
          ctx.font = `600 ${titleSize}px ui-sans-serif, system-ui, sans-serif`;
          ctx.fillStyle = "#0f172a";
          const titleLines = wrap(ctx, page.section, leftW, 2);
          let ty = top + ch * 0.20;
          titleLines.forEach((line) => {
            ctx.fillText(line, left + pad, ty);
            ty += titleSize * 1.15;
          });

          // body
          const fs = Math.max(6, ch * 0.052);
          ctx.font = `${fs}px ui-sans-serif, system-ui, sans-serif`;
          ctx.fillStyle = "rgba(71,85,105,0.92)";
          let ly = ty + ch * 0.045;
          const maxBody = Math.floor((top + ch * 0.80 - ly) / (fs * 1.45));
          for (const rawLine of page.lines) {
            if (maxBody <= 0) break;
            for (const line of wrap(ctx, rawLine, leftW, 1)) {
              if (ly > top + ch * 0.80) break;
              ctx.fillText(line, left + pad, ly);
              ly += fs * 1.45;
            }
          }

          // right column: extracted table, else the entity list
          if (page.table && page.table.length > 1) {
            const cols = page.table[0].length;
            const cwid = rightW / cols;
            const rh = Math.max(8, ch * 0.072);
            let ry = top + ch * 0.20;
            ctx.font = `${Math.max(5.5, ch * 0.042)}px ui-monospace, SFMono-Regular, Menlo, monospace`;
            page.table.slice(0, 5).forEach((row, ri) => {
              if (ry + rh > top + ch - pad) return;
              if (ri === 0) {
                ctx.fillStyle = "rgba(37,99,235,0.08)";
                ctx.fillRect(rightX, ry, rightW, rh);
              }
              ctx.strokeStyle = "rgba(15,23,42,0.12)";
              ctx.lineWidth = 1;
              ctx.beginPath();
              ctx.moveTo(rightX, ry + rh);
              ctx.lineTo(rightX + rightW, ry + rh);
              ctx.stroke();
              row.forEach((cell, ci) => {
                ctx.fillStyle = ri === 0 ? "rgba(71,85,105,0.95)" : "rgba(100,116,139,0.9)";
                ctx.fillText(truncate(ctx, cell, cwid - 4), rightX + ci * cwid + 2, ry + rh * 0.24);
              });
              ry += rh;
            });
          } else {
            // no table: show the graph entities this page yields
            ctx.font = `600 ${Math.max(6, ch * 0.045)}px ui-monospace, SFMono-Regular, Menlo, monospace`;
            ctx.fillStyle = "rgba(100,116,139,0.85)";
            ctx.fillText("EXTRACTED ENTITIES", rightX, top + ch * 0.20);
            let ey = top + ch * 0.30;
            const efs = Math.max(6, ch * 0.048);
            ctx.font = `${efs}px ui-monospace, SFMono-Regular, Menlo, monospace`;
            for (const ent of page.entities.slice(0, 6)) {
              if (ey > top + ch - pad) break;
              ctx.fillStyle = "rgba(37,99,235,0.08)";
              const tw2 = Math.min(rightW, ctx.measureText(ent).width + 10);
              ctx.fillRect(rightX, ey - 2, tw2, efs + 5);
              ctx.strokeStyle = "rgba(37,99,235,0.3)";
              ctx.lineWidth = 1;
              ctx.strokeRect(rightX + 0.5, ey - 1.5, tw2 - 1, efs + 4);
              ctx.fillStyle = "#2563eb";
              ctx.fillText(truncate(ctx, ent, rightW - 8), rightX + 5, ey);
              ey += efs + 9;
            }
          }

          // ---- scan pass: entities detach as the beam crosses ----------
          const inFocus = depth > 0.68 && depth < 0.9;
          if (inFocus && !reduced.current) {
            const sp = scan.current;
            const yScan = top + ch * Math.min(1, Math.max(0, sp));
            if (sp < 1) {
              const g = ctx.createLinearGradient(0, yScan - 18, 0, yScan + 18);
              g.addColorStop(0, "rgba(37,99,235,0)");
              g.addColorStop(0.5, "rgba(37,99,235,0.16)");
              g.addColorStop(1, "rgba(37,99,235,0)");
              ctx.fillStyle = g;
              ctx.fillRect(left, yScan - 18, cw, 36);
              ctx.strokeStyle = "rgba(37,99,235,0.65)";
              ctx.lineWidth = 1;
              ctx.beginPath();
              ctx.moveTo(left, yScan);
              ctx.lineTo(left + cw, yScan);
              ctx.stroke();
            }
            if (sp >= 1) {
              ctx.font = `600 ${Math.max(6, ch * 0.05)}px ui-monospace, SFMono-Regular, Menlo, monospace`;
              ctx.fillStyle = `rgba(37,99,235,${Math.min(0.95, (sp - 1) / 0.4)})`;
              ctx.textAlign = "right";
              ctx.fillText(
                `→ ${page.entities.length} entities · graph updated`,
                left + cw - pad,
                top + ch - pad - ch * 0.10,
              );
              ctx.textAlign = "left";
            }
          }
        }

        ctx.globalAlpha = 1;
        if (depth > 0.55) hits.push({ page, x, y, w: cw, h: ch });
      }
      hit.current = hits;
    },
    [pages, speed],
  );

  /* ---------------- lifecycle ---------------- */
  useEffect(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    if (!wrap || !canvas) return;

    reduced.current = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = wrap.clientWidth;
      const h = wrap.clientHeight;
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
      }
      size.current = { w, h, dpr };
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(wrap);

    // Stop the loop when scrolled out of view — no idle rAF on other pages.
    const io = new IntersectionObserver((entries) => {
      visible.current = entries[0]?.isIntersecting ?? true;
    }, { threshold: 0.01 });
    io.observe(wrap);

    const loop = (t: number) => {
      raf.current = requestAnimationFrame(loop);
      const dt = Math.min(0.05, (t - last.current) / 1000 || 0.016);
      last.current = t;
      if (!visible.current || document.hidden) return;
      draw(t, dt);
    };
    raf.current = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf.current);
      ro.disconnect();
      io.disconnect();
    };
  }, [draw]);

  const onMove = (e: React.PointerEvent) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    pointer.current.tx = ((e.clientX - rect.left) / rect.width - 0.5) * 2;
    pointer.current.ty = ((e.clientY - rect.top) / rect.height - 0.5) * 2;
    let found: typeof hover = null;
    for (const c of hit.current) {
      if (Math.abs(e.clientX - rect.left - c.x) < c.w / 2 && Math.abs(e.clientY - rect.top - c.y) < c.h / 2) {
        found = c.page;
      }
    }
    setHover(found);
  };

  const onClick = () => {
    if (hover) onSelect?.(hover);
  };

  return (
    <div ref={wrapRef} className="df-wrap">
      <canvas
        ref={canvasRef}
        className="df-canvas"
        onPointerMove={onMove}
        onPointerLeave={() => { pointer.current.tx = 0; pointer.current.ty = 0; setHover(null); }}
        onClick={onClick}
        style={{ cursor: hover ? "pointer" : "default" }}
        aria-label="Animated archive of refinery documents moving through space"
        role="img"
      />
      <div className="df-legend" aria-hidden="true">
        <span><i style={{ background: kindColor("inspection") }} />Inspection</span>
        <span><i style={{ background: kindColor("procedure") }} />Procedure</span>
        <span><i style={{ background: kindColor("baseline") }} />Baseline</span>
        <span><i style={{ background: kindColor("manual") }} />Manual</span>
        <span><i style={{ background: kindColor("record") }} />Record</span>
        <span><i style={{ background: kindColor("register") }} />Register</span>
      </div>
      <div className="df-status" aria-live="polite">
        {hover ? (
          <>
            <b>{hover.doc}</b>
            <span>{KIND_LABEL[hover.kind]} · {hover.section}</span>
          </>
        ) : (
          <span className="df-status__idle">{count} documents in the archive · move to inspect · click to open</span>
        )}
      </div>
    </div>
  );
}

/* ---------------- helpers ---------------- */

function kindColor(kind: DocPage["kind"]): string {
  switch (kind) {
    case "inspection": return "#45d5ff";
    case "procedure": return "#3ddc97";
    case "baseline": return "#ffb454";
    case "manual": return "#b79cff";
    case "record": return "#ff7a3d";
    default: return "#64748b";
  }
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  const rr = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}

function truncate(ctx: CanvasRenderingContext2D, text: string, max: number): string {
  if (ctx.measureText(text).width <= max) return text;
  let out = text;
  while (out.length > 1 && ctx.measureText(`${out}…`).width > max) out = out.slice(0, -1);
  return `${out}…`;
}

function wrap(ctx: CanvasRenderingContext2D, text: string, max: number, maxLines: number): string[] {
  const words = text.split(" ");
  const lines: string[] = [];
  let cur = "";
  for (const word of words) {
    const next = cur ? `${cur} ${word}` : word;
    if (ctx.measureText(next).width > max && cur) {
      lines.push(cur);
      cur = word;
      if (lines.length >= maxLines) return lines;
    } else {
      cur = next;
    }
  }
  if (cur) lines.push(cur);
  return lines.slice(0, maxLines);
}
