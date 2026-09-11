/**
 * Section 4 engine — the living system.
 * The particle core from Section 3 blooms into PROJECT 117, a ring of
 * capability nodes breathes into place, the center becomes the ORCHESTRATOR,
 * and activation pulses travel out to MAINTENANCE → DATA ANALYSIS → SAFETY →
 * VERIFICATION. On zoom-out the network relabels itself as the plant.
 * draw(p, time, mouse): p is section-local progress 0..1.
 */
import { COLORS, MONO, clamp01, easeInOutCubic, easeOutCubic, lerp, ramp, rng, fitCanvas } from "./easing.js";

const SATELLITES = [
  { label: "LOCAL MODELS", plant: "MACHINES" },
  { label: "RAG", plant: "DOCUMENTS" },
  { label: "MEMORY", plant: "SENSORS" },
  { label: "TOOLS", plant: "ENGINEERS" },
  { label: "SANDBOX", plant: "AI" },
  { label: "MAINTENANCE AGENT", plant: "PUMPS" },
  { label: "DATA ANALYSIS AGENT", plant: "TELEMETRY" },
  { label: "SAFETY AGENT", plant: "WORK ORDERS" },
  { label: "VERIFICATION", plant: "SOPS" },
];

const FLOW_ORDER = ["MAINTENANCE AGENT", "DATA ANALYSIS AGENT", "SAFETY AGENT", "VERIFICATION"];

export class NetworkScene {
  constructor(canvas) {
    this.canvas = canvas;
    const rand = rng(44117);
    this.extra = Array.from({ length: 14 }, () => ({
      a: rand() * Math.PI * 2,
      r: 1.15 + rand() * 0.5,
      s: 1 + rand() * 1.6,
    }));
  }

  draw(p, time, mouse) {
    const { ctx, w, h } = fitCanvas(this.canvas);
    ctx.clearRect(0, 0, w, h);

    const env = ramp(p, 0.0, 0.04) * (1 - ramp(p, 0.975, 1.0));
    if (env <= 0.001) return;

    const cx = w / 2 + mouse.x * 6;
    const cy = h / 2 + mouse.y * 4;
    const R = Math.min(w, h) * 0.33;

    const revealT = ramp(p, 0.03, 0.22);
    const flowT = ramp(p, 0.4, 0.78);
    const zoomT = easeInOutCubic(ramp(p, 0.8, 0.95));
    const zoom = lerp(1, 0.58, zoomT);

    const nodes = SATELLITES.map((n, i) => {
      const ang = (i / SATELLITES.length) * Math.PI * 2 - Math.PI / 2 + 0.12;
      const appear = easeOutCubic(clamp01((revealT - i * 0.045) / 0.5));
      return {
        ...n,
        i,
        ang,
        appear,
        x: cx + Math.cos(ang) * R * zoom,
        y: cy + Math.sin(ang) * R * 0.82 * zoom,
        breath: Math.sin(time * 1.3 + i * 1.7) * 1.6,
      };
    });

    ctx.save();
    ctx.globalAlpha = env;

    // ---------- edges ----------
    const edgeT = ramp(p, 0.16, 0.34);
    for (const n of nodes) {
      const a = edgeT * n.appear;
      if (a <= 0.01) continue;
      const grow = easeOutCubic(clamp01(edgeT * 1.4 - n.i * 0.06));
      ctx.strokeStyle = `rgba(102,120,138,${(0.4 * a).toFixed(3)})`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(lerp(cx, n.x, grow), lerp(cy, n.y, grow));
      ctx.stroke();
    }

    // ---------- the request entering the orchestrator ----------
    const reqT = ramp(p, 0.42, 0.52);
    if (reqT > 0.001 && reqT < 0.999) {
      const ex = easeInOutCubic(reqT);
      const x = lerp(-60, cx, ex);
      ctx.fillStyle = COLORS.ink;
      ctx.beginPath();
      ctx.arc(x, cy, 3, 0, Math.PI * 2);
      ctx.fill();
      const g = ctx.createLinearGradient(x - 70, cy, x, cy);
      g.addColorStop(0, "rgba(233,238,244,0)");
      g.addColorStop(1, `rgba(233,238,244,${(0.5 * (1 - reqT)).toFixed(3)})`);
      ctx.strokeStyle = g;
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.moveTo(x - 70, cy);
      ctx.lineTo(x, cy);
      ctx.stroke();
    }

    // ---------- activation pulses ----------
    FLOW_ORDER.forEach((label, k) => {
      const node = nodes.find((n) => n.label === label);
      if (!node) return;
      const start = 0.54 + k * 0.06;
      const pt = ramp(p, start, start + 0.05);
      if (pt <= 0 || pt >= 1) return;
      const e = easeInOutCubic(pt);
      ctx.fillStyle = COLORS.cyan;
      ctx.shadowColor = COLORS.cyan;
      ctx.shadowBlur = 12;
      ctx.beginPath();
      ctx.arc(lerp(cx, node.x, e), lerp(cy, node.y, e), 3.2, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
    });

    // ---------- nodes ----------
    const activeAt = (label) => {
      const k = FLOW_ORDER.indexOf(label);
      return k < 0 ? 0 : ramp(p, 0.6 + k * 0.06, 0.66 + k * 0.06);
    };

    ctx.textAlign = "center";
    for (const n of nodes) {
      if (n.appear <= 0.01) continue;
      const active = activeAt(n.label);
      const r = (3.4 + n.breath * 0.4) * n.appear * (1 + active * 0.5);
      const alpha = n.appear * (0.55 + active * 0.45);

      if (active > 0.01) {
        const g = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, 26);
        g.addColorStop(0, `rgba(70,184,232,${(0.5 * active * n.appear).toFixed(3)})`);
        g.addColorStop(1, "rgba(70,184,232,0)");
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(n.x, n.y, 26, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.fillStyle = active > 0.5 ? COLORS.cyan : COLORS.ink2;
      ctx.globalAlpha = env * alpha;
      ctx.beginPath();
      ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
      ctx.fill();

      const fs = Math.max(9, Math.min(12, w * 0.008));
      ctx.font = `${fs}px ${MONO}`;
      const labelY = n.y - r - 10;
      if (zoomT < 0.999) {
        ctx.globalAlpha = env * n.appear * (1 - zoomT) * 0.9;
        ctx.fillStyle = COLORS.ink3;
        ctx.fillText(n.label, n.x, labelY);
      }
      if (zoomT > 0.001) {
        ctx.globalAlpha = env * n.appear * zoomT * 0.9;
        ctx.fillStyle = COLORS.ink2;
        ctx.fillText(n.plant, n.x, labelY);
      }
      ctx.globalAlpha = env;
    }

    // ---------- the wider plant on zoom-out ----------
    if (zoomT > 0.001) {
      for (const ex of this.extra) {
        const x = cx + Math.cos(ex.a) * R * ex.r * zoom;
        const y = cy + Math.sin(ex.a) * R * ex.r * 0.82 * zoom;
        ctx.fillStyle = `rgba(102,120,138,${(0.35 * zoomT).toFixed(3)})`;
        ctx.beginPath();
        ctx.arc(x, y, ex.s, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = `rgba(102,120,138,${(0.12 * zoomT).toFixed(3)})`;
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(cx + Math.cos(ex.a) * R * zoom, cy + Math.sin(ex.a) * R * 0.82 * zoom);
        ctx.stroke();
      }
    }

    // ---------- center: core -> PROJECT 117 -> ORCHESTRATOR ----------
    const corePulse = 1 + Math.sin(time * 3.1) * 0.1;
    const coreR = 4.4 * corePulse * (1 + flowT * 0.4);
    const coreG = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR * 8);
    coreG.addColorStop(0, "rgba(233,238,244,0.95)");
    coreG.addColorStop(0.3, `rgba(70,184,232,${(0.45 + flowT * 0.2).toFixed(3)})`);
    coreG.addColorStop(1, "rgba(70,184,232,0)");
    ctx.fillStyle = coreG;
    ctx.beginPath();
    ctx.arc(cx, cy, coreR * 8, 0, Math.PI * 2);
    ctx.fill();

    const labelFs = Math.max(11, Math.min(15, w * 0.011));
    ctx.font = `700 ${labelFs}px ${MONO}`;
    const sweep = ramp(p, 0.06, 0.3);
    const band = (sweep * 1.6 - 0.3) * w * 0.5;
    ctx.fillStyle = COLORS.ink;
    ctx.globalAlpha = env * ramp(p, 0.04, 0.12);
    const centerLabel = flowT > 0.45 ? "ORCHESTRATOR" : "PROJECT 117";
    ctx.fillText(centerLabel, cx, cy + coreR * 8 + 6);
    const dist = Math.abs(band - cx);
    if (dist < w * 0.2 && sweep < 0.999) {
      ctx.globalAlpha = env * (1 - dist / (w * 0.2)) * 0.8 * (1 - sweep * 0.4);
      ctx.fillStyle = COLORS.cyan;
      ctx.fillText(centerLabel, cx, cy + coreR * 8 + 6);
    }
    ctx.globalAlpha = 1;
    ctx.restore();
  }
}
