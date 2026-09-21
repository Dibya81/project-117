/**
 * Canvas nodes.
 *
 * Status is carried by a keyframe box-shadow glow on the node itself —
 * normal: none; active/flowing: soft blue pulse; warning: amber; critical: red
 * faster pulse; disabled: flat grey. Colour is never the only signal: each
 * state also shows a text label, which matters for the warning/critical pair.
 */
import { Handle, Position, type NodeProps } from "reactflow";
import type { Equipment, Sensor } from "../../types";
import { EquipmentGlyph } from "./glyphs";
import { SENSOR_COLOR, SENSOR_LABEL, formatBand, formatValue, lifeUsed, sensorLevel } from "../../sim/thresholds";
import { EQUIPMENT_LABEL } from "../../sim/validate";

const STATUS_TEXT: Record<string, string> = {
  normal: "NORMAL",
  warning: "WARNING",
  critical: "CRITICAL",
  disabled: "DISABLED",
};

export interface EquipmentNodeData extends Equipment {
  zoneName?: string;
  /** True while an agent event names this unit — edge animation follows it. */
  traced?: boolean;
  faulted?: boolean;
}

export function EquipmentNode({ data, selected }: NodeProps<EquipmentNodeData>) {
  const status = data.status ?? "normal";
  const used = lifeUsed(data.age_years, data.expected_lifespan_years);
  const classes = [
    "rf-eq",
    `rf-eq--${status}`,
    selected ? "is-selected" : "",
    data.traced ? "is-traced" : "",
    data.faulted ? "is-faulted" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={classes} title={`${data.tag} — ${EQUIPMENT_LABEL[data.type] ?? data.type}`}>
      <Handle type="target" position={Position.Left} id="in" className="rf-handle rf-handle--in" />
      <Handle type="target" position={Position.Top} id="sig" className="rf-handle rf-handle--sig" />
      <Handle type="source" position={Position.Right} id="out" className="rf-handle rf-handle--out" />

      <div className="rf-eq__top">
        <span className="rf-eq__glyph">
          <EquipmentGlyph type={data.type} />
        </span>
        <span className="rf-eq__tag">{data.tag}</span>
        <span className={`rf-eq__status rf-eq__status--${status}`}>{STATUS_TEXT[status] ?? status}</span>
      </div>

      <div className="rf-eq__type">{EQUIPMENT_LABEL[data.type] ?? data.type}</div>

      <div className="rf-eq__meta">
        <span className="rf-eq__life" aria-label={`${Math.round(used * 100)} percent of expected life used`}>
          <i style={{ width: `${Math.round(used * 100)}%` }} />
        </span>
        <span className="rf-eq__age">{data.age_years.toFixed(1)}/{data.expected_lifespan_years}y</span>
      </div>
    </div>
  );
}

export interface SensorNodeData extends Sensor {
  equipmentTag?: string;
  /** Bleeds the connected edge while an agent works on this unit. */
  traced?: boolean;
}

export function SensorNode({ data, selected }: NodeProps<SensorNodeData>) {
  const level = sensorLevel(data);
  const classes = [
    "rf-sensor",
    `rf-sensor--${level}`,
    selected ? "is-selected" : "",
    data.traced ? "is-traced" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={classes}
      title={`${data.tag} · ${SENSOR_LABEL[data.type] ?? data.type} · normal ${formatBand(data)} · current ${formatValue(data)}`}
    >
      <Handle type="target" position={Position.Left} id="in" className="rf-handle rf-handle--sig" />
      <Handle type="source" position={Position.Right} id="out" className="rf-handle rf-handle--in" />
      <span className="rf-sensor__type" style={{ background: SENSOR_COLOR[data.type] }}>
        {data.type}
      </span>
      <span className="rf-sensor__tag">{data.tag}</span>
      <span className="rf-sensor__value">{formatValue(data)}</span>
      <span className={`rf-sensor__dot rf-sensor__dot--${level}`} aria-hidden="true" />
      <span className="rf-sensor__level">{level === "normal" ? "in band" : level}</span>
    </div>
  );
}

export interface ZoneNodeData {
  name: string;
  sequence: number;
  unitCount: number;
  sensorCount: number;
}

export function ZoneNode({ data }: NodeProps<ZoneNodeData>) {
  return (
    <div className="rf-zone">
      <div className="rf-zone__head">
        <span className="rf-zone__seq">{String(data.sequence + 1).padStart(2, "0")}</span>
        <span className="rf-zone__name">{data.name}</span>
        <span className="rf-zone__counts">
          {data.unitCount} units · {data.sensorCount} sensors
        </span>
      </div>
    </div>
  );
}
