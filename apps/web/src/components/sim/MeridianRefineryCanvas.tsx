"use client";

import { useState, useRef, useMemo, useEffect, type MouseEvent, type WheelEvent } from "react";
import { Icon } from "@/components/ui/Icon";
import { AgentDispatchBoxes } from "@/components/sim/AgentDispatchBoxes";
import type { AgentTask, EquipmentDef, PlantDef } from "@/lib/sim/types";
import type { CanvasRuntime, SpatialReading } from "@/components/sim/SchematicCanvas";

export interface RefineryUnit {
  id: string;
  tag: string;
  name: string;
  kind:
    | "tank"
    | "spherical_tank"
    | "pump"
    | "desalter"
    | "furnace"
    | "column"
    | "fcc"
    | "reactor"
    | "amine"
    | "sru"
    | "gas_treat"
    | "cooling_tower"
    | "boiler"
    | "power_gen"
    | "flare";
  zone: "CRUDE INTAKE" | "DISTILLATION" | "CONVERSION" | "TREATMENT" | "UTILITY SYSTEMS" | "PRODUCTS";
  x: number;
  y: number;
  w: number;
  h: number;
  temperature?: string;
  pressure?: string;
  flow?: string;
  power?: string;
  status: "Normal" | "Running" | "Warning" | "Critical";
  eq?: EquipmentDef;
}

export const REFINERY_UNITS: RefineryUnit[] = [
  // 1. CRUDE INTAKE (x: 25..225)
  { id: "e-T-101", tag: "T-101", name: "Crude Storage Tank", kind: "tank", zone: "CRUDE INTAKE", x: 60, y: 85, w: 100, h: 140, temperature: "32.4 °C", pressure: "1.2 bar", status: "Normal" },
  { id: "e-P-101", tag: "P-101 A/B", name: "Crude Charge Pump", kind: "pump", zone: "CRUDE INTAKE", x: 65, y: 325, w: 90, h: 65, flow: "85.2 %", status: "Running" },

  // 2. DISTILLATION (x: 235..510)
  { id: "e-D-101", tag: "D-101", name: "Desalter Unit", kind: "desalter", zone: "DISTILLATION", x: 255, y: 130, w: 90, h: 70, temperature: "120.5 °C", pressure: "3.4 bar", status: "Normal" },
  { id: "e-F-101", tag: "F-101", name: "Crude Furnace", kind: "furnace", zone: "DISTILLATION", x: 250, y: 285, w: 100, h: 125, temperature: "680.2 °C", status: "Normal" },
  { id: "e-C-101", tag: "C-101", name: "Atmospheric Distillation", kind: "column", zone: "DISTILLATION", x: 405, y: 70, w: 60, h: 195, temperature: "356.8 °C", pressure: "1.1 bar", status: "Normal" },
  { id: "e-C-102", tag: "C-102", name: "Vacuum Distillation", kind: "column", zone: "DISTILLATION", x: 408, y: 295, w: 54, h: 150, temperature: "285.1 °C", pressure: "0.2 bar", status: "Normal" },

  // 3. CONVERSION (x: 520..710)
  { id: "e-C-201", tag: "C-201", name: "FCC Unit", kind: "fcc", zone: "CONVERSION", x: 550, y: 75, w: 75, h: 185, temperature: "520.4 °C", pressure: "1.8 bar", status: "Normal" },
  { id: "e-H-201", tag: "H-201", name: "Hydrocracker", kind: "reactor", zone: "CONVERSION", x: 555, y: 295, w: 65, h: 145, temperature: "415.6 °C", pressure: "3.8 bar", status: "Normal" },

  // 4. TREATMENT (x: 720..930)
  { id: "e-A-301", tag: "A-301", name: "Amine Unit", kind: "amine", zone: "TREATMENT", x: 735, y: 80, w: 52, h: 105, temperature: "45.2 °C", pressure: "1.6 bar", status: "Normal" },
  { id: "e-FLARE", tag: "FLARE-01", name: "To Flare Stack", kind: "flare", zone: "TREATMENT", x: 840, y: 65, w: 38, h: 130, temperature: "950 °C", status: "Normal" },
  { id: "e-S-301", tag: "S-301", name: "SRU Sulfur Recovery", kind: "sru", zone: "TREATMENT", x: 735, y: 220, w: 52, h: 80, temperature: "220.4 °C", pressure: "2.1 bar", status: "Normal" },
  { id: "e-G-301", tag: "G-301", name: "Gas Treatment", kind: "gas_treat", zone: "TREATMENT", x: 830, y: 220, w: 52, h: 80, temperature: "38.7 °C", pressure: "2.6 bar", status: "Normal" },
  { id: "e-H-301", tag: "H-301", name: "Hydrotreater", kind: "reactor", zone: "TREATMENT", x: 735, y: 335, w: 55, h: 115, temperature: "392.1 °C", pressure: "4.2 bar", status: "Normal" },

  // 5. UTILITY SYSTEMS (x: 940..1135)
  { id: "e-CT-401", tag: "CT-401", name: "Cooling Tower", kind: "cooling_tower", zone: "UTILITY SYSTEMS", x: 965, y: 80, w: 80, h: 95, temperature: "28.3 °C", status: "Normal" },
  { id: "e-B-401", tag: "B-401", name: "Boiler Package", kind: "boiler", zone: "UTILITY SYSTEMS", x: 975, y: 210, w: 60, h: 85, pressure: "12.4 bar", status: "Normal" },
  { id: "e-PG-401", tag: "PG-401", name: "Power Generator", kind: "power_gen", zone: "UTILITY SYSTEMS", x: 965, y: 330, w: 75, h: 85, power: "18.2 MW", status: "Normal" },

  // 6. PRODUCTS (x: 1145..1355)
  { id: "e-T-501", tag: "T-501", name: "LPG Storage", kind: "spherical_tank", zone: "PRODUCTS", x: 1180, y: 65, w: 85, h: 90, temperature: "48.6 °C", pressure: "6.2 bar", status: "Normal" },
  { id: "e-T-502", tag: "T-502", name: "Gasoline Storage", kind: "tank", zone: "PRODUCTS", x: 1185, y: 175, w: 80, h: 80, temperature: "36.1 °C", pressure: "1.4 bar", status: "Normal" },
  { id: "e-T-503", tag: "T-503", name: "Diesel Storage", kind: "tank", zone: "PRODUCTS", x: 1185, y: 275, w: 80, h: 80, temperature: "34.8 °C", pressure: "1.3 bar", status: "Normal" },
  { id: "e-T-504", tag: "T-504", name: "Jet Fuel Storage", kind: "tank", zone: "PRODUCTS", x: 1185, y: 375, w: 80, h: 80, temperature: "32.1 °C", pressure: "1.2 bar", status: "Normal" },
];

const ZONE_BANDS = [
  { name: "CRUDE INTAKE",   x: 25,  w: 200, fill: "rgba(245,158,11,0.06)", accent: "#f59e0b" },
  { name: "DISTILLATION",   x: 235, w: 275, fill: "rgba(239,68,68,0.05)",  accent: "#ef4444" },
  { name: "CONVERSION",     x: 520, w: 190, fill: "rgba(6,182,212,0.06)",  accent: "#06b6d4" },
  { name: "TREATMENT",      x: 720, w: 210, fill: "rgba(16,185,129,0.06)", accent: "#10b981" },
  { name: "UTILITY SYSTEMS",x: 940, w: 195, fill: "rgba(139,92,246,0.06)", accent: "#8b5cf6" },
  { name: "PRODUCTS",       x: 1145,w: 210, fill: "rgba(59,130,246,0.06)", accent: "#3b82f6" },
];

const EQUIPMENT_ALIASES: Record<string, string[]> = {
  "T-101": ["TK-1101", "TK-100", "TK-1102", "e-TK-1101", "e-T-101"],
  "P-101 A/B": ["P-1042", "P-1001", "P-110", "P-1002", "P-101", "e-P-1042", "e-P-101"],
  "D-101": ["VS-1201", "DS-120", "e-VS-1201", "e-D-101"],
  "F-101": ["F-1043", "F-130", "e-F-1043", "e-F-101"],
  "C-101": ["COL-1044", "COL-140", "e-COL-1044", "e-C-101"],
  "C-102": ["COL-1052", "COL-150", "e-COL-1052", "e-C-102"],
  "C-201": ["VS-1081", "COL-201", "e-VS-1081", "e-C-201"],
  "H-201": ["VS-1092", "R-160", "e-VS-1092", "e-H-201"],
  "A-301": ["VS-1126", "A-301", "e-VS-1126", "e-A-301"],
  "FLARE-01": ["UT-1161", "FLARE-01", "e-UT-1161", "e-FLARE"],
  "S-301": ["VS-1162", "S-301", "e-VS-1162", "e-S-301"],
  "G-301": ["C-1125", "G-301", "e-C-1125", "e-G-301"],
  "H-301": ["VS-1062", "H-301", "e-VS-1062", "e-H-301"],
  "CT-401": ["UT-1133", "CT-401", "e-UT-1133", "e-CT-401"],
  "B-401": ["F-1141", "B-401", "e-F-1141", "e-B-401"],
  "PG-401": ["M-1143", "PG-401", "e-M-1143", "e-PG-401"],
  "T-501": ["TK-1121", "TK-501", "e-TK-1121", "e-T-501"],
  "T-502": ["TK-1122", "TK-502", "e-TK-1122", "e-T-502"],
  "T-503": ["TK-1123", "TK-503", "e-TK-1123", "e-T-503"],
  "T-504": ["TK-1102", "TK-504", "TK-190", "e-TK-1102", "e-T-504"],
};

function resolveEquipment(unit: RefineryUnit, plant: PlantDef): EquipmentDef {
  // 1. Direct tag / id match
  let eq = plant.equipment.find(
    (e) => e.tag === unit.tag || e.id === unit.id || e.id === `e-${unit.tag}` || e.tag === unit.tag.replace(/\s+A\/B/, "")
  );
  if (eq) return eq;

  // 2. Check aliases
  const aliases = EQUIPMENT_ALIASES[unit.tag] || EQUIPMENT_ALIASES[unit.id] || [];
  for (const alias of aliases) {
    eq = plant.equipment.find((e) => e.tag === alias || e.id === alias || e.id === `e-${alias}`);
    if (eq) return eq;
  }

  // 3. Fallback: match by name
  eq = plant.equipment.find(
    (e) => e.name.toLowerCase().includes(unit.name.toLowerCase()) || unit.name.toLowerCase().includes(e.name.toLowerCase())
  );
  if (eq) return eq;

  // 4. Return robust synthetic EquipmentDef
  const kindMap: Record<string, EquipmentDef["kind"]> = {
    tank: "tank", spherical_tank: "tank", pump: "pump", desalter: "vessel",
    furnace: "furnace", column: "column", fcc: "column", reactor: "vessel",
    amine: "vessel", sru: "vessel", gas_treat: "vessel", cooling_tower: "utility",
    boiler: "furnace", power_gen: "motor", flare: "safety",
  };
  return {
    id: unit.id,
    tag: unit.tag,
    name: unit.name,
    kind: kindMap[unit.kind] ?? "vessel",
    area_id: unit.zone,
    x: unit.x,
    y: unit.y,
    criticality: unit.kind === "fcc" || unit.kind === "column" ? 1 : 2,
    capacity: 100,
    state: unit.status === "Critical" ? "critical" : unit.status === "Warning" ? "warning" : "normal",
    sensors: [],
    failure_modes: [],
    manufacturer: "Meridian Heavy Industries",
    model: "MHI-2026-SYNTH",
    installed: "2024-03-15",
    last_inspection: "2026-08-20",
  };
}

export interface ProcessPipelineDef {
  id: string;
  name: string;
  d: string;
  color: string;
  label?: string;
  labelPos?: { x: number; y: number };
  valves?: { x: number; y: number; orientation: "h" | "v" }[];
  isRerouteCandidate?: boolean;
  isCriticalPath?: boolean;
}

export const REFINERY_PIPELINES: ProcessPipelineDef[] = [
  { id: "pipe-crude-1", name: "Crude Feed", d: "M 110 225 L 110 325", color: "#f59e0b", label: "Crude Feed", labelPos: { x: 118, y: 275 }, valves: [{ x: 110, y: 275, orientation: "v" }], isCriticalPath: true },
  { id: "pipe-crude-2", name: "Desalter Feed", d: "M 155 357 L 205 357 L 205 165 L 255 165", color: "#f59e0b", valves: [{ x: 205, y: 260, orientation: "v" }], isCriticalPath: true },
  { id: "pipe-desalter-furnace", name: "Furnace Charge", d: "M 300 200 L 300 285", color: "#f59e0b", valves: [{ x: 300, y: 242, orientation: "v" }], isCriticalPath: true },
  { id: "pipe-furnace-c101", name: "Flash Zone Feed", d: "M 350 347 L 378 347 L 378 190 L 405 190", color: "#f59e0b", valves: [{ x: 378, y: 265, orientation: "v" }], isCriticalPath: true },
  { id: "pipe-c101-naphtha", name: "Naphtha Draw", d: "M 465 110 L 515 110", color: "#f97316", label: "Naphtha", labelPos: { x: 485, y: 102 } },
  { id: "pipe-c101-kerosene", name: "Kerosene Draw", d: "M 465 145 L 515 145", color: "#3b82f6", label: "Kero", labelPos: { x: 485, y: 137 } },
  { id: "pipe-c101-diesel", name: "Diesel Draw", d: "M 465 180 L 515 180", color: "#eab308", label: "Diesel", labelPos: { x: 485, y: 172 }, valves: [{ x: 490, y: 180, orientation: "h" }] },
  { id: "pipe-c101-bottoms", name: "Atmospheric Residue", d: "M 435 265 L 435 295", color: "#64748b" },
  { id: "pipe-c102-vgo", name: "VGO Draw", d: "M 462 360 L 515 360", color: "#a855f7", label: "VGO", labelPos: { x: 485, y: 352 } },
  { id: "pipe-c102-hydrocracker", name: "Hydrocracker Feed", d: "M 462 380 L 555 380", color: "#06b6d4", valves: [{ x: 508, y: 380, orientation: "h" }], isRerouteCandidate: true },
  { id: "pipe-c101-fcc", name: "FCC Feed", d: "M 465 130 L 550 130", color: "#06b6d4", valves: [{ x: 508, y: 130, orientation: "h" }], isRerouteCandidate: true, isCriticalPath: true },
  { id: "pipe-fcc-to-treater", name: "FCC Product Route", d: "M 625 175 L 685 175 L 685 390 L 735 390", color: "#06b6d4", valves: [{ x: 685, y: 280, orientation: "v" }], isCriticalPath: true },
  { id: "pipe-sourgas-flare", name: "Sour Gas Header", d: "M 787 115 L 840 115", color: "#ef4444", label: "Sour Gas", labelPos: { x: 792, y: 106 } },
  { id: "pipe-fcc-sru", name: "SRU Feed", d: "M 625 210 L 675 210 L 675 260 L 735 260", color: "#10b981" },
  { id: "pipe-h301-products", name: "Treated Stream", d: "M 790 395 L 890 395 L 890 315 L 1185 315", color: "#10b981", valves: [{ x: 890, y: 355, orientation: "v" }] },
  { id: "pipe-cooling-water", name: "Cooling Water Supply", d: "M 1045 130 L 1100 130 L 1100 450 L 920 450", color: "#06b6d4" },
  { id: "pipe-steam-header", name: "High Pressure Steam", d: "M 1035 250 L 1115 250 L 1115 215 L 1185 215", color: "#f97316" },
  { id: "pipe-fuel-gas", name: "Refinery Fuel Gas", d: "M 1040 370 L 1125 370 L 1125 415 L 1185 415", color: "#10b981" },
  { id: "pipe-prod-lpg", name: "LPG Line", d: "M 787 135 L 820 135 L 820 100 L 1180 100", color: "#10b981" },
  { id: "pipe-prod-gasoline", name: "Gasoline Run-down", d: "M 787 255 L 900 255 L 900 215 L 1185 215", color: "#22c55e" },
  { id: "pipe-prod-diesel", name: "Diesel Run-down", d: "M 790 415 L 1140 415 L 1140 315 L 1185 315", color: "#22c55e" },
  { id: "pipe-prod-jetfuel", name: "Jet Fuel Run-down", d: "M 790 435 L 1150 435 L 1150 415 L 1185 415", color: "#22c55e" },
];

const AGENTS = [
  { id: "perception", label: "Perception Agent", role: "Detecting · correlating sensors", color: "#f59e0b", icon: "👁", ax: 110, ay: 50 },
  { id: "operations", label: "Operations Agent",  role: "Tracing topology · rerouting",    color: "#06b6d4", icon: "⚙", ax: 580, ay: 50 },
  { id: "safety",     label: "Safety Agent",      role: "Evaluating risk · verifying",     color: "#10b981", icon: "🛡", ax: 1020, ay: 50 },
] as const;

export function MeridianRefineryCanvas({
  plant,
  runtime,
  readings,
  selected,
  onSelectEquipment,
  failover = null,
  activeIncident = null,
  tasks = [],
  models = {},
}: {
  plant: PlantDef;
  runtime: CanvasRuntime | null;
  readings: Record<string, SpatialReading>;
  selected: EquipmentDef | null;
  onSelectEquipment: (eq: EquipmentDef) => void;
  failover?: { from: string; to: string } | null;
  activeIncident?: any;
  tasks?: AgentTask[];
  models?: Record<string, string | null>;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [startPan, setStartPan] = useState({ x: 0, y: 0 });
  const [hoveredUnitId, setHoveredUnitId] = useState<string | null>(null);

  const [agentPhase, setAgentPhase] = useState<0 | 1 | 2 | 3>(0);
  const choreTimers = useRef<ReturnType<typeof setTimeout>[]>([]);
  useEffect(() => {
    choreTimers.current.forEach(clearTimeout);
    choreTimers.current = [];
    if (activeIncident) {
      setAgentPhase(1);
      choreTimers.current.push(
        setTimeout(() => setAgentPhase(2), 2800),
        setTimeout(() => setAgentPhase(3), 5200),
      );
    } else {
      setAgentPhase(0);
    }
    return () => choreTimers.current.forEach(clearTimeout);
  }, [activeIncident]);

  const liveUnits = useMemo(() => {
    return REFINERY_UNITS.map((unit) => {
      const eq = resolveEquipment(unit, plant);
      let status = unit.status;
      let temp = unit.temperature, press = unit.pressure, flw = unit.flow, pwr = unit.power;
      if (eq) {
        const state = runtime?.states[eq.id];
        if (state === "failed" || state === "critical") status = "Critical";
        else if (state === "warning") status = "Warning";
        else status = "Normal";

        for (const s of eq.sensors) {
          const r = readings[s.id];
          if (r !== undefined && r.value !== undefined) {
            if (s.measurement === "temperature") temp = `${r.value.toFixed(1)} ${s.unit}`;
            if (s.measurement === "pressure") press = `${r.value.toFixed(1)} ${s.unit}`;
            if (s.measurement === "flow") flw = `${r.value.toFixed(1)} ${s.unit}`;
            if (s.measurement === "power") pwr = `${r.value.toFixed(1)} ${s.unit}`;
          }
        }
      }
      return { ...unit, status, temperature: temp, pressure: press, flow: flw, power: pwr, eq };
    });
  }, [plant, runtime, readings]);

  const activeOriginUnit = useMemo(() => {
    if (!activeIncident) return null;
    const tag = activeIncident.equipmentTag || activeIncident.tag || activeIncident.equipment_id;
    return liveUnits.find((u) => u.tag === tag || u.id === tag || u.id === `e-${tag}` || u.eq?.tag === tag || u.eq?.id === tag) ?? liveUnits.find(u => u.kind === "fcc") ?? null;
  }, [activeIncident, liveUnits]);

  const handleWheel = (e: WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.08 : 0.92;
    setZoom((z) => Math.max(0.7, Math.min(2.5, z * factor)));
  };
  const handleMouseDown = (e: MouseEvent) => {
    // Only drag background if clicking directly on background SVG
    if (e.button === 0 && (e.target === svgRef.current || (e.target as HTMLElement).getAttribute("data-bg") === "true")) {
      setIsPanning(true);
      setStartPan({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };
  const handleMouseMove = (e: MouseEvent) => {
    if (isPanning) setPan({ x: e.clientX - startPan.x, y: e.clientY - startPan.y });
  };
  const handleMouseUp = () => setIsPanning(false);
  const resetView = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

  const hasIncident = Boolean(activeIncident);
  const isCrit = activeIncident?.severity === "critical";

  const vbCx = 690, vbCy = 270;
  const tx = vbCx + pan.x / zoom - vbCx;
  const ty = vbCy + pan.y / zoom - vbCy;

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        overflow: "hidden",
        background: "#f1f5f9",
        cursor: isPanning ? "grabbing" : "default",
        userSelect: "none",
      }}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      {/* Incident banner */}
      {hasIncident && (
        <div style={{
          position: "absolute", top: 0, left: 0, right: 0, height: 28, zIndex: 20,
          background: isCrit ? "linear-gradient(90deg,#dc2626,#991b1b)" : "linear-gradient(90deg,#d97706,#92400e)",
          display: "flex", alignItems: "center", gap: 10, padding: "0 14px",
          fontFamily: "monospace", fontSize: 10.5, fontWeight: 700, letterSpacing: "0.1em", color: "#fff",
        }}>
          <span style={{ animation: "mr-unit-crit-flash 0.9s ease-in-out infinite" }}>{isCrit ? "🔴" : "🟡"}</span>
          <span>ACTIVE INCIDENT · {(activeIncident?.title ?? "FAULT DETECTED").toUpperCase()}</span>
          <span style={{ marginLeft: "auto", opacity: 0.8, fontSize: 9.5 }}>
            {agentPhase >= 1 && "PERCEPTION"}{agentPhase >= 2 && " · OPERATIONS"}{agentPhase >= 3 && " · SAFETY"}{agentPhase > 0 && " ENGAGED"}
          </span>
        </div>
      )}

      {/* Zoom controls */}
      <div style={{
        position: "absolute",
        top: hasIncident ? 36 : 8,
        right: 12,
        zIndex: 20,
        display: "flex",
        gap: 3,
        background: "rgba(255,255,255,0.95)",
        padding: "2px 4px",
        borderRadius: 6,
        border: "1px solid #cbd5e1",
        boxShadow: "0 2px 6px rgba(0,0,0,0.06)",
      }}>
        <button type="button" onClick={() => setZoom(z => Math.min(2.5, z * 1.2))} style={{ width: 24, height: 24, borderRadius: 4, border: "1px solid #e2e8f0", background: "#fff", cursor: "pointer", color: "#475569", display: "flex", alignItems: "center", justifyContent: "center" }} title="Zoom In"><Icon name="plus" size={11} /></button>
        <button type="button" onClick={() => setZoom(z => Math.max(0.7, z * 0.8))} style={{ width: 24, height: 24, borderRadius: 4, border: "1px solid #e2e8f0", background: "#fff", cursor: "pointer", color: "#475569", fontSize: 14, fontWeight: "bold", lineHeight: 1, display: "flex", alignItems: "center", justifyContent: "center" }} title="Zoom Out">−</button>
        <button type="button" onClick={resetView} style={{ padding: "0 6px", height: 24, borderRadius: 4, border: "1px solid #e2e8f0", background: "#fff", cursor: "pointer", color: "#475569", fontSize: 9.5, fontFamily: "monospace", display: "flex", alignItems: "center", gap: 3 }} title="Reset Viewport"><Icon name="refresh" size={10} /><span>FIT</span></button>
      </div>

      {/* ── THE SVG CANVAS (Widescreen 1380 x 540) ── */}
      <svg
        ref={svgRef}
        viewBox="0 0 1380 540"
        preserveAspectRatio="xMidYMid meet"
        style={{ display: "block", width: "100%", height: "100%", position: "absolute", inset: 0 }}
        onClick={(e) => { if (e.target === svgRef.current) setHoveredUnitId(null); }}
      >
        <defs>
          {/* Tank gradients */}
          <linearGradient id="grad-tank" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#bfdbfe" /><stop offset="40%" stopColor="#eff6ff" /><stop offset="75%" stopColor="#dbeafe" /><stop offset="100%" stopColor="#93c5fd" />
          </linearGradient>
          {/* Column gradient */}
          <linearGradient id="grad-col" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#94a3b8" /><stop offset="35%" stopColor="#e2e8f0" /><stop offset="70%" stopColor="#cbd5e1" /><stop offset="100%" stopColor="#64748b" />
          </linearGradient>
          {/* Reactor */}
          <linearGradient id="grad-reactor" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#c7d2fe" /><stop offset="40%" stopColor="#eef2ff" /><stop offset="75%" stopColor="#c7d2fe" /><stop offset="100%" stopColor="#818cf8" />
          </linearGradient>
          {/* FCC */}
          <linearGradient id="grad-fcc" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#a5f3fc" /><stop offset="45%" stopColor="#ecfeff" /><stop offset="100%" stopColor="#67e8f9" />
          </linearGradient>
          {/* Furnace */}
          <linearGradient id="grad-furnace" x1="0%" y1="100%" x2="0%" y2="0%">
            <stop offset="0%" stopColor="#dc2626" /><stop offset="50%" stopColor="#f97316" /><stop offset="100%" stopColor="#fbbf24" />
          </linearGradient>
          {/* Cooling tower */}
          <linearGradient id="grad-tower" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#bae6fd" /><stop offset="50%" stopColor="#e0f2fe" /><stop offset="100%" stopColor="#7dd3fc" />
          </linearGradient>
          {/* Generic unit */}
          <linearGradient id="grad-generic" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#a7f3d0" /><stop offset="45%" stopColor="#f0fdf4" /><stop offset="100%" stopColor="#6ee7b7" />
          </linearGradient>
          {/* Spherical tank */}
          <radialGradient id="grad-sphere" cx="35%" cy="30%" r="70%">
            <stop offset="0%" stopColor="#ffffff" /><stop offset="45%" stopColor="#bfdbfe" /><stop offset="100%" stopColor="#60a5fa" />
          </radialGradient>

          {/* Grid pattern */}
          <pattern id="eng-grid" width="30" height="30" patternUnits="userSpaceOnUse">
            <path d="M 30 0 L 0 0 0 30" fill="none" stroke="rgba(148,163,184,0.18)" strokeWidth="0.6" />
          </pattern>

          {/* Clean soft drop shadows */}
          <filter id="f-shadow" x="-8%" y="-8%" width="120%" height="120%">
            <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="#0f172a" floodOpacity="0.08" />
          </filter>
          <filter id="f-crit-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="0" stdDeviation="6" floodColor="#ef4444" floodOpacity="0.6" />
          </filter>
          <filter id="f-sel-glow" x="-15%" y="-15%" width="130%" height="130%">
            <feDropShadow dx="0" dy="0" stdDeviation="5" floodColor="#0284c7" floodOpacity="0.5" />
          </filter>
        </defs>

        {/* ── PAN/ZOOM INNER WRAPPER ── */}
        <g transform={`translate(${vbCx},${vbCy}) scale(${zoom}) translate(${-vbCx + tx},${-vbCy + ty})`}>
          {/* Engineering grid background */}
          <rect x="0" y="0" width="1380" height="540" fill="url(#eng-grid)" data-bg="true" />

          {/* ── 1. ZONE BANDS ───────────────────────────────────────────── */}
          {ZONE_BANDS.map((z) => (
            <g key={z.name} data-bg="true">
              <rect x={z.x} y="38" width={z.w} height="480" fill={z.fill} rx="8" data-bg="true" />
              <line x1={z.x} y1="38" x2={z.x + z.w} y2="38" stroke={z.accent} strokeWidth="2.5" opacity={0.6} />
              <text x={z.x + z.w / 2} y="54" textAnchor="middle" fill={z.accent} fontSize="9.5" fontWeight="800" letterSpacing="0.16em" fontFamily="monospace">
                {z.name}
              </text>
              <line x1={z.x + z.w} y1="42" x2={z.x + z.w} y2="510" stroke="rgba(148,163,184,0.3)" strokeWidth="1" strokeDasharray="3,3" />
            </g>
          ))}

          {/* ── 2. PROCESS PIPELINES ────────────────────────────────────── */}
          {REFINERY_PIPELINES.map((pipe) => {
            const isReroute = failover && pipe.isRerouteCandidate;
            const isOriginPipe = activeIncident && pipe.isCriticalPath;
            return (
              <g key={pipe.id} style={{ pointerEvents: "none" }}>
                {/* Glow underlay */}
                <path
                  d={pipe.d}
                  fill="none"
                  stroke={isReroute ? "#10b981" : isOriginPipe ? "#ef4444" : pipe.color}
                  strokeWidth="6"
                  opacity={isReroute ? 0.45 : isOriginPipe ? 0.35 : 0.22}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                {/* Main pipe */}
                <path
                  d={pipe.d}
                  fill="none"
                  stroke={isReroute ? "#10b981" : isOriginPipe ? "#ef4444" : pipe.color}
                  strokeWidth="2.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                {/* Flow animation dashes */}
                <path
                  d={pipe.d}
                  fill="none"
                  stroke="#ffffff"
                  strokeWidth="1.8"
                  strokeDasharray="4 8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  opacity={0.8}
                  style={{ animation: isOriginPipe ? "mr-pipe-disrupted 0.6s linear infinite" : "mr-pipe-flow 1.2s linear infinite" }}
                />

                {/* Optional mini label */}
                {pipe.label && pipe.labelPos && (
                  <text
                    x={pipe.labelPos.x}
                    y={pipe.labelPos.y}
                    fontSize="7.5"
                    fontFamily="monospace"
                    fontWeight="700"
                    fill={pipe.color}
                    textAnchor="middle"
                    style={{ textShadow: "0 0 3px #fff, 0 0 3px #fff" }}
                  >
                    {pipe.label}
                  </text>
                )}

                {/* Valves */}
                {pipe.valves?.map((v, i) => (
                  <g key={i} transform={`translate(${v.x},${v.y})`}>
                    {v.orientation === "h" ? (
                      <>
                        <polygon points="-5,-4 -5,4 5,-4 5,4" fill="#334155" stroke="#94a3b8" strokeWidth="1" />
                        <line x1="0" y1="-4" x2="0" y2="-7" stroke="#475569" strokeWidth="1" />
                        <circle cx="0" cy="-7" r="2" fill="#e2e8f0" stroke="#475569" strokeWidth="1" />
                      </>
                    ) : (
                      <>
                        <polygon points="-4,-5 4,-5 -4,5 4,5" fill="#334155" stroke="#94a3b8" strokeWidth="1" />
                        <line x1="4" y1="0" x2="7" y2="0" stroke="#475569" strokeWidth="1" />
                        <circle cx="7" cy="0" r="2" fill="#e2e8f0" stroke="#475569" strokeWidth="1" />
                      </>
                    )}
                  </g>
                ))}
              </g>
            );
          })}

          {/* ── 3. AI AGENT CHOREOGRAPHY BEAMS & PULSES ───────────────── */}
          {activeIncident && activeOriginUnit && (
            <g style={{ pointerEvents: "none" }}>
              {/* Concentric expanding ripples around incident origin */}
              <circle cx={activeOriginUnit.x + activeOriginUnit.w / 2} cy={activeOriginUnit.y + activeOriginUnit.h / 2} r="45" fill="none" stroke="#ef4444" strokeWidth="2" style={{ animation: "mr-origin-ring-1 2s ease-out infinite" }} />
              <circle cx={activeOriginUnit.x + activeOriginUnit.w / 2} cy={activeOriginUnit.y + activeOriginUnit.h / 2} r="65" fill="none" stroke="#f59e0b" strokeWidth="1.5" strokeDasharray="3 3" style={{ animation: "mr-origin-ring-2 2.5s ease-out infinite" }} />

              {/* Agent investigation lines */}
              {agentPhase >= 1 && (
                <path
                  d={`M ${AGENTS[0].ax} ${AGENTS[0].ay} Q ${(AGENTS[0].ax + activeOriginUnit.x) / 2} ${Math.min(AGENTS[0].ay, activeOriginUnit.y) - 20} ${activeOriginUnit.x + activeOriginUnit.w / 2} ${activeOriginUnit.y}`}
                  fill="none" stroke="#f59e0b" strokeWidth="2" strokeDasharray="5 4" style={{ animation: "mr-agent-sweep 1.2s linear infinite" }}
                />
              )}
              {agentPhase >= 2 && (
                <path
                  d={`M ${AGENTS[1].ax} ${AGENTS[1].ay} Q 620 180 ${activeOriginUnit.x + activeOriginUnit.w / 2} ${activeOriginUnit.y + activeOriginUnit.h / 2}`}
                  fill="none" stroke="#06b6d4" strokeWidth="2.2" strokeDasharray="6 3" style={{ animation: "mr-agent-sweep 0.9s linear infinite" }}
                />
              )}
              {agentPhase >= 3 && (
                <path
                  d={`M ${AGENTS[2].ax} ${AGENTS[2].ay} Q 880 220 ${activeOriginUnit.x + activeOriginUnit.w / 2} ${activeOriginUnit.y + activeOriginUnit.h}`}
                  fill="none" stroke="#10b981" strokeWidth="2" strokeDasharray="4 4" style={{ animation: "mr-agent-sweep 1.4s linear infinite" }}
                />
              )}
            </g>
          )}

          {/* ── 4. EQUIPMENT RENDERING & INTEGRATED BADGES ──────────────── */}
          {liveUnits.map((unit) => {
            const isSel = Boolean(
              selected && (
                selected.id === unit.id ||
                selected.tag === unit.tag ||
                selected.id === `e-${unit.tag}` ||
                (unit.eq && (selected.id === unit.eq.id || selected.tag === unit.eq.tag)) ||
                (EQUIPMENT_ALIASES[unit.tag] && (EQUIPMENT_ALIASES[unit.tag].includes(selected.tag) || EQUIPMENT_ALIASES[unit.tag].includes(selected.id)))
              )
            );
            const isCritical = unit.status === "Critical";
            const isWarning = unit.status === "Warning";

            const statusColor = isCritical ? "#ef4444" : isWarning ? "#f59e0b" : "#10b981";
            const eqFilter = isCritical ? "url(#f-crit-glow)" : isSel ? "url(#f-sel-glow)" : "url(#f-shadow)";

            return (
              <g
                key={unit.id}
                transform={`translate(${unit.x},${unit.y})`}
                style={{ cursor: "pointer", pointerEvents: "all" }}
                onClick={(e) => {
                  e.stopPropagation();
                  const eq = unit.eq || resolveEquipment(unit, plant);
                  onSelectEquipment(eq);
                }}
                onMouseEnter={() => setHoveredUnitId(unit.id)}
                onMouseLeave={() => setHoveredUnitId(null)}
              >
                {/* ── 4A. EQUIPMENT SVG SHAPES ── */}

                {/* ── TANK ── */}
                {unit.kind === "tank" && (
                  <g filter={eqFilter}>
                    <rect x="0" y="16" width={unit.w} height={unit.h - 16} rx="4" fill="url(#grad-tank)" stroke={isSel ? "#0284c7" : "#60a5fa"} strokeWidth={isSel ? 2.5 : 1.6} />
                    <ellipse cx={unit.w / 2} cy="16" rx={unit.w / 2} ry="10" fill="#dbeafe" stroke={isSel ? "#0284c7" : "#60a5fa"} strokeWidth={isSel ? 2.5 : 1.6} />
                    <line x1="8" y1={unit.h * 0.4} x2={unit.w - 8} y2={unit.h * 0.4} stroke="#93c5fd" strokeWidth="1" strokeDasharray="3 3" />
                    <line x1="8" y1={unit.h * 0.7} x2={unit.w - 8} y2={unit.h * 0.7} stroke="#93c5fd" strokeWidth="1" strokeDasharray="3 3" />
                    <rect x="6" y={unit.h - 8} width={unit.w - 12} height="8" fill="#64748b" rx="1" opacity={0.6} />
                  </g>
                )}

                {/* ── SPHERICAL TANK ── */}
                {unit.kind === "spherical_tank" && (
                  <g filter={eqFilter}>
                    <circle cx={unit.w / 2} cy={unit.h / 2} r={unit.w / 2 - 2} fill="url(#grad-sphere)" stroke={isSel ? "#0284c7" : "#3b82f6"} strokeWidth={isSel ? 2.5 : 1.8} />
                    <ellipse cx={unit.w / 2} cy={unit.h / 2} rx={unit.w / 2 - 4} ry="8" fill="none" stroke="#60a5fa" strokeWidth="1" opacity={0.7} />
                    <line x1={unit.w * 0.22} y1={unit.h * 0.72} x2={unit.w * 0.15} y2={unit.h + 2} stroke="#64748b" strokeWidth="2.5" />
                    <line x1={unit.w * 0.78} y1={unit.h * 0.72} x2={unit.w * 0.85} y2={unit.h + 2} stroke="#64748b" strokeWidth="2.5" />
                  </g>
                )}

                {/* ── PUMP ── */}
                {unit.kind === "pump" && (
                  <g filter={eqFilter}>
                    <rect x="0" y={unit.h - 10} width={unit.w} height="10" rx="2" fill="#64748b" stroke="#475569" strokeWidth="1" />
                    <circle cx={unit.w * 0.38} cy={unit.h * 0.45} r={unit.h * 0.38} fill="url(#grad-col)" stroke={isSel ? "#0284c7" : "#475569"} strokeWidth={isSel ? 2.5 : 1.8} />
                    <g style={{ transformOrigin: `${unit.w * 0.38}px ${unit.h * 0.45}px`, animation: "mr-pump-spin 2s linear infinite" }}>
                      <line x1={unit.w * 0.38} y1={unit.h * 0.15} x2={unit.w * 0.38} y2={unit.h * 0.75} stroke="#0284c7" strokeWidth="2" />
                      <line x1={unit.w * 0.1} y1={unit.h * 0.45} x2={unit.w * 0.66} y2={unit.h * 0.45} stroke="#0284c7" strokeWidth="2" />
                    </g>
                    <rect x={unit.w * 0.65} y={unit.h * 0.22} width={unit.w * 0.32} height={unit.h * 0.48} rx="3" fill="#93c5fd" stroke="#3b82f6" strokeWidth="1.4" />
                    <line x1={unit.w * 0.72} y1={unit.h * 0.22} x2={unit.w * 0.72} y2={unit.h * 0.7} stroke="#2563eb" strokeWidth="1" />
                    <line x1={unit.w * 0.82} y1={unit.h * 0.22} x2={unit.w * 0.82} y2={unit.h * 0.7} stroke="#2563eb" strokeWidth="1" />
                  </g>
                )}

                {/* ── DESALTER ── */}
                {unit.kind === "desalter" && (
                  <g filter={eqFilter}>
                    <rect x="0" y="10" width={unit.w} height={unit.h - 20} rx={(unit.h - 20) / 2} fill="url(#grad-tank)" stroke={isSel ? "#0284c7" : "#60a5fa"} strokeWidth={isSel ? 2.5 : 1.8} />
                    <line x1={unit.w * 0.25} y1={unit.h - 10} x2={unit.w * 0.25} y2={unit.h} stroke="#64748b" strokeWidth="3" />
                    <line x1={unit.w * 0.75} y1={unit.h - 10} x2={unit.w * 0.75} y2={unit.h} stroke="#64748b" strokeWidth="3" />
                    <circle cx={unit.w * 0.35} cy={unit.h / 2} r="4" fill="#93c5fd" stroke="#2563eb" strokeWidth="1" />
                    <circle cx={unit.w * 0.65} cy={unit.h / 2} r="4" fill="#93c5fd" stroke="#2563eb" strokeWidth="1" />
                  </g>
                )}

                {/* ── FURNACE ── */}
                {unit.kind === "furnace" && (
                  <g filter={eqFilter}>
                    <rect x={unit.w * 0.38} y="0" width={unit.w * 0.24} height={unit.h * 0.38} fill="#94a3b8" stroke="#64748b" strokeWidth="1.5" />
                    <polygon points={`0,${unit.h * 0.38} ${unit.w},${unit.h * 0.38} ${unit.w},${unit.h} 0,${unit.h}`} fill="url(#grad-col)" stroke={isSel ? "#0284c7" : "#64748b"} strokeWidth={isSel ? 2.5 : 1.8} />
                    <rect x={unit.w * 0.2} y={unit.h * 0.52} width={unit.w * 0.6} height={unit.h * 0.38} rx="3" fill="url(#grad-furnace)" opacity={0.9} />
                    <ellipse cx={unit.w / 2} cy={unit.h * 0.72} rx={unit.w * 0.18} ry={unit.h * 0.12} fill="#fef08a" opacity={0.95} />
                  </g>
                )}

                {/* ── DISTILLATION COLUMN ── */}
                {unit.kind === "column" && (
                  <g filter={eqFilter}>
                    <rect x="0" y="14" width={unit.w} height={unit.h - 28} fill="url(#grad-col)" stroke={isSel ? "#0284c7" : "#64748b"} strokeWidth={isSel ? 2.5 : 1.8} />
                    <ellipse cx={unit.w / 2} cy="14" rx={unit.w / 2} ry="9" fill="#e2e8f0" stroke={isSel ? "#0284c7" : "#64748b"} strokeWidth={isSel ? 2.5 : 1.8} />
                    <ellipse cx={unit.w / 2} cy={unit.h - 14} rx={unit.w / 2} ry="9" fill="#cbd5e1" stroke={isSel ? "#0284c7" : "#64748b"} strokeWidth={isSel ? 2.5 : 1.8} />
                    {Array.from({ length: 9 }).map((_, i) => (
                      <line key={i} x1="4" y1={28 + i * ((unit.h - 56) / 8)} x2={unit.w - 4} y2={28 + i * ((unit.h - 56) / 8)} stroke="#94a3b8" strokeWidth="1.2" strokeDasharray="3 2" />
                    ))}
                    <line x1={unit.w * 0.22} y1={unit.h - 10} x2={unit.w * 0.22} y2={unit.h} stroke="#475569" strokeWidth="3" />
                    <line x1={unit.w * 0.78} y1={unit.h - 10} x2={unit.w * 0.78} y2={unit.h} stroke="#475569" strokeWidth="3" />
                  </g>
                )}

                {/* ── FCC UNIT ── */}
                {unit.kind === "fcc" && (
                  <g filter={eqFilter}>
                    <rect x="4" y="12" width={unit.w - 8} height={unit.h * 0.44} rx="6" fill="url(#grad-fcc)" stroke={isSel ? "#0284c7" : "#06b6d4"} strokeWidth={isSel ? 2.5 : 1.8} />
                    <ellipse cx={unit.w / 2} cy="12" rx={(unit.w - 8) / 2} ry="7" fill="#cffafe" stroke="#06b6d4" strokeWidth="1.5" />
                    <rect x="10" y={unit.h * 0.52} width={unit.w - 20} height={unit.h * 0.42} rx="5" fill="url(#grad-reactor)" stroke={isSel ? "#0284c7" : "#6366f1"} strokeWidth={isSel ? 2.5 : 1.8} />
                    <path d={`M ${unit.w * 0.3} ${unit.h * 0.44} L ${unit.w * 0.3} ${unit.h * 0.52}`} stroke="#0891b2" strokeWidth="3" />
                    <path d={`M ${unit.w * 0.7} ${unit.h * 0.44} L ${unit.w * 0.7} ${unit.h * 0.52}`} stroke="#6366f1" strokeWidth="3" />
                    <line x1="8" y1={unit.h * 0.24} x2={unit.w - 8} y2={unit.h * 0.24} stroke="#0891b2" strokeWidth="1.2" strokeDasharray="3 2" />
                  </g>
                )}

                {/* ── REACTOR ── */}
                {unit.kind === "reactor" && (
                  <g filter={eqFilter}>
                    <rect x="0" y="12" width={unit.w} height={unit.h - 24} rx="4" fill="url(#grad-reactor)" stroke={isSel ? "#0284c7" : "#818cf8"} strokeWidth={isSel ? 2.5 : 1.8} />
                    <ellipse cx={unit.w / 2} cy="12" rx={unit.w / 2} ry="8" fill="#e0e7ff" stroke="#818cf8" strokeWidth="1.5" />
                    <ellipse cx={unit.w / 2} cy={unit.h - 12} rx={unit.w / 2} ry="8" fill="#c7d2fe" stroke="#818cf8" strokeWidth="1.5" />
                    <line x1="6" y1={unit.h * 0.35} x2={unit.w - 6} y2={unit.h * 0.35} stroke="#a5b4fc" strokeWidth="1.4" />
                    <line x1="6" y1={unit.h * 0.65} x2={unit.w - 6} y2={unit.h * 0.65} stroke="#a5b4fc" strokeWidth="1.4" />
                    <line x1={unit.w * 0.22} y1={unit.h - 8} x2={unit.w * 0.22} y2={unit.h} stroke="#475569" strokeWidth="3" />
                    <line x1={unit.w * 0.78} y1={unit.h - 8} x2={unit.w * 0.78} y2={unit.h} stroke="#475569" strokeWidth="3" />
                  </g>
                )}

                {/* ── COOLING TOWER ── */}
                {unit.kind === "cooling_tower" && (
                  <g filter={eqFilter}>
                    <polygon
                      points={`12,0 ${unit.w - 12},0 ${unit.w - 4},${unit.h * 0.4} ${unit.w},${unit.h} 0,${unit.h} 4,${unit.h * 0.4}`}
                      fill="url(#grad-tower)" stroke={isSel ? "#0284c7" : "#0284c7"} strokeWidth={isSel ? 2.5 : 1.8}
                    />
                    <path d={`M 14 0 Q ${unit.w / 2} -12 ${unit.w - 14} 0`} fill="none" stroke="#e0f2fe" strokeWidth="2.5" opacity={0.8} />
                    <line x1="8" y1={unit.h * 0.55} x2={unit.w - 8} y2={unit.h * 0.55} stroke="#38bdf8" strokeWidth="1.2" strokeDasharray="3 3" />
                  </g>
                )}

                {/* ── FLARE ── */}
                {unit.kind === "flare" && (
                  <g filter={eqFilter}>
                    <rect x={unit.w / 2 - 3.5} y="18" width="7" height={unit.h - 18} fill="#9ca3af" stroke={isSel ? "#0284c7" : "#6b7280"} strokeWidth={isSel ? 2.5 : 1.5} />
                    <path d={`M ${unit.w / 2 - 8} 20 Q ${unit.w / 2} -6 ${unit.w / 2 + 8} 20 Z`} fill="url(#grad-furnace)" opacity={0.9} style={{ animation: "mr-reroute-glow 0.6s ease-in-out infinite" }} />
                    <rect x="2" y={unit.h - 16} width={unit.w - 4} height="12" rx="3" fill="#e2e8f0" stroke="#94a3b8" strokeWidth="1" />
                  </g>
                )}

                {/* ── GENERIC (amine, sru, gas_treat, boiler, power_gen) ── */}
                {(unit.kind === "amine" || unit.kind === "sru" || unit.kind === "gas_treat" || unit.kind === "boiler" || unit.kind === "power_gen") && (
                  <g filter={eqFilter}>
                    <rect x="0" y="8" width={unit.w} height={unit.h - 14} rx="4" fill="url(#grad-generic)" stroke={isSel ? "#0284c7" : "#34d399"} strokeWidth={isSel ? 2.5 : 1.8} />
                    <ellipse cx={unit.w / 2} cy="8" rx={unit.w / 2} ry="6" fill="#d1fae5" stroke="#34d399" strokeWidth="1.4" />
                    <rect x="4" y={unit.h - 6} width={unit.w - 8} height="6" fill="#86efac" stroke="#4ade80" strokeWidth="0.8" />
                    {unit.kind === "power_gen" && <text x={unit.w / 2} y={unit.h * 0.62} textAnchor="middle" fontSize="12" fill="#f59e0b">⚡</text>}
                  </g>
                )}

                {/* ── 4B. INTEGRATED COMPACT TAG & TELEMETRY PILL (NO OVERLAP) ── */}
                {/* Header Tag + Status Dot (Directly Above) */}
                <g transform={`translate(${unit.w / 2}, -9)`}>
                  <rect
                    x="-34"
                    y="-10"
                    width="68"
                    height="18"
                    rx="4"
                    fill={isSel ? "#f0f9ff" : "#ffffff"}
                    stroke={isCritical ? "#ef4444" : isWarning ? "#f59e0b" : isSel ? "#0284c7" : "#cbd5e1"}
                    strokeWidth={isSel || isCritical ? "2" : "1"}
                    filter="url(#f-shadow)"
                  />
                  <circle cx="-24" cy="-1" r="3" fill={statusColor} />
                  <text x="-16" y="2.5" fontSize="8.5" fontWeight="700" fill={isSel ? "#0284c7" : "#0f172a"} fontFamily="monospace">
                    {unit.tag}
                  </text>
                </g>

                {/* Sub Telemetry Badge (Directly Below Unit) */}
                <g transform={`translate(${unit.w / 2}, ${unit.h + 12})`}>
                  <rect
                    x="-42"
                    y="-8"
                    width="84"
                    height="16"
                    rx="3"
                    fill="rgba(255,255,255,0.94)"
                    stroke={isSel ? "#0284c7" : "#e2e8f0"}
                    strokeWidth={isSel ? "1.5" : "1"}
                  />
                  <text x="0" y="3.5" textAnchor="middle" fontSize="8" fontWeight="700" fill={isSel ? "#0284c7" : "#0369a1"} fontFamily="monospace">
                    {unit.temperature ? unit.temperature : unit.flow ? unit.flow : unit.power ? unit.power : unit.pressure ? unit.pressure : unit.status}
                  </text>
                </g>
              </g>
            );
          })}

          {/* ── 5. PIPE LEGEND (Bottom Right) ───────────────────────────── */}
          <g transform="translate(1000, 465)" style={{ pointerEvents: "none" }}>
            <rect x="0" y="0" width="340" height="52" rx="6" fill="rgba(255,255,255,0.92)" stroke="#cbd5e1" strokeWidth="1" filter="url(#f-shadow)" />
            <text x="12" y="14" fontSize="8.5" fontWeight="800" fill="#475569" fontFamily="monospace" letterSpacing="0.12em">PROCESS STREAM LEGEND</text>
            <g transform="translate(12, 24)">
              <line x1="0" y1="3" x2="16" y2="3" stroke="#f59e0b" strokeWidth="2.8" />
              <text x="22" y="6" fontSize="8" fontWeight="600" fill="#334155" fontFamily="sans-serif">Crude Feed</text>
            </g>
            <g transform="translate(95, 24)">
              <line x1="0" y1="3" x2="16" y2="3" stroke="#06b6d4" strokeWidth="2.8" />
              <text x="22" y="6" fontSize="8" fontWeight="600" fill="#334155" fontFamily="sans-serif">Conversion Gas</text>
            </g>
            <g transform="translate(195, 24)">
              <line x1="0" y1="3" x2="16" y2="3" stroke="#10b981" strokeWidth="2.8" />
              <text x="22" y="6" fontSize="8" fontWeight="600" fill="#334155" fontFamily="sans-serif">Treated Products</text>
            </g>
            <g transform="translate(12, 39)">
              <line x1="0" y1="3" x2="16" y2="3" stroke="#f97316" strokeWidth="2.8" />
              <text x="22" y="6" fontSize="8" fontWeight="600" fill="#334155" fontFamily="sans-serif">High Press Steam</text>
            </g>
            <g transform="translate(130, 39)">
              <line x1="0" y1="3" x2="16" y2="3" stroke="#ef4444" strokeWidth="2.8" />
              <text x="22" y="6" fontSize="8" fontWeight="600" fill="#334155" fontFamily="sans-serif">Sour Gas / Flare</text>
            </g>
          </g>

          {/* Watermark */}
          <text x="690" y="528" textAnchor="middle" fontSize="8" fontFamily="monospace" fill="#94a3b8" letterSpacing="0.2em" style={{ pointerEvents: "none" }}>
            MERIDIAN SYNTHETIC REFINERY · SOVEREIGN DIGITAL TWIN · PROJECT 117
          </text>
        </g>
      </svg>

      {/* AI Agent Workforce Dispatch boxes */}
      <AgentDispatchBoxes tasks={tasks} models={models} />
    </div>
  );
}
