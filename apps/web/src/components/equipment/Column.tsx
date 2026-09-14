import { assetDefs, ladder, palette, platform, ports, statusBeacon, tagPlate, verticalShell, type EquipmentAssetProps } from "./shared";

export function Column({ box: b, id, name, status, selected, variant = "fractionation" }: EquipmentAssetProps) {
  const trayCount = variant === "vacuum" ? 7 : variant === "atmospheric" ? 12 : 10;
  const fill = variant === "vacuum" ? `url(#eq-column-violet)` : `url(#eq-column-steel)`;
  return (
    <g data-equipment-asset={`${variant}-column`}>
      {assetDefs("eq-column")}
      <g filter="url(#eq-column-shadow)">
        {verticalShell(b, fill, { top: 0.06, bottom: 0.86 })}
        <g stroke="rgba(51,65,85,0.48)" strokeWidth={1.15}>
          {Array.from({ length: trayCount }, (_, i) => {
            const y = b.y + b.h * 0.14 + (i * b.h * 0.63) / Math.max(1, trayCount - 1);
            return <line key={i} x1={b.x + b.w * 0.22} y1={y} x2={b.x + b.w * 0.78} y2={y} />;
          })}
        </g>
        <line x1={b.x + b.w * 0.34} y1={b.y + b.h * 0.86} x2={b.x + b.w * 0.34} y2={b.y + b.h} stroke={palette.stroke} strokeWidth={2} />
        <line x1={b.x + b.w * 0.66} y1={b.y + b.h * 0.86} x2={b.x + b.w * 0.66} y2={b.y + b.h} stroke={palette.stroke} strokeWidth={2} />
        {[0.24, 0.42, 0.6].map((py) => <line key={py} x1={b.x + b.w * 0.8} y1={b.y + b.h * py} x2={b.x + b.w} y2={b.y + b.h * py} stroke={palette.stroke} strokeWidth={1.4} />)}
      </g>
      {platform(b, 0.36)}
      {platform(b, 0.62)}
      {ladder(b, "right", 0.13, 0.82)}
      {ports(b, [[0.5, 0.03], [0.98, 0.24], [0.98, 0.42], [0.98, 0.6], [0.5, 0.98], [0.02, 0.76]])}
      {tagPlate(b, id, name)}
      {statusBeacon(b, status, selected)}
    </g>
  );
}

export function AtmosphericDistillationColumn(props: EquipmentAssetProps) {
  return <Column {...props} variant="atmospheric" />;
}

export function VacuumDistillationColumn(props: EquipmentAssetProps) {
  return <Column {...props} variant="vacuum" />;
}

export function FractionationColumn(props: EquipmentAssetProps) {
  return <Column {...props} variant="fractionation" />;
}
