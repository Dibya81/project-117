import { assetDefs, horizontalVesselShell, legs, palette, ports, statusBeacon, tagPlate, type EquipmentAssetProps } from "./shared";

export function Desalter({ box: b, id, name, status, selected }: EquipmentAssetProps) {
  return (
    <g data-equipment-asset="desalter">
      {assetDefs("eq-desalter")}
      <g filter="url(#eq-desalter-shadow)">
        {legs(b, 2)}
        {horizontalVesselShell(b, "url(#eq-desalter-steel)")}
        <g stroke={palette.blue} strokeWidth={1.4}>
          <circle cx={b.x + b.w * 0.34} cy={b.y + b.h * 0.51} r={b.h * 0.055} fill="#dbeafe" />
          <circle cx={b.x + b.w * 0.66} cy={b.y + b.h * 0.51} r={b.h * 0.055} fill="#dbeafe" />
          <path d={`M ${b.x + b.w * 0.22} ${b.y + b.h * 0.42} H ${b.x + b.w * 0.78} M ${b.x + b.w * 0.22} ${b.y + b.h * 0.6} H ${b.x + b.w * 0.78}`} />
        </g>
        <path d={`M ${b.x + b.w * 0.3} ${b.y + b.h * 0.28} V ${b.y + b.h * 0.18} H ${b.x + b.w * 0.7} V ${b.y + b.h * 0.28}`} fill="none" stroke={palette.stroke} strokeWidth={1.2} />
      </g>
      {ports(b, [[0.02, 0.51], [0.98, 0.51], [0.5, 0.17], [0.5, 0.87]])}
      {tagPlate(b, id, name)}
      {statusBeacon(b, status, selected)}
    </g>
  );
}
