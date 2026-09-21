/**
 * Builder palette.
 *
 * Grouped by process role. The draggable types are exactly the ones the schema
 * declares — `equipment.type` in schema.sql and the five sensor types — so a
 * dropped node is always a valid row. Items are HTML5-draggable; the canvas
 * reads the same MIME keys.
 */
import type { EquipmentType, SensorType } from "../types";
import { EquipmentGlyph } from "./nodes/glyphs";
import { EQUIPMENT_LABEL } from "../sim/validate";
import { SENSOR_LABEL } from "../sim/thresholds";
import { DND_EQUIPMENT, DND_SENSOR } from "./Canvas";

interface Group {
  title: string;
  note?: string;
  equipment: EquipmentType[];
}

const GROUPS: Group[] = [
  { title: "Process", equipment: ["tank", "column", "heat_exchanger", "furnace", "reactor"] },
  { title: "Flow", equipment: ["pump", "valve", "compressor", "compressor_blower", "motor", "conveyor"] },
  { title: "Heavy", note: "steel plant types", equipment: ["caster", "mill_stand"] },
];

const SENSORS: SensorType[] = ["PT", "TT", "FT", "LT", "VT"];

export function Palette() {
  return (
    <aside className="palette" aria-label="Builder palette">
      <h3 className="palette__title">Palette</h3>
      <p className="palette__hint">Drag onto the canvas. Sensors wire into equipment only.</p>

      <section className="palette__group">
        <h4>Instrumentation</h4>
        <div className="palette__items">
          {SENSORS.map((t) => (
            <div
              key={t}
              className="palette__item palette__item--sensor"
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData(DND_SENSOR, t);
                e.dataTransfer.effectAllowed = "move";
              }}
              title={`${t} — ${SENSOR_LABEL[t]}`}
            >
              <span className="palette__badge">{t}</span>
              <span className="palette__label">{SENSOR_LABEL[t]}</span>
            </div>
          ))}
        </div>
      </section>

      {GROUPS.map((g) => (
        <section className="palette__group" key={g.title}>
          <h4>
            {g.title}
            {g.note && <em>{g.note}</em>}
          </h4>
          <div className="palette__items">
            {g.equipment.map((t) => (
              <div
                key={t}
                className="palette__item"
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.setData(DND_EQUIPMENT, t);
                  e.dataTransfer.effectAllowed = "move";
                }}
                title={EQUIPMENT_LABEL[t]}
              >
                <EquipmentGlyph type={t} size={18} />
                <span className="palette__label">{EQUIPMENT_LABEL[t]}</span>
              </div>
            ))}
          </div>
        </section>
      ))}
    </aside>
  );
}
