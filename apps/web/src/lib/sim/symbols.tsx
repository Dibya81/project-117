"use client";

/**
 * Project 117 Industrial Symbol Library — ORIGINAL vector assets.
 *
 * P&ID/ISA-5.1 conventions used as conceptual reference only: instrument
 * bubbles with tag letters, bow-tie valves, volute pumps, tray columns,
 * finned exchangers. All artwork below is hand-authored for this project
 * (see docs/simulation/ASSET_SOURCES.md — every entry marked ORIGINAL).
 *
 * State discipline (spec §8): the machine body never changes color. State is
 * carried by the status halo + badge: warning=amber ring, critical=red pulse,
 * failed=red + fault cross, disabled=dashed mute, investigating=cyan sweep,
 * acting=cyan double arc, verifying=green sweep, verified=green tick.
 */
import type { CSSProperties, ReactNode } from "react";

export type SymbolType =
  // instrumentation (ISA bubbles)
  | "inst_pt" | "inst_tt" | "inst_ft" | "inst_lt" | "inst_at" | "inst_vib"
  | "inst_rpm" | "inst_amp" | "inst_kw" | "inst_gd" | "inst_lk" | "inst_zt" | "inst_st"
  // valves
  | "valve_gate" | "valve_globe" | "valve_ball" | "valve_butterfly"
  | "valve_check" | "valve_control" | "valve_relief" | "valve_esv"
  // pumps
  | "pump_centrifugal" | "pump_pd"
  // machines
  | "motor" | "fan" | "blower" | "compressor" | "turbine"
  // process equipment
  | "tank" | "vessel_v" | "vessel_h" | "separator" | "column" | "exchanger"
  | "furnace" | "reactor" | "boiler" | "cooling_tower" | "filter" | "scrubber"
  // safety + infra
  | "esd_panel" | "fire_detector" | "alarm_beacon" | "estop" | "flare"
  | "junction" | "conveyor" | "utility_pkg";

export interface SymbolDef {
  type: SymbolType;
  category: "instrumentation" | "valve" | "pump" | "machine" | "process" | "safety" | "infrastructure";
  label: string;
  /** connection ports in 48×48 viewBox coordinates */
  ports: { in?: [number, number]; out?: [number, number]; signal?: [number, number] };
  draw: () => ReactNode;
}

/* --------------------------------------------------------------------------
 * glyph primitives — stroke-based engineering linework, 48×48 grid
 * ------------------------------------------------------------------------ */

const S = "currentColor";
const F = "none";
const W = 1.7;

function bowtie(cx = 24, cy = 24, r = 9): ReactNode {
  return (
    <g stroke={S} strokeWidth={W} fill={F} strokeLinejoin="round">
      <path d={`M${cx - r} ${cy - r * 0.8} L${cx - r} ${cy + r * 0.8} L${cx} ${cy} Z`} />
      <path d={`M${cx + r} ${cy - r * 0.8} L${cx + r} ${cy + r * 0.8} L${cx} ${cy} Z`} />
      <line x1={cx - r - 6} y1={cy} x2={cx - r} y2={cy} />
      <line x1={cx + r} y1={cy} x2={cx + r + 6} y2={cy} />
    </g>
  );
}

function bubble(letters: string, dashed = false): ReactNode {
  return (
    <g>
      <circle cx="24" cy="24" r="15" stroke={S} strokeWidth={W} fill={F} strokeDasharray={dashed ? "4 3" : undefined} />
      <line x1="9" y1="24" x2="39" y2="24" stroke={S} strokeWidth={1} opacity="0.55" />
      <text x="24" y="21" textAnchor="middle" fontSize="8.5" fontFamily="var(--font-mono), ui-monospace, monospace" fill={S} stroke="none" fontWeight="700">
        {letters.slice(0, 2)}
      </text>
      {letters.length > 2 && (
        <text x="24" y="31" textAnchor="middle" fontSize="7" fontFamily="var(--font-mono), ui-monospace, monospace" fill={S} stroke="none">
          {letters.slice(2)}
        </text>
      )}
    </g>
  );
}

function volute(): ReactNode {
  return (
    <g stroke={S} strokeWidth={W} fill={F} strokeLinejoin="round">
      {/* centrifugal pump: circle casing + volute tongue + discharge neck */}
      <circle cx="22" cy="26" r="12" />
      <path d="M22 14 a12 12 0 0 1 12 12 l7 -3 -1 9 -8 1" />
      <path d="M34 20 L34 9 L42 9" />
      <line x1="6" y1="26" x2="10" y2="26" />
      {/* impeller */}
      <path d="M22 20 a6 6 0 0 1 6 6 M22 32 a6 6 0 0 1 -6 -6 M16 26 a6 6 0 0 1 6 -6" />
      <circle cx="22" cy="26" r="1.6" fill={S} stroke="none" />
    </g>
  );
}

function towerFlare(): ReactNode {
  return (
    <g stroke={S} strokeWidth={W} fill={F} strokeLinejoin="round">
      <path d="M20 40 L22 14 L26 14 L28 40 Z" />
      <path d="M21 33 L27 33 M21.5 26 L26.5 26 M22 20 L26 20" strokeWidth="0.9" opacity="0.6" />
      <path d="M24 4 c-2.6 2.4 -2.6 5.4 0 8 c2.6 -2.6 2.6 -5.4 0 -8 Z" fill={S} stroke="none" opacity="0.85" />
    </g>
  );
}

/* --------------------------------------------------------------------------
 * the registry
 * ------------------------------------------------------------------------ */

export const SYMBOLS: Record<SymbolType, SymbolDef> = {
  /* ---------------- instrumentation (ISA-5.1-style bubbles) ---------------- */
  inst_pt: { type: "inst_pt", category: "instrumentation", label: "Pressure Transmitter", ports: { signal: [24, 39] }, draw: () => bubble("PT") },
  inst_tt: { type: "inst_tt", category: "instrumentation", label: "Temperature Transmitter", ports: { signal: [24, 39] }, draw: () => bubble("TT") },
  inst_ft: { type: "inst_ft", category: "instrumentation", label: "Flow Transmitter", ports: { signal: [24, 39] }, draw: () => bubble("FT") },
  inst_lt: { type: "inst_lt", category: "instrumentation", label: "Level Transmitter", ports: { signal: [24, 39] }, draw: () => bubble("LT") },
  inst_at: { type: "inst_at", category: "instrumentation", label: "Analyzer", ports: { signal: [24, 39] }, draw: () => bubble("AT") },
  inst_vib: { type: "inst_vib", category: "instrumentation", label: "Vibration Sensor", ports: { signal: [24, 39] }, draw: () => bubble("VIB") },
  inst_rpm: { type: "inst_rpm", category: "instrumentation", label: "Speed Sensor", ports: { signal: [24, 39] }, draw: () => bubble("RPM") },
  inst_amp: { type: "inst_amp", category: "instrumentation", label: "Current Sensor", ports: { signal: [24, 39] }, draw: () => bubble("A") },
  inst_kw: { type: "inst_kw", category: "instrumentation", label: "Power Sensor", ports: { signal: [24, 39] }, draw: () => bubble("kW") },
  inst_gd: { type: "inst_gd", category: "instrumentation", label: "Gas Detector", ports: { signal: [24, 39] }, draw: () => bubble("GD", true) },
  inst_lk: { type: "inst_lk", category: "instrumentation", label: "Leak Detector", ports: { signal: [24, 39] }, draw: () => bubble("LK", true) },
  inst_zt: { type: "inst_zt", category: "instrumentation", label: "Position Transmitter", ports: { signal: [24, 39] }, draw: () => bubble("ZT") },
  inst_st: { type: "inst_st", category: "instrumentation", label: "Speed Transmitter", ports: { signal: [24, 39] }, draw: () => bubble("ST") },

  /* ---------------- valves ------------------------------------------------- */
  valve_gate: {
    type: "valve_gate", category: "valve", label: "Gate Valve",
    ports: { in: [9, 24], out: [39, 24] },
    draw: () => (
      <g>
        {bowtie()}
        <line x1="24" y1="24" x2="24" y2="12" stroke={S} strokeWidth={W} />
        <line x1="18" y1="12" x2="30" y2="12" stroke={S} strokeWidth={W} />
      </g>
    ),
  },
  valve_globe: {
    type: "valve_globe", category: "valve", label: "Globe Valve",
    ports: { in: [9, 24], out: [39, 24] },
    draw: () => (
      <g>
        {bowtie()}
        <circle cx="24" cy="24" r="3" fill={S} stroke="none" />
        <line x1="24" y1="21" x2="24" y2="12" stroke={S} strokeWidth={W} />
        <line x1="19" y1="12" x2="29" y2="12" stroke={S} strokeWidth={W} />
      </g>
    ),
  },
  valve_ball: {
    type: "valve_ball", category: "valve", label: "Ball Valve",
    ports: { in: [9, 24], out: [39, 24] },
    draw: () => (
      <g>
        {bowtie()}
        <circle cx="24" cy="24" r="3.2" stroke={S} strokeWidth={W} fill={F} />
        <line x1="21.4" y1="24" x2="26.6" y2="24" stroke={S} strokeWidth={W} />
      </g>
    ),
  },
  valve_butterfly: {
    type: "valve_butterfly", category: "valve", label: "Butterfly Valve",
    ports: { in: [9, 24], out: [39, 24] },
    draw: () => (
      <g>
        {bowtie()}
        <line x1="19" y1="19" x2="29" y2="29" stroke={S} strokeWidth={W} />
        <circle cx="24" cy="24" r="1.4" fill={S} stroke="none" />
      </g>
    ),
  },
  valve_check: {
    type: "valve_check", category: "valve", label: "Check Valve",
    ports: { in: [9, 24], out: [39, 24] },
    draw: () => (
      <g>
        {bowtie()}
        <path d="M20 28 L27 20" stroke={S} strokeWidth={W} />
        <path d="M27 20 L27.8 24.5 M27 20 L22.6 21.4" stroke={S} strokeWidth={W} />
      </g>
    ),
  },
  valve_control: {
    type: "valve_control", category: "valve", label: "Control Valve",
    ports: { in: [9, 24], out: [39, 24], signal: [24, 8] },
    draw: () => (
      <g>
        {bowtie()}
        <line x1="24" y1="24" x2="24" y2="15" stroke={S} strokeWidth={W} />
        <path d="M18 15 a6 5 0 0 1 12 0 Z" stroke={S} strokeWidth={W} fill={F} />
        <line x1="24" y1="10" x2="24" y2="6" stroke={S} strokeWidth={1} strokeDasharray="2 2" />
      </g>
    ),
  },
  valve_relief: {
    type: "valve_relief", category: "valve", label: "Pressure Relief Valve",
    ports: { in: [24, 39], out: [24, 10] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F} strokeLinejoin="round">
        <path d="M18 32 L24 22 L30 32 Z" />
        <path d="M24 22 L24 14 M20 14 L28 14 M21 11 L27 11 M22.5 8.5 L25.5 8.5" />
        <line x1="24" y1="32" x2="24" y2="40" />
      </g>
    ),
  },
  valve_esv: {
    type: "valve_esv", category: "valve", label: "Emergency Shutoff Valve",
    ports: { in: [9, 24], out: [39, 24], signal: [24, 6] },
    draw: () => (
      <g>
        {bowtie()}
        <line x1="24" y1="24" x2="24" y2="14" stroke={S} strokeWidth={W} />
        <rect x="18" y="6" width="12" height="8" stroke={S} strokeWidth={W} fill={F} />
        <text x="24" y="11.8" textAnchor="middle" fontSize="5" fontFamily="var(--font-mono), ui-monospace, monospace" fill={S} stroke="none" fontWeight="700">ESV</text>
      </g>
    ),
  },

  /* ---------------- pumps -------------------------------------------------- */
  pump_centrifugal: {
    type: "pump_centrifugal", category: "pump", label: "Centrifugal Pump",
    ports: { in: [6, 26], out: [42, 9] },
    draw: () => volute(),
  },
  pump_pd: {
    type: "pump_pd", category: "pump", label: "Positive Displacement Pump",
    ports: { in: [8, 30], out: [40, 30] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F} strokeLinejoin="round">
        <rect x="12" y="18" width="24" height="16" rx="2" />
        <line x1="20" y1="18" x2="20" y2="34" />
        <line x1="28" y1="18" x2="28" y2="34" />
        <path d="M16 22 h8 M16 30 h8 M28 22 h8 M28 30 h8" strokeWidth="1" opacity="0.6" />
        <line x1="4" y1="26" x2="12" y2="26" />
        <line x1="36" y1="26" x2="44" y2="26" />
      </g>
    ),
  },

  /* ---------------- machines ---------------------------------------------- */
  motor: {
    type: "motor", category: "machine", label: "Electric Motor",
    ports: { out: [40, 24], signal: [24, 8] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F}>
        <circle cx="22" cy="24" r="12" />
        <text x="22" y="28.5" textAnchor="middle" fontSize="11" fontFamily="var(--font-mono), ui-monospace, monospace" fill={S} stroke="none" fontWeight="700">M</text>
        <line x1="34" y1="24" x2="42" y2="24" />
        <path d="M18 9 h8 l-2 4 h-6 Z" strokeWidth="1" opacity="0.6" />
      </g>
    ),
  },
  fan: {
    type: "fan", category: "machine", label: "Fan",
    ports: { in: [10, 26], out: [38, 22] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F} strokeLinejoin="round">
        <circle cx="24" cy="24" r="12" />
        <path d="M24 24 L24 14 a10 10 0 0 1 8 4 Z M24 24 L33 27 a10 10 0 0 1 -6 7 Z M24 24 L16 29 a10 10 0 0 1 -3 -9 Z" />
        <circle cx="24" cy="24" r="1.6" fill={S} stroke="none" />
      </g>
    ),
  },
  blower: {
    type: "blower", category: "machine", label: "Blower",
    ports: { in: [10, 28], out: [34, 12] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F} strokeLinejoin="round">
        <path d="M12 34 a12 12 0 0 1 20 -18 l6 -3 2 8 -8 4 a8 8 0 0 0 -4 9 Z" />
        <line x1="34" y1="12" x2="40" y2="12" />
        <line x1="6" y1="30" x2="13" y2="30" />
        <circle cx="24" cy="26" r="2" fill={S} stroke="none" />
      </g>
    ),
  },
  compressor: {
    type: "compressor", category: "machine", label: "Compressor",
    ports: { in: [8, 32], out: [38, 12] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F} strokeLinejoin="round">
        <path d="M12 36 L34 12 L40 12 L40 20 L20 40 L12 40 Z" />
        <line x1="14" y1="32" x2="32" y2="16" strokeWidth="1" opacity="0.6" />
        <line x1="17" y1="36" x2="36" y2="19" strokeWidth="1" opacity="0.4" />
        <line x1="4" y1="36" x2="12" y2="36" />
        <line x1="40" y1="12" x2="46" y2="12" />
      </g>
    ),
  },
  turbine: {
    type: "turbine", category: "machine", label: "Turbine",
    ports: { in: [8, 24], out: [40, 24] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F}>
        <circle cx="24" cy="24" r="12" />
        <text x="24" y="28.5" textAnchor="middle" fontSize="11" fontFamily="var(--font-mono), ui-monospace, monospace" fill={S} stroke="none" fontWeight="700">T</text>
        <path d="M15 18 a9 9 0 0 1 9 -6 M33 30 a9 9 0 0 1 -9 6" strokeWidth="1" opacity="0.55" />
        <line x1="36" y1="24" x2="44" y2="24" />
      </g>
    ),
  },

  /* ---------------- process equipment ------------------------------------- */
  tank: {
    type: "tank", category: "process", label: "Storage Tank",
    ports: { in: [24, 8], out: [24, 42] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F}>
        <path d="M14 12 h20 v24 a10 6 0 0 1 -20 0 Z" />
        <ellipse cx="24" cy="12" rx="10" ry="4" />
        <line x1="17" y1="27" x2="31" y2="27" strokeWidth="0.9" strokeDasharray="3 2.4" opacity="0.6" />
        <line x1="24" y1="42" x2="24" y2="46" />
      </g>
    ),
  },
  vessel_v: {
    type: "vessel_v", category: "process", label: "Vertical Vessel",
    ports: { in: [10, 24], out: [38, 24] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F}>
        <rect x="17" y="10" width="14" height="28" rx="7" />
        <line x1="17" y1="24" x2="31" y2="24" strokeWidth="0.9" strokeDasharray="3 2.4" opacity="0.6" />
        <line x1="17" y1="30" x2="31" y2="30" strokeWidth="0.7" opacity="0.35" />
        <line x1="10" y1="24" x2="17" y2="24" />
        <line x1="31" y1="24" x2="38" y2="24" />
      </g>
    ),
  },
  vessel_h: {
    type: "vessel_h", category: "process", label: "Horizontal Vessel",
    ports: { in: [8, 22], out: [40, 22] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F}>
        <rect x="10" y="18" width="28" height="12" rx="6" />
        <line x1="14" y1="36" x2="14" y2="30" />
        <line x1="34" y1="36" x2="34" y2="30" />
        <line x1="8" y1="22" x2="10" y2="22" />
        <line x1="38" y1="22" x2="40" y2="22" />
        <line x1="16" y1="24" x2="32" y2="24" strokeWidth="0.8" strokeDasharray="3 2.4" opacity="0.5" />
      </g>
    ),
  },
  separator: {
    type: "separator", category: "process", label: "Separator",
    ports: { in: [8, 18], out: [24, 6], out2: [24, 42] } as SymbolDef["ports"],
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F}>
        <rect x="17" y="8" width="14" height="32" rx="7" />
        <line x1="17" y1="28" x2="31" y2="28" strokeWidth="0.9" strokeDasharray="3 2.4" opacity="0.6" />
        <path d="M20 14 c2 3 6 3 8 0" strokeWidth="1" opacity="0.6" />
        <line x1="8" y1="18" x2="17" y2="18" />
        <line x1="24" y1="8" x2="24" y2="3" />
        <line x1="24" y1="40" x2="24" y2="45" />
      </g>
    ),
  },
  column: {
    type: "column", category: "process", label: "Distillation Column",
    ports: { in: [12, 30], out: [24, 6] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F}>
        <rect x="18" y="6" width="12" height="36" rx="5" />
        {[12, 17, 22, 27, 32, 37].map((y) => (
          <line key={y} x1="18" y1={y} x2="30" y2={y} strokeWidth="0.8" opacity="0.5" />
        ))}
        <line x1="12" y1="30" x2="18" y2="30" />
        <line x1="24" y1="6" x2="24" y2="2" />
      </g>
    ),
  },
  exchanger: {
    type: "exchanger", category: "process", label: "Heat Exchanger",
    ports: { in: [8, 30], out: [40, 30], signal: [24, 10] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F} strokeLinejoin="round">
        <rect x="10" y="18" width="28" height="14" rx="7" />
        <path d="M14 30 l4 -8 l4 8 l4 -8 l4 8 l4 -8" strokeWidth="1.1" opacity="0.75" />
        <line x1="8" y1="30" x2="10" y2="30" />
        <line x1="38" y1="30" x2="40" y2="30" />
        <line x1="24" y1="18" x2="24" y2="10" />
      </g>
    ),
  },
  furnace: {
    type: "furnace", category: "process", label: "Furnace / Fired Heater",
    ports: { in: [8, 34], out: [40, 14] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F} strokeLinejoin="round">
        <rect x="14" y="12" width="20" height="28" />
        <rect x="18" y="8" width="12" height="4" strokeWidth="1" opacity="0.6" />
        <path d="M19 34 v-8 M24 34 v-8 M29 34 v-8" strokeWidth="1" opacity="0.55" />
        <path d="M24 18 c-2 2.2 -2 4.6 0 7 c2 -2.4 2 -4.8 0 -7 Z" fill={S} stroke="none" opacity="0.8" />
        <line x1="8" y1="34" x2="14" y2="34" />
        <line x1="34" y1="14" x2="40" y2="14" />
      </g>
    ),
  },
  reactor: {
    type: "reactor", category: "process", label: "Reactor",
    ports: { in: [24, 6], out: [24, 44] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F}>
        <rect x="15" y="10" width="18" height="28" rx="9" />
        <line x1="24" y1="6" x2="24" y2="30" strokeWidth="1.1" />
        <path d="M19 22 h10 M19 28 h10" strokeWidth="1" opacity="0.55" />
        <circle cx="24" cy="8" r="2.4" />
        <line x1="24" y1="38" x2="24" y2="44" />
      </g>
    ),
  },
  boiler: {
    type: "boiler", category: "process", label: "Boiler",
    ports: { in: [10, 36], out: [24, 6] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F} strokeLinejoin="round">
        <rect x="14" y="14" width="20" height="26" rx="2" />
        <path d="M14 28 a10 5 0 0 1 20 0" strokeWidth="1.1" />
        <path d="M24 20 c-2 2.2 -2 4.4 0 6.6 c2 -2.2 2 -4.4 0 -6.6 Z" fill={S} stroke="none" opacity="0.8" />
        <line x1="10" y1="36" x2="14" y2="36" />
        <line x1="24" y1="14" x2="24" y2="6" />
      </g>
    ),
  },
  cooling_tower: {
    type: "cooling_tower", category: "process", label: "Cooling Tower",
    ports: { in: [10, 38], out: [38, 10] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F} strokeLinejoin="round">
        <path d="M16 40 L20 10 h8 l4 30 Z" />
        <path d="M20 17 h8 M18.6 26 h10.8 M17.5 34 h13" strokeWidth="0.8" opacity="0.5" />
        <circle cx="24" cy="14" r="2.6" strokeWidth="1" />
        <path d="M24 14 L24 9 M24 14 L28.4 16.4 M24 14 L19.6 16.4" strokeWidth="1" />
      </g>
    ),
  },
  filter: {
    type: "filter", category: "process", label: "Filter",
    ports: { in: [10, 24], out: [38, 24] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F}>
        <path d="M12 14 h24 v6 l-8 8 v10 l-8 4 v-14 l-8 -8 Z" strokeLinejoin="round" />
        <line x1="18" y1="22" x2="30" y2="22" strokeWidth="0.8" opacity="0.6" />
        <line x1="20" y1="26" x2="28" y2="26" strokeWidth="0.8" opacity="0.45" />
      </g>
    ),
  },
  scrubber: {
    type: "scrubber", category: "process", label: "Scrubber",
    ports: { in: [12, 38], out: [24, 6] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F}>
        <rect x="17" y="8" width="14" height="32" rx="6" />
        <path d="M21 14 l6 6 M27 14 l-6 6 M21 24 l6 6 M27 24 l-6 6" strokeWidth="0.9" opacity="0.55" />
        <line x1="12" y1="38" x2="17" y2="34" />
        <line x1="24" y1="8" x2="24" y2="3" />
      </g>
    ),
  },

  /* ---------------- safety + infrastructure -------------------------------- */
  esd_panel: {
    type: "esd_panel", category: "safety", label: "Emergency Shutdown Panel",
    ports: { signal: [24, 44] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F}>
        <rect x="14" y="10" width="20" height="28" rx="2" />
        <circle cx="24" cy="19" r="4.5" />
        <circle cx="24" cy="19" r="1.6" fill={S} stroke="none" />
        <line x1="18" y1="28" x2="30" y2="28" strokeWidth="1" opacity="0.6" />
        <line x1="18" y1="32" x2="30" y2="32" strokeWidth="1" opacity="0.35" />
        <text x="24" y="44" textAnchor="middle" fontSize="5.4" fontFamily="var(--font-mono), ui-monospace, monospace" fill={S} stroke="none" fontWeight="700">ESD</text>
      </g>
    ),
  },
  fire_detector: {
    type: "fire_detector", category: "safety", label: "Fire Detector",
    ports: { signal: [24, 40] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F}>
        <circle cx="24" cy="24" r="13" strokeDasharray="4 3" />
        <path d="M24 16 c-3.4 3 -3.4 7.2 0 10.4 c3.4 -3.2 3.4 -7.4 0 -10.4 Z" fill={S} stroke="none" opacity="0.85" />
      </g>
    ),
  },
  alarm_beacon: {
    type: "alarm_beacon", category: "safety", label: "Alarm Beacon",
    ports: { signal: [24, 42] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F}>
        <path d="M17 34 a7 8 0 0 1 14 0 Z" />
        <rect x="15" y="34" width="18" height="3" rx="1" />
        <path d="M24 12 v4 M15 15 l2.4 2.4 M33 15 l-2.4 2.4" strokeWidth="1.2" />
        <circle cx="24" cy="27" r="2" fill={S} stroke="none" />
      </g>
    ),
  },
  estop: {
    type: "estop", category: "safety", label: "Emergency Stop",
    ports: { signal: [24, 42] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F}>
        <rect x="16" y="24" width="16" height="12" rx="1.5" />
        <path d="M19 24 a5 4.6 0 0 1 10 0 Z" />
        <line x1="24" y1="13" x2="24" y2="16" strokeWidth="1.2" />
      </g>
    ),
  },
  flare: {
    type: "flare", category: "safety", label: "Flare",
    ports: { in: [22, 40] },
    draw: () => towerFlare(),
  },
  junction: {
    type: "junction", category: "infrastructure", label: "Junction",
    ports: { in: [16, 24], out: [32, 24] },
    draw: () => (
      <g>
        <circle cx="24" cy="24" r="3.4" stroke={S} strokeWidth={W} fill={F} />
        <circle cx="24" cy="24" r="1.2" fill={S} stroke="none" />
      </g>
    ),
  },
  conveyor: {
    type: "conveyor", category: "machine", label: "Conveyor",
    ports: { in: [6, 30], out: [42, 18] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F}>
        <path d="M8 32 L40 18" />
        <circle cx="10" cy="31.4" r="3" />
        <circle cx="38" cy="18.6" r="3" />
        <path d="M16 28 l2 -1 M24 24.6 l2 -1 M32 21.4 l2 -1" strokeWidth="1" opacity="0.6" />
      </g>
    ),
  },
  utility_pkg: {
    type: "utility_pkg", category: "infrastructure", label: "Utility Package",
    ports: { out: [38, 24] },
    draw: () => (
      <g stroke={S} strokeWidth={W} fill={F}>
        <rect x="10" y="14" width="28" height="20" rx="2" />
        <path d="M14 20 h8 M14 24 h8 M14 28 h8" strokeWidth="1" opacity="0.55" />
        <circle cx="31" cy="24" r="3.4" />
        <line x1="38" y1="24" x2="44" y2="24" />
      </g>
    ),
  },
};

/* --------------------------------------------------------------------------
 * mapping: equipment kind + sensor measurement → symbol
 * ------------------------------------------------------------------------ */

export const KIND_SYMBOL: Record<string, SymbolType> = {
  pump: "pump_centrifugal",
  valve: "valve_gate",
  tank: "tank",
  vessel: "vessel_v",
  column: "column",
  exchanger: "exchanger",
  furnace: "furnace",
  compressor: "compressor",
  motor: "motor",
  conveyor: "conveyor",
  safety: "esd_panel",
  utility: "utility_pkg",
};

export const MEAS_SYMBOL: Record<string, SymbolType> = {
  pressure: "inst_pt",
  temperature: "inst_tt",
  flow: "inst_ft",
  level: "inst_lt",
  vibration: "inst_vib",
  rpm: "inst_rpm",
  current: "inst_amp",
  power: "inst_kw",
  gas: "inst_gd",
  leak: "inst_lk",
  position: "inst_zt",
  speed: "inst_st",
};

/** Valve subtypes by tag content — dataset names drive the variant. */
export function valveSymbolFor(name: string): SymbolType {
  const n = name.toLowerCase();
  if (n.includes("control") || n.includes("level") || n.includes("feed")) return "valve_control";
  if (n.includes("relief") || n.includes("safety")) return "valve_relief";
  if (n.includes("emergency") || n.includes("shutdown")) return "valve_esv";
  if (n.includes("check")) return "valve_check";
  if (n.includes("butterfly")) return "valve_butterfly";
  if (n.includes("ball")) return "valve_ball";
  if (n.includes("globe")) return "valve_globe";
  return "valve_gate";
}

export function symbolForEquipment(kind: string, name: string): SymbolType {
  if (kind === "valve") return valveSymbolFor(name);
  if (kind === "safety") return name.toLowerCase().includes("fire") ? "fire_detector" : "esd_panel";
  if (kind === "utility") return name.toLowerCase().includes("cooling") || name.toLowerCase().includes("tower") ? "cooling_tower" : name.toLowerCase().includes("flare") ? "flare" : "utility_pkg";
  return KIND_SYMBOL[kind] ?? "utility_pkg";
}

/* --------------------------------------------------------------------------
 * state overlay + renderer
 * ------------------------------------------------------------------------ */

export type SimVisualState =
  | "normal" | "warning" | "critical" | "failed" | "disabled"
  | "investigating" | "acting" | "verifying" | "verified";

const STATE_COLOR: Record<SimVisualState, string | null> = {
  normal: null,
  warning: "#ffb454",
  critical: "#ff5d5d",
  failed: "#ff5d5d",
  disabled: "#5b6c81",
  investigating: "#45d5ff",
  acting: "#45d5ff",
  verifying: "#3ddc97",
  verified: "#3ddc97",
};

export function SimSymbol({
  type,
  state = "normal",
  size = 48,
  style,
  onClick,
  label,
}: {
  type: SymbolType;
  state?: SimVisualState;
  size?: number;
  style?: CSSProperties;
  onClick?: () => void;
  label?: string;
}) {
  const def = SYMBOLS[type] ?? SYMBOLS.utility_pkg;
  const sc = STATE_COLOR[state];
  const pulsing = state === "critical" || state === "failed" || state === "investigating" || state === "acting";
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      style={{ display: "block", overflow: "visible", cursor: onClick ? "pointer" : "default", ...style }}
      onClick={onClick}
      role={onClick ? "button" : "img"}
      aria-label={label ?? def.label}
    >
      {/* status halo — state without repainting the machine */}
      {sc && (
        <circle
          cx="24"
          cy="24"
          r="21"
          fill="none"
          stroke={sc}
          strokeWidth={state === "failed" ? 2 : 1.4}
          strokeDasharray={state === "disabled" || state === "verifying" ? "4 4" : undefined}
          opacity={0.85}
        >
          {pulsing && <animate attributeName="r" values="19;23;19" dur={state === "critical" || state === "failed" ? "1.1s" : "1.8s"} repeatCount="indefinite" />}
        </circle>
      )}
      <g opacity={state === "disabled" ? 0.42 : 1}>{def.draw()}</g>

      {/* fault cross */}
      {state === "failed" && (
        <g stroke="#ff5d5d" strokeWidth="2.2" strokeLinecap="round">
          <line x1="36" y1="6" x2="44" y2="14" />
          <line x1="44" y1="6" x2="36" y2="14" />
        </g>
      )}
      {/* verified tick */}
      {state === "verified" && (
        <path d="M35 8 l3 3 l6 -6" stroke="#3ddc97" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      )}
      {/* investigating sweep arc */}
      {state === "investigating" && (
        <circle cx="24" cy="24" r="25" fill="none" stroke="#45d5ff" strokeWidth="1.2" strokeDasharray="30 128" strokeLinecap="round">
          <animateTransform attributeName="transform" type="rotate" from="0 24 24" to="360 24 24" dur="2.2s" repeatCount="indefinite" />
        </circle>
      )}
      {/* acting double arc */}
      {state === "acting" && (
        <g>
          <circle cx="24" cy="24" r="25" fill="none" stroke="#45d5ff" strokeWidth="1.2" strokeDasharray="22 136" strokeLinecap="round">
            <animateTransform attributeName="transform" type="rotate" from="0 24 24" to="360 24 24" dur="1.4s" repeatCount="indefinite" />
          </circle>
          <circle cx="24" cy="24" r="28" fill="none" stroke="#45d5ff" strokeWidth="0.8" strokeDasharray="14 162" strokeLinecap="round" opacity="0.6">
            <animateTransform attributeName="transform" type="rotate" from="360 24 24" to="0 24 24" dur="2.4s" repeatCount="indefinite" />
          </circle>
        </g>
      )}
    </svg>
  );
}
