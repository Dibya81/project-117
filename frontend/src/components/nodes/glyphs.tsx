/**
 * Equipment glyphs.
 *
 * Inline SVG per equipment type — no image assets, so the canvas stays sharp at
 * any zoom and nothing has to be fetched. Each glyph is drawn on a 24×24 grid.
 */
import type { EquipmentType } from "../../types";

const S = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

function Pump() {
  return (
    <>
      <circle cx="10" cy="12" r="5.5" {...S} />
      <path d="M15.5 12h5M20.5 9.5v5M4.5 12H2" {...S} />
    </>
  );
}
function Valve() {
  return (
    <>
      <path d="M4 7l8 5-8 5V7zM20 7l-8 5 8 5V7z" {...S} />
      <path d="M12 12V5M9.5 5h5" {...S} />
    </>
  );
}
function Tank() {
  return (
    <>
      <rect x="5" y="6" width="14" height="13" rx="2.5" {...S} />
      <path d="M5 13h14M9 6V4M15 6V4" {...S} />
    </>
  );
}
function Exchanger() {
  return (
    <>
      <rect x="3" y="8" width="18" height="9" rx="2" {...S} />
      <path d="M7 8v9M11 8v9M15 8v9M3 12.5h18" {...S} />
    </>
  );
}
function Compressor() {
  return (
    <>
      <circle cx="12" cy="12" r="5" {...S} />
      <path d="M12 7v10M7 12h10M8.5 8.5l7 7M15.5 8.5l-7 7" {...S} />
    </>
  );
}
function Blower() {
  return (
    <>
      <rect x="4" y="7" width="10" height="10" rx="2" {...S} />
      <path d="M14 12h4a2.5 2.5 0 0 1 0 5h-3" {...S} />
      <circle cx="9" cy="12" r="2.4" {...S} />
    </>
  );
}
function Column() {
  return (
    <>
      <rect x="8" y="3" width="8" height="18" rx="3.5" {...S} />
      <path d="M8 8h8M8 12h8M8 16h8" {...S} />
    </>
  );
}
function Reactor() {
  return (
    <>
      <rect x="7" y="6" width="10" height="14" rx="2" {...S} />
      <path d="M7 10h10M12 3v3M9.5 3h5" {...S} />
    </>
  );
}
function Furnace() {
  return (
    <>
      <path d="M6 20V9a6 6 0 0 1 12 0v11z" {...S} />
      <path d="M12 17c1.6-1 1.6-3 .6-4.2-.8-1-.6-2 .4-3-2.2.4-3.4 2-3 3.6.3 1.3-.2 2.4-1 3 .8.5 2 .6 3 .6z" {...S} />
    </>
  );
}
function Conveyor() {
  return (
    <>
      <path d="M2 15h20" {...S} />
      <circle cx="6" cy="15" r="3" {...S} />
      <circle cx="18" cy="15" r="3" {...S} />
      <rect x="9" y="7" width="6" height="5" rx="1" {...S} />
    </>
  );
}
function Motor() {
  return (
    <>
      <rect x="4" y="8" width="13" height="9" rx="2" {...S} />
      <path d="M17 12h3M8 8V6M12 8V6" {...S} />
    </>
  );
}
function Caster() {
  return (
    <>
      <path d="M5 5h9l5 6-5 6H5z" {...S} />
      <path d="M9 9h6M9 13h6" {...S} />
    </>
  );
}
function MillStand() {
  return (
    <>
      <rect x="6" y="4" width="12" height="5" rx="1" {...S} />
      <rect x="6" y="15" width="12" height="5" rx="1" {...S} />
      <path d="M4 11.5h16M12 9v6" {...S} />
    </>
  );
}

const GLYPHS: Record<EquipmentType, () => JSX.Element> = {
  pump: Pump,
  valve: Valve,
  tank: Tank,
  heat_exchanger: Exchanger,
  compressor: Compressor,
  compressor_blower: Blower,
  column: Column,
  reactor: Reactor,
  furnace: Furnace,
  conveyor: Conveyor,
  motor: Motor,
  caster: Caster,
  mill_stand: MillStand,
};

export function EquipmentGlyph({ type, size = 22 }: { type: EquipmentType; size?: number }) {
  const G = GLYPHS[type] ?? Valve;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <G />
    </svg>
  );
}
