import { assetDefs, basePlate, palette, ports, statusBeacon, tagPlate, type EquipmentAssetProps } from "./shared";

export function Furnace({ box: b, id, name, status, selected }: EquipmentAssetProps) {
  return (
    <g data-equipment-asset="furnace">
      {assetDefs("eq-furnace")}
      <g filter="url(#eq-furnace-shadow)">
        <rect x={b.x + b.w * 0.7} y={b.y + b.h * 0.02} width={b.w * 0.1} height={b.h * 0.2} fill="#cbd5e1" stroke={palette.stroke} strokeWidth={1.3} />
        <rect x={b.x + b.w * 0.06} y={b.y + b.h * 0.16} width={b.w * 0.88} height={b.h * 0.72} rx={3} fill="#e8ded2" stroke={palette.stroke} strokeWidth={1.7} />
        <g stroke="#8b9aab" strokeWidth={1.1}>{Array.from({ length: 6 }, (_, i) => <line key={i} x1={b.x + b.w * 0.13} y1={b.y + b.h * (0.24 + i * 0.045)} x2={b.x + b.w * 0.87} y2={b.y + b.h * (0.24 + i * 0.045)} />)}</g>
        <rect x={b.x + b.w * 0.15} y={b.y + b.h * 0.54} width={b.w * 0.7} height={b.h * 0.29} rx={3} fill="#3d2618" stroke="#2a1a10" strokeWidth={1.2} />
        {[0.32, 0.5, 0.68].map((fx) => <path key={fx} d={`M ${b.x + b.w * fx} ${b.y + b.h * 0.8} q ${-b.w * 0.045} ${-b.h * 0.13} 0 ${-b.h * 0.24} q ${b.w * 0.048} ${b.h * 0.1} 0 ${b.h * 0.24} z`} fill="#f59e0b" />)}
        {basePlate(b, 0.88)}
      </g>
      {ports(b, [[0.02, 0.38], [0.98, 0.38], [0.02, 0.72], [0.98, 0.72], [0.75, 0.02]])}
      {tagPlate(b, id, name)}
      {statusBeacon(b, status, selected)}
    </g>
  );
}
