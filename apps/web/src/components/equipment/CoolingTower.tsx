import { assetDefs, palette, ports, statusBeacon, tagPlate, type EquipmentAssetProps } from "./shared";

export function CoolingTower({ box: b, id, name, status, selected }: EquipmentAssetProps) {
  return (
    <g data-equipment-asset="cooling-tower">
      {assetDefs("eq-cooling")}
      <g filter="url(#eq-cooling-shadow)">
        <polygon points={`${b.x + b.w * 0.18},${b.y + b.h * 0.08} ${b.x + b.w * 0.82},${b.y + b.h * 0.08} ${b.x + b.w * 0.95},${b.y + b.h * 0.96} ${b.x + b.w * 0.05},${b.y + b.h * 0.96}`} fill="url(#eq-cooling-cool)" stroke={palette.stroke} strokeWidth={1.7} />
        <path d={`M ${b.x + b.w * 0.2} ${b.y + b.h * 0.08} Q ${b.x + b.w * 0.5} ${b.y - b.h * 0.04} ${b.x + b.w * 0.8} ${b.y + b.h * 0.08}`} fill="none" stroke="#e0f2fe" strokeWidth={2.3} />
        <rect x={b.x + b.w * 0.18} y={b.y + b.h * 0.64} width={b.w * 0.64} height={b.h * 0.13} fill="#dbeafe" stroke="#38bdf8" strokeWidth={1.1} />
        <g stroke="#38bdf8" strokeWidth={1}>{Array.from({ length: 5 }, (_, i) => <line key={i} x1={b.x + b.w * (0.24 + i * 0.13)} y1={b.y + b.h * 0.16} x2={b.x + b.w * (0.18 + i * 0.16)} y2={b.y + b.h * 0.92} />)}</g>
      </g>
      {ports(b, [[0.05, 0.78], [0.95, 0.78], [0.5, 0.05]])}
      {tagPlate(b, id, name)}
      {statusBeacon(b, status, selected)}
    </g>
  );
}
