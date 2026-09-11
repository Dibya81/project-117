/**
 * Section 2 engine — the information field.
 * Industrial information fragments float at parallax depths, fragment apart,
 * then the "700+ PAGES" burst expands a field of page-glyphs into depth,
 * freezes, and the camera pushes into one focused page before dying to black.
 * draw(p, time, mouse): p is the section-local progress 0..1.
 */
import { COLORS, MONO, clamp01, easeInOutCubic, easeOutExpo, lerp, ramp, rng, fitCanvas } from "./easing.js";

const LABELS = ["PDF", "SOP", "INSPECTION", "SCADA", "CMMS", "ERP", "SENSOR", "WORK ORDER", "DRAWING"];
const FRAGS = 54;
const PAGES = 170;

export class InfoField {
  constructor(canvas) {
    this.canvas = canvas;
    const rand = rng(117117);

    this.frags = Array.from({ length: FRAGS }, (_, i) => ({
      label: LABELS[i % LABELS.length],
      x: (rand() - 0.5) * 1.7,
      y: (rand() - 0.5) * 1.5,
      z: 0.35 + rand() * 0.65,
      rot: (rand() - 0.5) * 0.16,
      phase: rand() * Math.PI * 2,
      speed: 0.14 + rand() * 0.3,
      scatter: 0.7 + rand() * 1.1,
    }));

    this.links = [];
    for (let i = 0; i < FRAGS; i++) {
      for (let j = i + 1; j < FRAGS; j++) {
        const a = this.frags[i];
        const b = this.frags[j];
        if (Math.hypot(a.x - b.x, a.y - b.y) < 0.42 && this.links.length < 46 && rand() > 0.35) {
          this.links.push([i, j]);
        }
      }
    }

    this.pages = Array.from({ length: PAGES }, () => {
      const ring = 0.12 + Math.floor(rand() * 7) * 0.09;
      const ang = rand() * Math.PI * 2;
      return {
        hx: Math.cos(ang) * ring,
        hy: Math.sin(ang) * ring * 0.7,
        bx: Math.cos(ang) * ring * (2.6 + rand() * 2.4),
        by: Math.sin(ang) * ring * (2.0 + rand() * 1.8),
        z: 0.3 + rand() * 0.7,
        w: 10 + rand() * 14,
        rot: (rand() - 0.5) * 0.5,
        focus: false,
      };
    });
    let best = 0;
    let bestD = Infinity;
    this.pages.forEach((pg, i) => {
      const d = Math.hypot(pg.hx - 0.08, pg.hy + 0.04);
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    });
    this.focusPage = best;
    this.pages[best].focus = true;
  }

  draw(p, time, mouse) {
    const { ctx, w, h } = fitCanvas(this.canvas);
    ctx.clearRect(0, 0, w, h);

    const cx = w / 2;
    const cy = h / 2;
    const S = Math.min(w, h) * 0.5;

    const env = ramp(p, 0.0, 0.06) * (1 - ramp(p, 0.965, 1.0));
    if (env <= 0.001) return;

    const fragT = ramp(p, 0.42, 0.62);
    const burstT = easeOutExpo(ramp(p, 0.7, 0.8));
    const freezeT = ramp(p, 0.8, 0.84);
    const focusT = easeInOutCubic(ramp(p, 0.86, 0.95));
    const dieT = ramp(p, 0.95, 1.0);

    const mx = mouse.x * 18;
    const my = mouse.y * 12;

    // ---------- fragment field ----------
    const fieldA = env * (1 - ramp(p, 0.66, 0.74));
    if (fieldA > 0.001) {
      const driftScale = 1 - freezeT;
      const pts = this.frags.map((f) => {
        const spread = 1 + fragT * f.scatter * 1.35;
        const dx = Math.sin(time * f.speed + f.phase) * 10 * driftScale;
        const dy = Math.cos(time * f.speed * 0.8 + f.phase) * 8 * driftScale;
        return {
          f,
          x: cx + f.x * spread * S + dx - mx * f.z,
          y: cy + f.y * spread * S * 0.72 + dy - my * f.z,
        };
      });

      const linkA = 0.3 * (1 - fragT) * fieldA;
      if (linkA > 0.01) {
        ctx.lineWidth = 1;
        for (const [i, j] of this.links) {
          const a = pts[i];
          const b = pts[j];
          const breakAt = ((i * 7 + j * 13) % 10) / 10;
          if (fragT > breakAt) continue;
          ctx.strokeStyle = `rgba(102,120,138,${linkA.toFixed(3)})`;
          if (fragT > breakAt - 0.12) ctx.setLineDash([4, 5 + fragT * 14]);
          else ctx.setLineDash([]);
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
        ctx.setLineDash([]);
      }

      for (const { f, x, y } of pts) {
        const a = fieldA * (0.25 + f.z * 0.6);
        const size = (7 + f.z * 8) * (w / 1600 + 0.55);
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(f.rot + fragT * (f.phase - Math.PI) * 0.3);
        ctx.globalAlpha = a;
        ctx.strokeStyle = COLORS.ink3;
        ctx.lineWidth = 1;
        ctx.strokeRect(-size, -size * 0.68, size * 2, size * 1.36);
        ctx.strokeStyle = COLORS.ink2;
        ctx.beginPath();
        ctx.moveTo(-size * 0.7, -size * 0.2);
        ctx.lineTo(size * 0.7, -size * 0.2);
        ctx.moveTo(-size * 0.7, size * 0.18);
        ctx.lineTo(size * 0.35, size * 0.18);
        ctx.stroke();
        ctx.fillStyle = f.z > 0.75 ? COLORS.cyan : COLORS.ink3;
        ctx.font = `${Math.max(8, size * 0.52)}px ${MONO}`;
        ctx.textAlign = "center";
        ctx.fillText(f.label, 0, -size * 0.95);
        ctx.restore();
      }
      ctx.globalAlpha = 1;
    }

    // ---------- 700+ page burst ----------
    const burstA = env * ramp(p, 0.68, 0.74);
    if (burstA > 0.001) {
      const focus = this.pages[this.focusPage];
      const fx = lerp(cx + lerp(focus.hx, focus.bx, burstT) * S, cx, 0.15);
      const fy = lerp(cy + lerp(focus.hy, focus.by, burstT) * S * 0.72, cy, 0.15);
      const zoom = 1 + focusT * 7;

      ctx.save();
      ctx.translate(cx, cy);
      ctx.scale(zoom, zoom);
      ctx.translate(-lerp(cx, fx, focusT), -lerp(cy, fy, focusT));

      for (const pg of this.pages) {
        const x = cx + lerp(pg.hx, pg.bx, burstT) * S - mx * pg.z * 0.4;
        const y = cy + lerp(pg.hy, pg.by, burstT) * S * 0.72 - my * pg.z * 0.4;
        let a = burstA * (0.08 + pg.z * 0.3);
        if (focusT > 0) a = pg.focus ? Math.max(a, burstA * (0.5 + focusT * 0.5)) : a * (1 - focusT);
        if (a <= 0.004) continue;
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(pg.rot * (1 - focusT));
        const pw = pg.w * (w / 1600 + 0.6);
        ctx.globalAlpha = a;
        ctx.strokeStyle = pg.focus ? COLORS.cyan : COLORS.ink3;
        ctx.lineWidth = pg.focus ? 1.4 / zoom : 1;
        ctx.strokeRect(-pw, -pw * 1.3, pw * 2, pw * 2.6);
        if (pg.focus && focusT > 0.25) {
          ctx.globalAlpha = a * ramp(focusT, 0.25, 0.6);
          ctx.strokeStyle = COLORS.ink2;
          for (let li = 0; li < 6; li++) {
            const lw = pw * (li === 0 ? 1.5 : 1.1 - (li % 3) * 0.22);
            ctx.beginPath();
            ctx.moveTo(-pw * 0.7, -pw * 0.9 + li * pw * 0.38);
            ctx.lineTo(-pw * 0.7 + lw, -pw * 0.9 + li * pw * 0.38);
            ctx.stroke();
          }
        }
        ctx.restore();
      }
      ctx.restore();
      ctx.globalAlpha = 1;
    }

    // ---------- die to black ----------
    if (dieT > 0) {
      ctx.fillStyle = `rgba(4,6,9,${(dieT * 0.96).toFixed(3)})`;
      ctx.fillRect(0, 0, w, h);
    }
  }
}
