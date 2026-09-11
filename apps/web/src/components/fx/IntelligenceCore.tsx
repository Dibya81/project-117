"use client";

/**
 * IntelligenceCore — sovereign AI visualization.
 * An isometric-style orbiting node system built directly in Three.js r3f.
 * Represents the Project 117 intelligence lattice: core node → agent ring →
 * knowledge ring → live telemetry particles.
 * Runs in an isolated container; does NOT cover DOM.
 */

import { useEffect, useRef } from "react";

interface Props {
  size?: "full" | "compact";
  className?: string;
  style?: React.CSSProperties;
}

export function IntelligenceCore({ size = "full", className, style }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let W = canvas.offsetWidth;
    let H = canvas.offsetHeight;
    const DPR = Math.min(window.devicePixelRatio, 2);

    function resize() {
      if (!canvas || !ctx) return;
      W = canvas.offsetWidth;
      H = canvas.offsetHeight;
      canvas.width = W * DPR;
      canvas.height = H * DPR;
      ctx.scale(DPR, DPR);
    }
    resize();

    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    // ---------- scene state ----------
    const t0 = performance.now();

    // Agent node definitions
    const AGENT_NODES = [
      { label: "DATA", color: "#45d5ff", r: 1.0 },
      { label: "MAINT", color: "#ffb454", r: 1.15 },
      { label: "OPS", color: "#3ddc97", r: 0.85 },
      { label: "SAFETY", color: "#ff5d5d", r: 1.05 },
      { label: "DOCS", color: "#b79cff", r: 0.95 },
    ];

    // Knowledge ring
    const K_COUNT = 12;
    const K_NODES = Array.from({ length: K_COUNT }, (_, i) => ({
      angle: (i / K_COUNT) * Math.PI * 2,
      color: i % 3 === 0 ? "#b79cff" : i % 3 === 1 ? "#45d5ff33" : "#3ddc9733",
      size: i % 4 === 0 ? 3 : 2,
      speed: 0.18 + (i % 5) * 0.04,
    }));

    // Particles streaming between nodes
    const particles: Array<{
      from: [number, number]; to: [number, number]; t: number; speed: number;
      color: string; size: number;
    }> = [];

    function spawnParticle(cx: number, cy: number, agentAngles: number[], agentR: number) {
      const a = agentAngles[Math.floor(Math.random() * agentAngles.length)];
      const outward = Math.random() > 0.5;
      const from: [number, number] = outward ? [cx, cy] : [
        cx + Math.cos(a) * agentR, cy + Math.sin(a) * agentR
      ];
      const to: [number, number] = outward ? [
        cx + Math.cos(a) * agentR, cy + Math.sin(a) * agentR
      ] : [cx, cy];
      particles.push({
        from, to, t: 0,
        speed: 0.006 + Math.random() * 0.008,
        color: AGENT_NODES[Math.floor(Math.random() * AGENT_NODES.length)].color,
        size: 1.5 + Math.random(),
      });
    }

    // ---------- draw ----------
    let frame = 0;
    function draw() {
      if (!ctx) return;
      const elapsed = (performance.now() - t0) / 1000;
      ctx.clearRect(0, 0, W, H);

      const cx = W / 2;
      const cy = H / 2;
      const baseR = Math.min(W, H) * (size === "compact" ? 0.22 : 0.28);
      const agentR = baseR;
      const knowledgeR = baseR * 1.7;

      // Atmosphere glow
      const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, baseR * 2.2);
      grad.addColorStop(0, "rgba(69,213,255,0.055)");
      grad.addColorStop(0.5, "rgba(69,213,255,0.018)");
      grad.addColorStop(1, "transparent");
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, W, H);

      // Knowledge ring
      K_NODES.forEach((kn, i) => {
        const angle = kn.angle + elapsed * kn.speed * (i % 2 === 0 ? 1 : -1);
        const kx = cx + Math.cos(angle) * knowledgeR;
        const ky = cy + Math.sin(angle) * knowledgeR;

        // Line to center
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(kx, ky);
        ctx.strokeStyle = kn.color.length > 7 ? kn.color : kn.color + "18";
        ctx.lineWidth = 0.5;
        ctx.stroke();

        // Node dot
        ctx.beginPath();
        ctx.arc(kx, ky, kn.size, 0, Math.PI * 2);
        ctx.fillStyle = kn.color;
        ctx.fill();
      });

      // Agent orbit ring (dashed)
      ctx.beginPath();
      ctx.arc(cx, cy, agentR, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(69,213,255,0.1)";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 8]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Knowledge ring guide
      ctx.beginPath();
      ctx.arc(cx, cy, knowledgeR, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(183,156,255,0.06)";
      ctx.lineWidth = 1;
      ctx.stroke();

      // Agent nodes
      const agentAngles = AGENT_NODES.map((_, i) =>
        (i / AGENT_NODES.length) * Math.PI * 2 + elapsed * 0.12
      );

      AGENT_NODES.forEach((agent, i) => {
        const angle = agentAngles[i];
        const ax = cx + Math.cos(angle) * agentR;
        const ay = cy + Math.sin(angle) * agentR;

        // Connection line to core
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(ax, ay);
        ctx.strokeStyle = agent.color + "40";
        ctx.lineWidth = 1;
        ctx.stroke();

        // Agent glow
        const g2 = ctx.createRadialGradient(ax, ay, 0, ax, ay, 14 * agent.r);
        g2.addColorStop(0, agent.color + "55");
        g2.addColorStop(1, "transparent");
        ctx.fillStyle = g2;
        ctx.fillRect(ax - 14, ay - 14, 28, 28);

        // Agent node
        const pulse = 1 + Math.sin(elapsed * 2.4 + i * 1.2) * 0.15;
        ctx.beginPath();
        ctx.arc(ax, ay, 5 * agent.r * pulse, 0, Math.PI * 2);
        ctx.fillStyle = agent.color;
        ctx.fill();

        // Label
        if (size === "full") {
          ctx.fillStyle = agent.color;
          ctx.font = `500 8px "JetBrains Mono", monospace`;
          ctx.textAlign = "center";
          ctx.fillText(agent.label, ax, ay + 16);
        }
      });

      // Particles
      if (frame % 18 === 0) spawnParticle(cx, cy, agentAngles, agentR);
      for (let j = particles.length - 1; j >= 0; j--) {
        const p = particles[j];
        p.t += p.speed;
        if (p.t >= 1) { particles.splice(j, 1); continue; }
        const px = p.from[0] + (p.to[0] - p.from[0]) * p.t;
        const py = p.from[1] + (p.to[1] - p.from[1]) * p.t;
        const alpha = Math.sin(p.t * Math.PI);
        ctx.beginPath();
        ctx.arc(px, py, p.size, 0, Math.PI * 2);
        ctx.fillStyle = p.color + Math.round(alpha * 255).toString(16).padStart(2, "0");
        ctx.fill();
      }

      // Core node — the sovereign AI
      const coreGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, 18);
      coreGrad.addColorStop(0, "#45d5ff");
      coreGrad.addColorStop(0.4, "#1a8ab5");
      coreGrad.addColorStop(1, "#0a2540");
      ctx.beginPath();
      ctx.arc(cx, cy, 10 + Math.sin(elapsed * 1.8) * 1.5, 0, Math.PI * 2);
      ctx.fillStyle = coreGrad;
      ctx.fill();

      // Core outer ring
      ctx.beginPath();
      ctx.arc(cx, cy, 16, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(69,213,255,0.5)";
      ctx.lineWidth = 1;
      ctx.stroke();

      // Core label
      if (size === "full") {
        ctx.fillStyle = "#eaf2fa";
        ctx.font = `600 9px "JetBrains Mono", monospace`;
        ctx.textAlign = "center";
        ctx.fillText("P-117", cx, cy + 3);
      }

      frame++;
      rafRef.current = requestAnimationFrame(draw);
    }

    draw();
    return () => {
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
    };
  }, [size]);

  return (
    <canvas
      ref={canvasRef}
      className={className}
      style={{
        width: "100%",
        height: "100%",
        display: "block",
        pointerEvents: "none",
        ...style,
      }}
    />
  );
}
