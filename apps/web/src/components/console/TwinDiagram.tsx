"use client";

/**
 * TwinDiagram — procedural technical schematic of an asset (per kind), with
 * sensors living spatially on the machine. Hover = live reading; click =
 * jump to that sensor's telemetry. Pure SVG linework — instrumentation,
 * not decoration.
 */
import { useState } from "react";
import type { HealthState, SensorReading } from "@/types";

const SENSOR_STATE = (s: SensorReading): HealthState =>
  s.critAbove != null && s.value >= s.critAbove ? "critical" : s.warnAbove != null && s.value >= s.warnAbove ? "warning" : "ok";

const STATE_COLOR: Record<HealthState, string> = {
  ok: "#3ddc97",
  warning: "#ffb454",
  critical: "#ff5d5d",
  unknown: "#5b6c81",
};

/** Hotspot anchors per equipment kind, in viewBox coordinates (0..100). */
const ANCHORS: Record<string, [number, number][]> = {
  compressor: [[30, 38], [62, 30], [72, 62]],
  pump: [[34, 56], [62, 34], [66, 62]],
  tank: [[50, 34], [50, 66], [76, 50]],
  valve: [[50, 30], [30, 58], [68, 58]],
  exchanger: [[30, 42], [56, 30], [70, 58]],
};

function Schematic({ kind }: { kind: string }) {
  const stroke = "rgba(157,177,199,0.55)";
  const faint = "rgba(140,180,220,0.16)";
  switch (kind) {
    case "compressor":
      return (
        <g stroke={stroke} fill="none" strokeWidth="1.4">
          <rect x="26" y="34" width="44" height="26" rx="4" />
          <circle cx="38" cy="47" r="7" />
          <circle cx="38" cy="47" r="3" strokeDasharray="2 3" />
          <line x1="70" y1="47" x2="86" y2="47" />
          <line x1="78" y1="42" x2="86" y2="47" />
          <line x1="78" y1="52" x2="86" y2="47" />
          <line x1="30" y1="60" x2="30" y2="70" stroke={faint} />
          <line x1="66" y1="60" x2="66" y2="70" stroke={faint} />
          <line x1="22" y1="70" x2="74" y2="70" stroke={faint} />
        </g>
      );
    case "pump":
      return (
        <g stroke={stroke} fill="none" strokeWidth="1.4">
          <circle cx="46" cy="48" r="16" />
          <path d="M46 32 A16 16 0 0 1 62 48 L46 48 Z" strokeDasharray="3 3" />
          <line x1="46" y1="16" x2="46" y2="32" />
          <rect x="41" y="10" width="10" height="7" rx="1.5" />
          <line x1="62" y1="48" x2="84" y2="48" />
          <line x1="16" y1="48" x2="30" y2="48" />
          <line x1="34" y1="64" x2="34" y2="72" stroke={faint} />
          <line x1="58" y1="64" x2="58" y2="72" stroke={faint} />
        </g>
      );
    case "tank":
      return (
        <g stroke={stroke} fill="none" strokeWidth="1.4">
          <path d="M34 16 h28 v10 c6 4 8 10 8 18 v22 c0 8 -6 14 -14 14 h-16 c-8 0 -14 -6 -14 -14 v-22 c0 -8 2 -14 8 -18 z" />
          <line x1="28" y1="52" x2="68" y2="52" strokeDasharray="4 4" stroke={faint} />
          <line x1="47" y1="16" x2="47" y2="8" />
          <circle cx="47" cy="8" r="2.4" />
          <line x1="70" y1="64" x2="84" y2="64" stroke={faint} />
        </g>
      );
    case "valve":
      return (
        <g stroke={stroke} fill="none" strokeWidth="1.4">
          <path d="M30 38 L46 52 L30 66 Z" />
          <path d="M66 38 L50 52 L66 66 Z" />
          <line x1="16" y1="52" x2="30" y2="52" />
          <line x1="66" y1="52" x2="84" y2="52" />
          <line x1="48" y1="52" x2="48" y2="28" />
          <rect x="42" y="20" width="12" height="8" rx="2" />
        </g>
      );
    default: // exchanger
      return (
        <g stroke={stroke} fill="none" strokeWidth="1.4">
          <rect x="24" y="32" width="52" height="34" rx="15" />
          <line x1="32" y1="40" x2="68" y2="40" stroke={faint} />
          <line x1="32" y1="49" x2="68" y2="49" stroke={faint} />
          <line x1="32" y1="58" x2="68" y2="58" stroke={faint} />
          <line x1="24" y1="49" x2="12" y2="49" />
          <line x1="76" y1="49" x2="88" y2="49" />
          <line x1="50" y1="66" x2="50" y2="76" stroke={faint} />
        </g>
      );
  }
}

export function TwinDiagram({
  kind,
  status,
  sensors,
  onSensorClick,
}: {
  kind: string;
  status: HealthState;
  sensors: SensorReading[];
  onSensorClick?: (key: string) => void;
}) {
  const [hot, setHot] = useState<number | null>(null);
  const anchors = ANCHORS[kind] ?? ANCHORS.exchanger;
  const glow = STATE_COLOR[status];

  return (
    <div style={{ position: "relative" }}>
      <svg viewBox="0 0 100 84" style={{ width: "100%", height: "auto", display: "block" }} role="img" aria-label={`${kind} schematic with spatial sensors`}>
        <defs>
          <radialGradient id="tw-glow" cx="50%" cy="48%" r="55%">
            <stop offset="0%" stopColor={glow} stopOpacity="0.14" />
            <stop offset="100%" stopColor={glow} stopOpacity="0" />
          </radialGradient>
        </defs>
        <rect x="0" y="0" width="100" height="84" fill="url(#tw-glow)" rx="8" />
        <rect x="6" y="6" width="88" height="72" fill="none" stroke="rgba(140,180,220,0.12)" strokeDasharray="6 5" rx="6" />
        <Schematic kind={kind} />

        {sensors.map((s, i) => {
          const a = anchors[i % anchors.length];
          const st = SENSOR_STATE(s);
          const c = STATE_COLOR[st];
          const active = hot === i;
          return (
            <g
              key={s.key}
              transform={`translate(${a[0]}, ${a[1]})`}
              onMouseEnter={() => setHot(i)}
              onMouseLeave={() => setHot(null)}
              onClick={() => onSensorClick?.(s.key)}
              style={{ cursor: "pointer" }}
              role="button"
              aria-label={`${s.label}: ${s.value} ${s.unit}`}
            >
              <circle r="10" fill="transparent" />
              <circle r={active ? 6.5 : 5} fill="#070b12" stroke={c} strokeWidth={active ? 2 : 1.3} style={{ transition: "all 200ms", filter: `drop-shadow(0 0 5px ${c})` }} />
              <circle r="1.8" fill={c} />
              {st !== "ok" && (
                <circle r="5" fill="none" stroke={c} strokeWidth="0.8" opacity="0.7">
                  <animate attributeName="r" values="5;10" dur="1.6s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.7;0" dur="1.6s" repeatCount="indefinite" />
                </circle>
              )}
              {/* callout */}
              <g transform={`translate(0, ${active ? -20 : -16})`} opacity={active ? 1 : 0.85} style={{ transition: "all 200ms" }}>
                <rect x="-22" y="-9" width="44" height={active ? 16 : 11} rx="2.5" fill="rgba(7,11,18,0.94)" stroke={active ? c : "rgba(140,180,220,0.2)"} strokeWidth="0.6" />
                <text textAnchor="middle" y="-3.5" fontSize="4.4" fontFamily="ui-monospace, monospace" fill={active ? "#eaf2fa" : "#9db1c7"}>
                  {s.label.toUpperCase()}
                </text>
                {active && (
                  <text textAnchor="middle" y="3.4" fontSize="4.6" fontFamily="ui-monospace, monospace" fill={c} fontWeight="700">
                    {s.value} {s.unit}
                  </text>
                )}
              </g>
            </g>
          );
        })}
      </svg>
      <div className="cs-mono cs-dim" style={{ position: "absolute", bottom: 6, right: 10, fontSize: 8.5, letterSpacing: "0.22em", textTransform: "uppercase" }}>
        hover = reading · click = telemetry
      </div>
    </div>
  );
}
