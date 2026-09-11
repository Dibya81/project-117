"use client";

/**
 * TrendChart — lightweight SVG trend with animated stroke draw, gradient
 * area fill, threshold band and a glowing live head. No chart dependency.
 */
import { useEffect, useRef, useState } from "react";

const TONES = {
  cyan: { stroke: "#45d5ff", fill: "rgba(69,213,255,.14)", glow: "rgba(69,213,255,.5)" },
  amber: { stroke: "#ffb454", fill: "rgba(255,180,84,.13)", glow: "rgba(255,180,84,.5)" },
  green: { stroke: "#3ddc97", fill: "rgba(61,220,151,.12)", glow: "rgba(61,220,151,.5)" },
  red: { stroke: "#ff5d5d", fill: "rgba(255,93,93,.12)", glow: "rgba(255,93,93,.5)" },
  ember: { stroke: "#ff7a3d", fill: "rgba(255,122,61,.13)", glow: "rgba(255,122,61,.5)" },
} as const;

export function TrendChart({
  points,
  height = 96,
  threshold,
  critThreshold,
  unit,
  tone = "cyan",
  live = false,
}: {
  points: { t: number; value: number }[];
  height?: number;
  threshold?: number;
  critThreshold?: number;
  unit?: string;
  tone?: keyof typeof TONES;
  live?: boolean;
}) {
  const pathRef = useRef<SVGPathElement>(null);
  const [drawn, setDrawn] = useState(false);

  useEffect(() => {
    // stroke-draw on mount
    const path = pathRef.current;
    if (!path) return;
    const len = path.getTotalLength();
    path.style.strokeDasharray = `${len}`;
    path.style.strokeDashoffset = `${len}`;
    const raf = requestAnimationFrame(() => {
      path.style.transition = "stroke-dashoffset 1100ms cubic-bezier(.16,1,.3,1)";
      path.style.strokeDashoffset = "0";
      setDrawn(true);
    });
    return () => cancelAnimationFrame(raf);
  }, [points]);

  if (!points.length) return null;
  const W = 320;
  const H = height;
  const values = points.map((p) => p.value);
  const min = Math.min(...values, threshold ?? Infinity, critThreshold ?? Infinity);
  const max = Math.max(...values, threshold ?? -Infinity, critThreshold ?? -Infinity);
  const span = max - min || 1;
  const x = (i: number) => (i / (points.length - 1)) * (W - 12) + 6;
  const y = (v: number) => H - 10 - ((v - min) / span) * (H - 20);

  const d = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)} ${y(p.value).toFixed(1)}`).join(" ");
  const area = `${d} L${x(points.length - 1).toFixed(1)} ${H - 2} L${x(0).toFixed(1)} ${H - 2} Z`;
  const c = TONES[tone];
  const last = points[points.length - 1];

  return (
    <figure style={{ margin: 0 }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img" aria-label={`Trend, latest ${last.value}${unit ? ` ${unit}` : ""}`}>
        <defs>
          <linearGradient id={`tc-${tone}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={c.fill} />
            <stop offset="100%" stopColor="transparent" />
          </linearGradient>
        </defs>

        {/* threshold zone + line */}
        {threshold != null && (
          <>
            <rect x={0} y={0} width={W} height={y(threshold)} fill="rgba(255,93,93,.045)" />
            <line x1={0} x2={W} y1={y(threshold)} y2={y(threshold)} stroke="#ffb454" strokeWidth="1" strokeDasharray="4 5" opacity="0.75" />
            <text x={W - 5} y={Math.max(9, y(threshold) - 5)} textAnchor="end" fill="#ffb454" fontSize="8" fontFamily="ui-monospace, monospace">
              warn {threshold}{unit ? ` ${unit}` : ""}
            </text>
          </>
        )}
        {critThreshold != null && (
          <line x1={0} x2={W} y1={y(critThreshold)} y2={y(critThreshold)} stroke="#ff5d5d" strokeWidth="1" strokeDasharray="2 4" opacity="0.8" />
        )}

        <path d={area} fill={`url(#tc-${tone})`} opacity={drawn ? 1 : 0} style={{ transition: "opacity 900ms ease 500ms" }} />
        <path ref={pathRef} d={d} fill="none" stroke={c.stroke} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />

        {/* live head */}
        <circle cx={x(points.length - 1)} cy={y(last.value)} r="6" fill={c.glow} opacity={drawn ? 0.35 : 0} className={live ? "cs-chart-livehalo" : undefined} />
        <circle cx={x(points.length - 1)} cy={y(last.value)} r="2.8" fill={c.stroke} opacity={drawn ? 1 : 0} style={{ transition: "opacity 300ms ease 1000ms" }} />
      </svg>
      <figcaption className="cs-mono cs-dim" style={{ fontSize: 10, display: "flex", justifyContent: "space-between" }}>
        <span>{new Date(points[0].t).toLocaleDateString()}</span>
        <span style={{ color: c.stroke }}>latest {last.value}{unit ? ` ${unit}` : ""}</span>
      </figcaption>
    </figure>
  );
}
