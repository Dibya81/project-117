import type { ReactNode } from "react";

export type EquipmentStatus = "healthy" | "normal" | "warning" | "fault" | "critical" | "isolated" | "blocked" | "active" | "recovering" | "verified";

export interface EquipmentBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface EquipmentAssetProps {
  box: EquipmentBox;
  id?: string;
  name?: string;
  status?: EquipmentStatus | string;
  selected?: boolean;
  variant?: string;
}

export const palette = {
  stroke: "#53687f",
  dark: "#263342",
  graphite: "#334155",
  steel0: "#f8fafc",
  steel1: "#dbe5ef",
  steel2: "#b9c8d8",
  steel3: "#8498ad",
  highlight: "#f8fafc",
  cyan: "#0891b2",
  blue: "#2563eb",
  green: "#16a34a",
  amber: "#d97706",
  red: "#dc2626",
  orange: "#ea580c",
  violet: "#6d5dfc",
  muted: "#94a3b8",
};

export function statusColor(status: EquipmentAssetProps["status"], selected?: boolean): string {
  if (selected) return palette.blue;
  if (status === "warning") return palette.amber;
  if (status === "fault" || status === "critical" || status === "blocked") return palette.red;
  if (status === "isolated") return palette.muted;
  if (status === "active") return palette.cyan;
  if (status === "recovering" || status === "verified" || status === "healthy") return palette.green;
  return palette.green;
}

export function shellGradient(id: string, a = palette.steel0, b = palette.steel1, c = palette.steel3): ReactNode {
  return (
    <linearGradient id={id} x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stopColor={c} />
      <stop offset="28%" stopColor={b} />
      <stop offset="54%" stopColor={a} />
      <stop offset="78%" stopColor={b} />
      <stop offset="100%" stopColor={c} />
    </linearGradient>
  );
}

export function assetDefs(prefix: string): ReactNode {
  return (
    <defs>
      {shellGradient(`${prefix}-steel`)}
      {shellGradient(`${prefix}-warm`, "#fff7ed", "#fed7aa", "#c2410c")}
      {shellGradient(`${prefix}-cool`, "#ecfeff", "#bae6fd", "#0284c7")}
      {shellGradient(`${prefix}-green`, "#ecfdf5", "#bbf7d0", "#059669")}
      {shellGradient(`${prefix}-violet`, "#eef2ff", "#c7d2fe", "#6d5dfc")}
      <radialGradient id={`${prefix}-sphere`} cx="34%" cy="28%" r="72%">
        <stop offset="0%" stopColor="#fff" />
        <stop offset="48%" stopColor="#dbeafe" />
        <stop offset="100%" stopColor="#60a5fa" />
      </radialGradient>
      <filter id={`${prefix}-shadow`} x="-20%" y="-20%" width="140%" height="150%">
        <feDropShadow dx="0" dy="2" stdDeviation="2.4" floodColor="#0f172a" floodOpacity="0.16" />
      </filter>
    </defs>
  );
}

export function basePlate(b: EquipmentBox, y = 0.9): ReactNode {
  return <rect x={b.x + b.w * 0.08} y={b.y + b.h * y} width={b.w * 0.84} height={Math.max(3, b.h * 0.08)} rx={2} fill="#cbd5e1" stroke={palette.stroke} strokeWidth={1.2} />;
}

export function legs(b: EquipmentBox, n = 2): ReactNode {
  const y0 = b.y + b.h * 0.8;
  const y1 = b.y + b.h * 0.98;
  return (
    <g stroke={palette.stroke} strokeWidth={1.5} strokeLinecap="round">
      {Array.from({ length: n }, (_, i) => {
        const x = b.x + b.w * ((i + 1) / (n + 1));
        return <line key={i} x1={x} y1={y0} x2={x} y2={y1} />;
      })}
      <line x1={b.x + b.w * 0.16} y1={y1} x2={b.x + b.w * 0.84} y2={y1} strokeWidth={2.2} />
    </g>
  );
}

export function verticalShell(b: EquipmentBox, fill: string, opts: { top?: number; bottom?: number; rx?: number } = {}): ReactNode {
  const x = b.x + b.w * 0.18;
  const w = b.w * 0.64;
  const y = b.y + b.h * (opts.top ?? 0.09);
  const h = b.h * ((opts.bottom ?? 0.84) - (opts.top ?? 0.09));
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={opts.rx ?? w / 2} fill={fill} stroke={palette.stroke} strokeWidth={1.6} />
      <ellipse cx={x + w / 2} cy={y + 2} rx={w / 2} ry={Math.max(2, b.h * 0.032)} fill="#d8e2ed" stroke={palette.stroke} strokeWidth={1.2} />
      <ellipse cx={x + w / 2} cy={y + h - 2} rx={w / 2} ry={Math.max(2, b.h * 0.032)} fill="#b6c6d6" stroke={palette.stroke} strokeWidth={1.2} />
    </g>
  );
}

export function horizontalVesselShell(b: EquipmentBox, fill: string): ReactNode {
  const x = b.x + b.w * 0.08;
  const y = b.y + b.h * 0.32;
  const w = b.w * 0.84;
  const h = b.h * 0.38;
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={h / 2} fill={fill} stroke={palette.stroke} strokeWidth={1.6} />
      <ellipse cx={x} cy={y + h / 2} rx={Math.max(2, b.w * 0.022)} ry={h / 2} fill="#c3d0dd" stroke={palette.stroke} strokeWidth={1.1} />
      <ellipse cx={x + w} cy={y + h / 2} rx={Math.max(2, b.w * 0.022)} ry={h / 2} fill="#b5c4d2" stroke={palette.stroke} strokeWidth={1.1} />
    </g>
  );
}

export function ladder(b: EquipmentBox, side: "left" | "right" = "right", y0 = 0.18, y1 = 0.8): ReactNode {
  const x = side === "right" ? b.x + b.w * 0.86 : b.x + b.w * 0.14;
  const rail = b.w * 0.035;
  return (
    <g stroke="#6b7f95" strokeWidth={1} strokeLinecap="round">
      <line x1={x - rail} y1={b.y + b.h * y0} x2={x - rail} y2={b.y + b.h * y1} />
      <line x1={x + rail} y1={b.y + b.h * y0} x2={x + rail} y2={b.y + b.h * y1} />
      {Array.from({ length: 7 }, (_, i) => {
        const y = b.y + b.h * (y0 + ((y1 - y0) * i) / 6);
        return <line key={i} x1={x - rail} y1={y} x2={x + rail} y2={y} />;
      })}
    </g>
  );
}

export function platform(b: EquipmentBox, y: number): ReactNode {
  return (
    <g stroke={palette.stroke} strokeWidth={1.1}>
      <line x1={b.x + b.w * 0.1} y1={b.y + b.h * y} x2={b.x + b.w * 0.9} y2={b.y + b.h * y} />
      <line x1={b.x + b.w * 0.1} y1={b.y + b.h * (y - 0.035)} x2={b.x + b.w * 0.9} y2={b.y + b.h * (y - 0.035)} />
      {Array.from({ length: 5 }, (_, i) => {
        const x = b.x + b.w * (0.16 + i * 0.16);
        return <line key={i} x1={x} y1={b.y + b.h * (y - 0.035)} x2={x} y2={b.y + b.h * y} />;
      })}
    </g>
  );
}

export function ports(b: EquipmentBox, points: Array<[number, number]>): ReactNode {
  return (
    <g>
      {points.map(([px, py], i) => (
        <circle key={i} cx={b.x + b.w * px} cy={b.y + b.h * py} r={Math.max(2, Math.min(b.w, b.h) * 0.025)} fill="#fff" stroke={palette.cyan} strokeWidth={1.2} />
      ))}
    </g>
  );
}

export function statusBeacon(b: EquipmentBox, status: EquipmentAssetProps["status"], selected?: boolean): ReactNode {
  const c = statusColor(status, selected);
  return (
    <g>
      <circle cx={b.x + b.w * 0.86} cy={b.y + b.h * 0.12} r={Math.max(3, Math.min(b.w, b.h) * 0.04)} fill={c} stroke="#fff" strokeWidth={1.1} />
      {(status === "fault" || status === "critical" || status === "warning") && <circle cx={b.x + b.w * 0.86} cy={b.y + b.h * 0.12} r={Math.max(6, Math.min(b.w, b.h) * 0.075)} fill="none" stroke={c} strokeWidth={1} opacity={0.55} />}
    </g>
  );
}

export function tagPlate(b: EquipmentBox, id?: string, name?: string): ReactNode {
  if (!id && !name) return null;
  const label = id ?? name ?? "";
  return (
    <g>
      <rect x={b.x + b.w * 0.18} y={b.y + b.h * 0.01} width={b.w * 0.46} height={Math.max(10, b.h * 0.11)} rx={2} fill="rgba(255,255,255,0.86)" stroke="#cbd5e1" strokeWidth={0.8} />
      <text x={b.x + b.w * 0.41} y={b.y + b.h * 0.085} textAnchor="middle" fontFamily="ui-monospace, monospace" fontSize={Math.max(6, Math.min(11, b.h * 0.07))} fontWeight={800} fill="#1f2937">
        {label}
      </text>
    </g>
  );
}
