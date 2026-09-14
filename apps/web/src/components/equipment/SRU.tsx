import { assetDefs, ladder, palette, ports, statusBeacon, tagPlate, type EquipmentAssetProps } from "./shared";

export function SRU({ box: b, id, name = "SRU", status, selected }: EquipmentAssetProps) {
  return (
    <g data-equipment-asset="sulfur-recovery-unit">
      {assetDefs("eq-sru")}
      <g filter="url(#eq-sru-shadow)">
        <rect x={b.x + b.w * 0.1} y={b.y + b.h * 0.32} width={b.w * 0.42} height={b.h * 0.42} rx={4} fill="url(#eq-sru-warm)" stroke={palette.orange} strokeWidth={1.6} />
        <rect x={b.x + b.w * 0.58} y={b.y + b.h * 0.22} width={b.w * 0.28} height={b.h * 0.56} rx={b.w * 0.14} fill="url(#eq-sru-steel)" stroke={palette.stroke} strokeWidth={1.5} />
        <path d={`M ${b.x + b.w * 0.52} ${b.y + b.h * 0.53} H ${b.x + b.w * 0.58}`} stroke={palette.stroke} strokeWidth={2.2} />
        <rect x={b.x + b.w * 0.2} y={b.y + b.h * 0.18} width={b.w * 0.1} height={b.h * 0.14} fill="#cbd5e1" stroke={palette.stroke} strokeWidth={1.1} />
        <circle cx={b.x + b.w * 0.27} cy={b.y + b.h * 0.53} r={b.h * 0.08} fill="#fef3c7" stroke={palette.orange} strokeWidth={1.1} />
      </g>
      {ports(b, [[0.02, 0.53], [0.98, 0.53], [0.25, 0.18], [0.72, 0.82]])}
      {tagPlate(b, id, name)}
      {statusBeacon(b, status, selected)}
    </g>
  );
}

export function GasTreatmentUnit({ box: b, id, name = "Gas Treatment", status, selected }: EquipmentAssetProps) {
  return (
    <g data-equipment-asset="gas-treatment-unit">
      {assetDefs("eq-gas-treatment")}
      <g filter="url(#eq-gas-treatment-shadow)">
        <rect x={b.x + b.w * 0.1} y={b.y + b.h * 0.72} width={b.w * 0.8} height={b.h * 0.08} rx={2} fill="#64748b" stroke={palette.stroke} strokeWidth={1.1} />
        <rect x={b.x + b.w * 0.16} y={b.y + b.h * 0.2} width={b.w * 0.24} height={b.h * 0.55} rx={b.w * 0.12} fill="url(#eq-gas-treatment-steel)" stroke={palette.stroke} strokeWidth={1.4} />
        <rect x={b.x + b.w * 0.47} y={b.y + b.h * 0.28} width={b.w * 0.28} height={b.h * 0.39} rx={4} fill="#cbd5e1" stroke={palette.stroke} strokeWidth={1.2} />
        <path d={`M ${b.x + b.w * 0.4} ${b.y + b.h * 0.48} H ${b.x + b.w * 0.47}`} stroke={palette.cyan} strokeWidth={3} strokeLinecap="round" />
        <path d={`M ${b.x + b.w * 0.75} ${b.y + b.h * 0.48} H ${b.x + b.w * 0.9}`} stroke={palette.cyan} strokeWidth={3} strokeLinecap="round" />
        {[0.34, 0.42, 0.5, 0.58].map((p) => (
          <line key={p} x1={b.x + b.w * 0.19} y1={b.y + b.h * p} x2={b.x + b.w * 0.37} y2={b.y + b.h * p} stroke="#64748b" strokeWidth={0.8} opacity={0.5} />
        ))}
        <circle cx={b.x + b.w * 0.61} cy={b.y + b.h * 0.47} r={b.h * 0.08} fill="#ecfeff" stroke={palette.cyan} strokeWidth={1.1} />
        {ladder(b, "left", 0.24, 0.7)}
      </g>
      {ports(b, [[0.02, 0.48], [0.98, 0.48], [0.28, 0.16], [0.28, 0.82]])}
      {tagPlate(b, id, name)}
      {statusBeacon(b, status, selected)}
    </g>
  );
}

export function HydrogenUnit({ box: b, id, name = "Hydrogen Unit", status, selected }: EquipmentAssetProps) {
  return (
    <g data-equipment-asset="hydrogen-unit">
      {assetDefs("eq-hydrogen")}
      <g filter="url(#eq-hydrogen-shadow)">
        <rect x={b.x + b.w * 0.08} y={b.y + b.h * 0.68} width={b.w * 0.84} height={b.h * 0.1} rx={2} fill="#64748b" stroke={palette.stroke} strokeWidth={1.1} />
        <rect x={b.x + b.w * 0.1} y={b.y + b.h * 0.24} width={b.w * 0.26} height={b.h * 0.44} rx={4} fill="url(#eq-hydrogen-warm)" stroke={palette.orange} strokeWidth={1.4} />
        <rect x={b.x + b.w * 0.46} y={b.y + b.h * 0.14} width={b.w * 0.22} height={b.h * 0.56} rx={b.w * 0.11} fill="url(#eq-hydrogen-steel)" stroke={palette.stroke} strokeWidth={1.4} />
        <rect x={b.x + b.w * 0.75} y={b.y + b.h * 0.26} width={b.w * 0.12} height={b.h * 0.4} rx={2} fill="#dbeafe" stroke={palette.cyan} strokeWidth={1.1} />
        <path d={`M ${b.x + b.w * 0.36} ${b.y + b.h * 0.46} H ${b.x + b.w * 0.46} M ${b.x + b.w * 0.68} ${b.y + b.h * 0.46} H ${b.x + b.w * 0.75}`} stroke={palette.cyan} strokeWidth={3} strokeLinecap="round" />
        <g stroke="#9a5b13" strokeWidth={0.9} opacity={0.55}>
          {[0.31, 0.39, 0.47, 0.55].map((p) => (
            <line key={p} x1={b.x + b.w * 0.14} y1={b.y + b.h * p} x2={b.x + b.w * 0.32} y2={b.y + b.h * p} />
          ))}
        </g>
        <path d={`M ${b.x + b.w * 0.54} ${b.y + b.h * 0.2} q ${b.w * 0.04} ${b.h * 0.12} 0 ${b.h * 0.24} q ${-b.w * 0.04} ${b.h * 0.12} 0 ${b.h * 0.24}`} fill="none" stroke="#64748b" strokeWidth={1.1} />
      </g>
      {ports(b, [[0.02, 0.46], [0.98, 0.46], [0.57, 0.1], [0.57, 0.82]])}
      {tagPlate(b, id, name)}
      {statusBeacon(b, status, selected)}
    </g>
  );
}
