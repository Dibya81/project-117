"use client";

/**
 * EquipmentShape — procedural industrial equipment, drawn as the thing itself.
 *
 * This replaces the previous treatment, where every asset was a rounded
 * rectangle containing a generic circular glyph. A box with an icon in it is a
 * node on a diagram; a refinery is not made of nodes. Each function below draws
 * one piece of equipment out of its own primitives — shell, dome, skirt, trays,
 * firebox, saddles, baseplate — with no enclosing frame, so the plant reads as
 * machinery sitting on a plot rather than as cards wired together.
 *
 * Every shape fills the box it is given, so the caller controls scale: a
 * distillation column is handed a tall narrow box, a storage tank a wide low
 * one, a pump a small square. Coordinates are derived from the box, so a shape
 * stays correct at any size.
 */

import type { ReactNode } from "react";

export interface ShapeBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

const stroke = { stroke: "#5b6f86", strokeWidth: 1.6, fill: "none", strokeLinejoin: "round" as const };

/** Legs or a skirt, whichever the vessel type uses. */
function legs(b: ShapeBox, n = 2): ReactNode {
  const y0 = b.y + b.h * 0.86;
  const y1 = b.y + b.h;
  return (
    <g {...stroke}>
      {Array.from({ length: n }, (_, i) => {
        const x = b.x + b.w * ((i + 1) / (n + 1));
        return <line key={i} x1={x} y1={y0} x2={x} y2={y1} />;
      })}
      <line x1={b.x + b.w * 0.16} y1={y1} x2={b.x + b.w * 0.84} y2={y1} strokeWidth={2.4} />
    </g>
  );
}

/** Vertical shell — the body shared by tanks, columns and vertical vessels. */
function shell(b: ShapeBox, opts: { rx: number; top: number; bottom: number; fill: string }): ReactNode {
  const x = b.x + b.w * 0.16;
  const w = b.w * 0.68;
  const y = b.y + b.h * opts.top;
  const h = b.h * (opts.bottom - opts.top);
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={opts.rx} fill={opts.fill} stroke="#5b6f86" strokeWidth={1.6} />
      {/* Dished head, drawn as the ellipse a real head projects. */}
      <ellipse cx={x + w / 2} cy={y + 2} rx={w / 2} ry={b.h * 0.028} fill="#c9d6e4" stroke="#5b6f86" strokeWidth={1.3} />
      <ellipse cx={x + w / 2} cy={y + h - 2} rx={w / 2} ry={b.h * 0.028} fill="#b9c8d9" stroke="#5b6f86" strokeWidth={1.3} />
    </g>
  );
}

export function EquipmentShape({ kind, box, tone = "#5b6f86" }: { kind: string; box: ShapeBox; tone?: string }) {
  const b = box;

  /* ------------------------------------------------------------- storage tank */
  if (kind === "tank") {
    return (
      <g data-shape="tank">
        {/* Cylindrical shell on a ring foundation, domed roof, level gauge. */}
        <rect
          x={b.x + b.w * 0.1}
          y={b.y + b.h * 0.2}
          width={b.w * 0.8}
          height={b.h * 0.58}
          fill="#d6e0ec"
          stroke="#5b6f86"
          strokeWidth={1.7}
        />
        <ellipse cx={b.x + b.w * 0.5} cy={b.y + b.h * 0.2} rx={b.w * 0.4} ry={b.h * 0.07} fill="#c4d2e2" stroke="#5b6f86" strokeWidth={1.5} />
        <ellipse cx={b.x + b.w * 0.5} cy={b.y + b.h * 0.78} rx={b.w * 0.4} ry={b.h * 0.07} fill="#b3c4d6" stroke="#5b6f86" strokeWidth={1.5} />
        {/* Stairway rail — the detail that makes a disc read as a tank. */}
        <line x1={b.x + b.w * 0.1} y1={b.y + b.h * 0.78} x2={b.x + b.w * 0.02} y2={b.y + b.h * 0.94} stroke="#7c8fa4" strokeWidth={1.4} />
        <line x1={b.x + b.w * 0.9} y1={b.y + b.h * 0.78} x2={b.x + b.w * 0.98} y2={b.y + b.h * 0.94} stroke="#7c8fa4" strokeWidth={1.4} />
        <rect x={b.x + b.w * 0.04} y={b.y + b.h * 0.94} width={b.w * 0.92} height={b.h * 0.06} rx={2} fill="#cbd5e1" stroke="#5b6f86" strokeWidth={1.3} />
        {/* Level gauge on the shell. */}
        <rect x={b.x + b.w * 0.86} y={b.y + b.h * 0.36} width={b.w * 0.033} height={b.h * 0.26} rx={2} fill="#2f7fd4" opacity={0.85} />
      </g>
    );
  }

  /* --------------------------------------------------------- distillation column */
  if (kind === "column") {
    const x = b.x + b.w * 0.2;
    const w = b.w * 0.6;
    return (
      <g data-shape="column">
        {shell(b, { rx: w / 2, top: 0.08, bottom: 0.86, fill: "#dbe4ee" })}
        {/* Trays: the horizontal decks inside a real tower. */}
        <g stroke="rgba(51,65,85,0.5)" strokeWidth={1.2}>
          {Array.from({ length: 10 }, (_, i) => {
            const y = b.y + b.h * 0.15 + (i * b.h * 0.62) / 9;
            return <line key={i} x1={x + 2} y1={y} x2={x + w - 2} y2={y} />;
          })}
        </g>
        {/* Skirt and draw nozzles. */}
        <line x1={b.x + b.w * 0.34} y1={b.y + b.h * 0.86} x2={b.x + b.w * 0.34} y2={b.y + b.h} {...stroke} strokeWidth={2} />
        <line x1={b.x + b.w * 0.66} y1={b.y + b.h * 0.86} x2={b.x + b.w * 0.66} y2={b.y + b.h} {...stroke} strokeWidth={2} />
        <line x1={b.x + b.w * 0.8} y1={b.y + b.h * 0.3} x2={b.x + b.w} y2={b.y + b.h * 0.3} {...stroke} />
        <line x1={b.x + b.w * 0.8} y1={b.y + b.h * 0.62} x2={b.x + b.w} y2={b.y + b.h * 0.62} {...stroke} />
      </g>
    );
  }

  /* ------------------------------------------------------------------ furnace */
  if (kind === "furnace") {
    return (
      <g data-shape="furnace">
        <rect x={b.x + b.w * 0.06} y={b.y + b.h * 0.12} width={b.w * 0.88} height={b.h * 0.74} rx={3} fill="#e3dcd3" stroke="#5b6f86" strokeWidth={1.7} />
        {/* Firebox with flame — what makes it a furnace and not a box. */}
        <rect x={b.x + b.w * 0.16} y={b.y + b.h * 0.5} width={b.w * 0.68} height={b.h * 0.34} rx={3} fill="#3d2618" stroke="#2a1a10" strokeWidth={1.2} />
        <g className="eq-flame">
          {[0.3, 0.5, 0.7].map((fx, i) => (
            <path
              key={i}
              d={`M ${b.x + b.w * fx} ${b.y + b.h * 0.82} q ${-b.w * 0.045} ${-b.h * 0.14} 0 ${-b.h * 0.24} q ${b.w * 0.045} ${b.h * 0.1} 0 ${b.h * 0.24} z`}
              fill="#f59e0b"
            />
          ))}
        </g>
        {/* Convection section tubes and stack. */}
        <g stroke="#8b9aab" strokeWidth={1.1}>
          {Array.from({ length: 5 }, (_, i) => (
            <line key={i} x1={b.x + b.w * 0.12} y1={b.y + b.h * (0.2 + i * 0.05)} x2={b.x + b.w * 0.88} y2={b.y + b.h * (0.2 + i * 0.05)} />
          ))}
        </g>
        <rect x={b.x + b.w * 0.7} y={b.y} width={b.w * 0.1} height={b.h * 0.14} fill="#c3ccd6" stroke="#5b6f86" strokeWidth={1.3} />
      </g>
    );
  }

  /* ------------------------------------------------------------- heat exchanger */
  if (kind === "exchanger") {
    return (
      <g data-shape="exchanger">
        {legs(b, 2)}
        <rect x={b.x + b.w * 0.08} y={b.y + b.h * 0.3} width={b.w * 0.84} height={b.h * 0.42} rx={b.h * 0.21} fill="#dbe7e6" stroke="#5b6f86" strokeWidth={1.7} />
        {/* Channel ends and tube bundle. */}
        <ellipse cx={b.x + b.w * 0.08} cy={b.y + b.h * 0.51} rx={b.w * 0.02} ry={b.h * 0.21} fill="#c3d4d2" stroke="#5b6f86" strokeWidth={1.3} />
        <ellipse cx={b.x + b.w * 0.92} cy={b.y + b.h * 0.51} rx={b.w * 0.02} ry={b.h * 0.21} fill="#c3d4d2" stroke="#5b6f86" strokeWidth={1.3} />
        <g stroke="rgba(51,65,85,0.35)" strokeWidth={1}>
          {Array.from({ length: 6 }, (_, i) => (
            <line key={i} x1={b.x + b.w * 0.12} y1={b.y + b.h * (0.36 + i * 0.06)} x2={b.x + b.w * 0.88} y2={b.y + b.h * (0.36 + i * 0.06)} />
          ))}
        </g>
      </g>
    );
  }

  /* ------------------------------------------------------------ pressure vessel */
  if (kind === "vessel") {
    return (
      <g data-shape="vessel">
        {shell(b, { rx: b.w * 0.34, top: 0.1, bottom: 0.88, fill: "#dde6f0" })}
        <line x1={b.x + b.w * 0.16} y1={b.y + b.h * 0.5} x2={b.x + b.w * 0.84} y2={b.y + b.h * 0.5} stroke="rgba(51,65,85,0.4)" strokeWidth={1.2} />
        {legs(b, 2)}
      </g>
    );
  }

  /* --------------------------------------------------------------------- pump */
  if (kind === "pump") {
    const cy = b.y + b.h * 0.56;
    return (
      <g data-shape="pump">
        <rect x={b.x + b.w * 0.04} y={b.y + b.h * 0.86} width={b.w * 0.92} height={b.h * 0.14} rx={2} fill="#cbd5e1" stroke="#5b6f86" strokeWidth={1.4} />
        {/* Volute casing with discharge, then the motor. */}
        <circle cx={b.x + b.w * 0.32} cy={cy} r={b.h * 0.26} fill="#dbe5f0" stroke="#5b6f86" strokeWidth={1.7} />
        <circle cx={b.x + b.w * 0.32} cy={cy} r={b.h * 0.09} fill="#b6c7da" stroke="#5b6f86" strokeWidth={1.2} />
        <path d={`M ${b.x + b.w * 0.32} ${cy - b.h * 0.26} v ${-b.h * 0.2}`} {...stroke} strokeWidth={1.8} />
        <rect x={b.x + b.w * 0.52} y={cy - b.h * 0.17} width={b.w * 0.44} height={b.h * 0.34} rx={3} fill="#cfd9e6" stroke="#5b6f86" strokeWidth={1.6} />
        <g stroke="rgba(51,65,85,0.35)" strokeWidth={1}>
          {Array.from({ length: 4 }, (_, i) => (
            <line key={i} x1={b.x + b.w * (0.58 + i * 0.09)} y1={cy - b.h * 0.17} x2={b.x + b.w * (0.58 + i * 0.09)} y2={cy + b.h * 0.17} />
          ))}
        </g>
      </g>
    );
  }

  /* --------------------------------------------------------------- compressor */
  if (kind === "compressor") {
    return (
      <g data-shape="compressor">
        <rect x={b.x + b.w * 0.05} y={b.y + b.h * 0.84} width={b.w * 0.9} height={b.h * 0.16} rx={2} fill="#cbd5e1" stroke="#5b6f86" strokeWidth={1.4} />
        <circle cx={b.x + b.w * 0.34} cy={b.y + b.h * 0.5} r={b.h * 0.3} fill="#dfe3f2" stroke="#5b6f86" strokeWidth={1.7} />
        <circle cx={b.x + b.w * 0.34} cy={b.y + b.h * 0.5} r={b.h * 0.15} fill="#c2c8e0" stroke="#5b6f86" strokeWidth={1.2} />
        <rect x={b.x + b.w * 0.58} y={b.y + b.h * 0.3} width={b.w * 0.38} height={b.h * 0.4} rx={4} fill="#d3d8ea" stroke="#5b6f86" strokeWidth={1.6} />
      </g>
    );
  }

  /* -------------------------------------------------------------------- motor */
  if (kind === "motor") {
    return (
      <g data-shape="motor">
        <rect x={b.x + b.w * 0.06} y={b.y + b.h * 0.86} width={b.w * 0.88} height={b.h * 0.14} rx={2} fill="#cbd5e1" stroke="#5b6f86" strokeWidth={1.4} />
        <rect x={b.x + b.w * 0.12} y={b.y + b.h * 0.26} width={b.w * 0.76} height={b.h * 0.6} rx={b.h * 0.16} fill="#dae1ec" stroke="#5b6f86" strokeWidth={1.7} />
        <g stroke="rgba(51,65,85,0.35)" strokeWidth={1}>
          {Array.from({ length: 5 }, (_, i) => (
            <line key={i} x1={b.x + b.w * (0.2 + i * 0.14)} y1={b.y + b.h * 0.26} x2={b.x + b.w * (0.2 + i * 0.14)} y2={b.y + b.h * 0.86} />
          ))}
        </g>
      </g>
    );
  }

  /* -------------------------------------------------------------------- valve */
  if (kind === "valve") {
    const cy = b.y + b.h * 0.58;
    const r = b.h * 0.2;
    return (
      <g data-shape="valve">
        <path d={`M ${b.x + b.w * 0.12} ${cy - r} L ${b.x + b.w * 0.12} ${cy + r} L ${b.x + b.w * 0.5} ${cy} Z`} fill="#d8e1ec" stroke="#5b6f86" strokeWidth={1.6} />
        <path d={`M ${b.x + b.w * 0.88} ${cy - r} L ${b.x + b.w * 0.88} ${cy + r} L ${b.x + b.w * 0.5} ${cy} Z`} fill="#d8e1ec" stroke="#5b6f86" strokeWidth={1.6} />
        <line x1={b.x + b.w * 0.5} y1={cy - r} x2={b.x + b.w * 0.5} y2={b.y + b.h * 0.18} {...stroke} strokeWidth={1.5} />
        <rect x={b.x + b.w * 0.32} y={b.y + b.h * 0.06} width={b.w * 0.36} height={b.h * 0.12} rx={2} fill="#c3ccd6" stroke="#5b6f86" strokeWidth={1.3} />
      </g>
    );
  }

  /* ----------------------------------------------------- safety / ESD panel */
  if (kind === "safety") {
    return (
      <g data-shape="safety">
        <rect x={b.x + b.w * 0.16} y={b.y + b.h * 0.14} width={b.w * 0.68} height={b.h * 0.72} rx={4} fill="#f6e0e0" stroke="#b91c1c" strokeWidth={1.7} />
        <circle cx={b.x + b.w * 0.5} cy={b.y + b.h * 0.34} r={b.h * 0.1} fill="#dc2626" />
        <g stroke="#b91c1c" strokeWidth={1.4}>
          <line x1={b.x + b.w * 0.28} y1={b.y + b.h * 0.58} x2={b.x + b.w * 0.72} y2={b.y + b.h * 0.58} />
          <line x1={b.x + b.w * 0.28} y1={b.y + b.h * 0.7} x2={b.x + b.w * 0.72} y2={b.y + b.h * 0.7} />
        </g>
      </g>
    );
  }

  /* ------------------------------------------------------- generic machine */
  return (
    <g data-shape="utility">
      <rect x={b.x + b.w * 0.1} y={b.y + b.h * 0.22} width={b.w * 0.8} height={b.h * 0.64} rx={4} fill="#dde5ee" stroke="#5b6f86" strokeWidth={1.7} />
      <rect x={b.x + b.w * 0.24} y={b.y + b.h * 0.4} width={b.w * 0.52} height={b.h * 0.28} rx={3} fill="#c6d2e0" stroke="#5b6f86" strokeWidth={1.2} />
      <line x1={b.x + b.w * 0.5} y1={b.y + b.h * 0.22} x2={b.x + b.w * 0.5} y2={b.y + b.h * 0.06} stroke="#5b6f86" strokeWidth={1.5} />
      <circle cx={b.x + b.w * 0.5} cy={b.y + b.h * 0.05} r={b.h * 0.05} fill="#cbd5e1" stroke="#5b6f86" strokeWidth={1.2} />
    </g>
  );
}
