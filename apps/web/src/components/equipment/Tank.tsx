import { assetDefs, basePlate, ladder, palette, ports, statusBeacon, tagPlate, type EquipmentAssetProps } from "./shared";

export function Tank(props: EquipmentAssetProps) {
  const { box: b, id, name, status, selected, variant = "storage" } = props;
  const fill = variant === "product" ? `url(#eq-tank-cool)` : `url(#eq-tank-steel)`;
  const roofY = b.y + b.h * 0.18;
  const shellH = b.h * 0.58;
  return (
    <g data-equipment-asset={`tank-${variant}`}>
      {assetDefs("eq-tank")}
      <g filter="url(#eq-tank-shadow)">
        <rect x={b.x + b.w * 0.1} y={roofY} width={b.w * 0.8} height={shellH} fill={fill} stroke={palette.stroke} strokeWidth={1.7} />
        <ellipse cx={b.x + b.w * 0.5} cy={roofY} rx={b.w * 0.4} ry={b.h * 0.07} fill="#dbe7f2" stroke={palette.stroke} strokeWidth={1.5} />
        <ellipse cx={b.x + b.w * 0.5} cy={roofY + shellH} rx={b.w * 0.4} ry={b.h * 0.07} fill="#b6c8da" stroke={palette.stroke} strokeWidth={1.5} />
        <path d={`M ${b.x + b.w * 0.13} ${roofY + shellH * 0.34} H ${b.x + b.w * 0.87} M ${b.x + b.w * 0.13} ${roofY + shellH * 0.68} H ${b.x + b.w * 0.87}`} stroke="#8aa0b7" strokeWidth={1} strokeDasharray="4 3" />
        <rect x={b.x + b.w * 0.83} y={b.y + b.h * 0.36} width={b.w * 0.036} height={b.h * 0.28} rx={2} fill={variant === "crude" ? palette.amber : palette.cyan} opacity={0.86} />
        <line x1={b.x + b.w * 0.1} y1={roofY + shellH} x2={b.x + b.w * 0.02} y2={b.y + b.h * 0.94} stroke="#7c8fa4" strokeWidth={1.4} />
        <line x1={b.x + b.w * 0.9} y1={roofY + shellH} x2={b.x + b.w * 0.98} y2={b.y + b.h * 0.94} stroke="#7c8fa4" strokeWidth={1.4} />
        {basePlate(b, 0.93)}
      </g>
      {ladder(b, "left", 0.23, 0.78)}
      {ports(b, [[0.02, 0.62], [0.98, 0.62], [0.5, 0.13]])}
      {tagPlate(b, id, name)}
      {statusBeacon(b, status, selected)}
    </g>
  );
}

export function VerticalTank(props: EquipmentAssetProps) {
  return <Tank {...props} variant="vertical" />;
}

export function ProductStorageTank(props: EquipmentAssetProps) {
  return <Tank {...props} variant="product" />;
}

export function CrudeStorageTank(props: EquipmentAssetProps) {
  return <Tank {...props} variant="crude" />;
}
