import { assetDefs, ladder, palette, platform, ports, statusBeacon, tagPlate, type EquipmentAssetProps } from "./shared";

export function FCC({ box: b, id, name, status, selected }: EquipmentAssetProps) {
  return (
    <g data-equipment-asset="fcc-unit">
      {assetDefs("eq-fcc")}
      <g filter="url(#eq-fcc-shadow)">
        <rect x={b.x + b.w * 0.16} y={b.y + b.h * 0.08} width={b.w * 0.48} height={b.h * 0.48} rx={5} fill="url(#eq-fcc-cool)" stroke={palette.cyan} strokeWidth={1.7} />
        <ellipse cx={b.x + b.w * 0.4} cy={b.y + b.h * 0.08} rx={b.w * 0.24} ry={b.h * 0.035} fill="#cffafe" stroke={palette.cyan} strokeWidth={1.2} />
        <rect x={b.x + b.w * 0.36} y={b.y + b.h * 0.58} width={b.w * 0.44} height={b.h * 0.34} rx={5} fill="url(#eq-fcc-violet)" stroke={palette.violet} strokeWidth={1.7} />
        <path d={`M ${b.x + b.w * 0.34} ${b.y + b.h * 0.56} C ${b.x + b.w * 0.18} ${b.y + b.h * 0.68}, ${b.x + b.w * 0.2} ${b.y + b.h * 0.84}, ${b.x + b.w * 0.36} ${b.y + b.h * 0.85}`} fill="none" stroke={palette.cyan} strokeWidth={3} />
        <path d={`M ${b.x + b.w * 0.58} ${b.y + b.h * 0.56} V ${b.y + b.h * 0.68} H ${b.x + b.w * 0.36}`} fill="none" stroke={palette.violet} strokeWidth={3} />
        <g stroke="#0891b2" strokeWidth={1.1}>{Array.from({ length: 4 }, (_, i) => <line key={i} x1={b.x + b.w * 0.22} y1={b.y + b.h * (0.18 + i * 0.07)} x2={b.x + b.w * 0.58} y2={b.y + b.h * (0.18 + i * 0.07)} />)}</g>
      </g>
      {platform(b, 0.52)}
      {ladder(b, "right", 0.15, 0.88)}
      {ports(b, [[0.02, 0.36], [0.98, 0.75], [0.5, 0.02], [0.3, 0.98]])}
      {tagPlate(b, id, name)}
      {statusBeacon(b, status, selected)}
    </g>
  );
}
