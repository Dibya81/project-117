import { assetDefs, basePlate, palette, ports, statusBeacon, tagPlate, type EquipmentAssetProps } from "./shared";

export function Boiler({ box: b, id, name = "Boiler", status, selected }: EquipmentAssetProps) {
  return (
    <g data-equipment-asset="boiler">
      {assetDefs("eq-boiler")}
      <g filter="url(#eq-boiler-shadow)">
        <rect x={b.x + b.w * 0.12} y={b.y + b.h * 0.26} width={b.w * 0.66} height={b.h * 0.42} rx={b.h * 0.18} fill="url(#eq-boiler-warm)" stroke={palette.orange} strokeWidth={1.6} />
        <rect x={b.x + b.w * 0.76} y={b.y + b.h * 0.12} width={b.w * 0.1} height={b.h * 0.58} fill="#cbd5e1" stroke={palette.stroke} strokeWidth={1.2} />
        <path d={`M ${b.x + b.w * 0.18} ${b.y + b.h * 0.36} H ${b.x + b.w * 0.72} M ${b.x + b.w * 0.18} ${b.y + b.h * 0.46} H ${b.x + b.w * 0.72} M ${b.x + b.w * 0.18} ${b.y + b.h * 0.56} H ${b.x + b.w * 0.72}`} stroke="#7c2d12" strokeWidth={1.1} opacity={0.6} />
        <rect x={b.x + b.w * 0.2} y={b.y + b.h * 0.68} width={b.w * 0.5} height={b.h * 0.14} rx={2} fill="#3d2618" stroke="#2a1a10" strokeWidth={1.1} />
        <circle cx={b.x + b.w * 0.33} cy={b.y + b.h * 0.75} r={b.h * 0.035} fill="#f59e0b" />
        <circle cx={b.x + b.w * 0.48} cy={b.y + b.h * 0.75} r={b.h * 0.035} fill="#f59e0b" />
        {basePlate(b, 0.82)}
      </g>
      {ports(b, [[0.02, 0.47], [0.98, 0.47], [0.81, 0.12], [0.44, 0.86]])}
      {tagPlate(b, id, name)}
      {statusBeacon(b, status, selected)}
    </g>
  );
}

export function SteamDrum({ box: b, id, name = "Steam Drum", status, selected }: EquipmentAssetProps) {
  return (
    <g data-equipment-asset="steam-drum">
      {assetDefs("eq-steam-drum")}
      <g filter="url(#eq-steam-drum-shadow)">
        <rect x={b.x + b.w * 0.14} y={b.y + b.h * 0.33} width={b.w * 0.72} height={b.h * 0.34} rx={b.h * 0.17} fill="url(#eq-steam-drum-steel)" stroke={palette.stroke} strokeWidth={1.5} />
        <line x1={b.x + b.w * 0.22} y1={b.y + b.h * 0.42} x2={b.x + b.w * 0.78} y2={b.y + b.h * 0.42} stroke={palette.highlight} strokeWidth={1.7} opacity={0.75} />
        <path d={`M ${b.x + b.w * 0.32} ${b.y + b.h * 0.33} V ${b.y + b.h * 0.18} M ${b.x + b.w * 0.66} ${b.y + b.h * 0.33} V ${b.y + b.h * 0.18}`} stroke="#475569" strokeWidth={2.2} strokeLinecap="round" />
        <path d={`M ${b.x + b.w * 0.26} ${b.y + b.h * 0.67} v ${b.h * 0.12} M ${b.x + b.w * 0.74} ${b.y + b.h * 0.67} v ${b.h * 0.12}`} stroke="#475569" strokeWidth={2} />
      </g>
      {ports(b, [[0.02, 0.5], [0.98, 0.5], [0.32, 0.18], [0.66, 0.18], [0.5, 0.82]])}
      {tagPlate(b, id, name)}
      {statusBeacon(b, status, selected)}
    </g>
  );
}
