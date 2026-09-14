import { assetDefs, ladder, palette, ports, statusBeacon, tagPlate, verticalShell, type EquipmentAssetProps } from "./shared";

export function AmineUnit({ box: b, id, name, status, selected }: EquipmentAssetProps) {
  return (
    <g data-equipment-asset="amine-treating-unit">
      {assetDefs("eq-amine")}
      <g filter="url(#eq-amine-shadow)">
        {verticalShell(b, "url(#eq-amine-green)", { top: 0.12, bottom: 0.86 })}
        <rect x={b.x + b.w * 0.58} y={b.y + b.h * 0.28} width={b.w * 0.24} height={b.h * 0.36} rx={3} fill="#d1fae5" stroke={palette.green} strokeWidth={1.3} />
        <path d={`M ${b.x + b.w * 0.24} ${b.y + b.h * 0.34} H ${b.x + b.w * 0.78} M ${b.x + b.w * 0.24} ${b.y + b.h * 0.56} H ${b.x + b.w * 0.78}`} stroke="#059669" strokeWidth={1.2} />
      </g>
      {ladder(b, "left", 0.22, 0.78)}
      {ports(b, [[0.02, 0.58], [0.98, 0.38], [0.5, 0.05], [0.5, 0.98]])}
      {tagPlate(b, id, name)}
      {statusBeacon(b, status, selected)}
    </g>
  );
}
