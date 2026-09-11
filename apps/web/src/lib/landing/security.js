/**
 * Section 3 engine — the security boundary and the particle reveal hand-off.
 * A confidential document drifts toward a boundary; on contact the boundary
 * fractures and the far side becomes inaccessible. Then "BRING THE
 * INTELLIGENCE." is rasterized, sampled into particles which blow outward
 * and converge into a single core — the seed of Section 4.
 * draw(p, time): p is section-local progress 0..1.
 */
import { COLORS, MONO, clamp01, easeInOutCubic, easeOutCubic, lerp, ramp, rng, fitCanvas } from "./easing.js";

export class SecurityScene {
  constructor(canvas) {
    this.canvas = canvas;
    this.rand = rng(717);
    this.particles = null;
    this.jag = Array.from({ length: 26 }, () => this.rand() * 2 - 1);
  }

  buildParticles(w, h) {
    const off = document.createElement("canvas");
    off.width = w;
    off.height = h;
    const octx = off.getContext("2d", { willReadFrequently: true });
    octx.fillStyle = "#fff";
    octx.textAlign = "center";
    octx.textBaseline = "middle";
    const px = Math.min(w * 0.085, 120);
    octx.font = `800 ${px}px ui-monospace, monospace, sans-serif`;
    octx.fillText("BRING THE", w / 2, h / 2 - px * 0.55);
    octx.fillText("INTELLIGENCE.", w / 2, h / 2 + px * 0.55);
    const data = octx.getImageData(0, 0, w, h).data;
    const pts = [];
    const step = Math.max(4, Math.round(w / 260));
    for (let y = 0; y < h; y += step) {
      for (let x = 0; x < w; x += step) {
        if (data[(y * w + x) * 4 + 3] > 120) pts.push([x, y]);
      }
    }
    const rand = this.rand;
    const picked = [];
    const target = Math.min(340, pts.length);
    for (let i = 0; i < target && pts.length; i++) picked.push(pts[Math.floor(rand() * pts.length)]);
    this.particles = picked.map(([x, y]) => {
      const ang = Math.atan2(y - h / 2, x - w / 2) + (rand() - 0.5) * 0.9;
      const dist = (0.35 + rand() * 0.75) * Math.min(w, h);
      return {
        tx: x,
        ty: y,
        mx: x + Math.cos(ang) * dist,
        my: y + Math.sin(ang) * dist * 0.8,
        swirl: (rand() - 0.5) * 2.4,
        r: 0.8 + rand() * 1.6,
        delay: rand() * 0.25,
      };
    });
  }

  draw(p, time) {
    const { ctx, w, h } = fitCanvas(this.canvas);
    ctx.clearRect(0, 0, w, h);

    const env = ramp(p, 0.0, 0.04) * (1 - ramp(p, 0.985, 1.0));
    if (env <= 0.001) return;

    const boundaryX = w * 0.62;
    const cy = h / 2;

    // ---------- phase A: document approaches the boundary ----------
    const phaseA = 1 - ramp(p, 0.42, 0.52);
    if (phaseA > 0.001) {
      const boundaryA = ramp(p, 0.1, 0.2) * phaseA;
      const contact = ramp(p, 0.3, 0.34);
      const fracture = ramp(p, 0.34, 0.48);

      if (fracture > 0.001) {
        ctx.fillStyle = `rgba(3,5,8,${(fracture * 0.8 * phaseA).toFixed(3)})`;
        ctx.fillRect(boundaryX, 0, w - boundaryX, h);
        ctx.strokeStyle = `rgba(239,68,68,${(0.1 * fracture * phaseA).toFixed(3)})`;
        ctx.lineWidth = 1;
        const gap = 26;
        for (let x = boundaryX + gap; x < w + h; x += gap) {
          ctx.beginPath();
          ctx.moveTo(x, 0);
          ctx.lineTo(x - h, h);
          ctx.stroke();
        }
      }

      if (boundaryA > 0.001) {
        ctx.strokeStyle = `rgba(232,113,58,${(0.85 * boundaryA).toFixed(3)})`;
        ctx.lineWidth = 2;
        ctx.beginPath();
        const segs = this.jag.length;
        for (let i = 0; i <= segs; i++) {
          const y = (i / segs) * h;
          const jx = this.jag[i % segs] * 9 * fracture;
          if (i === 0) ctx.moveTo(boundaryX + jx, y);
          else ctx.lineTo(boundaryX + jx, y);
        }
        ctx.stroke();
      }

      const flash = Math.max(0, 1 - Math.abs(p - 0.335) / 0.02) * phaseA;
      if (flash > 0.001) {
        const g = ctx.createRadialGradient(boundaryX, cy, 0, boundaryX, cy, 160);
        g.addColorStop(0, `rgba(239,68,68,${(0.5 * flash).toFixed(3)})`);
        g.addColorStop(1, "rgba(239,68,68,0)");
        ctx.fillStyle = g;
        ctx.fillRect(boundaryX - 160, cy - 160, 320, 320);
      }

      const docA = ramp(p, 0.03, 0.1) * phaseA;
      if (docA > 0.001) {
        const approach = easeInOutCubic(ramp(p, 0.06, 0.33));
        const shake = contact * Math.max(0, 1 - fracture) * Math.sin(time * 46) * 2.2;
        const dw = Math.max(30, w * 0.028);
        const dx = lerp(w * 0.24, boundaryX - dw * 1.6, approach) + shake;
        const dy = cy + Math.sin(time * 0.7) * 6 * (1 - contact);
        ctx.save();
        ctx.translate(dx, dy);
        ctx.globalAlpha = docA;
        ctx.fillStyle = "rgba(22,30,41,0.92)";
        ctx.strokeStyle = COLORS.ink2;
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.rect(-dw, -dw * 1.32, dw * 2, dw * 2.64);
        ctx.fill();
        ctx.stroke();
        ctx.strokeStyle = COLORS.ink3;
        for (let li = 0; li < 7; li++) {
          const lw = dw * (li === 0 ? 1.5 : 1.15 - (li % 3) * 0.25);
          ctx.beginPath();
          ctx.moveTo(-dw * 0.75, -dw * 0.95 + li * dw * 0.34);
          ctx.lineTo(-dw * 0.75 + lw, -dw * 0.95 + li * dw * 0.34);
          ctx.stroke();
        }
        ctx.fillStyle = COLORS.orange;
        ctx.font = `${Math.max(8, dw * 0.24)}px ${MONO}`;
        ctx.textAlign = "center";
        ctx.fillText("CONFIDENTIAL", 0, -dw * 1.52);
        ctx.restore();
        ctx.globalAlpha = 1;
      }
    }

    // ---------- phase B: particle text converges ----------
    const phaseB = ramp(p, 0.6, 0.66);
    if (phaseB > 0.001) {
      if (!this.particles) this.buildParticles(w, h);
      if (!this.particles.length) return;
      const explode = easeOutCubic(ramp(p, 0.62, 0.72));
      const converge = easeInOutCubic(ramp(p, 0.74, 0.94));
      const cx = w / 2;
      const cyy = h / 2;

      for (const pt of this.particles) {
        const local = clamp01((converge - pt.delay * 0.4) / (1 - pt.delay * 0.4));
        const bx = lerp(pt.tx, pt.mx, explode);
        const by = lerp(pt.ty, pt.my, explode);
        const orbit = (1 - local) * 90 * pt.swirl;
        const homeX = cx + Math.cos(pt.swirl * 6) * orbit;
        const homeY = cyy + Math.sin(pt.swirl * 6) * orbit * 0.5;
        const x = lerp(bx, homeX, local);
        const y = lerp(by, homeY, local);
        const a = phaseB * (0.35 + 0.65 * Math.max(explode, local)) * (1 - local * 0.55);
        ctx.fillStyle = `rgba(70,184,232,${a.toFixed(3)})`;
        ctx.beginPath();
        ctx.arc(x, y, pt.r, 0, Math.PI * 2);
        ctx.fill();
      }

      const core = ramp(p, 0.9, 0.97);
      if (core > 0.001) {
        const pulse = 1 + Math.sin(time * 3.2) * 0.12;
        const r = (3 + core * 5) * pulse;
        const g = ctx.createRadialGradient(cx, cyy, 0, cx, cyy, r * 9);
        g.addColorStop(0, `rgba(233,238,244,${(0.95 * core).toFixed(3)})`);
        g.addColorStop(0.25, `rgba(70,184,232,${(0.5 * core).toFixed(3)})`);
        g.addColorStop(1, "rgba(70,184,232,0)");
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(cx, cyy, r * 9, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }
}
