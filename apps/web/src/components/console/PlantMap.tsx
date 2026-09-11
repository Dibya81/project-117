"use client";

/**
 * PlantMap — procedural 2D plant visualization on canvas.
 * Equipment rendered at their real layout positions with kind glyphs and
 * status glow; pipes carry a slow energy flow. Hover illuminates an asset
 * (+ tooltip with live-ish telemetry), click dives into its digital twin.
 * Canvas (not DOM) so 60fps pulses cost nothing.
 */
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { Equipment } from "@/types";

const COLORS = {
  ok: "#3ddc97",
  warning: "#ffb454",
  critical: "#ff5d5d",
  unknown: "#5b6c81",
};

/** Fixed pipe topology (Unit flow) for the demo plant. */
const PIPES: [string, string][] = [
  ["T-118", "P-1042"],
  ["P-1042", "E-340"],
  ["E-340", "C-3"],
  ["C-3", "V-2210"],
  ["E-340", "P-2051"],
];

export function PlantMap({ equipment, onHover }: { equipment: Equipment[]; onHover?: (eq: Equipment | null) => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [hovered, setHovered] = useState<Equipment | null>(null);
  const [tip, setTip] = useState<{ x: number; y: number } | null>(null);
  const router = useRouter();
  const hoveredRef = useRef<string | null>(null);
  const routerRef = useRef(router);
  routerRef.current = router;

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap || equipment.length === 0) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // --- layout: map (x,z) positions into canvas space ---
    const xs = equipment.map((e) => e.position[0]);
    const zs = equipment.map((e) => e.position[2]);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minZ = Math.min(...zs), maxZ = Math.max(...zs);
    const px = new Map<string, { x: number; y: number }>();

    let W = 0, H = 0, dpr = 1;
    const layout = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = wrap.clientWidth;
      H = wrap.clientHeight;
      canvas.width = W * dpr;
      canvas.height = H * dpr;
      canvas.style.width = `${W}px`;
      canvas.style.height = `${H}px`;
      const padX = W * 0.1, padY = H * 0.18;
      const spanX = maxX - minX || 1;
      const spanZ = maxZ - minZ || 1;
      equipment.forEach((e) => {
        const nx = (e.position[0] - minX) / spanX;
        const nz = (e.position[2] - minZ) / spanZ;
        px.set(e.id, {
          x: padX + nx * (W - padX * 2),
          y: padY + nz * (H - padY * 2),
        });
      });
    };
    layout();

    const ro = new ResizeObserver(layout);
    ro.observe(wrap);

    const glyph = (kind: Equipment["kind"], x: number, y: number, r: number, color: string) => {
      ctx.beginPath();
      switch (kind) {
        case "pump":
          ctx.arc(x, y, r, 0, Math.PI * 2);
          ctx.moveTo(x - r * 0.5, y);
          ctx.arc(x, y, r * 0.5, Math.PI, 0);
          break;
        case "compressor":
          ctx.moveTo(x, y - r);
          ctx.lineTo(x + r, y + r * 0.7);
          ctx.lineTo(x - r, y + r * 0.7);
          ctx.closePath();
          break;
        case "tank":
          ctx.roundRect(x - r * 0.8, y - r, r * 1.6, r * 2, r * 0.4);
          break;
        case "valve":
          ctx.moveTo(x, y - r);
          ctx.lineTo(x + r, y);
          ctx.lineTo(x, y + r);
          ctx.lineTo(x - r, y);
          ctx.closePath();
          break;
        case "exchanger":
          for (let i = 0; i < 6; i++) {
            const a = (Math.PI / 3) * i - Math.PI / 6;
            const vx = x + Math.cos(a) * r;
            const vy = y + Math.sin(a) * r;
            if (i === 0) ctx.moveTo(vx, vy);
            else ctx.lineTo(vx, vy);
          }
          ctx.closePath();
          break;
      }
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.6;
      ctx.stroke();
    };

    let raf = 0;
    let t = 0;
    const draw = () => {
      raf = requestAnimationFrame(draw);
      t += 0.016;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);

      // grid
      ctx.strokeStyle = "rgba(140,180,220,0.05)";
      ctx.lineWidth = 1;
      for (let gx = 0; gx < W; gx += 44) {
        ctx.beginPath();
        ctx.moveTo(gx, 0);
        ctx.lineTo(gx, H);
        ctx.stroke();
      }
      for (let gy = 0; gy < H; gy += 44) {
        ctx.beginPath();
        ctx.moveTo(0, gy);
        ctx.lineTo(W, gy);
        ctx.stroke();
      }

      // pipes + energy flow
      PIPES.forEach(([a, b]) => {
        const pa = px.get(a);
        const pb = px.get(b);
        if (!pa || !pb) return;
        ctx.beginPath();
        ctx.moveTo(pa.x, pa.y);
        ctx.lineTo(pb.x, pb.y);
        ctx.strokeStyle = "rgba(140,180,220,0.16)";
        ctx.lineWidth = 1.4;
        ctx.stroke();
        // traveling energy pulse
        const k = (t * 0.22 + (a.charCodeAt(0) % 7) * 0.13) % 1;
        const fx = pa.x + (pb.x - pa.x) * k;
        const fy = pa.y + (pb.y - pa.y) * k;
        ctx.beginPath();
        ctx.arc(fx, fy, 2.2, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(69,213,255,0.85)";
        ctx.shadowColor = "#45d5ff";
        ctx.shadowBlur = 8;
        ctx.fill();
        ctx.shadowBlur = 0;
      });

      // equipment nodes
      equipment.forEach((e) => {
        const p = px.get(e.id);
        if (!p) return;
        const c = COLORS[e.status];
        const isHover = hoveredRef.current === e.id;
        const pulseRate = e.status === "critical" ? 2.6 : e.status === "warning" ? 1.4 : 0.6;
        const pulse = 0.5 + 0.5 * Math.sin(t * pulseRate * 2);
        const r = isHover ? 15 : 12;

        // halo
        const grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r * 3.2);
        grad.addColorStop(0, `${c}${e.status === "ok" ? "18" : "38"}`);
        grad.addColorStop(1, "transparent");
        ctx.beginPath();
        ctx.arc(p.x, p.y, r * (2.4 + pulse * 0.8), 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();

        // glyph + core
        glyph(e.kind, p.x, p.y, r, isHover ? "#eaf2fa" : c);
        ctx.beginPath();
        ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
        ctx.fillStyle = c;
        ctx.shadowColor = c;
        ctx.shadowBlur = isHover ? 16 : 8;
        ctx.fill();
        ctx.shadowBlur = 0;

        // label
        ctx.font = "600 10px ui-monospace, monospace";
        ctx.textAlign = "center";
        ctx.fillStyle = isHover ? "#eaf2fa" : "rgba(157,177,199,0.85)";
        ctx.fillText(e.id, p.x, p.y + r + 15);

        // critical: radiating ring
        if (e.status === "critical" && !reduced) {
          const rr = (t * 26) % 46;
          ctx.beginPath();
          ctx.arc(p.x, p.y, r + rr, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(255,93,93,${Math.max(0, 0.5 - rr / 92)})`;
          ctx.lineWidth = 1.2;
          ctx.stroke();
        }
      });

      if (reduced) cancelAnimationFrame(raf); // one static frame
    };
    draw();

    // --- interaction ---
    const pick = (mx: number, my: number): Equipment | null => {
      for (const e of equipment) {
        const p = px.get(e.id);
        if (!p) continue;
        const d = Math.hypot(mx - p.x, my - p.y);
        if (d < 22) return e;
      }
      return null;
    };

    const onMove = (ev: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      const mx = ev.clientX - rect.left;
      const my = ev.clientY - rect.top;
      const hit = pick(mx, my);
      hoveredRef.current = hit?.id ?? null;
      setHovered(hit);
      setTip(hit ? { x: mx, y: my } : null);
      canvas.style.cursor = hit ? "pointer" : "default";
    };
    const onLeave = () => {
      hoveredRef.current = null;
      setHovered(null);
      setTip(null);
    };
    const onClick = (ev: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      const hit = pick(ev.clientX - rect.left, ev.clientY - rect.top);
      if (hit) routerRef.current.push(`/console/equipment/${hit.id}`);
    };

    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerleave", onLeave);
    canvas.addEventListener("pointerdown", onClick);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerleave", onLeave);
      canvas.removeEventListener("pointerdown", onClick);
    };
  }, [equipment]);

  return (
    <div ref={wrapRef} style={{ position: "relative", width: "100%", height: 340 }}>
      <canvas ref={canvasRef} role="img" aria-label="Live plant map — equipment with status glow" />
      {hovered && tip && (
        <div
          className="cs-panel"
          style={{
            position: "absolute",
            left: Math.min(tip.x + 16, (wrapRef.current?.clientWidth ?? 300) - 220),
            top: Math.max(tip.y - 78, 8),
            padding: "10px 14px",
            pointerEvents: "none",
            zIndex: 5,
            background: "rgba(8,13,20,0.95)",
            animation: "p117-scale-in 180ms var(--ease-spring) both",
            minWidth: 190,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className="cs-mono cs-text-cyan" style={{ fontSize: 11, fontWeight: 700 }}>{hovered.id}</span>
            <span style={{ fontSize: 11.5, color: "var(--ink-1)" }}>{hovered.name}</span>
          </div>
          {hovered.sensors.slice(0, 2).map((s) => {
            const hot = (s.warnAbove != null && s.value >= s.warnAbove) || (s.critAbove != null && s.value >= s.critAbove);
            return (
              <div key={s.key} className="cs-mono" style={{ fontSize: 10, color: hot ? "var(--warn)" : "var(--ink-3)", marginTop: 4 }}>
                {s.label}: {s.value} {s.unit}
                {s.warnAbove != null && ` / warn ${s.warnAbove}`}
              </div>
            );
          })}
          {hovered.insight && (
            <div style={{ fontSize: 10, color: "var(--warn)", marginTop: 5, maxWidth: 210, lineHeight: 1.45 }}>
              ⚡ {hovered.insight.slice(0, 84)}…
            </div>
          )}
        </div>
      )}
    </div>
  );
}
